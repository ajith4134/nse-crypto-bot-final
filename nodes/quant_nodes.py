"""Quant / finance + math-structure nodes (arch GARCH, EVT, ADF, EWMA, statsforecast).

Wraps installed OSS behind the project NodeProtocol, in the multi-output contract
(task in {binary,multiclass,regression}; predict_output rows = class-probs or
[value]). To stay FAST (no per-row model refits — the trap that made the old
nolds/stumpy nodes slow), volatility/forecast nodes fit ONCE and apply a causal
recursion; tail/stationarity nodes use cheap per-window statistics.

Each node takes a 1-D signal from feature column `col` (default 0, a return-like
feature) with CAUSAL trailing windows (no look-ahead). Honest walk-forward use.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


def _readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = Ridge() if task == "regression" else LogisticRegression(max_iter=1000)
    return make_pipeline(StandardScaler(), est)


class _HeadBase(BaseNode):
    """Task-aware readout + predict_output, copied from oss_nodes mechanics.
    Subclasses provide `_augment(X) -> np.ndarray` (features per row)."""

    kind = "quant"

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 64):
        self.name, self.summary = name, summary
        self.col, self.W = col, W
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "out")

    # subclass hook
    def _augment(self, X: Matrix) -> np.ndarray:
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
        return super().predict_output(X)                # binary [1-p, p]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [int(round(v)) for v in self._ro.predict(self._augment(X))]
        return super().predict(X)


# --------------------------------------------------------------------------- #
#  Cheap per-window feature nodes
# --------------------------------------------------------------------------- #
class _WindowFeat(_HeadBase):
    NFEAT = 1

    def _features(self, win: list[float]) -> list[float]:
        raise NotImplementedError

    def _augment(self, X: Matrix) -> np.ndarray:
        col = [float(r[self.col]) for r in X]
        rows = []
        for i in range(len(X)):
            w = col[max(0, i - self.W + 1): i + 1]
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                f = self._features(w) if len(w) >= 12 else [0.0] * self.NFEAT
            rows.append([float(v) for v in X[i]] + [float(v) for v in f])
        return np.asarray(rows, dtype=float)


class EVTTailNode(_WindowFeat):
    """Extreme-value theory: fit a Generalized Pareto to peaks-over-threshold of
    |returns| in the window → tail shape/scale + probability of a large move."""
    NFEAT = 3

    def __init__(self, name="evt_tail", col=0, W=96):
        super().__init__(name, "EVT peaks-over-threshold (GPD) tail-risk features.", col, W)

    def _features(self, win):
        from scipy import stats
        a = np.abs(np.asarray(win, float))
        thr = np.quantile(a, 0.9)
        exc = a[a > thr] - thr
        if len(exc) < 5:
            return [0.0, float(np.std(a)), 0.0]
        xi, loc, scale = stats.genpareto.fit(exc, floc=0.0)
        big = np.quantile(a, 0.99)
        p_exceed = float(1.0 - stats.genpareto.cdf(max(big - thr, 0), xi, loc=0.0, scale=scale))
        return [float(xi), float(scale), p_exceed]


class ADFStationarityNode(_WindowFeat):
    """Augmented Dickey-Fuller stationarity: is this window mean-reverting vs
    trending/random? (kind=math) — the 'structure vs randomness' lens."""
    kind = "math"
    NFEAT = 3

    def __init__(self, name="adf_stationarity", col=0, W=96):
        super().__init__(name, "ADF test statistic/p-value + drift — mean-reversion vs random.", col, W)

    def _features(self, win):
        from statsmodels.tsa.stattools import adfuller
        x = np.asarray(win, float)
        try:
            stat, pval = adfuller(x, autolag="AIC")[:2]
        except Exception:
            stat, pval = 0.0, 1.0
        drift = float(np.polyfit(np.arange(len(x)), x, 1)[0])
        return [float(stat), float(pval), drift]


class EWMAVolNode(_WindowFeat):
    """RiskMetrics EWMA conditional volatility (λ=0.94) + realized vol + vol-of-vol
    — cheap volatility-clustering features; pairs with the GARCH node."""
    NFEAT = 3

    def __init__(self, name="ewma_vol", col=0, W=96):
        super().__init__(name, "EWMA (RiskMetrics) conditional volatility features.", col, W)

    def _features(self, win):
        r = np.asarray(win, float)
        lam, var = 0.94, float(np.var(r))
        for x in r:
            var = lam * var + (1 - lam) * x * x
        realized = float(np.std(r))
        half = max(1, len(r) // 2)
        vov = abs(float(np.std(r[half:])) - float(np.std(r[:half])))
        return [float(np.sqrt(var)), realized, vov]


# --------------------------------------------------------------------------- #
#  Fit-once nodes (no per-row refit)
# --------------------------------------------------------------------------- #
class GarchVolNode(_HeadBase):
    """arch GARCH(1,1): fit ONCE on the training return series, then apply the
    fitted (ω,α,β) recursion causally to produce a per-row conditional-volatility
    feature. Best suited to the `volatility` head. Robust fallback to EWMA."""

    def __init__(self, name="garch_vol", col=0):
        super().__init__(name, "arch GARCH(1,1) conditional volatility (fit-once recursion).", col)
        self._p = None

    def _fit_params(self, X):
        from arch import arch_model
        r = np.asarray([row[self.col] for row in X], float) * 100.0   # scale for stability
        try:
            res = arch_model(r, mean="Zero", vol="Garch", p=1, q=1).fit(disp="off")
            pr = res.params
            self._p = (float(pr["omega"]), float(pr["alpha[1]"]), float(pr["beta[1]"]))
        except Exception:
            self._p = None

    def _vol_series(self, X) -> np.ndarray:
        r = np.asarray([row[self.col] for row in X], float) * 100.0
        if self._p is None:                                  # EWMA fallback
            lam, var, out = 0.94, float(np.var(r)) or 1.0, []
            for x in r:
                var = lam * var + (1 - lam) * x * x; out.append(np.sqrt(var))
            return np.asarray(out)
        omega, alpha, beta = self._p
        lr = omega / max(1e-6, 1 - alpha - beta)             # long-run var seed
        var, out = lr, []
        for x in r:
            var = omega + alpha * x * x + beta * var; out.append(np.sqrt(max(var, 1e-12)))
        return np.asarray(out)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        vol = self._vol_series(X).reshape(-1, 1)
        return np.hstack([base, vol])

    def fit(self, X, y):
        self._fit_params(X)
        return super().fit(X, y)


class StatsForecastNode(_HeadBase):
    """statsforecast AutoETS: fit ONCE on the training target series, produce a
    one-step in-sample/out-of-sample forecast aligned per row as a feature.
    Robust fallback to a last-value/AR(1) forecast."""

    def __init__(self, name="statsforecast_ets", col=0):
        super().__init__(name, "statsforecast AutoETS one-step forecast (fit-once).", col)
        self._fitted_train = None
        self._ytr = None

    def fit(self, X, y):
        self._ytr = np.asarray(y, float)
        try:
            from statsforecast.models import AutoETS
            self._model = AutoETS(season_length=1)
            self._model.fit(self._ytr)
            self._fitted_train = np.asarray(
                self._model.predict_in_sample()["fitted"], float)
        except Exception:
            self._model = None
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        n = len(X)
        if self._fitted_train is not None and n == len(self._fitted_train):
            fc = self._fitted_train                          # training rows
        elif self._model is not None:
            try:
                fc = np.asarray(self._model.predict(h=n)["mean"], float)
            except Exception:
                fc = np.full(n, float(self._ytr[-1]) if self._ytr is not None else 0.0)
        else:
            fc = np.full(n, float(self._ytr[-1]) if self._ytr is not None else 0.0)
        return np.hstack([base, fc.reshape(-1, 1)])


def evt_tail_node(name="evt_tail"): return EVTTailNode(name)
def adf_stationarity_node(name="adf_stationarity"): return ADFStationarityNode(name)
def ewma_vol_node(name="ewma_vol"): return EWMAVolNode(name)
def garch_vol_node(name="garch_vol"): return GarchVolNode(name)
def statsforecast_node(name="statsforecast_ets"): return StatsForecastNode(name)
