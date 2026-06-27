"""Sklearn-style estimator wrappers for advanced ML libraries that are NOT
natively sklearn — so the project's UniversalNode adapter (nodes/universal_node.py)
can drive them uniformly via the algo registry.

These are NOT NodeProtocol nodes. Each class exposes the duck-typed API the
UniversalNode uses:

  * classifiers : ``fit(X, y) -> self``, ``predict(X)``, ``predict_proba(X)``
                  (shape ``(n, 2)`` for binary), and a ``classes_`` attribute.
  * regressors  : ``fit(X, y) -> self``, ``predict(X)`` (float output).
  * transformers: ``fit(X, y=None) -> self``, ``transform(X)``.

All accept numpy arrays, wrap the real library in robust try/except, suppress
warnings, cap iterations/epochs for speed, and run on CPU only.

Real libs wrapped:
  BayesianGMMClassifier   -> sklearn.mixture.BayesianGaussianMixture (per class)
  SurvivalForestClassifier-> sksurv.ensemble.RandomSurvivalForest
  XGBoostLSS{Classifier,Regressor} -> xgboostlss (Gaussian distribution)
  LightGBMLSSRegressor    -> lightgbmlss (Gaussian distribution)
  MetricLearnKNN          -> metric_learn.LMNN/NCA -> KNeighborsClassifier
  BART{Classifier,Regressor} -> stochtree (StochTreeBART* sklearn wrappers)
  MMDFeature              -> hyppo.ksample.MMD (transformer / feature extractor)
"""
from __future__ import annotations

import warnings

import numpy as np

warnings.filterwarnings("ignore")


def _Xf(X) -> np.ndarray:
    return np.asarray(X, dtype=float)


# --------------------------------------------------------------------------- #
# 1. Bayesian Gaussian Mixture classifier (sklearn only — no extra dep)        #
# --------------------------------------------------------------------------- #
class BayesianGMMClassifier:
    """One variational Bayesian Gaussian mixture per class; predict_proba is the
    Bayes-rule normalisation of per-class (prior * likelihood)."""

    def __init__(self, n_components: int = 3, max_iter: int = 80,
                 covariance_type: str = "full", random_state: int = 0):
        self.n_components = n_components
        self.max_iter = max_iter
        self.covariance_type = covariance_type
        self.random_state = random_state
        self.classes_ = np.array([0, 1])
        self._models: dict = {}
        self._logprior: dict = {}

    def fit(self, X, y):
        from sklearn.mixture import BayesianGaussianMixture

        Xa, ya = _Xf(X), np.asarray(y).astype(int).ravel()
        self.classes_ = np.array(sorted(set(ya.tolist())))
        n = len(ya)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            for c in self.classes_:
                Xc = Xa[ya == c]
                k = max(1, min(self.n_components, len(Xc)))
                gm = BayesianGaussianMixture(
                    n_components=k, covariance_type=self.covariance_type,
                    max_iter=self.max_iter, reg_covar=1e-5,
                    weight_concentration_prior_type="dirichlet_process",
                    random_state=self.random_state)
                try:
                    gm.fit(Xc)
                    self._models[int(c)] = gm
                except Exception:
                    self._models[int(c)] = None
                self._logprior[int(c)] = np.log(max(len(Xc), 1) / n)
        return self

    def _log_post(self, Xa: np.ndarray) -> np.ndarray:
        cols = []
        for c in self.classes_:
            gm = self._models.get(int(c))
            if gm is None:
                cols.append(np.full(len(Xa), -1e30))
            else:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    cols.append(gm.score_samples(Xa) + self._logprior[int(c)])
        return np.column_stack(cols)

    def predict_proba(self, X):
        Xa = _Xf(X)
        lp = self._log_post(Xa)
        lp = lp - lp.max(axis=1, keepdims=True)
        p = np.exp(lp)
        s = p.sum(axis=1, keepdims=True)
        s[s == 0] = 1.0
        return p / s

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


