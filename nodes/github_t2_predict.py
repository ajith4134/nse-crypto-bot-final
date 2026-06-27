"""GitHub-tier-2 predictor / probabilistic / dynamics nodes (T2).

Wraps ten OSS projects behind the project NodeProtocol in the multi-output
contract (task in {binary,multiclass,regression}; predict_output rows = class
probabilities or [value]). Every node reuses the task-aware readout `_HeadBase`
from nodes/quant_nodes.py (imported, not re-implemented): a LogisticRegression
(classification) / Ridge (regression) head over engineered features, with the
binary [1-p, p] / degenerate-class guards already baked in.

Design rules honoured here:
  * fit-once, no per-row model refits (the trap that made old nodes slow) — the
    external model is fit a single time, then applied causally / vectorised;
  * ROBUST: every external library call is wrapped in try/except and degrades to
    a Ridge/Logistic-friendly feature built from simple trailing-window stats,
    with `self.fell_back = True` recorded so the dashboard can see it;
  * each node is a class plus a NO-ARG factory.

Each node augments the raw feature row with one or more model-derived columns and
lets the shared readout learn the mapping to the active head. The 1-D signal a
node forecasts/embeds is feature column `col` (default 0, a return-like feature),
matching the convention in nodes/quant_nodes.py.
"""
from __future__ import annotations

import datetime as _dt
import os
import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

warnings.filterwarnings("ignore")
os.environ.setdefault("LIGHTGBM_VERBOSE", "-1")
os.environ.setdefault("PYTHONWARNINGS", "ignore")


# --------------------------------------------------------------------------- #
#  Task-aware readout + _HeadBase — COPIED verbatim from nodes/quant_nodes.py.
#  (Originally meant to be imported; quant_nodes was concurrently refactored and
#  no longer exports `_HeadBase`, so it is vendored here to keep this module
#  self-contained and robust. LogisticRegression for classification / Ridge for
#  regression; predict_output yields class-probs or [value]; binary -> [1-p, p];
#  degenerate single-class guard.)
# --------------------------------------------------------------------------- #
def _readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = Ridge() if task == "regression" else LogisticRegression(max_iter=1000)
    return make_pipeline(StandardScaler(), est)


class _HeadBase(BaseNode):
    """Task-aware readout + predict_output. Subclasses provide
    `_augment(X) -> np.ndarray` (features per row)."""

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
#  Shared augmentation helpers (all T2 nodes append model columns to the row)
# --------------------------------------------------------------------------- #
class _Aug(_HeadBase):
    """`_HeadBase` plus tiny helpers shared by every T2 node."""

    def __init__(self, name: str, summary: str, col: int = 0):
        super().__init__(name, summary, col)
        self.fell_back = False

    def _series(self, X: Matrix) -> np.ndarray:
        return np.asarray([float(r[self.col]) for r in X], dtype=float)

    def _base(self, X: Matrix) -> np.ndarray:
        return np.asarray([[float(v) for v in r] for r in X], dtype=float)

    def _finish(self, base: np.ndarray, feat) -> np.ndarray:
        feat = np.asarray(feat, dtype=float).reshape(len(base), -1)
        out = np.hstack([base, feat])
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

    def _winstats(self, s: np.ndarray, W: int = 32) -> np.ndarray:
        """Cheap causal window stats used as the universal Ridge/Logistic
        fallback feature when an external library is unavailable/fails."""
        n = len(s)
        out = np.zeros((n, 3), dtype=float)
        for i in range(n):
            w = s[max(0, i - W + 1): i + 1]
            out[i] = [w[-1], float(w.mean()), float(w[-1] - w[0]) if len(w) > 1 else 0.0]
        return out


