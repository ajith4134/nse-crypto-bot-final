"""Base prediction nodes (pure-Python, CPU-only, zero deps).

Three deliberately diverse weak/strong learners so stacking has signal to
combine: logistic regression (linear), k-nearest-neighbours (local, solves
XOR-like data), and a decision stump (axis split). Each conforms to NodeProtocol
and is a drop-in for a future scikit-learn / AutoGluon node behind the same API.

Inputs:  Matrix of feature rows + integer Labels (0/1).
Outputs: per-row p(class=1).
"""
from __future__ import annotations

import math

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from native import fastops as _fo


def _sigmoid(z: float) -> float:
    if z < -60:
        return 0.0
    if z > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


class LogisticRegressionNode(BaseNode):
    """Linear logistic regression via full-batch gradient descent (standardized)."""
    kind = "base"
    summary = "Linear logistic-regression node trained by gradient descent."

    def __init__(self, lr: float = 0.3, epochs: int = 400, name: str = "logreg"):
        self.name = name
        self.lr, self.epochs = lr, epochs
        self.w: Vector = []
        self.b = 0.0
        self.mean: Vector = []
        self.std: Vector = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def _standardize(self, X: Matrix) -> Matrix:
        return [[(x[j] - self.mean[j]) / self.std[j] for j in range(len(x))] for x in X]

    def fit(self, X: Matrix, y: Labels) -> "LogisticRegressionNode":
        n, d = len(X), len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self.mean = [sum(r[j] for r in X) / n for j in range(d)]
        self.std = [(sum((r[j] - self.mean[j]) ** 2 for r in X) / n) ** 0.5 or 1.0
                    for j in range(d)]
        Xs = self._standardize(X)
        self.w, self.b = _fo.logreg_train(Xs, y, self.lr, self.epochs)  # native if available
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        Xs = self._standardize(X)
        return [_sigmoid(sum(self.w[j] * xi[j] for j in range(len(xi))) + self.b)
                for xi in Xs]


class KNNNode(BaseNode):
    """k-nearest-neighbours; p(class=1) = fraction of k neighbours in class 1."""
    kind = "base"
    summary = "k-NN node; strong on locally-clustered / XOR-like patterns."

    def __init__(self, k: int = 5, name: str = "knn"):
        self.name = name
        self.k = k
        self.X: Matrix = []
        self.y: Labels = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "KNNNode":
        self.X, self.y = [list(r) for r in X], list(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", "p(class=1)")
        self._prep = _fo.prepare(self.X)            # marshal dataset into C once
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        out: Vector = []
        for q in X:
            dists = _fo.sqdists_prepared(self._prep, q)   # native if available
            nearest = sorted(range(len(dists)), key=lambda i: dists[i])[: self.k]
            out.append(sum(self.y[i] for i in nearest) / self.k)
        return out


class DecisionStumpNode(BaseNode):
    """Single axis-aligned split; leaves emit their class-1 proportion."""
    kind = "base"
    summary = "Decision-stump node; one threshold split, interpretable & weak."

    def __init__(self, name: str = "stump"):
        self.name = name
        self.feat = 0
        self.thresh = 0.0
        self.left_p = 0.5
        self.right_p = 0.5
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "DecisionStumpNode":
        n, d = len(X), len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        best_err = float("inf")
        for f in range(d):
            vals = sorted(set(r[f] for r in X))
            cands = [(vals[i] + vals[i + 1]) / 2 for i in range(len(vals) - 1)] or vals
            for t in cands:
                left = [yi for xi, yi in zip(X, y) if xi[f] <= t]
                right = [yi for xi, yi in zip(X, y) if xi[f] > t]
                if not left or not right:
                    continue
                lp = sum(left) / len(left)
                rp = sum(right) / len(right)
                err = sum((lp >= 0.5) != yi for yi in left) + \
                      sum((rp >= 0.5) != yi for yi in right)
                if err < best_err:
                    best_err, self.feat, self.thresh = err, f, t
                    self.left_p, self.right_p = lp, rp
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        return [self.left_p if xi[self.feat] <= self.thresh else self.right_p for xi in X]
