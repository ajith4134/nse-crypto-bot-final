"""UniversalNode — builds a NodeProtocol node from any AlgoSpec (core/algo_registry).

Plus the Tier A/B ultra-advanced ML algorithm specs (one register() line each) and
build_nodes(task), which returns task-appropriate, importable, non-GPU nodes — the
declarative way to include ANY ML algorithm. Non-sklearn estimators with custom
adapters live in nodes/advanced_ml_nodes.py.
"""
from __future__ import annotations

import os
import warnings

import numpy as np

from core.algo_registry import REGISTRY, import_obj, register, spec_importable
from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


class UniversalNode(BaseNode):
    """Adapter turning any sklearn-compatible AlgoSpec estimator into a task-aware
    NodeProtocol node (binary / multiclass / regression)."""

    def __init__(self, spec, name: str | None = None, **params):
        self.spec = spec
        self.name = name or spec.id
        self.kind = spec.kind
        self.summary = spec.summary or spec.id
        self.params = params
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self._est = None
        self.schema = IOSchema(0, "features", "out")

    def _make(self):
        path = (self.spec.reg_import_path
                if self.task == "regression" and self.spec.reg_import_path
                else self.spec.import_path)
        cls = import_obj(path)
        return cls(**{**self.spec.fixed_args, **self.params})

    def fit(self, X: Matrix, y: Labels) -> "UniversalNode":
        Xa = np.asarray(X, dtype=float)
        self.schema = IOSchema(Xa.shape[1], f"{Xa.shape[1]} numeric features", self.task)
        self._est = self._make()
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            if self.task == "regression":
                ya = np.asarray(y, dtype=float)
                self._ymin, self._ymax = float(ya.min()), float(ya.max())
                getattr(self._est, self.spec.fit_method)(Xa, ya)
            else:
                ya = np.asarray(y, dtype=int)
                self._classes = sorted(set(int(v) for v in ya))
                if len(self._classes) < 2:
                    return self
                getattr(self._est, self.spec.fit_method)(Xa, ya)
        return self

    def _proba_matrix(self, X: Matrix) -> np.ndarray:
        Xa = np.asarray(X, dtype=float)
        pm = self.spec.proba_method
        if pm and hasattr(self._est, pm):
            try:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    p = np.asarray(getattr(self._est, pm)(Xa), dtype=float)
                cols = list(getattr(self._est, "classes_", range(p.shape[1])))
                order = [cols.index(c) if c in cols else min(i, p.shape[1] - 1)
                         for i, c in enumerate(self._classes)]
                return np.asarray([[float(r[o]) for o in order] for r in p])
            except Exception:
                pass
        pred = getattr(self._est, self.spec.point_method)(Xa)            # one-hot fallback
        out = np.zeros((len(Xa), len(self._classes)))
        idx = {c: i for i, c in enumerate(self._classes)}
        for i, v in enumerate(np.ravel(pred)):
            out[i, idx.get(int(round(float(v))), 0)] = 1.0
        return out

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            v = getattr(self._est, self.spec.point_method)(np.asarray(X, dtype=float))
            return [[float(x)] for x in np.ravel(v)]
        if len(self._classes) < 2:
            return [[1.0]] * len(X)
        return [[float(x) for x in row] for row in self._proba_matrix(X)]

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            v = [r[0] for r in self.predict_output(X)]
            lo, hi = min(v), max(v)
            return [(x - lo) / (hi - lo) if hi > lo else 0.5 for x in v]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        M = self._proba_matrix(X)
        if self.task == "multiclass":
            return [float(r.max()) for r in M]
        j = self._classes.index(1) if 1 in self._classes else len(self._classes) - 1
        return [float(r[j]) for r in M]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [int(round(r[0])) for r in self.predict_output(X)]
        return super().predict(X)


# --------------------------------------------------------------------------- #
#  Tier A/B specs — one register() line per algorithm (import paths verified
#  post-install; spec_importable() filters out any that didn't install).
# --------------------------------------------------------------------------- #
_CLS = frozenset({"binary", "multiclass"})
_ALL = frozenset({"binary", "multiclass", "regression"})
_REG = frozenset({"regression"})

register(id="imodels_figs", import_path="imodels.FIGSClassifier",
         reg_import_path="imodels.FIGSRegressor", tasks=_ALL, kind="ml",
         summary="imodels FIGS — fast interpretable greedy tree-sums.", license="MIT")
register(id="imodels_rulefit", import_path="imodels.RuleFitClassifier",
         reg_import_path="imodels.RuleFitRegressor", tasks=frozenset({"binary", "regression"}),
         kind="ml", summary="imodels RuleFit — sparse rule ensemble.", license="MIT")
