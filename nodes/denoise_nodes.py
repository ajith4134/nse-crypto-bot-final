"""Signal-from-noise separation / denoising nodes (behind the project
NodeProtocol, core/node_protocol.py).

Each node treats a chosen column `col` as a 1-D signal, takes a CAUSAL trailing
window of length `W` (signal[max(0,i-W+1) : i+1] — past+present only, never the
future) and DECOMPOSES / DENOISES that window into components, then summarises
the components into a fixed-length feature vector (energy / variance of each
component, residual energy, denoised-vs-raw structure ...). Those features are
concatenated with the raw X row and read out by a task-aware sklearn head
(LogisticRegression for classification, Ridge for regression) — the exact
readout / degenerate-guard / predict_output machinery is inherited unchanged
from nodes.quant_nodes._WindowFeat / _HeadBase (imported, not re-implemented).

Conventions inherited from _WindowFeat: short windows (< 12 samples) -> a
fixed-length zero feature vector; every fragile numeric / optimiser call runs
under suppressed warnings (warnings.simplefilter("ignore") + np.errstate). On
top of that each node here adds a ROBUST per-node try/except: a window whose
decomposition fails yields a zero feature vector, and a node whose fit/predict
fails degrades to a constant (0.5) predictor — so a single flaky library never
breaks the graph. Heavy decompositions amortise work with a `stride` (recompute
the window features every `stride` rows, reuse in between — still causal).

Nodes (kind="signal" unless noted):
  1.  RobustPCANode      — self-implemented Principal Component Pursuit (IALM/PCP)
                           on a Hankel matrix of the window (pure numpy).
  2.  SignalDecompNode   — gfosd signal decomposition (smooth+sparse+residual).
  3.  PicardICANode (ml) — python-picard ICA on a delay-embedding.
  4.  VMDNode            — vmdpy Variational Mode Decomposition (K=3).
  5.  EWTNode            — ewtpy Empirical Wavelet Transform (N=3).
  6.  FastICANode (ml)   — sklearn FastICA on a delay-embedding.
  7.  DictLearnNode (ml) — sklearn MiniBatchDictionaryLearning on patches.
  8.  SVDDenoiseNode     — randomized_svd low-rank denoise of a Hankel matrix.
  9.  SavgolDenoiseNode  — scipy Savitzky-Golay smoothing residuals.
  10. TVWaveletDenoiseNode — skimage TV + wavelet denoising residuals.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import Labels, Matrix, Vector
# COPY (import) the shared task-aware readout bases from the quant module.
from nodes.quant_nodes import _HeadBase, _WindowFeat  # noqa: F401  (_HeadBase re-export)


# --------------------------------------------------------------------------- #
#  Shared denoise base: causal strided window features + robust fallbacks
# --------------------------------------------------------------------------- #
class _DenoiseFeat(_WindowFeat):
    """Causal trailing-window decomposition base.

    Subclasses set NFEAT and implement `_compute(w) -> list[float]` (the window
    decomposition -> feature vector). This base wraps `_compute` in a robust
    try/except (-> zeros on failure, NaN/inf sanitised), amortises expensive
    decompositions with `stride`, and degrades the whole node to a constant
    predictor if fit/predict ever raises. Causal-window semantics, the <12
    short-window zero rule and warning suppression come from _WindowFeat.
    """

    kind = "signal"
    NFEAT = 3

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 64,
                 stride: int = 1):
        super().__init__(name, summary, col=col, W=W)
        self.stride = max(1, int(stride))
        self._broken = False
        self._const = 0.0

    # -- per-window decomposition (subclass) -------------------------------- #
    def _compute(self, w: np.ndarray) -> list[float]:
        raise NotImplementedError

    def _features(self, win) -> list[float]:
        """Robust wrapper: failure -> zeros; output sanitised + length-fixed."""
        try:
            f = list(self._compute(np.asarray(win, dtype=float)))
        except Exception:
            f = [0.0] * self.NFEAT
        f = f[: self.NFEAT] + [0.0] * max(0, self.NFEAT - len(f))
        return [float(v) if np.isfinite(v) else 0.0 for v in f]

    # -- causal + strided design matrix ------------------------------------ #
    def _augment(self, X: Matrix) -> np.ndarray:
        col = [float(r[self.col] if self.col < len(r) else r[0]) for r in X]
        rows: list[list[float]] = []
        last: list[float] | None = None
        cnt = 0
        for i in range(len(X)):
            w = col[max(0, i - self.W + 1): i + 1]
            if last is None or cnt >= self.stride:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    last = self._features(w) if len(w) >= 12 \
                        else [0.0] * self.NFEAT
                cnt = 0
            cnt += 1
            rows.append([float(v) for v in X[i]] + [float(v) for v in last])
        return np.asarray(rows, dtype=float)

    # -- robust NodeProtocol surface --------------------------------------- #
    def fit(self, X: Matrix, y: Labels) -> "_DenoiseFeat":
        self._broken = False
        try:
            return super().fit(X, y)
        except Exception:
            self._broken = True
            ya = np.asarray(y, dtype=float)
            self._const = float(ya.mean()) if len(ya) else 0.0
            return self

    def predict_proba(self, X: Matrix) -> Vector:
        if self._broken:
            return [0.5] * len(X)
        try:
            return super().predict_proba(X)
        except Exception:
            return [0.5] * len(X)

    def predict(self, X: Matrix) -> Labels:
        if self._broken:
            v = self._const
            return [int(round(v))] * len(X) if self.task == "regression" \
                else [1 if v >= 0.5 else 0] * len(X)
        try:
            return super().predict(X)
        except Exception:
            return [0] * len(X)

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self._broken:
            return [[self._const]] * len(X) if self.task == "regression" \
                else [[0.5, 0.5]] * len(X)
        try:
            return super().predict_output(X)
        except Exception:
            return [[self._const]] * len(X) if self.task == "regression" \
                else [[0.5, 0.5]] * len(X)


# --------------------------------------------------------------------------- #
#  small numeric helpers
# --------------------------------------------------------------------------- #
def _energy(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    return float(np.dot(x, x))


def _hankel(w: np.ndarray, rows: int | None = None) -> np.ndarray:
    """Hankel embedding of a 1-D window: H[i, j] = w[i + j]."""
    n = len(w)
    if rows is None:
        rows = max(2, n // 2)
    rows = min(rows, n - 1)
    cols = n - rows + 1
    H = np.empty((rows, cols), dtype=float)
    for i in range(rows):
        H[i] = w[i: i + cols]
    return H


# --------------------------------------------------------------------------- #
#  1. RobustPCANode — Principal Component Pursuit (IALM/PCP), pure numpy
# --------------------------------------------------------------------------- #
class RobustPCANode(_DenoiseFeat):
    """Self-implemented Principal Component Pursuit (low-rank L + sparse S, via
    the inexact augmented Lagrange multiplier method) on a Hankel matrix of the
    causal window. Features = [‖L‖/‖X‖ (signal fraction), ‖S‖/‖X‖ (sparse-noise
    fraction), rank-1 energy of L]. Pure numpy (the `rpca` pip wheel failed)."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 48, stride: int = 2,
                 name: str = "robust_pca"):
        super().__init__(name,
                         "self-implemented PCP/IALM (low-rank+sparse) on a "
                         "Hankel window -> [signal frac, sparse-noise frac, "
                         "rank-1 energy] + X readout.",
                         col=col, W=W, stride=stride)

    @staticmethod
    def _pcp(M: np.ndarray, tol: float = 1e-4, maxit: int = 60):
        m, n = M.shape
        Mn = float(np.linalg.norm(M, "fro"))
        if Mn == 0.0:
            return np.zeros_like(M), np.zeros_like(M)
        lam = 1.0 / np.sqrt(max(m, n))
        norm2 = float(np.linalg.norm(M, 2))
        norm_inf = float(np.linalg.norm(M.ravel(), np.inf)) / lam
        Y = M / max(norm2, norm_inf, 1e-12)
        mu = 1.25 / max(norm2, 1e-12)
        mu_bar, rho = mu * 1e7, 1.5
        L = np.zeros_like(M)
        S = np.zeros_like(M)
        for _ in range(maxit):
            U, s, Vt = np.linalg.svd(M - S + Y / mu, full_matrices=False)
            s = np.maximum(s - 1.0 / mu, 0.0)            # singular-value shrink
            L = (U * s) @ Vt
            T = M - L + Y / mu                            # soft-threshold S
            S = np.sign(T) * np.maximum(np.abs(T) - lam / mu, 0.0)
            Z = M - L - S
            Y = Y + mu * Z
            mu = min(mu * rho, mu_bar)
            if float(np.linalg.norm(Z, "fro")) / Mn < tol:
                break
        return L, S

    def _compute(self, w: np.ndarray) -> list[float]:
        H = _hankel(w)
        nX = float(np.linalg.norm(H, "fro"))
        if nX == 0.0:
            return [0.0, 0.0, 0.0]
        L, S = self._pcp(H)
        sig = float(np.linalg.norm(L, "fro")) / nX
        spn = float(np.linalg.norm(S, "fro")) / nX
        sv = np.linalg.svd(L, compute_uv=False)
        tot = float(np.sum(sv ** 2))
        rank1 = float(sv[0] ** 2 / tot) if tot > 0 and len(sv) else 0.0
        return [sig, spn, rank1]


