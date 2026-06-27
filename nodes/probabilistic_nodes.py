"""Uncertainty / probabilistic / symbolic / fuzzy / survival nodes.

Wraps installed OSS (MAPIE, prophet, gplearn, pyFTS/scikit-fuzzy, pymc, lifelines)
behind the project NodeProtocol, in the multi-output contract (task in
{binary, multiclass, regression}; predict_output rows = class-probabilities or
[value]). The shared mechanics — a task-aware StandardScaler+LogisticRegression/
Ridge readout and `predict_output` — are COPIED from nodes/quant_nodes.py so this
module is self-contained and consistent with the rest of the node zoo.

Each node fits its heavy model ONCE (row-level on X->y, or once on the train
target series) and exposes the result as augmented feature columns the readout
consumes. Every model path has a robust, cheap fallback and a degenerate guard,
so a node never crashes the graph — it just degrades gracefully.
"""
from __future__ import annotations

import logging
import os
import time
import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
for _n in ("prophet", "cmdstanpy", "pystan", "pymc", "pytensor", "lifelines"):
    logging.getLogger(_n).setLevel(logging.CRITICAL)


# --------------------------------------------------------------------------- #
#  Shared readout + head mechanics (COPIED from nodes/quant_nodes.py)
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

    kind = "ml"

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


def _base_matrix(X: Matrix) -> np.ndarray:
    return np.asarray([[float(v) for v in row] for row in X], float)