# --------------------------------------------------------------------------- #
# 2. Random Survival Forest as a binary classifier (scikit-survival)           #
# --------------------------------------------------------------------------- #
class SurvivalForestClassifier:
    """RandomSurvivalForest treated as a binary classifier: y is the event
    indicator paired with a synthetic time; risk score -> min-max normalised
    probability of the positive class."""

    def __init__(self, n_estimators: int = 100, max_depth: int = 8,
                 min_samples_leaf: int = 5, random_state: int = 0):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.classes_ = np.array([0, 1])
        self._est = None
        self._lo = 0.0
        self._hi = 1.0

    def fit(self, X, y):
        from sksurv.ensemble import RandomSurvivalForest
        from sksurv.util import Surv

        Xa, ya = _Xf(X), np.asarray(y).astype(int).ravel()
        self.classes_ = np.array(sorted(set(ya.tolist())))
        if len(self.classes_) < 2:
            return self
        event = ya.astype(bool)
        rng = np.random.RandomState(self.random_state)
        # synthetic time: events get shorter (earlier) times than censored rows.
        time = np.where(event, rng.uniform(0.5, 1.5, len(ya)),
                        rng.uniform(1.5, 2.5, len(ya)))
        sy = Surv.from_arrays(event=event, time=time)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            self._est = RandomSurvivalForest(
                n_estimators=self.n_estimators, max_depth=self.max_depth,
                min_samples_leaf=self.min_samples_leaf, n_jobs=1,
                random_state=self.random_state)
            self._est.fit(Xa, sy)
            risk = np.asarray(self._est.predict(Xa), dtype=float)
        self._lo, self._hi = float(risk.min()), float(risk.max())
        return self

    def _risk(self, X) -> np.ndarray:
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            return np.asarray(self._est.predict(_Xf(X)), dtype=float)

    def predict_proba(self, X):
        if self._est is None:
            return np.tile([1.0, 0.0], (len(_Xf(X)), 1))
        r = self._risk(X)
        rng = self._hi - self._lo
        p1 = (r - self._lo) / rng if rng > 0 else np.full(len(r), 0.5)
        p1 = np.clip(p1, 0.0, 1.0)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


# Alias used by the algo registry (universal_node.py).
SurvivalForestNode = SurvivalForestClassifier


# --------------------------------------------------------------------------- #
# 3. XGBoostLSS (distributional gradient boosting)                             #
# --------------------------------------------------------------------------- #
def _xgblss_train(Xa, ya, n_estimators, eta, seed):
    """Train a Gaussian XGBoostLSS booster; return (model, mean_fn) or raise."""
    import xgboost as xgb
    from xgboostlss.distributions.Gaussian import Gaussian
    from xgboostlss.model import XGBoostLSS

    dist = Gaussian(stabilization="None", response_fn="exp", loss_fn="nll")
    model = XGBoostLSS(dist)
    dtrain = xgb.DMatrix(Xa, label=ya, nthread=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.train({"eta": eta, "nthread": 1, "seed": seed},
                    dtrain, num_boost_round=n_estimators, verbose_eval=False)

    def mean_fn(Xq):
        d = xgb.DMatrix(_Xf(Xq), nthread=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            params = model.predict(d, pred_type="parameters")
        return np.asarray(params["loc"], dtype=float)

    return model, mean_fn


class XGBoostLSSRegressor:
    """xgboostlss Gaussian regressor; predict = predicted distribution mean
    (loc). Falls back to plain xgboost if LSS training fails."""

    def __init__(self, n_estimators: int = 60, eta: float = 0.1, random_state: int = 0):
        self.n_estimators = n_estimators
        self.eta = eta
        self.random_state = random_state
        self._mean_fn = None
        self._fallback = None
        self.used_fallback = False

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y, dtype=float).ravel()
        try:
            _, self._mean_fn = _xgblss_train(Xa, ya, self.n_estimators,
                                             self.eta, self.random_state)
        except Exception:
            import xgboost as xgb
            self.used_fallback = True
            self._fallback = xgb.XGBRegressor(
                n_estimators=self.n_estimators, learning_rate=self.eta,
                n_jobs=1, random_state=self.random_state)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._fallback.fit(Xa, ya)
        return self

    def predict(self, X):
        if self._mean_fn is not None:
            return self._mean_fn(X)
        return np.asarray(self._fallback.predict(_Xf(X)), dtype=float)


class XGBoostLSSClassifier:
    """xgboostlss Gaussian fit on the {0,1} target; the predicted mean (loc) is
    clipped to [0,1] and used as P(class=1). Falls back to plain xgboost."""

    def __init__(self, n_estimators: int = 60, eta: float = 0.1, random_state: int = 0):
        self.n_estimators = n_estimators
        self.eta = eta
        self.random_state = random_state
        self.classes_ = np.array([0, 1])
        self._mean_fn = None
        self._fallback = None
        self.used_fallback = False

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y).astype(int).ravel()
        self.classes_ = np.array(sorted(set(ya.tolist())))
        try:
            _, self._mean_fn = _xgblss_train(Xa, ya.astype(float),
                                             self.n_estimators, self.eta,
                                             self.random_state)
        except Exception:
            import xgboost as xgb
            self.used_fallback = True
            self._fallback = xgb.XGBClassifier(
                n_estimators=self.n_estimators, learning_rate=self.eta,
                n_jobs=1, random_state=self.random_state)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._fallback.fit(Xa, ya)
        return self

    def predict_proba(self, X):
        if self._mean_fn is not None:
            p1 = np.clip(self._mean_fn(X), 0.0, 1.0)
            return np.column_stack([1.0 - p1, p1])
        proba = self._fallback.predict_proba(_Xf(X))
        return np.asarray(proba, dtype=float)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


