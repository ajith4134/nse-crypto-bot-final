"""Trading Phase T8.9 (end-to-end brain trading pipeline + safety) acceptance tests.

Fully OFFLINE + deterministic. Exercises trading.brain.pipeline.BrainTradingPipeline,
which stitches the whole T8 stack (features → regime → pattern/anomaly → news →
strategy signal → experience recall → regime/anomaly entry gate → T3 safety gate) into
ONE traced, safety-gated decision per market.

Every component is INJECTED with seeded/stubbed doubles (a seeded geometric-walk OHLCV,
a seeded DEAP strategy, a seed-0 GaussianHMM regime model, a stub news fetcher, an empty
in-memory experience bank, a no-op kill-switch, a non-persisting circuit breaker), so the
suite touches no network/broker/disk and is reproducible on every run.
"""
from __future__ import annotations

import unittest
import warnings

warnings.filterwarnings("ignore")

import json

import numpy as np
import pandas as pd

from trading.brain.entryexit import EntryExitPolicy
from trading.brain.experience import ExperienceBank
from trading.brain.news import NewsItem, NewsResearcher
from trading.brain.observability import BrainTracer
from trading.brain.patterns import PatternScanner
from trading.brain.pipeline import BrainTradingPipeline
from trading.brain.regime import RegimeModel
from trading.execution.circuit_breaker import DailyCircuitBreaker
from trading.execution.kill_switch import KillSwitch
from trading.strategy.genome import random_strategy
from trading.strategy.operators import market_features

_SEED = 20260628
_DECISION_KEYS = {
    "symbol", "market", "regime", "anomaly_score", "news_compound", "news_p",
    "signal", "recall_bias", "recall_confidence", "entry", "action", "confidence",
    "safety_blocked", "safety_reason",
}


