"""Quant / finance / math-structure nodes — OSS time-series & extreme-value
models wrapped behind the project NodeProtocol (core/node_protocol.py).

Two node STYLES share one task-aware readout machinery (copied in spirit from
nodes/oss_nodes.py SklearnNode + SklearnRegressorNode):

  (A) FEATURE node  (_FeatNode): derive a 1-D signal from a chosen column,
      compute CAUSAL trailing-window features (no look-ahead), concat them with
      the raw X row, then fit a task-aware sklearn readout
      (LogisticRegression(max_iter=1000) for classification, Ridge() for
      regression).  Nodes: EVTTailNode, ADFStationarityNode, CointSpreadNode.

  (B) PREDICTOR node (_PredNode): per row, produce a 1-step-ahead forecast of
      the chosen column's trailing window (a model's own forecast), then fit a
      task-aware readout mapping that single forecast scalar -> target:
      classification -> logistic on the predicted value (class probs);
      regression -> Ridge-calibrated value.  Nodes: GarchVolNode,
      StateSpaceNode, StatsForecastNode.

Causality: for each row i the trailing window is signal[max(0,i-win+1):i+1] —
only past+present, never future.  Short windows fall back to fixed-length zeros.
At predict time the training column tail is prepended so test rows keep full
causal context (and the prepended history is dropped from the output).  Every
heavy library call is wrapped in try/except with a cheap, robust fallback so a
node never breaks the graph.  Inputs are np.asarray'd; numeric/optimizer
warnings are suppressed (warnings.catch_warnings + np.errstate).
"""
from __future__ import annotations

import contextlib
import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


@contextlib.contextmanager
def _quiet():
    """Suppress library warnings + numpy floating errors around fragile fits."""
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        yield


