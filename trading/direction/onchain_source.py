"""trading/direction/onchain_source.py — E5: the orphaned on-chain lane becomes a measured lens.

trading/altdata/onchain.py (free keyless Fear&Greed + BTC network flow + mempool whale proxy)
was flagged unwired on 2026-07-07 and again by the 2026-07-17 audit — a real, already-built
signal family that nothing consumed. This wraps its composite as truth-ledger source
"onchain_flow" under the standard lens contract (CONVENTIONS §16: weightless until earned).

Split matching the module's cost profile:
  • refresh()  — 3 guarded HTTP fetches (~8s worst case) → cached snapshot state file.
    Runs ONLY on the funnel's learning cadence (ONCHAIN_EVERY_S, default 900).
  • readings() — O(1) state-file read on the hot path. The composite is MARKET-level
    (BTC-network risk-on/off), so every candidate in a cycle sees the same lean — exactly
    like the breadth-tilt lens; the ledger measures whether that lean has any edge.

Abstains when |composite| < ONCHAIN_MIN_ABS (0.1), the snapshot is stale (> 2× refresh
interval), or the lane is disabled (ONCHAIN_SOURCE=0).
"""
from __future__ import annotations

import os
import time

from trading import state

_SNAP = "onchain_snapshot.json"
_LAST = [0.0]


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default) in ("1", "true", "TRUE", "yes", "on")


def enabled() -> bool:
    return _flag("ONCHAIN_SOURCE")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def refresh(force: bool = False) -> dict | None:
    """Fetch + cache the on-chain snapshot (learning cadence only — never the hot path)."""
    if not enabled():
        return None
    every = _f("ONCHAIN_EVERY_S", 900)
    if not force and time.time() - _LAST[0] < every:
        return None
    _LAST[0] = time.time()
    try:
        from trading.altdata.onchain import OnChainAltData
        snap = OnChainAltData().snapshot()
        snap["ts"] = time.time()
        state.save_json(_SNAP, snap)
        return snap
    except Exception as e:
        return {"available": False, "error": repr(e)}


def readings(symbol: str, *, segment: str = "futures",
             regime: str | None = None, record: bool = True) -> list[tuple[str, float]]:
    """Hot-path lens: cached composite → ('onchain_flow', p_up). Never fetches."""
    if not enabled():
        return []
    try:
        snap = state.load_json(_SNAP, {}) or {}
        if not snap.get("available"):
            return []
        if time.time() - float(snap.get("ts") or 0) > 2 * _f("ONCHAIN_EVERY_S", 900):
            return []                                  # stale cache → honest abstain
        comp = float(snap.get("composite") or 0.0)
        if abs(comp) < _f("ONCHAIN_MIN_ABS", 0.1):
            return []
        p = round(min(0.98, max(0.02, 0.5 + 0.15 * comp)), 4)
        if record:
            try:
                from trading.direction import truth_ledger as _tl
                flat = (symbol or "").replace("/", "").split(":")[0].upper()
                _tl.record(symbol=flat, market="CRYPTO", segment=segment or "futures",
                           direction=("LONG" if p >= 0.5 else "SHORT"),
                           source="onchain_flow",
                           confidence=(p if p >= 0.5 else 1.0 - p), regime=regime)
            except Exception:
                pass
        return [("onchain_flow", p)]
    except Exception:
        return []


def status() -> dict:
    snap = state.load_json(_SNAP, {}) or {}
    return {"enabled": enabled(), "available": bool(snap.get("available")),
            "composite": snap.get("composite"), "ts": snap.get("ts"),
            "sources_live": snap.get("sources_live")}
