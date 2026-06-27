"""Feature-extractor nodes wrapping established GitHub/OSS projects.

Each node wraps a third-party feature library (TA-Lib, NeuroKit2, librosa,
EntropyHub, tsfel) — or a pure-numpy re-implementation where the upstream lib
would not build (FracDiff) — behind the project NodeProtocol and the multi-output
contract (task in {binary, multiclass, regression}; predict_output rows = class
probabilities or [value]).

Mechanics are REUSED from nodes/quant_nodes: `_HeadBase` provides the task-aware
readout (LogisticRegression cls / Ridge reg) + predict_output, and `_WindowFeat`
turns a per-window feature function into a per-row augmented design matrix using
CAUSAL trailing windows of feature column `col` (no look-ahead). Short windows
(< 12) emit a fixed-length zero vector; library warnings are suppressed and any
NaN/inf collapses to 0 so degenerate windows never poison the readout.
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import Matrix
from nodes.quant_nodes import _HeadBase, _WindowFeat  # reuse-first: shared mechanics

__all__ = [
    "TALibNode", "NeuroKit2Node", "LibrosaNode", "EntropyHubNode",
    "TSFELNode", "FracDiffNode",
    "talib_node", "neurokit2_node", "librosa_node", "entropyhub_node",
    "tsfel_node", "fracdiff_node",
]


def _clean(vals, n: int) -> list[float]:
    """Coerce a feature list to exactly `n` finite floats (NaN/inf -> 0)."""
    out = []
    for v in list(vals)[:n]:
        f = float(v)
        out.append(f if np.isfinite(f) else 0.0)
    out += [0.0] * (n - len(out))
    return out


def _last_finite(arr) -> float:
    """Last finite element of a TA-Lib-style array (trailing NaNs warmup)."""
    a = np.asarray(arr, float)
    a = a[np.isfinite(a)]
    return float(a[-1]) if a.size else 0.0


# --------------------------------------------------------------------------- #
# 1. TA-Lib — classic technical indicators on the window as a price series
# --------------------------------------------------------------------------- #
class TALibNode(_WindowFeat):
    """TA-Lib indicators computed on the trailing window treated as a price-like
    series: RSI(14), MOM(10), ROC(10), STDDEV(10) and the linear-regression
    slope. Close-only indicators (no synthetic OHLC needed)."""
    kind = "signal"
    NFEAT = 5

    def __init__(self, name="talib_feats", col=0, W=64):
        super().__init__(name, "TA-Lib RSI/MOM/ROC/STDDEV/lin-reg-slope window features.", col, W)

    def _features(self, win):
        import talib
        a = np.asarray(win, float)
        return _clean([
            _last_finite(talib.RSI(a, timeperiod=14)),
            _last_finite(talib.MOM(a, timeperiod=10)),
            _last_finite(talib.ROC(a, timeperiod=10)),
            _last_finite(talib.STDDEV(a, timeperiod=10)),
            _last_finite(talib.LINEARREG_SLOPE(a, timeperiod=10)),
        ], self.NFEAT)


# --------------------------------------------------------------------------- #
# 2. NeuroKit2 — nonlinear / complexity features
# --------------------------------------------------------------------------- #
class NeuroKit2Node(_WindowFeat):
    """NeuroKit2 nonlinear-dynamics features per window: sample entropy,
    approximate entropy and Higuchi fractal dimension (functional API). These
    can fail on short/constant windows, so every call is guarded."""
    kind = "chaos"
    NFEAT = 3

    def __init__(self, name="neurokit2_feats", col=0, W=64):
        super().__init__(name, "NeuroKit2 SampEn/ApEn/Higuchi-FD complexity features.", col, W)

    @staticmethod
    def _scalar(res) -> float:
        # nk functions return (value, info_dict)
        v = res[0] if isinstance(res, tuple) else res
        return float(np.asarray(v).ravel()[0])

    def _features(self, win):
        import neurokit2 as nk
        a = np.asarray(win, float)
        feats = []
        for fn in (nk.entropy_sample, nk.entropy_approximate, nk.fractal_higuchi):
            try:
                feats.append(self._scalar(fn(a)))
            except Exception:
                feats.append(0.0)
        return _clean(feats, self.NFEAT)


# --------------------------------------------------------------------------- #
# 3. librosa — spectral features (treat the window as audio, sr=1)
# --------------------------------------------------------------------------- #
class LibrosaNode(_WindowFeat):
    """librosa spectral features of the window read as an audio signal (sr=1):
    mean spectral centroid, bandwidth, roll-off and zero-crossing rate."""
    kind = "signal"
    NFEAT = 4

    def __init__(self, name="librosa_feats", col=0, W=64):
        super().__init__(name, "librosa spectral centroid/bandwidth/rolloff/ZCR window features.", col, W)

    def _features(self, win):
        import librosa
        y = np.asarray(win, float).astype(np.float32)
        try:
            centroid = librosa.feature.spectral_centroid(y=y, sr=1).mean()
            bw = librosa.feature.spectral_bandwidth(y=y, sr=1).mean()
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=1).mean()
            zcr = librosa.feature.zero_crossing_rate(y=y).mean()
        except Exception:
            return [0.0] * self.NFEAT
        return _clean([centroid, bw, rolloff, zcr], self.NFEAT)


# --------------------------------------------------------------------------- #
# 4. EntropyHub — several entropy measures
# --------------------------------------------------------------------------- #
class EntropyHubNode(_WindowFeat):
    """EntropyHub entropies per window: sample entropy, permutation entropy and
    dispersion entropy. EntropyHub returns arrays across embedding dimensions —
    take the final (highest-m) scalar of each."""
    kind = "chaos"
    NFEAT = 3

    def __init__(self, name="entropyhub_feats", col=0, W=64):
        super().__init__(name, "EntropyHub SampEn/PermEn/DispEn window features.", col, W)

    @staticmethod
    def _final(x) -> float:
        a = np.asarray(x, float).ravel()
        a = a[np.isfinite(a)]
        return float(a[-1]) if a.size else 0.0

    def _features(self, win):
        import EntropyHub as EH
        a = np.asarray(win, float)
        feats = []
        try:
            feats.append(self._final(EH.SampEn(a, m=2)[0]))
        except Exception:
            feats.append(0.0)
        try:
            feats.append(self._final(EH.PermEn(a, m=3)[0]))
        except Exception:
            feats.append(0.0)
        try:
            feats.append(self._final(EH.DispEn(a, m=2, c=4)[0]))
        except Exception:
            feats.append(0.0)
        return _clean(feats, self.NFEAT)


# --------------------------------------------------------------------------- #
# 5. tsfel — small curated set of cheap features (avoid slow full config)
# --------------------------------------------------------------------------- #
class TSFELNode(_WindowFeat):
    """tsfel features per window, calling the feature functions directly for a
    SMALL curated, cheap set (avoids the slow full-config extractor):
    abs_energy, spectral_centroid, fundamental_frequency, entropy, slope,
    mean_abs_diff."""
    kind = "ml"
    NFEAT = 6

    def __init__(self, name="tsfel_feats", col=0, W=64):
        super().__init__(name, "tsfel curated cheap window features (energy/spectral/entropy/slope).", col, W)

    def _features(self, win):
        import tsfel.feature_extraction.features as ft
        a = np.asarray(win, float)
        fs = 1
        feats = []
        for call in (
            lambda: ft.abs_energy(a),
            lambda: ft.spectral_centroid(a, fs),
            lambda: ft.fundamental_frequency(a, fs),
            lambda: ft.entropy(a),
            lambda: ft.slope(a),
            lambda: ft.mean_abs_diff(a),
        ):
            try:
                feats.append(float(np.asarray(call()).ravel()[0]))
            except Exception:
                feats.append(0.0)
        return _clean(feats, self.NFEAT)


# --------------------------------------------------------------------------- #
# 6. FracDiff — pure-numpy López de Prado fixed-width fractional differentiation
# --------------------------------------------------------------------------- #
def _fracdiff_weights(d: float, size: int) -> np.ndarray:
    """López de Prado fixed-width fractional-differentiation binomial weights.

    w_0 = 1; w_k = -w_{k-1} * (d - k + 1) / k. Returned newest-first so a direct
    dot with a trailing window (oldest..newest) lines weights up with lags."""
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    # w[0] multiplies the most recent point; reverse so it aligns with win[-1]
    return np.asarray(w[::-1], float)


class FracDiffNode(_WindowFeat):
    """Fixed-width fractional differentiation (López de Prado), pure numpy — the
    `fracdiff` package fails to build, so weights are computed directly. Emits
    the fractionally differenced value of the trailing window for d=0.4 and
    d=0.6 (two memory-preserving stationarity features)."""
    kind = "quant"
    NFEAT = 2

    def __init__(self, name="fracdiff_feats", col=0, W=64):
        super().__init__(name, "Fractional differentiation (numpy, d=0.4 & 0.6) window features.", col, W)

    def _features(self, win):
        a = np.asarray(win, float)
        n = len(a)
        out = []
        for d in (0.4, 0.6):
            w = _fracdiff_weights(d, n)
            out.append(float(np.dot(w, a)))
        return _clean(out, self.NFEAT)


# --------------------------------------------------------------------------- #
# No-arg factories
# --------------------------------------------------------------------------- #
def talib_node(): return TALibNode()
def neurokit2_node(): return NeuroKit2Node()
def librosa_node(): return LibrosaNode()
def entropyhub_node(): return EntropyHubNode()
def tsfel_node(): return TSFELNode()
def fracdiff_node(): return FracDiffNode()