# --------------------------------------------------------------------------- #
#  Fit-once forecasters (1, 2, 4) — model column = one-step / horizon forecast
# --------------------------------------------------------------------------- #
class _ForecastBase(_Aug):
    """Fit a global forecaster ONCE on the training signal; the per-row feature
    is the model's fitted/forecast value. Train rows reuse the cached training
    feature; out-of-sample rows (chrono test block) get the model's forecast for
    that horizon. Falls back to naive trailing-window stats on any failure."""

    kind = "ml"

    def __init__(self, name, summary, col=0):
        super().__init__(name, summary, col)
        self._ntr = 0
        self._train_feat = None
        self._series_tr = None

    # subclass hooks ------------------------------------------------------- #
    def _fit_model(self, s: np.ndarray) -> None:
        raise NotImplementedError

    def _insample(self, s: np.ndarray) -> np.ndarray:
        """Per-train-row model feature (default: naive lag-1 forecast)."""
        out = s.copy()
        out[1:] = s[:-1]
        return out.reshape(-1, 1)

    def _future(self, m: int) -> np.ndarray:
        """Model forecast feature for `m` out-of-sample rows."""
        raise NotImplementedError

    # protocol ------------------------------------------------------------- #
    def fit(self, X: Matrix, y: Labels) -> "_ForecastBase":
        s = self._series(X)
        self._ntr, self._series_tr = len(X), s
        try:
            self._fit_model(s)
            self._train_feat = np.asarray(self._insample(s), float).reshape(len(X), -1)
        except Exception:
            self.fell_back = True
            self._model = None
            self._train_feat = self._winstats(s)
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = self._base(X)
        if len(X) == self._ntr and self._train_feat is not None:
            return self._finish(base, self._train_feat)
        s = self._series(X)
        if getattr(self, "_model", None) is None:
            return self._finish(base, self._winstats(s))
        try:
            f = np.asarray(self._future(len(X)), float).reshape(-1)
            if len(f) < len(X):          # tile/pad short horizons
                f = np.concatenate([f, np.full(len(X) - len(f), f[-1])])
            return self._finish(base, f[:len(X)].reshape(-1, 1))
        except Exception:
            self.fell_back = True
            return self._finish(base, self._winstats(s))


class MLForecastNode(_ForecastBase):
    """mlforecast: a global LightGBM forecaster on the target signal (lags
    1..5). Fit-once; per-row feature is the in-sample fitted value (train) or the
    multi-step forecast (test). Robust Ridge-on-window-stats fallback."""

    def __init__(self, name="mlforecast_lgbm", col=0):
        super().__init__(name, "mlforecast global LightGBM 1-step forecast (fit-once).", col)
        self._mf = None
        self._model = None

    def _fit_model(self, s):
        import pandas as pd
        from lightgbm import LGBMRegressor
        from mlforecast import MLForecast
        n = len(s)
        df = pd.DataFrame({"unique_id": ["s"] * n, "ds": np.arange(n), "y": s})
        self._mf = MLForecast(
            models=[LGBMRegressor(n_estimators=60, verbosity=-1, n_jobs=1)],
            freq=1, lags=[1, 2, 3, 4, 5])
        self._mf.fit(df, fitted=True)
        self._model = self._mf

    def _insample(self, s):
        fv = self._mf.forecast_fitted_values()
        out = s.copy()
        for d, v in zip(fv["ds"].to_numpy(), fv["LGBMRegressor"].to_numpy()):
            di = int(d)
            if 0 <= di < len(out):
                out[di] = float(v)
        return out.reshape(-1, 1)

    def _future(self, m):
        return self._mf.predict(h=m)["LGBMRegressor"].to_numpy()


