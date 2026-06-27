"""OSS-backed prediction nodes — the reuse-first realignment of the node layer.

Each class wraps a mature, CPU-friendly library behind the SAME `NodeProtocol`
the hand-rolled stdlib nodes used (fit/predict_proba/predict over Matrix/Labels),
so the brain, router, eval plane and dashboard are unchanged — only the model
behind the interface is now production OSS instead of a stdlib miniature:

  - scikit-learn      LogisticRegression, KNN, DecisionTree(stump), MLP,
                      GaussianNB, RandomForest, GradientBoosting, SVC
  - XGBoost           gradient-boosted trees (core tabular predictor)
  - LightGBM          gradient-boosted trees (fast, leaf-wise)
  - ReservoirPy       echo-state reservoir expansion + linear readout (chaos)
  - hmmlearn          Gaussian-HMM latent-regime gating (regime/change-point)
  - nolds             nonlinear-dynamics features (chaos/noise measures)

AutoGluon (production stacked ensemble) and PySR (symbolic regression / Phase-5
equation discovery) live in `nodes.automl_node` and `nodes.symbolic_node` — they
are too slow for the brain's inner growth loop, so they are demonstrated by their
own runners rather than placed in the candidate pool.

Inputs:  Matrix of feature rows + integer Labels (0/1).
Outputs: per-row p(class=1).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  Generic scikit-learn / estimator adapter
# --------------------------------------------------------------------------- #
class SklearnNode(BaseNode):
    """Wraps any classifier exposing fit + predict_proba behind NodeProtocol.

    Generalized to both the BINARY and the MULTICLASS output heads (see
    core/heads.py) while keeping binary behaviour byte-for-byte identical so the
    existing factories and pool are unchanged:

      * fit sees 2 classes -> task="binary"; predict_proba returns p(class=1),
        predict_output returns [p0, p1], predict thresholds at 0.5 (BaseNode).
      * fit sees >2 classes -> task="multiclass", n_classes=K; predict_output
        returns the full per-row class-probability matrix with columns remapped
        to label order 0..K-1, predict returns argmax labels, and predict_proba
        returns the winning-class confidence (max row prob) so the node still
        satisfies the Vector-returning NodeProtocol.

    Handles the degenerate single-class training split (returns the constant
    class) and always reports probabilities in label order regardless of the
    estimator's internal class ordering.
    """

    kind = "base"

    def __init__(self, estimator, name: str, summary: str):
        self.name = name
        self.summary = summary
        self._est = estimator
        self._classes: list[int] = []
        self.task = "binary"
        self.n_classes = 2
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "SklearnNode":
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=int)
        d = Xa.shape[1]
        self._classes = sorted(set(int(v) for v in ya))
        k = len(self._classes)
        if k > 2:                                        # multiclass head
            self.task = "multiclass"
            self.n_classes = k
            self.schema = IOSchema(d, f"{d} numeric features",
                                   f"p(class) over {k} classes")
        else:                                            # binary head (unchanged)
            self.task = "binary"
            self.n_classes = 2
            self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        if k < 2:                                        # only one class present
            return self
        self._est.fit(Xa, ya)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        Xa = np.asarray(X, dtype=float)
        proba = self._est.predict_proba(Xa)
        if self.task == "multiclass":
            # no single "positive" class exists; report the winning-class
            # confidence so the Vector contract still holds (use predict_output
            # for the full per-class matrix).
            return [float(row.max()) for row in proba]
        cols = list(self._est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        """Full per-row class-probability matrix.

        binary -> [p0, p1] rows (BaseNode default, from predict_proba);
        multiclass -> length-K rows, columns ordered by ascending class label
        (0..K-1) regardless of the estimator's internal `classes_` order.
        """
        if self.task != "multiclass":
            return super().predict_output(X)
        if len(self._classes) < 2:                       # degenerate single class
            return [[1.0]] * len(X)
        proba = self._est.predict_proba(np.asarray(X, dtype=float))
        cols = list(self._est.classes_)
        order = [cols.index(c) for c in self._classes]   # est col per sorted label
        return [[float(row[o]) for o in order] for row in proba]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(row))]
                    for row in self.predict_output(X)]
        return super().predict(X)                        # binary: threshold at 0.5


# --------------------------------------------------------------------------- #
#  Concrete scikit-learn node factories
# --------------------------------------------------------------------------- #
def logreg_node(name: str = "sk_logreg") -> SklearnNode:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    return SklearnNode(est, name, "scikit-learn logistic regression (standardized).")


def knn_node(k: int = 5, name: str | None = None) -> SklearnNode:
    from sklearn.neighbors import KNeighborsClassifier
    name = name or f"sk_knn{k}"
    return SklearnNode(KNeighborsClassifier(n_neighbors=k), name,
                       f"scikit-learn k-NN (k={k}); strong on local/XOR-like data.")


def stump_node(name: str = "sk_stump") -> SklearnNode:
    from sklearn.tree import DecisionTreeClassifier
    return SklearnNode(DecisionTreeClassifier(max_depth=1), name,
                       "scikit-learn decision stump (depth-1 tree).")


def tree_node(depth: int = 5, name: str | None = None) -> SklearnNode:
    from sklearn.tree import DecisionTreeClassifier
    name = name or f"sk_tree{depth}"
    return SklearnNode(DecisionTreeClassifier(max_depth=depth), name,
                       f"scikit-learn decision tree (depth={depth}).")


def mlp_node(hidden: int = 16, name: str | None = None) -> SklearnNode:
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    name = name or f"sk_mlp{hidden}"
    est = make_pipeline(StandardScaler(),
                        MLPClassifier(hidden_layer_sizes=(hidden,), max_iter=500,
                                      early_stopping=False, random_state=1))
    return SklearnNode(est, name, f"scikit-learn MLP (1 hidden layer, {hidden} units).")


def gaussnb_node(name: str = "sk_gaussnb") -> SklearnNode:
    from sklearn.naive_bayes import GaussianNB
    return SklearnNode(GaussianNB(), name, "scikit-learn Gaussian Naive Bayes.")


def rf_node(n_trees: int = 100, depth: int | None = None, name: str | None = None) -> SklearnNode:
    from sklearn.ensemble import RandomForestClassifier
    name = name or f"sk_rf{n_trees}"
    return SklearnNode(
        RandomForestClassifier(n_estimators=n_trees, max_depth=depth,
                               n_jobs=-1, random_state=1),
        name, f"scikit-learn random forest ({n_trees} trees).")


def gbdt_node(n_trees: int = 100, name: str = "sk_gbdt") -> SklearnNode:
    from sklearn.ensemble import GradientBoostingClassifier
    return SklearnNode(GradientBoostingClassifier(n_estimators=n_trees, random_state=1),
                       name, f"scikit-learn gradient boosting ({n_trees} trees).")


def svm_node(name: str = "sk_svm") -> SklearnNode:
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    est = make_pipeline(StandardScaler(), SVC(probability=True, random_state=1))
    return SklearnNode(est, name, "scikit-learn RBF-kernel SVM (probabilistic).")


# --------------------------------------------------------------------------- #
#  Gradient-boosting library nodes (the plan's core tabular predictors)
# --------------------------------------------------------------------------- #
def xgboost_node(n_trees: int = 200, depth: int = 4, name: str = "xgboost") -> SklearnNode:
    from xgboost import XGBClassifier
    est = XGBClassifier(n_estimators=n_trees, max_depth=depth, learning_rate=0.1,
                        tree_method="hist", n_jobs=-1, eval_metric="logloss",
                        verbosity=0, random_state=1)
    return SklearnNode(est, name, f"XGBoost gradient-boosted trees ({n_trees}x d{depth}).")


def lightgbm_node(n_trees: int = 200, leaves: int = 31, name: str = "lightgbm") -> SklearnNode:
    from lightgbm import LGBMClassifier
    est = LGBMClassifier(n_estimators=n_trees, num_leaves=leaves, learning_rate=0.1,
                         n_jobs=-1, random_state=1, verbose=-1)
    return SklearnNode(est, name, f"LightGBM leaf-wise boosted trees ({n_trees}, {leaves} leaves).")


# --------------------------------------------------------------------------- #
#  Multiclass classifier factories (generalized SklearnNode; n_classes>2)
# --------------------------------------------------------------------------- #
def rf_multiclass_node(n_trees: int = 100, depth: int | None = None,
                       name: str = "sk_rf_mc") -> SklearnNode:
    from sklearn.ensemble import RandomForestClassifier
    return SklearnNode(
        RandomForestClassifier(n_estimators=n_trees, max_depth=depth,
                               n_jobs=-1, random_state=1),
        name, f"scikit-learn random forest, multiclass-capable ({n_trees} trees).")


def logreg_multiclass_node(name: str = "sk_logreg_mc") -> SklearnNode:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    return SklearnNode(est, name,
                       "scikit-learn logistic regression, multiclass-capable (standardized).")


# --------------------------------------------------------------------------- #
#  Regression node + factories (the magnitude / regression output head)
# --------------------------------------------------------------------------- #
class SklearnRegressorNode(BaseNode):
    """Wraps any regressor exposing fit + predict behind NodeProtocol, serving
    the regression output head (see core/heads.py).

    `predict(X)` returns the raw predicted values and `predict_output(X)` returns
    length-1 [value] rows. To stay a valid NodeProtocol member (so the registry
    accepts it) `predict_proba` is kept present and returns a MIN-MAX NORMALIZED
    pseudo-probability in [0, 1] (the value rescaled by the train-time target
    range) — it is a monotone confidence proxy, NOT a calibrated class
    probability. The degenerate constant-target case is handled by predicting
    that constant (pseudo-proba 0.5).
    """

    kind = "regressor"

    def __init__(self, estimator, name: str, summary: str):
        self.name = name
        self.summary = summary
        self._est = estimator
        self.task = "regression"
        self.n_classes = 1
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0
        self.schema = IOSchema(0, "features", "predicted value")

    def fit(self, X: Matrix, y: Labels) -> "SklearnRegressorNode":
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float)
        d = Xa.shape[1]
        self.schema = IOSchema(d, f"{d} numeric features", "predicted value")
        self._ymin = float(ya.min()) if len(ya) else 0.0
        self._ymax = float(ya.max()) if len(ya) else 1.0
        if self._ymax <= self._ymin:                     # degenerate constant y
            self._constant = float(ya[0]) if len(ya) else 0.0
            return self
        self._constant = None
        self._est.fit(Xa, ya)
        return self

    def predict(self, X: Matrix) -> Labels:
        if self._constant is not None:
            return [self._constant] * len(X)
        return [float(v) for v in self._est.predict(np.asarray(X, dtype=float))]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return [[v] for v in self.predict(X)]

    def predict_proba(self, X: Matrix) -> Vector:
        # min-max-normalized pseudo-probability (monotone confidence proxy).
        vals = self.predict(X)
        span = self._ymax - self._ymin
        if span <= 0.0:
            return [0.5] * len(vals)
        return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]


def ridge_reg_node(alpha: float = 1.0, name: str = "sk_ridge_reg") -> SklearnRegressorNode:
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    return SklearnRegressorNode(est, name,
                                f"scikit-learn Ridge regression (alpha={alpha}, standardized).")


def rf_reg_node(n_trees: int = 100, depth: int | None = None,
                name: str | None = None) -> SklearnRegressorNode:
    from sklearn.ensemble import RandomForestRegressor
    name = name or f"sk_rf_reg{n_trees}"
    return SklearnRegressorNode(
        RandomForestRegressor(n_estimators=n_trees, max_depth=depth,
                              n_jobs=-1, random_state=1),
        name, f"scikit-learn random forest regressor ({n_trees} trees).")


def gbdt_reg_node(n_trees: int = 100, name: str = "sk_gbdt_reg") -> SklearnRegressorNode:
    from sklearn.ensemble import GradientBoostingRegressor
    return SklearnRegressorNode(
        GradientBoostingRegressor(n_estimators=n_trees, random_state=1),
        name, f"scikit-learn gradient boosting regressor ({n_trees} trees).")


def xgb_reg_node(n_trees: int = 200, depth: int = 4, name: str = "xgboost_reg") -> SklearnRegressorNode:
    from xgboost import XGBRegressor
    est = XGBRegressor(n_estimators=n_trees, max_depth=depth, learning_rate=0.1,
                       tree_method="hist", n_jobs=-1, verbosity=0, random_state=1)
    return SklearnRegressorNode(est, name,
                                f"XGBoost gradient-boosted regression trees ({n_trees}x d{depth}).")


# --------------------------------------------------------------------------- #
#  ReservoirPy echo-state node (chaotic / noisy series — the CPU standout)
# --------------------------------------------------------------------------- #
class ReservoirPyNode(BaseNode):
    """Echo-state reservoir (ReservoirPy) as a fixed nonlinear expansion feeding
    a logistic readout. Each feature row is run through the reservoir with a
    state reset so rows stay i.i.d. for classification."""

    kind = "base"

    def __init__(self, units: int = 100, sr: float = 0.9, lr: float = 0.3,
                 seed: int = 3, name: str | None = None):
        self.name = name or f"esn{units}"
        self.summary = f"ReservoirPy echo-state node ({units} units) + logistic readout."
        self.units, self.sr, self.lr, self.seed = units, sr, lr, seed
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def _build(self, d: int):
        from reservoirpy.nodes import Reservoir
        self._res = Reservoir(self.units, sr=self.sr, lr=self.lr, seed=self.seed,
                              input_dim=d)
        self._res.run(np.zeros((1, d)))          # initialize internal state once

    def _expand(self, X: Matrix) -> np.ndarray:
        states = []
        for row in X:
            self._res.reset()                    # fresh zero state per i.i.d. row
            s = self._res.step(np.asarray(row, dtype=float))
            states.append(np.asarray(s).reshape(-1))
        return np.asarray(states, dtype=float)

    def fit(self, X: Matrix, y: Labels) -> "ReservoirPyNode":
        from sklearn.linear_model import LogisticRegression
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in y))
        if len(self._classes) < 2:
            return self
        self._build(d)
        self._readout = LogisticRegression(max_iter=1000)
        self._readout.fit(self._expand(X), np.asarray(y, dtype=int))
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._readout.predict_proba(self._expand(X))
        cols = list(self._readout.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]


# --------------------------------------------------------------------------- #
#  hmmlearn latent-regime gating node (regime / change-point family)
# --------------------------------------------------------------------------- #
class HMMRegimeNode(BaseNode):
    """Fits a Gaussian HMM to discover latent regimes, then trains one logistic
    expert per regime and routes each row to its regime's expert at predict time
    (a real, learned version of the hand-rolled RegimeGatedNode)."""

    kind = "regime"

    def __init__(self, n_regimes: int = 2, seed: int = 0, name: str = "hmm_regime"):
        self.name = name
        self.summary = f"hmmlearn Gaussian-HMM regime gating ({n_regimes} regimes) + per-regime experts."
        self.n_regimes, self.seed = n_regimes, seed
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "HMMRegimeNode":
        from hmmlearn.hmm import GaussianHMM
        from sklearn.linear_model import LogisticRegression
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=int)
        d = Xa.shape[1]
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in ya))
        if len(self._classes) < 2:
            return self
        self._hmm = GaussianHMM(n_components=self.n_regimes, covariance_type="diag",
                                n_iter=50, random_state=self.seed)
        try:
            self._hmm.fit(Xa)
            states = self._hmm.predict(Xa)
        except Exception:                                 # HMM failed to converge
            states = np.zeros(len(Xa), dtype=int)
        self._experts: dict[int, object] = {}
        self._fallback = LogisticRegression(max_iter=1000).fit(Xa, ya)
        for r in range(self.n_regimes):
            mask = states == r
            if mask.sum() >= 5 and len(set(ya[mask])) == 2:
                self._experts[r] = LogisticRegression(max_iter=1000).fit(Xa[mask], ya[mask])
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        Xa = np.asarray(X, dtype=float)
        try:
            states = self._hmm.predict(Xa)
        except Exception:
            states = np.zeros(len(Xa), dtype=int)
        out: Vector = []
        for i, row in enumerate(Xa):
            est = self._experts.get(int(states[i]), self._fallback)
            cols = list(est.classes_)
            j = cols.index(1) if 1 in cols else len(cols) - 1
            out.append(float(est.predict_proba(row.reshape(1, -1))[0, j]))
        return out


# --------------------------------------------------------------------------- #
#  nolds nonlinear-dynamics feature node (chaos / noise measures)
# --------------------------------------------------------------------------- #
class NoldsChaosNode(BaseNode):
    """Augments each feature row with nonlinear-dynamics measures from `nolds`
    (sample entropy, Hurst exponent, DFA) computed over the row treated as a
    short signal, then classifies with logistic regression. Measures that are
    infeasible on a given row length are skipped gracefully."""

    kind = "chaos"

    def __init__(self, name: str = "nolds_chaos"):
        self.name = name
        self.summary = "nolds chaos/noise features (sampen, Hurst, DFA) + logistic readout."
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    @staticmethod
    def _measures(row: np.ndarray) -> list[float]:
        import warnings

        import nolds
        seq = np.asarray(row, dtype=float)
        feats: list[float] = []
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            for fn in (lambda s: nolds.sampen(s),
                       lambda s: nolds.hurst_rs(s),
                       lambda s: nolds.dfa(s)):
                try:
                    v = float(fn(seq))
                    feats.append(v if np.isfinite(v) else 0.0)
                except Exception:
                    feats.append(0.0)
        return feats

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray(X, dtype=float)
        extra = np.asarray([self._measures(np.asarray(r, dtype=float)) for r in X], dtype=float)
        return np.hstack([base, extra])

    def fit(self, X: Matrix, y: Labels) -> "NoldsChaosNode":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in y))
        if len(self._classes) < 2:
            return self
        self._clf = make_pipeline(StandardScaler(),
                                  LogisticRegression(max_iter=1000))
        self._clf.fit(self._augment(X), np.asarray(y, dtype=int))
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._clf.predict_proba(self._augment(X))
        cols = list(self._clf.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]


# --------------------------------------------------------------------------- #
#  scikit-learn StackingClassifier node (the Phase-1 'models as nodes' core)
# --------------------------------------------------------------------------- #
class SklearnStackingNode(BaseNode):
    """Real stacked ensemble (sklearn StackingClassifier): diverse base learners
    feed a logistic meta-learner via cross-validated out-of-fold predictions —
    the production form of the hand-rolled StackingEnsembleNode."""

    kind = "ensemble"

    def __init__(self, name: str = "sk_stacking"):
        self.name = name
        self.summary = "scikit-learn StackingClassifier (RF + GBDT + KNN + LogReg, logistic meta)."
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "SklearnStackingNode":
        from sklearn.ensemble import (GradientBoostingClassifier,
                                      RandomForestClassifier, StackingClassifier)
        from sklearn.linear_model import LogisticRegression
        from sklearn.neighbors import KNeighborsClassifier
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=int)
        d = Xa.shape[1]
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in ya))
        if len(self._classes) < 2:
            return self
        self._est = StackingClassifier(
            estimators=[
                ("rf", RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=1)),
                ("gbdt", GradientBoostingClassifier(n_estimators=100, random_state=1)),
                ("knn", KNeighborsClassifier(n_neighbors=10)),
                ("lr", LogisticRegression(max_iter=1000)),
            ],
            final_estimator=LogisticRegression(max_iter=1000),
            cv=5, n_jobs=-1)
        self._est.fit(Xa, ya)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._est.predict_proba(np.asarray(X, dtype=float))
        cols = list(self._est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]