def _make_ohlcv(n: int = 700, seed: int = _SEED) -> pd.DataFrame:
    """Deterministic geometric random-walk OHLCV (~n bars); envelope invariants hold."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.012, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    wig = np.abs(rng.normal(0.0, 0.004, n))
    high = np.maximum(open_, close) * (1.0 + wig)
    low = np.minimum(open_, close) * (1.0 - wig)
    volume = rng.uniform(1_000.0, 5_000.0, n)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all()
    return df


# computed once for the whole suite (deterministic)
_OHLCV = _make_ohlcv()
_REGIME = RegimeModel(seed=0).fit(_OHLCV)


def _stub_news():
    return [
        NewsItem(title="BTCUSDT rallies on strong demand",
                 summary="great bullish breakout, record gains", source="stub"),
        NewsItem(title="Market upbeat", summary="positive outlook", source="stub"),
    ]


def _strategy(market="CRYPTO", seed=_SEED):
    return random_strategy(market_features(market), np.random.default_rng(seed),
                           market=market, strat_id="evolved")


def _full_pipeline(market="CRYPTO", *, kill=None, breaker=None, strat_seed=_SEED):
    """A pipeline wired with every (deterministic) component."""
    return BrainTradingPipeline(
        market=market,
        evolved_strategy=_strategy(market, strat_seed),
        regime_model=RegimeModel(seed=0).fit(_OHLCV) if market == "CRYPTO" else
        RegimeModel(seed=0).fit(_OHLCV),
        pattern_scanner=PatternScanner(),
        news=NewsResearcher(fetcher=_stub_news),
        experience=ExperienceBank(use_lancedb=False),
        entryexit=EntryExitPolicy(allowed_regimes=("bull", "bear", "neutral")),
        tracer=BrainTracer(),
        kill_switch=kill,
        breaker=breaker,
    )


def _assert_no_numpy(case: unittest.TestCase, obj, path="root"):
    """Recursively assert no numpy scalar/array types leak into a payload."""
    if isinstance(obj, np.generic) or isinstance(obj, np.ndarray):
        case.fail(f"numpy type leaked at {path}: {type(obj)!r}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_numpy(case, v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_no_numpy(case, v, f"{path}[{i}]")


class TestDecideContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dec = _full_pipeline().decide("BTCUSDT", _OHLCV)

    def test_returns_all_documented_keys(self):
        self.assertEqual(set(self.dec), _DECISION_KEYS)

    def test_action_in_allowed_set(self):
        self.assertIn(self.dec["action"], {"LONG", "SHORT", "FLAT"})

    def test_confidence_in_unit_interval(self):
        self.assertIsInstance(self.dec["confidence"], float)
        self.assertGreaterEqual(self.dec["confidence"], 0.0)
        self.assertLessEqual(self.dec["confidence"], 1.0)

    def test_anomaly_score_is_float(self):
        self.assertIsInstance(self.dec["anomaly_score"], float)

    def test_news_p_in_unit_interval(self):
        self.assertIsInstance(self.dec["news_p"], float)
        self.assertGreaterEqual(self.dec["news_p"], 0.0)
        self.assertLessEqual(self.dec["news_p"], 1.0)

    def test_entry_is_dict_and_safety_flags(self):
        self.assertIsInstance(self.dec["entry"], dict)
        self.assertIsInstance(self.dec["safety_blocked"], bool)
        self.assertEqual(self.dec["safety_blocked"], False)


class TestTracing(unittest.TestCase):
    def setUp(self):
        self.pipe = _full_pipeline()
        self.pipe.decide("BTCUSDT", _OHLCV)

    def test_stream_of_mind_nonempty(self):
        som = self.pipe.tracer.stream_of_mind()
        self.assertTrue(som)
        self.assertEqual(som, self.pipe.status()["stream_of_mind"])

    def test_records_regime_and_decision_steps(self):
        names = [s.name for s in self.pipe.tracer._spans]
        self.assertIn("regime", names)
        self.assertIn("decision", names)


class TestSafetyGate(unittest.TestCase):
    def test_kill_switch_blocks_to_flat(self):
        kill = KillSwitch(cancel_all=lambda: [], flatten_all=lambda: [])
        pipe = _full_pipeline(kill=kill)
        kill.engage("test")
        dec = pipe.decide("BTCUSDT", _OHLCV)
        self.assertEqual(dec["action"], "FLAT")
        self.assertTrue(dec["safety_blocked"])
        self.assertIn("kill-switch", dec["safety_reason"].lower())
        self.assertFalse(dec["entry"]["enter"])

    def test_tripped_breaker_blocks_to_flat(self):
        breaker = DailyCircuitBreaker(max_daily_loss=1000, persist=False)
        pipe = _full_pipeline(breaker=breaker)
        breaker.record_trade(-2000)
        self.assertFalse(breaker.allow_new_order())
        dec = pipe.decide("BTCUSDT", _OHLCV)
        self.assertEqual(dec["action"], "FLAT")
        self.assertTrue(dec["safety_blocked"])
        self.assertIn("circuit breaker", dec["safety_reason"].lower())

    def test_untripped_breaker_does_not_block(self):
        breaker = DailyCircuitBreaker(max_daily_loss=1000, persist=False)
        pipe = _full_pipeline(breaker=breaker)
        breaker.record_trade(-100)  # within limit
        dec = pipe.decide("BTCUSDT", _OHLCV)
        self.assertFalse(dec["safety_blocked"])

    def test_no_safety_components_decides_cleanly(self):
        pipe = _full_pipeline()  # no kill, no breaker
        dec = pipe.decide("BTCUSDT", _OHLCV)
        self.assertFalse(dec["safety_blocked"])
        self.assertEqual(dec["safety_reason"], "")
        # action must follow the entry gate exactly
        entry = dec["entry"]
        expected = entry["side"] if entry.get("enter") else "FLAT"
        self.assertEqual(dec["action"], expected)


class TestSafetyReview(unittest.TestCase):
    def test_checks_list_includes_expected_checks(self):
        review = _full_pipeline().safety_review()
        names = {c["check"] for c in review["checks"]}
        for needed in ("kill_switch_present", "circuit_breaker_present",
                       "entry_gating_active", "tracer_active"):
            self.assertIn(needed, names)
        self.assertIsInstance(review["passed"], bool)

    def test_components_present_make_checks_true(self):
        kill = KillSwitch(cancel_all=lambda: [], flatten_all=lambda: [])
        breaker = DailyCircuitBreaker(max_daily_loss=1000, persist=False)
        review = _full_pipeline(kill=kill, breaker=breaker).safety_review()
        by = {c["check"]: c["ok"] for c in review["checks"]}
        self.assertTrue(by["kill_switch_present"])
        self.assertTrue(by["circuit_breaker_present"])
        self.assertTrue(by["entry_gating_active"])
        self.assertTrue(by["tracer_active"])
        self.assertTrue(review["passed"])

    def test_missing_safety_components_fail_review(self):
        review = _full_pipeline().safety_review()  # no kill / breaker
        by = {c["check"]: c["ok"] for c in review["checks"]}
        self.assertFalse(by["kill_switch_present"])
        self.assertFalse(by["circuit_breaker_present"])
        self.assertFalse(review["passed"])


class TestDeterminism(unittest.TestCase):
    def test_identical_components_give_identical_decision(self):
        a = _full_pipeline().decide("BTCUSDT", _OHLCV)
        b = _full_pipeline().decide("BTCUSDT", _OHLCV)
        self.assertEqual(a["action"], b["action"])
        self.assertEqual(a["confidence"], b["confidence"])
        self.assertEqual(a["signal"], b["signal"])
        self.assertEqual(a["regime"], b["regime"])


class TestSerialization(unittest.TestCase):
    def test_decide_is_json_serializable(self):
        dec = _full_pipeline().decide("BTCUSDT", _OHLCV)
        json.dumps(dec)
        _assert_no_numpy(self, dec)

    def test_status_is_json_serializable(self):
        pipe = _full_pipeline()
        pipe.decide("BTCUSDT", _OHLCV)
        st = pipe.status()
        json.dumps(st)
        _assert_no_numpy(self, st)

    def test_status_reports_components_and_stream(self):
        pipe = _full_pipeline()
        pipe.decide("BTCUSDT", _OHLCV)
        st = pipe.status()
        self.assertTrue(st["has_strategy"])
        self.assertTrue(st["has_regime_model"])
        self.assertIsInstance(st["stream_of_mind"], list)
        self.assertIn("safety", st)


class TestBothMarkets(unittest.TestCase):
    def test_crypto_market_field(self):
        dec = _full_pipeline("CRYPTO").decide("BTCUSDT", _OHLCV)
        self.assertEqual(dec["market"], "CRYPTO")

    def test_nse_pipeline_runs(self):
        pipe = _full_pipeline("NSE")
        dec = pipe.decide("RELIANCE", _OHLCV)
        self.assertEqual(dec["market"], "NSE")
        self.assertEqual(set(dec), _DECISION_KEYS)
        self.assertIn(dec["action"], {"LONG", "SHORT", "FLAT"})
        json.dumps(dec)


if __name__ == "__main__":
    unittest.main()
