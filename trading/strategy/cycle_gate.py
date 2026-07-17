"""trading/strategy/cycle_gate.py — the random-walk-null gate for cycle-citing strategies.

Owner's 2026-07-17 Fourier-debunk video (research/video/fourier-debunk/), every claim
verified: a pure random walk "shows" a dominant multi-year cycle under the DFT (the periodic-
extension cliff manufactures the low-frequency peak — 98.7% of random walks report one), an
8-harmonic fit reaches in-sample R²=1.0 yet forecasts 2.84× WORSE than the martingale
'tomorrow = today', and a random walk's RETURNS spectrum is flat. Therefore:

  1. cycle claims are tested on RETURNS (stationary), never price levels;
  2. the series is demeaned + Hann-windowed (kills the seam/leakage artifact);
  3. the observed dominant-peak share must beat a PERMUTATION null — the same statistic on
     shuffled returns, which destroys any real cycle while keeping the marginal distribution;
  4. the naive martingale baseline is computed alongside, so any forecast-flavored claim has
     the number it must beat on record.

Wired into StrategyFoundry.promote(): a spec whose name/idea/family/reference cites cycles
(fourier/period/seasonal/harmonic/MESA/Hilbert/…) can only promote if its segment's reference
series actually CONTAINS a significant cycle. Non-cycle strategies are untouched. Data
missing → gate degrades open with the reason recorded (mirrors the reasoning-verifier
pattern) — absence of data is not evidence against the strategy.

Pure numpy + stdlib; no network; never raises from gate().
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_CYCLE_RX = re.compile(
    r"(?i)\b(fourier|fft|spectral|cycle|cyclic|cyclical|period(?:ic|icity)?|season(?:al|ality)?"
    r"|harmonic|mesa|hilbert|sine\s?wave|ehlers|dominant\s?cycle)\b")

_SIMS = int(os.environ.get("CYCLE_GATE_SIMS", "200") or 200)
_ALPHA = float(os.environ.get("CYCLE_GATE_ALPHA", "0.05") or 0.05)


def is_cycle_citing(*texts) -> bool:
    """True when any of the strategy's descriptive texts claims a cycle/periodicity edge."""
    return any(t and _CYCLE_RX.search(str(t)) for t in texts)


def martingale_baseline(closes) -> dict:
    """The two numbers every direction/forecast claim must beat, from the same series:
    persistence sign-accuracy (sign(r_t)==sign(r_{t+1})) and the base up-rate. The optimal
    point forecast of a martingale IS 'tomorrow = today' — an in-sample fit means nothing
    until it beats these out-of-sample."""
    import numpy as np
    c = np.asarray([float(x) for x in closes], dtype="float64")
    if c.size < 20 or not np.all(c > 0):
        return {"n": int(c.size), "persistence_acc": None, "up_rate": None}
    r = np.diff(np.log(c))
    r = r[r != 0.0]
    if r.size < 10:
        return {"n": int(r.size), "persistence_acc": None, "up_rate": None}
    same = np.sign(r[1:]) == np.sign(r[:-1])
    return {"n": int(r.size),
            "persistence_acc": round(float(same.mean()), 4),
            "up_rate": round(float((r > 0).mean()), 4)}


def _peak_share(r, np) -> float:
    """Dominant-peak share of a demeaned, Hann-windowed returns series' power spectrum
    (DC excluded). The statistic the video showed exploding on raw price levels."""
    x = (r - r.mean()) * np.hanning(r.size)
    p = np.abs(np.fft.rfft(x)) ** 2
    p = p[1:]                                   # drop DC
    tot = p.sum()
    return float(p.max() / tot) if tot > 0 else 0.0


def spectral_null_test(closes, *, n_sims: int = _SIMS, seed: int = 7) -> dict:
    """Does this series contain a REAL cycle? Observed dominant-peak share of the RETURNS
    spectrum vs a permutation null (shuffled returns × n_sims). Returns {passed, p_value,
    peak_share, null_med, n} — passed=True only when the peak beats the null at _ALPHA."""
    import numpy as np
    c = np.asarray([float(x) for x in closes], dtype="float64")
    if c.size < 128 or not np.all(c > 0):
        return {"passed": False, "p_value": None, "peak_share": None,
                "null_med": None, "n": int(c.size), "reason": "insufficient data"}
    r = np.diff(np.log(c))
    obs = _peak_share(r, np)
    rng = np.random.default_rng(seed)
    null = np.empty(n_sims)
    for i in range(n_sims):
        null[i] = _peak_share(rng.permutation(r), np)
    p_value = float((1 + (null >= obs).sum()) / (n_sims + 1))
    return {"passed": p_value < _ALPHA, "p_value": round(p_value, 4),
            "peak_share": round(obs, 6), "null_med": round(float(np.median(null)), 6),
            "n": int(r.size)}


def _reference_closes(segment: str) -> list[float] | None:
    """The segment's reference series for the null test: the local BTC perp 5m feather
    (zero network, same data the truth ledger labels from). None when absent."""
    try:
        from trading.direction.truth_ledger import _candle_dir
        p = Path(_candle_dir()) / "futures" / "BTC_USDT_USDT-5m-futures.feather"
        if not p.exists():
            return None
        import pandas as pd
        df = pd.read_feather(p, columns=["close"])
        closes = df["close"].to_numpy()[-4096:]
        return closes.tolist() if len(closes) >= 128 else None
    except Exception:
        return None


def gate(segment: str, *texts, closes=None) -> dict:
    """The promotion-side check. Not cycle-citing → {required: False, passed: True}.
    Cycle-citing → the reference series must contain a significant cycle. No data →
    degraded-open with the reason recorded (never blocks on infrastructure absence)."""
    try:
        if not is_cycle_citing(*texts):
            return {"required": False, "passed": True}
        series = closes if closes is not None else _reference_closes(segment)
        if series is None:
            return {"required": True, "passed": True, "degraded": True,
                    "reason": "no reference series (gate skipped, recorded)"}
        rep = spectral_null_test(series)
        rep.update({"required": True, "baseline": martingale_baseline(series)})
        return rep
    except Exception as e:
        return {"required": True, "passed": True, "degraded": True,
                "reason": f"gate error: {str(e)[:80]}"}