class FunctimeNode(_ForecastBase):
    """functime: autoregressive LightGBM forecaster (polars panel). Fit-once;
    test rows get the lib forecast, train rows a naive in-sample column (functime
    exposes no in-sample fit). Robust fallback on the fiddly polars/date API."""

    def __init__(self, name="functime_lgbm", col=0):
        super().__init__(name, "functime autoregressive LightGBM forecast (fit-once).", col)
        self._f = None
        self._model = None

    def _fit_model(self, s):
        import polars as pl
        from functime.forecasting import lightgbm
        n = len(s)
        d0 = _dt.date(2000, 1, 1)
        times = [d0 + _dt.timedelta(days=i) for i in range(n)]
        y = pl.DataFrame({"entity": ["s"] * n, "time": times, "value": s})
        self._f = lightgbm(freq="1d", lags=8)
        self._f.fit(y=y)
        self._model = self._f

    def _future(self, m):
        return np.asarray(self._f.predict(fh=m)["value"].to_numpy(), float)


class AutoTSNode(_ForecastBase):
    """autots: AutoTS forecaster with a small genetic search (max_generations=2)
    on the target signal. Fit-once (kept deliberately small — it can still be
    slow, FLAG if >15s); test rows get the genetic-best forecast tiled to the
    horizon, train rows a naive column. Robust fallback."""

    def __init__(self, name="autots_forecast", col=0):
        super().__init__(name, "AutoTS small genetic-search forecast (fit-once).", col)
        self._model = None
        self._fc = None

    def _fit_model(self, s):
        import pandas as pd
        from autots import AutoTS
        n = len(s)
        idx = pd.date_range("2000-01-01", periods=n, freq="D")
        df = pd.DataFrame({"value": s}, index=idx)
        self._H = 14
        mdl = AutoTS(forecast_length=self._H, frequency="D",
                     max_generations=2, num_validations=0, verbose=-1,
                     model_list="superfast", ensemble=None, n_jobs=1)
        mdl = mdl.fit(df.reset_index().rename(columns={"index": "ds"}),
                      date_col="ds", value_col="value", id_col=None)
        self._fc = np.asarray(mdl.predict().forecast["value"].to_numpy(), float)
        self._model = mdl

    def _future(self, m):
        base = self._fc if self._fc is not None and len(self._fc) else np.array([self._series_tr[-1]])
        reps = int(np.ceil(m / len(base)))
        return np.tile(base, reps)[:m]


# --------------------------------------------------------------------------- #
#  3. FLAML AutoML — direct X->y model, output used as a feature for the readout
# --------------------------------------------------------------------------- #
class FLAMLNode(_Aug):
    """flaml.AutoML.fit(X, y, task=..., time_budget=10) directly on X->y; the
    model's class-1 probability (or regression prediction) becomes a feature for
    the shared readout. Tiny time budget. Robust fallback to a plain readout."""

    kind = "ml"

    def __init__(self, name="flaml_automl", col=0):
        super().__init__(name, "flaml AutoML (small time-budget) predictor feature.", col)
        self._aml = None

    def fit(self, X, y):
        Xa, ya = self._base(X), np.asarray(y)
        try:
            from flaml import AutoML
            task = "regression" if self.task == "regression" else "classification"
            self._aml = AutoML()
            self._aml.fit(X_train=Xa, y_train=ya, task=task,
                          time_budget=10, verbose=0, n_jobs=1,
                          early_stop=True, metric="accuracy" if task == "classification" else "rmse")
        except Exception:
            self.fell_back = True
            self._aml = None
        return super().fit(X, y)

    def _augment(self, X):
        base = self._base(X)
        if self._aml is None:
            return self._finish(base, self._winstats(self._series(X)))
        try:
            if self.task == "regression":
                f = np.asarray(self._aml.predict(base), float)
            else:
                proba = np.asarray(self._aml.predict_proba(base), float)
                f = proba[:, -1] if proba.ndim == 2 else proba
            return self._finish(base, f.reshape(-1, 1))
        except Exception:
            self.fell_back = True
            return self._finish(base, self._winstats(self._series(X)))


