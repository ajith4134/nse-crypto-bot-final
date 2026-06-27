"""Detection / discovery nodes — "is the structure real, weak, or random?".

A zoo of *structure-detection* time-series nodes wrapped behind the project
NodeProtocol (core/node_protocol.py).  Each node turns a chosen column into a
1-D signal and derives CAUSAL trailing-window features that answer a detection
question: surrogate / chaos tests (random vs structured), weak-signal detectors
(multitaper F-test, Lomb-Scargle FAP, matched filter, stochastic resonance),
change-point / regime structure (BOCPD, recurring states) and
compression/discretisation pattern measures (NCD, SAX, shapelets).

Machinery is REUSED, not reinvented: every node subclasses ``_WindowFeat`` (and
its task-aware ``_HeadBase`` readout) imported from ``nodes.quant_nodes`` — the
same causal trailing-window contract the rest of the node zoo is built on:

  * per row ``i`` the window is ``col[max(0, i-W+1) : i+1]`` (past+present only);
  * windows shorter than 12 samples fall back to fixed-length zeros;
  * a task-aware readout (LogisticRegression / Ridge) maps
    ``[raw X row | window features]`` to the target, so binary
    ``predict_output`` rows are 2-wide ``[1-p, p]`` automatically;
  * numeric / optimizer warnings are suppressed and every feature call is
    wrapped in try/except with a cheap, robust fallback so a node never breaks
    the graph;  degenerate (constant / empty) windows yield zeros.

Library vs self-implemented (nolitsa / claspy pip installs failed, so those are
written from scratch in numpy):
  SurrogateTestNode  - SELF (IAAFT surrogates + z-score)
  MultitaperFtestNode- LIB  (multitaper.MTSpec, fallback periodogram)
  LombScargleFAPNode - LIB  (astropy.timeseries.LombScargle)
  MatchedFilterNode  - LIB  (scipy.signal cross-correlation vs learned motif)
  BOCPDNode          - LIB  (bayesian_changepoint_detection, fallback CUSUM)
  ZeroOneChaosNode   - SELF (Gottwald-Melbourne 0-1 test)
  NCDNode            - SELF (stdlib lzma normalized compression distance)
  StochResonanceNode - SELF (bistable Langevin stochastic-resonance detector)
  TslearnSAXNode     - LIB  (tslearn SymbolicAggregateApproximation)
  TslearnShapeletNode- LIB  (tslearn KMeans shapelets; cheap min-distance)
  RecurringStateNode - SELF/LIB (ruptures segmentation + KMeans recurring state)
"""
from __future__ import annotations

import contextlib
import warnings

import numpy as np

# Reuse the project's causal trailing-window + task-aware readout machinery.
from core.node_protocol import IOSchema, Labels, Matrix, Vector  # noqa: F401
from nodes.quant_nodes import _HeadBase, _WindowFeat  # noqa: F401


@contextlib.contextmanager
def _quiet():
    """Suppress library warnings + numpy floating errors around fragile code."""
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        yield


def _clean(vals, n: int) -> list[float]:
    """Pad/trim to length n and replace non-finite entries with 0.0."""
    out = list(vals)[:n] + [0.0] * max(0, n - len(vals))
    return [float(v) if np.isfinite(v) else 0.0 for v in out]


def _z(w: np.ndarray) -> np.ndarray:
    """Zero-mean / unit-std a window (robust to constant windows)."""
    w = np.asarray(w, dtype=float)
    sd = float(w.std())
    return (w - w.mean()) / sd if sd > 0 else (w - w.mean())


