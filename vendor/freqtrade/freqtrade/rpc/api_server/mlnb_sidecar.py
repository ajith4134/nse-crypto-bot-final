# mlnb: brain-native API fields (fork workstream E2, 2026-07-10).
#
# The brain (funnel/dashboard, a SEPARATE process tree) persists its live state as plain
# JSON under the project state dir. This module reads those sidecars mtime-cached and
# enriches every trade the API serves with the brain's fields SAME-ORIGIN, so FreqUI
# never needs the fragile cross-origin overlay again (root of the 2026-07-10 fabricated
# 🔒 incident: overlay unreachable → UI invented a lock the brain never set).
#
# Honesty rules:
#  - Serve only what a sidecar actually recorded; a missing file/entry → None, never a
#    fabricated value.
#  - brain_pred/strategy_label are ENTRY-TIME facts from crypto_entry_meta.json (what the
#    brain thought when it opened the trade). LIVE re-scoring (nn_pred) needs the torch
#    net and stays on the dashboard; FreqUI may layer it on top when reachable.
#  - Never raise into a request: any sidecar problem degrades to None fields.
#
# Config: "mlnb_state_dir" (falls back to $MLNB_STATE_DIR, then ~/trading/state).
# Kill-switch: "mlnb_native_fields": false.
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

_LOCKS_FILE = "profit_tailgate_locks.json"
_ENTRY_META_FILE = "crypto_entry_meta.json"
_META_MATCH_WINDOW_S = 15 * 60      # entry meta ts ↔ trade open ts tolerance (mirrors entry_meta)

# file path -> (mtime, parsed) — big sidecars (entry meta grows to MBs) parse once per change
_CACHE: dict[str, tuple[float, Any]] = {}


def state_dir(config: dict | None = None) -> Path:
    raw = (config or {}).get("mlnb_state_dir") or os.environ.get("MLNB_STATE_DIR", "")
    return Path(raw) if raw else Path.home() / "trading" / "state"


def load_state_json(config: dict | None, name: str, default: Any) -> Any:
    """mtime-cached read of one sidecar file; never raises."""
    path = state_dir(config) / name
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return default
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return default
    _CACHE[key] = (mtime, data)
    return data


def _entry_meta_for(trade: dict, config: dict | None) -> dict | None:
    """The brain's entry-time snapshot recorded closest to this trade's open (or None)."""
    data = load_state_json(config, _ENTRY_META_FILE, None)
    if not isinstance(data, dict):
        return None
    seg = (trade.get("bot_segment") or "futures").lower()
    rows = data.get(f"{seg}|{trade.get('pair')}") or []
    open_ts = (trade.get("open_timestamp") or 0) / 1000.0
    if not rows or not open_ts:
        return None
    best = min(rows, key=lambda r: abs(r.get("ts", 0) - open_ts), default=None)
    if best and abs(best.get("ts", 0) - open_ts) <= _META_MATCH_WINDOW_S:
        meta = best.get("meta")
        return meta if isinstance(meta, dict) else None
    return None


def enrich_trades(trades: list, config: dict | None = None) -> list:
    """In-place: add the brain's native fields to serialized trade dicts.

    tg_locked_pct / tg_peak_pct / tg_trail_dist — the LIVE ratchet state for open trades
    (the same lock file the tailgate enforcement reads, so what the UI shows is exactly
    what will exit the trade). strategy_label / brain_pred — entry-time decision facts.
    """
    if config is not None and not config.get("mlnb_native_fields", True):
        return trades
    try:
        locks = load_state_json(config, _LOCKS_FILE, {}) or {}
        for t in trades:
            if not isinstance(t, dict):
                continue
            lk = locks.get(str(t.get("trade_id"))) if t.get("is_open") else None
            if isinstance(lk, dict) and lk.get("locked") is not None:
                t.setdefault("tg_locked_pct", lk.get("locked"))
                t.setdefault("tg_peak_pct", lk.get("peak"))
                t.setdefault("tg_trail_dist", lk.get("dist"))
            else:
                t.setdefault("tg_locked_pct", None)
                t.setdefault("tg_peak_pct", None)
                t.setdefault("tg_trail_dist", None)
            meta = _entry_meta_for(t, config)
            label = (meta or {}).get("strategy") or t.get("enter_tag") or None
            t.setdefault("strategy_label", str(label) if label else None)
            brain = (meta or {}).get("brain") or {}
            conf = brain.get("confidence")
            direction = (meta or {}).get("direction")
            t.setdefault(
                "brain_pred",
                f"{direction} {float(conf):.2f}" if direction and conf is not None else None,
            )
    except Exception:                                   # noqa: BLE001 — never break the API
        logger.debug("mlnb sidecar enrichment failed", exc_info=True)
    return trades
