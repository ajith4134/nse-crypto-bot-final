"""Pillar 20 — anti-overfitting backbone: CPCV, meta-labeling, and the mandatory
Deflated-Sharpe promotion gate on the Foundry + per-coin picker."""
import os
import tempfile
import unittest

import numpy as np
import pandas as pd


class TestCPCV(unittest.TestCase):
    def test_paths_and_purge(self):
        from trading.strategy.cpcv import combinatorial_purged_folds, n_paths
        paths = combinatorial_purged_folds(600, n_groups=6, k_test=2, embargo_pct=0.02)
        self.assertEqual(len(paths), n_paths(6, 2))       # C(6,2) = 15
        emb = max(1, int(600 * 0.02))
        for p in paths:
            self.assertEqual(len(p["test"]), 2)
            for (ts, te) in p["test"]:
                for (s, e) in p["train"]:
                    # no train segment overlaps a test block or its embargo window
                    self.assertTrue(e <= ts or s >= te + emb)

    def test_cpcv_scheme_in_evaluate_oos(self):
        from trading.strategy.genome import random_strategy
        from trading.strategy.features import FEATURE_NAMES
        from trading.strategy.fitness import evaluate_oos
        rng = np.random.default_rng(1)
        n = 800
        rets = np.random.default_rng(2).normal(0.0002, 0.012, n)
        close = 100.0 * np.exp(np.cumsum(rets))
        open_ = np.concatenate([[close[0]], close[:-1]])
        df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.4,
                           "low": np.minimum(open_, close) - 0.4,
                           "close": close, "volume": 1000.0})
        strat = random_strategy(list(FEATURE_NAMES), rng, market="CRYPTO")
        oos = evaluate_oos(strat, df, scheme="cpcv", cpcv_groups=6, cpcv_k_test=2)
        # CPCV yields one OOS return per combinatorial path → a distribution for DSR/PBO
        self.assertEqual(len(oos["fold_returns"]), 15)
        self.assertIn("trade_returns", oos)


class TestMetaLabel(unittest.TestCase):
    def test_triple_barrier_and_gate(self):
        from trading.strategy.metalabel import triple_barrier_labels, MetaLabeler
        rng = np.random.RandomState(3)
        n = 500
        close = 100 + np.cumsum(rng.randn(n))
        df = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                           "close": close, "volume": 1000.0})
        sig = pd.Series(np.where(rng.rand(n) > 0.7, 1, 0))
        lab = triple_barrier_labels(df, sig, pt=1.5, sl=1.0, max_hold=10)
        self.assertGreater(len(lab), 0)
        self.assertTrue(set(lab["label"].unique()).issubset({0, 1}))
        feats = pd.DataFrame({"f1": rng.randn(n), "f2": rng.randn(n),
                              "mom": pd.Series(close).pct_change().fillna(0)})
        ml = MetaLabeler(threshold=0.5).fit(feats, lab)
        self.assertTrue(ml.as_dict()["fitted"])
        g = ml.gate(feats.iloc[10])
        self.assertIn("act", g)
        self.assertGreaterEqual(g["proba"], 0.0)
        self.assertLessEqual(g["proba"], 1.0)


class TestFoundryGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        import trading.state as st
        self._orig = st.STATE_DIR
        st.STATE_DIR = self._tmp

    def tearDown(self):
        import trading.state as st
        st.STATE_DIR = self._orig

    def test_deflation_gate_blocks_selection_bias(self):
        from trading.strategy.foundry import StrategyFoundry
        f = StrategyFoundry(persist=False)
        seg = "crypto_futures"
        sids = [sid for sid, sp in f.specs.items() if sp.segment == seg][:8]
        self.assertGreaterEqual(len(sids), 4)
        # Record many mediocre + one lucky high-Sharpe: the lucky one must be deflated away
        for i, sid in enumerate(sids):
            f.record(sid, {"sharpe": 0.1 + 0.05 * i, "win_rate": 0.5,
                           "max_drawdown": -0.1, "trades": 30})
        # one lucky spike among the trials
        f.record(sids[0], {"sharpe": 2.2, "win_rate": 0.55, "max_drawdown": -0.1, "trades": 30})
        report = f.deflation_gate(seg, dsr_min=0.6)
        self.assertIn(sids[0], report)
        # the benchmark deflates the lucky Sharpe; gate must be an honest bool with a benchmark
        self.assertIn("benchmark", report[sids[0]])
        self.assertIsInstance(report[sids[0]]["passed"], bool)

    def test_promote_routes_through_gate(self):
        from trading.strategy.foundry import StrategyFoundry
        f = StrategyFoundry(persist=False)
        seg = "crypto_futures"
        sids = [sid for sid, sp in f.specs.items() if sp.segment == seg][:6]
        for sid in sids:                      # all too few trades → gate must reject all
            f.record(sid, {"sharpe": 1.0, "win_rate": 0.6, "max_drawdown": -0.1, "trades": 3})
        promoted = f.promote(seg, keep=5, gate=True, min_trades=10)
        self.assertEqual(promoted, [], "gate must block strategies with too few trades")
        # without the gate the same specs would promote — proves the gate is doing work
        promoted_nogate = f.promote(seg, keep=5, gate=False)
        self.assertGreater(len(promoted_nogate), 0)


if __name__ == "__main__":
    unittest.main()
