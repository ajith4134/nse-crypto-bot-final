"""AI-scientist idea #10 — Intermarket GNN (PyG GCN over the cross-feature graph)."""
import unittest

import numpy as np

from core.node_protocol import NodeProtocol
from nodes.intermarket_gnn import IntermarketGNNNode, intermarket_gnn_node


def _graph_dataset(n=500, seed=0):
    """8 features where the label depends on a COMBINATION of correlated groups — a GNN that
    message-passes across the relationship graph should capture it."""
    rng = np.random.default_rng(seed)
    g1 = rng.normal(size=(n, 1))                      # driver A
    g2 = rng.normal(size=(n, 1))                      # driver B
    # two correlated clusters around the drivers (contagion structure)
    A = np.hstack([g1 + 0.1 * rng.normal(size=(n, 1)), g1 + 0.1 * rng.normal(size=(n, 1)),
                   g1 + 0.1 * rng.normal(size=(n, 1)),
                   g2 + 0.1 * rng.normal(size=(n, 1)), g2 + 0.1 * rng.normal(size=(n, 1)),
                   g2 + 0.1 * rng.normal(size=(n, 1)),
                   rng.normal(size=(n, 1)), rng.normal(size=(n, 1))])
    # graph-structured target: cluster-A activation vs cluster-B activation (needs to read the
    # two correlated groups the GNN message-passes over), with mild noise.
    y = ((A[:, 0:3].mean(1) - A[:, 3:6].mean(1)) + 0.3 * rng.normal(size=n) > 0).astype(int)
    return A.tolist(), y.tolist()


class TestIntermarketGNN(unittest.TestCase):
    def test_protocol_fit_predict(self):
        X, y = _graph_dataset()
        node = intermarket_gnn_node("gnn_test")
        self.assertIsInstance(node, NodeProtocol)
        node.epochs = 80
        node.fit(X, y)
        p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        acc = np.mean([int(pi >= 0.5) == yi for pi, yi in zip(p, y)])
        self.assertGreater(acc, 0.6, f"GNN acc={acc:.3f} not above chance")

    def test_learns_relationship_graph(self):
        X, y = _graph_dataset(seed=1)
        node = IntermarketGNNNode(name="gnn_g", epochs=30)
        node.fit(X, y)
        if node.fell_back:
            self.skipTest("PyG unavailable — logistic fallback")
        # the learned edge_index should connect the correlated clusters (non-empty, valid indices)
        ei = node._edge_index
        self.assertEqual(ei.shape[0], 2)
        self.assertGreater(ei.shape[1], 0)
        self.assertTrue(int(ei.max()) < len(X[0]))

    def test_predict_shape_on_new_rows(self):
        X, y = _graph_dataset(seed=2)
        node = IntermarketGNNNode(name="gnn_new", epochs=25)
        node.fit(X, y)
        out = node.predict(X[:20])
        self.assertEqual(len(out), 20)
        self.assertTrue(set(out) <= {0, 1})


if __name__ == "__main__":
    unittest.main()
