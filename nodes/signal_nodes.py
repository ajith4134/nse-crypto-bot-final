"""Signal-in-noise / pattern-detection nodes — the reuse-first signal layer.

Each class wraps a mature, CPU-friendly time-series / signal-processing library
behind the SAME `NodeProtocol` the rest of the zoo uses (fit/predict_proba/
predict/predict_output over Matrix/Labels), so the brain, router, eval plane and
dashboard are unchanged — only the feature mechanism behind the interface is new:

  - stumpy     matrix-profile (motif / discord / novelty distance)
  - pyod       outlier detection (IForest) anomaly score as a feature
  - pywt       discrete wavelet energy per decomposition level
  - PyEMD      empirical-mode-decomposition IMF energies
  - pyts       Singular-Spectrum-Analysis component variances
  - filterpy   1-D constant-velocity Kalman level / velocity / residual
  - numpy      Random-Matrix-Theory (Marchenko-Pastur) eigen signal count
  - nistrng    NIST SP800-22 randomness-test statistics on the sign stream

UNIFORM MECHANISM
-----------------
Our X is feature ROWS, so every node derives a 1-D signal from one feature
column (`col`) and, for each row i, looks only at a CAUSAL trailing window
`signal[i-W+1 : i+1]` (NO look-ahead). A small per-library feature vector is
computed on that window and APPENDED to the raw row; a task-aware scikit-learn
readout (LogisticRegression for binary/multiclass, Ridge for regression — both
standardized) is then fit on the augmented matrix. This mirrors the readout /
predict_output style of `SklearnNode` (multiclass) and `SklearnRegressorNode`
(regression) in `nodes/oss_nodes.py`.

`_Base` implements fit/predict_proba/predict/predict_output ONCE (task-aware);
each concrete node only overrides `_features(win)` (or, where the window is the
full feature matrix / a global detector, `_augment` / `_fit_extra`). Short
windows (len < 8) return a fixed-length zero vector so the augmented matrix stays
rectangular, and every feature function suppresses numerical warnings.

Inputs:  Matrix of feature rows + Labels (0/1 ints) or regression targets.
Outputs: per-row class probabilities (classification) or [value] (regression).
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  Shared causal-window signal base (task-aware readout, copied from oss_nodes)
# --------------------------------------------------------------------------- #
class _Base(BaseNode):
    """Causal trailing-window feature node + standardized sklearn readout.

    Subclasses override `_features(win) -> list[float]` (fixed length). The
    fit/predict family is implemented once and supports binary, multiclass and
    regression heads exactly like SklearnNode / SklearnRegressorNode.
    """

    kind = "signal"

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 64):
        self.name = name
        self.summary = summary
        self.kind = "signal"
        self.col = col
        self.W = W
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "features", "p/score")
        self._classes: list[int] = []
        self.n_classes = 2
        self._constant: float | None = None
        self._ymin = 0.0
        self._ymax = 1.0

    # -- per-library feature hook ------------------------------------------- #
    def _features(self, win: list[float]) -> list[float]:
        """Return a FIXED-length feature vector for one causal window."""
        raise NotImplementedError

    def _fit_extra(self, X: Matrix) -> None:
        """Optional hook to fit a stateful detector on the training rows."""
        return None

    # -- augmentation: raw row ++ window features --------------------------- #
    def _augment(self, X: Matrix) -> np.ndarray:
        col = [float(r[self.col]) for r in X]
        out = []
        for i in range(len(X)):
            win = col[max(0, i - self.W + 1):i + 1]
            out.append(list(map(float, X[i])) + self._features(win))
        return np.asarray(out, dtype=float)

    # -- readout (task-aware, standardized) --------------------------------- #
    def _readout(self):
        from sklearn.linear_model import LogisticRegression, Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        est = Ridge() if self.task == "regression" else LogisticRegression(max_iter=1000)
        return make_pipeline(StandardScaler(), est)

    # -- fit / predict family (mirrors oss_nodes by task) ------------------- #
    def fit(self, X: Matrix, y: Labels) -> "_Base":
        self._fit_extra(X)
        Xa = self._augment(X)
        d = Xa.shape[1]
        if self.task == "regression":
            ya = np.asarray(y, dtype=float)
            self.schema = IOSchema(d, f"{d} numeric features (+window)", "predicted value")
            self._ymin = float(ya.min()) if len(ya) else 0.0
            self._ymax = float(ya.max()) if len(ya) else 1.0
            if self._ymax <= self._ymin:                 # degenerate constant y
                self._constant = float(ya[0]) if len(ya) else 0.0
                return self
            self._constant = None
            self._readout_est = self._readout()
            self._readout_est.fit(Xa, ya)
            return self
        ya = np.asarray(y, dtype=int)
        self._classes = sorted(set(int(v) for v in ya))
        self.n_classes = len(self._classes)
        if self.n_classes > 2:
            self.task = "multiclass"
            self.schema = IOSchema(d, f"{d} numeric features (+window)",
                                   f"p(class) over {self.n_classes} classes")
        else:
            self.schema = IOSchema(d, f"{d} numeric features (+window)", "p(class=1)")
        if self.n_classes < 2:                            # only one class present
            return self
        self._readout_est = self._readout()
        self._readout_est.fit(Xa, ya)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            vals = self.predict(X)
            span = self._ymax - self._ymin
            if span <= 0.0:
                return [0.5] * len(vals)
            return [min(1.0, max(0.0, (v - self._ymin) / span)) for v in vals]
        if self.n_classes < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        proba = self._readout_est.predict_proba(self._augment(X))
        if self.task == "multiclass":
            return [float(row.max()) for row in proba]
        cols = list(self._readout_est.classes_)
        j = cols.index(1) if 1 in cols else len(cols) - 1
        return [float(v) for v in proba[:, j]]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            if self._constant is not None:
                return [self._constant] * len(X)
            return [float(v) for v in self._readout_est.predict(self._augment(X))]
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(row))]
                    for row in self.predict_output(X)]
        return super().predict(X)                         # binary: threshold 0.5

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self.task == "regression":
            return [[v] for v in self.predict(X)]
        if self.task == "multiclass":
            if self.n_classes < 2:
                return [[1.0]] * len(X)
            proba = self._readout_est.predict_proba(self._augment(X))
            cols = list(self._readout_est.classes_)
            order = [cols.index(c) for c in self._classes]
            return [[float(row[o]) for o in order] for row in proba]
        return super().predict_output(X)                  # binary: [p0, p1]


# --------------------------------------------------------------------------- #
#  1. stumpy matrix profile (motif / discord novelty distances)
# --------------------------------------------------------------------------- #
class StumpyMatrixProfileNode(_Base):
    """Per-window matrix profile (stumpy.stump): features = [min, mean, std] of
    the profile distances — small min => repeated motif, large => discord."""

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0]
        import stumpy
        m = min(8, len(win) // 2)
        if m < 3:
            return [0.0, 0.0, 0.0]
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                mp = stumpy.stump(np.asarray(win, dtype=float), m=m)[:, 0].astype(float)
                mp = mp[np.isfinite(mp)]
                if mp.size == 0:
                    return [0.0, 0.0, 0.0]
                return [float(mp.min()), float(mp.mean()), float(mp.std())]
            except Exception:
                return [0.0, 0.0, 0.0]


def stumpy_matrix_profile_node(col: int = 0, W: int = 64,
                               name: str = "stumpy_mp") -> StumpyMatrixProfileNode:
    return StumpyMatrixProfileNode(
        name, "stumpy matrix-profile (motif/discord distances) + sklearn readout.",
        col=col, W=W)


# --------------------------------------------------------------------------- #
#  2. pyod anomaly score as an extra feature (global IForest detector)
# --------------------------------------------------------------------------- #
class PyODAnomalyNode(_Base):
    """Fits a pyod IForest on the TRAINING feature rows; at predict the detector's
    per-row anomaly score (decision_function) is appended as one extra feature
    feeding the readout (anomaly-score-as-feature)."""

    def __init__(self, name: str, summary: str, col: int = 0, W: int = 64):
        super().__init__(name, summary, col=col, W=W)
        self._det = None

    def _features(self, win: list[float]) -> list[float]:   # unused (see _augment)
        return [0.0]

    def _fit_extra(self, X: Matrix) -> None:
        from pyod.models.iforest import IForest
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            self._det = IForest(random_state=1)
            self._det.fit(np.asarray(X, dtype=float))

    def _augment(self, X: Matrix) -> np.ndarray:
        Xa = np.asarray(X, dtype=float)
        if self._det is None:
            return Xa
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            score = np.asarray(self._det.decision_function(Xa), dtype=float).reshape(-1, 1)
        return np.hstack([Xa, np.nan_to_num(score)])


def pyod_anomaly_node(col: int = 0, W: int = 64,
                      name: str = "pyod_iforest") -> PyODAnomalyNode:
    return PyODAnomalyNode(
        name, "pyod IForest anomaly score as an extra feature + sklearn readout.",
        col=col, W=W)


# --------------------------------------------------------------------------- #
#  3. pywt discrete-wavelet energy per level
# --------------------------------------------------------------------------- #
class WaveletEnergyNode(_Base):
    """Per-window db4 wavelet decomposition (level 3): features = energy
    (sum of squares) of each coefficient band [cA3, cD3, cD2, cD1]."""

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0, 0.0]
        import pywt
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                coeffs = pywt.wavedec(np.asarray(win, dtype=float), "db4", level=3)
                energies = [float(np.sum(np.asarray(c, dtype=float) ** 2)) for c in coeffs]
            except Exception:
                return [0.0, 0.0, 0.0, 0.0]
        return (energies + [0.0, 0.0, 0.0, 0.0])[:4]


def wavelet_energy_node(col: int = 0, W: int = 64,
                        name: str = "pywt_energy") -> WaveletEnergyNode:
    return WaveletEnergyNode(
        name, "pywt db4 wavelet energy per level (3) + sklearn readout.",
        col=col, W=W)


# --------------------------------------------------------------------------- #
#  4. PyEMD empirical-mode-decomposition IMF energies
# --------------------------------------------------------------------------- #
class EMDEnergyNode(_Base):
    """Per-window EMD: features = energy (sum of squares) of the first 3 IMFs
    (zero-padded if fewer IMFs are extracted)."""

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0]
        from PyEMD import EMD
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                imfs = EMD().emd(np.asarray(win, dtype=float))
                en = [float(np.sum(np.asarray(imf, dtype=float) ** 2)) for imf in imfs[:3]]
            except Exception:
                return [0.0, 0.0, 0.0]
        return (en + [0.0, 0.0, 0.0])[:3]


def emd_energy_node(col: int = 0, W: int = 64,
                    name: str = "pyemd_energy") -> EMDEnergyNode:
    return EMDEnergyNode(
        name, "PyEMD IMF energies (first 3) + sklearn readout.", col=col, W=W)


# --------------------------------------------------------------------------- #
#  5. pyts Singular-Spectrum-Analysis component variances
# --------------------------------------------------------------------------- #
class SSANode(_Base):
    """Per-window Singular Spectrum Analysis (pyts): features = variance of the
    first 3 reconstructed components (trend / oscillation / noise split)."""

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0]
        from pyts.decomposition import SingularSpectrumAnalysis
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                ws = max(3, min(len(win) // 2, 10))
                ws = min(ws, len(win) - 1)
                ssa = SingularSpectrumAnalysis(window_size=ws, groups=3)
                comps = ssa.fit_transform(np.asarray(win, dtype=float).reshape(1, -1))[0]
                return [float(np.var(comps[k])) for k in range(3)]
            except Exception:
                return [0.0, 0.0, 0.0]


def ssa_node(col: int = 0, W: int = 64, name: str = "pyts_ssa") -> SSANode:
    return SSANode(
        name, "pyts Singular-Spectrum-Analysis component variances (3) + sklearn readout.",
        col=col, W=W)


# --------------------------------------------------------------------------- #
#  6. filterpy 1-D constant-velocity Kalman level / velocity / residual
# --------------------------------------------------------------------------- #
class KalmanLevelNode(_Base):
    """Per-window 1-D constant-velocity Kalman filter (filterpy): features =
    [filtered level, filtered velocity, last innovation/residual]."""

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0]
        from filterpy.kalman import KalmanFilter
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                kf = KalmanFilter(dim_x=2, dim_z=1)
                kf.x = np.array([float(win[0]), 0.0])
                kf.F = np.array([[1.0, 1.0], [0.0, 1.0]])
                kf.H = np.array([[1.0, 0.0]])
                kf.P *= 10.0
                kf.R = np.array([[1.0]])
                kf.Q = np.array([[1e-3, 0.0], [0.0, 1e-3]])
                resid = 0.0
                for z in win:
                    kf.predict()
                    resid = float(z) - float((kf.H @ kf.x)[0])
                    kf.update(float(z))
                return [float(kf.x[0]), float(kf.x[1]), float(resid)]
            except Exception:
                return [0.0, 0.0, 0.0]


def kalman_level_node(col: int = 0, W: int = 64,
                      name: str = "filterpy_kalman") -> KalmanLevelNode:
    return KalmanLevelNode(
        name, "filterpy constant-velocity Kalman level/velocity/residual + sklearn readout.",
        col=col, W=W)


# --------------------------------------------------------------------------- #
#  7. numpy Random-Matrix-Theory (Marchenko-Pastur) eigen signal count
# --------------------------------------------------------------------------- #
class RMTSignalNode(_Base):
    """Marchenko-Pastur signal detection over a trailing window of the FULL
    feature matrix (last W rows): correlation-matrix eigenvalues above the noise
    edge lambda+ = (1 + sqrt(d/W))^2 are real structure. Features =
    [count of eigenvalues above lambda+, largest eigenvalue]. Uses all columns."""

    def _features(self, win: list[float]) -> list[float]:   # unused (see _augment)
        return [0.0, 0.0]

    def _augment(self, X: Matrix) -> np.ndarray:
        Xa = np.asarray(X, dtype=float)
        n, d = Xa.shape
        out = []
        for i in range(n):
            win = Xa[max(0, i - self.W + 1):i + 1]
            out.append(list(map(float, Xa[i])) + self._rmt_feats(win, d))
        return np.asarray(out, dtype=float)

    @staticmethod
    def _rmt_feats(win: np.ndarray, d: int) -> list[float]:
        T = win.shape[0]
        if T < max(8, d + 2) or d < 2:
            return [0.0, 0.0]
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                C = np.nan_to_num(np.corrcoef(win, rowvar=False))
                ev = np.linalg.eigvalsh(C)
                lam_plus = (1.0 + np.sqrt(d / T)) ** 2
                count = float(np.sum(ev > lam_plus))
                largest = float(np.max(ev))
            except Exception:
                return [0.0, 0.0]
        return [count, largest]


def rmt_signal_node(W: int = 64, name: str = "rmt_mp") -> RMTSignalNode:
    return RMTSignalNode(
        name, "numpy Marchenko-Pastur eigen signal count over full-matrix window + sklearn readout.",
        col=0, W=W)


# --------------------------------------------------------------------------- #
#  8. nistrng NIST SP800-22 randomness-test statistics on the sign stream
# --------------------------------------------------------------------------- #
class NISTRandomnessNode(_Base):
    """Per-window randomness fingerprint: the window is binarized by the sign of
    its first differences (up=1 / down=0) and a few fast NIST SP800-22 tests are
    run; features = their p-values [monobit, frequency-within-block, runs].
    Low p-values flag structure (non-random) rather than noise."""

    _TESTS = ("monobit", "frequency_within_block", "runs")

    def _features(self, win: list[float]) -> list[float]:
        if len(win) < 8:
            return [0.0, 0.0, 0.0]
        import nistrng
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            diffs = np.diff(np.asarray(win, dtype=float))
            bits = (diffs > 0).astype(np.int64)
            if bits.size < 8:
                return [0.0, 0.0, 0.0]
            feats: list[float] = []
            try:
                seq = nistrng.pack_sequence(bits)
                for nm in self._TESTS:
                    try:
                        res = nistrng.run_by_name_battery(
                            nm, seq, nistrng.SP800_22R1A_BATTERY)
                        if res:
                            v = float(res[0].score)
                            feats.append(v if np.isfinite(v) else 0.0)
                        else:
                            feats.append(0.0)
                    except Exception:
                        feats.append(0.0)
            except Exception:
                return [0.0, 0.0, 0.0]
        return (feats + [0.0, 0.0, 0.0])[:3]


def nist_randomness_node(col: int = 0, W: int = 64,
                         name: str = "nistrng_tests") -> NISTRandomnessNode:
    return NISTRandomnessNode(
        name, "nistrng SP800-22 randomness statistics on the sign stream + sklearn readout.",
        col=col, W=W)
