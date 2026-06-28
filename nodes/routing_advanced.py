"""Ultra-advanced routing/combination nodes — the reuse-first Phase-3 frontier.

Three upgrades the research flagged as the highest value/effort moves to push the
network's routing past static stacking, all CPU-only and behind NodeProtocol:

  • DESRouterNode          — DESlib dynamic ensemble selection (KNORA-U/E, META-DES,
                             OLA): per-query competence routing over a region of
                             competence. The one mature OSS lineage that genuinely
                             beats global stacking per-instance. (classification)
  • ConformalGatedRouterNode — MAPIE split-conformal uncertainty-gated routing:
                             route each input to the expert whose calibrated
                             prediction SET is smallest (most confident).
                             (classification)
  • CaruanaEnsembleNode    — greedy ensemble selection (Caruana 2004), the static
                             global combiner inside AutoGluon/auto-sklearn; the
                             robust, dependency-free default/fallback. (any task)

Reuse note: DESlib 0.3.7 predates scikit-learn 1.6's removal of
`BaseEstimator._validate_data`; `_apply_sklearn_compat()` restores it (delegating
to the new module-level `validate_data`) so DESlib runs unchanged on sklearn 1.8.
Each node wraps fitted NodeProtocol nodes as sklearn estimators (`_NodeAsSklearn`)
so the whole node zoo drops into DESlib/MAPIE with no per-node changes.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector

warnings.filterwarnings("ignore")


def _apply_sklearn_compat() -> None:
    """Restore BaseEstimator._validate_data removed in sklearn>=1.6 (DESlib needs it)."""
    from sklearn.base import BaseEstimator
    if hasattr(BaseEstimator, "_validate_data"):
        return
    from sklearn.utils.validation import validate_data as _vd

    def _validate_data(self, X="no_validation", y="no_validation", **kw):
        return _vd(self, X=X, y=y, **kw)

    BaseEstimator._validate_data = _validate_data


def _sklearn_adapter():
    """Build the _NodeAsSklearn adapter class (sklearn imported lazily)."""
    from sklearn.base import BaseEstimator, ClassifierMixin

    class _NodeAsSklearn(BaseEstimator, ClassifierMixin):
        """Wrap an already-fitted NodeProtocol node as a fitted sklearn classifier."""

        def __init__(self, node=None):
            self.node = node

        def fit(self, X, y):
            self.classes_ = np.unique(np.asarray(y).astype(int))
            return self

        def predict(self, X):
            return np.asarray(self.node.predict(X)).astype(int)

        def predict_proba(self, X):
            return np.asarray(self.node.predict_output(X), dtype=float)

    return _NodeAsSklearn


def _split(X, y, frac):
    cut = int(len(X) * (1 - frac))
    return X[:cut], y[:cut], X[cut:], y[cut:]


def _argmax_rows(out: np.ndarray) -> Labels:
    return [int(i) for i in np.argmax(out, axis=1)]


class DESRouterNode(BaseNode):
    """Dynamic Ensemble Selection router (DESlib) — per-query competence routing.

    Fits the expert pool on a train split, then DESlib builds each query's 'region
    of competence' from a held-out DSEL set and selects/weights the locally-best
    experts (KNORA-U = weighted vote of locally-correct experts; KNORA-E = only
    experts perfect in the region; META-DES = a learned competence meta-classifier;
    OLA = single locally-best expert). Classification only (DESlib's domain).
    """
    kind = "router"
    summary = "DESlib dynamic ensemble selection (per-query competence routing)."

    def __init__(self, expert_factories: list[NodeFactory], method: str = "KNORAU",
                 k: int = 7, dsel_frac: float = 0.3, task: str = "binary",
                 head: str = "y", name: str = "des_router"):
        self.name = name
        self.expert_factories = expert_factories
        self.method = method
        self.k = k
        self.dsel_frac = dsel_frac
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [DES:{method}]")

    def fit(self, X: Matrix, y: Labels) -> "DESRouterNode":
        if self.task == "regression":
            raise NotImplementedError("DESRouterNode is classification-only (DESlib).")
        _apply_sklearn_compat()
        from deslib.dcs import LCA, OLA
        from deslib.des import KNORAE, KNORAU, METADES
        methods = {"KNORAU": KNORAU, "KNORAE": KNORAE, "METADES": METADES,
                   "OLA": OLA, "LCA": LCA}
        M = methods[self.method]
        Adapter = _sklearn_adapter()

        Xa, ya, Xb, yb = _split(X, y, self.dsel_frac)
        pool = []
        for f in self.expert_factories:
            nd = f()
            nd.head, nd.task = self.head, self.task
            nd.fit(Xa, ya)
            pool.append(Adapter(nd).fit(Xa, ya))
        self.expert_names = [p.node.name for p in pool]
        self._des = M(pool_classifiers=pool, k=max(1, min(self.k, len(Xb) - 1)))
        self._des.fit(np.asarray(Xb, dtype=float), np.asarray(yb).astype(int))
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [DES:{self.method}]")
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return np.asarray(self._des.predict_proba(np.asarray(X, dtype=float))).tolist()

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        return _argmax_rows(np.asarray(self.predict_output(X)))


class ConformalGatedRouterNode(BaseNode):
    """Uncertainty-gated router (MAPIE split-conformal) — route by confidence.

    Each expert gets a split-conformal wrapper calibrated on a held-out set; for a
    query, the expert whose calibrated prediction SET is smallest (ties broken by
    calibration accuracy) is the most locally-confident and handles it.
    Classification only.

    COVERAGE CAVEAT: selecting the narrowest set per instance and reporting that
    set would break MAPIE's marginal coverage guarantee (selection bias). Set size
    is used here ONLY as a routing score — not as a reported confidence interval.
    """
    kind = "router"
    summary = "Conformal uncertainty-gated router (route to the most-confident expert)."

    def __init__(self, expert_factories: list[NodeFactory], confidence: float = 0.9,
                 calib_frac: float = 0.3, task: str = "binary", head: str = "y",
                 name: str = "conformal_router"):
        self.name = name
        self.expert_factories = expert_factories
        self.confidence = confidence
        self.calib_frac = calib_frac
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [conformal-gated]")

    def fit(self, X: Matrix, y: Labels) -> "ConformalGatedRouterNode":
        if self.task == "regression":
            raise NotImplementedError("ConformalGatedRouterNode is classification-only (MAPIE).")
        from mapie.classification import SplitConformalClassifier
        Adapter = _sklearn_adapter()
        Xa, ya, Xb, yb = _split(X, y, self.calib_frac)
        Xbn, ybn = np.asarray(Xb, dtype=float), np.asarray(yb).astype(int)
        self.experts, self._scc, self._calib_acc, self.expert_names = [], [], [], []
        for f in self.expert_factories:
            nd = f()
            nd.head, nd.task = self.head, self.task
            nd.fit(Xa, ya)
            scc = SplitConformalClassifier(estimator=Adapter(nd).fit(Xa, ya),
                                           confidence_level=self.confidence,
                                           conformity_score="lac", prefit=True)
            scc.conformalize(Xbn, ybn)
            self.experts.append(nd)
            self._scc.append(scc)
            self._calib_acc.append(float(np.mean(np.asarray(nd.predict(Xb)).astype(int) == ybn)))
            self.expert_names.append(nd.name)
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [conformal-gated]")
        return self

    def _set_sizes(self, X: Matrix) -> np.ndarray:
        Xn = np.asarray(X, dtype=float)
        sizes = []
        for scc in self._scc:
            _, ys = scc.predict_set(Xn)
            ys = np.asarray(ys)
            if ys.ndim == 3:                      # (n, n_classes, n_confidence) -> drop last
                ys = ys[..., 0]
            sizes.append(ys.sum(axis=1).reshape(len(X)))
        return np.asarray(sizes)                   # (n_experts, n)

    def predict_output(self, X: Matrix) -> list[list[float]]:
        sizes = self._set_sizes(X)
        outs = [np.asarray(nd.predict_output(X)) for nd in self.experts]
        res = []
        for i in range(len(X)):
            col = sizes[:, i]
            best = min(range(len(self.experts)), key=lambda e: (col[e], -self._calib_acc[e]))
            res.append(outs[best][i].tolist())
        return res

    def routing_histogram(self, X: Matrix) -> dict:
        sizes = self._set_sizes(X)
        counts = {n: 0 for n in self.expert_names}
        for i in range(len(X)):
            col = sizes[:, i]
            best = min(range(len(self.experts)), key=lambda e: (col[e], -self._calib_acc[e]))
            counts[self.expert_names[best]] += 1
        return counts

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        return _argmax_rows(np.asarray(self.predict_output(X)))


class CaruanaEnsembleNode(BaseNode):
    """Greedy ensemble selection (Caruana et al. 2004) — the robust STATIC combiner.

    Repeatedly adds, WITH REPLACEMENT, the expert whose inclusion most improves a
    held-out score (accuracy for classification, −MAE for regression); the repeat
    counts become blend weights. This is the global combiner used by AutoGluon and
    auto-sklearn — tiny, CPU-trivial, hard to beat as a default. Task-aware, so it
    serves any head; the natural safe fallback when per-query routing is uncertain.
    """
    kind = "meta"
    summary = "Caruana greedy ensemble selection (static weighted global combiner)."

    def __init__(self, base_factories: list[NodeFactory], rounds: int = 30,
                 val_frac: float = 0.3, task: str = "binary", head: str = "y",
                 name: str = "caruana_ensemble"):
        self.name = name
        self.base_factories = base_factories
        self.rounds = rounds
        self.val_frac = val_frac
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [caruana]")

    def fit(self, X: Matrix, y: Labels) -> "CaruanaEnsembleNode":
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya, Xb, yb = _split(X, y, self.val_frac)
        ybn = np.asarray(yb, dtype=float)
        val = []
        for f in self.base_factories:
            m = f()
            m.head, m.task = self.head, self.task
            m.fit(Xa, ya)
            val.append(np.asarray(m.predict_output(Xb), dtype=float))

        def score(pred):
            if self._cls:
                return float(np.mean(np.argmax(pred, axis=1) == ybn.astype(int)))
            return -float(np.mean(np.abs(pred[:, 0] - ybn)))

        counts = [0] * len(self.base_factories)
        chosen: list[int] = []
        best_score = -1e18
        for _ in range(self.rounds):
            bj, bs, _bp = None, best_score, None
            for j in range(len(self.base_factories)):
                cand = ((sum(val[c] for c in chosen) + val[j]) / (len(chosen) + 1)
                        if chosen else val[j])
                s = score(cand)
                if bj is None or s > bs:
                    bj, bs = j, s
            if chosen and bs <= best_score:           # no further improvement
                break
            chosen.append(bj)
            counts[bj] += 1
            best_score = bs
        if sum(counts) == 0:
            counts[0] = 1
        self.counts = counts
        self.base_names = [f().name for f in self.base_factories]
        # refit on ALL data for inference
        self.models = []
        for f in self.base_factories:
            m = f()
            m.head, m.task = self.head, self.task
            m.fit(X, y)
            self.models.append(m)
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [caruana]")
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        tot = sum(self.counts)
        acc = None
        for m, c in zip(self.models, self.counts):
            if c == 0:
                continue
            o = np.asarray(m.predict_output(X), dtype=float) * c
            acc = o if acc is None else acc + o
        return (acc / tot).tolist()

    def weights(self) -> dict:
        tot = sum(self.counts) or 1
        return {n: round(c / tot, 3) for n, c in zip(self.base_names, self.counts) if c}

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return _argmax_rows(np.asarray(rows))
