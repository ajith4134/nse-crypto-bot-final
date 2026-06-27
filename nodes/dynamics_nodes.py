"""Nonlinear-dynamics / chaos / physics nodes — the reuse-first dynamics layer.

Each class wraps a mature OSS dynamical-systems / chaos library behind the SAME
`NodeProtocol` the rest of the network speaks (fit / predict_proba / predict /
predict_output over Matrix / Labels), exactly mirroring `nodes/oss_nodes.py`
(SklearnNode + SklearnRegressorNode): the readout is chosen by `self.task`
(LogisticRegression(max_iter=1000) for classification, Ridge() for regression),
predict_output returns per-class [p0, p1] rows for classification and length-1
[value] rows for regression.

Wrapped libraries:
  - pysindy    SINDyNode            (physics)  equation-discovery / next-step predictor
  - pyunicorn  RQANode              (chaos)    recurrence-quantification measures
  - ordpy      PermEntropyNode      (chaos)    permutation entropy + complexity
  - antropy    AntropyNode          (chaos)    entropy + fractal-dimension features
  - pydmd      DMDNode              (physics)  dynamic-mode-decomposition features
  - pyinform   TransferEntropyNode  (chaos)    directional transfer entropy

UNIFORM PATTERN: X is feature ROWS. A 1-D signal is derived from one feature
column (`self.col`); for each row i a CAUSAL trailing window of width `self.W`
ending at i (NO look-ahead) feeds `_features(win) -> list[float]`. The features
are concatenated onto the raw row and fed to a standardized linear readout. All
heavy computation is wrapped in warnings.catch_warnings + np.errstate(all=...)
and is robust to short windows (len < 10 -> fixed-length zeros).
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  Shared causal-window base (fit / predict_proba / predict / predict_output
#  implemented ONCE, task-aware, copying the oss_nodes readout style).
# --------------------------------------------------------------------------- #
class _Base(BaseNode):
    """Derive a 1-D signal from feature column `col`, build a causal trailing
    window of width `W` per row, turn the window into extra features via the
    subclass `_features`, and classify/regress with a standardized linear
    readout. The default task is binary; set `node.task = "regression"` (and the
    appropriate `head`) before fit() to serve the regression head."""

    kind = "chaos"
    _NFEAT = 0                       # subclasses set this (fixed feature width)

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 80):
        self.name = name
        self.summary = summary
        self.kind = type(self).kind
        self.col = col
        self.W = W
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "features", "out")
        self._classes: list[int] = []
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0

    # -- subclass hook ------------------------------------------------------- #
    def _features(self, win: np.ndarray) -> list[float]:
        raise NotImplementedError

    def _safe_features(self, win: np.ndarray) -> list[float]:
        if len(win) < 10:
            return [0.0] * self._NFEAT
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                f = self._features(np.asarray(win, dtype=float))
            except Exception:
                f = [0.0] * self._NFEAT
        f = [float(v) if np.isfinite(v) else 0.0 for v in f]
        if len(f) < self._NFEAT:                          # pad / clip to fixed width
            f = f + [0.0] * (self._NFEAT - len(f))
        return f[: self._NFEAT]

    def _augment(self, X: Matrix) -> np.ndarray:
        c = [float(r[self.col]) for r in X]
        out: list[list[float]] = []
        for i in range(len(X)):
            w = c[max(0, i - self.W + 1): i + 1]
            out.append(list(map(float, X[i])) + self._safe_features(np.asarray(w)))
        return np.asarray(out, dtype=float)

    # -- readout (task-aware, copying oss_nodes) ----------------------------- #
    def _readout(self):
        from sklearn.linear_model import LogisticRegression, Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        head = Ridge() if self.task == "regression" else LogisticRegression(max_iter=1000)
        return make_pipeline(StandardScaler(), head)

    # -- NodeProtocol -------------------------------------------------------- #
    def fit(self, X: Matrix, y: Labels) -> "_Base":
        Xa = self._augment(X)
        d = Xa.shape[1]
        if self.task == "regression":
            ya = np.asarray(y, dtype=float)
            self.schema = IOSchema(d, f"{d} numeric features", "predicted value")
            self._ymin = float(ya.min()) if len(ya) else 0.0
            self._ymax = float(ya.max()) if len(ya) else 1.0
            if self._ymax <= self._ymin:                  # degenerate constant target
                self._constant = float(ya[0]) if len(ya) else 0.0
                return self
            self._constant = None
            self._est = self._readout()
            self._est.fit(Xa, ya)
            return self
        ya = np.asarray(y, dtype=int)
        self.schema = IOSchema(d, f"{d} numeric features", "p(class=1)")
        self._classes = sorted(set(int(v) for v in ya))
        if len(self._classes) < 2:                        # only one class present
            return self
        self._est = self._readout()
        self._est.fit(Xa, ya)
        return self

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            if self._constant is not None:
                return [self._constant] * len(X)
            return [float(v) for v in self._est.predict(self._augment(X))]
        return super().predict(X)                         # binary: threshold proba

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":                     # monotone confidence proxy
            vals = self.predict(X)
            span = self._ymax - self._ymin
            if span <= 0.0:
                return [0.5] * len(vals)
            return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._est.predict_proba(self._augment(X))
        cols = list(self._est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            return [[v] for v in self.predict(X)]
        return [[1.0 - p, p] for p in self.predict_proba(X)]   # [p0, p1]


# --------------------------------------------------------------------------- #
#  1. SINDyNode — pysindy equation discovery / next-step predictor (physics)
# --------------------------------------------------------------------------- #
class SINDyNode(_Base):
    """Sparse Identification of Nonlinear Dynamics (pysindy).

    Treats the chosen column as a 1-D discrete dynamical system x(t) -> x(t+1)
    and, in fit(), discovers a sparse governing equation on the TRAILING TRAIN
    series (stored as `self.equation_`). predict_output: for each row it predicts
    the next-step value from the window's last state; the predicted next-step
    DELTA (x_next - x_now) is the working signal -> for the classification head a
    logistic readout maps it (and the window features) to class probabilities;
    for the regression head the predicted next value is returned directly.

    Robust: any pysindy failure falls back to a Ridge over window statistics
    (mean / std / last / slope / range), so the node always trains and predicts.
    """

    kind = "physics"
    _NFEAT = 6                       # [pred_next, pred_delta, mean, std, slope, range]

    def __init__(self, name: str = "sindy", summary: str | None = None,
                 col: int = 0, W: int = 120):
        super().__init__(
            name,
            summary or "pysindy sparse equation discovery; next-step x(t)->x(t+1) predictor.",
            col=col, W=W)
        self.equation_: str = "(unfit)"
        self._model = None

    @staticmethod
    def _winstats(w: np.ndarray) -> list[float]:
        n = len(w)
        slope = float(np.polyfit(np.arange(n), w, 1)[0]) if n >= 2 else 0.0
        return [float(np.mean(w)), float(np.std(w)), slope, float(w.max() - w.min())]

    def _predict_next(self, w: np.ndarray) -> float:
        """Predict the next value after the window's last state."""
        last = float(w[-1])
        if self._model is not None:
            try:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    nxt = self._model.predict(np.asarray([[last]], dtype=float))
                v = float(np.asarray(nxt).reshape(-1)[0])
                if np.isfinite(v):
                    return v
            except Exception:
                pass
        return last                                       # fallback: persistence

    def _features(self, win: np.ndarray) -> list[float]:
        nxt = self._predict_next(win)
        delta = nxt - float(win[-1])
        return [nxt, delta] + self._winstats(win)

    def fit(self, X: Matrix, y: Labels) -> "SINDyNode":
        # Discover the governing equation on the trailing train series of `col`.
        series = np.asarray([float(r[self.col]) for r in X], dtype=float)
        self._model = None
        self.equation_ = "(fallback: pysindy unavailable / failed)"
        if len(series) >= 20:
            try:
                import pysindy as ps
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    model = ps.DiscreteSINDy(            # pysindy 2.x discrete map x[k]->x[k+1]
                        optimizer=ps.STLSQ(threshold=0.01),
                        feature_library=ps.PolynomialLibrary(degree=3))
                    model.fit(series.reshape(-1, 1), t=1, feature_names=["x"])
                    eqs = model.equations(precision=4)
                self._model = model
                self.equation_ = "x[k+1] = " + (eqs[0] if eqs else "0")
            except Exception as exc:                      # stay robust -> Ridge fallback
                self._model = None
                self.equation_ = f"(fallback: SINDy failed: {type(exc).__name__})"
        return super().fit(X, y)


