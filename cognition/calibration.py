"""cognition/calibration.py — knowing what it knows; abstain + ask for help (Phase P4.5).

"Knows what it knows / abstains / asks for help." The brain attaches a *confidence* to each
answer (from its reasoning evidence). This layer turns raw confidence into a principled
decision to ANSWER or ABSTAIN-and-escalate-to-the-human, with real reused tools:

  * **conformal selective prediction** — the gate. On held-out (confidence, was_correct) pairs
    we compute a distribution-free threshold τ on the calibrated reliability probability such
    that, among answers the brain *does* give, the error rate is held at or below the chosen
    risk α = 1 − confidence_level (split-conformal selective classification, with the finite-
    sample (n+1) correction). The brain answers iff calibrated_p ≥ τ; otherwise it abstains and
    escalates. This is monotonic and intuitive (more evidence → more likely to answer).

  * **netcal** ``LogisticCalibration`` + ``ECE`` recalibrates the raw confidence into an honest
    probability and measures Expected Calibration Error — so the reported confidence means what
    it says (over-confidence is detected, not hidden).

  * **MAPIE** ``SplitConformalClassifier`` runs alongside as an auxiliary conformal *prediction
    set* (the project's existing conformal pick) surfaced in the decision for transparency; the
    answer/abstain GATE is the monotonic selective threshold above. (crepes is the BSD
    alternative for the conformal layer.)

Pure-CPU, deterministic, offline. Degrades to a quantile abstention threshold if a library or
the calibration data is unavailable — it always makes a safe decision, never crashes.
"""
from __future__ import annotations

import numpy as np

# class indices for the binary "is the answer reliable?" problem
_UNRELIABLE, _RELIABLE = 0, 1


