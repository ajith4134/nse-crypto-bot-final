"""LearnedRouterNode — Phase 3: dynamic routing between full-model nodes.

Instead of statically stacking all base nodes, the router LEARNS which node to
trust per input: for a query it finds the k nearest training points and picks
the base node with the highest local accuracy there (Dynamic Classifier
Selection / DCS-LA). This directly targets the open 'routing between nodes'
problem and is the seed of the brain's wiring policy.

Inputs:  Matrix + Labels.   Outputs: routed p(class=1).
"""
from __future__ import annotations

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from native import fastops as _fo

VOL_IDX = 8  # vol10 feature, used for the regime/roughness score


def _roughness(x: list[float]) -> float:
    vol = x[VOL_IDX] if len(x) > VOL_IDX else 0.0
    return vol + 0.5 * abs(x[0] - 2 * x[1] + x[2])


class LearnedRouterNode(BaseNode):
    kind = "router"
    summary = "Learned router (DCS local-accuracy); regime-aware option folds in noise routing."

    def __init__(self, base_factories: list[NodeFactory], k: int = 25,
                 regime_aware: bool = False, score_weight: float = 2.0,
                 name: str = "learned_router"):
        self.name = name
        self.base_factories = base_factories
        self.k = k
        self.regime_aware = regime_aware
        self.score_weight = score_weight
        self.base_names = [f().name for f in base_factories]
        self.bases: list[BaseNode] = []
        self.schema = IOSchema(0, "features", "p(class=1) [routed]")

    def fit(self, X: Matrix, y: Labels) -> "LearnedRouterNode":
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1) [routed]")
        self.mean = [sum(r[j] for r in X) / len(X) for j in range(d)]
        self.std = [(sum((r[j] - self.mean[j]) ** 2 for r in X) / len(X)) ** 0.5 or 1.0
                    for j in range(d)]
        if self.regime_aware:                                # standardize the regime score
            sc = [_roughness(x) for x in X]
            self.smean = sum(sc) / len(sc)
            self.sstd = (sum((s - self.smean) ** 2 for s in sc) / len(sc)) ** 0.5 or 1.0
        self.Xz = [self._aug(x) for x in X]
        self._prep = _fo.prepare(self.Xz)
        self.bases = [f().fit(X, y) for f in self.base_factories]
        # correctness of each base on each training point
        self.correct = [[int(p == t) for p, t in zip(b.predict(X), y)] for b in self.bases]
        return self

    def _z(self, x: list[float]) -> list[float]:
        return [(x[j] - self.mean[j]) / self.std[j] for j in range(len(x))]

    def _aug(self, x: list[float]) -> list[float]:
        z = self._z(x)
        if self.regime_aware:           # append weighted regime score -> neighbours share regime
            z = z + [self.score_weight * (_roughness(x) - self.smean) / self.sstd]
        return z

    def _route(self, x: list[float]) -> int:
        d = _fo.sqdists_prepared(self._prep, self._aug(x))
        nbrs = sorted(range(len(d)), key=lambda i: d[i])[: self.k]
        best_b, best_acc = 0, -1.0
        for b in range(len(self.bases)):
            acc = sum(self.correct[b][i] for i in nbrs) / len(nbrs)
            if acc > best_acc:
                best_acc, best_b = acc, b
        return best_b

    def predict_proba(self, X: Matrix) -> Vector:
        return [self.bases[self._route(x)].predict_proba([x])[0] for x in X]

    def routing_histogram(self, X: Matrix) -> dict:
        counts = {n: 0 for n in self.base_names}
        for x in X:
            counts[self.base_names[self._route(x)]] += 1
        return counts
