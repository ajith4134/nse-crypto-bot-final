"""trading/broker_sense/ui_data.py — UI-ONLY market data (owner goal 2026-07-07).

The owner's directive: "fully on UI only for now — disable the free-API polling and
let's see its performance on the web-app accounts." This module is THE market-data
door for that mode:

  feed_capture()  — called by the interception layer for every captured candles/kline
                    payload (the trading app's OWN data, fetched by the app itself
                    while the eyes browse — zero polling by us). Parses Binance kline
                    arrays and Upstox/TV-style OHLC dicts, indexes them by
                    (symbol, timeframe) in RAM with a bounded per-key history.
  ui_ohlcv()      — the funnel/fusion read path: candles for a symbol+tf from captures
                    ONLY. Returns None honestly when the eyes haven't seen that
                    symbol/tf fresh enough — callers record a data failure (evidence
                    lane) instead of silently falling back to an API.
  enabled()       — the UI_ONLY_DATA switch (env, default OFF until the eyes' coverage
                    is proven; flip in start_all.sh).
  coverage()      — honest meter: which symbols/tfs the eyes are currently feeding,
                    freshness, hit/miss counters — the owner's "let's see its
                    performance" instrument.

No fabrication: parsed rows must have monotonic timestamps + positive prices or the
payload is rejected. State is RAM-first (this is a live feed), with a periodic
state-file snapshot so the dashboard can show coverage across processes.
"""
from __future__ import annotations

import os
import re
import time

from trading import state

_STORE: dict[tuple[str, str], dict] = {}       # (SYMBOL, tf) -> {rows, ts, source_url}
_HITS = {"served": 0, "missed": 0, "fed": 0}
_MAX_ROWS = 500
_SNAPSHOT_EVERY_S = 60.0
_last_snap = 0.0
_FRESH_S = {"1m": 180, "5m": 900, "15m": 2700, "1h": 7200, "4h": 21600, "1d": 90000}

_TF_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
          "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}


def enabled() -> bool:
    """UI-only mode is ON when the env flag says so OR the coverage governor flipped the
    durable state flag (owner 2026-07-07: 'you flip it yourself without forgetting')."""
    if os.environ.get("UI_ONLY_DATA", "") in ("1", "true", "TRUE", "yes"):
        return True
    if os.environ.get("UI_ONLY_DATA", "") in ("0", "false", "FALSE", "no") and \
            os.environ.get("UI_ONLY_DATA_FORCE_ENV", "") == "1":
        return False                      # explicit env override escape hatch
    try:
        return bool(state.load_json("ui_only_mode.json", {}).get("enabled"))
    except Exception:
        return False


def maybe_auto_flip(shortlist: list[str] | None = None,
                    min_hit_rate: float = 0.8, min_symbols: int = 8) -> dict:
    """THE GOVERNOR (owner's order): once the eyes' capture coverage is warm enough —
    served hit-rate ≥ min_hit_rate with ≥ min_symbols indexed, and (when given) most of
    the active shortlist covered — flip UI-only mode ON durably (state flag), announce
    it (mind-events) and record it in the rule ledger. Idempotent; never flips OFF
    automatically (turning the API path back on is the owner's call)."""
    mode = state.load_json("ui_only_mode.json", {})
    if mode.get("enabled"):
        return {"enabled": True, "already": True}
    cov = coverage()
    hr = cov.get("hit_rate")
    n = cov.get("symbols", 0)
    short_cov = None
    if shortlist:
        have = {k for (k, _tf) in _STORE}
        def _flat(s):
            import re as _re
            return _re.sub(r"[/:]", "", s.upper()).replace("USDTUSDT", "USDT")
        covered = sum(1 for s in shortlist if _flat(s) in have or
                      _norm_symbol(s) in have)
        short_cov = covered / max(1, len(shortlist))
    # Primary criterion = SHORTLIST COVERAGE (can the eyes feed the symbols we actually
    # trade?). hit_rate is only meaningful AFTER the flip (pre-flip almost nothing reads
    # ui_ohlcv, so it sits near 0 forever — original hit-rate gate could never fire).
    if short_cov is not None:
        need_n = min(min_symbols, max(3, len(shortlist)))   # small shortlists still flip
        ready = short_cov >= 0.8 and n >= need_n
        needs = f"shortlist>=80% (now {short_cov:.0%}), symbols>={need_n} (now {n})"
    else:
        ready = hr is not None and hr >= min_hit_rate and n >= min_symbols
        needs = f"hit_rate>={min_hit_rate}, symbols>={min_symbols}"
    if not ready:
        return {"enabled": False, "hit_rate": hr, "symbols": n,
                "shortlist_coverage": short_cov, "needs": needs}
    state.save_json("ui_only_mode.json",
                    {"enabled": True, "flipped_ts": time.time(),
                     "evidence": {"hit_rate": hr, "symbols": n,
                                  "shortlist_coverage": short_cov}})
    try:
        from trading.brain import surface
        surface.record_change("ui-data-governor", knob="data.ui_only.mode",
                              old=False, new=True,
                              evidence={"hit_rate": hr, "symbols": n,
                                        "shortlist_coverage": short_cov},
                              reason="coverage threshold reached — owner's standing "
                                     "order: flip UI-only yourself, no reminders")
    except Exception:
        pass
    try:
        from trading.brain import mind_events
        mind_events.emit("data-mode",
                         f"UI-ONLY DATA MODE FLIPPED ON (owner's standing order): the "
                         f"eyes' captures now feed ALL market data — free-API polling "
                         f"paths are off. Evidence: hit-rate {hr}, {n} symbols indexed."
                         , salience=0.95)
    except Exception:
        pass
    return {"enabled": True, "flipped": True, "hit_rate": hr, "symbols": n}


