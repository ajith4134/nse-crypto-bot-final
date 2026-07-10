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

# 2026-07-10: lookup() used to state.load_json() on EVERY call — this file grows to
# many MB (decision snapshots), and closed_view calls lookup once per trade row, so a
# cold view rebuild parsed gigabytes of JSON while holding the GIL and starved every
# other thread in the process (the live-browser login stream froze for seconds).
# Parse ONCE per file change (mtime-keyed); all lookups share the parsed dict.
_CACHE: tuple[float, dict] | None = None


def _load() -> dict:
    global _CACHE
    try:
        mt = state._path(FILE).stat().st_mtime
    except OSError:
        mt = 0.0
    if _CACHE is not None and _CACHE[0] == mt:
        return _CACHE[1]
    data = state.load_json(FILE, {})
    if not isinstance(data, dict):
        data = {}
    _CACHE = (mt, data)
    return data


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
    # UI-VIEW AT ENTRY (owner goal 2026-07-07, #12): what the EYES had for this symbol
    # the moment it was entered — which timeframes of the app's OWN candles were fresh
    # in the capture store, and whether UI-only mode was on. One chokepoint covers every
    # crypto entry path; honest empty coverage when the eyes were cold. Cheap (RAM reads).
    try:
        from trading.broker_sense import ui_data
        tfs = [tf for tf in ("1m", "5m", "15m", "1h")
               if ui_data.ui_ohlcv(pair, timeframe=tf, limit=1)]
        if isinstance(meta.get("decision_snapshot"), dict):
            meta["decision_snapshot"]["ui_view"] = {
                "tfs_covered": tfs, "n_tfs": len(tfs),
                "ui_only_mode": ui_data.enabled()}
    except Exception:
        pass
    global _CACHE
    data = state.load_json(FILE, {})        # authoritative re-read for the read-modify-write
    if not isinstance(data, dict):
        data = {}
    now = time.time()
    rows = [r for r in data.get(_key(pair, segment), []) if now - r.get("ts", 0) < MAX_AGE_S]
    rows.append({"ts": now, "meta": meta})
    data[_key(pair, segment)] = rows[-MAX_PER_KEY:]
    state.save_json(FILE, data)
    try:                                    # keep readers hot without a re-parse
        _CACHE = (state._path(FILE).stat().st_mtime, data)
    except OSError:
        _CACHE = None


def lookup(pair: str, segment: str | None, open_date: str) -> dict | None:
    """Entry metadata recorded closest to (and within MATCH_WINDOW_S of) the trade's open."""
    open_ts = _parse_ts(open_date)
    rows = _load().get(_key(pair, segment), [])
    if open_ts is None or not rows:
        return None
    best = min(rows, key=lambda r: abs(r.get("ts", 0) - open_ts), default=None)
    if best and abs(best.get("ts", 0) - open_ts) <= MATCH_WINDOW_S:
        return best.get("meta")
    return None