def sindy_node(name: str = "sindy", col: int = 0, W: int = 120) -> SINDyNode:
    return SINDyNode(name=name, col=col, W=W)


# --------------------------------------------------------------------------- #
#  2. RQANode — pyunicorn recurrence quantification analysis (chaos)
# --------------------------------------------------------------------------- #
class RQANode(_Base):
    """Recurrence Quantification Analysis (pyunicorn RecurrencePlot).

    Per causal window builds a recurrence plot at a FIXED recurrence rate and
    extracts [determinism, laminarity, recurrence_rate, diagonal_entropy], which
    quantify how deterministic / laminar / structured the local dynamics are.
    """

    kind = "chaos"
    _NFEAT = 4                       # [determinism, laminarity, recurrence_rate, diag_entropy]

    def __init__(self, name: str = "rqa", summary: str | None = None,
                 col: int = 0, W: int = 80, rr: float = 0.1, dim: int = 3, tau: int = 1):
        super().__init__(
            name,
            summary or "pyunicorn RQA features (determinism, laminarity, RR, diagonal entropy).",
            col=col, W=W)
        self.rr, self.dim, self.tau = rr, dim, tau

    def _features(self, win: np.ndarray) -> list[float]:
        import contextlib
        import io

        from pyunicorn.timeseries import RecurrencePlot
        with contextlib.redirect_stdout(io.StringIO()):
            rp = RecurrencePlot(win, recurrence_rate=self.rr, dim=self.dim,
                                tau=self.tau, silence_level=3)
            det = rp.determinism()
            lam = rp.laminarity()
            rate = rp.recurrence_rate()
            ent = rp.diag_entropy()
        return [det, lam, rate, ent]


