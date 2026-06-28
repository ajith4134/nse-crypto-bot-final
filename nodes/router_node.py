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


# --------------------------------------------------------------------------- #
#  Phase-3 frontier: Hellsemble "circles of difficulty" + deep (L2/L3) routing
# --------------------------------------------------------------------------- #
def _argmax(row: list[float]) -> int:
    bi, bv = 0, row[0]
    for i, v in enumerate(row):
        if v > bv:
            bv, bi = v, i
    return bi


def _split_groups(items: list, g: int) -> list[list]:
    """Contiguous near-equal partition of `items` into at most `g` groups."""
    g = max(1, min(g, len(items)))
    size = (len(items) + g - 1) // g
    return [items[i:i + size] for i in range(0, len(items), size)]


class HellsembleRouterNode(BaseNode):
    """Hellsemble 'circles of difficulty' router — the plan's named Phase-3 mechanism.

    Unlike ``LearnedRouterNode`` (every expert sees ALL data; DCS picks a local
    winner per query), Hellsemble SPECIALISES experts on progressively harder
    subsets: expert r is trained only on the instances no earlier expert solved
    (its 'circle of difficulty'). Each training instance is then assigned to the
    first expert in the sequence that solved it; a k-NN gate over standardized
    features routes a query to the locally-dominant expert.

    Task-aware (binary | multiclass | regression): 'solved' means argmax==label
    for classification, or absolute error <= a learned tolerance for regression,
    so the same node plugs into the multi-output head network (see run_multi).

    Inputs: Matrix + Labels/targets.  Outputs: routed predict_output rows.
    """
    kind = "router"
    summary = "Hellsemble circles-of-difficulty router (experts specialise on the hard remainder)."

    def __init__(self, expert_factories: list[NodeFactory], k: int = 25,
                 max_experts: int | None = None, min_remaining: int = 20,
                 order_experts: bool = True, task: str = "binary", head: str = "y",
                 name: str = "hellsemble_router"):
        self.name = name
        self.expert_factories = expert_factories
        self.k = k
        self.max_experts = max_experts or len(expert_factories)
        self.min_remaining = min_remaining
        self.order_experts = order_experts        # lead the circles with the strongest expert
        self.task = task
        self.head = head
        self.experts: list[BaseNode] = []
        self.expert_names: list[str] = []
        self.schema = IOSchema(0, "features", "routed output [hellsemble]")

    # ── standardization for the gate's neighbour space ──
    def _z(self, x: list[float]) -> list[float]:
        return [(x[j] - self.mean[j]) / self.std[j] for j in range(len(x))]

    def _order(self, X: Matrix, y: Labels) -> list[NodeFactory]:
        """Sort factories by standalone strength on an internal 80/20 holdout
        (accuracy for classification, −MAE for regression), strongest first."""
        c = max(1, int(len(X) * 0.8))
        Xa, ya, Xb, yb = X[:c], y[:c], X[c:], y[c:]
        if not Xb:
            return list(self.expert_factories)
        strengths = []
        for f in self.expert_factories:
            m = f()
            m.head, m.task = self.head, self.task
            m.fit(Xa, ya)
            out = m.predict_output(Xb)
            if self._cls:
                s = sum(_argmax(r) == int(t) for r, t in zip(out, yb)) / len(yb)
            else:
                s = -sum(abs(float(r[0]) - float(t)) for r, t in zip(out, yb)) / len(yb)
            strengths.append(s)
        return [f for _, f in sorted(zip(strengths, self.expert_factories),
                                     key=lambda t: -t[0])]

    def _solved(self, row: list[float], yt, tol: float) -> bool:
        if self._cls:
            return _argmax(row) == int(yt)
        return abs(float(row[0]) - float(yt)) <= tol

    def _loss(self, row: list[float], yt) -> float:
        if self._cls:
            c = int(yt)
            p = row[c] if 0 <= c < len(row) else 0.0
            return 1.0 - float(p)
        return abs(float(row[0]) - float(yt))

    def fit(self, X: Matrix, y: Labels) -> "HellsembleRouterNode":
        n, d = len(X), len(X[0])
        self._cls = self.task in ("binary", "multiclass")
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [hellsemble]")
        self.mean = [sum(r[j] for r in X) / n for j in range(d)]
        self.std = [(sum((r[j] - self.mean[j]) ** 2 for r in X) / n) ** 0.5 or 1.0
                    for j in range(d)]
        self._prep = _fo.prepare([self._z(x) for x in X])
        self._k = min(self.k, n)

        # Hellsemble is sensitive to the LEAD learner: a weak expert-0 'solves' the
        # easy bulk first, collapsing the gate onto it. Order factories strongest-
        # first on an internal holdout so the circles start from a strong base.
        factories = self._order(X, y) if (self.order_experts and len(self.expert_factories) > 1) \
            else list(self.expert_factories)

        # ── circles of difficulty: each expert trains on the unsolved remainder ──
        self.experts, self.expert_names = [], []
        remaining = list(range(n))
        tol = 0.0
        r = 0
        while remaining and len(self.experts) < self.max_experts:
            ysub = [y[i] for i in remaining]
            if self._cls and len(set(ysub)) < 2 and self.experts:
                break                                   # remainder is one class — nothing to split
            e = factories[r % len(factories)]()
            e.head, e.task = self.head, self.task
            e.name = f"{e.name}#{r}"
            e.fit([X[i] for i in remaining], ysub)
            self.experts.append(e)
            self.expert_names.append(e.name)
            out = e.predict_output([X[i] for i in remaining])
            if not self._cls and r == 0:                # regression solve-tolerance = median error
                errs = sorted(abs(float(o[0]) - float(yy)) for o, yy in zip(out, ysub))
                tol = errs[len(errs) // 2] if errs else 0.0
            still = [i for li, i in enumerate(remaining)
                     if not self._solved(out[li], y[i], tol)]
            if len(still) == len(remaining):            # this expert solved nothing new — stop
                break
            remaining = still
            r += 1
            if len(remaining) < self.min_remaining:
                break
        if not self.experts:                            # degenerate guard: always ≥1 expert
            e = self.expert_factories[0]()
            e.head, e.task = self.head, self.task
            e.fit(X, y)
            self.experts, self.expert_names = [e], [e.name]
        self._tol = tol

        # ── gate target: first expert (in difficulty order) that solves each point ──
        full = [e.predict_output(X) for e in self.experts]
        self._assigned = []
        for i in range(n):
            a = None
            for ei in range(len(self.experts)):
                if self._solved(full[ei][i], y[i], tol):
                    a = ei
                    break
            if a is None:                               # unsolved by all → lowest-loss expert
                a = min(range(len(self.experts)), key=lambda ei: self._loss(full[ei][i], y[i]))
            self._assigned.append(a)
        return self

    def _route(self, x: list[float]) -> int:
        dd = _fo.sqdists_prepared(self._prep, self._z(x))
        nbrs = sorted(range(len(dd)), key=lambda i: dd[i])[: self._k]
        votes: dict[int, int] = {}
        for i in nbrs:
            a = self._assigned[i]
            votes[a] = votes.get(a, 0) + 1
        return max(votes, key=lambda e: (votes[e], -e))

    def predict_output(self, X: Matrix) -> list[list[float]]:
        outs = [e.predict_output(X) for e in self.experts]
        return [outs[self._route(x)][qi] for qi, x in enumerate(X)]

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        if self.task == "binary":
            return [float(r[1]) for r in rows]
        return [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [_argmax(r) for r in rows]

    def routing_histogram(self, X: Matrix) -> dict:
        counts = {n: 0 for n in self.expert_names}
        for x in X:
            counts[self.expert_names[self._route(x)]] += 1
        return counts


class DeepRouterNode(BaseNode):
    """Deep (L2/L3) routing — the plan's stated open research gap ('routing at depth').

    Splits the expert pool into `branching` groups; each group becomes a
    sub-router (recursively, depth-1). A top Hellsemble router then routes among
    those sub-routers, treating each whole sub-router as one composite expert.
    depth=1 reduces to a flat ``HellsembleRouterNode``; depth=2 is
    routers-of-routers (L2); depth=3 adds one more level (L3).

    Composition is clean because every router IS a NodeProtocol node: the top
    router fits each sub-router on its own difficulty circle, exactly mirroring
    the single-layer mechanism one level up.
    """
    kind = "router"
    summary = "Deep router (L2/L3): a Hellsemble router whose experts are themselves routers."

    def __init__(self, expert_factories: list[NodeFactory], depth: int = 2,
                 branching: int = 3, k: int = 25, task: str = "binary",
                 head: str = "y", name: str = "deep_router"):
        self.name = name
        self.task = task
        self.head = head
        self.depth = max(1, depth)
        self.branching = branching
        self.k = k
        self.expert_factories = expert_factories
        self.schema = IOSchema(0, "features", f"{task} output [deep L{self.depth}]")

        if self.depth <= 1 or len(expert_factories) <= branching:
            sub_factories = expert_factories                       # base layer: route raw experts
        else:
            groups = _split_groups(expert_factories, branching)
            sub_factories = [
                (lambda g=g, i=i: DeepRouterNode(
                    g, depth=self.depth - 1, branching=branching, k=k,
                    task=task, head=head, name=f"{name}.L{self.depth - 1}g{i}"))
                for i, g in enumerate(groups)
            ]
        self._router = HellsembleRouterNode(sub_factories, k=k, task=task,
                                            head=head, name=f"{name}.router")

    def fit(self, X: Matrix, y: Labels) -> "DeepRouterNode":
        self._router.head, self._router.task = self.head, self.task
        self._router.fit(X, y)
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [deep L{self.depth}]")
        return self

    @property
    def layer_names(self) -> list[str]:
        """Names of the immediate sub-routers this level routes among (post-fit)."""
        return list(self._router.expert_names)

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return self._router.predict_output(X)

    def predict_proba(self, X: Matrix) -> Vector:
        return self._router.predict_proba(X)

    def predict(self, X: Matrix) -> Labels:
        return self._router.predict(X)

    def routing_histogram(self, X: Matrix) -> dict:
        return self._router.routing_histogram(X)
