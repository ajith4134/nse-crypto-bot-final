"""Risk-map overlay — CANON-49 (JKA-07..10 spec, made honest).

The JKA video's "proprietary risk map", implemented openly:
  1. neutral-zone DEAD BAND around the signal — abstain (position 0) when the
     up-probability sits within +/- dead_band of 0.5 (or an expected-return
     signal within +/- dead_band of 0.0);
  2. INVERSE-FORECAST-VOL sizing — position magnitude ~ target_risk / sigma_hat
     (risk-parity per trade);
  3. HARD EXPOSURE CAP — |position| never exceeds exposure_cap.

sigma_hat comes from `forecast_sigma`: arch (installed) GARCH(1,1) one-step
volatility forecast, with a numpy EWMA (RiskMetrics lambda=0.94) fallback for
short histories or fit failures. Overlay logic is from-scratch (~50 lines; the
stitch map found no OSS for this exact shape)."""
from __future__ import annotations

import numpy as np

# arch needs enough history for a sane GARCH(1,1) MLE fit
_MIN_GARCH_OBS = 100
_EWMA_LAMBDA = 0.94


class RiskOverlay:
    """position(signal, sigma_hat) -> signed fraction of capital in [-cap, cap].

    signal: an up-probability in [0, 1] (dead band around 0.5) OR any signed
    expected-return-like signal (dead band around 0.0). dead_band is expressed
    in the signal's own units."""

    def __init__(self, dead_band: float = 0.05, target_risk: float = 0.01,
                 exposure_cap: float = 1.0):
        assert dead_band >= 0 and target_risk > 0 and exposure_cap > 0
        self.dead_band = float(dead_band)
        self.target_risk = float(target_risk)
        self.exposure_cap = float(exposure_cap)

    def _edge(self, signal: float) -> float:
        """Signed edge: probability -> distance from 0.5; return -> itself."""
        s = float(signal)
        if 0.0 <= s <= 1.0:
            return s - 0.5                                   # probability mode
        return s                                             # return mode

    def position(self, signal: float, sigma_hat: float) -> float:
        """Signed fraction of capital. 0.0 inside the dead band (abstain);
        otherwise sign(edge) * min(target_risk / sigma_hat, exposure_cap)."""
        edge = self._edge(signal)
        if abs(edge) <= self.dead_band:                      # JKA-08 dead band
            return 0.0
        sigma = max(float(sigma_hat), 1e-12)
        size = self.target_risk / sigma                      # JKA-09 inv-vol
        size = min(size, self.exposure_cap)                  # JKA-10 hard cap
        return float(np.sign(edge) * size)

    def positions(self, signals, sigma_hats) -> np.ndarray:
        """Vectorized convenience over aligned arrays."""
        signals = np.asarray(signals, float)
        sigma_hats = np.asarray(sigma_hats, float)
        assert signals.shape == sigma_hats.shape
        return np.array([self.position(s, v)
                         for s, v in zip(signals, sigma_hats)])


def forecast_sigma(returns, horizon: int = 1) -> float:
    """One-step-ahead volatility forecast of a return series (per-bar sigma,
    same units as `returns`).

    Primary: arch GARCH(1,1) (returns scaled x100 for optimizer conditioning,
    the arch-docs convention, then scaled back). Fallback for short histories
    (< 100 obs) or fit failure: numpy EWMA variance, RiskMetrics lambda=0.94."""
    r = np.asarray(returns, float).reshape(-1)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return 0.0
    if len(r) >= _MIN_GARCH_OBS:
        try:
            from arch import arch_model
            am = arch_model(r * 100.0, vol="GARCH", p=1, q=1, mean="Zero")
            res = am.fit(disp="off", show_warning=False)
            fc = res.forecast(horizon=int(horizon), reindex=False)
            var = float(fc.variance.values[-1, int(horizon) - 1])
            if np.isfinite(var) and var > 0:
                return float(np.sqrt(var) / 100.0)
        except Exception:
            pass                                             # honest fallback
    return _ewma_sigma(r)


def _ewma_sigma(r: np.ndarray, lam: float = _EWMA_LAMBDA) -> float:
    """RiskMetrics EWMA volatility: var_t = lam*var_{t-1} + (1-lam)*r_t^2."""
    var = float(np.var(r[: max(2, min(20, len(r)))]))        # seed variance
    for x in r:
        var = lam * var + (1.0 - lam) * float(x) ** 2
    return float(np.sqrt(max(var, 0.0)))
