"""trading/broker_sense/data_failsafe.py — the owner's rule 4: NEVER skip a trade for data.

Whenever a GUI read is missing or inconsistent (OCR misread, chart didn't render, screener
field absent), these API fallbacks fill the gap: ccxt (crypto ticker/book/candles),
CryptoEngineClient.pair_candles (Freqtrade's own data), OpenAlgoClient quote/depth (NSE).
Every result carries source="api:<which>" so the journal/dashboard stay honest about where
each number came from. All calls are best-effort with tight timeouts; a total miss returns
None rather than raising, and the funnel records the miss instead of silently trading.
"""
from __future__ import annotations

import os
import time

_CCXT_TIMEOUT_MS = 8000
_cache: dict = {}                       # (kind, symbol) -> (ts, value); TTL cache
# Zero-lag warm cache (owner 2026-07-06): with BRAIN_WARM_ALL_PAIRS=1 the cache holds EVERY
# whitelisted pair's candles/quotes/books warm in RAM for a longer TTL, so the funnel reads them
# instantly instead of re-fetching each pair each cycle (uses the box's spare RAM to kill I/O
# lag; 30s stays fresh for 5m candles). BRAIN_CACHE_TTL overrides. Ban-safe: fewer fetches, not
# more. The cache is never evicted mid-run (unbounded by design — the box has the RAM headroom).
_WARM = os.environ.get("BRAIN_WARM_ALL_PAIRS", "1") in ("1", "true", "TRUE", "yes")
_TTL = float(os.environ.get("BRAIN_CACHE_TTL", "30" if _WARM else "10"))


# RAM guard (owner 2026-07-06): the warm cache may grow to hold every pair. This keeps the box's
# spare free — if the process RSS exceeds BRAIN_RAM_BUDGET_GB, evict the oldest cache entries until
# back under budget. So RAM is used near-fully for zero-lag warmth, but never past the safe ceiling.
_RAM_BUDGET_BYTES = float(os.environ.get("BRAIN_RAM_BUDGET_GB", "27")) * (1024 ** 3)
_insert_count = 0


def _rss_bytes() -> int:
    try:
        with open("/proc/self/statm") as f:            # pages; portable, no psutil dep
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return 0


