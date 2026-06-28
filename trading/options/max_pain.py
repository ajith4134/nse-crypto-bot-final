"""trading/options/max_pain.py — Max Pain strike per expiry (T4 §6 of features).

Max Pain = the expiry settlement price at which the TOTAL intrinsic value paid out
to option buyers (equivalently, the loss to option writers) is MINIMISED. Folklore
says price tends to gravitate there into expiry because writers (who are net short)
are incentivised to pin it. We compute it exactly by evaluating total pain at every
listed strike and taking the minimum.

At candidate settlement S:
    call pain(S) = Σ_{K < S} call_oi[K] · (S − K)     # ITM calls pay out
    put  pain(S) = Σ_{K > S} put_oi[K]  · (K − S)     # ITM puts  pay out

Inputs are plain {strike: open_interest} dicts (per single expiry). Pure Python.
"""
from __future__ import annotations


def _pain_at(settle: float, call_oi: dict[float, float], put_oi: dict[float, float]) -> float:
    call_pain = sum(oi * (settle - k) for k, oi in call_oi.items() if k < settle)
    put_pain = sum(oi * (k - settle) for k, oi in put_oi.items() if k > settle)
    return call_pain + put_pain


def max_pain(call_oi: dict[float, float], put_oi: dict[float, float]) -> dict:
    """Return the max-pain strike + the full pain curve for one expiry."""
    strikes = sorted(set(call_oi) | set(put_oi))
    if not strikes:
        raise ValueError("need at least one strike with open interest")
    curve = {k: _pain_at(k, call_oi, put_oi) for k in strikes}
    mp = min(curve, key=curve.get)
    return {
        "max_pain_strike": mp,
        "min_pain_value": curve[mp],
        "pain_curve": curve,
        "strikes": strikes,
        "total_call_oi": sum(call_oi.values()),
        "total_put_oi": sum(put_oi.values()),
    }