def _norm_symbol(raw: str) -> str:
    """BTCUSDT / BTC-USDT / NSE_EQ|INE... → canonical uppercase token."""
    return re.sub(r"[^A-Z0-9|_:-]", "", (raw or "").upper())


def _interval_from(params: dict, url: str) -> str | None:
    iv = (params.get("interval") or params.get("resolution") or [None])
    iv = iv[0] if isinstance(iv, list) else iv
    if not iv:
        m = re.search(r"interval=([a-zA-Z0-9]+)", url)
        iv = m.group(1) if m else None
    if not iv:
        return None
    iv = str(iv)
    tv = {"1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m", "60": "1h",
          "120": "2h", "240": "4h", "1D": "1d", "D": "1d"}
    return tv.get(iv, iv.lower())


def _parse_rows(body) -> list | None:
    """Binance kline arrays [[t,o,h,l,c,v,...],...] or dict-of-arrays (TV/udf style)."""
    try:
        if isinstance(body, list) and body and isinstance(body[0], (list, tuple)) \
                and len(body[0]) >= 6:
            rows = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]),
                     float(r[5])] for r in body[-_MAX_ROWS:]]
        elif isinstance(body, dict) and all(k in body for k in ("t", "o", "h", "l", "c")):
            v = body.get("v") or [0.0] * len(body["t"])
            rows = [[int(body["t"][i]) * (1000 if body["t"][i] < 10**12 else 1),
                     float(body["o"][i]), float(body["h"][i]), float(body["l"][i]),
                     float(body["c"][i]), float(v[i])]
                    for i in range(len(body["t"]))][-_MAX_ROWS:]
        else:
            return None
    except Exception:
        return None
    if len(rows) < 2:
        return None
    if any(rows[i][0] >= rows[i + 1][0] for i in range(len(rows) - 1)):
        return None                                   # non-monotonic → reject
    if any(r[4] <= 0 or r[2] < r[3] for r in rows):
        return None                                   # nonsense prices → reject
    return rows


def feed_capture(broker: str, url: str, body) -> bool:
    """Interception hook: index a captured candles payload by (symbol, tf). Cheap +
    never raises; returns True when stored (so the interceptor can count it)."""
    try:
        from urllib.parse import parse_qs, urlparse
        u = urlparse(url)
        params = parse_qs(u.query)
        sym = (params.get("symbol") or params.get("instrument_key")
               or params.get("pair") or [None])[0]
        if not sym:
            m = re.search(r"/(?:kline[s]?|candle[s]?|history)/([A-Za-z0-9|_:-]{3,})", u.path)
            sym = m.group(1) if m else None
        tf = _interval_from(params, url)
        if not sym or not tf:
            return False
        rows = _parse_rows(body)
        if not rows:
            return False
        key = (_norm_symbol(sym), tf)
        _STORE[key] = {"rows": rows, "ts": time.time(), "url": url[:160],
                       "broker": broker}
        _HITS["fed"] += 1
        _maybe_snapshot()
        return True
    except Exception:
        return False


def _candidates(symbol: str) -> list[str]:
    """Symbol spellings the apps use: BTC/USDT:USDT → BTCUSDT; RELIANCE → RELIANCE…"""
    s = (symbol or "").upper()
    out = [_norm_symbol(s)]
    flat = re.sub(r"[/:]", "", s)
    if flat.endswith("USDTUSDT"):
        flat = flat[:-4]
    out.append(_norm_symbol(flat))
    base = s.split("/")[0]
    if base and base != s:
        out.append(_norm_symbol(base + "USDT"))
        out.append(_norm_symbol(base))
    return list(dict.fromkeys(out))


def ui_ohlcv(symbol: str, timeframe: str = "5m", limit: int = 240) -> list | None:
    """Candles from the eyes' captures ONLY. None (honest miss) when absent/stale."""
    fresh = _FRESH_S.get(timeframe, 3600)
    for cand in _candidates(symbol):
        row = _STORE.get((cand, timeframe))
        if row and time.time() - row["ts"] <= fresh:
            _HITS["served"] += 1
            return row["rows"][-limit:]
    _HITS["missed"] += 1
    return None


def coverage() -> dict:
    now = time.time()
    syms: dict[str, dict] = {}
    for (sym, tf), row in _STORE.items():
        e = syms.setdefault(sym, {"tfs": {}, "broker": row.get("broker")})
        e["tfs"][tf] = round(now - row["ts"], 1)
    total = _HITS["served"] + _HITS["missed"]
    return {"enabled": enabled(), "symbols": len(syms),
            "keys": len(_STORE), "fed": _HITS["fed"],
            "served": _HITS["served"], "missed": _HITS["missed"],
            "hit_rate": round(_HITS["served"] / total, 4) if total else None,
            "detail": dict(sorted(syms.items())[:80])}


def _maybe_snapshot() -> None:
    global _last_snap
    if time.time() - _last_snap < _SNAPSHOT_EVERY_S:
        return
    _last_snap = time.time()
    try:
        # Never clobber a good cross-process snapshot with an empty RAM store (a fresh
        # restart starts cold and would otherwise zero the dashboard's coverage view
        # until the crawl re-warms — observed 2026-07-07).
        if not _STORE:
            return
        state.save_json("ui_data_coverage.json", coverage())
    except Exception:
        pass
