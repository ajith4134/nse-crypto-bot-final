"""AI-scientist idea #5 — TSFM ensemble + conformal calibration.

Hermetic: members are patched out so the ensemble exercises its base AR-fallback + conformal path
WITHOUT downloading multi-GB HF foundation models (those load only in a real MLNB_FOUNDATION_NODES
run). This validates the ensemble machinery + calibration; the real model path is unchanged.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import numpy as np

from core.node_protocol import NodeProtocol
import nodes.tsfm_ensemble as TE
from nodes.tsfm_ensemble import TSFMEnsembleNode, tsfm_ensemble_node


def _dataset(n=400, d=6, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    base = 1.4 * X[:, 0] - 1.0 * X[:, 1]
    y = (base + rng.normal(scale=0.5, size=n) > 0).astype(int)
    return X.tolist(), y.tolist()


class TestTSFMEnsemble(unittest.TestCase):
    def setUp(self):
        # force the AR-fallback ensemble path (no HF members) → fast + deterministic
        self._patch = mock.patch.object(TE, "_member_classes", return_value=[])
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_protocol_fit_predict(self):
        X, y = _dataset()
        node = tsfm_ensemble_node("tsfm_test")
        self.assertIsInstance(node, NodeProtocol)
        node.fit(X, y)
        self.assertTrue(node.fell_back)                 # no members → base AR fallback
        p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        acc = np.mean([int(pi >= 0.5) == yi for pi, yi in zip(p, y)])
        self.assertGreater(acc, 0.6, f"ensemble acc={acc:.3f}")

    def test_conformal_calibration_applied(self):
        X, y = _dataset(seed=1)
        node = TSFMEnsembleNode(name="tsfm_cal", calibrate=True)
        node.fit(X, y)
        self.assertIsNotNone(node._iso, "conformal calibration not fit")
        raw = np.linspace(0.05, 0.95, 25)
        cal = node._iso.predict(raw)
        self.assertTrue(np.all(np.diff(cal) >= -1e-9))   # isotonic = monotone non-decreasing
        self.assertTrue(np.all((cal >= 0) & (cal <= 1)))

    def test_uncalibrated_matches_raw(self):
        X, y = _dataset(seed=2)
        node = TSFMEnsembleNode(name="tsfm_raw", calibrate=False)
        node.fit(X, y)
        self.assertIsNone(node._iso)
        self.assertEqual(len(node.predict_proba(X)), len(X))


class TestTimeMoENode(unittest.TestCase):
    def test_valid_node_ar_fallback(self):
        # patch the model load to fail → base AR fallback (no download); still a valid node.
        from nodes.foundation_nodes import TimeMoENode
        X, y = _dataset(seed=3)
        with mock.patch.object(TimeMoENode, "_model", side_effect=RuntimeError("offline")):
            node = TimeMoENode(name="time_moe_t")
            self.assertIsInstance(node, NodeProtocol)
            node.fit(X, y)
            p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(node.fell_back)


if __name__ == "__main__":
    unittest.main()
