"""AI-scientist idea #6 — LiT order-book transformer node."""
import unittest

import numpy as np

from core.node_protocol import NodeProtocol
from nodes.lob_transformer import LOBTransformerNode, lob_transformer_node


def _microstructure_dataset(n=800, d=12, seed=0):
    """Direction depends on interactions across microstructure 'levels' (imbalance × spread) —
    exactly what attention should pick up over hand-crafted single-feature rules."""
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    imbalance = X[:, 0] - X[:, 1]
    spread = np.abs(X[:, 4]) + 0.5
    flow = X[:, 6] + X[:, 7]
    logit = imbalance / spread + 0.6 * flow + 0.4 * X[:, 2] * X[:, 3]
    y = (logit + rng.normal(scale=0.4, size=n) > 0).astype(int)
    return X.tolist(), y.tolist()


class TestLOBTransformer(unittest.TestCase):
    def test_protocol_fit_predict(self):
        X, y = _microstructure_dataset()
        node = lob_transformer_node("lit_test")
        self.assertIsInstance(node, NodeProtocol)
        node.epochs = 30
        node.fit(X, y)
        p = node.predict_proba(X)
        self.assertEqual(len(p), len(X))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        acc = np.mean([int(pi >= 0.5) == yi for pi, yi in zip(p, y)])
        self.assertGreater(acc, 0.62, f"LiT acc={acc:.3f} not above chance")

    def test_tokenization_shapes(self):
        X, y = _microstructure_dataset(d=10, seed=1)   # 10 not divisible by token_dim=4 → padding
        node = LOBTransformerNode(name="lit_tok", token_dim=4, epochs=15)
        node.fit(X, y)
        if node.fell_back:
            self.skipTest("torch unavailable")
        self.assertEqual(node._pad, 2)                 # 10 → pad to 12
        self.assertEqual(node._seq_len, 3)             # 12 / 4
        out = node.predict(X[:16])
        self.assertEqual(len(out), 16)
        self.assertTrue(set(out) <= {0, 1})

    def test_generalizes_to_holdout(self):
        Xtr, ytr = _microstructure_dataset(n=800, seed=2)
        Xte, yte = _microstructure_dataset(n=300, seed=99)
        node = LOBTransformerNode(name="lit_gen", epochs=40)
        node.fit(Xtr, ytr)
        if node.fell_back:
            self.skipTest("torch unavailable")
        acc = np.mean((np.asarray(node.predict_proba(Xte)) >= 0.5) == np.asarray(yte))
        self.assertGreater(acc, 0.58, f"LiT holdout acc={acc:.3f}")


if __name__ == "__main__":
    unittest.main()