# --------------------------------------------------------------------------- #
#  Shared task-aware base: causal trailing-window design + readout
# --------------------------------------------------------------------------- #
class _QBase(BaseNode):
    """Common machinery for the quant nodes.

    Subclasses provide `_window_feats(window) -> list[float]` (length n_feats)
    and a `_design(X)` (FEATURE: window-feats hstacked with X; PREDICTOR: just
    the forecast column).  The task-aware fit/predict_proba/predict/
    predict_output mirror oss_nodes: classification readout is
    LogisticRegression(max_iter=1000) returning p(class=1); regression readout
    is Ridge() returning length-1 [value] rows with a monotone min-max
    pseudo-probability for the NodeProtocol Vector contract.
    """

    kind = "quant"
    n_feats = 1
    min_win = 8

    def __init__(self, name: str, summary: str, col: int = 0,
                 win: int = 64, stride: int = 1):
        self.name = name
        self.summary = summary
        self.col = col
        self.win = win
        self.stride = stride
        self.task = "binary"
        self.n_classes = 2
        self.head = "y"
        self._classes: list[int] = []
        self._est = None
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0
        self._histX: np.ndarray | None = None
        self.schema = IOSchema(0, "features", "p(class=1)")

    # -- signal / window-feature extraction (causal) ------------------------ #
    def _col_signal(self, M: np.ndarray) -> np.ndarray:
        c = self.col if self.col < M.shape[1] else 0
        return M[:, c]

    def _window_feats(self, window: np.ndarray) -> list[float]:
        raise NotImplementedError

    def _safe(self, window: np.ndarray, prev) -> list[float]:
        """Compute window-features, guarding short windows and failures."""
        if len(window) < self.min_win:
            return [0.0] * self.n_feats
        with _quiet():
            try:
                f = list(self._window_feats(np.asarray(window, dtype=float)))
            except Exception:
                f = list(prev) if prev is not None else [0.0] * self.n_feats
        f = f[: self.n_feats] + [0.0] * max(0, self.n_feats - len(f))
        return [float(v) if np.isfinite(v) else 0.0 for v in f]

    def _hist_frame(self, X: Matrix):
        """Prepend stored training rows so test windows keep causal history."""
        Xa = np.asarray(X, dtype=float)
        if self._histX is not None and len(self._histX):
            return np.vstack([self._histX, Xa]), len(self._histX)
        return Xa, 0

    def _extra(self, X: Matrix) -> np.ndarray:
        full, off = self._hist_frame(X)
        sig = self._col_signal(full)
        out: list[list[float]] = []
        last = None
        cnt = 0
        for i in range(len(full)):
            lo = max(0, i - self.win + 1)
            if last is None or cnt >= self.stride:   # refit; else amortize
                last = self._safe(sig[lo: i + 1], last)
                cnt = 0
            cnt += 1
            if i >= off:
                out.append(last)
        return np.asarray(out, dtype=float)

    # -- design matrix (style-specific) ------------------------------------- #
    def _design(self, X: Matrix) -> np.ndarray:
        raise NotImplementedError

    def _in_desc(self, d: int) -> str:
        return f"{d} numeric features"

    def _readout(self):
        from sklearn.linear_model import LogisticRegression, Ridge
        return Ridge() if self.task == "regression" \
            else LogisticRegression(max_iter=1000)

    # -- NodeProtocol surface (task-aware, copied from oss_nodes) ----------- #
    def fit(self, X: Matrix, y: Labels) -> "_QBase":
        self._histX = None
        D = self._design(X)
        d = np.asarray(X, dtype=float).shape[1]
        if self.task == "regression":
            ya = np.asarray(y, dtype=float)
            self.schema = IOSchema(d, self._in_desc(d), "predicted value")
            self._ymin = float(ya.min()) if len(ya) else 0.0
            self._ymax = float(ya.max()) if len(ya) else 1.0
            if self._ymax <= self._ymin:                 # degenerate constant y
                self._constant = float(ya[0]) if len(ya) else 0.0
            else:
                self._constant = None
                self._est = self._readout()
                with _quiet():
                    self._est.fit(D, ya)
        else:
            ya = np.asarray(y, dtype=int)
            self.schema = IOSchema(d, self._in_desc(d), "p(class=1)")
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) > 2:
                self.task = "multiclass"
                self.n_classes = len(self._classes)
            if len(self._classes) >= 2:
                self._est = self._readout()
                with _quiet():
                    self._est.fit(D, ya)
        self._histX = np.asarray(X, dtype=float)         # history for predict
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            vals = [r[0] for r in self.predict_output(X)]
            span = self._ymax - self._ymin
            if span <= 0.0:
                return [0.5] * len(vals)
            return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        with _quiet():
            proba = self._est.predict_proba(self._design(X))
        cols = list(self._est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            return [r[0] for r in self.predict_output(X)]
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))]
                    for r in self.predict_output(X)]
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            if self._constant is not None:
                return [[self._constant]] * len(X)
            with _quiet():
                vals = self._est.predict(self._design(X))
            return [[float(v)] for v in vals]
        if self.task == "multiclass":
            if len(self._classes) < 2:
                return [[1.0]] * len(X)
            with _quiet():
                proba = self._est.predict_proba(self._design(X))
            cols = list(self._est.classes_)
            order = [cols.index(c) for c in self._classes]
            return [[float(row[o]) for o in order] for row in proba]
        return [[1.0 - p, p] for p in self.predict_proba(X)]


class _FeatNode(_QBase):
    """Style A: window-features concatenated with the raw X row."""

    def _design(self, X: Matrix) -> np.ndarray:
        return np.hstack([np.asarray(X, dtype=float), self._extra(X)])

    def _in_desc(self, d: int) -> str:
        return f"{d} feats + {self.n_feats} causal window feats"


class _PredNode(_QBase):
    """Style B: a single 1-step forecast scalar feeding the task readout."""

    n_feats = 1

    def _design(self, X: Matrix) -> np.ndarray:
        return self._extra(X)

    def _in_desc(self, d: int) -> str:
        return f"1-step forecast of col {self.col} -> {self.task} readout"


