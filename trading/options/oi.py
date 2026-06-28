"""trading/options/oi.py — OI heatmap aggregation + OI-change tracker (T4 §1 /oitracker).

Two things the OI panel needs:

  oi_heatmap   — normalise call/put OI per strike to [0,1] intensities so the
                 dashboard can colour a heatmap, plus flag the highest-OI strikes
                 (the "walls" that often act as support/resistance).
  OITracker    — diff OI between two snapshots and, combined with the price move,
                 classify the change the way an Indian options desk reads it:
                     price ↑ & OI ↑  → LONG buildup
                     price ↓ & OI ↑  → SHORT buildup
                     price ↑ & OI ↓  → SHORT covering
                     price ↓ & OI ↓  → LONG unwinding

Pure Python, deterministic. Inputs are {strike: oi} dicts / scalars.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def oi_heatmap(call_oi: dict[float, float], put_oi: dict[float, float], *, top_n: int = 3) -> dict:
    """Per-strike normalised OI intensities + the highest-OI call/put strikes."""
    strikes = sorted(set(call_oi) | set(put_oi))
    if not strikes:
        raise ValueError("need at least one strike")
    max_c = max(call_oi.values(), default=0.0) or 1.0
    max_p = max(put_oi.values(), default=0.0) or 1.0
    cells = []
    for k in strikes:
        c, p = call_oi.get(k, 0.0), put_oi.get(k, 0.0)
        cells.append({
            "strike": k, "call_oi": c, "put_oi": p,
            "call_intensity": c / max_c, "put_intensity": p / max_p,
        })
    call_walls = sorted(call_oi, key=call_oi.get, reverse=True)[:top_n]
    put_walls = sorted(put_oi, key=put_oi.get, reverse=True)[:top_n]
    return {
        "cells": cells,
        "call_walls": call_walls,   # likely resistance
        "put_walls": put_walls,     # likely support
        "max_call_oi": max(call_oi.values(), default=0.0),
        "max_put_oi": max(put_oi.values(), default=0.0),
    }


def classify_oi_change(price_change: float, oi_change: float) -> str:
    """The four-quadrant desk reading of a (price, OI) move."""
    if oi_change > 0:
        return "long_buildup" if price_change > 0 else \
               ("short_buildup" if price_change < 0 else "buildup")
    if oi_change < 0:
        return "short_covering" if price_change > 0 else \
               ("long_unwinding" if price_change < 0 else "unwinding")
    return "flat"


@dataclass
class OITracker:
    """Diffs successive OI snapshots per strike and classifies the move."""

    _prev_oi: dict[float, float] = field(default_factory=dict, init=False)
    _prev_price: float | None = field(default=None, init=False)

    def update(self, oi_by_strike: dict[float, float], price: float) -> dict:
        """Feed a new snapshot; return per-strike OI deltas + classification."""
        changes = {}
        price_change = 0.0 if self._prev_price is None else price - self._prev_price
        for k, oi in oi_by_strike.items():
            prev = self._prev_oi.get(k, oi)            # first sight → no change
            d = oi - prev
            changes[k] = {
                "oi": oi, "oi_change": d,
                "signal": classify_oi_change(price_change, d) if self._prev_price is not None
                else "init",
            }
        self._prev_oi = dict(oi_by_strike)
        self._prev_price = price
        return {"price": price, "price_change": price_change, "per_strike": changes}
