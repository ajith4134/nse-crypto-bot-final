"""Online / incremental-learning nodes (River) — the growing-brain fit.

River learns one sample at a time (`learn_one`/`predict_one`) with no batch
retrain — the natural lifecycle for an always-learning network. Here it is
wrapped behind the batch NodeProtocol (fit iterates learn_one over rows;
predict_output iterates predict_one), so it drops straight into the existing
pool/dashboard. A true streaming node lifecycle (partial_fit/update per event)
is the next enhancement; this adapter is the bridge.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


def _rows_to_dicts(X: Matrix) -> list[dict]:
    return [{f"f{j}": float(v) for j, v in enumerate(row)} for row in X]


class RiverNode(BaseNode):
    """Adapter: any River classifier/regressor as a NodeProtocol node.

    `model_factory(task)` returns a fresh River pipeline for the given task.
    Classification handles binary & multiclass; regression returns the value.
    """

    kind = "online"

    def __init__(self, model_factory, name: str, summary: str):
        self.name, self.summary = name, summary
        self._mk = model_factory
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "online prediction")

    def fit(self, X: Matrix, y: Labels) -> "RiverNode":
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", self.task)
        self._model = self._mk(self.task)
        dicts = _rows_to_dicts(X)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in y))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for x, yi in zip(dicts, y):
                self._model.learn_one(x, int(yi) if self.task != "regression" else float(yi))
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        dicts = _rows_to_dicts(X)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.task == "regression":
                return [[float(self._model.predict_one(x))] for x in dicts]
            out = []
            for x in dicts:
                p = self._model.predict_proba_one(x) or {}
                row = [float(p.get(c, 0.0)) for c in self._classes]
                s = sum(row)
                row = [v / s for v in row] if s > 0 else [1.0 / len(self._classes)] * len(self._classes)
                out.append(row)
            return out

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            v = [r[0] for r in self.predict_output(X)]
            lo, hi = min(v), max(v)
            return [(x - lo) / (hi - lo) if hi > lo else 0.5 for x in v]
        out = self.predict_output(X)
        if self.task == "multiclass":
            return [float(max(r)) for r in out]
        j = self._classes.index(1) if 1 in self._classes else len(self._classes) - 1
        return [float(r[j]) for r in out]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [int(round(r[0])) for r in self.predict_output(X)]
        return super().predict(X)


# ---- model factories (River pipelines) ------------------------------------ #
def _logreg_factory(task):
    from river import linear_model, preprocessing
    if task == "regression":
        return preprocessing.StandardScaler() | linear_model.LinearRegression()
    return preprocessing.StandardScaler() | linear_model.LogisticRegression()


def _hoeffding_factory(task):
    from river import tree
    return (tree.HoeffdingAdaptiveTreeRegressor() if task == "regression"
            else tree.HoeffdingAdaptiveTreeClassifier())


def _arf_factory(task):
    from river import forest
    return (forest.ARFRegressor(n_models=10) if task == "regression"
            else forest.ARFClassifier(n_models=10))


def river_logreg_node(name="river_linear"):
    return RiverNode(_logreg_factory, name, "River online linear model (incremental SGD).")


def river_hoeffding_node(name="river_hoeffding"):
    return RiverNode(_hoeffding_factory, name, "River Hoeffding adaptive tree (incremental, multiclass).")


def river_arf_node(name="river_arf"):
    return RiverNode(_arf_factory, name, "River Adaptive Random Forest (online ensemble, drift-aware).")
