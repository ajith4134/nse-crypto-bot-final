"""Drift monitoring (Tier-3 infra, group K of the model catalog).

Two complementary detectors, reuse-first:
  * batch data/target drift via Evidently (reference vs current window)
  * streaming concept-drift via River's ADWIN on a prediction-error stream

Both degrade gracefully (numeric fallback) so callers never break. This gives the
self-evolve loop a real "the market changed" trigger instead of a timer.

    from core.drift import data_drift, StreamingDriftDetector
    rep = data_drift(reference_X, current_X)      # {"drift_share":..,"drifted":bool,..}
    det = StreamingDriftDetector()
    for err in errors:
        if det.update(err): print("drift!")
"""
from __future__ import annotations

import warnings

import numpy as np


def data_drift(reference, current, threshold: float = 0.5) -> dict:
    """Share of columns whose distribution drifted (reference vs current window).
    Uses Evidently if available; else a Kolmogorov-Smirnov fallback."""
    ref = np.asarray(reference, float)
    cur = np.asarray(current, float)
    ref[~np.isfinite(ref)] = 0.0
    cur[~np.isfinite(cur)] = 0.0
    try:
        import pandas as pd
        from evidently import Report
        from evidently.presets import DataDriftPreset
        cols = [f"f{i}" for i in range(ref.shape[1])]
        rdf, cdf = pd.DataFrame(ref, columns=cols), pd.DataFrame(cur, columns=cols)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rep = Report(metrics=[DataDriftPreset()]).run(reference_data=rdf, current_data=cdf)
            d = rep.dict()
        # locate the drift-share metric across evidently versions
        share, ndrift = _extract_evidently_share(d)
        if share is not None:
            return {"backend": "evidently", "drift_share": float(share),
                    "n_drifted": int(ndrift), "drifted": float(share) >= threshold}
    except Exception:
        pass
    # KS fallback
    from scipy import stats
    drifted = 0
    for j in range(ref.shape[1]):
        try:
            p = stats.ks_2samp(ref[:, j], cur[:, j]).pvalue
        except Exception:
            p = 1.0
        drifted += int(p < 0.05)
    share = drifted / max(1, ref.shape[1])
    return {"backend": "ks", "drift_share": float(share), "n_drifted": int(drifted),
            "drifted": share >= threshold}


def _extract_evidently_share(d):
    """Best-effort pull of drift-share + count from Evidently's nested result dict."""
    found_share, found_n = None, 0
    stack = [d]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                kl = str(k).lower()
                if kl in ("share_of_drifted_columns", "drift_share") and isinstance(v, (int, float)):
                    found_share = v
                if kl in ("number_of_drifted_columns", "n_drifted_features") and isinstance(v, (int, float)):
                    found_n = v
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return found_share, found_n


class StreamingDriftDetector:
    """River ADWIN concept-drift detector over a scalar error/pnl stream. update(x)
    returns True on the step a change is detected. Page-Hinkley fallback if River absent."""

    def __init__(self, delta: float = 0.002):
        self.backend = "adwin"
        try:
            from river import drift
            self._d = drift.ADWIN(delta=delta)
        except Exception:
            self.backend = "page_hinkley_fallback"
            self._d = None
            self._mean = 0.0
            self._n = 0
            self._cum = 0.0
            self._min = 0.0
            self._lambda = 5.0

    def update(self, x: float) -> bool:
        x = float(x)
        if self._d is not None:
            self._d.update(x)
            return bool(self._d.drift_detected)
        # Page-Hinkley
        self._n += 1
        self._mean += (x - self._mean) / self._n
        self._cum += x - self._mean - 0.005
        self._min = min(self._min, self._cum)
        return (self._cum - self._min) > self._lambda
