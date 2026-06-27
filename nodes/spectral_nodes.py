"""Spectral / manifold / functional / regime nodes (OSS behind NodeProtocol).

Adds a frequency-domain and shape/topology lens to the network: how much of a
window's energy sits in which band, irregular-sampling periodicities, analytic
amplitude/phase, low-dimensional manifold structure of the feature rows, curve
shape via functional PCA, and discrete market/dynamical regimes.

Everything is wrapped in the project's multi-output contract (task in
{binary,multiclass,regression}; ``predict_output`` rows = class-probabilities or
``[value]``) via the ``_HeadBase`` readout pattern copied from quant_nodes. The
window nodes use CAUSAL trailing windows of feature column ``col`` (no
look-ahead). The manifold/regime nodes are FIT ONCE on the training matrix /
series and then APPLIED per row, so there is no per-row model refit (the trap
that makes such nodes slow). Warnings from the scientific libs are suppressed.

Each node = a class + a NO-ARG factory at the bottom.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  Task-aware readout + _HeadBase (copied from nodes/quant_nodes.py)
# --------------------------------------------------------------------------- #
def _readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    est = Ridge() if task == "regression" else LogisticRegression(max_iter=1000)
    return make_pipeline(StandardScaler(), est)


class _HeadBase(BaseNode):
    """Task-aware readout + predict_output. Subclasses provide
    ``_augment(X) -> np.ndarray`` (features per row)."""

    kind = "signal"

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


class _WindowFeat(_HeadBase):
    """Per-row CAUSAL trailing window of column ``col`` -> ``_features(win)``,
    concatenated to the raw feature row. Short/degenerate windows are guarded."""
    NFEAT = 1
    MINLEN = 16

    def _features(self, win: np.ndarray) -> list[float]:
        raise NotImplementedError

    def _augment(self, X: Matrix) -> np.ndarray:
        col = [float(r[self.col]) for r in X]
        rows = []
        for i in range(len(X)):
            w = np.asarray(col[max(0, i - self.W + 1): i + 1], dtype=float)
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                if len(w) >= self.MINLEN and np.ptp(w) > 0:
                    try:
                        f = self._features(w)
                    except Exception:
                        f = [0.0] * self.NFEAT
                else:
                    f = [0.0] * self.NFEAT
            rows.append([float(v) for v in X[i]] + [float(v) for v in f])
        return np.asarray(rows, dtype=float)


# --------------------------------------------------------------------------- #
#  1. SpectralNode (signal) — FFT bands + spectral entropy
# --------------------------------------------------------------------------- #
class SpectralNode(_WindowFeat):
    """scipy.signal periodogram + antropy spectral entropy per window.

    Features: [dominant frequency, power in 3 bands (low/mid/high), spectral
    entropy]. A frequency-domain summary of the trailing window."""
    kind = "signal"
    NFEAT = 5

    def __init__(self, name="spectral", col=0, W=64):
        super().__init__(name, "FFT dominant freq + 3-band power + spectral entropy.", col, W)

    def _features(self, win):
        from scipy.signal import periodogram
        import antropy
        x = win - win.mean()
        freqs, psd = periodogram(x, fs=1.0)
        if len(psd) < 4 or psd.sum() <= 0:
            return [0.0] * self.NFEAT
        dom = float(freqs[int(np.argmax(psd))])
        # split the (positive) spectrum into three contiguous frequency bands
        b = np.array_split(psd, 3)
        tot = psd.sum()
        p_lo, p_mid, p_hi = (float(seg.sum() / tot) for seg in b)
        se = float(antropy.spectral_entropy(win, sf=1.0, method="welch",
                                            normalize=True))
        if not np.isfinite(se):
            se = 0.0
        return [dom, p_lo, p_mid, p_hi, se]


# --------------------------------------------------------------------------- #
#  2. LombScargleNode (signal) — periodogram for irregular sampling
# --------------------------------------------------------------------------- #
class LombScargleNode(_WindowFeat):
    """Lomb-Scargle periodogram per window (handles irregular sampling).

    Uses astropy.timeseries.LombScargle when available, else scipy.signal's
    lombscargle. Features: [peak power, peak frequency, power-weighted mean
    frequency]."""
    kind = "signal"
    NFEAT = 3

    def __init__(self, name="lombscargle", col=0, W=64):
        super().__init__(name, "Lomb-Scargle periodogram peak/centroid (irregular sampling).", col, W)
        self._use_astropy = None

    def _features(self, win):
        n = len(win)
        t = np.arange(n, dtype=float)
        y = win - win.mean()
        fmin, fmax = 1.0 / n, 0.5
        freqs = np.linspace(fmin, fmax, max(16, n // 2))
        if self._use_astropy is None:
            try:
                import astropy.timeseries  # noqa: F401
                self._use_astropy = True
            except Exception:
                self._use_astropy = False
        if self._use_astropy:
            from astropy.timeseries import LombScargle
            power = LombScargle(t, y).power(freqs)
        else:
            ang = 2.0 * np.pi * freqs
            power = __import__("scipy.signal", fromlist=["lombscargle"]).lombscargle(
                t, y, ang, normalize=True)
        power = np.asarray(power, float)
        if power.size == 0 or not np.isfinite(power).any() or power.sum() <= 0:
            return [0.0, 0.0, 0.0]
        peak_p = float(power.max())
        peak_f = float(freqs[int(np.argmax(power))])
        mean_f = float((freqs * power).sum() / power.sum())
        return [peak_p, peak_f, mean_f]


# --------------------------------------------------------------------------- #
#  3. HilbertNode (signal) — analytic signal amplitude/phase
# --------------------------------------------------------------------------- #
class HilbertNode(_WindowFeat):
    """scipy.signal.hilbert analytic signal per window.

    Features: [mean instantaneous amplitude, amplitude std, mean instantaneous
    frequency] (phase-derivative based)."""
    kind = "signal"
    NFEAT = 3

    def __init__(self, name="hilbert", col=0, W=64):
        super().__init__(name, "Hilbert analytic-signal amplitude/phase/inst-freq.", col, W)

    def _features(self, win):
        from scipy.signal import hilbert
        x = win - win.mean()
        a = hilbert(x)
        amp = np.abs(a)
        phase = np.unwrap(np.angle(a))
        inst_freq = np.diff(phase) / (2.0 * np.pi)
        mean_amp = float(amp.mean())
        amp_std = float(amp.std())
        mean_if = float(inst_freq.mean()) if inst_freq.size else 0.0
        return [mean_amp, amp_std, mean_if]


# --------------------------------------------------------------------------- #
#  4. ManifoldNode (ml) — UMAP / KernelPCA embedding of feature rows
# --------------------------------------------------------------------------- #
class ManifoldNode(_HeadBase):
    """Row-level manifold embedding: FIT a UMAP (or KernelPCA fallback) on the
    TRAIN feature-row matrix in ``fit()``, embed to 2-3 dims, then at predict the
    extra features are the embedding coordinates (``transform``). Concatenated
    with X before the readout. Not windowed."""
    kind = "ml"

    def __init__(self, name="manifold", n_components=3):
        super().__init__(name, "UMAP/KernelPCA low-dim manifold embedding of feature rows.")
        self.n_components = n_components
        self._reducer = None
        self._backend = "none"

    def _fit_reducer(self, X):
        M = np.asarray([[float(v) for v in r] for r in X], float)
        nc = min(self.n_components, max(2, M.shape[1] - 1))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                import umap
                nn = max(2, min(15, M.shape[0] - 1))
                self._reducer = umap.UMAP(n_components=nc, n_neighbors=nn,
                                          random_state=0)
                self._reducer.fit(M)
                self._backend = "umap"
                return
            except Exception:
                pass
            try:
                from sklearn.decomposition import KernelPCA
                self._reducer = KernelPCA(n_components=nc, kernel="rbf")
                self._reducer.fit(M)
                self._backend = "kpca"
            except Exception:
                self._reducer = None
                self._backend = "none"

    def _augment(self, X):
        base = np.asarray([[float(v) for v in r] for r in X], float)
        if self._reducer is None:
            return base
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                emb = np.asarray(self._reducer.transform(base), float)
            except Exception:
                return base
        emb = np.nan_to_num(emb, nan=0.0, posinf=0.0, neginf=0.0)
        return np.hstack([base, emb])

    def fit(self, X, y):
        self._fit_reducer(X)
        return super().fit(X, y)


# --------------------------------------------------------------------------- #
#  5. FunctionalDataNode (math) — functional PCA scores per window curve
# --------------------------------------------------------------------------- #
class FunctionalDataNode(_HeadBase):
    """Treat each CAUSAL trailing window as a curve and summarise its SHAPE.

    Primary: scikit-fda FPCA — fit components ONCE on the matrix of training
    window curves, then the per-row features are the FPCA scores of that row's
    window. Robust fallback: polynomial-fit coefficients (degree 2 -> 3 coeffs)
    if the skfda API is unavailable/heavy."""
    kind = "math"
    NCOMP = 3

    def __init__(self, name="functional_fpca", col=0, W=64):
        super().__init__(name, "Functional PCA scores of trailing-window curve (skfda).", col, W)
        self._fpca = None
        self._grid = None
        self._backend = "poly"

    def _windows(self, X) -> np.ndarray:
        """Equal-length trailing windows (front-padded), one per row -> matrix."""
        col = [float(r[self.col]) for r in X]
        W = self.W
        rows = []
        for i in range(len(X)):
            w = col[max(0, i - W + 1): i + 1]
            if len(w) < W:                                  # front-pad short windows
                w = [w[0]] * (W - len(w)) + w if w else [0.0] * W
            rows.append(w)
        return np.asarray(rows, dtype=float)

    def _poly_feats(self, M: np.ndarray) -> np.ndarray:
        t = np.linspace(0.0, 1.0, M.shape[1])
        out = []
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            for w in M:
                try:
                    c = np.polyfit(t, w - w.mean(), 2)
                except Exception:
                    c = np.zeros(3)
                out.append(c[: self.NCOMP])
        return np.nan_to_num(np.asarray(out, float))

    def fit(self, X, y):
        M = self._windows(X)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                from skfda import FDataGrid
                from skfda.preprocessing.dim_reduction import FPCA
                grid = np.linspace(0.0, 1.0, M.shape[1])
                fd = FDataGrid(data_matrix=M, grid_points=grid)
                nc = min(self.NCOMP, M.shape[0] - 1)
                self._fpca = FPCA(n_components=nc)
                self._fpca.fit(fd)
                self._grid = grid
                self._backend = "skfda"
            except Exception:
                self._fpca = None
                self._backend = "poly"
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray([[float(v) for v in r] for r in X], float)
        M = self._windows(X)
        if self._backend == "skfda" and self._fpca is not None:
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                try:
                    from skfda import FDataGrid
                    fd = FDataGrid(data_matrix=M, grid_points=self._grid)
                    feats = np.asarray(self._fpca.transform(fd), float)
                except Exception:
                    feats = self._poly_feats(M)
        else:
            feats = self._poly_feats(M)
        feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
        return np.hstack([base, feats])


# --------------------------------------------------------------------------- #
#  6. RegimeNode (regime) — Markov-switching regime prob + HDBSCAN cluster label
# --------------------------------------------------------------------------- #
class RegimeNode(_HeadBase):
    """Discrete-regime features for each row.

    (a) statsmodels MarkovRegression (2 regimes, switching variance) fit ONCE on
        the training signal series; per-row smoothed regime-probability is then
        obtained for ANY window of rows by re-smoothing the fitted params on that
        row's series (no refit) — robust fallback to a GaussianMixture on the
        signal if MarkovRegression fails.
    (b) HDBSCAN cluster label of the feature rows (approximate_predict so test
        rows are labelled with the train clusterer; -1 = noise).

    The Markov model is fit on the signal column rather than the binary target
    so it is non-degenerate and the regime probability is computable per row from
    X alone (causal, no target leakage at predict time)."""
    kind = "regime"
    KREG = 2

    def __init__(self, name="regime", col=0):
        super().__init__(name, "Markov-switching regime prob + HDBSCAN cluster label.", col)
        self._mk_params = None
        self._gmm = None
        self._clusterer = None
        self._regime_backend = "none"

    def _series(self, X) -> np.ndarray:
        return np.asarray([float(r[self.col]) for r in X], float)

    def _fit_regime(self, X):
        s = self._series(X)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                from statsmodels.tsa.regime_switching.markov_regression import (
                    MarkovRegression)
                res = MarkovRegression(s, k_regimes=self.KREG,
                                       switching_variance=True).fit(disp=False)
                self._mk_params = np.asarray(res.params, float)
                # sanity check: params must re-smooth without error
                _ = MarkovRegression(s, k_regimes=self.KREG,
                                     switching_variance=True).smooth(self._mk_params)
                self._regime_backend = "markov"
                return
            except Exception:
                self._mk_params = None
            try:
                from sklearn.mixture import GaussianMixture
                self._gmm = GaussianMixture(n_components=self.KREG, random_state=0)
                self._gmm.fit(s.reshape(-1, 1))
                self._hi = int(np.argmax(self._gmm.means_.ravel()))
                self._regime_backend = "gmm"
            except Exception:
                self._regime_backend = "none"

    def _regime_prob(self, X) -> np.ndarray:
        s = self._series(X)
        n = len(s)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            if self._regime_backend == "markov" and self._mk_params is not None:
                try:
                    from statsmodels.tsa.regime_switching.markov_regression import (
                        MarkovRegression)
                    sm = MarkovRegression(s, k_regimes=self.KREG,
                                          switching_variance=True).smooth(self._mk_params)
                    return np.asarray(sm.smoothed_marginal_probabilities[:, -1], float)
                except Exception:
                    pass
            if self._regime_backend == "gmm" and self._gmm is not None:
                try:
                    return self._gmm.predict_proba(s.reshape(-1, 1))[:, self._hi]
                except Exception:
                    pass
        return np.full(n, 0.5)

    def _fit_clusters(self, X):
        M = np.asarray([[float(v) for v in r] for r in X], float)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                import hdbscan
                self._clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=max(5, M.shape[0] // 50),
                    prediction_data=True).fit(M)
            except Exception:
                self._clusterer = None

    def _cluster_labels(self, X) -> np.ndarray:
        M = np.asarray([[float(v) for v in r] for r in X], float)
        if self._clusterer is None:
            return np.zeros(M.shape[0])
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                import hdbscan
                labels, _ = hdbscan.approximate_predict(self._clusterer, M)
                return np.asarray(labels, float)
            except Exception:
                return np.zeros(M.shape[0])

    def _augment(self, X):
        base = np.asarray([[float(v) for v in r] for r in X], float)
        prob = self._regime_prob(X).reshape(-1, 1)
        lab = self._cluster_labels(X).reshape(-1, 1)
        return np.hstack([base, np.nan_to_num(prob), np.nan_to_num(lab)])

    def fit(self, X, y):
        self._fit_regime(X)
        self._fit_clusters(X)
        return super().fit(X, y)


# --------------------------------------------------------------------------- #
#  NO-ARG factories
# --------------------------------------------------------------------------- #
def spectral_node(): return SpectralNode()
def lombscargle_node(): return LombScargleNode()
def hilbert_node(): return HilbertNode()
def manifold_node(): return ManifoldNode()
def functional_data_node(): return FunctionalDataNode()
def regime_node(): return RegimeNode()
