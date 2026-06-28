"""trading/options/pcr.py — Put/Call Ratio, OI and volume (T4 §5 of features).

PCR-OI     = Σ put OI     / Σ call OI
PCR-Volume = Σ put volume / Σ call volume

Read contrarian-ly: a high PCR (lots of puts) is often a bottoming/oversold tell,
a very low PCR a frothy/overbought one. We return both the aggregate and a
per-strike breakdown so the dashboard can show where the put/call skew sits.

Inputs are plain {strike: value} dicts. Pure Python, deterministic.
"""
from __future__ import annotations


def _ratio(put_total: float, call_total: float) -> float | None:
    if call_total <= 0:
        return None                  # undefined; don't fabricate an infinity
    return put_total / call_total


def put_call_ratio(call_oi: dict[float, float], put_oi: dict[float, float], *,
                   call_volume: dict[float, float] | None = None,
                   put_volume: dict[float, float] | None = None) -> dict:
    """Aggregate + per-strike PCR for OI and (optionally) volume."""
    strikes = sorted(set(call_oi) | set(put_oi))
    per_strike = {}
    for k in strikes:
        c, p = call_oi.get(k, 0.0), put_oi.get(k, 0.0)
        per_strike[k] = {"call_oi": c, "put_oi": p, "pcr_oi": _ratio(p, c)}

    out = {
        "pcr_oi": _ratio(sum(put_oi.values()), sum(call_oi.values())),
        "total_call_oi": sum(call_oi.values()),
        "total_put_oi": sum(put_oi.values()),
        "per_strike": per_strike,
    }
    if call_volume is not None and put_volume is not None:
        out["pcr_volume"] = _ratio(sum(put_volume.values()), sum(call_volume.values()))
        out["total_call_volume"] = sum(call_volume.values())
        out["total_put_volume"] = sum(put_volume.values())
    return out
