"""Sidecar store for per-entry brain metadata (trader psychology + decision snapshot).

Freqtrade's /forceenter carries only enter_tag (a strategy name), so the full decision
context the brain considered at entry is persisted HERE at order time (keyed by pair +
timestamp), then merged into the ClosedTrade by freqtrade_ingest.map_trade when the trade
closes. Plain JSON via trading.state so it survives restarts.
"""
from __future__ import annotations

import datetime as _dt
import time

from trading import state

FILE = "crypto_entry_meta.json"
MAX_PER_KEY = 20          # entries kept per pair (brain re-enters the same pair over time)
MAX_AGE_S = 30 * 86400
MATCH_WINDOW_S = 15 * 60  # entry meta ↔ Freqtrade open_date tolerance


def _key(pair: str, segment: str | None) -> str:
    return f"{(segment or 'futures').lower()}|{pair}"


def _parse_ts(iso: str) -> float | None:
    if not iso:
        return None
    try:
        return _dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def record(pair: str, segment: str | None, meta: dict) -> None:
    """Persist the brain's entry-time metadata for `pair` (called at forceenter time)."""
    data = state.load_json(FILE, {})
    now = time.time()
    rows = [r for r in data.get(_key(pair, segment), []) if now - r.get("ts", 0) < MAX_AGE_S]
    rows.append({"ts": now, "meta": meta})
    data[_key(pair, segment)] = rows[-MAX_PER_KEY:]
    state.save_json(FILE, data)


def lookup(pair: str, segment: str | None, open_date: str) -> dict | None:
    """Entry metadata recorded closest to (and within MATCH_WINDOW_S of) the trade's open."""
    open_ts = _parse_ts(open_date)
    rows = state.load_json(FILE, {}).get(_key(pair, segment), [])
    if open_ts is None or not rows:
        return None
    best = min(rows, key=lambda r: abs(r.get("ts", 0) - open_ts), default=None)
    if best and abs(best.get("ts", 0) - open_ts) <= MATCH_WINDOW_S:
        return best.get("meta")
    return None
