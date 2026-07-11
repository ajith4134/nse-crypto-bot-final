"""Tests for trading/strategy/direction_equation.py — P2 Rank-IC equation orchestrator.

Covers: forward-return alignment (no look-ahead), horizon Rank-IC sign, score_equation on a
known factor (incl. invert flag for a negative-IC anti-signal), discover ranking/top_k + honest
degrade on too-little data, and the persist/load roundtrip.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from trading import state
from trading.strategy import direction_equation as de
from trading.strategy.generators.expression import ExpressionStrategy


def _trending_ohlcv(n=600, seed=2):
    rng = np.random.RandomState(seed)
    ret = np.zeros(n)
    mom = 0.0
    for i in range(1, n):
        mom = 0.6 * mom + rng.randn() * 0.01
        ret[i] = 0.5 * mom + rng.randn() * 0.008
    c = 100 * np.exp(np.cumsum(ret))
    o = c * (1 + rng.randn(n) * 0.001)
    h = np.maximum(o, c) * (1 + abs(rng.randn(n)) * 0.002)
    l = np.minimum(o, c) * (1 - abs(rng.randn(n)) * 0.002)
    v = 1000 + abs(rng.randn(n)) * 300
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v})


class TestForwardReturn(unittest.TestCase):
    def test_alignment_no_lookahead(self):
        close = pd.Series([1.0, 2.0, 4.0, 8.0])
        fwd = de._forward_return(close, 1)
        self.assertAlmostEqual(fwd[0], 1.0)      # 2/1 - 1
        self.assertAlmostEqual(fwd[1], 1.0)      # 4/2 - 1
        self.assertTrue(np.isnan(fwd[-1]))       # no future for the last bar

    def test_horizon_ic_sign(self):
        # a factor equal to the forward return must have IC ≈ +1
        close = pd.Series(np.linspace(1, 2, 50))
        fwd = pd.Series(de._forward_return(close, 1))
        ic = de.horizon_ic(fwd.fillna(0.0), close, 1)
        self.assertGreater(ic, 0.9)


class TestScoreEquation(unittest.TestCase):
    def setUp(self):
        self.ohlcv = _trending_ohlcv()
        from trading.strategy.features import compute_features
        self.feats = compute_features(self.ohlcv)
        self.close = self.feats["close"]

    def test_scores_a_known_equation(self):
        flist = [c for c in ("rsi", "macd_hist", "ema_fast") if c in self.feats.columns]
        cand = ExpressionStrategy(market="crypto", features=flist,
                                  expr=flist[0], kind="sympy", id="t0")
        rec = de.score_equation(cand, self.feats, self.close, horizons=(1, 4))
        self.assertIsNotNone(rec)
        self.assertIn("best_ic", rec)
        self.assertEqual(rec["invert"], rec["best_ic"] < 0)
        self.assertIn(rec["best_horizon"], (1, 4))

    def test_constant_factor_degrades(self):
        cand = ExpressionStrategy(market="crypto", features=["rsi"], expr="0.0",
                                  kind="sympy", id="const")
        self.assertIsNone(de.score_equation(cand, self.feats, self.close))


class TestDiscover(unittest.TestCase):
    def test_ranked_topk(self):
        ranked = de.discover(_trending_ohlcv(), "crypto_futures", budget=6, seed=2,
                             top_k=3, generators=None)
        self.assertLessEqual(len(ranked), 3)
        if len(ranked) >= 2:                      # sorted by |IC| descending
            self.assertGreaterEqual(ranked[0]["abs_ic"], ranked[1]["abs_ic"])
        for r in ranked:
            self.assertGreaterEqual(r["abs_ic"], 0.0)
            self.assertLessEqual(r["abs_ic"], 1.0)

    def test_too_little_data_degrades(self):
        self.assertEqual(de.discover(_trending_ohlcv(n=80), "crypto"), [])


class TestCpcvGate(unittest.TestCase):
    def setUp(self):
        self.ohlcv = _trending_ohlcv(n=800)

    def test_cpcv_robustness_shape(self):
        flist = ["rsi", "macd_hist"]
        rob = de.cpcv_robustness(self.ohlcv, "rsi", "sympy", flist, horizon=1)
        self.assertIsNotNone(rob)
        self.assertIn("cpcv_mean_ic", rob)
        self.assertIn("sign_consistency", rob)
        self.assertIsInstance(rob["passed"], bool)
        self.assertGreaterEqual(rob["n_paths"], 2)

    def test_validate_survivors_and_pbo(self):
        ranked = de.discover(self.ohlcv, "crypto_futures", budget=6, seed=3, top_k=5)
        rep = de.validate(self.ohlcv, ranked, "crypto_futures", persist=False)
        self.assertEqual(rep["n_candidates"], len(ranked))
        self.assertLessEqual(rep["n_survivors"], rep["n_candidates"])
        for s in rep["survivors"]:                      # every survivor is CPCV-robust
            self.assertTrue(s["cpcv"]["passed"])
        if rep["pbo"] is not None:
            self.assertGreaterEqual(rep["pbo"], 0.0)
            self.assertLessEqual(rep["pbo"], 1.0)

    def test_gate_degrades_on_short_series(self):
        self.assertIsNone(de.cpcv_robustness(_trending_ohlcv(n=40), "rsi", "sympy",
                                             ["rsi"], horizon=1))


class TestPersist(unittest.TestCase):
    def setUp(self):
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="deq_"))

    def tearDown(self):
        state.STATE_DIR = self._orig

    def test_roundtrip(self):
        eqs = [{"expr": "x0*x1", "abs_ic": 0.2, "best_horizon": 4}]
        de.save_equations("crypto", eqs)
        self.assertEqual(de.load_equations("crypto")[0]["expr"], "x0*x1")
        self.assertEqual(de.load_equations("nse"), [])     # unseen market


if __name__ == "__main__":
    unittest.main()
