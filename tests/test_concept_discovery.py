"""Concept Discovery Engine (trading/brain/discovery/) — pure-self feature invention.

Runs the full invent → probe → name → manifold pipeline on synthetic OHLCV and asserts the
two-lane output is well-formed. Degrades gracefully if torch/umap/etc. are absent (numpy
fallbacks), so the suite stays green regardless of the installed stack.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _ohlcv(n=320, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    close = 100 + np.cumsum(rng.standard_normal(n) * 0.5) + 8 * np.sin(t * 0.05)
    high = close + np.abs(rng.standard_normal(n) * 0.3)
    low = close - np.abs(rng.standard_normal(n) * 0.3)
    op = close + rng.standard_normal(n) * 0.2
    vol = 1000 + np.abs(rng.standard_normal(n) * 200)
    return np.column_stack([op, high, low, close, vol])


class TestConceptDiscovery(unittest.TestCase):
    def test_pipeline_end_to_end(self):
        from trading.brain.discovery import ConceptDiscoveryEngine
        ohlcv = _ohlcv()
        eng = ConceptDiscoveryEngine(window=24, latent_dim=10, dict_size=20,
                                     top_features=8, use_llm=False)
        res = eng.discover(series=ohlcv[:, 3], ohlcv=ohlcv)
        # features
        self.assertLessEqual(len(res["features"]), 8)
        self.assertGreater(len(res["features"]), 0)
        for f in res["features"]:
            self.assertIn(f["lane"], ("experiment", "validated"))
            self.assertTrue(f["name"])
            self.assertTrue(0.0 <= f["activation_rate"] <= 1.0)
        # stats: experiment + validated == total
        st = res["stats"]
        self.assertEqual(st["n_experiment"] + st["n_validated"], len(res["features"]))
        # manifold: one normalized point per window, valid cluster ids
        pts = res["manifold"]["points"]
        self.assertEqual(len(pts), st["n_windows"])
        self.assertTrue(all(0.0 <= p["x"] <= 1.0 and 0.0 <= p["y"] <= 1.0 for p in pts))

    def test_persist_and_reload(self):
        from trading.brain.discovery import engine as E
        from trading.brain.discovery import ConceptDiscoveryEngine
        orig = E._PATH
        E._PATH = os.path.join(tempfile.mkdtemp(), "cd.json")
        try:
            eng = ConceptDiscoveryEngine(window=20, latent_dim=8, dict_size=16,
                                         top_features=6, use_llm=False)
            res = eng.discover(series=_ohlcv()[:, 3], ohlcv=_ohlcv())
            eng.save()
            self.assertTrue(os.path.exists(E._PATH))
            reloaded = ConceptDiscoveryEngine.load()
            self.assertEqual(len(reloaded["features"]), len(res["features"]))
        finally:
            E._PATH = orig

    def test_validation_gate_sign_consistency(self):
        from trading.brain.discovery.engine import ConceptDiscoveryEngine
        # a feature perfectly correlated with forward return (both halves) → validated
        rng = np.random.default_rng(1)
        fwd = rng.standard_normal(120)
        act = fwd * 2.0 + rng.standard_normal(120) * 0.1     # strong consistent signal
        ok, score = ConceptDiscoveryEngine._validate(act, fwd)
        self.assertTrue(ok)
        self.assertGreater(abs(score), 0.08)
        # pure noise → not validated
        ok2, _ = ConceptDiscoveryEngine._validate(rng.standard_normal(120), rng.standard_normal(120))
        self.assertFalse(ok2)


if __name__ == "__main__":
    unittest.main()