class CalibratedAbstainer:
    """Conformal abstention + calibration over answer-confidence (MAPIE + netcal)."""

    def __init__(self, *, confidence_level: float = 0.9, min_calib: int = 30):
        self.confidence_level = float(confidence_level)
        self.min_calib = int(min_calib)
        self.fitted = False
        self.engine = "fallback"
        self._scc = None          # MAPIE SplitConformalClassifier (auxiliary prediction set)
        self._netcal = None       # netcal LogisticCalibration
        self._threshold = 0.5     # conformal selective threshold τ on calibrated_p
        self.ece_raw = None
        self.ece_calibrated = None
        self.empirical_risk = None  # error rate among answered, on the calibration split
        self.n_calib = 0

    # ── fit on a calibration set ────────────────────────────────────────────────────
    def calibrate(self, confidences, correct) -> "CalibratedAbstainer":
        """Fit on (confidence, was_correct) history. confidences∈[0,1], correct∈{0,1}."""
        conf = np.asarray(confidences, dtype=float).ravel()
        y = np.asarray(correct, dtype=int).ravel()
        self.n_calib = int(conf.size)
        if conf.size < self.min_calib or len(np.unique(y)) < 2:
            self._fit_fallback(conf, y)
            return self
        try:
            self._fit_netcal(conf, y)                 # calibrated reliability probability
            self._fit_selective(conf, y)              # conformal selective threshold τ (the gate)
            self._fit_conformal(conf, y)              # MAPIE prediction set (auxiliary)
            self.engine = "conformal+netcal"
            self.fitted = True
        except Exception:
            self._fit_fallback(conf, y)
        return self

    def _fit_selective(self, conf, y) -> None:
        """Conformal selective threshold τ: smallest τ on calibrated_p keeping answered-error ≤ α."""
        p = self._batch_calibrated(conf)
        alpha = 1.0 - self.confidence_level
        order = np.argsort(-p)                         # consider most-confident-first
        best_tau, best_risk = float(np.max(p)) + 1e-6, 1.0
        n = p.size
        for i in range(n):
            tau = p[order[i]]
            ans = p >= tau
            k = int(ans.sum())
            if k == 0:
                continue
            errs = int(((1 - y)[ans]).sum())
            # finite-sample conformal upper bound on the answered-error rate
            risk = (errs + 1) / (k + 1)
            if risk <= alpha:
                best_tau, best_risk = float(tau), float(errs / k)
        self._threshold = best_tau
        self.empirical_risk = round(best_risk, 4)

    def _fit_conformal(self, conf, y) -> None:
        from mapie.classification import SplitConformalClassifier
        from sklearn.linear_model import LogisticRegression
        X = conf.reshape(-1, 1)
        # split: half to train the reliability model, half to conformalize (coverage guarantee)
        rng = np.random.default_rng(0)
        idx = rng.permutation(conf.size)
        cut = conf.size // 2
        tr, ca = idx[:cut], idx[cut:]
        clf = LogisticRegression().fit(X[tr], y[tr])
        scc = SplitConformalClassifier(estimator=clf, confidence_level=self.confidence_level,
                                       prefit=True)
        scc.conformalize(X[ca], y[ca])
        self._scc = scc
        self._clf = clf

    def _batch_calibrated(self, conf):
        if self._netcal is not None:
            try:
                return np.asarray(self._netcal.transform(np.asarray(conf, dtype=float))).ravel()
            except Exception:
                pass
        return np.asarray(conf, dtype=float).ravel()

    def _fit_netcal(self, conf, y) -> None:
        from netcal.metrics import ECE
        from netcal.scaling import LogisticCalibration
        nc = LogisticCalibration()
        nc.fit(conf, y)
        self._netcal = nc
        try:
            self.ece_raw = round(float(ECE(10).measure(conf, y)), 4)
            self.ece_calibrated = round(float(ECE(10).measure(np.asarray(nc.transform(conf)).ravel(), y)), 4)
        except Exception:
            pass

    def _fit_fallback(self, conf, y) -> None:
        # threshold = midpoint between mean confidence of correct vs incorrect answers
        self.engine = "fallback"
        if conf.size and len(np.unique(y)) == 2:
            hi = conf[y == _RELIABLE].mean()
            lo = conf[y == _UNRELIABLE].mean()
            self._threshold = float((hi + lo) / 2)
        elif conf.size:
            self._threshold = float(np.quantile(conf, 0.5))
        self.fitted = conf.size > 0

    # ── decide on a new answer ──────────────────────────────────────────────────────
    def decide(self, confidence: float) -> dict:
        """ANSWER vs ABSTAIN-and-escalate for an answer with the given confidence."""
        c = float(max(0.0, min(1.0, confidence)))
        calibrated = self._calibrated_prob(c)
        # GATE: conformal selective threshold on calibrated reliability probability
        answer = calibrated >= self._threshold
        if self.engine.startswith("conformal"):
            reason = (f"calibrated p={calibrated:.2f} ≥ τ={self._threshold:.2f}: confident "
                      "enough to answer (conformal risk ≤ "
                      f"{1 - self.confidence_level:.2f})") if answer else \
                     (f"calibrated p={calibrated:.2f} < τ={self._threshold:.2f}: not confident "
                      "— escalate to the human")
        else:
            reason = "above threshold" if answer else "below confidence threshold"
        # auxiliary MAPIE conformal prediction set (transparency, not the gate)
        aux_set = self._mapie_set(c)
        return {
            "answer": bool(answer),
            "abstain": not bool(answer),
            "escalate_to_human": not bool(answer),
            "confidence": round(c, 4),
            "calibrated_confidence": round(calibrated, 4),
            "threshold": round(self._threshold, 4),
            "prediction_set": [_RELIABLE] if answer else [_UNRELIABLE],
            "mapie_conformal_set": aux_set,
            "reason": reason,
            "engine": self.engine,
        }

    def _mapie_set(self, c: float):
        if self._scc is None:
            return None
        try:
            classes, mask = self._scc.predict_set(np.array([[c]]))
            return sorted(int(cls) for cls, m in zip(classes, mask[0])
                          if bool(np.asarray(m).ravel()[0]))
        except Exception:
            return None

    def _calibrated_prob(self, c: float) -> float:
        if self._netcal is not None:
            try:
                return float(np.asarray(self._netcal.transform(np.array([c]))).ravel()[0])
            except Exception:
                pass
        return c

    @staticmethod
    def _reason(present: set) -> str:
        if present == {_RELIABLE}:
            return "conformal set = {reliable}: confident enough to answer"
        if present == {_UNRELIABLE}:
            return "conformal set = {unreliable}: not confident — escalate to human"
        if present == {_UNRELIABLE, _RELIABLE}:
            return "conformal set ambiguous {both}: cannot rule out error — ask the human"
        return "conformal set empty: no coverage at this confidence — ask the human"

    def status(self) -> dict:
        return {"engine": self.engine, "fitted": self.fitted,
                "confidence_level": self.confidence_level, "n_calib": self.n_calib,
                "ece_raw": self.ece_raw, "ece_calibrated": self.ece_calibrated,
                "threshold": round(self._threshold, 4), "empirical_risk": self.empirical_risk}
