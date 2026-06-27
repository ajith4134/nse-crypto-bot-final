"""Step 3: chaos / nonlinear-dynamics node families (pure-Python).

- RecurrenceNode: analog forecasting by recurrence — k-NN in the delay-embedding
  subspace (the lagged-return features), i.e. 'what happened last time the system
  was in a similar state'.
- ChaosFeatureNode: augments inputs with nonlinear-dynamics statistics — local
  curvature, a divergence (local-Lyapunov-style) ratio, energy, and sign-change
  count — then a logistic readout. Designed to lean on structure that survives
  noise better than raw values.

Feature layout assumed (from data/features.py): indices 0,1,2 = ret1,ret2,ret3.
"""
from __future__ import annotations

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from nodes.base_learners import LogisticRegressionNode
from native import fastops as _fo

EMB = (0, 1, 2)  # delay-embedding dims = recent returns


class RecurrenceNode(BaseNode):
    kind = "base"
    summary = "Recurrence/analog node: k-NN in the delay-embedding subspace."

    def __init__(self, k: int = 20, name: str = "recurrence"):
        self.name = name
        self.k = k
        self.schema = IOSchema(0, "delay embedding", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "RecurrenceNode":
        self.E = [[x[e] for e in EMB] for x in X]
        self.y = list(y)
        self.schema = IOSchema(len(X[0]), "delay embedding (ret lags)", "p(class=1)")
        self._prep = _fo.prepare(self.E)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        out = []
        for x in X:
            q = [x[e] for e in EMB]
            dists = _fo.sqdists_prepared(self._prep, q)
            nn = sorted(range(len(dists)), key=lambda i: dists[i])[: self.k]
            out.append(sum(self.y[i] for i in nn) / self.k)
        return out


class ChaosFeatureNode(BaseNode):
    kind = "base"
    summary = "Chaos-feature node: curvature/divergence/energy/sign-change + logistic."

    def __init__(self, name: str = "chaos_feat"):
        self.name = name
        self.readout = LogisticRegressionNode(name=f"{name}__readout")
        self.schema = IOSchema(0, "features + chaos stats", "p(class=1)")

    @staticmethod
    def _augment(x: list[float]) -> list[float]:
        r1, r2, r3 = x[0], x[1], x[2]
        curv = abs(r1 - 2 * r2 + r3)                       # local curvature
        div = abs(r1 - r2) / (abs(r2 - r3) + 1e-6)         # divergence (Lyapunov-ish)
        energy = r1 * r1 + r2 * r2 + r3 * r3
        signchg = int((r1 > 0) != (r2 > 0)) + int((r2 > 0) != (r3 > 0))
        return list(x) + [curv, div, energy, float(signchg)]

    def fit(self, X: Matrix, y: Labels) -> "ChaosFeatureNode":
        self.schema = IOSchema(len(X[0]), "features + 4 chaos stats", "p(class=1)")
        self.readout.fit([self._augment(x) for x in X], y)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        return self.readout.predict_proba([self._augment(x) for x in X])