def rqa_node(name: str = "rqa", col: int = 0, W: int = 80) -> RQANode:
    return RQANode(name=name, col=col, W=W)


# --------------------------------------------------------------------------- #
#  3. PermEntropyNode — ordpy permutation entropy + complexity (chaos)
# --------------------------------------------------------------------------- #
class PermEntropyNode(_Base):
    """Ordinal-pattern complexity (ordpy).

    Per causal window: [permutation_entropy, statistical_complexity] — the
    complexity-entropy plane coordinates that separate stochastic from chaotic
    dynamics.
    """

    kind = "chaos"
    _NFEAT = 2                       # [perm_entropy, statistical_complexity]

    def __init__(self, name: str = "permentropy", summary: str | None = None,
                 col: int = 0, W: int = 80, dx: int = 3):
        super().__init__(
            name,
            summary or "ordpy permutation entropy + statistical complexity (complexity-entropy plane).",
            col=col, W=W)
        self.dx = dx

    def _features(self, win: np.ndarray) -> list[float]:
        import ordpy
        pe = float(ordpy.permutation_entropy(win, dx=self.dx, normalized=True))
        _h, c = ordpy.complexity_entropy(win, dx=self.dx)
        return [pe, float(c)]


def permentropy_node(name: str = "permentropy", col: int = 0, W: int = 80) -> PermEntropyNode:
    return PermEntropyNode(name=name, col=col, W=W)


# --------------------------------------------------------------------------- #
#  4. AntropyNode — antropy entropy + fractal-dimension features (chaos)
# --------------------------------------------------------------------------- #
class AntropyNode(_Base):
    """Entropy / fractal-dimension features (antropy).

    Per causal window: [perm_entropy, spectral_entropy(sf=1), sample_entropy,
    higuchi_fd, detrended_fluctuation] — a compact regularity + self-similarity
    fingerprint of the local signal.
    """

    kind = "chaos"
    _NFEAT = 5

    def __init__(self, name: str = "antropy", summary: str | None = None,
                 col: int = 0, W: int = 80):
        super().__init__(
            name,
            summary or "antropy features (perm/spectral/sample entropy, Higuchi FD, DFA).",
            col=col, W=W)

    def _features(self, win: np.ndarray) -> list[float]:
        import antropy as ant
        return [
            float(ant.perm_entropy(win, normalize=True)),
            float(ant.spectral_entropy(win, sf=1, normalize=True)),
            float(ant.sample_entropy(win)),
            float(ant.higuchi_fd(win)),
            float(ant.detrended_fluctuation(win)),
        ]


def antropy_node(name: str = "antropy", col: int = 0, W: int = 80) -> AntropyNode:
    return AntropyNode(name=name, col=col, W=W)


