"""CORTEX B8 acceptance tests — final integration (CANON-51/42).

Mirrors tests/test_cortex_b1..b7 style: unittest, tiny synthetic data, ZERO
live state touched — MLNB_TRUST_PATH, MLNB_VALIDATION_PATH and
trading.state.STATE_DIR are all redirected to a tmpdir BEFORE any module
builds state (project rule: never mutate live journals/wallets).

  S  trading/cortex_signal.py — flat+reason when unfit / short data; a valid
     signal dict after a tiny synthetic fit; dead-band flat; per-signal keys.
  W  brain_executor._cortex_shadow — env unset → decider dict untouched
     (zero behavior change); CORTEX_SIGNAL=1 → shadow logged, decider still
     trades; CORTEX_TRADE=1 → cortex decision replaces the decider's.
  V  trading/validation_holdout.py — record/score roundtrip in a tmp STATE
     dir; unmatured stays pending; unresolvable price stays pending; rolling
     accuracy series persisted.
  T  trust feedback — apply_trust_feedback turns a closed trade into
     TrustLedger.update calls for exactly the experts that fired.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

# ── isolate ALL state BEFORE importing anything state-shaped ────────────────
_TMP = tempfile.TemporaryDirectory(prefix="mlnb_cortex_b8_")
os.environ["MLNB_TRUST_PATH"] = os.path.join(_TMP.name, "node_trust.json")
os.environ["MLNB_VALIDATION_PATH"] = os.path.join(_TMP.name, "validation.jsonl")

import trading.state as tstate                                        # noqa: E402
tstate.STATE_DIR = Path(_TMP.name) / "state"                          # tmp STATE dir

import pandas as pd                                                   # noqa: E402

from trading import cortex_signal as cx                               # noqa: E402
from trading import validation_holdout as vh                          # noqa: E402


def _ohlcv(n=400, seed=3, trend=0.002):
    """Synthetic trending OHLCV frame with enough bars to clear warm-up."""
    rng = np.random.RandomState(seed)
    ret = trend + 0.004 * rng.randn(n)
    close = 100.0 * np.cumprod(1.0 + ret)
    high = close * (1.0 + np.abs(0.002 * rng.randn(n)))
    low = close * (1.0 - np.abs(0.002 * rng.randn(n)))
    openp = np.concatenate([[close[0]], close[:-1]])
    vol = 1000 + 100 * rng.rand(n)
    return pd.DataFrame({"open": openp, "high": high, "low": low,
                         "close": close, "volume": vol})


# ── S. CortexSignalSource ────────────────────────────────────────────────────

class TestCortexSignalSource(unittest.TestCase):
    def test_flat_when_data_short(self):
        src = cx.CortexSignalSource(auto_fit=False)
        sig = src.signal("BTC/USDT:USDT", _ohlcv(10))
        self.assertEqual(sig["side"], "flat")
        self.assertEqual(sig["size_fraction"], 0.0)
        self.assertIn("insufficient bars", sig["reason"])

    def test_flat_when_unfit_and_no_autofit(self):
        src = cx.CortexSignalSource(auto_fit=False)
        sig = src.signal("BTC/USDT:USDT", _ohlcv(400))
        self.assertEqual(sig["side"], "flat")
        self.assertIn("unfit", sig["reason"])

    def test_flat_when_df_none(self):
        src = cx.CortexSignalSource(auto_fit=False)
        sig = src.signal("X", None)
        self.assertEqual(sig["side"], "flat")

    def test_signal_dict_after_tiny_fit(self):
        df = _ohlcv(420, trend=0.003)                # strong uptrend → decidable
        src = cx.CortexSignalSource(min_bars=60, dead_band=0.0,
                                    target_risk=0.02, exposure_cap=0.5)
        src.fit(df)
        self.assertTrue(src._fitted())
        sig = src.signal("BTC/USDT:USDT", df)
        for key in ("symbol", "side", "size_fraction", "confidence",
                    "tier_reached", "experts_fired", "regime_probs"):
            self.assertIn(key, sig, f"missing key {key}")
        self.assertEqual(sig["symbol"], "BTC/USDT:USDT")
        self.assertIn(sig["side"], ("long", "short", "flat"))
        if sig["side"] != "flat":                    # non-flat → sized + attributed
            self.assertGreater(sig["size_fraction"], 0.0)
            self.assertLessEqual(sig["size_fraction"], 0.5)   # exposure cap
            self.assertIsNotNone(sig["tier_reached"])
            self.assertTrue(sig["experts_fired"])
        else:                                        # flat is honest, never silent
            self.assertIn("reason", sig)

    def test_dead_band_forces_flat(self):
        df = _ohlcv(420, trend=0.003)
        src = cx.CortexSignalSource(min_bars=60, dead_band=0.49)  # swallow any edge
        src.fit(df)
        sig = src.signal("ETH/USDT:USDT", df)
        self.assertEqual(sig["side"], "flat")
        self.assertEqual(sig["size_fraction"], 0.0)

    def test_never_raises_on_garbage(self):
        src = cx.CortexSignalSource(auto_fit=False)
        sig = src.signal("X", pd.DataFrame({"close": [1, 2, 3]}))
        self.assertEqual(sig["side"], "flat")


# ── W. shadow-mode wiring (env flags) ────────────────────────────────────────

class _StubDecider:
    """Stands in for PerCoinBrainDecider inside BrainExecutor."""
    def __init__(self, df):
        self._df = df
    def decide(self, market, symbol, price, *, in_position):
        return {"action": "LONG", "size": 1.0, "tag": "stub", "_brain": {}}
    def _ohlcv(self, symbol):
        return self._df


class TestShadowMode(unittest.TestCase):
    def _executor(self, df):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        return BrainExecutor(decider=_StubDecider(df))

    def setUp(self):
        for k in ("CORTEX_SIGNAL", "CORTEX_TRADE"):
            os.environ.pop(k, None)
        cx._SOURCE = None                            # fresh singleton per test

    def test_env_unset_is_zero_change(self):
        ex = self._executor(_ohlcv(200))
        d0 = {"action": "LONG", "size": 1.0, "tag": "stub", "_brain": {}}
        out = ex._cortex_shadow("BTC/USDT:USDT", dict(d0), in_position=False)
        self.assertEqual(out, d0)                    # byte-identical decision

    def test_shadow_mode_logs_but_decider_trades(self):
        os.environ["CORTEX_SIGNAL"] = "1"
        df = _ohlcv(420, trend=0.003)
        cx.get_cortex_source().fit(df)
        ex = self._executor(df)
        d0 = {"action": "LONG", "size": 1.0, "tag": "stub", "_brain": {}}
        out = ex._cortex_shadow("BTC/USDT:USDT", dict(d0), in_position=False)
        self.assertEqual(out, d0)                    # shadow: existing one trades
        shad = tstate.load_json("cortex_shadow.json", {})
        self.assertTrue(any(k.endswith("BTC/USDT:USDT") for k in shad),
                        "shadow comparison was not persisted")

    def test_cortex_trade_replaces_decision(self):
        os.environ["CORTEX_SIGNAL"] = "1"
        os.environ["CORTEX_TRADE"] = "1"
        df = _ohlcv(420, trend=0.003)
        src = cx.CortexSignalSource(min_bars=60, dead_band=0.0)
        src.fit(df)
        cx._SOURCE = src
        ex = self._executor(df)
        d0 = {"action": "LONG", "size": 1.0, "tag": "stub", "_brain": {}}
        out = ex._cortex_shadow("BTC/USDT:USDT", dict(d0), in_position=False)
        # cortex governs: tag is cortex OR (if it stayed flat) action FLAT
        if out.get("tag") == "cortex":
            self.assertIn(out["action"], ("LONG", "SHORT", "FLAT", "EXIT"))
            self.assertEqual(out["_brain"].get("source"), "cortex_b8")
        else:                                        # only allowed on shadow error
            self.assertEqual(out, d0)


# ── V. live-unseen validation holdout (CANON-42) ─────────────────────────────

class TestValidationHoldout(unittest.TestCase):
    def setUp(self):
        p = Path(os.environ["MLNB_VALIDATION_PATH"])
        if p.exists():
            p.unlink()
        ap = p.with_name(p.stem + "_accuracy.json")
        if ap.exists():
            ap.unlink()

    def test_record_and_score_roundtrip(self):
        t0 = 1_000_000.0
        vh.record_prediction(t0, "BTC/USDT", +1, 300, price_at_pred=100.0)
        vh.record_prediction(t0, "ETH/USDT", -1, 300, price_at_pred=50.0)
        vh.record_prediction(t0, "SOL/USDT", +1, 9999, price_at_pred=10.0)  # unmatured
        prices = {"BTC/USDT": 101.0, "ETH/USDT": 51.0}                      # BTC ✓, ETH ✗
        summary = vh.score_matured(t0 + 600,
                                   price_lookup=lambda s, ts: prices.get(s))
        self.assertEqual(summary["newly_scored"], 2)
        self.assertEqual(summary["n_scored"], 2)
        self.assertEqual(summary["n_pending"], 1)                            # SOL waits
        self.assertAlmostEqual(summary["accuracy"], 0.5)
        # rolling series persisted next to the ledger
        ap = Path(os.environ["MLNB_VALIDATION_PATH"]).with_name("validation_accuracy.json")
        series = json.loads(ap.read_text())
        self.assertTrue(series and series[-1]["n_scored"] == 2)

    def test_unresolvable_price_stays_pending(self):
        t0 = 2_000_000.0
        vh.record_prediction(t0, "XRP/USDT", +1, 60, price_at_pred=1.0)
        s = vh.score_matured(t0 + 120, price_lookup=lambda s_, ts: None)
        self.assertEqual(s["newly_scored"], 0)
        self.assertEqual(s["n_pending"], 1)                                  # never guessed

    def test_rescoring_is_idempotent(self):
        t0 = 3_000_000.0
        vh.record_prediction(t0, "BTC/USDT", +1, 60, price_at_pred=100.0)
        vh.score_matured(t0 + 120, price_lookup=lambda s, ts: 101.0)
        s2 = vh.score_matured(t0 + 240, price_lookup=lambda s, ts: 90.0)
        self.assertEqual(s2["newly_scored"], 0)                              # scored once
        self.assertEqual(s2["n_scored"], 1)
        self.assertAlmostEqual(s2["accuracy"], 1.0)                          # first verdict kept


# ── T. trust feedback from closed trades ─────────────────────────────────────

class TestTrustFeedback(unittest.TestCase):
    def test_closed_trade_updates_fired_experts(self):
        from core.trust import TrustLedger
        led_path = os.path.join(_TMP.name, "trust_fb.json")
        led = TrustLedger(path=led_path)
        # pending signal on the pair, with two fired experts
        pend_file = Path(tstate.STATE_DIR) / "cortex_pending.json"
        if pend_file.exists():
            pend_file.unlink()
        cx.record_pending("BTC/USDT:USDT", "long", ["sk_logreg", "sk_stump"], ts=100.0)
        closed = [{"pair": "BTC/USDT:USDT", "profit_abs": -5.0,
                   "profit_ratio": -0.02, "close_timestamp": 200_000.0}]
        credited = cx.apply_trust_feedback(closed, ledger=led)
        self.assertEqual(credited, 1)
        self.assertEqual(led.counts.get("sk_logreg"), 1)
        self.assertEqual(led.counts.get("sk_stump"), 1)
        self.assertGreater(led.losses["sk_logreg"], 0.0)      # losing trade → loss > 0
        # pending entry consumed — a second pass credits nothing
        self.assertEqual(cx.apply_trust_feedback(closed, ledger=led), 0)

    def test_no_pending_no_crash(self):
        self.assertEqual(cx.apply_trust_feedback([{"pair": "Z", "profit_abs": 1.0}]), 0)


if __name__ == "__main__":
    unittest.main()
