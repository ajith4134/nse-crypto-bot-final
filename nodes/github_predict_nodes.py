"""GitHub-project predictor nodes — CatBoost, NGBoost, EBM, skforecast.

Wraps four mature open-source GitHub prediction libraries behind the project
NodeProtocol (core/node_protocol.py), in the multi-output contract (task in
{binary, multiclass, regression}; predict_output rows are per-class
probabilities for classification or a length-1 [value] for regression). The
mechanics are COPIED from the existing node zoo so the brain, router, eval plane
and dashboard are unchanged — only the model behind the interface differs:

  - oss_nodes.SklearnNode        : multiclass-aware class-probability readout,
                                    label-order remap, degenerate single-class guard.
  - oss_nodes.SklearnRegressorNode: regression head, min-max pseudo-probability,
                                    degenerate constant-target guard.
  - quant_nodes._HeadBase        : task-aware predict_output (classification =
                                    class-prob rows, regression = [value], binary
                                    = [1-p, p]) + augment->readout pattern.

Like run_multi.py, a node's `task` is set by the runner (`nd.task = head.task`)
before fit; the DIRECT nodes (CatBoost/NGBoost/EBM) then instantiate the
classifier or the regressor variant of the wrapped library accordingly, while
classification auto-detects binary vs multiclass from the training labels.

  1. CatBoostNode   (kind="ml") — CatBoost gradient-boosted trees.
  2. NGBoostNode    (kind="ml") — NGBoost probabilistic boosting (predictive std).
  3. EBMNode        (kind="ml") — interpret glassbox Explainable Boosting Machine.
  4. SkforecastNode (kind="ml") — LightGBM in a skforecast recursive forecaster,
                                  one-step forecast appended as a feature -> readout.

Inputs:  Matrix of feature rows + Labels (0/1/.. classification or float regr).
Outputs: per-row p(class=1) (binary) and the general predict_output contract.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
#  Direct X->y base (CatBoost / NGBoost / EBM)
# --------------------------------------------------------------------------- #
class _DirectNode(BaseNode):
    """Task-aware adapter that fits an estimator directly on X->y.

    Mechanics merged from oss_nodes.SklearnNode (multiclass class-prob readout +
    label-order remap + single-class guard) and SklearnRegressorNode (regression
    head + min-max pseudo-proba + constant-target guard). Subclasses supply the
    library's classifier / regressor via `_make_classifier(k)` / `_make_regressor()`.
    """

    kind = "ml"

    def __init__(self, name: str, summary: str):
        self.name = name
        self.summary = summary
        self.task = "binary"          # set by runner (nd.task = head.task) before fit
        self.head = "y"
        self.n_classes = 2
        self._classes: list[int] = []
        self._est = None
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0
        self.schema = IOSchema(0, "features", "p(class=1)")

    # ---- subclass hooks --------------------------------------------------- #
    def _make_classifier(self, n_classes: int):
        raise NotImplementedError

    def _make_regressor(self):
        raise NotImplementedError

    def _reg_predict(self, Xa: np.ndarray) -> list[float]:
        """Regression point prediction (subclass may override, e.g. NGBoost mean)."""
        return [float(v) for v in self._est.predict(Xa)]

    # ---- helpers ---------------------------------------------------------- #
    def _cols(self) -> list[int]:
        cols = getattr(self._est, "classes_", None)
        if cols is None:                                 # e.g. NGBClassifier
            return list(self._classes)
        return [int(c) for c in cols]

    # ---- fit -------------------------------------------------------------- #
    def fit(self, X: Matrix, y: Labels) -> "_DirectNode":
        Xa = np.asarray(X, dtype=float)
        d = Xa.shape[1]
        if self.task == "regression":
            ya = np.asarray(y, dtype=float)
            self.n_classes = 1
            self.schema = IOSchema(d, f"{d} numeric features", "predicted value")
            self._ymin = float(ya.min()) if len(ya) else 0.0
            self._ymax = float(ya.max()) if len(ya) else 1.0
            if self._ymax <= self._ymin:                 # degenerate constant target
                self._constant = float(ya[0]) if len(ya) else 0.0
                return self
            self._constant = None
            self._est = self._make_regressor()
            self._est.fit(Xa, ya)
            return self
        # classification (binary or multiclass, auto-detected from labels)
        ya = np.asarray(y, dtype=int)
        self._classes = sorted(set(int(v) for v in ya))
        k = len(self._classes)
        if k > 2:
            self.task = "multiclass"
            self.n_classes = k
            self.schema = IOSchema(d, f"{d} numeric features",
                                   f"p(class) over {k} classes")
        else:
            self.task = "binary"
            self.n_classes = 2
            self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        if k < 2:                                         # only one class present
            return self
        self._est = self._make_classifier(k)
        self._est.fit(Xa, ya)
        return self

    # ---- predict ---------------------------------------------------------- #
    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            vals = self._raw_reg(X)
            span = self._ymax - self._ymin
            if span <= 0.0:
                return [0.5] * len(vals)
            return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._est.predict_proba(np.asarray(X, dtype=float))
        if self.task == "multiclass":
            return [float(np.asarray(r).max()) for r in proba]
        cols = self._cols()
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(r[j]) for r in proba]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            return [[v] for v in self._raw_reg(X)]
        if len(self._classes) < 2:                        # degenerate single class
            return [[1.0]] * len(X)
        if self.task == "multiclass":
            proba = self._est.predict_proba(np.asarray(X, dtype=float))
            cols = self._cols()
            order = [cols.index(c) for c in self._classes]
            return [[float(np.asarray(r)[o]) for o in order] for r in proba]
        return super().predict_output(X)                  # binary -> [1-p, p]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            return self._raw_reg(X)
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        return super().predict(X)                         # binary: threshold 0.5

    def _raw_reg(self, X: Matrix) -> list[float]:
        if self._constant is not None:
            return [self._constant] * len(X)
        return self._reg_predict(np.asarray(X, dtype=float))


# --------------------------------------------------------------------------- #
#  1. CatBoost — yandex/catboost
# --------------------------------------------------------------------------- #
class CatBoostNode(_DirectNode):
    """CatBoost gradient-boosted trees (CatBoostClassifier / CatBoostRegressor).

    iterations~200, verbose=False, thread_count=-1. Fits X->y directly; uses
    predict_proba for the classification heads and the task-aware predict_output.
    """

    def __init__(self, name: str = "catboost", iterations: int = 200):
        super().__init__(name, f"CatBoost gradient-boosted trees ({iterations} iters).")
        self.iterations = iterations

    def _make_classifier(self, n_classes: int):
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=self.iterations, verbose=False,
                                  thread_count=-1, random_seed=1)

    def _make_regressor(self):
        from catboost import CatBoostRegressor
        return CatBoostRegressor(iterations=self.iterations, verbose=False,
                                 thread_count=-1, random_seed=1)


# --------------------------------------------------------------------------- #
#  2. NGBoost — stanfordmlgroup/ngboost  (probabilistic boosting)
# --------------------------------------------------------------------------- #
class NGBoostNode(_DirectNode):
    """NGBoost natural-gradient probabilistic boosting (NGBClassifier / NGBRegressor).

    Classification uses predict_proba (NGBClassifier exposes no `classes_`, so
    columns are read in sorted-label order). Regression reads the predictive
    distribution: predict_output uses the Normal mean and the predictive standard
    deviation is stored in `self.pred_std_` (per-row uncertainty). n_estimators
    kept modest (~200) for CPU speed.
    """

    def __init__(self, name: str = "ngboost", n_estimators: int = 200):
        super().__init__(name, f"NGBoost probabilistic boosting ({n_estimators} est).")
        self.n_estimators = n_estimators
        self.pred_std_: np.ndarray | None = None

    def _make_classifier(self, n_classes: int):
        from ngboost import NGBClassifier
        return NGBClassifier(n_estimators=self.n_estimators, verbose=False,
                             random_state=1)

    def _make_regressor(self):
        from ngboost import NGBRegressor
        return NGBRegressor(n_estimators=self.n_estimators, verbose=False,
                            random_state=1)

    def _reg_predict(self, Xa: np.ndarray) -> list[float]:
        dist = self._est.pred_dist(Xa)                    # Normal predictive dist
        mean = np.asarray(getattr(dist, "loc", None)
                          if getattr(dist, "loc", None) is not None
                          else dist.mean(), dtype=float).reshape(-1)
        try:
            self.pred_std_ = np.asarray(dist.scale, dtype=float).reshape(-1)
        except Exception:
            self.pred_std_ = None
        return [float(v) for v in mean]


# --------------------------------------------------------------------------- #
#  3. EBM — interpretml/interpret  (glassbox GAM)
# --------------------------------------------------------------------------- #
class EBMNode(_DirectNode):
    """Explainable Boosting Machine (interpret glassbox GAM): an interpretable,
    additive boosted model. ExplainableBoostingClassifier / ...Regressor expose
    the sklearn predict_proba / predict API used by the task-aware readout."""

    def __init__(self, name: str = "ebm"):
        super().__init__(name, "interpret Explainable Boosting Machine (glassbox GAM).")

    def _make_classifier(self, n_classes: int):
        from interpret.glassbox import ExplainableBoostingClassifier
        return ExplainableBoostingClassifier(random_state=1)

    def _make_regressor(self):
        from interpret.glassbox import ExplainableBoostingRegressor
        return ExplainableBoostingRegressor(random_state=1)


# --------------------------------------------------------------------------- #
#  Task-aware readout (copied from quant_nodes._HeadBase) for SkforecastNode
# --------------------------------------------------------------------------- #
def _readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = Ridge() if task == "regression" else LogisticRegression(max_iter=1000)
    return make_pipeline(StandardScaler(), est)


class _HeadBase(BaseNode):
    """Task-aware readout + predict_output, copied from quant_nodes mechanics.
    Subclasses provide `_augment(X) -> np.ndarray` (features per row)."""

    kind = "ml"

    def __init__(self, name: str, summary: str, col: int = 0):
        self.name, self.summary = name, summary
        self.col = col
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "out")

    def _augment(self, X: Matrix) -> np.ndarray:        # subclass hook
        raise NotImplementedError

    def fit(self, X: Matrix, y: Labels) -> "_HeadBase":
        ya = np.asarray(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", self.task)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:
                return self
        self._ro = _readout(self.task)
        self._ro.fit(self._augment(X), ya)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task != "regression" and len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        A = self._augment(X)
        if self.task == "regression":
            v = self._ro.predict(A)
            lo, hi = float(np.min(v)), float(np.max(v))
            return [float((x - lo) / (hi - lo)) if hi > lo else 0.5 for x in v]
        proba = self._ro.predict_proba(A)
        if self.task == "multiclass":
            return [float(r.max()) for r in proba]
        cols = list(self._ro.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(r[j]) for r in proba]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task != "regression" and len(self._classes) < 2:
            return [[1.0]] * len(X)
        if self.task == "regression":
            return [[float(v)] for v in self._ro.predict(self._augment(X))]
        if self.task == "multiclass":
            proba = self._ro.predict_proba(self._augment(X))
            cols = list(self._ro.classes_)
            order = [cols.index(c) for c in self._classes]
            return [[float(r[o]) for o in order] for r in proba]
        return super().predict_output(X)                  # binary [1-p, p]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [float(v) for v in self._ro.predict(self._augment(X))]
        return super().predict(X)


# --------------------------------------------------------------------------- #
#  4. skforecast — JoaquinAmatRodrigo/skforecast (recursive forecaster)
# --------------------------------------------------------------------------- #
class SkforecastNode(_HeadBase):
    """LightGBM regressor wrapped in a skforecast ForecasterRecursive (lags=12)
    on the TARGET series. Fit-once: produce one-step forecasts aligned per row
    (in-sample fitted for the training rows, recursive predict for the horizon)
    and APPEND that forecast as a feature to X -> task-aware readout, so the same
    node serves classification heads too.

    Robust to skforecast API drift: tries `from skforecast.recursive import
    ForecasterRecursive` (recent) then `estimator=`/`regressor=` kwargs; if any of
    that fails it falls back to an AR last-value/previous-value forecast and sets
    `self.fallback` so the runner can flag it.
    """

    def __init__(self, name: str = "skforecast_lgbm", col: int = 0, lags: int = 12):
        super().__init__(name, "skforecast ForecasterRecursive (LightGBM, lags=12) one-step forecast.", col)
        self.lags = lags
        self._fc = None
        self._ytr: np.ndarray | None = None
        self._fitted_train: np.ndarray | None = None
        self.fallback = False

    def fit(self, X: Matrix, y: Labels) -> "SkforecastNode":
        self._ytr = np.asarray(y, dtype=float)
        self._fitted_train = None
        self._fc = None
        self.fallback = False
        try:
            import pandas as pd
            from lightgbm import LGBMRegressor
            from skforecast.recursive import ForecasterRecursive
            s = pd.Series(self._ytr)
            reg = LGBMRegressor(n_estimators=200, n_jobs=-1, verbose=-1, random_state=1)
            try:
                self._fc = ForecasterRecursive(estimator=reg, lags=self.lags)
            except TypeError:                             # older kwarg name
                self._fc = ForecasterRecursive(regressor=reg, lags=self.lags)
            self._fc.fit(y=s)
            # in-sample one-step fitted values (aligned to rows [lags:])
            Xtr, _ = self._fc.create_train_X_y(s)
            est = getattr(self._fc, "estimator", None) or getattr(self._fc, "regressor", None)
            fitted_tail = np.asarray(est.predict(Xtr), dtype=float)
            fitted = np.empty(len(self._ytr), dtype=float)
            seed = float(np.mean(self._ytr)) if len(self._ytr) else 0.0
            fitted[:self.lags] = seed
            fitted[self.lags:] = fitted_tail[: max(0, len(self._ytr) - self.lags)]
            self._fitted_train = fitted
        except Exception:                                 # robust AR fallback
            self._fc = None
            self.fallback = True
            yt = self._ytr
            fitted = np.empty(len(yt), dtype=float)
            if len(yt):
                fitted[0] = float(yt[0])
                fitted[1:] = yt[:-1]                       # AR(1) previous-value
            self._fitted_train = fitted
        return super().fit(X, y)

    def _forecast(self, n: int) -> np.ndarray:
        # training rows: length-matched in-sample fitted (real or AR fallback)
        if self._fitted_train is not None and n == len(self._fitted_train):
            return self._fitted_train
        # other lengths (e.g. test horizon): recursive multi-step forecast
        if self._fc is not None:
            try:
                pred = np.asarray(self._fc.predict(steps=n), dtype=float).reshape(-1)
                if len(pred) == n:
                    return pred
            except Exception:
                pass
        last = float(self._ytr[-1]) if self._ytr is not None and len(self._ytr) else 0.0
        return np.full(n, last, dtype=float)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in r] for r in X], dtype=float)
        fc = self._forecast(len(X)).reshape(-1, 1)
        return np.hstack([base, fc])


# --------------------------------------------------------------------------- #
#  No-arg factories
# --------------------------------------------------------------------------- #
def catboost_node() -> CatBoostNode:
    return CatBoostNode()


def ngboost_node() -> NGBoostNode:
    return NGBoostNode()


def ebm_node() -> EBMNode:
    return EBMNode()


def skforecast_node() -> SkforecastNode:
    return SkforecastNode()