# --------------------------------------------------------------------------- #
# 4. LightGBMLSS (distributional gradient boosting)                            #
# --------------------------------------------------------------------------- #
class LightGBMLSSRegressor:
    """lightgbmlss Gaussian regressor; predict = predicted distribution mean
    (loc). Falls back to plain lightgbm if LSS training fails."""

    def __init__(self, n_estimators: int = 60, eta: float = 0.1, random_state: int = 0):
        self.n_estimators = n_estimators
        self.eta = eta
        self.random_state = random_state
        self._model = None
        self._fallback = None
        self.used_fallback = False

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y, dtype=float).ravel()
        try:
            import lightgbm as lgb
            from lightgbmlss.distributions.Gaussian import Gaussian
            from lightgbmlss.model import LightGBMLSS

            dist = Gaussian(stabilization="None", response_fn="exp", loss_fn="nll")
            self._model = LightGBMLSS(dist)
            dtrain = lgb.Dataset(Xa, label=ya)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._model.train(
                    {"eta": self.eta, "verbose": -1, "num_threads": 1,
                     "seed": self.random_state},
                    dtrain, num_boost_round=self.n_estimators)
        except Exception:
            import lightgbm as lgb
            self.used_fallback = True
            self._model = None
            self._fallback = lgb.LGBMRegressor(
                n_estimators=self.n_estimators, learning_rate=self.eta,
                n_jobs=1, random_state=self.random_state, verbose=-1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._fallback.fit(Xa, ya)
        return self

    def predict(self, X):
        if self._model is not None:
            import pandas as pd
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                params = self._model.predict(pd.DataFrame(_Xf(X)),
                                             pred_type="parameters")
            return np.asarray(params["loc"], dtype=float)
        return np.asarray(self._fallback.predict(_Xf(X)), dtype=float)


# --------------------------------------------------------------------------- #
# 5. Metric-learning KNN (metric_learn LMNN/NCA -> KNeighborsClassifier)       #
# --------------------------------------------------------------------------- #
class MetricLearnKNN:
    """sklearn Pipeline: supervised metric learning (LMNN, falling back to NCA)
    transform -> KNeighborsClassifier."""

    def __init__(self, n_neighbors: int = 5, max_iter: int = 30, random_state: int = 0):
        self.n_neighbors = n_neighbors
        self.max_iter = max_iter
        self.random_state = random_state
        self.classes_ = np.array([0, 1])
        self._pipe = None
        self.used_fallback = False

    @staticmethod
    def _patch_metric_learn():
        """metric_learn 0.7.0 calls check_X_y/check_array with the kwarg
        ``force_all_finite``, which newer sklearn renamed to
        ``ensure_all_finite``. Shim the names metric_learn imported so the real
        library works without downgrading sklearn."""
        import functools
        import inspect

        import metric_learn._util as mu

        def shim(fn):
            if getattr(fn, "_ml_shimmed", False):
                return fn
            params = inspect.signature(fn).parameters

            @functools.wraps(fn)
            def wrapper(*a, **k):
                if "force_all_finite" in k and "force_all_finite" not in params:
                    k["ensure_all_finite"] = k.pop("force_all_finite")
                return fn(*a, **k)

            wrapper._ml_shimmed = True
            return wrapper

        mu.check_X_y = shim(mu.check_X_y)
        mu.check_array = shim(mu.check_array)

    def _build(self):
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.pipeline import Pipeline

        try:
            self._patch_metric_learn()
        except Exception:
            pass
        knn = KNeighborsClassifier(n_neighbors=self.n_neighbors)
        try:
            from metric_learn import LMNN
            transformer = LMNN(n_neighbors=min(3, self.n_neighbors),
                               max_iter=self.max_iter, init="auto",
                               random_state=self.random_state)
        except Exception:
            from metric_learn import NCA
            self.used_fallback = True
            transformer = NCA(max_iter=self.max_iter,
                              random_state=self.random_state)
        return Pipeline([("metric", transformer), ("knn", knn)])

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y).astype(int).ravel()
        self.classes_ = np.array(sorted(set(ya.tolist())))
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                self._pipe = self._build()
                self._pipe.fit(Xa, ya)
            except Exception:
                # metric learner failed -> plain KNN on raw features.
                from sklearn.neighbors import KNeighborsClassifier
                self.used_fallback = True
                self._pipe = KNeighborsClassifier(n_neighbors=self.n_neighbors)
                self._pipe.fit(Xa, ya)
        self.classes_ = np.asarray(self._pipe.classes_)
        return self

    def predict_proba(self, X):
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            return np.asarray(self._pipe.predict_proba(_Xf(X)), dtype=float)

    def predict(self, X):
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            return np.asarray(self._pipe.predict(_Xf(X)))