# --------------------------------------------------------------------------- #
#  5. deeptime — slow collective coordinates from a Hankel delay embedding
# --------------------------------------------------------------------------- #
class DeeptimeNode(_Aug):
    """deeptime: build a Hankel (delay) embedding of the target signal, then fit
    TICA (slow collective coordinates) ONCE on the training embedding and append
    the leading slow components per row. Robust fallback to window stats."""

    kind = "physics"

    def __init__(self, name="deeptime_tica", col=0, d: int = 10, dim: int = 2):
        super().__init__(name, "deeptime TICA slow collective coordinates on a delay embedding.", col)
        self.d, self.dim = d, dim
        self._tica = None

    def _embed(self, s: np.ndarray) -> np.ndarray:
        n = len(s)
        E = np.zeros((n, self.d), dtype=float)
        for i in range(n):
            for k in range(self.d):
                E[i, k] = s[max(0, i - k)]
        return E

    def fit(self, X, y):
        s = self._series(X)
        try:
            from deeptime.decomposition import TICA
            E = self._embed(s)
            self._tica = TICA(lagtime=1, dim=self.dim).fit(E).fetch_model()
        except Exception:
            self.fell_back = True
            self._tica = None
        return super().fit(X, y)

    def _augment(self, X):
        base, s = self._base(X), self._series(X)
        if self._tica is None:
            return self._finish(base, self._winstats(s))
        try:
            Z = np.asarray(self._tica.transform(self._embed(s)), float)
            return self._finish(base, Z)
        except Exception:
            self.fell_back = True
            return self._finish(base, self._winstats(s))


# --------------------------------------------------------------------------- #
#  6. pomegranate HMM — per-row state posterior; fallback to hmmlearn
# --------------------------------------------------------------------------- #
class PomegranateHMMNode(_Aug):
    """pomegranate v1 GaussianHMM (3 states, torch-CPU) on the target signal; the
    per-row state posterior is the feature. Robust fallback to hmmlearn's
    GaussianHMM, then to a z-score-bucket posterior."""

    kind = "regime"

    def __init__(self, name="pomegranate_hmm", col=0, n_states: int = 3):
        super().__init__(name, "pomegranate/hmmlearn Gaussian-HMM state posteriors.", col)
        self.n_states = n_states
        self._hmm = None
        self._impl = "naive"

    def fit(self, X, y):
        s = self._series(X).reshape(-1, 1)
        try:                                            # primary: pomegranate v1
            import torch
            from pomegranate.distributions import Normal
            from pomegranate.hmm import DenseHMM
            dists = [Normal(covariance_type="diag") for _ in range(self.n_states)]
            hmm = DenseHMM(dists, max_iter=20, verbose=False)
            ten = torch.tensor(s.reshape(1, -1, 1), dtype=torch.float32)
            hmm.fit(ten)
            self._hmm, self._impl = hmm, "pomegranate"
        except Exception:
            try:                                        # fallback: hmmlearn
                from hmmlearn.hmm import GaussianHMM
                m = GaussianHMM(n_components=self.n_states,
                                covariance_type="diag", n_iter=25)
                m.fit(s)
                self._hmm, self._impl, self.fell_back = m, "hmmlearn", True
            except Exception:
                self._impl, self.fell_back = "naive", True
        return super().fit(X, y)

    def _naive_post(self, s: np.ndarray) -> np.ndarray:
        z = (s - s.mean()) / (s.std() + 1e-9)
        lo, hi = -0.43, 0.43
        post = np.zeros((len(s), 3))
        post[:, 0] = (z < lo).astype(float)
        post[:, 1] = ((z >= lo) & (z <= hi)).astype(float)
        post[:, 2] = (z > hi).astype(float)
        return post

    def _augment(self, X):
        base, s = self._base(X), self._series(X)
        try:
            if self._impl == "pomegranate":
                import torch
                ten = torch.tensor(s.reshape(1, -1, 1), dtype=torch.float32)
                post = self._hmm.predict_proba(ten).detach().numpy()[0]
            elif self._impl == "hmmlearn":
                post = self._hmm.predict_proba(s.reshape(-1, 1))
            else:
                post = self._naive_post(s)
        except Exception:
            self.fell_back = True
            post = self._naive_post(s)
        return self._finish(base, post)