def robust_pca_node() -> RobustPCANode:
    return RobustPCANode()


# --------------------------------------------------------------------------- #
#  2. SignalDecompNode — gfosd signal decomposition (smooth + sparse + resid)
# --------------------------------------------------------------------------- #
class SignalDecompNode(_DenoiseFeat):
    """gfosd signal decomposition of the window into smooth-trend + sparse +
    residual components; features = [smooth-component energy, sparse-component
    energy, residual energy] (each as a fraction of total energy). Robust numpy
    fallback (deg-2 poly trend + sparse spikes + residual) if gfosd is awkward."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 48, stride: int = 6,
                 name: str = "signal_decomp"):
        super().__init__(name,
                         "gfosd smooth+sparse+residual decomposition -> "
                         "component energy fractions + X readout "
                         "(fallback: poly-trend + spikes + residual).",
                         col=col, W=W, stride=stride)

    @staticmethod
    def _fallback(w: np.ndarray) -> list[float]:
        t = np.arange(len(w), dtype=float)
        trend = np.polyval(np.polyfit(t, w, 2), t)
        resid = w - trend
        sd = float(np.std(resid))
        mask = np.abs(resid) > 2.0 * sd if sd > 0 else np.zeros_like(resid, bool)
        e_total = _energy(w - w.mean()) + 1e-12
        e_smooth = _energy(trend - trend.mean())
        e_sparse = _energy(resid[mask])
        e_resid = _energy(resid[~mask])
        return [e_smooth / e_total, e_sparse / e_total, e_resid / e_total]

    def _compute(self, w: np.ndarray) -> list[float]:
        try:
            from gfosd import Problem
            import gfosd.components as comp
            comps = [comp.SumSquare(weight=1.0),          # 0: residual / noise
                     comp.NoCurvature(),                  # 1: smooth trend
                     comp.SumAbs(weight=1.0)]             # 2: sparse spikes
            p = Problem(np.asarray(w, dtype=float), comps)
            p.decompose()
            d = np.asarray(p.decomposition, dtype=float)
            e_total = float(np.sum(d ** 2)) + 1e-12
            e_resid = _energy(d[0])
            e_smooth = _energy(d[1])
            e_sparse = _energy(d[2])
            return [e_smooth / e_total, e_sparse / e_total, e_resid / e_total]
        except Exception:
            return self._fallback(np.asarray(w, dtype=float))


def signal_decomp_node() -> SignalDecompNode:
    return SignalDecompNode()


# --------------------------------------------------------------------------- #
#  3. PicardICANode (ml) — python-picard ICA on a delay-embedding
# --------------------------------------------------------------------------- #
class PicardICANode(_DenoiseFeat):
    """python-picard ICA run on a small delay-embedding (4 lags) of the window;
    features = [top-component |kurtosis|, top-component energy fraction, mean
    |kurtosis| across components] of the recovered independent sources."""

    kind = "ml"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 4, lags: int = 4,
                 name: str = "picard_ica"):
        super().__init__(name,
                         "python-picard ICA on a 4-lag delay-embedding -> "
                         "[top |kurtosis|, top energy frac, mean |kurtosis|] "
                         "+ X readout.",
                         col=col, W=W, stride=stride)
        self.lags = lags

    @staticmethod
    def _embed(w: np.ndarray, lags: int) -> np.ndarray:
        L = len(w) - lags + 1
        return np.vstack([w[k: k + L] for k in range(lags)])

    @staticmethod
    def _kurt(x: np.ndarray) -> float:
        x = x - x.mean()
        v = float(np.mean(x ** 2))
        if v <= 0:
            return 0.0
        return float(np.mean(x ** 4) / (v ** 2) - 3.0)

    def _sources(self, w: np.ndarray) -> np.ndarray:
        from picard import picard
        E = self._embed(w, self.lags)
        _, _, S = picard(E, n_components=3, max_iter=100, whiten=True,
                         random_state=0)
        return np.asarray(S, dtype=float)

    def _compute(self, w: np.ndarray) -> list[float]:
        S = self._sources(np.asarray(w, dtype=float))
        kurts = np.array([abs(self._kurt(s)) for s in S])
        energies = np.array([_energy(s - s.mean()) for s in S])
        tot = float(energies.sum()) + 1e-12
        top = int(np.argmax(energies))
        return [float(kurts[top]), float(energies[top] / tot),
                float(np.mean(kurts))]


def picard_ica_node() -> PicardICANode:
    return PicardICANode()


# --------------------------------------------------------------------------- #
#  4. VMDNode — vmdpy Variational Mode Decomposition (K=3)
# --------------------------------------------------------------------------- #
class VMDNode(_DenoiseFeat):
    """vmdpy Variational Mode Decomposition of the window into K=3 band-limited
    modes; features = the energy fraction carried by each of the 3 modes."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 4,
                 name: str = "vmd"):
        super().__init__(name,
                         "vmdpy VMD(K=3) of the window -> per-mode energy "
                         "fractions + X readout.",
                         col=col, W=W, stride=stride)

    def _compute(self, w: np.ndarray) -> list[float]:
        from vmdpy import VMD
        x = np.asarray(w, dtype=float)
        if len(x) % 2:                                    # VMD prefers even len
            x = x[1:]
        u, _, _ = VMD(x, alpha=2000.0, tau=0.0, K=3, DC=0, init=1, tol=1e-7)
        energies = np.array([_energy(m) for m in u])
        tot = float(energies.sum()) + 1e-12
        return [float(e / tot) for e in energies[:3]]