# --------------------------------------------------------------------------- #
#  1. GarchVolNode (arch) — PREDICTOR, conditional volatility forecast
# --------------------------------------------------------------------------- #
class GarchVolNode(_PredNode):
    """arch GARCH(1,1): 1-step conditional volatility forecast per trailing
    window (chosen column treated as the return series), mapped to the target
    by the task readout.  Best suited to the 'volatility' head.  Robust
    try/except fallback to the rolling standard deviation of the window."""

    kind = "quant"

    def __init__(self, col: int = 0, win: int = 120, stride: int = 3,
                 name: str = "garch_vol"):
        super().__init__(name,
                         "arch GARCH(1,1) 1-step conditional-volatility forecast "
                         "-> task readout (fallback: rolling std).",
                         col=col, win=win, stride=stride)
        self.min_win = 20
        self.n_feats = 1
        self.head = "volatility"

    def _window_feats(self, w: np.ndarray) -> list[float]:
        try:
            from arch import arch_model
            r = w * 100.0                                # rescale for stability
            res = arch_model(r, vol="Garch", p=1, q=1).fit(
                disp="off", show_warning=False)
            fc = res.forecast(horizon=1, reindex=False)
            v = float(np.sqrt(fc.variance.values[-1, 0])) / 100.0
            if not np.isfinite(v):
                raise ValueError("non-finite GARCH forecast")
            return [v]
        except Exception:
            return [float(np.std(w))]                    # robust fallback


def garch_vol_node(col: int = 0, win: int = 120, name: str = "garch_vol") -> GarchVolNode:
    return GarchVolNode(col=col, win=win, name=name)


# --------------------------------------------------------------------------- #
#  2. EVTTailNode (scipy.stats.genpareto) — FEATURE, extreme-value tail
# --------------------------------------------------------------------------- #
class EVTTailNode(_FeatNode):
    """Per window, fit a Generalized Pareto over peaks-over-threshold (90th pct
    of |returns|).  Features = [tail shape xi, scale, exceedance prob of a large
    move].  scipy.stats.genpareto.fit (floc=0) is robust; degenerate windows
    yield zeros."""

    kind = "quant"

    def __init__(self, col: int = 0, win: int = 120, stride: int = 1,
                 name: str = "evt_tail"):
        super().__init__(name,
                         "scipy genpareto POT tail features [xi, scale, "
                         "exceedance-prob of a large move] + X readout.",
                         col=col, win=win, stride=stride)
        self.min_win = 40
        self.n_feats = 3

    def _window_feats(self, w: np.ndarray) -> list[float]:
        from scipy.stats import genpareto
        a = np.abs(w)
        thr = float(np.percentile(a, 90))
        exc = a[a > thr] - thr
        if len(exc) < 5:
            return [0.0, 0.0, 0.0]
        c, _loc, sc = genpareto.fit(exc, floc=0)
        pex = len(exc) / len(a)                           # exceedance frequency
        large = float(np.percentile(a, 99))              # a "large" move
        tail_prob = pex * float(genpareto.sf(max(large - thr, 0.0),
                                             c, loc=0, scale=sc))
        return [float(c), float(sc), float(tail_prob)]


def evt_tail_node(col: int = 0, win: int = 120, name: str = "evt_tail") -> EVTTailNode:
    return EVTTailNode(col=col, win=win, name=name)


# --------------------------------------------------------------------------- #
#  3. StateSpaceNode (statsmodels UnobservedComponents) — PREDICTOR
# --------------------------------------------------------------------------- #
class StateSpaceNode(_PredNode):
    """statsmodels UnobservedComponents local-level + linear-trend structural
    model fit on the trailing series, forecasting 1 step ahead; mapped to the
    target by the task readout.  Robust fallback to the last observed value."""

    kind = "quant"

    def __init__(self, col: int = 0, win: int = 80, stride: int = 8,
                 name: str = "state_space"):
        super().__init__(name,
                         "statsmodels UnobservedComponents (local linear trend) "
                         "1-step forecast -> task readout (fallback: last value).",
                         col=col, win=win, stride=stride)
        self.min_win = 12
        self.n_feats = 1

    def _window_feats(self, w: np.ndarray) -> list[float]:
        try:
            from statsmodels.tsa.statespace.structural import \
                UnobservedComponents
            res = UnobservedComponents(w, level="local linear trend").fit(
                disp=False, maxiter=50)
            v = float(np.asarray(res.forecast(1)).reshape(-1)[0])
            if not np.isfinite(v):
                raise ValueError("non-finite UCM forecast")
            return [v]
        except Exception:
            return [float(w[-1])]                         # robust fallback


def state_space_node(col: int = 0, win: int = 80, name: str = "state_space") -> StateSpaceNode:
    return StateSpaceNode(col=col, win=win, name=name)


