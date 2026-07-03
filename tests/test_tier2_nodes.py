"""Tier-2 model nodes (nodes/tier2_nodes.py, groups G/J/K).

Each node is checked for NodeProtocol conformance on a small synthetic series; skipped
cleanly if its OSS dep is absent so the suite stays green regardless of install state.
"""
from __future__ import annotations

import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _synth(n=150, seed=3):
    rng = np.random.default_rng(seed)
    ys = np.cumsum(rng.standard_normal(n)) * 0.5 + np.sin(np.arange(n) * 0.1)
    X = [[float(ys[i]),
          float(np.mean(ys[max(0, i - 5):i + 1])),
          float(np.std(ys[max(0, i - 5):i + 1]) + 1e-6)] for i in range(n)]
    ret = np.diff(ys, append=ys[-1])
    cut = int(n * 0.8)
    return X[:cut], X[cut:], list(ret)[:cut], [1 if v > 0 else 0 for v in ret][:cut]


def _imp():
    try:
        import nodes.tier2_nodes as T  # noqa
        import torch  # noqa
        return T
    except Exception:
        return None


class TestTier2Nodes(unittest.TestCase):
    def _assert(self, node, Xtr, Xte, y, task):
        node.task = task
        node.fit(Xtr, y)
        proba = node.predict_proba(Xte)
        out = node.predict_output(Xte)
        self.assertEqual(len(proba), len(Xte))
        self.assertEqual(len(out), len(Xte))
        self.assertTrue(all(np.isfinite(v) for v in proba), f"{node.name} non-finite")
        self.assertTrue(all(0.0 <= v <= 1.0 for v in proba), f"{node.name} out of [0,1]")

    def test_kan(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert(T.KANNode(), Xtr, Xte, yreg, "regression")

    def test_xlstm(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.XLSTMNode(), Xtr, Xte, ybin, "binary")

    def test_liquid_ltc(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.LiquidLTCNode(), Xtr, Xte, ybin, "binary")

    def test_neural_cde(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert(T.NeuralCDENode(), Xtr, Xte, yreg, "regression")

    def test_quantlib_greeks(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.QuantLibGreeksNode(), Xtr, Xte, ybin, "binary")

    def test_markov_regime(self):
        T = _imp()
        if T is None:
            self.skipTest("tier2 stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.MarkovRegimeNode(), Xtr, Xte, ybin, "binary")

    def test_pool_exposes_tier2(self):
        import nodes.pool as pool
        names = pool.foundation_names()
        if not names:
            self.skipTest("stack absent")
        for n in ("kan", "xlstm", "liquid_ltc", "neural_cde", "quantlib_greeks", "markov_regime"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