# --------------------------------------------------------------------------- #
#  5. DMDNode — pydmd dynamic mode decomposition (physics)
# --------------------------------------------------------------------------- #
class DMDNode(_Base):
    """Dynamic Mode Decomposition (pydmd).

    Per causal window builds a Hankel (time-delay) embedding and fits a DMD
    model; features = [dominant eigenvalue modulus, growth rate (log|eig|),
    one-step reconstruction error] — the local linear-operator spectrum and how
    well it explains the window.
    """

    kind = "physics"
    _NFEAT = 3                       # [dominant |eig|, growth rate, reconstruction error]

    def __init__(self, name: str = "dmd", summary: str | None = None,
                 col: int = 0, W: int = 80, delay: int = 10, rank: int = 4):
        super().__init__(
            name,
            summary or "pydmd dynamic mode decomposition (dominant eigenvalue, growth rate, recon error).",
            col=col, W=W)
        self.delay, self.rank = delay, rank

    def _features(self, win: np.ndarray) -> list[float]:
        from pydmd import DMD
        d = min(self.delay, max(2, len(win) // 2))
        m = len(win) - d + 1
        if m < 2:
            return [0.0, 0.0, 0.0]
        H = np.asarray([win[i: i + d] for i in range(m)], dtype=float).T  # (delay, snapshots)
        dmd = DMD(svd_rank=self.rank)
        dmd.fit(H)
        eigs = np.asarray(dmd.eigs)
        if eigs.size == 0:
            return [0.0, 0.0, 0.0]
        dom = eigs[int(np.argmax(np.abs(eigs)))]
        mod = float(np.abs(dom))
        growth = float(np.log(mod)) if mod > 0 else 0.0
        recon = dmd.reconstructed_data.real
        err = float(np.sqrt(np.mean((H - recon) ** 2))) if recon.shape == H.shape else 0.0
        return [mod, growth, err]


def dmd_node(name: str = "dmd", col: int = 0, W: int = 80) -> DMDNode:
    return DMDNode(name=name, col=col, W=W)


# --------------------------------------------------------------------------- #
#  6. TransferEntropyNode — pyinform directional information flow (chaos)
# --------------------------------------------------------------------------- #
class TransferEntropyNode(_Base):
    """Directional information transfer between two feature columns (pyinform).

    Per causal window: discretizes columns `col` (x) and `col2` (y) into `bins`
    bins and computes transfer entropy in both directions; features =
    [TE(x->y), TE(y->x)] — net directional coupling of the two signals.
    """

    kind = "chaos"
    _NFEAT = 2                       # [te_xy, te_yx]

    def __init__(self, name: str = "transfer_entropy", summary: str | None = None,
                 col: int = 0, col2: int = 1, W: int = 80, bins: int = 3, k: int = 1):
        super().__init__(
            name,
            summary or "pyinform transfer entropy between two feature columns (both directions).",
            col=col, W=W)
        self.col2, self.bins, self.k = col2, bins, k

    @staticmethod
    def _discretize(v: np.ndarray, bins: int) -> np.ndarray:
        v = np.asarray(v, dtype=float)
        lo, hi = float(v.min()), float(v.max())
        if hi <= lo:
            return np.zeros(len(v), dtype=int)
        idx = np.floor((v - lo) / (hi - lo) * bins).astype(int)
        return np.clip(idx, 0, bins - 1)

    def _augment(self, X: Matrix) -> np.ndarray:
        # Override: this node needs TWO columns per window (x and y).
        c1 = [float(r[self.col]) for r in X]
        c2 = [float(r[self.col2]) for r in X]
        out: list[list[float]] = []
        for i in range(len(X)):
            lo = max(0, i - self.W + 1)
            wx = np.asarray(c1[lo: i + 1])
            wy = np.asarray(c2[lo: i + 1])
            out.append(list(map(float, X[i])) + self._te_features(wx, wy))
        return np.asarray(out, dtype=float)

    def _te_features(self, wx: np.ndarray, wy: np.ndarray) -> list[float]:
        if len(wx) < 10:
            return [0.0, 0.0]
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                from pyinform import transfer_entropy
                xs = self._discretize(wx, self.bins)
                ys = self._discretize(wy, self.bins)
                te_xy = float(transfer_entropy(xs, ys, k=self.k))   # x -> y
                te_yx = float(transfer_entropy(ys, xs, k=self.k))   # y -> x
            except Exception:
                return [0.0, 0.0]
        return [te_xy if np.isfinite(te_xy) else 0.0,
                te_yx if np.isfinite(te_yx) else 0.0]

    def _features(self, win: np.ndarray) -> list[float]:    # unused (see _augment)
        return [0.0, 0.0]


def transfer_entropy_node(name: str = "transfer_entropy", col: int = 0,
                          col2: int = 1, W: int = 80) -> TransferEntropyNode:
    return TransferEntropyNode(name=name, col=col, col2=col2, W=W)
