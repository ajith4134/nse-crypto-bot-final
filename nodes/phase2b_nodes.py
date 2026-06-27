"""Phase-2b node families (pure-Python): Random Forest + Regime-Gated.

- RandomForestNode: bagged shallow decision trees with feature subsampling — a
  strong tabular workhorse, a genuinely different family from the linear/NN nodes.
- RegimeGatedNode: splits data by a volatility/regime feature and fits a separate
  linear model per regime, routing at predict time — the 'change-point / regime'
  family from the plan, and a mini preview of input-dependent routing.
"""
from __future__ import annotations

import random

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from nodes.base_learners import LogisticRegressionNode


def _gini(pos: int, n: int) -> float:
    if n == 0:
        return 0.0
    p = pos / n
    return 1 - p * p - (1 - p) ** 2


class _Tree:
    """Shallow CART-ish tree on a feature subset."""
    def __init__(self, depth: int, min_leaf: int = 8, max_thresh: int = 16):
        self.depth, self.min_leaf, self.max_thresh = depth, min_leaf, max_thresh
        self.leaf_p = 0.5
        self.f = self.t = None
        self.left = self.right = None

    def fit(self, X: Matrix, y: Labels, feats: list[int]) -> "_Tree":
        n = len(y)
        self.leaf_p = sum(y) / n if n else 0.5
        if self.depth == 0 or n < 2 * self.min_leaf or self.leaf_p in (0.0, 1.0):
            return self
        best = (None, None, 1e9)
        for f in feats:
            vals = sorted(set(r[f] for r in X))
            if len(vals) < 2:
                continue
            cands = vals if len(vals) <= self.max_thresh else \
                vals[:: max(1, len(vals) // self.max_thresh)]
            for t in cands:
                ly = [yi for xi, yi in zip(X, y) if xi[f] <= t]
                ry = [yi for xi, yi in zip(X, y) if xi[f] > t]
                if len(ly) < self.min_leaf or len(ry) < self.min_leaf:
                    continue
                imp = (len(ly) * _gini(sum(ly), len(ly)) +
                       len(ry) * _gini(sum(ry), len(ry))) / n
                if imp < best[2]:
                    best = (f, t, imp)
        if best[0] is None:
            return self
        self.f, self.t, _ = best
        lX = [x for x in X if x[self.f] <= self.t]
        lY = [y[i] for i, x in enumerate(X) if x[self.f] <= self.t]
        rX = [x for x in X if x[self.f] > self.t]
        rY = [y[i] for i, x in enumerate(X) if x[self.f] > self.t]
        self.left = _Tree(self.depth - 1, self.min_leaf).fit(lX, lY, feats)
        self.right = _Tree(self.depth - 1, self.min_leaf).fit(rX, rY, feats)
        return self

    def proba(self, x: list[float]) -> float:
        if self.f is None:
            return self.leaf_p
        return (self.left if x[self.f] <= self.t else self.right).proba(x)


class RandomForestNode(BaseNode):
    kind = "base"
    summary = "Random-forest node: bagged shallow trees with feature subsampling."

    def __init__(self, n_trees: int = 10, depth: int = 3, seed: int = 5,
                 name: str = "random_forest"):
        self.name = name
        self.n_trees, self.depth, self.seed = n_trees, depth, seed
        self.trees: list[_Tree] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "RandomForestNode":
        n, d = len(X), len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        rng = random.Random(self.seed)
        m = max(1, int(d ** 0.5))
        self.trees = []
        for _ in range(self.n_trees):
            idx = [rng.randrange(n) for _ in range(n)]              # bootstrap
            bX, bY = [X[i] for i in idx], [y[i] for i in idx]
            feats = rng.sample(range(d), m)                         # feature subset
            self.trees.append(_Tree(self.depth).fit(bX, bY, feats))
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        return [sum(t.proba(x) for t in self.trees) / len(self.trees) for x in X]


class RegimeGatedNode(BaseNode):
    kind = "base"
    summary = "Regime-gated node: separate linear model per volatility regime."

    def __init__(self, gate_idx: int = 8, name: str = "regime_gated"):
        self.name = name
        self.gate_idx = gate_idx
        self.lo = LogisticRegressionNode(name=f"{name}__lo")
        self.hi = LogisticRegressionNode(name=f"{name}__hi")
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "RegimeGatedNode":
        d = len(X[0])
        g = min(self.gate_idx, d - 1)
        self.gate_idx = g
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1) [regime-gated]")
        gv = sorted(r[g] for r in X)
        self.thresh = gv[len(gv) // 2]                              # median split
        loX = [x for x in X if x[g] <= self.thresh]
        loY = [y[i] for i, x in enumerate(X) if x[g] <= self.thresh]
        hiX = [x for x in X if x[g] > self.thresh]
        hiY = [y[i] for i, x in enumerate(X) if x[g] > self.thresh]
        # guard against an empty/degenerate regime
        self.lo.fit(loX or X, loY or y)
        self.hi.fit(hiX or X, hiY or y)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        out = []
        for x in X:
            mdl = self.lo if x[self.gate_idx] <= self.thresh else self.hi
            out.append(mdl.predict_proba([x])[0])
        return out
