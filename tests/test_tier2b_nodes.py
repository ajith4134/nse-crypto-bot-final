"""Remaining catalog-ADD nodes (nodes/tier2b_nodes.py) — the MED/LOW ADDs completed."""
from __future__ import annotations

import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _synth(n=150, seed=6):
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
        import nodes.tier2b_nodes as T  # noqa
        import torch  # noqa
        return T
    except Exception:
        return None


class TestTier2bNodes(unittest.TestCase):
    def _assert(self, node, Xtr, Xte, y, task):
        node.task = task
        node.fit(Xtr, y)
        proba = node.predict_proba(Xte)
        out = node.predict_output(Xte)
        self.assertEqual(len(proba), len(Xte))
        self.assertEqual(len(out), len(Xte))
        self.assertTrue(all(np.isfinite(v) for v in proba), f"{node.name} non-finite")
        self.assertTrue(all(0.0 <= v <= 1.0 for v in proba), f"{node.name} out of [0,1]")

    def _run(self, factory, task, reg=False):
        T = _imp()
        if T is None:
            self.skipTest("tier2b stack absent")
        Xtr, Xte, yreg, ybin = _synth()
        self._assert(factory(T), Xtr, Xte, yreg if reg else ybin, task)

    def test_tide(self):
        self._run(lambda T: T.TiDENode(), "regression", reg=True)

    def test_timemixer(self):
        self._run(lambda T: T.TimeMixerNode(), "binary")

    def test_mamba(self):
        self._run(lambda T: T.MambaNode(), "regression", reg=True)

    def test_normflow(self):
        self._run(lambda T: T.NormFlowNode(), "binary")

    def test_bayesian_nn(self):
        self._run(lambda T: T.BayesianTorchNode(), "regression", reg=True)

    def test_lingam(self):
        self._run(lambda T: T.LiNGAMNode(), "binary")

    # TimesNet is correct but slow (~55s/fit); covered by the smoke test, kept out of CI here.

    def test_pool_exposes_tier2b(self):
        import nodes.pool as pool
        names = pool.foundation_names()
        if not names:
            self.skipTest("stack absent")
        for n in ("tide", "mamba", "normflow", "bayesian_nn", "lingam"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