def _guard_ram():
    """Evict oldest cache entries while over the RAM budget (checked every 64 inserts)."""
    global _insert_count
    _insert_count += 1
    if _insert_count % 64 != 0 or not _cache:
        return
    if _rss_bytes() <= _RAM_BUDGET_BYTES:
        return
    for k in sorted(_cache, key=lambda kk: _cache[kk][0])[: max(1, len(_cache) // 8)]:
        _cache.pop(k, None)                            # drop the oldest ~12.5%


def _cached(kind: str, symbol: str, fn):
    k = (kind, symbol)
    hit = _cache.get(k)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    val = fn()
    if val is not None:
        _cache[k] = (time.time(), val)
        _guard_ram()
    return val


_EX_CACHE = None


def _ccxt_ex():
    # CACHE the ccxt instance: a fresh ccxt.binance() loads all markets on its first fetch
    # (~1.6s HTTP), and this was created ANEW on every call — so every quote/ohlcv/top_of_book paid
    # the market-load, making live_price ~2s and the executor's per-symbol loop ~5min over the
    # universe (deadline-deferred most symbols → entered=[]). Reused warm instance ≈ 158ms (2026-07-12).
    # Matches app_school._ccxt_exchange, already shared across the fast_candles thread pool.
    global _EX_CACHE
    if _EX_CACHE is None:
        import ccxt
        _EX_CACHE = ccxt.binance({"timeout": _CCXT_TIMEOUT_MS, "enableRateLimit": True,
                                  "options": {"defaultType": "swap"}})
    return _EX_CACHE


def _base(symbol: str) -> str:
    return symbol.split(":")[0] if ":" in symbol else symbol


def _ui_only() -> bool:
    """Owner 2026-07-07: UI_ONLY_DATA=1 disables EVERY API fallback in this module —
    the eyes' captured app data (ui_data) is the sole market-data source; misses are
    honest Nones (recorded upstream), never silent API polls."""
    from trading.broker_sense import ui_data
    return ui_data.enabled()


def quote(symbol: str, market: str) -> dict | None:
    """Last price + bid/ask via API. crypto → ccxt Binance; NSE → OpenAlgo.
    UI-only mode: last close from the eyes' candles, else honest None."""
    if _ui_only():
        from trading.broker_sense import ui_data
        rows = ui_data.ui_ohlcv(symbol, timeframe="1m", limit=2) or \
            ui_data.ui_ohlcv(symbol, timeframe="5m", limit=2)
        if rows:
            return {"last": rows[-1][4], "bid": None, "ask": None,
                    "source": "ui:capture"}
        return None
    def _get():
        try:
            if market == "crypto":
                t = _ccxt_ex().fetch_ticker(_base(symbol))
                return {"last": t.get("last"), "bid": t.get("bid"), "ask": t.get("ask"),
                        "source": "api:ccxt-binance"}
            from trading.openalgo_client import OpenAlgoClient
            q = OpenAlgoClient().quote(symbol.split("/")[0])
            if isinstance(q, dict):
                d = q.get("data", q)
                return {"last": d.get("ltp"), "bid": d.get("bid"), "ask": d.get("ask"),
                        "source": "api:openalgo"}
        except Exception:
            return None
    return _cached("quote", f"{market}|{symbol}", _get)


def top_of_book(symbol: str, market: str) -> dict | None:
    """Best bid/ask via API (order-book fail-safe for the screen monitor).
    UI-only mode: no API — honest None (books come from the eyes or not at all)."""
    if _ui_only():
        return None
    def _get():
        try:
            if market == "crypto":
                ob = _ccxt_ex().fetch_order_book(_base(symbol), limit=5)
                bid = ob["bids"][0][0] if ob.get("bids") else None
                ask = ob["asks"][0][0] if ob.get("asks") else None
                return {"bid": bid, "ask": ask, "source": "api:ccxt-binance"}
            from trading.openalgo_client import OpenAlgoClient
            d = OpenAlgoClient().depth(symbol.split("/")[0])
            if isinstance(d, dict):
                dd = d.get("data", d)
                bids, asks = dd.get("bids") or [], dd.get("asks") or []
                return {"bid": (bids[0] or {}).get("price") if bids else None,
                        "ask": (asks[0] or {}).get("price") if asks else None,
                        "source": "api:openalgo-depth"}
        except Exception:
            return None
    return _cached("book", f"{market}|{symbol}", _get)


def ohlcv(symbol: str, market: str, timeframe: str = "5m", limit: int = 24) -> list | None:
    """[[ts, o, h, l, c, v], …] via API — feeds the local chart render when no app chart
    could be captured. crypto → Freqtrade's own candles, then ccxt. NSE has no public
    candle API here → None (the chart chain then uses the TradingView public chart).
    UI-only mode: the eyes' captured candles or an honest None — no API path at all."""
    if _ui_only():
        from trading.broker_sense import ui_data
        return ui_data.ui_ohlcv(symbol, timeframe=timeframe, limit=limit)
    def _get():
        if market != "crypto":
            return _nse_ohlcv(symbol, timeframe, limit)      # NSE → OpenAlgo broker history
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            df = CryptoEngineClient().pair_candles(symbol, timeframe=timeframe, limit=limit)
            if df is not None and len(df):
                cols = [c for c in ("date", "open", "high", "low", "close", "volume")
                        if c in df.columns]
                return df[cols].values.tolist()
        except Exception:
            pass
        try:
            return _ccxt_ex().fetch_ohlcv(_base(symbol), timeframe=timeframe, limit=limit)
        except Exception:
            return None
    return _cached(f"ohlcv:{timeframe}", f"{market}|{symbol}", _get)


def _nse_ohlcv(symbol: str, timeframe: str, limit: int) -> list | None:
    """NSE candles via OpenAlgo's broker history API (rule 4: never skip a trade for data —
    NSE DOES have candles through the connected broker). Returns [[ts,o,h,l,c,v], …] newest-last,
    trimmed to `limit`. None only if the server/symbol truly has nothing."""
    import datetime as _dt
    try:
        from trading.openalgo_client import OpenAlgoClient
        today = _dt.date.today()
        # enough calendar days back to cover `limit` intraday bars even across a weekend/holiday
        span = 10 if timeframe.endswith(("m", "h")) else max(10, limit * 2)
        r = OpenAlgoClient().history(
            symbol.replace("/", "").upper(), "NSE", interval=timeframe,
            start_date=(today - _dt.timedelta(days=span)).isoformat(),
            end_date=today.isoformat())
        rows = r.get("data") if isinstance(r, dict) else r
        if not rows:
            return None
        out = []
        for c in rows:
            if isinstance(c, dict):
                ts = c.get("timestamp") or c.get("date") or c.get("time")
                ts = int(ts.timestamp() * 1000) if hasattr(ts, "timestamp") else ts
                out.append([ts, c.get("open"), c.get("high"), c.get("low"),
                            c.get("close"), c.get("volume")])
            else:                                            # already a sequence
                out.append(list(c)[:6])
        return out[-limit:] if limit else out
    except Exception:
        return None


def consistent(gui_value: float | None, api_value: float | None,
               tol_pct: float = 1.0) -> bool:
    """The accuracy gate: a GUI/OCR number must sit within tol% of the API reference to
    drive a trade; otherwise the funnel swaps in the API number (rule 4) and logs it."""
    if gui_value is None or api_value is None or api_value == 0:
        return False
    return abs(float(gui_value) - float(api_value)) / abs(float(api_value)) * 100 <= tol_pct
