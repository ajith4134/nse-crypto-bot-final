"""AI-scientist idea #7 — Regime-conditioned MoE router (learned gate over frozen experts)."""
import unittest

import numpy as np

from core.node_protocol import NodeProtocol
from nodes.regime_moe import RegimeMoERouter, regime_moe_node


def _regime_dataset(n=600, d=6, seed=0):
    """Two regimes: in regime A a linear rule wins, in regime B a nonlinear rule wins — so a good
    gate must route to different experts per regime and beat any single fixed expert."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    regime = (np.arange(n) // (n // 4)) % 2                      # alternating blocks
    lin = (1.6 * X[:, 0] - 1.2 * X[:, 1] > 0).astype(int)
    nonlin = ((X[:, 2] * X[:, 3] + 0.7 * X[:, 4] ** 2 - 0.5) > 0).astype(int)
    y = np.where(regime == 0, lin, nonlin)
    # expose the regime to the features so the gate can condition on it
    X = np.column_stack([X, regime.astype(float)])
    return X.tolist(), y.tolist()


class TestRegimeMoE(unittest.TestCase):
    def test_protocol_fit_predict(self):
        X, y = _regime_dataset()
        node = regime_moe_node("moe_test")
        self.assertIsInstance(node, NodeProtocol)
        node.epochs = 80
        node.fit(X, y)
        p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        acc = np.mean([int(pi >= 0.5) == yi for pi, yi in zip(p, y)])
        self.assertGreater(acc, 0.65, f"MoE router acc={acc:.3f} not above chance")

    def test_gate_learns_nonuniform_weights(self):
        X, y = _regime_dataset(seed=1)
        node = RegimeMoERouter(name="moe_w", epochs=150)
        node.fit(X, y)
        if node.fell_back:
            self.skipTest("torch/val unavailable — uniform fallback")
        w = np.array(list(node.expert_weights_.values()))
        self.assertEqual(len(w), node._n_exp)
        self.assertAlmostEqual(float(w.sum()), 1.0, places=3)
        # a learned gate should not be perfectly uniform (it discriminates experts)
        self.assertGreater(float(w.std()), 0.02)

    def test_beats_or_matches_single_expert(self):
        # the routed mixture should be at least competitive with the best single frozen expert.
        X, y = _regime_dataset(seed=2)
        node = RegimeMoERouter(name="moe_cmp", epochs=150)
        node.fit(X, y)
        if node.fell_back:
            self.skipTest("fallback path")
        ya = np.asarray(y)
        Az = node._z(np.asarray(X, np.float32))
        E = node._expert_probs(Az)
        best_single = max(np.mean((E[:, i] >= 0.5) == ya) for i in range(node._n_exp))
        mix_acc = np.mean((np.asarray(node.predict_proba(X)) >= 0.5) == ya)
        self.assertGreaterEqual(mix_acc, best_single - 0.03)


if __name__ == "__main__":
    unittest.main()