# --------------------------------------------------------------------------- #
# 6. BART — Bayesian Additive Regression Trees (stochtree)                     #
# --------------------------------------------------------------------------- #
class BARTRegressor:
    """stochtree BART regressor (posterior-mean prediction). Falls back to
    sklearn GradientBoostingRegressor if stochtree is unavailable/fails."""

    def __init__(self, num_gfr: int = 5, num_mcmc: int = 40, random_state: int = 0):
        self.num_gfr = num_gfr
        self.num_mcmc = num_mcmc
        self.random_state = random_state
        self._est = None
        self.used_fallback = False

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y, dtype=float).ravel()
        try:
            from stochtree import StochTreeBARTRegressor
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                self._est = StochTreeBARTRegressor(
                    num_gfr=self.num_gfr, num_burnin=0, num_mcmc=self.num_mcmc)
                self._est.fit(Xa, ya)
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor
            self.used_fallback = True
            self._est = GradientBoostingRegressor(random_state=self.random_state)
            self._est.fit(Xa, ya)
        return self

    def predict(self, X):
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            return np.asarray(self._est.predict(_Xf(X)), dtype=float).ravel()


class BARTClassifier:
    """stochtree BART binary classifier; posterior-mean class probabilities.
    Falls back to sklearn GradientBoostingClassifier if stochtree fails."""

    def __init__(self, num_gfr: int = 5, num_mcmc: int = 40, random_state: int = 0):
        self.num_gfr = num_gfr
        self.num_mcmc = num_mcmc
        self.random_state = random_state
        self.classes_ = np.array([0, 1])
        self._est = None
        self.used_fallback = False

    def fit(self, X, y):
        Xa, ya = _Xf(X), np.asarray(y).astype(int).ravel()
        self.classes_ = np.array(sorted(set(ya.tolist())))
        try:
            from stochtree import StochTreeBARTBinaryClassifier
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                self._est = StochTreeBARTBinaryClassifier(
                    num_gfr=self.num_gfr, num_burnin=0, num_mcmc=self.num_mcmc)
                self._est.fit(Xa, ya)
        except Exception:
            from sklearn.ensemble import GradientBoostingClassifier
            self.used_fallback = True
            self._est = GradientBoostingClassifier(random_state=self.random_state)
            self._est.fit(Xa, ya)
        self.classes_ = np.asarray(getattr(self._est, "classes_", self.classes_))
        return self

    def predict_proba(self, X):
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            p = np.asarray(self._est.predict_proba(_Xf(X)), dtype=float)
        if p.ndim == 1:
            p = np.column_stack([1.0 - p, p])
        return p

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


# --------------------------------------------------------------------------- #
# 7. MMD feature extractor (hyppo) — a TRANSFORMER, not a classifier           #
# --------------------------------------------------------------------------- #
class MMDFeature:
    """Per-row distributional feature: splits each row's feature window into two
    halves and computes the hyppo MMD k-sample statistic between them (a measure
    of within-window non-stationarity). transform returns shape (n, 1)."""

    def __init__(self, compute_kernel: str = "gaussian"):
        self.compute_kernel = compute_kernel
        self._mmd = None

    def fit(self, X, y=None):
        try:
            from hyppo.ksample import MMD
            self._mmd = MMD(compute_kernel=self.compute_kernel)
        except Exception:
            self._mmd = None
        return self

    def _row_stat(self, row: np.ndarray) -> float:
        h = len(row) // 2
        if h < 2:
            return float(abs(np.mean(row[:h]) - np.mean(row[h:]))) if h else 0.0
        a = row[:h].reshape(-1, 1)
        b = row[h:2 * h].reshape(-1, 1)
        if self._mmd is not None:
            try:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    return float(self._mmd.test(a, b, reps=0).stat)
            except Exception:
                pass
        return float(abs(np.mean(a) - np.mean(b)))

    def transform(self, X):
        Xa = _Xf(X)
        return np.array([[self._row_stat(r)] for r in Xa], dtype=float)

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)


