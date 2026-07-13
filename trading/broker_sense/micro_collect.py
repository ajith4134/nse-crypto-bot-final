"""trading/broker_sense/micro_collect.py — actively COLLECT microstructure data for the
symbols the brain is deciding on (owner 2026-07-13: "brain collecting all this every trade").

The parked chart tabs stream kline + markPrice + OI, but the direction model needs the FULL
microstructure set — order book, taker flow, long/short crowd, aggTrades. Those live behind
their own data doors, which endpoint discovery already confirmed. This reads each missing
kind from the APP'S OWN endpoint via the browser page's origin/session (motto: data = web
navigation; ban-safer than an external keyed REST call), then hands the body to
ui_market.feed_capture — the exact same ingestion the passive interception uses, so the
parsers and ui_market storage are reused unchanged.

Throttled hard (once per kind/symbol per MICRO_COLLECT_TTL, capped symbols/call) so it never
hammers the app; fail-open; kill-switch MICRO_COLLECT=0. Only runs for the small set of
symbols direction actually wants (open trades + direction_collect_wanted), never the universe.
"""
from __future__ import annotations

import os
import time

# The app's own confirmed data doors (endpoint discovery / app_school_map), with the query
# params the app uses. feed_capture is called with the EXPLICIT kind, so classification is not
# needed — only the body shape must match ui_market's parser (it does: same doors the app hits).
_ENDPOINTS = {
    "open_interest": "https://www.binance.com/fapi/v1/openInterest?symbol={s}",
    "orderbook":     "https://www.binance.com/fapi/v1/depth?symbol={s}&limit=20",
    "taker_volume":  "https://www.binance.com/futures/data/takerlongshortRatio?symbol={s}&period=5m&limit=1",
    "long_short":    "https://www.binance.com/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1",
    "recent_trades": "https://www.binance.com/fapi/v1/aggTrades?symbol={s}&limit=50",
}
_KIND_TO_FRESH = {                       # ui_market accessor to test current freshness
    "open_interest": "open_interest", "orderbook": "book", "taker_volume": "taker",
    "long_short": "long_short", "recent_trades": "recent_liquidations",
}
_FETCH_JS = ("async (u) => { try { const r = await fetch(u); if(!r.ok) return null; "
             "return await r.json(); } catch(e){ return null; } }")

_last: dict = {}                         # (sym, kind) -> ts  (throttle)


def enabled() -> bool:
    return os.environ.get("MICRO_COLLECT", "1") in ("1", "true", "TRUE", "yes", "on")


def _ttl() -> float:
    try:
        return float(os.environ.get("MICRO_COLLECT_TTL", "90"))
    except ValueError:
        return 90.0


def _flat(symbol: str) -> str:
    """'BTC/USDT:USDT' -> 'BTCUSDT' (Binance futures data-endpoint symbol)."""
    s = str(symbol or "").upper().split(":", 1)[0].replace("/", "")
    return s


def _missing_kinds(symbol: str) -> list[str]:
    """Which microstructure kinds are NOT fresh for this symbol right now."""
    try:
        from trading.broker_sense import ui_market as um
    except Exception:
        return list(_ENDPOINTS)
    out = []
    for kind, acc in _KIND_TO_FRESH.items():
        try:
            fn = getattr(um, acc, None)
            val = fn(symbol) if fn else None
            if not val:
                out.append(kind)
        except Exception:
            out.append(kind)
    return out


def collect(symbols, sessions, *, broker: str = "binance", deadline: float | None = None,
            max_symbols: int = 10) -> dict:
    """Fetch each symbol's MISSING microstructure kinds from the app's own doors and ingest.
    `sessions` is the funnel's browser session manager; runs in the funnel process (headed)."""
    rep = {"fetched": 0, "stored": 0, "symbols": 0, "errors": []}
    if not enabled():
        return rep
    try:
        from trading.broker_sense import ui_market as um
        pg = None
        now = time.time()
        for sym in list(symbols or [])[:max_symbols]:
            if deadline is not None and time.monotonic() > deadline:
                break
            miss = [k for k in _missing_kinds(sym)
                    if now - _last.get((sym, k), 0.0) > _ttl()]
            if not miss:
                continue
            flat = _flat(sym)
            if pg is None:
                pg = sessions.page(broker, "https://www.binance.com/en/futures/BTCUSDT",
                                   timeout_ms=15000)
            rep["symbols"] += 1
            for kind in miss:
                url = _ENDPOINTS[kind].format(s=flat)
                try:
                    body = pg.evaluate(_FETCH_JS, url)
                except Exception as e:
                    rep["errors"].append(f"{kind}:{type(e).__name__}")
                    continue
                _last[(sym, kind)] = now
                if body is None:
                    continue
                rep["fetched"] += 1
                try:
                    rep["stored"] += int(um.feed_capture(broker, kind, url, body) or 0)
                except Exception:
                    pass
        return rep
    except Exception as e:
        rep["errors"].append(f"{type(e).__name__}: {str(e)[:60]}")
        return rep
