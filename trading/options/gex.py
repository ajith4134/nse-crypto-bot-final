"""trading/options/gex.py — dealer Gamma Exposure (GEX) + zero-gamma level (T4 §7).

GEX estimates how much delta dealers must hedge per 1% move, by strike. The widely
used (SqueezeMetrics-style) convention treats call gamma as POSITIVE dealer exposure
and put gamma as NEGATIVE:

    GEX_strike = spot² · 0.01 · contract_size · gamma · (call_oi − put_oi)

Positive total GEX ⇒ dealers are long gamma ⇒ they sell rallies / buy dips ⇒
volatility is dampened (mean-reverting). Negative GEX ⇒ short gamma ⇒ they chase ⇒
moves amplify. The **zero-gamma (flip) level** is the spot where cumulative GEX
crosses zero — the regime boundary.

This is an ESTIMATE of dealer positioning under the standard sign convention; it is
labelled as such and never presented as the exchange's own number. Pure Python.
"""
from __future__ import annotations


def gamma_exposure(strikes: list[dict], *, spot: float, contract_size: float = 1.0) -> dict:
    """Per-strike + total GEX.

    `strikes`: list of {"strike", "gamma", "call_oi", "put_oi"} (gamma = per-unit
    Black-76 gamma at that strike). Returns per-strike GEX, the total, and the
    largest positive/negative gamma walls.
    """
    if spot <= 0:
        raise ValueError("spot must be > 0")
    scale = spot * spot * 0.01 * contract_size
    per_strike = []
    total = 0.0
    for row in strikes:
        k = float(row["strike"])
        gamma = float(row.get("gamma", 0.0))
        net_oi = float(row.get("call_oi", 0.0)) - float(row.get("put_oi", 0.0))
        gex = scale * gamma * net_oi
        total += gex
        per_strike.append({"strike": k, "gex": gex, "gamma": gamma, "net_oi": net_oi})
    per_strike.sort(key=lambda r: r["strike"])
    call_wall = max(per_strike, key=lambda r: r["gex"], default=None)
    put_wall = min(per_strike, key=lambda r: r["gex"], default=None)
    return {
        "total_gex": total,
        "regime": "positive" if total > 0 else ("negative" if total < 0 else "neutral"),
        "per_strike": per_strike,
        "call_wall": call_wall["strike"] if call_wall else None,   # biggest +GEX strike
        "put_wall": put_wall["strike"] if put_wall else None,      # biggest −GEX strike
        "zero_gamma": zero_gamma_level(per_strike),
        "estimate": True,
    }


def zero_gamma_level(per_strike: list[dict]) -> float | None:
    """Spot at which CUMULATIVE GEX (by strike, low→high) crosses zero.

    Linearly interpolates between the two adjacent strikes that bracket the sign
    change. Returns None when cumulative GEX never changes sign.
    """
    rows = sorted(per_strike, key=lambda r: r["strike"])
    prev_k = None
    prev_cum = 0.0
    cum = 0.0
    for r in rows:
        cum_new = cum + r["gex"]
        # Crossing = prev cumulative and new cumulative straddle zero (opposite signs).
        if prev_k is not None and prev_cum * cum_new < 0.0:
            frac = (0.0 - prev_cum) / (cum_new - prev_cum)
            return prev_k + frac * (r["strike"] - prev_k)
        prev_k, prev_cum = r["strike"], cum_new
        cum = cum_new
    return None