# =========================================================================== #
#  1. SurrogateTestNode  (chaos)  — SELF-IMPLEMENTED IAAFT surrogate test
# =========================================================================== #
class SurrogateTestNode(_WindowFeat):
    """Is the window's structure real or could a random (linear) process explain
    it?  Self-implemented IAAFT (iterative amplitude-adjusted Fourier transform)
    surrogates preserve the amplitude spectrum + value distribution but destroy
    nonlinear structure.  Feature = z-score of the real series' discriminating
    statistic (lag-1 autocorrelation) vs the surrogate distribution: large |z|
    => structure beyond a random linear surrogate."""

    kind = "chaos"
    NFEAT = 1

    def __init__(self, name: str = "surrogate_test", col: int = 0, W: int = 96,
                 k: int = 12, iters: int = 30):
        super().__init__(name,
                         "self-impl IAAFT surrogate test: z-score of real lag-1 "
                         "autocorr vs surrogate distribution (structure vs random).",
                         col, W)
        self.k, self.iters = k, iters

    @staticmethod
    def _stat(w: np.ndarray) -> float:
        w = w - w.mean()
        d = float(np.dot(w, w))
        return float(np.dot(w[:-1], w[1:]) / d) if d > 0 else 0.0

    def _iaaft(self, x: np.ndarray, rng) -> np.ndarray:
        n = len(x)
        amp = np.abs(np.fft.rfft(x))
        sorted_x = np.sort(x)
        s = rng.permutation(x)
        for _ in range(self.iters):
            phases = np.angle(np.fft.rfft(s))
            s = np.fft.irfft(amp * np.exp(1j * phases), n=n)
            ranks = np.argsort(np.argsort(s))
            s = sorted_x[ranks]
        return s

    def _features(self, win):
        try:
            w = np.asarray(win, dtype=float)
            if w.std() == 0:
                return [0.0]
            rng = np.random.default_rng(0)
            real = self._stat(w)
            surr = np.array([self._stat(self._iaaft(w, rng)) for _ in range(self.k)])
            mu, sd = float(surr.mean()), float(surr.std())
            return _clean([(real - mu) / sd if sd > 0 else 0.0], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def surrogate_test_node() -> SurrogateTestNode:
    return SurrogateTestNode()


# =========================================================================== #
#  2. MultitaperFtestNode  (signal)  — multitaper.MTSpec harmonic F-test
# =========================================================================== #
class MultitaperFtestNode(_WindowFeat):
    """DPSS multitaper PSD + Thomson harmonic F-test (multitaper.MTSpec): detects
    sinusoidal line components buried in noise.  Features = [max F-statistic,
    frequency of the max-F line, total power].  Robust fallback to a plain
    periodogram peak when the multitaper library/fit fails."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, name: str = "multitaper_ftest", col: int = 0, W: int = 96):
        super().__init__(name,
                         "multitaper DPSS F-test [max F, freq of max-F, total "
                         "power] (fallback: periodogram peak).",
                         col, W)

    def _features(self, win):
        w = np.asarray(win, dtype=float)
        w = w - w.mean()
        try:
            from multitaper import MTSpec
            m = MTSpec(w, nw=3.0, kspec=4, dt=1.0)
            F = np.asarray(m.ftest()[0]).ravel()
            freq = np.asarray(m.freq).ravel()
            spec = np.asarray(m.spec).ravel()
            kf = int(np.argmax(F[1:]) + 1) if len(F) > 1 else 0
            return _clean([float(F[kf]), float(freq[kf]),
                           float(np.sum(spec))], self.NFEAT)
        except Exception:
            try:
                p = np.abs(np.fft.rfft(w)) ** 2
                freq = np.fft.rfftfreq(len(w))
                k = int(np.argmax(p[1:]) + 1) if len(p) > 1 else 0
                return _clean([float(p[k]), float(freq[k]),
                               float(np.sum(p))], self.NFEAT)
            except Exception:
                return [0.0] * self.NFEAT


def multitaper_ftest_node() -> MultitaperFtestNode:
    return MultitaperFtestNode()


# =========================================================================== #
#  3. LombScargleFAPNode  (signal)  — astropy LombScargle false-alarm prob
# =========================================================================== #
class LombScargleFAPNode(_WindowFeat):
    """astropy.timeseries.LombScargle periodogram: detect a periodic component
    and quantify its significance.  Features = [peak power, 1 - false_alarm_
    probability(peak), peak frequency].  ``1 - FAP`` ~ 1 => a confidently real
    period.  Robust fallback to an FFT peak with no FAP if astropy fails."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, name: str = "lombscargle_fap", col: int = 0, W: int = 128):
        super().__init__(name,
                         "Lomb-Scargle [peak power, 1-FAP, peak freq] periodic "
                         "signal significance (fallback: FFT peak).",
                         col, W)

    def _features(self, win):
        w = np.asarray(win, dtype=float)
        try:
            from astropy.timeseries import LombScargle
            t = np.arange(len(w), dtype=float)
            ls = LombScargle(t, w)
            freq, power = ls.autopower()
            k = int(np.argmax(power))
            pk = float(power[k])
            fap = float(ls.false_alarm_probability(pk))
            return _clean([pk, 1.0 - fap, float(freq[k])], self.NFEAT)
        except Exception:
            try:
                w = w - w.mean()
                p = np.abs(np.fft.rfft(w)) ** 2
                freq = np.fft.rfftfreq(len(w))
                k = int(np.argmax(p[1:]) + 1) if len(p) > 1 else 0
                tot = float(np.sum(p))
                return _clean([float(p[k]), float(p[k] / tot) if tot > 0 else 0.0,
                               float(freq[k])], self.NFEAT)
            except Exception:
                return [0.0] * self.NFEAT


def lombscargle_fap_node() -> LombScargleFAPNode:
    return LombScargleFAPNode()


# =========================================================================== #
#  4. MatchedFilterNode  (signal)  — scipy cross-correlation vs learned motif
# =========================================================================== #
class MatchedFilterNode(_WindowFeat):
    """Matched filter: cross-correlate (scipy.signal.correlate) each normalized
    window against a learned template motif — the mean normalized motif of the
    training column.  Features = [max cross-correlation, lag of the max, cross-
    correlation energy].  A strong, well-localised peak => the known motif
    recurs in this window.  Learns the template at fit; robust fallbacks
    throughout."""

    kind = "signal"
    NFEAT = 3

    def __init__(self, name: str = "matched_filter", col: int = 0, W: int = 96,
                 L: int = 24):
        super().__init__(name,
                         "scipy matched filter vs learned mean motif [max xcorr, "
                         "lag of max, xcorr energy].",
                         col, W)
        self.L = L
        self._template: np.ndarray | None = None

    def _learn(self, X: Matrix) -> None:
        try:
            col = np.asarray([float(r[self.col]) for r in X], dtype=float)
            L = min(self.L, max(4, len(col) // 4))
            chunks = [_z(col[i:i + L]) for i in range(0, len(col) - L + 1, L)]
            if chunks:
                self._template = np.mean(np.vstack(chunks), axis=0)
        except Exception:
            self._template = None

    def fit(self, X: Matrix, y: Labels):
        self._learn(X)
        return super().fit(X, y)

    def _features(self, win):
        try:
            from scipy.signal import correlate
            t = self._template
            w = _z(np.asarray(win, dtype=float))
            if t is None or len(w) < len(t):
                return [0.0] * self.NFEAT
            xc = correlate(w, t, mode="valid")
            mx = float(np.max(np.abs(xc)))
            lag = float(np.argmax(np.abs(xc)))
            energy = float(np.sum(xc ** 2))
            return _clean([mx, lag, energy], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def matched_filter_node() -> MatchedFilterNode:
    return MatchedFilterNode()


# =========================================================================== #
#  5. BOCPDNode  (regime)  — bayesian_changepoint_detection run-length posterior
# =========================================================================== #
class BOCPDNode(_WindowFeat):
    """Bayesian Online Change-Point Detection (bayesian_changepoint_detection):
    runs the online run-length posterior over the trailing window; feature = the
    posterior probability that a change point just occurred at the most recent
    sample (P(run length = 0 | data)).  Robust fallback to a rolling CUSUM
    change score when the library fails."""

    kind = "regime"
    NFEAT = 1

    def __init__(self, name: str = "bocpd", col: int = 0, W: int = 80):
        super().__init__(name,
                         "Bayesian online change-point posterior P(changepoint "
                         "now) (fallback: rolling CUSUM).",
                         col, W)

    @staticmethod
    def _cusum(w: np.ndarray) -> float:
        z = _z(w)
        s = np.cumsum(z - z.mean())
        rng = float(s.max() - s.min())
        return float(rng / (len(z) ** 0.5)) if len(z) else 0.0

    def _features(self, win):
        w = np.asarray(win, dtype=float)
        try:
            from functools import partial

            import bayesian_changepoint_detection.online_changepoint_detection \
                as oncd
            R, _ = oncd.online_changepoint_detection(
                w, partial(oncd.constant_hazard, 200.0),
                oncd.StudentT(0.1, 0.01, 1.0, 0.0))
            return _clean([float(R[0, len(w)])], self.NFEAT)
        except Exception:
            try:
                return _clean([self._cusum(w)], self.NFEAT)
            except Exception:
                return [0.0] * self.NFEAT


def bocpd_node() -> BOCPDNode:
    return BOCPDNode()


# =========================================================================== #
#  6. ZeroOneChaosNode  (chaos)  — SELF-IMPLEMENTED Gottwald-Melbourne 0-1 test
# =========================================================================== #
class ZeroOneChaosNode(_WindowFeat):
    """Self-implemented Gottwald-Melbourne 0-1 test for chaos.  Drives the signal
    through random rotations, measures the asymptotic growth (mean-square
    displacement) of the resulting translation variables, and reports the median
    correlation-based K-statistic in [0, 1]: K ~ 0 => regular/periodic, K ~ 1 =>
    chaotic.  Single per-window feature."""

    kind = "chaos"
    NFEAT = 1

    def __init__(self, name: str = "zero_one_chaos", col: int = 0, W: int = 128):
        super().__init__(name,
                         "self-impl Gottwald-Melbourne 0-1 test K-statistic "
                         "(0=regular, 1=chaotic).",
                         col, W)

    @staticmethod
    def _K(x: np.ndarray) -> float:
        x = np.asarray(x, dtype=float)
        x = x - x.mean()
        N = len(x)
        n_idx = np.arange(1, N + 1)
        ncut = max(2, N // 10)
        ks = []
        for c in np.linspace(np.pi / 5.0, 4.0 * np.pi / 5.0, 7):
            p = np.cumsum(x * np.cos(n_idx * c))
            q = np.cumsum(x * np.sin(n_idx * c))
            Vosc = (x.mean() ** 2) * (1.0 - np.cos(n_idx[:ncut] * c)) \
                / (1.0 - np.cos(c)) if (1.0 - np.cos(c)) != 0 else 0.0
            M = np.empty(ncut)
            for n in range(1, ncut + 1):
                d = (p[n:] - p[:-n]) ** 2 + (q[n:] - q[:-n]) ** 2
                M[n - 1] = d.mean() if len(d) else 0.0
            D = M - Vosc
            nn = np.arange(1, ncut + 1, dtype=float)
            if np.std(nn) > 0 and np.std(D) > 0:
                ks.append(float(np.corrcoef(nn, D)[0, 1]))
        return float(np.median(ks)) if ks else 0.0

    def _features(self, win):
        try:
            w = np.asarray(win, dtype=float)
            if w.std() == 0:
                return [0.0]
            return _clean([self._K(w)], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def zero_one_chaos_node() -> ZeroOneChaosNode:
    return ZeroOneChaosNode()


# =========================================================================== #
#  7. NCDNode  (math)  — SELF-IMPLEMENTED Normalized Compression Distance (lzma)
# =========================================================================== #
class NCDNode(_WindowFeat):
    """Self-implemented Normalized Compression Distance using stdlib ``lzma``.
    Quantises the window to bytes and measures NCD between its two halves
    (similar halves compress better together => low NCD => repeating structure),
    plus the overall compression ratio (low ratio => highly compressible =>
    structured).  Features = [NCD, compression ratio]."""

    kind = "math"
    NFEAT = 2

    def __init__(self, name: str = "ncd", col: int = 0, W: int = 96):
        super().__init__(name,
                         "self-impl lzma NCD between window halves + compression "
                         "ratio (compressibility = structure).",
                         col, W)

    @staticmethod
    def _b(w: np.ndarray) -> bytes:
        lo, hi = float(w.min()), float(w.max())
        q = np.zeros_like(w) if hi <= lo else (w - lo) / (hi - lo)
        return (q * 255.0).astype(np.uint8).tobytes()

    @staticmethod
    def _c(b: bytes) -> int:
        import lzma
        return len(lzma.compress(b, preset=1))

    def _features(self, win):
        try:
            w = np.asarray(win, dtype=float)
            h = len(w) // 2
            a, b = self._b(w[:h]), self._b(w[h:])
            ca, cb, cab = self._c(a), self._c(b), self._c(a + b)
            ncd = (cab - min(ca, cb)) / max(ca, cb) if max(ca, cb) else 0.0
            raw = self._b(w)
            ratio = self._c(raw) / len(raw) if len(raw) else 0.0
            return _clean([ncd, ratio], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def ncd_node() -> NCDNode:
    return NCDNode()


# =========================================================================== #
#  8. StochResonanceNode  (signal)  — SELF-IMPLEMENTED bistable Langevin SR
# =========================================================================== #
class StochResonanceNode(_WindowFeat):
    """Self-implemented bistable Langevin stochastic-resonance detector.  Drives
    the normalized window as the forcing of an over-damped double-well system
    ``dx = (x - x^3 + A*signal) dt + sqrt(2D dt) noise`` (Euler-Maruyama); added
    noise can *amplify* a weak periodic input via stochastic resonance.
    Features = [output SNR proxy = output power at the dominant input frequency /
    total output power, response amplitude = output std]."""

    kind = "signal"
    NFEAT = 2

    def __init__(self, name: str = "stoch_resonance", col: int = 0, W: int = 128,
                 A: float = 0.35, D: float = 0.10, dt: float = 0.2):
        super().__init__(name,
                         "self-impl bistable Langevin stochastic-resonance "
                         "[output SNR proxy, response amplitude].",
                         col, W)
        self.A, self.D, self.dt = A, D, dt

    def _features(self, win):
        try:
            s = _z(np.asarray(win, dtype=float))
            rng = np.random.default_rng(0)
            x = 0.0
            out = np.empty(len(s))
            noise = np.sqrt(2.0 * self.D * self.dt)
            for i, v in enumerate(s):
                x += self.dt * (x - x ** 3 + self.A * v) \
                    + noise * rng.standard_normal()
                if not np.isfinite(x):
                    x = 0.0
                out[i] = x
            Sin = np.abs(np.fft.rfft(s))
            Sout = np.abs(np.fft.rfft(out - out.mean())) ** 2
            k = int(np.argmax(Sin[1:]) + 1) if len(Sin) > 1 else 0
            tot = float(np.sum(Sout))
            snr = float(Sout[k] / tot) if tot > 0 else 0.0
            return _clean([snr, float(out.std())], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def stoch_resonance_node() -> StochResonanceNode:
    return StochResonanceNode()


# =========================================================================== #
#  9. TslearnSAXNode  (ml)  — tslearn SymbolicAggregateApproximation histogram
# =========================================================================== #
class TslearnSAXNode(_WindowFeat):
    """tslearn SymbolicAggregateApproximation (SAX): PAA-reduce + discretise the
    window into ``A`` symbols, then summarise as the normalised symbol histogram
    (the discrete "shape vocabulary" the window uses).  Features = per-symbol
    frequency (length = alphabet size).  Robust fallback to a quantile histogram
    if tslearn fails."""

    kind = "ml"

    def __init__(self, name: str = "tslearn_sax", col: int = 0, W: int = 96,
                 n_segments: int = 10, alphabet: int = 5):
        self.n_segments, self.alphabet = n_segments, alphabet
        self.NFEAT = alphabet
        super().__init__(name,
                         "tslearn SAX symbol histogram (discrete shape "
                         "vocabulary) (fallback: quantile histogram).",
                         col, W)

    def _features(self, win):
        w = np.asarray(win, dtype=float)
        try:
            from tslearn.piecewise import SymbolicAggregateApproximation
            sax = SymbolicAggregateApproximation(
                n_segments=min(self.n_segments, max(1, len(w))),
                alphabet_size_avg=self.alphabet)
            codes = np.ravel(sax.fit_transform(w.reshape(1, -1, 1))).astype(int)
            hist = np.bincount(codes, minlength=self.alphabet)[:self.alphabet]
            tot = float(hist.sum())
            return _clean((hist / tot).tolist() if tot else hist.tolist(),
                          self.NFEAT)
        except Exception:
            try:
                edges = np.quantile(w, np.linspace(0, 1, self.alphabet + 1)[1:-1])
                codes = np.digitize(w, edges)
                hist = np.bincount(codes, minlength=self.alphabet)[:self.alphabet]
                tot = float(hist.sum())
                return _clean((hist / tot).tolist() if tot else hist.tolist(),
                              self.NFEAT)
            except Exception:
                return [0.0] * self.NFEAT


def tslearn_sax_node() -> TslearnSAXNode:
    return TslearnSAXNode()


# =========================================================================== #
#  10. TslearnShapeletNode  (ml)  — cheap min-distance to learned motif shapelets
# =========================================================================== #
class TslearnShapeletNode(_WindowFeat):
    """Cheap shapelet-distance features.  Learns ``k`` representative motifs
    (shapelets) at fit time via tslearn TimeSeriesKMeans (fallback: plain
    KMeans) over normalized length-L subsequences of the training column.  Per
    window, the feature for each shapelet is the minimum sliding Euclidean
    distance to it — small distance => that discriminative motif is present.
    (Full LearningShapelets is skipped for speed; this is the fast variant.)"""

    kind = "ml"

    def __init__(self, name: str = "tslearn_shapelet", col: int = 0, W: int = 96,
                 L: int = 20, k: int = 3, sub_stride: int = 4):
        self.L, self.k, self.sub_stride = L, k, sub_stride
        self.NFEAT = k
        super().__init__(name,
                         "min sliding distance to k learned motif shapelets "
                         "(cheap shapelet variant).",
                         col, W)
        self._shapelets: list[np.ndarray] = []

    def _learn(self, X: Matrix) -> None:
        try:
            col = np.asarray([float(r[self.col]) for r in X], dtype=float)
            L = min(self.L, max(4, len(col) // 4))
            subs = [_z(col[i:i + L])
                    for i in range(0, len(col) - L + 1, self.sub_stride)]
            if len(subs) < self.k:
                self._shapelets = [s for s in subs]
                return
            M = np.vstack(subs)
            with _quiet():
                try:
                    from tslearn.clustering import TimeSeriesKMeans
                    km = TimeSeriesKMeans(n_clusters=self.k, metric="euclidean",
                                          max_iter=10, random_state=0)
                    km.fit(M.reshape(M.shape[0], M.shape[1], 1))
                    self._shapelets = [c.ravel() for c in km.cluster_centers_]
                except Exception:
                    from sklearn.cluster import KMeans
                    km = KMeans(n_clusters=self.k, n_init=3, random_state=0).fit(M)
                    self._shapelets = [c for c in km.cluster_centers_]
        except Exception:
            self._shapelets = []

    def fit(self, X: Matrix, y: Labels):
        self._learn(X)
        return super().fit(X, y)

    @staticmethod
    def _min_dist(w: np.ndarray, s: np.ndarray) -> float:
        L = len(s)
        if len(w) < L:
            return float(np.linalg.norm(_z(w)[:L] - s[:len(w)]))
        best = np.inf
        for i in range(0, len(w) - L + 1):
            d = float(np.linalg.norm(_z(w[i:i + L]) - s))
            if d < best:
                best = d
        return float(best)

    def _features(self, win):
        try:
            if not self._shapelets:
                return [0.0] * self.NFEAT
            w = np.asarray(win, dtype=float)
            feats = [self._min_dist(w, s) for s in self._shapelets]
            return _clean(feats, self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def tslearn_shapelet_node() -> TslearnShapeletNode:
    return TslearnShapeletNode()


# =========================================================================== #
#  11. RecurringStateNode  (regime)  — ruptures segmentation + KMeans state
# =========================================================================== #
class RecurringStateNode(_WindowFeat):
    """Recurring-state labeller (claspy substitute: claspy pip install failed).
    Self-implemented on top of ``ruptures``: change-point-segment each window
    (Binseg/l2), summarise the most recent segment by [mean, std, slope], then
    map it to a *recurring* state with a KMeans model learned over training
    windows.  Feature = the integer state label per row — recurring regimes get
    the same label.  Robust fallback to mean-based binning."""

    kind = "regime"
    NFEAT = 1

    def __init__(self, name: str = "recurring_state", col: int = 0, W: int = 96,
                 n_states: int = 4, n_bkps: int = 2, fit_stride: int = 3):
        super().__init__(name,
                         "ruptures segmentation + KMeans recurring-state label "
                         "per row (self-impl claspy substitute).",
                         col, W)
        self.n_states, self.n_bkps, self.fit_stride = n_states, n_bkps, fit_stride
        self._km = None
        self._mu = 0.0
        self._sd = 1.0

    def _seg_stat(self, w: np.ndarray) -> list[float]:
        w = np.asarray(w, dtype=float)
        seg = w
        try:
            import ruptures as rpt
            if len(w) >= 2 * (self.n_bkps + 1):
                algo = rpt.Binseg(model="l2", min_size=2).fit(w)
                bkps = algo.predict(n_bkps=self.n_bkps)
                start = bkps[-2] if len(bkps) >= 2 else 0
                seg = w[start:]
        except Exception:
            seg = w
        if len(seg) < 2:
            seg = w
        slope = float(np.polyfit(np.arange(len(seg)), seg, 1)[0]) \
            if len(seg) >= 2 else 0.0
        return [float(seg.mean()), float(seg.std()), slope]

    def _learn(self, X: Matrix) -> None:
        try:
            col = np.asarray([float(r[self.col]) for r in X], dtype=float)
            stats = []
            for i in range(0, len(col), self.fit_stride):
                w = col[max(0, i - self.W + 1): i + 1]
                if len(w) >= 12:
                    stats.append(self._seg_stat(w))
            if len(stats) < self.n_states:
                return
            M = np.asarray(stats, dtype=float)
            self._mu = M.mean(axis=0)
            self._sd = np.where(M.std(axis=0) > 0, M.std(axis=0), 1.0)
            with _quiet():
                from sklearn.cluster import KMeans
                self._km = KMeans(n_clusters=self.n_states, n_init=3,
                                  random_state=0).fit((M - self._mu) / self._sd)
        except Exception:
            self._km = None

    def fit(self, X: Matrix, y: Labels):
        self._learn(X)
        return super().fit(X, y)

    def _features(self, win):
        try:
            w = np.asarray(win, dtype=float)
            if self._km is None:
                return [float(np.sign(w[-1] - w.mean()) + 1)]
            s = (np.asarray(self._seg_stat(w)) - self._mu) / self._sd
            with _quiet():
                label = int(self._km.predict(s.reshape(1, -1))[0])
            return _clean([float(label)], self.NFEAT)
        except Exception:
            return [0.0] * self.NFEAT


def recurring_state_node() -> RecurringStateNode:
    return RecurringStateNode()