register(id="deep_forest", import_path="deepforest.CascadeForestClassifier",
         reg_import_path="deepforest.CascadeForestRegressor", tasks=_ALL, kind="ml",
         summary="Deep Forest (gcForest) — deep cascade of forests, no backprop.")
register(id="quantile_forest", import_path="quantile_forest.RandomForestQuantileRegressor",
         tasks=_REG, kind="ml", summary="Quantile regression forest (distributional).",
         license="Apache-2.0")
register(id="lce", import_path="lce.LCEClassifier", reg_import_path="lce.LCERegressor",
         tasks=_ALL, kind="ml", summary="Local Cascade Ensemble (RF+XGBoost hybrid).",
         license="Apache-2.0")
register(id="rotation_forest", import_path="aeon.classification.sklearn.RotationForestClassifier",
         tasks=_CLS, kind="ml", summary="Rotation Forest — PCA-rotated subspace trees.",
         license="BSD-3")
register(id="wittgenstein_ripper", import_path="wittgenstein.RIPPER", tasks=frozenset({"binary"}),
         kind="ml", summary="RIPPER rule induction (human-readable rules).", license="MIT")
register(id="tabpfn", import_path="tabpfn.TabPFNClassifier", tasks=_CLS, kind="ml",
         summary="TabPFN — tabular foundation model (in-context).",
         requires_env="TABPFN_TOKEN",  # weights need 1-time license accept + token (non-commercial)
         fixed_args={}, license="non-commercial-weights")
register(id="pyoperon_sr", import_path="pyoperon.sklearn.SymbolicRegressor", tasks=_REG,
         kind="symbolic", summary="Operon GP symbolic regression (SRBench leader).", license="MIT")
register(id="nearest_centroid", import_path="sklearn.neighbors.NearestCentroid", tasks=_CLS,
         kind="ml", summary="Nearest-centroid (prototypical) classifier.", license="BSD-3",
         proba_method="")  # no predict_proba -> one-hot fallback
register(id="quantile_reg", import_path="sklearn.linear_model.QuantileRegressor", tasks=_REG,
         kind="ml", summary="Linear quantile regression.", license="BSD-3",
         fixed_args={"alpha": 0.0, "solver": "highs"})
register(id="bayes_gmm", import_path="nodes.advanced_ml_nodes.BayesianGMMClassifier", tasks=_CLS,
         kind="ml", summary="Variational/DP Bayesian Gaussian mixture classifier.", license="BSD-3")
register(id="scikit_survival_rsf", import_path="nodes.advanced_ml_nodes.SurvivalForestClassifier",
         tasks=frozenset({"binary"}), kind="quant",
         summary="Random Survival Forest risk score.", license="GPL-3.0")
register(id="mljar_automl", import_path="supervised.AutoML", tasks=_ALL, kind="ml",
         summary="mljar-supervised AutoML (stacked ensemble).", license="MIT",
         fixed_args={"total_time_limit": 15, "explain_level": 0, "verbose": 0})
register(id="xgboostlss", import_path="nodes.advanced_ml_nodes.XGBoostLSSClassifier",
         reg_import_path="nodes.advanced_ml_nodes.XGBoostLSSRegressor", tasks=frozenset({"binary", "regression"}),
         kind="ml", summary="XGBoostLSS distributional boosting.", license="Apache-2.0")
register(id="lightgbmlss", import_path="nodes.advanced_ml_nodes.LightGBMLSSRegressor",
         tasks=_REG, kind="ml", summary="LightGBMLSS distributional boosting.", license="Apache-2.0")
register(id="metric_learn_knn", import_path="nodes.advanced_ml_nodes.MetricLearnKNN", tasks=_CLS,
         kind="ml", summary="metric-learn (LMNN) + kNN.", license="MIT")
register(id="bart", import_path="nodes.advanced_ml_nodes.BARTClassifier",
         reg_import_path="nodes.advanced_ml_nodes.BARTRegressor", tasks=frozenset({"binary", "regression"}),
         kind="ml", summary="Bayesian Additive Regression Trees (stochtree).", license="MIT")


def build_nodes(task: str) -> list:
    """(spec_id, factory) for every registry node valid for `task`, importable in
    this env, and non-GPU (never-skip). Factories are no-arg, matching the runner's
    pool contract; the runner sets node.task/.head before fit."""
    out = []
    for spec in REGISTRY.values():
        if task not in spec.tasks or spec.needs_gpu or not spec_importable(spec):
            continue
        if spec.requires_env and not os.environ.get(spec.requires_env):
            continue                         # license/token-gated (e.g. TabPFN) — opt-in only
        out.append((spec.id, (lambda s=spec: UniversalNode(s))))
    return out