# --------------------------------------------------------------------------- #
#  1. ConformalNode — MAPIE calibrated uncertainty (meta/uncertainty)
# --------------------------------------------------------------------------- #
class ConformalNode(_HeadBase):
    """MAPIE conformal prediction: wrap a RandomForest base estimator and
    cross-conformalize on X->y (row-level). The readout consumes the base
    point/proba prediction PLUS a calibrated-uncertainty column — the conformal
    SET SIZE per row (classification) or the prediction-INTERVAL width
    (regression). The mean uncertainty is stored as `self.set_size_` /
    `self.interval_width_`. Robust fallback to the bare RandomForest if MAPIE is
    unavailable."""

    def __init__(self, name="conformal", col=0):
        super().__init__(name, "MAPIE conformal prediction with calibrated set-size / interval uncertainty.", col)
        self._rf = None
        self._mapie = None
        self.set_size_ = None
        self.interval_width_ = None

    def fit(self, X, y):
        ya = np.asarray(y)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
        Xa = _base_matrix(X)
        try:
            if self.task == "regression":
                from sklearn.ensemble import RandomForestRegressor
                from mapie.regression import CrossConformalRegressor
                self._rf = RandomForestRegressor(n_estimators=60, random_state=0, n_jobs=1).fit(Xa, ya)
                cv = min(5, max(2, len(Xa) // 50))
                self._mapie = CrossConformalRegressor(
                    RandomForestRegressor(n_estimators=60, random_state=0, n_jobs=1),
                    confidence_level=0.9, cv=cv)
                self._mapie.fit_conformalize(Xa, ya)
                _, ints = self._mapie.predict_interval(Xa)
                width = np.asarray(ints)[:, 1, 0] - np.asarray(ints)[:, 0, 0]
                self.interval_width_ = float(np.mean(width))
            else:
                if len(self._classes) < 2:
                    return super().fit(X, y)
                from sklearn.ensemble import RandomForestClassifier
                from mapie.classification import CrossConformalClassifier
                self._rf = RandomForestClassifier(n_estimators=60, random_state=0, n_jobs=1).fit(Xa, ya)
                cv = min(5, max(2, len(Xa) // 50))
                self._mapie = CrossConformalClassifier(
                    RandomForestClassifier(n_estimators=60, random_state=0, n_jobs=1),
                    confidence_level=0.9, cv=cv)
                self._mapie.fit_conformalize(Xa, ya)
                _, sets = self._mapie.predict_set(Xa)
                self.set_size_ = float(np.mean(np.asarray(sets)[:, :, 0].sum(axis=1)))
        except Exception:
            self._mapie = None                                   # bare-RF fallback
            if self._rf is None:
                from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
                self._rf = (RandomForestRegressor(n_estimators=60, random_state=0, n_jobs=1)
                            if self.task == "regression"
                            else RandomForestClassifier(n_estimators=60, random_state=0, n_jobs=1)).fit(Xa, ya)
        return super().fit(X, y)

    def _augment(self, X):
        base = _base_matrix(X)
        if self._rf is None:
            return base
        if self.task == "regression":
            point = self._rf.predict(base).reshape(-1, 1)
            if self._mapie is not None:
                try:
                    _, ints = self._mapie.predict_interval(base)
                    unc = (np.asarray(ints)[:, 1, 0] - np.asarray(ints)[:, 0, 0]).reshape(-1, 1)
                except Exception:
                    unc = np.zeros((len(X), 1))
            else:
                unc = np.zeros((len(X), 1))
            return np.hstack([base, point, unc])
        p = self._rf.predict_proba(base)
        cols = list(self._rf.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        p1 = p[:, j].reshape(-1, 1)
        if self._mapie is not None:
            try:
                _, sets = self._mapie.predict_set(base)
                size = np.asarray(sets)[:, :, 0].sum(axis=1).reshape(-1, 1)
            except Exception:
                size = np.ones((len(X), 1))
        else:
            size = np.ones((len(X), 1))
        return np.hstack([base, p1, size])


# --------------------------------------------------------------------------- #
#  2. ProphetNode — fit-once forecast of the target series
# --------------------------------------------------------------------------- #
class ProphetNode(_HeadBase):
    """facebook prophet: fit ONCE on the training target series (synthetic daily
    `ds` dates, `y` = target), then use the in-sample fitted `yhat` for the train
    rows and an out-of-sample forecast for the test rows, aligned per row as a
    feature. No MCMC (MAP fit) for speed. Robust fallback to a last-value
    forecast."""

    def __init__(self, name="prophet_forecast", col=0):
        super().__init__(name, "prophet fit-once in/out-of-sample yhat forecast as a per-row feature.", col)
        self._model = None
        self._fitted_train = None
        self._ytr = None

    def fit(self, X, y):
        self._ytr = np.asarray(y, float)
        try:
            import pandas as pd
            from prophet import Prophet
            n = len(self._ytr)
            ds = pd.date_range("2000-01-01", periods=n, freq="D")
            df = pd.DataFrame({"ds": ds, "y": self._ytr})
            self._model = Prophet(weekly_seasonality=False, daily_seasonality=False,
                                  yearly_seasonality=False, mcmc_samples=0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._model.fit(df)
                self._fitted_train = np.asarray(self._model.predict(df)["yhat"], float)
            self._train_n = n
        except Exception:
            self._model = None
        return super().fit(X, y)

    def _forecast(self, n):
        last = float(self._ytr[-1]) if self._ytr is not None and len(self._ytr) else 0.0
        if self._model is None:
            return np.full(n, last)
        if self._fitted_train is not None and n == self._train_n:
            return self._fitted_train
        try:
            import pandas as pd
            future = pd.DataFrame({"ds": pd.date_range("2000-01-01", periods=self._train_n + n, freq="D")})
            yhat = np.asarray(self._model.predict(future)["yhat"], float)
            return yhat[self._train_n:self._train_n + n]
        except Exception:
            return np.full(n, last)

    def _augment(self, X):
        base = _base_matrix(X)
        fc = self._forecast(len(X)).reshape(-1, 1)
        return np.hstack([base, fc])


# --------------------------------------------------------------------------- #
#  3. GplearnSymbolicNode — genetic-programming symbolic model (kind=symbolic)
# --------------------------------------------------------------------------- #
class GplearnSymbolicNode(_HeadBase):
    """gplearn genetic programming: evolve a SymbolicClassifier (cls) /
    SymbolicRegressor (reg) on X->y. The discovered program's output is a learned
    nonlinear feature for the readout, and the best program string is stored in
    `self.equation_`. Generations kept small (~10) for speed. Robust fallback to
    a no-op feature if evolution fails."""

    kind = "symbolic"

    def __init__(self, name="gplearn_symbolic", col=0):
        super().__init__(name, "gplearn symbolic regression/classification; best program stored in equation_.", col)
        self._gp = None
        self.equation_ = None

    def fit(self, X, y):
        ya = np.asarray(y)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:
                return super().fit(X, y)
        Xa = _base_matrix(X)
        try:
            if self.task == "regression":
                from gplearn.genetic import SymbolicRegressor
                self._gp = SymbolicRegressor(generations=10, population_size=500,
                                             random_state=0, n_jobs=1, verbose=0)
            else:
                from gplearn.genetic import SymbolicClassifier
                self._gp = SymbolicClassifier(generations=10, population_size=500,
                                              random_state=0, n_jobs=1, verbose=0)
            self._gp.fit(Xa, ya)
            self.equation_ = str(self._gp._program)
        except Exception as e:
            self._gp = None
            self.equation_ = f"<fallback: {type(e).__name__}>"
        return super().fit(X, y)

    def _augment(self, X):
        base = _base_matrix(X)
        if self._gp is None:
            return base
        try:
            if self.task == "regression":
                f = np.asarray(self._gp.predict(base), float).reshape(-1, 1)
            else:
                f = np.asarray(self._gp.predict_proba(base), float)[:, -1].reshape(-1, 1)
        except Exception:
            f = np.zeros((len(X), 1))
        return np.hstack([base, f])


# --------------------------------------------------------------------------- #
#  4. FuzzyTSNode — fuzzy time-series forecast / fuzzy memberships
# --------------------------------------------------------------------------- #
class FuzzyTSNode(_HeadBase):
    """Fuzzy time series: tries a pyFTS Chen model fit-once on the train target
    series for a one-step forecast feature. Robust fallback (used when pyFTS is
    unavailable) to triangular fuzzy-membership features (low/medium/high
    memberships of the windowed value), which capture the same fuzzy-state idea
    cheaply and stably."""

    def __init__(self, name="fuzzy_ts", col=0, W=64):
        super().__init__(name, "pyFTS fuzzy time-series forecast, else triangular fuzzy-membership features.", col, W)
        self._fts = None
        self._ytr = None
        self.path_ = "fuzzy_membership"

    def fit(self, X, y):
        self._ytr = np.asarray(y, float)
        col = np.asarray([float(r[self.col]) for r in X], float)
        self._lo, self._hi = float(np.min(col)), float(np.max(col))
        self._mid = 0.5 * (self._lo + self._hi)
        try:
            from pyFTS.partitioners import Grid
            from pyFTS.models import chen
            part = Grid.GridPartitioner(data=col, npart=10)
            self._fts = chen.ConventionalFTS(partitioner=part)
            self._fts.fit(col)
            # smoke test
            _ = self._fts.predict(col[:5])
            self.path_ = "pyFTS"
        except Exception:
            self._fts = None
            self.path_ = "fuzzy_membership"
        return super().fit(X, y)

    def _tri(self, v):
        lo, mid, hi = self._lo, self._mid, self._hi
        span = max(hi - lo, 1e-9)
        m_lo = max(0.0, 1.0 - abs(v - lo) / (0.5 * span))
        m_mid = max(0.0, 1.0 - abs(v - mid) / (0.5 * span))
        m_hi = max(0.0, 1.0 - abs(v - hi) / (0.5 * span))
        return [m_lo, m_mid, m_hi]

    def _augment(self, X):
        base = _base_matrix(X)
        col = [float(r[self.col]) for r in X]
        if self._fts is not None:
            try:
                fc = np.asarray(self._fts.predict(col), float)
                if len(fc) != len(X):
                    fc = np.resize(fc, len(X))
                return np.hstack([base, fc.reshape(-1, 1)])
            except Exception:
                pass
        mem = np.asarray([self._tri(v) for v in col], float)
        return np.hstack([base, mem])


# --------------------------------------------------------------------------- #
#  5. BayesianNode — small Bayesian regression with posterior-mean prediction
# --------------------------------------------------------------------------- #
class BayesianNode(_HeadBase):
    """Bayesian (logistic for cls / linear for reg) regression. PREFERS pymc
    (draws=300, tune=300, chains=2, cores=1) on a <=400-row subsample for speed,
    using the posterior-mean prediction as a feature. If pymc is missing or the
    fit exceeds a 15s budget, FALLS BACK to sklearn's conjugate Bayesian models
    (BayesianRidge / LogisticRegression). The path taken and fit time are stored
    in `self.bayes_path_` and `self.fit_seconds_`."""

    BUDGET = 15.0

    def __init__(self, name="bayesian", col=0):
        super().__init__(name, "small Bayesian regression (pymc, else sklearn-Bayesian) posterior-mean feature.", col)
        self._model = None
        self.bayes_path_ = None
        self.fit_seconds_ = None

    def fit(self, X, y):
        ya = np.asarray(y)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:
                return super().fit(X, y)
        Xa = _base_matrix(X)
        # subsample <=400 rows for the (slow) Bayesian fit
        rng = np.random.RandomState(0)
        idx = np.arange(len(Xa))
        if len(idx) > 400:
            idx = rng.choice(idx, 400, replace=False)
        Xs, ys = Xa[idx], ya[idx]
        t0 = time.time()
        self._fit_pymc(Xs, ys)
        if self._model is None:
            self._fit_sklearn(Xs, ys)
        self.fit_seconds_ = time.time() - t0
        return super().fit(X, y)

    def _fit_pymc(self, Xs, ys):
        try:
            import pymc as pm                       # noqa: F401
        except Exception:
            self.bayes_path_ = "sklearn (pymc unavailable)"
            return
        try:
            t0 = time.time()
            mu = Xs.mean(0); sd = Xs.std(0) + 1e-9
            Xn = (Xs - mu) / sd
            with pm.Model():
                b0 = pm.Normal("b0", 0, 5)
                b = pm.Normal("b", 0, 5, shape=Xn.shape[1])
                eta = b0 + pm.math.dot(Xn, b)
                if self.task == "regression":
                    sigma = pm.HalfNormal("sigma", 5)
                    pm.Normal("obs", mu=eta, sigma=sigma, observed=ys.astype(float))
                else:
                    pm.Bernoulli("obs", logit_p=eta, observed=ys.astype(int))
                trace = pm.sample(draws=300, tune=300, chains=2, cores=1,
                                  progressbar=False, random_seed=0)
            if time.time() - t0 > self.BUDGET:       # too slow -> fall back
                self._model = None
                self.bayes_path_ = "sklearn (pymc >15s)"
                return
            post = trace.posterior
            self._pymc = {
                "b0": float(post["b0"].mean()),
                "b": np.asarray(post["b"].mean(("chain", "draw"))),
                "mu": mu, "sd": sd,
            }
            self._model = "pymc"
            self.bayes_path_ = "pymc"
        except Exception:
            self._model = None
            self.bayes_path_ = "sklearn (pymc error)"

    def _fit_sklearn(self, Xs, ys):
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        if self.task == "regression":
            from sklearn.linear_model import BayesianRidge
            self._sk = make_pipeline(StandardScaler(), BayesianRidge()).fit(Xs, ys)
        else:
            from sklearn.linear_model import LogisticRegression
            self._sk = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(Xs, ys)
        self._model = "sklearn"
        if self.bayes_path_ is None:
            self.bayes_path_ = "sklearn"

    def _augment(self, X):
        base = _base_matrix(X)
        if self._model == "pymc":
            Xn = (base - self._pymc["mu"]) / self._pymc["sd"]
            eta = self._pymc["b0"] + Xn.dot(self._pymc["b"])
            f = eta if self.task == "regression" else 1.0 / (1.0 + np.exp(-eta))
            return np.hstack([base, f.reshape(-1, 1)])
        if self._model == "sklearn":
            if self.task == "regression":
                f = self._sk.predict(base)
            else:
                f = self._sk.predict_proba(base)[:, -1]
            return np.hstack([base, np.asarray(f).reshape(-1, 1)])
        return base


# --------------------------------------------------------------------------- #
#  6. SurvivalHazardNode — time-to-next-large-move survival model (kind=quant)
# --------------------------------------------------------------------------- #
class SurvivalHazardNode(_HeadBase):
    """Survival analysis of the "time to next large move". On the train target
    series we threshold |return| (90th pct) to mark large moves, take the gaps
    between consecutive large moves as durations (event=1), and fit a lifelines
    Weibull survival model. Per row we track the causal AGE (steps since the last
    large move) and emit [age, predicted-hazard-at-age] as features. Robust
    fallback to a constant empirical hazard rate when lifelines is unavailable or
    too few events exist."""

    kind = "quant"

    def __init__(self, name="survival_hazard", col=0):
        super().__init__(name, "lifelines Weibull time-to-next-large-move hazard, else empirical hazard rate.", col)
        self._lambda = None
        self._rho = None
        self._emp_rate = 0.0
        self.path_ = "empirical"

    def _large_idx(self, col):
        a = np.abs(np.asarray(col, float))
        thr = np.quantile(a, 0.9) if len(a) else 0.0
        return np.where(a > thr)[0], thr

    def fit(self, X, y):
        col = [float(r[self.col]) for r in X]
        idx, self._thr = self._large_idx(col)
        durations = np.diff(idx) if len(idx) >= 2 else np.asarray([], float)
        self._emp_rate = float(len(idx) / max(1, len(col)))
        if len(durations) >= 5:
            try:
                import pandas as pd
                from lifelines import WeibullFitter
                df = pd.DataFrame({"dur": durations.astype(float),
                                   "event": np.ones(len(durations))})
                wf = WeibullFitter().fit(df["dur"], df["event"])
                self._lambda = float(wf.lambda_)
                self._rho = float(wf.rho_)
                self.path_ = "lifelines_weibull"
            except Exception:
                self._lambda = self._rho = None
                self.path_ = "empirical"
        return super().fit(X, y)

    def _hazard(self, t):
        if self._lambda is not None and self._rho is not None:
            t = max(t, 1e-6)
            return (self._rho / self._lambda) * (t / self._lambda) ** (self._rho - 1.0)
        return self._emp_rate

    def _augment(self, X):
        base = _base_matrix(X)
        col = [float(r[self.col]) for r in X]
        ages, hazards, age = [], [], 0
        for v in col:
            ages.append(float(age))
            hazards.append(float(self._hazard(age)))
            age = 0 if abs(v) > self._thr else age + 1     # causal reset on a large move
        extra = np.column_stack([ages, hazards])
        return np.hstack([base, extra])


# --------------------------------------------------------------------------- #
#  NO-ARG factories
# --------------------------------------------------------------------------- #
def conformal_node(): return ConformalNode()
def prophet_node(): return ProphetNode()
def gplearn_symbolic_node(): return GplearnSymbolicNode()
def fuzzy_ts_node(): return FuzzyTSNode()
def bayesian_node(): return BayesianNode()
def survival_hazard_node(): return SurvivalHazardNode()
