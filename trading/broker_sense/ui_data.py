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
    return os.environ.get("UI_ONLY_DATA", "0") in ("1", "true", "TRUE", "yes")


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
        state.save_json("ui_data_coverage.json", coverage())
    except Exception:
        pass
