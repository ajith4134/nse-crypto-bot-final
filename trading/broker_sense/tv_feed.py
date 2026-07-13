"""trading/broker_sense/tv_feed.py — TradingView-WS SUPPLEMENTARY data lane (adopt item 6a).

A reverse-engineered TradingView WebSocket quote source (reuse: the `tradingview-ws` package) as
an EXTRA, opt-in fallback that feeds ui_market when the primary app feeds (upstox_feed / binance
interception) have no fresh quote for a symbol. It is deliberately SECONDARY and default-OFF:

  * MOTTO: NSE market data must come from the Upstox ACCOUNT UI. TradingView is a web source but
    NOT the Upstox account, so under NSE_UI_ONLY the NSE side stays Upstox-pure unless the owner
    explicitly opts NSE in (TV_WS_NSE=1). Crypto may use it freely as a supplementary web source.
  * BEST-EFFORT: TradingView's WS protocol drifts, so every call is bounded by a hard timeout in a
    worker thread (it can NEVER wedge a cycle) and degrades to None — the caller keeps its primary
    source. Its live efficacy depends on TradingView's current protocol; the lane is honest about
    that (status().last_ok).

Levers: TV_WS_LANE=1 (enable), TV_WS_NSE=1 (also allow NSE), TV_WS_TIMEOUT (6s).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

_STATS = {"asks": 0, "ok": 0, "timeouts": 0, "errors": 0, "last_ok": None}


def enabled() -> bool:
    return os.environ.get("TV_WS_LANE", "0") in ("1", "true", "TRUE", "yes", "on")


def _nse_allowed() -> bool:
    return os.environ.get("TV_WS_NSE", "0") in ("1", "true", "TRUE", "yes", "on")


def _timeout() -> float:
    try:
        return float(os.environ.get("TV_WS_TIMEOUT", "6") or 6)
    except ValueError:
        return 6.0


def _tv_market(market: str) -> str:
    """TradingView's `market` arg for the ws client (its exchange namespace)."""
    return "binance" if (market or "").lower() == "crypto" else "nse"


def _tv_ticker(symbol: str) -> str:
    """Map our symbol to TradingView's ticker form: BTC/USDT:USDT → BTCUSDT; RELIANCE → RELIANCE."""
    s = (symbol or "").upper().split(":")[0].replace("/", "")
    return s


def _fetch_blocking(symbol: str, market: str) -> Optional[dict]:
    """One bounded quote via tradingview-ws. Runs INSIDE a worker thread (never on the caller)."""
    try:
        import tradingview_ws as tv
        w = tv.TradingViewWs(_tv_ticker(symbol), _tv_market(market))
        q = w.realtime_quote()
        if isinstance(q, dict):
            last = q.get("lp") or q.get("last_price") or q.get("close") or q.get("price")
            if last is not None:
                return {"last": float(last),
                        "pct_change": (float(q["chp"]) if q.get("chp") is not None else None)}
    except Exception:
        return None
    return None


def quote(symbol: str, market: str) -> Optional[dict]:
    """Supplementary TradingView quote, hard-bounded so it can never wedge a cycle. None unless
    the lane is enabled (and, for NSE, opted in) AND TradingView actually answered in time."""
    if not enabled():
        return None
    if (market or "").lower() != "crypto" and not _nse_allowed():
        return None                                  # motto: NSE stays Upstox-pure by default
    _STATS["asks"] += 1
    result: dict = {}

    def _run():
        result["q"] = _fetch_blocking(symbol, market)

    th = threading.Thread(target=_run, daemon=True, name="tv-ws-quote")
    th.start()
    th.join(_timeout())
    if th.is_alive():                                # protocol hung → abandon (thread is daemon)
        _STATS["timeouts"] += 1
        return None
    q = result.get("q")
    if q is None:
        _STATS["errors"] += 1
        return None
    _STATS["ok"] += 1
    _STATS["last_ok"] = time.time()
    return {**q, "source": "tv:ws"}


def feed(symbol: str, market: str) -> bool:
    """Fetch a supplementary quote and push it into ui_market's ticker store (so it serves reads
    like any other captured quote). Returns True when a quote landed. Best-effort, never raises."""
    try:
        q = quote(symbol, market)
        if not q:
            return False
        from trading.broker_sense import ui_market
        return bool(ui_market.feed_capture(
            "tradingview", "ticker", "tv:ws",
            {"symbol": _tv_ticker(symbol), "ltp": q["last"], "pct_change": q.get("pct_change")}))
    except Exception:
        return False


def status() -> dict:
    return {"enabled": enabled(), "nse_allowed": _nse_allowed(),
            "timeout_s": _timeout(), "stats": dict(_STATS)}