# --------------------------------------------------------------------------- #
#  7. pgmpy Bayesian network — discretized features -> learned BN -> P(target)
# --------------------------------------------------------------------------- #
class PgmpyBayesNetNode(_Aug):
    """pgmpy: discretize a few features into bins, learn a small Bayesian network
    (HillClimbSearch + BIC) and infer P(target) per row as a feature. Inference
    can be slow -> FLAG. Robust fallback to a Gaussian NaiveBayes posterior."""

    kind = "math"

    def __init__(self, name="pgmpy_bayesnet", col=0, n_bins: int = 3, cols=(0, 1, 8)):
        super().__init__(name, "pgmpy HillClimb/BIC Bayesian network P(target) feature.", col)
        self.n_bins, self.cols = n_bins, cols
        self._model = None
        self._edges = None
        self._infer = None
        self._nb = None

    def _disc(self, X):
        Xa = self._base(X)
        cols = [c for c in self.cols if c < Xa.shape[1]]
        D = np.zeros((len(X), len(cols)), dtype=int)
        if self._edges is None:
            self._edges = {}
            for j, c in enumerate(cols):
                qs = np.quantile(Xa[:, c], np.linspace(0, 1, self.n_bins + 1)[1:-1])
                self._edges[c] = qs
        for j, c in enumerate(cols):
            D[:, j] = np.digitize(Xa[:, c], self._edges[c])
        return D, cols

    def fit(self, X, y):
        import pandas as pd
        D, cols = self._disc(X)
        ya = np.asarray(y)
        try:
            from pgmpy.estimators import BIC, HillClimbSearch
            names = [f"f{c}" for c in cols]
            df = pd.DataFrame(D, columns=names)
            df["target"] = ya.astype(int)
            est = HillClimbSearch(df)
            dag = est.estimate(scoring_method=BIC(df), max_indegree=2,
                               max_iter=int(1e4), show_progress=False)
            from pgmpy.models import DiscreteBayesianNetwork
            edges = list(dag.edges())
            nodes = set(df.columns)
            model = DiscreteBayesianNetwork(edges)
            model.add_nodes_from(nodes)
            model.fit(df)
            from pgmpy.inference import VariableElimination
            self._model, self._infer, self._names = model, VariableElimination(model), names
        except Exception:
            self.fell_back = True
            self._model = None
            try:
                from sklearn.naive_bayes import GaussianNB
                self._nb = GaussianNB().fit(self._base(X), ya)
            except Exception:
                self._nb = None
        return super().fit(X, y)

    def _augment(self, X):
        base = self._base(X)
        if self._model is not None:
            try:
                import pandas as pd
                D, cols = self._disc(X)
                names = [f"f{c}" for c in cols]
                ev = pd.DataFrame(D, columns=names)
                ev = ev[[n for n in names if n in self._model.nodes()]]
                pred = self._model.predict(ev, n_jobs=1,
                                           show_progress=False)["target"].to_numpy()
                return self._finish(base, np.asarray(pred, float).reshape(-1, 1))
            except Exception:
                self.fell_back = True
        if self._nb is not None:
            try:
                p = self._nb.predict_proba(base)
                return self._finish(base, p[:, -1].reshape(-1, 1))
            except Exception:
                self.fell_back = True
        return self._finish(base, self._winstats(self._series(X)))


