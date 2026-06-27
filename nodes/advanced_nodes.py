"""Advanced / newly-researched node families behind the project NodeProtocol.

Wraps freshly-surveyed OSS (tick Hawkes, reservoirpy next-gen reservoir NVAR,
pyEDM empirical-dynamic-modelling, minisom SOM, pyoselm ELM, pyvinecopulib vine
copulas, aeon MiniRocket, sklearn Nystroem) plus a dependency-free depth-2 path
signature, all in the multi-output contract (task in {binary,multiclass,
regression}; predict_output rows = class-probabilities or [value]).

Mechanics are COPIED from nodes/quant_nodes.py: the task-aware readout
(LogisticRegression for classification / Ridge for regression), the fit-once /
causal-trailing-window discipline, and the degenerate (single-class) guard. We
reuse `_HeadBase` (fit-once recursion nodes, row-level nodes) and `_WindowFeat`
(per-window causal-feature nodes) directly.

Window nodes take a 1-D signal from feature column `col` (default 0) with CAUSAL
trailing windows of length W (no look-ahead). Every external fit is wrapped with
a robust fallback so a node never crashes the graph; warnings are suppressed.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import IOSchema, Labels, Matrix, Vector
from nodes.quant_nodes import _HeadBase, _WindowFeat

warnings.filterwarnings("ignore")


# =========================================================================== #
#  1. HawkesNode (quant) — self-exciting point process on extreme-move events
# =========================================================================== #
class HawkesNode(_WindowFeat):
    """tick 1-D Hawkes: derive EVENTS from the window (times where |return|
    exceeds its 90th percentile), fit an exponential-kernel Hawkes process and
    read off [branching ratio, baseline intensity, event rate]. Robust fallback
    to inter-event-time mean/std if the tick fit fails."""

    kind = "quant"
    NFEAT = 3

    def __init__(self, name="hawkes", col=0, W=96):
        super().__init__(name, "tick Hawkes self-excitation on extreme-move events.", col, W)

    def _features(self, win):
        a = np.abs(np.asarray(win, float))
        thr = np.quantile(a, 0.90)
        ts = np.where(a > thr)[0].astype(np.float64)
        rate = float(len(ts)) / max(1.0, float(len(a)))
        if len(ts) < 3:
            return [0.0, rate, rate]
        try:
            from tick.hawkes import HawkesExpKern
            t0 = ts - ts[0] + 1e-6                         # start just after 0
            end = float(len(a))
            model = HawkesExpKern(decays=1.0, penalty="l2", C=1e3,
                                  max_iter=80, verbose=False)
            model.fit([t0], end_times=end)
            branching = float(np.ravel(model.adjacency)[0])   # exp-kernel integral
            baseline = float(np.ravel(model.baseline)[0])
            return [branching, baseline, rate]
        except Exception:
            iet = np.diff(ts)                              # inter-event-time fallback
            if len(iet) == 0:
                return [0.0, 0.0, rate]
            return [float(np.mean(iet)), float(np.std(iet)), rate]


# =========================================================================== #
#  2. NVARNode (physics) — next-generation reservoir (NVAR) 1-step forecast
# =========================================================================== #
class NVARNode(_HeadBase):
    """reservoirpy NVAR (next-gen reservoir): build delay + polynomial features
    of the signal and learn a 1-step forecast ONCE on the training series, then
    apply it causally to produce a per-row forecast feature. Robust fallback to
    a polynomial-AR forecast."""

    kind = "physics"

    def __init__(self, name="nvar", col=0, delay=2, order=2):
        super().__init__(name, "reservoirpy NVAR next-gen-reservoir 1-step forecast (fit-once).", col)
        self.delay, self.order = delay, order
        self._model = None
        self._poly = None                                 # (coef, p) AR fallback

    def _series(self, X):
        return np.asarray([row[self.col] for row in X], float)

    def _fit_poly(self, s):
        p = max(self.delay, 2)
        rows, tgt = [], []
        for i in range(p, len(s)):
            lags = s[i - p:i]
            rows.append(np.concatenate([lags, lags ** 2]))
            tgt.append(s[i])
        if len(rows) < 5:
            self._poly = (None, p)
            return
        A = np.asarray(rows); b = np.asarray(tgt)
        coef, *_ = np.linalg.lstsq(np.hstack([A, np.ones((len(A), 1))]), b, rcond=None)
        self._poly = (coef, p)

    def _poly_forecast(self, s):
        coef, p = self._poly
        out = np.empty(len(s))
        for i in range(len(s)):
            if coef is None or i < p:
                out[i] = s[i]
            else:
                lags = s[i - p:i]
                feat = np.concatenate([lags, lags ** 2, [1.0]])
                out[i] = float(feat @ coef)
        return out

    def fit(self, X, y):
        s = self._series(X)
        try:
            from reservoirpy.nodes import NVAR, Ridge
            nvar = NVAR(delay=self.delay, order=self.order, strides=1)
            readout = Ridge(output_dim=1, ridge=1e-4)
            self._model = nvar >> readout
            U = s[:-1].reshape(-1, 1); Yt = s[1:].reshape(-1, 1)
            self._model.fit(U, Yt, warmup=self.delay)
        except Exception:
            self._model = None
            self._fit_poly(s)
        return super().fit(X, y)

    def _forecast(self, s):
        if self._model is not None:
            try:
                pred = np.ravel(np.asarray(self._model.run(s.reshape(-1, 1))))
                if len(pred) == len(s):
                    return pred
            except Exception:
                pass
        if self._poly is None:
            self._fit_poly(s)
        return self._poly_forecast(s)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        fc = self._forecast(self._series(X)).reshape(-1, 1)
        return np.hstack([base, fc])


# =========================================================================== #
#  3. SignatureNode (math) — dependency-free depth-2 rough-path signature
# =========================================================================== #
class SignatureNode(_WindowFeat):
    """Depth-2 path signature (pure numpy, no iisignature) of the 2-D path
    (cumulative value, normalised time) over the window: level-1 = the value
    increment; level-2 = iterated integrals S^{vv}, S^{vt}, S^{tv} and the Lévy
    (signed) area. The rough-path / signature feature lens."""

    kind = "math"
    NFEAT = 5

    def __init__(self, name="signature", col=0, W=64):
        super().__init__(name, "depth-2 numpy path signature (rough-path) features.", col, W)

    def _features(self, win):
        V = np.asarray(win, float)
        T = np.linspace(0.0, 1.0, len(V))
        dV = np.diff(V); dT = np.diff(T)
        Vc = V[:-1] - V[0]                                # left-point cumulative
        Tc = T[:-1] - T[0]
        s_v = float(V[-1] - V[0])                         # level-1 (time incr ==1, omitted)
        S_vv = 0.5 * s_v * s_v                            # iterated integral ∫∫ dV dV
        S_vt = float(np.sum(Vc * dT))                     # ∫ (V_s-V_0) dT
        S_tv = float(np.sum(Tc * dV))                     # ∫ (T_s-T_0) dV
        levy = 0.5 * (S_vt - S_tv)                        # signed (Lévy) area
        return [s_v, S_vv, S_vt, S_tv, levy]


# =========================================================================== #
#  4. EDMNode (chaos) — empirical dynamic modelling (Takens) nonlinear forecast
# =========================================================================== #
class EDMNode(_WindowFeat):
    """pyEDM Simplex projection: a Takens-embedding nonlinear forecast of the
    series, giving a 1-step prediction and the local prediction skill (rho) as
    per-window features. Robust fallback to a k-NN-in-delay-space forecast."""

    kind = "chaos"
    NFEAT = 2

    def __init__(self, name="edm", col=0, W=96, E=3):
        super().__init__(name, "pyEDM Simplex Takens-embedding forecast + skill.", col, W)
        self.E = E

    def _knn_forecast(self, x):
        E, tau, k = self.E, 1, self.E + 1
        n = len(x)
        idx = [i for i in range((E - 1) * tau, n - 1)]
        if len(idx) < k + 1:
            return float(x[-1]), 0.0
        emb = np.array([[x[i - j * tau] for j in range(E)] for i in idx])
        nxt = np.array([x[i + 1] for i in idx])
        q = np.array([x[(n - 1) - j * tau] for j in range(E)])
        d = np.linalg.norm(emb - q, axis=1)
        nn = np.argsort(d)[:k]
        w = np.exp(-d[nn] / (d[nn].min() + 1e-9)); w /= w.sum()
        pred = float(np.sum(w * nxt[nn]))
        # in-sample skill via 1-NN leave-one-out correlation
        preds = []
        for r in range(len(emb)):
            dr = np.linalg.norm(emb - emb[r], axis=1); dr[r] = np.inf
            preds.append(nxt[np.argmin(dr)])
        rho = float(np.corrcoef(preds, nxt)[0, 1]) if np.std(preds) > 0 else 0.0
        return pred, (rho if np.isfinite(rho) else 0.0)

    def _features(self, win):
        x = np.asarray(win, float)
        try:
            import pandas as pd, pyEDM
            df = pd.DataFrame({"time": np.arange(1, len(x) + 1), "x": x})
            lib = f"1 {len(x)}"
            out = pyEDM.Simplex(dataFrame=df, columns="x", target="x",
                                lib=lib, pred=lib, E=self.E, Tp=1,
                                exclusionRadius=1, showPlot=False)
            obs = out["Observations"].to_numpy(float)
            prd = out["Predictions"].to_numpy(float)
            pred = prd[~np.isnan(prd)]
            pred1 = float(pred[-1]) if len(pred) else float(x[-1])
            err = pyEDM.ComputeError(obs, prd)
            rho = float(err.get("rho", 0.0))
            return [pred1, rho if np.isfinite(rho) else 0.0]
        except Exception:
            pred1, rho = self._knn_forecast(x)
            return [pred1, rho]


# =========================================================================== #
#  5. SOMNode (ml) — self-organising map novelty / topographic coordinates
# =========================================================================== #
class SOMNode(_HeadBase):
    """minisom 6x6 self-organising map fit ONCE on the training feature rows;
    per row appends [distance-to-best-matching-unit (novelty), BMU row, BMU col]
    to X, then the task-aware readout. Topographic clustering layer."""

    kind = "ml"

    def __init__(self, name="som", grid=6):
        super().__init__(name, "minisom self-organising-map novelty + BMU coordinates.", 0)
        self.grid = grid
        self._som = None
        self._scaler = None

    def fit(self, X, y):
        try:
            from minisom import MiniSom
            from sklearn.preprocessing import StandardScaler
            self._scaler = StandardScaler().fit(X)
            Z = self._scaler.transform(X)
            d = Z.shape[1]
            self._som = MiniSom(self.grid, self.grid, d,
                                sigma=1.0, learning_rate=0.5, random_seed=0)
            self._som.random_weights_init(Z)
            self._som.train_random(Z, 500)
        except Exception:
            self._som = None
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        if self._som is None:
            extra = np.zeros((len(X), 3))
        else:
            Z = self._scaler.transform(base)
            rows = []
            for z in Z:
                r, c = self._som.winner(z)
                w = self._som.get_weights()[r, c]
                rows.append([float(np.linalg.norm(z - w)), float(r), float(c)])
            extra = np.asarray(rows)
        return np.hstack([base, extra])


# =========================================================================== #
#  6. ELMNode (ml) — Extreme Learning Machine (random hidden layer, closed form)
# =========================================================================== #
class ELMNode(_HeadBase):
    """pyoselm Extreme Learning Machine on X -> y directly: a random hidden layer
    with a closed-form output solve. ELMClassifier for classification,
    ELMRegressor for regression. A fast nonlinear forecaster. Robust fallback to
    the standard task-aware readout if the ELM fit fails."""

    kind = "ml"

    def __init__(self, name="elm", n_hidden=60):
        super().__init__(name, "pyoselm Extreme Learning Machine (closed-form random net).", 0)
        self.n_hidden = n_hidden
        self._elm = None
        self._fallback = None

    def fit(self, X, y):
        ya = np.asarray(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", self.task)
        from sklearn.preprocessing import StandardScaler
        self._scaler = StandardScaler().fit(X)
        Z = self._scaler.transform(X)
        if self.task != "regression":
            self._classes = sorted(int(v) for v in set(ya))
            if len(self._classes) < 2:
                return self
        try:
            from pyoselm import ELMClassifier, ELMRegressor
            if self.task == "regression":
                self._elm = ELMRegressor(n_hidden=self.n_hidden, random_state=0)
            else:
                self._elm = ELMClassifier(n_hidden=self.n_hidden, random_state=0)
            self._elm.fit(Z, ya.astype(float) if self.task == "regression" else ya.astype(int))
        except Exception:
            from nodes.quant_nodes import _readout
            self._elm = None
            self._fallback = _readout(self.task)
            self._fallback.fit(Z, ya)
        return self

    def _proba_matrix(self, X):
        Z = self._scaler.transform(np.asarray([[float(v) for v in r] for r in X], float))
        if self._elm is not None:
            p = np.asarray(self._elm.predict_proba(Z), float)
        else:
            p = np.asarray(self._fallback.predict_proba(Z), float)
            return p, list(getattr(self._fallback, "classes_", self._classes))
        if p.ndim == 1 or p.shape[1] == 1:                # binary single-column p1
            p = p.reshape(-1)
            p = np.clip(p, 0.0, 1.0)
            return np.column_stack([1.0 - p, p]), [0, 1] if self._classes == [0, 1] else self._classes
        return p, list(self._classes)

    def predict_proba(self, X) -> Vector:
        if self.task != "regression" and len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        if self.task == "regression":
            Z = self._scaler.transform(np.asarray([[float(v) for v in r] for r in X], float))
            v = (self._elm.predict(Z) if self._elm is not None
                 else self._fallback.predict(Z))
            v = np.asarray(v, float)
            lo, hi = float(v.min()), float(v.max())
            return [float((x - lo) / (hi - lo)) if hi > lo else 0.5 for x in v]
        P, cols = self._proba_matrix(X)
        if self.task == "multiclass":
            return [float(r.max()) for r in P]
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(r[j]) for r in P]

    def predict_output(self, X):
        if self.task != "regression" and len(self._classes) < 2:
            return [[1.0]] * len(X)
        if self.task == "regression":
            Z = self._scaler.transform(np.asarray([[float(v) for v in r] for r in X], float))
            v = (self._elm.predict(Z) if self._elm is not None else self._fallback.predict(Z))
            return [[float(x)] for x in np.asarray(v, float)]
        P, cols = self._proba_matrix(X)
        if self.task == "multiclass":
            order = [cols.index(c) for c in self._classes]
            return [[float(r[o]) for o in order] for r in P]
        return [[1.0 - p, p] for p in self.predict_proba(X)]

    def predict(self, X) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            Z = self._scaler.transform(np.asarray([[float(v) for v in r] for r in X], float))
            v = (self._elm.predict(Z) if self._elm is not None else self._fallback.predict(Z))
            return [int(round(float(x))) for x in np.asarray(v, float)]
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


# =========================================================================== #
#  7. CopulaNode (quant) — vine-copula tail dependence per window
# =========================================================================== #
class CopulaNode(_WindowFeat):
    """pyvinecopulib vine copula fit per window on 2-3 derived feature columns
    (value, lagged value, abs-return), reading off [average pairwise tail
    dependence, copula log-likelihood]. Robust fallback to Spearman/Kendall tail
    statistics if the copula fit fails."""

    kind = "quant"
    NFEAT = 2

    def __init__(self, name="copula", col=0, W=96):
        super().__init__(name, "pyvinecopulib vine-copula tail dependence + log-likelihood.", col, W)

    @staticmethod
    def _cols(win):
        v = np.asarray(win, float)
        c0 = v[1:]
        c1 = v[:-1]                                       # lag-1
        c2 = np.abs(np.diff(v))                           # abs return
        return np.column_stack([c0, c1, c2])

    @staticmethod
    def _pit(M):
        n = M.shape[0]
        U = np.empty_like(M)
        for j in range(M.shape[1]):
            U[:, j] = (np.argsort(np.argsort(M[:, j])) + 1.0) / (n + 1.0)
        return np.clip(U, 1e-6, 1 - 1e-6)

    @staticmethod
    def _emp_tail(U, q=0.9):
        n, d = U.shape
        ups, los = [], []
        for a in range(d):
            for b in range(a + 1, d):
                up = np.mean((U[:, a] > q) & (U[:, b] > q)) / max(1e-9, (1 - q))
                lo = np.mean((U[:, a] < 1 - q) & (U[:, b] < 1 - q)) / max(1e-9, (1 - q))
                ups.append(up); los.append(lo)
        return float(np.mean(ups + los)) if ups else 0.0

    def _features(self, win):
        M = self._cols(win)
        if len(M) < 12:
            return [0.0, 0.0]
        U = self._pit(M)
        try:
            from pyvinecopulib import BicopFamily, FitControlsVinecop, Vinecop
            ctrl = FitControlsVinecop(family_set=[BicopFamily.gaussian,
                                                  BicopFamily.clayton,
                                                  BicopFamily.gumbel])
            vc = Vinecop.from_data(U, controls=ctrl)
            ll = float(vc.loglik(U))
            tail = self._emp_tail(U)
            return [tail, ll]
        except Exception:
            from scipy.stats import kendalltau
            taus = []
            for a in range(M.shape[1]):
                for b in range(a + 1, M.shape[1]):
                    t, _ = kendalltau(M[:, a], M[:, b])
                    taus.append(abs(t) if np.isfinite(t) else 0.0)
            return [float(np.mean(taus)) if taus else 0.0, self._emp_tail(U)]


# =========================================================================== #
#  8. RocketNode (ml) — MiniRocket random-convolution time-series transform
# =========================================================================== #
class RocketNode(_HeadBase):
    """aeon MiniRocket random-convolutional-kernel transform of the windowed
    univariate signal, fit ONCE on the training windows -> fixed feature map ->
    task-aware readout. Robust fallback to a numpy random-conv-kernel transform."""

    kind = "ml"

    def __init__(self, name="rocket", col=0, W=64, n_kernels=256):
        super().__init__(name, "aeon MiniRocket random-conv-kernel time-series features.", col, W)
        self.n_kernels = n_kernels
        self._mr = None
        self._rk = None                                   # numpy fallback kernels

    def _windows(self, X):
        col = [float(r[self.col]) for r in X]
        out = np.empty((len(X), self.W), float)
        for i in range(len(X)):
            w = col[max(0, i - self.W + 1): i + 1]
            if len(w) < self.W:
                w = [w[0]] * (self.W - len(w)) + list(w)  # left-pad (causal)
            out[i] = w
        return out

    def _rand_kernels(self, n=40, klen=9, seed=0):
        rng = np.random.default_rng(seed)
        self._rk = [(rng.standard_normal(klen), int(rng.integers(1, 4))) for _ in range(n)]

    def _np_transform(self, W3):
        if self._rk is None:
            self._rand_kernels()
        feats = []
        for w in W3[:, 0, :]:
            row = []
            for k, dil in self._rk:
                kk = np.repeat(k, dil)
                conv = np.convolve(w, kk, mode="valid")
                row += [float(np.max(conv)), float(np.mean(conv > 0))]  # max + PPV
            feats.append(row)
        return np.asarray(feats)

    def _transform(self, X):
        W3 = self._windows(X)[:, None, :]                 # (n, 1, W)
        if self._mr is not None:
            try:
                return np.asarray(self._mr.transform(W3), float)
            except Exception:
                pass
        return self._np_transform(W3)

    def fit(self, X, y):
        W3 = self._windows(X)[:, None, :]
        try:
            from aeon.transformations.collection.convolution_based import MiniRocket
            self._mr = MiniRocket(n_kernels=self.n_kernels, random_state=0)
            self._mr.fit(W3)
        except Exception:
            self._mr = None
            self._rand_kernels()
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        return np.hstack([base, self._transform(X)])


# =========================================================================== #
#  9. NystroemNode (ml) — Nystroem RBF kernel approximation feature map
# =========================================================================== #
class NystroemNode(_HeadBase):
    """sklearn Nystroem RBF kernel approximation fit ONCE on the training rows:
    an explicit low-rank kernel feature map concatenated with X, then the
    task-aware readout. A fast nonlinear layer."""

    kind = "ml"

    def __init__(self, name="nystroem", n_components=80, gamma=None):
        super().__init__(name, "sklearn Nystroem RBF kernel-approximation feature map.", 0)
        self.n_components = n_components
        self.gamma = gamma
        self._map = None
        self._scaler = None

    def fit(self, X, y):
        try:
            from sklearn.kernel_approximation import Nystroem
            from sklearn.preprocessing import StandardScaler
            self._scaler = StandardScaler().fit(X)
            Z = self._scaler.transform(X)
            nc = min(self.n_components, len(X))
            self._map = Nystroem(kernel="rbf", gamma=self.gamma,
                                 n_components=nc, random_state=0)
            self._map.fit(Z)
        except Exception:
            self._map = None
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in row] for row in X], float)
        if self._map is None:
            return base
        feats = self._map.transform(self._scaler.transform(base))
        return np.hstack([base, np.asarray(feats, float)])


# --------------------------------------------------------------------------- #
#  NO-ARG factories
# --------------------------------------------------------------------------- #
def hawkes_node(name="hawkes"): return HawkesNode(name)
def nvar_node(name="nvar"): return NVARNode(name)
def signature_node(name="signature"): return SignatureNode(name)
def edm_node(name="edm"): return EDMNode(name)
def som_node(name="som"): return SOMNode(name)
def elm_node(name="elm"): return ELMNode(name)
def copula_node(name="copula"): return CopulaNode(name)
def rocket_node(name="rocket"): return RocketNode(name)
def nystroem_node(name="nystroem"): return NystroemNode(name)
