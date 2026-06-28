"""Trading Phase T8.6 acceptance tests — fully offline + deterministic.

Pins the pattern/regime/picking/entry-exit "market-intelligence" layer against
synthetic, seeded OHLCV so CI passes with no broker/exchange/data access:
  • patterns.py  — STUMPY matrix profile, discord (anomaly) + motif discovery,
    anomaly score, TA-Lib candlestick firing, PatternScanner one-call scan.
  • regime.py    — hmmlearn GaussianHMM regime detection + RegimeGate activation.
  • picking.py   — cross-sectional ranking, IC validation, and the VENDORED
    gplearn symbolic factor miner + AssetPicker source selection.
  • entryexit.py — regime/anomaly-gated entry and multi-trigger (incl. learned) exit.

A single synthetic series carries an INJECTED anomaly spike and three distinct
regime segments (trend-up / chop / trend-down). Everything is seeded; the gplearn
miner uses a small population/generations for speed. STUMPY/hmmlearn emit benign
warnings which are suppressed at import time.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import unittest

import numpy as np
import pandas as pd

from trading.brain.continual import OnlineNode
from trading.brain.entryexit import EntryExitPolicy
from trading.brain.patterns import (
    PatternScanner,
    anomaly_score,
    candles_firing,
    find_anomalies,
    find_motifs,
    matrix_profile,
)
from trading.brain.picking import (
    AssetPicker,
    CrossSectionalRanker,
    GPLearnFactorMiner,
)
from trading.brain.regime import RegimeGate, RegimeModel

_WINDOW = 20
_SPIKE_BAR = 300


def _synthetic_ohlcv(n: int = 600, seed: int = 7) -> pd.DataFrame:
    """Deterministic OHLCV with 3 regime segments + an injected anomaly spike.

    Segments: [0, n/3) trend up, [n/3, 2n/3) chop/sideways, [2n/3, n) trend down.
    A sharp one-bar spike is injected at _SPIKE_BAR so the discord/anomaly detectors
    have a known target. Invariants high>=max(open,close), low<=min(open,close) hold.
    """
    rng = np.random.default_rng(seed)
    third = n // 3
    drift = np.concatenate([
        np.full(third, 0.6),                      # up
        np.full(third, 0.0),                      # chop
        np.full(n - 2 * third, -0.6),             # down
    ])
    noise = rng.normal(0.0, 0.4, size=n)
    close = 100.0 + np.cumsum(drift + noise)
    close = np.maximum(close, 1.0)                # keep positive

    # inject a sharp anomaly spike at a known bar
    close[_SPIKE_BAR] += 40.0

    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    body_hi = np.maximum(open_, close)
    body_lo = np.minimum(open_, close)
    wick = np.abs(rng.normal(0.0, 0.5, size=n)) + 0.1
    high = body_hi + wick
    low = body_lo - wick
    low = np.maximum(low, 0.5)
    vol = rng.integers(1000, 5000, size=n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol})


_OHLCV = _synthetic_ohlcv()


class TestSyntheticData(unittest.TestCase):
    def test_ohlcv_invariants(self):
        df = _OHLCV
        self.assertEqual(len(df), 600)
        self.assertTrue((df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all())
        self.assertTrue((df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all())
        self.assertTrue(np.isfinite(df.to_numpy()).all())

    def test_data_is_deterministic(self):
        again = _synthetic_ohlcv()
        self.assertTrue(np.allclose(again["close"].to_numpy(),
                                    _OHLCV["close"].to_numpy()))


class TestPatterns(unittest.TestCase):
    def setUp(self):
        self.close = _OHLCV["close"]

    def test_matrix_profile_length_and_finite(self):
        P = matrix_profile(self.close, m=_WINDOW)
        self.assertEqual(len(P), len(self.close) - _WINDOW + 1)
        self.assertTrue(np.isfinite(P).all())

    def test_find_anomalies_count_and_near_spike(self):
        anoms = find_anomalies(self.close, m=_WINDOW, k=3)
        self.assertEqual(len(anoms), 3)
        for a in anoms:
            self.assertIn("index", a)
            self.assertIn("distance", a)
        # the top discord window should overlap the injected spike bar
        top_idx = anoms[0]["index"]
        self.assertLessEqual(abs(top_idx - _SPIKE_BAR), _WINDOW)
        # discords are sorted largest-distance first
        dists = [a["distance"] for a in anoms]
        self.assertEqual(dists, sorted(dists, reverse=True))

    def test_find_motifs_valid(self):
        motifs = find_motifs(self.close, m=_WINDOW, k=3)
        self.assertLessEqual(len(motifs), 3)   # ≤k (may be empty on a pure random walk)
        for mtf in motifs:
            self.assertTrue(len(mtf["indices"]) >= 1)
            for i in mtf["indices"]:
                self.assertTrue(0 <= i < len(self.close))
            self.assertTrue(np.isfinite(mtf["distance"]))

    def test_anomaly_score_positive(self):
        self.assertGreater(anomaly_score(self.close, m=_WINDOW), 0.0)

    def test_candles_firing_dict_of_signs(self):
        firing = candles_firing(_OHLCV)
        self.assertIsInstance(firing, dict)
        for nm, sig in firing.items():
            self.assertIn(sig, (-1, 1))

    def test_scanner_keys_and_engine(self):
        out = PatternScanner(window=_WINDOW).scan(_OHLCV, k=3)
        for key in ("window", "motifs", "anomalies", "anomaly_score",
                    "candles_firing", "engine"):
            self.assertIn(key, out)
        self.assertEqual(out["window"], _WINDOW)
        self.assertEqual(out["engine"], "stumpy")
        self.assertEqual(len(out["anomalies"]), 3)


class TestRegime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = RegimeModel(n_states=3, seed=0, n_iter=50).fit(_OHLCV)

    def test_predict_labels_valid_vocab(self):
        labels = self.model.predict_labels(_OHLCV)
        self.assertEqual(len(labels), len(_OHLCV))
        self.assertTrue(set(labels) <= {"bull", "bear", "neutral"})

    def test_multiple_regimes_detected(self):
        labels = self.model.predict_labels(_OHLCV)
        self.assertGreaterEqual(len(set(labels)), 2)

    def test_current_regime_is_str(self):
        reg = self.model.current_regime(_OHLCV)
        self.assertIsInstance(reg, str)
        self.assertIn(reg, {"bull", "bear", "neutral"})

    def test_status_fitted(self):
        st = self.model.status()
        self.assertTrue(st["fitted"])
        self.assertEqual(st["n_states"], 3)

    def test_predict_states_ints(self):
        states = self.model.predict_states(_OHLCV)
        self.assertEqual(len(states), len(_OHLCV))
        self.assertTrue(set(np.unique(states)) <= {0, 1, 2})

    def test_gate_allows_and_blocks(self):
        gate = RegimeGate(allowed={"breakout": ("bull",)})
        self.assertTrue(gate.is_active("breakout", "bull"))
        self.assertFalse(gate.is_active("breakout", "bear"))
        # unknown strategy -> default allows everything
        self.assertTrue(gate.is_active("anything", "neutral"))

    def test_gate_activate_filters(self):
        gate = RegimeGate(allowed={"breakout": ("bull",), "meanrev": ("neutral",)})
        active = gate.activate(["breakout", "meanrev"], "bull")
        self.assertEqual(active, ["breakout"])


class TestPicking(unittest.TestCase):
    def _universe(self):
        # higher momentum / lower vol should rank first under default weights
        return {
            "AAA": {"mom": 2.0, "ret": 0.05, "vol": 0.1, "atr_pct": 0.1},
            "BBB": {"mom": 0.0, "ret": 0.00, "vol": 0.3, "atr_pct": 0.3},
            "CCC": {"mom": -2.0, "ret": -0.05, "vol": 0.6, "atr_pct": 0.6},
        }

    def test_ranker_orders_and_ranks(self):
        ranked = CrossSectionalRanker().rank(self._universe())
        self.assertEqual([r["symbol"] for r in ranked], ["AAA", "BBB", "CCC"])
        self.assertEqual([r["rank"] for r in ranked], [1, 2, 3])

    def test_validate_perfect_factor(self):
        fwd = [1.0, 2.0, 3.0, 4.0, 5.0]
        res = CrossSectionalRanker.validate([10, 20, 30, 40, 50], fwd)
        self.assertAlmostEqual(res["ic"], 1.0, places=6)
        self.assertTrue(res["tradeable"])

    def test_select_top(self):
        top = CrossSectionalRanker().select_top(self._universe(), k=2)
        self.assertEqual(top, ["AAA", "BBB"])

    def _miner_data(self, n=200, seed=0):
        rng = np.random.default_rng(seed)
        X = rng.normal(0.0, 1.0, size=(n, 2))
        fwd = X[:, 0] - 0.5 * X[:, 1] + rng.normal(0.0, 0.05, size=n)
        return X, fwd

    def test_gplearn_miner_learns_factor(self):
        X, fwd = self._miner_data()
        miner = GPLearnFactorMiner(["x0", "x1"], generations=5,
                                   population=300, seed=0).fit(X, fwd)
        prog = miner.program()
        self.assertTrue(len(prog) > 0)
        f = miner.factor(X)
        self.assertEqual(len(f), len(X))
        ic = CrossSectionalRanker.validate(f, fwd)["ic"]
        self.assertGreater(ic, 0.3)

    def test_asset_picker_with_miner_is_gplearn(self):
        X, fwd = self._miner_data()
        miner = GPLearnFactorMiner(["x0", "x1"], generations=5,
                                   population=300, seed=0).fit(X, fwd)
        picker = AssetPicker(miner=miner, top_k=2)
        # forward return ~ x0 - 0.5*x1 -> high-x0/low-x1 should be picked first
        universe = {
            "HI": {"x0": 3.0, "x1": -2.0},
            "MID": {"x0": 0.0, "x1": 0.0},
            "LO": {"x0": -3.0, "x1": 2.0},
        }
        res = picker.pick(universe)
        self.assertEqual(res["factor_source"], "gplearn")
        self.assertEqual(res["n_universe"], 3)
        self.assertEqual(res["top"][0], "HI")
        self.assertNotIn("LO", res["top"])

    def test_asset_picker_without_miner_is_composite(self):
        res = AssetPicker(top_k=2).pick(self._universe())
        self.assertEqual(res["factor_source"], "composite")
        self.assertEqual(res["top"][0], "AAA")

    def test_picker_status(self):
        st = AssetPicker(top_k=3).status()
        self.assertEqual(st["top_k"], 3)
        self.assertIsNone(st["miner"])


class TestEntryExit(unittest.TestCase):
    def setUp(self):
        self.policy = EntryExitPolicy(allowed_regimes=("bull", "bear"),
                                      max_anomaly=3.0)

    # ── entry ────────────────────────────────────────────────────────────────
    def test_enter_true_in_allowed_regime(self):
        res = self.policy.should_enter(signal=1, regime="bull", anomaly_score=1.0)
        self.assertTrue(res["enter"])
        self.assertEqual(res["side"], "LONG")

    def test_enter_short_side(self):
        res = self.policy.should_enter(signal=-1, regime="bear", anomaly_score=0.5)
        self.assertTrue(res["enter"])
        self.assertEqual(res["side"], "SHORT")

    def test_no_enter_on_zero_signal(self):
        self.assertFalse(
            self.policy.should_enter(signal=0, regime="bull")["enter"])

    def test_no_enter_on_disallowed_regime(self):
        self.assertFalse(
            self.policy.should_enter(signal=1, regime="neutral")["enter"])

    def test_no_enter_on_anomaly_spike(self):
        self.assertFalse(
            self.policy.should_enter(signal=1, regime="bull",
                                     anomaly_score=5.0)["enter"])

    # ── exit ─────────────────────────────────────────────────────────────────
    def test_exit_on_regime_leaving_allowed(self):
        res = self.policy.should_exit(position_side="LONG", signal=1,
                                      regime="neutral")
        self.assertTrue(res["exit"])

    def test_exit_on_anomaly_spike(self):
        res = self.policy.should_exit(position_side="LONG", signal=1,
                                      regime="bull", anomaly_score=9.0)
        self.assertTrue(res["exit"])

    def test_exit_on_signal_reversal(self):
        res = self.policy.should_exit(position_side="LONG", signal=-1,
                                      regime="bull")
        self.assertTrue(res["exit"])
        self.assertEqual(res["reason"], "signal reversed")

    def test_no_exit_on_plain_hold(self):
        res = self.policy.should_exit(position_side="LONG", signal=1,
                                      regime="bull", anomaly_score=0.5)
        self.assertFalse(res["exit"])

    def test_learned_exit_path(self):
        # OnlineNode trained on always-exit labels -> learned path fires
        node = OnlineNode(["f0", "f1"], name="exit")
        X = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.2, 0.1]] * 6
        y = [1] * len(X)
        node.fit(X, y)
        policy = EntryExitPolicy(allowed_regimes=("bull", "bear"),
                                 max_anomaly=3.0, exit_model=node,
                                 exit_threshold=0.5)
        res = policy.should_exit(position_side="LONG", signal=1, regime="bull",
                                 anomaly_score=0.5, exit_features=[0.4, 0.5])
        self.assertTrue(res["exit"])
        self.assertIn("learned exit", res["reason"])

    def test_status(self):
        st = self.policy.status()
        self.assertEqual(st["max_anomaly"], 3.0)
        self.assertFalse(st["learned_exit"])


if __name__ == "__main__":
    unittest.main()