# --------------------------------------------------------------------------- #
#  8. econml — per-row CATE (treatment-effect) estimate as a feature
# --------------------------------------------------------------------------- #
class EconMLNode(_Aug):
    """econml: synthesize a binary treatment by median-splitting a feature, fit a
    CATE estimator (LinearDML) and use the per-row treatment-effect estimate as a
    feature. Robust fallback to a group-ATE * treatment proxy."""

    kind = "math"

    def __init__(self, name="econml_cate", col=0, tcol: int = 1):
        super().__init__(name, "econml LinearDML per-row treatment-effect (CATE) feature.", col)
        self.tcol = tcol
        self._est = None
        self._thr = 0.0
        self._ate = 0.0

    def _treatment(self, X):
        Xa = self._base(X)
        tc = self.tcol if self.tcol < Xa.shape[1] else 0
        return (Xa[:, tc] > self._thr).astype(int), Xa

    def fit(self, X, y):
        Xa, ya = self._base(X), np.asarray(y, float)
        tc = self.tcol if self.tcol < Xa.shape[1] else 0
        self._thr = float(np.median(Xa[:, tc]))
        T, _ = self._treatment(X)
        # group-ATE proxy is always available (used as fallback feature)
        m1 = ya[T == 1].mean() if (T == 1).any() else 0.0
        m0 = ya[T == 0].mean() if (T == 0).any() else 0.0
        self._ate = float(m1 - m0)
        try:
            from econml.dml import LinearDML
            covs = np.delete(Xa, tc, axis=1)
            est = LinearDML(discrete_treatment=True, random_state=0)
            est.fit(Y=ya, T=T, X=covs)
            self._est = est
        except Exception:
            self.fell_back = True
            self._est = None
        return super().fit(X, y)

    def _augment(self, X):
        Xa = self._base(X)
        tc = self.tcol if self.tcol < Xa.shape[1] else 0
        T, _ = self._treatment(X)
        if self._est is not None:
            try:
                covs = np.delete(Xa, tc, axis=1)
                eff = np.asarray(self._est.effect(covs), float).reshape(-1)
                return self._finish(Xa, eff.reshape(-1, 1))
            except Exception:
                self.fell_back = True
        feat = T.astype(float) * self._ate
        return self._finish(Xa, feat.reshape(-1, 1))


# --------------------------------------------------------------------------- #
#  9 & 10. Kalman filters — filtered level + one-step prediction features
# --------------------------------------------------------------------------- #
class PykalmanNode(_Aug):
    """pykalman: a KalmanFilter with EM parameter learning on the target signal;
    features are the filtered level and its one-step-ahead prediction. Robust
    fallback to an EWMA level + lag-1 prediction."""

    kind = "signal"

    def __init__(self, name="pykalman_em", col=0):
        super().__init__(name, "pykalman EM-fitted filtered level + 1-step prediction.", col)
        self._kf = None

    def fit(self, X, y):
        s = self._series(X)
        try:
            from pykalman import KalmanFilter
            kf = KalmanFilter(initial_state_mean=float(s[0]), n_dim_obs=1)
            self._kf = kf.em(s, n_iter=5)
        except Exception:
            self.fell_back = True
            self._kf = None
        return super().fit(X, y)

    def _augment(self, X):
        base, s = self._base(X), self._series(X)
        if self._kf is not None:
            try:
                fm, _ = self._kf.filter(s)
                level = fm[:, 0]
                A = float(np.asarray(self._kf.transition_matrices).reshape(-1)[0])
                pred1 = A * level
                return self._finish(base, np.column_stack([level, pred1]))
            except Exception:
                self.fell_back = True
        # EWMA-level fallback
        lam, lvl, out = 0.8, float(s[0]), []
        for x in s:
            lvl = lam * lvl + (1 - lam) * x
            out.append(lvl)
        level = np.asarray(out)
        pred1 = np.concatenate([[level[0]], level[:-1]])
        return self._finish(base, np.column_stack([level, pred1]))


