"""Tier-3 infra nodes (nodes/tier3_nodes.py) + drift utility (core/drift.py)."""
from __future__ import annotations

import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _synth(n=150, seed=5):
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
        import nodes.tier3_nodes as T  # noqa
        import torch  # noqa
        return T
    except Exception:
        return None


class TestTier3Nodes(unittest.TestCase):
    def _assert(self, node, Xtr, Xte, y, task):
        node.task = task
        node.fit(Xtr, y)
        proba = node.predict_proba(Xte)
        out = node.predict_output(Xte)
        self.assertEqual(len(proba), len(Xte))
        self.assertEqual(len(out), len(Xte))
        self.assertTrue(all(np.isfinite(v) for v in proba), f"{node.name} non-finite")
        self.assertTrue(all(0.0 <= v <= 1.0 for v in proba), f"{node.name} out of [0,1]")

    def test_sb3_ppo_exec(self):
        T = _imp()
        if T is None:
            self.skipTest("tier3 stack absent")
        try:
            import stable_baselines3  # noqa
        except Exception:
            self.skipTest("sb3 absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.SB3RLExecNode(), Xtr, Xte, ybin, "binary")

    def test_alpha360(self):
        T = _imp()
        if T is None:
            self.skipTest("tier3 stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.Alpha360Node(), Xtr, Xte, ybin, "binary")

    def test_pygod_anomaly(self):
        T = _imp()
        if T is None:
            self.skipTest("tier3 stack absent")
        try:
            import pygod  # noqa
        except Exception:
            self.skipTest("pygod absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert(T.PyGODAnomalyNode(), Xtr, Xte, ybin, "binary")

    def test_temporal_graph(self):
        T = _imp()
        if T is None:
            self.skipTest("tier3 stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert(T.TemporalGraphNode(), Xtr, Xte, yreg, "regression")

    def test_pool_exposes_tier3(self):
        import nodes.pool as pool
        names = pool.foundation_names()
        if not names:
            self.skipTest("stack absent")
        for n in ("sb3_ppo_exec", "alpha360", "pygod_anomaly", "temporal_graph"):
            self.assertIn(n, names)


class TestDrift(unittest.TestCase):
    def test_data_drift_detects_shift(self):
        from core.drift import data_drift
        rng = np.random.default_rng(0)
        ref = rng.standard_normal((300, 5))
        same = rng.standard_normal((120, 5))
        shifted = rng.standard_normal((120, 5)) * 4 + 8
        r_same = data_drift(ref, same)
        r_shift = data_drift(ref, shifted)
        self.assertIn(r_same["backend"], ("evidently", "ks"))
        # clearly-shifted must report a higher drift share than same-distribution
        self.assertGreaterEqual(r_shift["drift_share"], r_same["drift_share"])
        self.assertTrue(r_shift["drifted"])

    def test_streaming_drift(self):
        from core.drift import StreamingDriftDetector
        det = StreamingDriftDetector()
        stream = list(np.random.default_rng(1).standard_normal(300)) + \
            list(np.random.default_rng(2).standard_normal(300) * 10 + 30)
        fired = any(det.update(v) for v in stream)
        self.assertTrue(fired)


if __name__ == "__main__":
    unittest.main()