# --------------------------------------------------------------------------- #
# Self-verification harness                                                    #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    import time as _time

    sys.path.insert(0, "/home/karan18190164")
    from sklearn.metrics import accuracy_score, r2_score
    from sklearn.model_selection import train_test_split

    from data.benchmarks import make_benchmark_dataset

    ds = make_benchmark_dataset("mackey_glass", 500, 0.05)
    X = np.asarray(ds["X"], dtype=float)
    y_bin = np.asarray(ds["y"], dtype=int)
    y_reg = np.asarray(ds["y_return"], dtype=float)
    print(f"dataset: X={X.shape}  y_bin balance={y_bin.mean():.2f}")

    Xtr, Xte, ytr, yte = train_test_split(X, y_bin, test_size=0.3, random_state=0)
    _, _, rtr, rte = train_test_split(X, y_reg, test_size=0.3, random_state=0)

    classifiers = {
        "BayesianGMMClassifier": BayesianGMMClassifier(),
        "SurvivalForestClassifier": SurvivalForestClassifier(),
        "XGBoostLSSClassifier": XGBoostLSSClassifier(),
        "MetricLearnKNN": MetricLearnKNN(),
        "BARTClassifier": BARTClassifier(),
    }
    regressors = {
        "XGBoostLSSRegressor": XGBoostLSSRegressor(),
        "LightGBMLSSRegressor": LightGBMLSSRegressor(),
        "BARTRegressor": BARTRegressor(),
    }

    rows = []
    for name, est in classifiers.items():
        t0 = _time.time()
        try:
            est.fit(Xtr, ytr)
            proba = est.predict_proba(Xte)
            pred = est.predict(Xte)
            dt = _time.time() - t0
            ok_shape = np.shape(proba) == (len(Xte), 2)
            ok_cls = list(np.asarray(est.classes_)) == [0, 1]
            acc = accuracy_score(yte, pred)
            fb = getattr(est, "used_fallback", False)
            flag = "<<<" if dt > 15 or fb else ""
            rows.append((name, "clf", f"acc={acc:.3f}", f"proba={np.shape(proba)}",
                         f"cls_ok={ok_cls}", f"{dt:.2f}s", "FALLBACK" if fb else "real", flag))
            assert ok_shape and ok_cls, f"{name} contract failed"
        except Exception as e:
            rows.append((name, "clf", f"ERROR: {e}", "", "", "", "", "<<<"))

    for name, est in regressors.items():
        t0 = _time.time()
        try:
            est.fit(Xtr, rtr)
            pred = est.predict(Xte)
            dt = _time.time() - t0
            r2 = r2_score(rte, pred)
            fb = getattr(est, "used_fallback", False)
            flag = "<<<" if dt > 15 or fb else ""
            rows.append((name, "reg", f"R2={r2:.3f}", f"n_pred={len(pred)}",
                         "", f"{dt:.2f}s", "FALLBACK" if fb else "real", flag))
        except Exception as e:
            rows.append((name, "reg", f"ERROR: {e}", "", "", "", "", "<<<"))

    # transformer
    t0 = _time.time()
    try:
        mf = MMDFeature().fit(Xtr)
        feat = mf.transform(Xte)
        dt = _time.time() - t0
        rows.append(("MMDFeature", "transform", f"out={feat.shape}", "",
                     "", f"{dt:.2f}s", "real", "<<<" if dt > 15 else ""))
    except Exception as e:
        rows.append(("MMDFeature", "transform", f"ERROR: {e}", "", "", "", "", "<<<"))

    print("\n" + "=" * 100)
    hdr = ("CLASS", "TYPE", "METRIC", "SHAPE", "CLASSES", "FIT", "LIB", "FLAG")
    print("{:<26}{:<10}{:<14}{:<16}{:<12}{:<9}{:<10}{}".format(*hdr))
    print("-" * 100)
    for r in rows:
        print("{:<26}{:<10}{:<14}{:<16}{:<12}{:<9}{:<10}{}".format(*r))
    print("=" * 100)