# --------------------------------------------------------------------------- #
#  4. StatsForecastNode (statsforecast AutoETS) — PREDICTOR
# --------------------------------------------------------------------------- #
class StatsForecastNode(_PredNode):
    """statsforecast AutoETS fit on the trailing series, 1-step forecast, mapped
    to the target by the task readout.  Kept fast (AutoETS).  Robust fallback to
    simple exponential smoothing (so it works even where statsforecast/numba is
    unavailable in the environment)."""

    kind = "quant"

    def __init__(self, col: int = 0, win: int = 80, stride: int = 1,
                 name: str = "statsforecast_ets"):
        super().__init__(name,
                         "statsforecast AutoETS 1-step forecast -> task readout "
                         "(fallback: simple exponential smoothing).",
                         col=col, win=win, stride=stride)
        self.min_win = 8
        self.n_feats = 1

    def _window_feats(self, w: np.ndarray) -> list[float]:
        try:
            from statsforecast.models import AutoETS
            m = AutoETS(season_length=1)
            res = m.forecast(y=np.asarray(w, dtype=float), h=1)
            v = float(np.asarray(res["mean"]).reshape(-1)[0])
            if not np.isfinite(v):
                raise ValueError("non-finite ETS forecast")
            return [v]
        except Exception:
            alpha, lvl = 0.5, float(w[0])                # simple exp smoothing
            for x in w[1:]:
                lvl = alpha * float(x) + (1.0 - alpha) * lvl
            return [lvl]


def statsforecast_node(col: int = 0, win: int = 80,
                       name: str = "statsforecast_ets") -> StatsForecastNode:
    return StatsForecastNode(col=col, win=win, name=name)


