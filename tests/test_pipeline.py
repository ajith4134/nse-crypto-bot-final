"""Phase-0/1 acceptance tests: interface enforcement + the learning loop works.

Verifies (a) nodes satisfy NodeProtocol, (b) a single linear node CANNOT solve
the XOR golden data, and (c) the stacked ensemble does — proving the
'known I/O -> accuracy' loop and that stacking adds value.
"""
from __future__ import annotations

import unittest

from core.node_protocol import NodeProtocol
from eval.golden import accuracy, make_golden_dataset, train_test_split
from nodes.base_learners import DecisionStumpNode, KNNNode, LogisticRegressionNode
from nodes.stacking_node import StackingEnsembleNode

BASES = [
    lambda: LogisticRegressionNode(name="logreg"),
    lambda: KNNNode(k=5, name="knn"),
    lambda: DecisionStumpNode(name="stump"),
]


class TestPipeline(unittest.TestCase):
    def setUp(self):
        X, y = make_golden_dataset(n=600, noise=0.45, seed=7)
        self.Xtr, self.ytr, self.Xte, self.yte = train_test_split(X, y, 0.3, 7)

    def test_nodes_satisfy_protocol(self):
        for f in BASES:
            self.assertIsInstance(f(), NodeProtocol)

    def test_linear_node_struggles_on_xor(self):
        lr = LogisticRegressionNode().fit(self.Xtr, self.ytr)
        acc = accuracy(lr.predict(self.Xte), self.yte)
        self.assertLess(acc, 0.70, f"linear node unexpectedly strong: {acc}")

    def test_ensemble_learns(self):
        ens = StackingEnsembleNode(BASES, folds=5).fit(self.Xtr, self.ytr)
        acc = accuracy(ens.predict(self.Xte), self.yte)
        self.assertGreater(acc, 0.85, f"ensemble too weak: {acc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