def vmd_node() -> VMDNode:
    return VMDNode()


# --------------------------------------------------------------------------- #
#  5. EWTNode — ewtpy Empirical Wavelet Transform (N=3)
# --------------------------------------------------------------------------- #
class EWTNode(_DenoiseFeat):
    """ewtpy Empirical Wavelet Transform extracting N=3 adaptive modes from the
    window; features = the energy fraction carried by each of the 3 modes."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 2,
                 name: str = "ewt"):
        super().__init__(name,
                         "ewtpy EWT1D(N=3) of the window -> per-mode energy "
                         "fractions + X readout.",
                         col=col, W=W, stride=stride)

    def _compute(self, w: np.ndarray) -> list[float]:
        import ewtpy
        ewt, _, _ = ewtpy.EWT1D(np.asarray(w, dtype=float), N=3)
        ewt = np.asarray(ewt, dtype=float)               # (T, n_modes)
        energies = np.array([_energy(ewt[:, j])
                             for j in range(ewt.shape[1])])
        tot = float(energies.sum()) + 1e-12
        out = [float(e / tot) for e in energies[:3]]
        return out + [0.0] * (3 - len(out))


def ewt_node() -> EWTNode:
    return EWTNode()


# --------------------------------------------------------------------------- #
#  6. FastICANode (ml) — sklearn FastICA on a delay-embedding
# --------------------------------------------------------------------------- #
class FastICANode(_DenoiseFeat):
    """sklearn FastICA on a small delay-embedding (4 lags) of the window;
    features = the energy fraction carried by each of the 3 independent
    components."""

    kind = "ml"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 2, lags: int = 4,
                 name: str = "fast_ica"):
        super().__init__(name,
                         "sklearn FastICA on a 4-lag delay-embedding -> "
                         "per-component energy fractions + X readout.",
                         col=col, W=W, stride=stride)
        self.lags = lags

    def _compute(self, w: np.ndarray) -> list[float]:
        from sklearn.decomposition import FastICA
        x = np.asarray(w, dtype=float)
        L = len(x) - self.lags + 1
        E = np.vstack([x[k: k + L] for k in range(self.lags)]).T   # (L, lags)
        S = FastICA(n_components=3, max_iter=200, random_state=0,
                    whiten="unit-variance").fit_transform(E)       # (L, 3)
        energies = np.array([_energy(S[:, j] - S[:, j].mean())
                             for j in range(S.shape[1])])
        tot = float(energies.sum()) + 1e-12
        out = [float(e / tot) for e in energies[:3]]
        return out + [0.0] * (3 - len(out))


def fast_ica_node() -> FastICANode:
    return FastICANode()


# --------------------------------------------------------------------------- #
#  7. DictLearnNode (ml) — sklearn MiniBatchDictionaryLearning on patches
# --------------------------------------------------------------------------- #
class DictLearnNode(_DenoiseFeat):
    """sklearn MiniBatchDictionaryLearning learns a sparse dictionary over
    sliding patches of the window; features = [mean |sparse code|, mean fraction
    of active atoms per patch, mean L1 sparse-code norm per patch] — i.e. how
    sparsely the window is explained by learned signal atoms."""

    kind = "ml"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 48, stride: int = 6, patch: int = 8,
                 name: str = "dict_learn"):
        super().__init__(name,
                         "sklearn MiniBatchDictionaryLearning over window "
                         "patches -> mean sparse-code activation features "
                         "+ X readout.",
                         col=col, W=W, stride=stride)
        self.patch = patch

    def _compute(self, w: np.ndarray) -> list[float]:
        from sklearn.decomposition import MiniBatchDictionaryLearning
        x = np.asarray(w, dtype=float)
        p = self.patch
        n = len(x) - p + 1
        if n < 4:
            return [0.0, 0.0, 0.0]
        P = np.vstack([x[i: i + p] for i in range(n)])
        P = P - P.mean(axis=1, keepdims=True)
        dl = MiniBatchDictionaryLearning(
            n_components=6, alpha=1.0, max_iter=8, batch_size=8,
            transform_algorithm="omp", random_state=0)
        codes = dl.fit_transform(P)                       # (n_patches, 6)
        mean_abs = float(np.mean(np.abs(codes)))
        frac_active = float(np.mean(np.abs(codes) > 1e-6))
        l1_per_patch = float(np.mean(np.sum(np.abs(codes), axis=1)))
        return [mean_abs, frac_active, l1_per_patch]


def dict_learn_node() -> DictLearnNode:
    return DictLearnNode()


# --------------------------------------------------------------------------- #
#  8. SVDDenoiseNode — randomized_svd low-rank denoise of a Hankel matrix
# --------------------------------------------------------------------------- #
class SVDDenoiseNode(_DenoiseFeat):
    """randomized_svd on a Hankel matrix of the window, keeping the top-k=3
    singular components as the 'clean' signal; features = [explained-variance
    ratio of the top-3 components, explained-variance ratio of the top-1
    component, residual (noise) energy fraction after the rank-3 reconstruction]."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 1, k: int = 3,
                 name: str = "svd_denoise"):
        super().__init__(name,
                         "randomized_svd low-rank (k=3) denoise of a Hankel "
                         "window -> [evr top-3, evr top-1, residual energy "
                         "frac] + X readout.",
                         col=col, W=W, stride=stride)
        self.k = k

    def _compute(self, w: np.ndarray) -> list[float]:
        from sklearn.utils.extmath import randomized_svd
        H = _hankel(w)
        H = H - H.mean()
        tot = _energy(H) + 1e-12
        k = min(self.k, min(H.shape) - 1)
        if k < 1:
            return [0.0, 0.0, 0.0]
        U, s, Vt = randomized_svd(H, n_components=k, random_state=0)
        sv_full = np.linalg.svd(H, compute_uv=False)
        ssum = float(np.sum(sv_full ** 2)) + 1e-12
        evr_top3 = float(np.sum(s[:3] ** 2) / ssum)
        evr_top1 = float(s[0] ** 2 / ssum)
        recon = (U * s) @ Vt
        resid_frac = _energy(H - recon) / tot
        return [evr_top3, evr_top1, resid_frac]


