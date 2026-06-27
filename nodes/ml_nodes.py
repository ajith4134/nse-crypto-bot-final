"""Advanced ML / topology / control nodes — the reuse-first expansion of the
node layer with heavier OSS behind the SAME `NodeProtocol` the stdlib + sklearn
nodes use (fit / predict_proba / predict / predict_output over Matrix/Labels),
so the brain, router, eval plane and dashboard are unchanged.

Two reused styles (each task-aware: binary | multiclass | regression):

  (A) FEATURE node  — `_FeatureBase`: per row, a CAUSAL trailing window of one
      input column is summarized into extra features, concatenated with the raw
      feature row, and fed to a small task-aware sklearn readout
      (LogisticRegression for classification / Ridge for regression).
        * Catch22Node   — pycatch22.catch22_all  (22 fast C-backed features)
        * TsfreshNode   — ~8 cheap tsfresh feature_calculators
        * TDANode       — Takens delay-embedding -> ripser persistence diagrams
        * CausalSelectNode — causal-learn PC structure discovery -> column select

  (B) PREDICTOR node — direct X->y model (its OWN classifier/regressor variant):
        * GaussianProcessNode — sklearn GP{Classifier,Regressor} (calibrated unc.)
        * DartsForecastNode    — darts LinearRegressionModel one-step forecast of
                                 the series in column 0 -> task readout
        * ControlSysIDNode     — linear system-ID (sippy ARX, else numpy AR(p))
                                 one-step-ahead forecast -> task readout

The task-aware readout / predict_output mechanics are copied from
`nodes/oss_nodes.py` (SklearnNode + SklearnRegressorNode) and shared via the
`_HeadMixin` below so every node here satisfies the general multi-head contract.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
#  Shared task-aware head (copied readout mechanics from oss_nodes.py)
# --------------------------------------------------------------------------- #
class _HeadMixin(BaseNode):
    """Task-aware readout + predict_output, factored out of SklearnNode /
    SklearnRegressorNode so both the feature and predictor styles here behave
    identically to the existing node zoo:

      * classification (2 classes) -> task="binary": predict_proba -> p(class=1),
        predict_output -> [p0, p1], predict -> threshold 0.5 (BaseNode).
      * classification (>2)        -> task="multiclass": predict_output -> full
        per-class matrix in label order, predict -> argmax, predict_proba -> max.
      * regression                 -> predict -> values, predict_output -> [v],
        predict_proba -> min-max-normalized pseudo-probability (monotone proxy).

    Subclasses provide `_make_estimator(task)` (an unfitted sklearn-like model)
    and may override `_transform(X)` (default identity) to build the design
    matrix fed to the estimator. Set `self.task = "regression"` BEFORE fit() to
    select the regression head; otherwise it is inferred from the labels.
    """

    def _init_head(self) -> None:
        self._classes: list[int] = []
        self.n_classes = 2
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0
        self._est = None

    # subclass hooks ------------------------------------------------------- #
    def _make_estimator(self, task: str):
        raise NotImplementedError

    def _transform(self, X: Matrix) -> np.ndarray:
        return np.asarray(X, dtype=float)

    # shared fit / predict ------------------------------------------------- #
    def _fit_head(self, Z: np.ndarray, y) -> "_HeadMixin":
        Z = np.asarray(Z, dtype=float)
        Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
        if self.task == "regression":
            ya = np.asarray(y, dtype=float)
            self._ymin = float(ya.min()) if len(ya) else 0.0
            self._ymax = float(ya.max()) if len(ya) else 1.0
            if self._ymax <= self._ymin:                 # degenerate constant y
                self._constant = float(ya[0]) if len(ya) else 0.0
                return self
            self._constant = None
            self._est = self._make_estimator("regression")
            self._est.fit(Z, ya)
            return self
        ya = np.asarray(y, dtype=int)
        self._classes = sorted(set(int(v) for v in ya))
        k = len(self._classes)
        self.task = "multiclass" if k > 2 else "binary"
        self.n_classes = k if k > 2 else 2
        if k < 2:                                         # only one class present
            return self
        self._est = self._make_estimator(self.task)
        self._est.fit(Z, ya)
        return self

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            if self._constant is not None:
                return [self._constant] * len(X)
            Z = np.nan_to_num(self._transform(X), nan=0.0, posinf=0.0, neginf=0.0)
            return [float(v) for v in self._est.predict(Z)]
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        return super().predict(X)                          # binary: threshold 0.5

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            vals = self.predict(X)
            span = self._ymax - self._ymin
            if span <= 0.0:
                return [0.5] * len(vals)
            return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        Z = np.nan_to_num(self._transform(X), nan=0.0, posinf=0.0, neginf=0.0)
        proba = self._est.predict_proba(Z)
        if self.task == "multiclass":
            return [float(r.max()) for r in proba]
        cols = list(self._est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            return [[v] for v in self.predict(X)]
        if self.task != "multiclass":
            return super().predict_output(X)               # binary -> [p0, p1]
        if len(self._classes) < 2:
            return [[1.0]] * len(X)
        Z = np.nan_to_num(self._transform(X), nan=0.0, posinf=0.0, neginf=0.0)
        proba = self._est.predict_proba(Z)
        cols = list(self._est.classes_)
        order = [cols.index(c) for c in self._classes]
        return [[float(r[o]) for o in order] for r in proba]


def _readout(task: str):
    """The small shared readout estimator: Ridge for regression, standardized
    LogisticRegression for classification (used by every FEATURE node)."""
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if task == "regression":
        from sklearn.linear_model import Ridge
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    from sklearn.linear_model import LogisticRegression
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


# =========================================================================== #
#  STYLE A — FEATURE nodes (causal trailing-window features + readout)
# =========================================================================== #
class _FeatureBase(_HeadMixin):
    """Causal trailing-window feature extractor + task-aware readout.

    For row i, takes the window of the chosen input column ending at i (length
    `win`, left-padded with the first value so every window is full-length and
    the feature vector has a constant width), summarizes it via `_features`, and
    concatenates those numbers with the raw feature row before the readout.
    Strictly causal (only values up to row i), so it is leak-free per split.
    """

    kind = "ml"

    def __init__(self, name: str, summary: str, win: int = 32, col: int = 0):
        self.name = name
        self.summary = summary
        self.win = int(win)
        self.col = int(col)
        self.task = "binary"
        self._init_head()
        self.schema = IOSchema(0, "features", "p(class=1)")

    # subclass hook: 1-D window (np.ndarray) -> fixed-length feature list
    def _features(self, win: np.ndarray) -> list[float]:
        raise NotImplementedError

    def _make_estimator(self, task: str):
        return _readout(task)

    def _transform(self, X: Matrix) -> np.ndarray:
        Xa = np.asarray(X, dtype=float)
        n, d = Xa.shape
        col = min(self.col, d - 1)
        series = Xa[:, col]
        pad = np.full(self.win - 1, series[0] if n else 0.0)
        ext = np.concatenate([pad, series])
        feats = [self._features(ext[i:i + self.win]) for i in range(n)]
        F = np.nan_to_num(np.asarray(feats, dtype=float),
                          nan=0.0, posinf=0.0, neginf=0.0)
        return np.hstack([Xa, F])

    def fit(self, X: Matrix, y) -> "_FeatureBase":
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} feats + trailing-window stats",
                               "task readout")
        return self._fit_head(self._transform(X), y)


class Catch22Node(_FeatureBase):
    """pycatch22 catch22 feature set over a causal trailing window (fast C
    backend) concatenated with the raw row, then a task-aware readout."""

    def __init__(self, win: int = 32, col: int = 0, name: str = "catch22"):
        super().__init__(name, "pycatch22 catch22 trailing-window features + readout.",
                         win=win, col=col)

    def _features(self, win: np.ndarray) -> list[float]:
        import pycatch22
        try:
            res = pycatch22.catch22_all(win.tolist(), catch24=False)
            vals = res["values"]
            return [float(v) if np.isfinite(v) else 0.0 for v in vals]
        except Exception:
            return [0.0] * 22


class TsfreshNode(_FeatureBase):
    """A small curated set of cheap tsfresh feature_calculators over a causal
    trailing window (NOT the full extract, which is far too slow), concatenated
    with the raw row, then a task-aware readout."""

    def __init__(self, win: int = 32, col: int = 0, name: str = "tsfresh"):
        super().__init__(name, "tsfresh curated trailing-window features + readout.",
                         win=win, col=col)

    def _features(self, win: np.ndarray) -> list[float]:
        from tsfresh.feature_extraction import feature_calculators as fc
        s = win.astype(float)
        out: list[float] = []
        getters = [
            lambda: fc.abs_energy(s),
            lambda: fc.mean_abs_change(s),
            lambda: fc.cid_ce(s, normalize=False),
            lambda: fc.count_above_mean(s),
            lambda: fc.longest_strike_above_mean(s),
            lambda: fc.c3(s, lag=1),
            lambda: fc.sample_entropy(s),
            lambda: fc.autocorrelation(s, lag=1),
        ]
        for g in getters:
            try:
                v = float(g())
                out.append(v if np.isfinite(v) else 0.0)
            except Exception:
                out.append(0.0)
        return out


class TDANode(_FeatureBase):
    """Topological-data-analysis features. The 1-D trailing window is Takens
    delay-embedded (dim=3, delay=2) into a point cloud; ripser computes H0/H1
    persistence diagrams; features are robust hand-computed summaries
    (per-dim: #finite bars, total persistence, max persistence, persistence
    entropy). Robust to tiny windows."""

    kind = "math"

    def __init__(self, win: int = 32, col: int = 0, dim: int = 3, delay: int = 2,
                 name: str = "tda_ph"):
        self.dim = int(dim)
        self.delay = int(delay)
        super().__init__(name, "ripser persistence-diagram features of a Takens "
                               "delay-embedded window + readout.", win=win, col=col)

    def _embed(self, win: np.ndarray) -> np.ndarray:
        span = (self.dim - 1) * self.delay
        m = len(win) - span
        if m < 3:                                          # too short -> degenerate
            return win.reshape(-1, 1)
        return np.column_stack([win[k * self.delay: k * self.delay + m]
                                for k in range(self.dim)])

    @staticmethod
    def _dgm_feats(dgm: np.ndarray) -> list[float]:
        if dgm is None or len(dgm) == 0:
            return [0.0, 0.0, 0.0, 0.0]
        bars = dgm[np.isfinite(dgm[:, 1])]                 # drop infinite-death bar
        if len(bars) == 0:
            return [0.0, 0.0, 0.0, 0.0]
        pers = np.clip(bars[:, 1] - bars[:, 0], 0.0, None)
        total = float(pers.sum())
        mx = float(pers.max()) if len(pers) else 0.0
        if total > 0:
            p = pers / total
            p = p[p > 0]
            ent = float(-(p * np.log(p)).sum())
        else:
            ent = 0.0
        return [float(len(bars)), total, mx, ent]

    def _features(self, win: np.ndarray) -> list[float]:
        try:
            from ripser import ripser
            cloud = self._embed(win.astype(float))
            dgms = ripser(cloud, maxdim=1)["dgms"]
            h0 = self._dgm_feats(dgms[0] if len(dgms) > 0 else None)
            h1 = self._dgm_feats(dgms[1] if len(dgms) > 1 else None)
            return h0 + h1
        except Exception:
            return [0.0] * 8


class CausalSelectNode(_FeatureBase):
    """Causal structure discovery -> predictor. Runs causal-learn's PC algorithm
    (fisherz) on the TRAIN columns + the target to keep only columns with an edge
    to y; falls back to sklearn mutual-information top-k if PC finds nothing or
    errors. The task-aware readout is then trained on the SELECTED columns only.
    No trailing window — `_transform` is a column selector."""

    kind = "math"

    def __init__(self, alpha: float = 0.05, top_k: int = 5, max_rows: int = 600,
                 max_cols: int = 16, name: str = "causal_select"):
        self.alpha = float(alpha)
        self.top_k = int(top_k)
        self.max_rows = int(max_rows)
        self.max_cols = int(max_cols)
        self.name = name
        self.summary = "causal-learn PC structure discovery -> column select + readout."
        self.win = 0
        self.col = 0
        self.task = "binary"
        self._init_head()
        self._sel: list[int] = []
        self._method = "?"
        self.schema = IOSchema(0, "features", "p(class=1)")

    def _features(self, win: np.ndarray) -> list[float]:        # unused
        return []

    def _transform(self, X: Matrix) -> np.ndarray:
        Xa = np.asarray(X, dtype=float)
        if not self._sel:
            return Xa
        return Xa[:, self._sel]

    def _discover(self, Xa: np.ndarray, ya: np.ndarray) -> list[int]:
        d = min(Xa.shape[1], self.max_cols)
        Xc = Xa[:, :d]
        rows = Xc.shape[0]
        if rows > self.max_rows:                           # subsample for speed
            idx = np.linspace(0, rows - 1, self.max_rows).astype(int)
            Xc, yc = Xc[idx], ya[idx]
        else:
            yc = ya
        # PC with fisherz on [X | y]; the target is the last node.
        try:
            from causallearn.search.ConstraintBased.PC import pc
            data = np.column_stack([Xc, yc.astype(float)])
            cg = pc(data, self.alpha, "fisherz", verbose=False, show_progress=False)
            adj = np.asarray(cg.G.graph)
            t = data.shape[1] - 1
            sel = [j for j in range(d)
                   if adj[j, t] != 0 or adj[t, j] != 0]
            if sel:
                self._method = "pc_fisherz"
                return sel
        except Exception:
            pass
        # fallback: mutual-information top-k
        try:
            if self.task == "regression":
                from sklearn.feature_selection import mutual_info_regression as mi
                scores = mi(Xc, yc, random_state=1)
            else:
                from sklearn.feature_selection import mutual_info_classif as mi
                scores = mi(Xc, yc.astype(int), random_state=1)
            k = min(self.top_k, d)
            self._method = "mutual_info_topk"
            return sorted(np.argsort(scores)[::-1][:k].tolist())
        except Exception:
            self._method = "all_cols"
            return list(range(d))

    def fit(self, X: Matrix, y) -> "CausalSelectNode":
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float if self.task == "regression" else int)
        self._sel = self._discover(Xa, ya)
        self.summary = (f"causal-learn select ({self._method}, "
                        f"{len(self._sel)} cols) + readout.")
        self.schema = IOSchema(Xa.shape[1],
                               f"{len(self._sel)} causally-selected columns",
                               "task readout")
        return self._fit_head(self._transform(X), y)

    def _make_estimator(self, task: str):
        return _readout(task)


# =========================================================================== #
#  STYLE B — PREDICTOR nodes (direct X->y model / forecaster)
# =========================================================================== #
class GaussianProcessNode(_HeadMixin):
    """Gaussian Process predictor (sklearn): GaussianProcessClassifier for
    classification heads, GaussianProcessRegressor for regression. Fits X->y
    directly on standardized features and gives CALIBRATED UNCERTAINTY. Because
    GP training is O(n^3), the training set is subsampled to <= `max_rows` rows.
    """

    kind = "ml"

    def __init__(self, max_rows: int = 800, seed: int = 1, name: str = "gaussian_process"):
        self.name = name
        self.summary = ("sklearn Gaussian Process (classifier/regressor by task); "
                        "calibrated uncertainty, subsampled for O(n^3).")
        self.max_rows = int(max_rows)
        self.seed = int(seed)
        self.task = "binary"
        self._init_head()
        self.schema = IOSchema(0, "features", "p(class=1)")

    def _make_estimator(self, task: str):
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        if task == "regression":
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import (RBF, ConstantKernel,
                                                          WhiteKernel)
            kernel = ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-2)
            return make_pipeline(StandardScaler(),
                                 GaussianProcessRegressor(kernel=kernel,
                                                          normalize_y=True,
                                                          n_restarts_optimizer=0,
                                                          random_state=self.seed))
        from sklearn.gaussian_process import GaussianProcessClassifier
        from sklearn.gaussian_process.kernels import RBF, ConstantKernel
        kernel = ConstantKernel(1.0) * RBF(1.0)
        return make_pipeline(StandardScaler(),
                             GaussianProcessClassifier(kernel=kernel,
                                                       n_restarts_optimizer=0,
                                                       random_state=self.seed))

    def fit(self, X: Matrix, y) -> "GaussianProcessNode":
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float if self.task == "regression" else int)
        n, d = Xa.shape
        self.schema = IOSchema(d, f"{d} numeric features", "task readout")
        if n > self.max_rows:                              # keep O(n^3) sane
            rng = np.random.default_rng(self.seed)
            idx = np.sort(rng.choice(n, self.max_rows, replace=False))
            Xa, ya = Xa[idx], ya[idx]
        return self._fit_head(Xa, ya)


class _ForecastBase(_HeadMixin):
    """Shared one-step-ahead forecaster -> task readout. Column `col` of the
    feature matrix is treated as the observable series (column 0 = per-step
    return in this project). For every row a CAUSAL one-step-ahead forecast of
    the next value is produced from the values up to that row, and the readout
    maps that forecast to the head. Strictly leak-free (only past values).
    """

    def __init__(self, name: str, summary: str, lags: int = 8, col: int = 0):
        self.name = name
        self.summary = summary
        self.lags = int(lags)
        self.col = int(col)
        self.task = "binary"
        self._init_head()
        self._s_train: np.ndarray = np.zeros(0)
        self.schema = IOSchema(0, "series in column", "task readout")

    def _make_estimator(self, task: str):
        return _readout(task)

    # subclass hooks ------------------------------------------------------- #
    def _train_forecaster(self, s: np.ndarray) -> None:
        raise NotImplementedError

    def _forecast_column(self, s_train: np.ndarray, s_eval: np.ndarray) -> np.ndarray:
        """Causal one-step-ahead forecast of the next value for each row of
        `s_eval`, using `s_train` as leading context. Returns shape (len(eval),1).
        """
        raise NotImplementedError

    def _transform(self, X: Matrix) -> np.ndarray:
        s_eval = np.asarray(X, dtype=float)[:, min(self.col, len(X[0]) - 1)]
        return self._forecast_column(self._s_train, s_eval)

    def fit(self, X: Matrix, y) -> "_ForecastBase":
        Xa = np.asarray(X, dtype=float)
        d = Xa.shape[1]
        self._s_train = Xa[:, min(self.col, d - 1)].astype(float)
        self.lags = max(2, min(self.lags, len(self._s_train) // 4))
        self.schema = IOSchema(d, "observable series (col 0) one-step forecast",
                               "task readout")
        self._train_forecaster(self._s_train)
        # in-sample forecast column for the readout (train context = itself)
        Z = self._forecast_column(np.zeros(0), self._s_train)
        return self._fit_head(Z, y)


def _ar_fit(s: np.ndarray, p: int):
    """OLS AR(p): regress s[t] on [s[t-1..t-p], 1]. Returns (coef_lag1..p, c0)."""
    n = len(s)
    if n <= p + 1:
        return np.zeros(p), float(s.mean()) if n else 0.0
    rows = np.column_stack([s[p - k - 1: n - k - 1] for k in range(p)])  # lag1..p
    A = np.column_stack([rows, np.ones(n - p)])
    target = s[p:]
    sol, *_ = np.linalg.lstsq(A, target, rcond=None)
    return sol[:p], float(sol[p])


def _ar_forecast_column(coef: np.ndarray, c0: float, p: int,
                        s_train: np.ndarray, s_eval: np.ndarray) -> np.ndarray:
    """Per-row next-value forecast c0 + sum_k coef_k * s[i-k+1] over s_eval, with
    s_train prepended as context so early eval rows still see real history."""
    full = np.concatenate([s_train, s_eval])
    off = len(s_train)
    out = np.zeros(len(s_eval))
    for j in range(len(s_eval)):
        i = off + j
        acc = c0
        for k in range(p):
            idx = i - k
            acc += coef[k] * (full[idx] if idx >= 0 else 0.0)
        out[j] = acc
    return out.reshape(-1, 1)


class DartsForecastNode(_ForecastBase):
    """darts one-step-ahead forecaster of the observable series (column 0) ->
    task readout. Uses darts' fast NON-NN `LinearRegressionModel` (an AR model
    on the series): on CPU the torch NN models (TCN/NHiTS) are too slow for the
    brain's inner loop, so the regression model is used per the spec. Robust
    fallback to a numpy AR(p) / last-value naive forecast if darts errors."""

    kind = "ml"

    def __init__(self, lags: int = 8, col: int = 0, name: str = "darts_forecast"):
        super().__init__(name,
                         "darts LinearRegressionModel one-step forecast (CPU-fast, "
                         "non-NN) of series col 0 + task readout.",
                         lags=lags, col=col)
        self._model = None
        self._fallback = None

    def _train_forecaster(self, s: np.ndarray) -> None:
        self._fallback = _ar_fit(s, self.lags)
        try:
            from darts import TimeSeries
            from darts.models import LinearRegressionModel
            ts = TimeSeries.from_values(s.astype(float))
            self._model = LinearRegressionModel(lags=self.lags)
            self._model.fit(ts)
        except Exception:
            self._model = None

    def _forecast_column(self, s_train: np.ndarray, s_eval: np.ndarray) -> np.ndarray:
        if self._model is not None:
            try:
                from darts import TimeSeries
                full = np.concatenate([s_train, s_eval]).astype(float)
                ts = TimeSeries.from_values(full)
                start = len(s_train)
                hf = self._model.historical_forecasts(
                    ts, start=max(start, self.lags), forecast_horizon=1,
                    stride=1, retrain=False, last_points_only=True,
                    verbose=False)
                vals = np.asarray(hf.values()).reshape(-1)
                # align to the tail eval rows; pad the lead with the first value.
                col = np.full(len(s_eval), vals[0] if len(vals) else 0.0)
                col[-len(vals):] = vals[-len(s_eval):] if len(vals) >= len(s_eval) \
                    else np.concatenate([col[:len(s_eval) - len(vals)], vals])
                return col.reshape(-1, 1)
            except Exception:
                pass
        coef, c0 = self._fallback
        return _ar_forecast_column(coef, c0, self.lags, s_train, s_eval)


class ControlSysIDNode(_ForecastBase):
    """Linear system identification (control family). Identifies an ARX model of
    the observable series with `sippy`; if the sippy API is unavailable/fiddly it
    falls back to a numpy least-squares AR(p) — both yield a one-step-ahead
    forecast that the task readout maps to the head. Always leak-free / robust.
    """

    kind = "control"

    def __init__(self, lags: int = 8, col: int = 0, name: str = "control_sysid"):
        super().__init__(name,
                         "sippy/control linear system-ID (ARX, numpy-AR fallback) "
                         "one-step forecast of series col 0 + task readout.",
                         lags=lags, col=col)
        self._coef = np.zeros(0)
        self._c0 = 0.0
        self._method = "?"

    def _train_forecaster(self, s: np.ndarray) -> None:
        # Try sippy ARX (autoregressive: no exogenous input); fall back to AR.
        try:
            from sippy import system_identification
            sysid = system_identification(s.astype(float), s.astype(float) * 0.0,
                                          "ARX",
                                          ARX_orders=[self.lags, 1, 0])
            # Extract a usable AR predictor; if the structure is unexpected, raise.
            num = np.asarray(getattr(sysid, "DENOMINATOR", None)).reshape(-1)
            if num is None or num.size < self.lags + 1:
                raise ValueError("unexpected sippy structure")
            # A(q) y = ... -> y[t] = -a1 y[t-1] - ... (use as AR coefficients)
            self._coef = -num[1:self.lags + 1]
            self._c0 = 0.0
            self._method = "sippy_arx"
            return
        except Exception:
            pass
        self._coef, self._c0 = _ar_fit(s, self.lags)
        self._method = "numpy_ar"
        self.summary = ("control linear system-ID (numpy AR(p) fallback) one-step "
                        "forecast of series col 0 + task readout.")

    def _forecast_column(self, s_train: np.ndarray, s_eval: np.ndarray) -> np.ndarray:
        return _ar_forecast_column(self._coef, self._c0, self.lags, s_train, s_eval)


# --------------------------------------------------------------------------- #
#  Factories (one per node)
# --------------------------------------------------------------------------- #
def gaussian_process_node(max_rows: int = 800, name: str = "gaussian_process") -> GaussianProcessNode:
    return GaussianProcessNode(max_rows=max_rows, name=name)


def catch22_node(win: int = 32, col: int = 0, name: str = "catch22") -> Catch22Node:
    return Catch22Node(win=win, col=col, name=name)


def tsfresh_node(win: int = 32, col: int = 0, name: str = "tsfresh") -> TsfreshNode:
    return TsfreshNode(win=win, col=col, name=name)


def tda_node(win: int = 32, col: int = 0, name: str = "tda_ph") -> TDANode:
    return TDANode(win=win, col=col, name=name)


def causal_select_node(top_k: int = 5, name: str = "causal_select") -> CausalSelectNode:
    return CausalSelectNode(top_k=top_k, name=name)


def darts_forecast_node(lags: int = 8, col: int = 0, name: str = "darts_forecast") -> DartsForecastNode:
    return DartsForecastNode(lags=lags, col=col, name=name)


def control_sysid_node(lags: int = 8, col: int = 0, name: str = "control_sysid") -> ControlSysIDNode:
    return ControlSysIDNode(lags=lags, col=col, name=name)