class SimdKalmanNode(_Aug):
    """simdkalman: a vectorized local-trend Kalman filter; features are the
    smoothed observation estimate and the one-step-ahead forecast. Robust
    fallback to a lag-1 / EWMA forecast."""

    kind = "signal"

    def __init__(self, name="simdkalman_1step", col=0):
        super().__init__(name, "simdkalman vectorized 1-step Kalman forecast feature.", col)
        self._kf = None

    def fit(self, X, y):
        try:
            import simdkalman
            self._kf = simdkalman.KalmanFilter(
                state_transition=[[1.0, 1.0], [0.0, 1.0]],
                process_noise=np.diag([0.01, 0.01]),
                observation_model=[[1.0, 0.0]],
                observation_noise=1.0)
        except Exception:
            self.fell_back = True
            self._kf = None
        return super().fit(X, y)

    def _augment(self, X):
        base, s = self._base(X), self._series(X)
        if self._kf is not None:
            try:
                data = s.reshape(1, -1)
                sm = self._kf.smooth(data)
                level = np.asarray(sm.observations.mean).reshape(-1)
                pr = self._kf.predict(data, 1)
                nxt = float(np.asarray(pr.observations.mean).reshape(-1)[-1])
                onestep = np.concatenate([level[1:], [nxt]])
                return self._finish(base, np.column_stack([level, onestep]))
            except Exception:
                self.fell_back = True
        lam, lvl, out = 0.7, float(s[0]), []
        for x in s:
            lvl = lam * lvl + (1 - lam) * x
            out.append(lvl)
        level = np.asarray(out)
        onestep = np.concatenate([level[1:], [level[-1]]])
        return self._finish(base, np.column_stack([level, onestep]))


# --------------------------------------------------------------------------- #
#  NO-ARG factories
# --------------------------------------------------------------------------- #
def mlforecast_node(): return MLForecastNode()
def functime_node(): return FunctimeNode()
def flaml_node(): return FLAMLNode()
def autots_node(): return AutoTSNode()
def deeptime_node(): return DeeptimeNode()
def pomegranate_hmm_node(): return PomegranateHMMNode()
def pgmpy_bayesnet_node(): return PgmpyBayesNetNode()
def econml_node(): return EconMLNode()
def pykalman_node(): return PykalmanNode()
def simdkalman_node(): return SimdKalmanNode()


# --------------------------------------------------------------------------- #
#  Self-verification on mackey_glass (direction, binary)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import time

    from core.node_protocol import NodeProtocol
    from data.benchmarks import make_benchmark_dataset
    from data.dataset import chrono_split

    d = make_benchmark_dataset("mackey_glass", 700, 0.05)
    Xtr, ytr, Xte, yte = chrono_split(d["X"], d["targets"]["direction"])

    factories = [
        ("MLForecastNode", mlforecast_node), ("FunctimeNode", functime_node),
        ("FLAMLNode", flaml_node), ("AutoTSNode", autots_node),
        ("DeeptimeNode", deeptime_node), ("PomegranateHMMNode", pomegranate_hmm_node),
        ("PgmpyBayesNetNode", pgmpy_bayesnet_node), ("EconMLNode", econml_node),
        ("PykalmanNode", pykalman_node), ("SimdKalmanNode", simdkalman_node),
    ]

    print(f"{'node':<20}{'kind':<9}{'proto':<6}{'rowlen':<7}{'acc':<7}{'fit_s':<8}"
          f"{'fell_back':<10}flag")
    print("-" * 80)
    for label, fac in factories:
        node = fac()
        t0 = time.time()
        node.fit(Xtr, ytr)
        dt = time.time() - t0
        rows = node.predict_output(Xte)
        preds = node.predict(Xte)
        acc = float(np.mean([int(p == t) for p, t in zip(preds, yte)]))
        rl = len(rows[0]) if rows else 0
        proto = isinstance(node, NodeProtocol)
        flag = "SLOW>15s" if dt > 15 else ""
        print(f"{node.name:<20}{node.kind:<9}{str(proto):<6}{rl:<7}{acc:<7.3f}"
              f"{dt:<8.2f}{str(node.fell_back):<10}{flag}")