def svd_denoise_node() -> SVDDenoiseNode:
    return SVDDenoiseNode()


# --------------------------------------------------------------------------- #
#  9. SavgolDenoiseNode — scipy Savitzky-Golay smoothing residuals
# --------------------------------------------------------------------------- #
class SavgolDenoiseNode(_DenoiseFeat):
    """scipy.signal.savgol_filter smooths the window; features = [residual std
    (estimated noise level), slope of the smoothed signal (1st derivative at the
    window end), curvature of the smoothed signal (2nd derivative at the end)]."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 48, stride: int = 1,
                 name: str = "savgol_denoise"):
        super().__init__(name,
                         "scipy Savitzky-Golay smoothing -> [residual std "
                         "(noise level), smoothed slope, smoothed curvature] "
                         "+ X readout.",
                         col=col, W=W, stride=stride)

    def _compute(self, w: np.ndarray) -> list[float]:
        from scipy.signal import savgol_filter
        x = np.asarray(w, dtype=float)
        win = min(len(x) if len(x) % 2 else len(x) - 1, 11)
        if win < 5:
            win = 5
        if win > len(x):
            return [0.0, 0.0, 0.0]
        sm = savgol_filter(x, win, polyorder=3)
        resid_std = float(np.std(x - sm))
        d1 = np.gradient(sm)
        d2 = np.gradient(d1)
        return [resid_std, float(d1[-1]), float(d2[-1])]


def savgol_denoise_node() -> SavgolDenoiseNode:
    return SavgolDenoiseNode()


# --------------------------------------------------------------------------- #
#  10. TVWaveletDenoiseNode — skimage TV + wavelet denoising residuals
# --------------------------------------------------------------------------- #
class TVWaveletDenoiseNode(_DenoiseFeat):
    """skimage.restoration TV (denoise_tv_chambolle) and wavelet
    (denoise_wavelet) denoising of the window; features = [TV-denoise residual
    energy fraction, wavelet-denoise residual energy fraction, estimated noise
    level (estimate_sigma)]."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, col: int = 0, W: int = 64, stride: int = 1,
                 name: str = "tv_wavelet_denoise"):
        super().__init__(name,
                         "skimage TV + wavelet denoising -> [TV residual frac, "
                         "wavelet residual frac, noise-level sigma] + X readout.",
                         col=col, W=W, stride=stride)

    def _compute(self, w: np.ndarray) -> list[float]:
        from skimage.restoration import (denoise_tv_chambolle,
                                         denoise_wavelet, estimate_sigma)
        x = np.asarray(w, dtype=float)
        rng = float(x.max() - x.min())
        xn = (x - x.min()) / rng if rng > 0 else x * 0.0  # normalise to [0,1]
        tot = _energy(xn - xn.mean()) + 1e-12
        tv = denoise_tv_chambolle(xn, weight=0.1)
        wv = denoise_wavelet(xn, rescale_sigma=True)
        tv_frac = _energy(xn - tv) / tot
        wv_frac = _energy(xn - wv) / tot
        try:
            sigma = float(estimate_sigma(xn))
        except Exception:
            sigma = float(np.std(xn - wv))
        return [tv_frac, wv_frac, sigma]


def tv_wavelet_denoise_node() -> TVWaveletDenoiseNode:
    return TVWaveletDenoiseNode()