# --------------------------------------------------------------------------- #
#  5. ADFStationarityNode (statsmodels adfuller) — FEATURE, math structure
# --------------------------------------------------------------------------- #
class ADFStationarityNode(_FeatNode):
    """Per window, structural 'is this mean-reverting vs trending/random'
    features: [ADF statistic, ADF p-value, Hurst-like slope].  The Hurst-like
    slope is the log-log regression slope of std(lagged differences) vs lag."""

    kind = "math"

    def __init__(self, col: int = 0, win: int = 80, stride: int = 1,
                 name: str = "adf_stationarity"):
        super().__init__(name,
                         "statsmodels ADF [stat, p-value] + Hurst-like slope "
                         "(mean-reversion vs trend structure) + X readout.",
                         col=col, win=win, stride=stride)
        self.min_win = 24
        self.n_feats = 3

    @staticmethod
    def _hurst(w: np.ndarray) -> float:
        ll, tau = [], []
        for k in range(2, min(20, len(w) // 2)):
            d = w[k:] - w[:-k]
            s = float(np.std(d))
            if s > 0:
                ll.append(np.log(k))
                tau.append(np.log(s))
        if len(tau) < 2:
            return 0.5
        return float(np.polyfit(ll, tau, 1)[0])

    def _window_feats(self, w: np.ndarray) -> list[float]:
        from statsmodels.tsa.stattools import adfuller
        stat, pval = 0.0, 1.0
        try:
            res = adfuller(w, maxlag=1, autolag=None)
            stat, pval = float(res[0]), float(res[1])
        except Exception:
            pass
        return [stat, pval, self._hurst(w)]


def adf_stationarity_node(col: int = 0, win: int = 80,
                          name: str = "adf_stationarity") -> ADFStationarityNode:
    return ADFStationarityNode(col=col, win=win, name=name)


# --------------------------------------------------------------------------- #
#  6. CointSpreadNode (statsmodels) — FEATURE, pairs/cointegration proxy
# --------------------------------------------------------------------------- #
class CointSpreadNode(_FeatNode):
    """Pairs / cointegration proxy.  If >=2 columns: per window, rolling OLS
    hedge of column0 on column1, then features = [hedge beta, spread z-score,
    spread ADF statistic].  If only one column is available it skips gracefully
    (all-zero window features, so the node degenerates to a plain X readout)."""

    kind = "quant"

    def __init__(self, col0: int = 0, col1: int = 1, win: int = 80,
                 stride: int = 1, name: str = "coint_spread"):
        super().__init__(name,
                         "rolling OLS hedge spread features [beta, z-score, "
                         "ADF stat] (pairs/cointegration proxy) + X readout.",
                         col=col0, win=win, stride=stride)
        self.col1 = col1
        self.min_win = 24
        self.n_feats = 3

    def _pair_feats(self, a: np.ndarray, b: np.ndarray) -> list[float]:
        if len(a) < self.min_win:
            return [0.0, 0.0, 0.0]
        with _quiet():
            try:
                bb = b - b.mean()
                denom = float(np.dot(bb, bb))
                beta = float(np.dot(bb, a - a.mean()) / denom) if denom > 0 else 0.0
                spread = a - beta * b
                mu, sd = float(spread.mean()), float(spread.std())
                z = float((spread[-1] - mu) / sd) if sd > 0 else 0.0
                try:
                    from statsmodels.tsa.stattools import adfuller
                    stat = float(adfuller(spread, maxlag=1, autolag=None)[0])
                except Exception:
                    stat = 0.0
                f = [beta, z, stat]
            except Exception:
                f = [0.0, 0.0, 0.0]
        return [float(v) if np.isfinite(v) else 0.0 for v in f]

    def _extra(self, X: Matrix) -> np.ndarray:
        full, off = self._hist_frame(X)
        if full.shape[1] < 2:                            # only one series -> skip
            return np.zeros((len(X), self.n_feats), dtype=float)
        c0 = self.col if self.col < full.shape[1] else 0
        c1 = self.col1 if self.col1 < full.shape[1] else (1 if full.shape[1] > 1 else 0)
        a_all, b_all = full[:, c0], full[:, c1]
        out: list[list[float]] = []
        last = None
        cnt = 0
        for i in range(len(full)):
            lo = max(0, i - self.win + 1)
            if last is None or cnt >= self.stride:
                last = self._pair_feats(a_all[lo: i + 1], b_all[lo: i + 1])
                cnt = 0
            cnt += 1
            if i >= off:
                out.append(last)
        return np.asarray(out, dtype=float)


def coint_spread_node(col0: int = 0, col1: int = 1, win: int = 80,
                      name: str = "coint_spread") -> CointSpreadNode:
    return CointSpreadNode(col0=col0, col1=col1, win=win, name=name)


# =========================================================================== #
#  BACKWARD-COMPAT shared bases (_HeadBase / _WindowFeat) + EWMAVolNode.
#  Many node modules (structure/advanced/frontier/dl/github_*) import
#  `_HeadBase`/`_WindowFeat` from here. The _QBase refactor above renamed the
#  internal bases; these additive classes preserve the public names + the simple
#  causal-window feature contract (_features(win)->list, NFEAT, _augment) those
#  modules were written against. (Additive — does not change _QBase or its nodes.)
# =========================================================================== #
def _compat_readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(),
                         Ridge() if task == "regression" else LogisticRegression(max_iter=1000))


# module-level alias some node modules import: `from nodes.quant_nodes import _readout`
_readout = _compat_readout


class _HeadBase(BaseNode):
    """Task-aware readout base: subclasses implement `_augment(X) -> np.ndarray`."""
    kind = "quant"

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 64):
        self.name, self.summary, self.col, self.W = name, summary, col, W
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self.schema = IOSchema(0, "features", "out")

    def _augment(self, X: Matrix) -> np.ndarray:
        raise NotImplementedError

    def fit(self, X: Matrix, y: Labels) -> "_HeadBase":
        ya = np.asarray(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", self.task)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:
                return self
        self._ro = _compat_readout(self.task)
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
        return super().predict_output(X)

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [int(round(v)) for v in self._ro.predict(self._augment(X))]
        return super().predict(X)


class _WindowFeat(_HeadBase):
    """Causal trailing-window feature base: subclasses set NFEAT + `_features`."""
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


class EWMAVolNode(_WindowFeat):
    """RiskMetrics EWMA conditional volatility (+ realized vol, vol-of-vol)."""
    NFEAT = 3

    def __init__(self, name="ewma_vol", col=0, W=96):
        super().__init__(name, "EWMA (RiskMetrics) conditional volatility features.", col, W)

    def _features(self, win):
        r = np.asarray(win, float)
        lam, var = 0.94, float(np.var(r))
        for x in r:
            var = lam * var + (1 - lam) * x * x
        half = max(1, len(r) // 2)
        vov = abs(float(np.std(r[half:])) - float(np.std(r[:half])))
        return [float(np.sqrt(var)), float(np.std(r)), vov]


def ewma_vol_node(name="ewma_vol"):
    return EWMAVolNode(name)
