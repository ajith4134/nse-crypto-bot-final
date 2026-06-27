"""AutoGluonNode — the plan's Phase-1 *production* stacked-ensemble node.

Wraps AutoGluon-Tabular (multi-layer stacking + bagging over LightGBM/XGBoost/
CatBoost/RF/KNN/NN) behind NodeProtocol. It is far heavier than the pool nodes,
so it is NOT placed in the brain's growth loop — it is the strong reference node
the eval plane compares the grown network against (`run_oss.py`).

Inputs:  Matrix of feature rows + integer Labels (0/1).
Outputs: per-row p(class=1).
"""
from __future__ import annotations

import tempfile

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


class AutoGluonNode(BaseNode):
    kind = "automl"

    def __init__(self, time_limit: int = 30, preset: str = "medium_quality",
                 name: str = "autogluon"):
        self.name = name
        self.summary = "AutoGluon-Tabular multi-layer stacked ensemble (production node)."
        self.time_limit, self.preset = time_limit, preset
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "AutoGluonNode":
        import pandas as pd
        from autogluon.tabular import TabularPredictor
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in y))
        if len(self._classes) < 2:
            return self
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(d)])
        df["__label__"] = list(y)
        self._path = tempfile.mkdtemp(prefix="ag_")
        self._predictor = TabularPredictor(
            label="__label__", path=self._path, verbosity=0,
            eval_metric="accuracy").fit(df, time_limit=self.time_limit, presets=self.preset)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        import pandas as pd
        d = self.schema.input_dim
        df = pd.DataFrame(X, columns=[f"f{i}" for i in range(d)])
        proba = self._predictor.predict_proba(df)
        col = 1 if 1 in proba.columns else proba.columns[-1]
        return [float(v) for v in proba[col].to_numpy()]
