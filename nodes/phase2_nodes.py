"""Phase-2 node families (pure-Python, CPU-only) — more diverse 'neurons'.

- MLPNode: a real single-hidden-layer neural network (the literal neuron analog).
- ReservoirNode: reservoir-computing / ELM style — a FIXED random nonlinear
  expansion + a trained linear readout; CPU-friendly. (Temporal echo-state
  recurrence arrives when we feed raw sequences; this is the feature-vector form.)
- GaussianNBNode: Gaussian Naive Bayes — a different inductive bias for diversity.

Each conforms to NodeProtocol and slots into the stacking layer unchanged.
"""
from __future__ import annotations

import math
import random

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from nodes.base_learners import LogisticRegressionNode, _sigmoid
from native import fastops as _fo


def _standardizer(X: Matrix):
    n, d = len(X), len(X[0])
    mean = [sum(r[j] for r in X) / n for j in range(d)]
    std = [(sum((r[j] - mean[j]) ** 2 for r in X) / n) ** 0.5 or 1.0 for j in range(d)]
    return mean, std


class MLPNode(BaseNode):
    kind = "base"
    summary = "Single-hidden-layer neural-net node (tanh) — the literal 'neuron' analog."

    def __init__(self, hidden: int = 8, lr: float = 0.1, epochs: int = 300,
                 seed: int = 1, name: str = "mlp"):
        self.name = name
        self.h, self.lr, self.epochs, self.seed = hidden, lr, epochs, seed
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "MLPNode":
        d = len(X[0])
        self.d = d
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self.mean, self.std = _standardizer(X)
        Xs = [[(r[j] - self.mean[j]) / self.std[j] for j in range(d)] for r in X]
        # native trainer if available; W1 is flat row-major H*d
        self.W1, self.b1, self.W2, self.b2 = _fo.mlp_train(
            Xs, y, self.h, self.lr, self.epochs, self.seed)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        d = len(self.mean)
        out = []
        for r in X:
            xi = [(r[j] - self.mean[j]) / self.std[j] for j in range(d)]
            hact = [math.tanh(sum(self.W1[j * d + k] * xi[k] for k in range(d)) + self.b1[j])
                    for j in range(len(self.W2))]
            out.append(_sigmoid(sum(self.W2[j] * hact[j] for j in range(len(self.W2))) + self.b2))
        return out


class ReservoirNode(BaseNode):
    kind = "base"
    summary = "Reservoir/ELM node: fixed random nonlinear expansion + linear readout."

    def __init__(self, size: int = 40, seed: int = 3, name: str = "reservoir"):
        self.name = name
        self.size, self.seed = size, seed
        self.readout = LogisticRegressionNode(name=f"{name}__readout", epochs=300)
        self.schema = IOSchema(0, "features", "p(class=1)")

    def _expand(self, X: Matrix) -> Matrix:
        d = len(self.mean)
        out = []
        for r in X:
            xi = [(r[j] - self.mean[j]) / self.std[j] for j in range(d)]
            out.append([math.tanh(sum(self.Win[s][k] * xi[k] for k in range(d)) + self.bias[s])
                        for s in range(self.size)])
        return out

    def fit(self, X: Matrix, y: Labels) -> "ReservoirNode":
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self.mean, self.std = _standardizer(X)
        rng = random.Random(self.seed)
        self.Win = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(self.size)]
        self.bias = [rng.uniform(-1, 1) for _ in range(self.size)]
        self.readout.fit(self._expand(X), y)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        return self.readout.predict_proba(self._expand(X))


class GaussianNBNode(BaseNode):
    kind = "base"
    summary = "Gaussian Naive-Bayes node — probabilistic, different inductive bias."

    def __init__(self, name: str = "gaussnb"):
        self.name = name
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "GaussianNBNode":
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self.stats = {}
        for c in (0, 1):
            rows = [x for x, t in zip(X, y) if t == c]
            n = len(rows) or 1
            mean = [sum(r[j] for r in rows) / n for j in range(d)]
            var = [max(sum((r[j] - mean[j]) ** 2 for r in rows) / n, 1e-6) for j in range(d)]
            self.stats[c] = (mean, var, len(rows) / len(X))
        return self

    def _loglik(self, x: list[float], c: int) -> float:
        mean, var, prior = self.stats[c]
        ll = math.log(prior or 1e-9)
        for j in range(len(x)):
            ll += -0.5 * math.log(2 * math.pi * var[j]) - (x[j] - mean[j]) ** 2 / (2 * var[j])
        return ll

    def predict_proba(self, X: Matrix) -> Vector:
        out = []
        for x in X:
            l0, l1 = self._loglik(x, 0), self._loglik(x, 1)
            m = max(l0, l1)
            p1 = math.exp(l1 - m) / (math.exp(l0 - m) + math.exp(l1 - m))
            out.append(p1)
        return out
