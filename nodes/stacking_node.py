"""StackingEnsembleNode — the Phase-1 'models as nodes' core.

Wires several base nodes as inputs whose out-of-fold predictions become the
features of a meta-learner node. This is the canonical stacked-generalization
recipe (Wolpert 1992) and the miniature of the full prediction-graph network:
base nodes -> meta node. Adding more base nodes needs no change to the meta node.

Inputs:  Matrix + Labels.
Outputs: p(class=1) from the meta-learner over base-node predictions.
"""
from __future__ import annotations

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.base_learners import LogisticRegressionNode


def _kfold_indices(n: int, folds: int) -> list[list[int]]:
    return [list(range(i, n, folds)) for i in range(folds)]


class StackingEnsembleNode(BaseNode):
    kind = "meta"
    summary = "Stacked-ensemble meta node combining base-node predictions."

    def __init__(self, base_factories: list[NodeFactory], folds: int = 5,
                 name: str = "stacking_ensemble"):
        self.name = name
        self.base_factories = base_factories
        self.folds = folds
        self.bases: list[BaseNode] = []
        self.meta = LogisticRegressionNode(name=f"{name}__meta")
        self.base_names = [f().name for f in base_factories]
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "StackingEnsembleNode":
        n, d = len(X), len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1) [meta]")
        folds = _kfold_indices(n, self.folds)

        # Out-of-fold meta-features: each base predicts the held-out fold only.
        meta_X: Matrix = [[0.0] * len(self.base_factories) for _ in range(n)]
        for val_idx in folds:
            tr_idx = [i for i in range(n) if i not in set(val_idx)]
            Xtr, ytr = [X[i] for i in tr_idx], [y[i] for i in tr_idx]
            Xval = [X[i] for i in val_idx]
            for c, factory in enumerate(self.base_factories):
                model = factory().fit(Xtr, ytr)
                for row, p in zip(val_idx, model.predict_proba(Xval)):
                    meta_X[row][c] = p

        self.meta.fit(meta_X, y)
        # Refit base nodes on all data for inference.
        self.bases = [f().fit(X, y) for f in self.base_factories]
        return self

    def _meta_features(self, X: Matrix) -> Matrix:
        cols = [b.predict_proba(X) for b in self.bases]
        return [[cols[c][i] for c in range(len(self.bases))] for i in range(len(X))]

    def predict_proba(self, X: Matrix) -> Vector:
        return self.meta.predict_proba(self._meta_features(X))
