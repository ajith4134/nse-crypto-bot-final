"""PySRNode — the plan's Phase-5 equation-discovery node.

Wraps PySR (symbolic regression, Julia-backed) behind NodeProtocol: it searches
for a closed-form expression f(features) that fits the {0,1} target, then squashes
the regression output into [0,1] as a probability. This is the 'AI that creates &
tests new equations' capability — the discovered equation is inspectable via
`.equation_`. First fit triggers a one-time Julia install (slow); kept out of the
growth pool and run on demand (`run_symbolic.py`).

Inputs:  Matrix of feature rows + integer Labels (0/1).
Outputs: per-row p(class=1) = clip(f(x), 0, 1).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


class PySRNode(BaseNode):
    kind = "symbolic"

    def __init__(self, niterations: int = 20, populations: int = 8,
                 seed: int = 0, name: str = "pysr"):
        self.name = name
        self.summary = "PySR symbolic-regression node — discovers a closed-form predictor."
        self.niterations, self.populations, self.seed = niterations, populations, seed
        self._classes: list[int] = []
        self.equation_: str = ""
        self.schema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "PySRNode":
        from pysr import PySRRegressor
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in y))
        if len(self._classes) < 2:
            return self
        self._model = PySRRegressor(
            niterations=self.niterations, populations=self.populations,
            binary_operators=["+", "-", "*", "/"],
            unary_operators=["tanh", "exp", "square"],
            model_selection="best", progress=False, verbosity=0,
            random_state=self.seed, deterministic=True, procs=0, multithreading=False)
        self._model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
        try:
            self.equation_ = str(self._model.sympy())
        except Exception:
            self.equation_ = ""
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        raw = self._model.predict(np.asarray(X, dtype=float))
        return [min(1.0, max(0.0, float(v))) for v in raw]
