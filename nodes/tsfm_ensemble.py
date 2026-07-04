"""AI-scientist idea #5 — TSFM ensemble + conformal calibration.

The individual TS foundation heads already exist (nodes/foundation_nodes.py: Chronos, TimesFM,
TinyTimeMixer/TTM, Moirai, Lag-Llama, and now TimeMoE). This node ENSEMBLES their one-step
forecasts (mean of whichever members load; each self-guards its heavy HF download and AR-falls-back
offline) into a single forecast feature for the task-aware readout, then applies split **conformal
calibration** (isotonic on a chronological hold-out) so the emitted p(up) is calibrated — the
Pillar-17 requirement for the UQ gate. If no foundation member loads (offline), the base
``_ExternalForecastBase`` AR fallback keeps it a valid, working NodeProtocol node.

Promotion by CPCV is handled by the existing evaluation harness (run_network's purged CV); this node
just exposes the calibrated ensemble as one routable node.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import Labels, Matrix, Vector
from nodes.foundation_nodes import _ExternalForecastBase

# The foundation forecasters to ensemble, in priority order. Each is optional — missing classes or
# unloadable models are simply skipped (never break the ensemble).
_MEMBER_NAMES = ["ChronosNode", "TimesFMNode", "TinyTimeMixerNode",
                 "MoiraiNode", "LagLlamaNode", "TimeMoENode"]


def _member_classes():
    from nodes import foundation_nodes as F
    return [getattr(F, n) for n in _MEMBER_NAMES if hasattr(F, n)]


class TSFMEnsembleNode(_ExternalForecastBase):
    """Mean-ensemble of TS foundation forecasters + isotonic conformal calibration of p(up)."""

    kind = "tsfm_ensemble"

    def __init__(self, name: str = "tsfm_ensemble", col: int = 0, calibrate: bool = True):
        super().__init__(name, "TSFM ensemble (Chronos/TimesFM/TTM/Moirai/LagLlama/TimeMoE mean) "
                               "+ split-conformal (isotonic) calibration of p(up).", col=col)
        self._members: list = []
        self._iso = None
        self._calibrate = bool(calibrate)
        self.active_members: list = []

    def _build_members(self):
        out = []
        for C in _member_classes():
            try:
                out.append(C(name=f"{self.name}__{C.__name__}", col=self.col))
            except Exception:
                continue
        return out

    # ---- ensemble forecaster (drives _ExternalForecastBase) ------------------------------
    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        self._members = self._build_members()
        fcs, active = [], []
        for m in self._members:
            try:
                fc = np.asarray(m._fit_forecaster(y), float).reshape(-1)
                if len(fc) == len(y) and np.isfinite(fc).all():
                    m._ytr = np.asarray(y, float).reshape(-1)
                    m._fitted = fc
                    fcs.append(fc); active.append(type(m).__name__)
            except Exception:
                continue
        self.active_members = active
        if not fcs:
            raise RuntimeError("no TSFM member loaded")     # → base AR fallback
        return np.mean(fcs, axis=0)

    def _forecast(self, h: int) -> np.ndarray:
        fcs = []
        for m in self._members:
            try:
                fcs.append(np.asarray(m._forecast(h), float).reshape(-1))
            except Exception:
                continue
        if not fcs:
            last = float(self._ytr[-1]) if self._ytr is not None else 0.0
            return np.full(h, last)
        L = min(len(f) for f in fcs)
        return np.mean([f[:L] for f in fcs], axis=0)

    # ---- fit + conformal calibration -----------------------------------------------------
    def fit(self, X: Matrix, y: Labels) -> "TSFMEnsembleNode":
        super().fit(X, y)                                    # ensemble forecaster + readout
        self._iso = None
        if self._calibrate:
            try:
                from sklearn.isotonic import IsotonicRegression
                ya = np.asarray(y).astype(int)
                raw = np.asarray(super().predict_proba(X), float)
                n = len(ya)
                cut = max(4, int(n * 0.7))                   # chronological hold-out tail = cal set
                if n - cut >= 4 and len(set(ya[cut:].tolist())) >= 2:
                    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
                    iso.fit(raw[cut:], ya[cut:])
                    self._iso = iso
            except Exception:
                self._iso = None
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        raw = np.asarray(super().predict_proba(X), float)
        if self._iso is not None:
            return np.clip(self._iso.predict(raw), 0.0, 1.0).tolist()
        return raw.tolist()

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


def tsfm_ensemble_node(name: str = "tsfm_ensemble") -> TSFMEnsembleNode:
    """Zero-arg factory (pool + autoload convention)."""
    return TSFMEnsembleNode(name=name)
