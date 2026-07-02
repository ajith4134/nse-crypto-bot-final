"""data_sources/orderflow.py — REAL order-flow + L2 snapshot data (Wave 3).

Two real sources, both free via ccxt:
  • flow_series(): OHLCV-derived cumulative volume delta (CVD) — delta ≈ volume × candle-close
    position in its range; a standard order-flow proxy with FULL history (real backtests for the
    CVD / footprint / absorption family).
  • order_book_snapshot(): live L2 depth (bid/ask sizes) → imbalance + microprice for the HFT/MM
    signals. True historical L2 depth isn't free, so depth-dependent strategies are LIVE-signal +
    forward-accumulating (collect_snapshot persists to disk); their backtests grow as data lands.
Offline-safe (empty/None on failure).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

_CACHE: dict = {}


def _binance():
    import ccxt
    return ccxt.binance({"enableRateLimit": True})


def flow_series(symbol: str = "BTC/USDT", *, timeframe: str = "5m", limit: int = 1000) -> pd.DataFrame:
    """OHLCV → {close, delta, cvd} order-flow proxy (real, full history). Empty on failure."""
    key = f"flow:{symbol}:{timeframe}:{limit}"
    hit = _CACHE.get(key); now = time.monotonic()
    if hit and now - hit[0] < 30:
        return hit[1]
    try:
        ex = _binance()
        ex.load_markets()
        mkt = ex.market(symbol)
        # raw klines carry REAL taker-buy base volume (index 9) — true order flow, not a proxy
        raw = ex.publicGetKlines({"symbol": mkt["id"], "interval": timeframe, "limit": limit})
    except Exception:
        return pd.DataFrame()
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw).iloc[:, :11]
    df.columns = ["time", "open", "high", "low", "close", "volume", "ct", "qv", "n",
                  "taker_buy_base", "tbq"]
    for c in ("close", "volume", "taker_buy_base"):
        df[c] = df[c].astype(float)
    # delta = taker BUY volume − taker SELL volume (aggressor-signed) → real CVD
    df["delta"] = 2.0 * df["taker_buy_base"] - df["volume"]
    df["cvd"] = df["delta"].cumsum()
    out = df[["close", "delta", "cvd"]].reset_index(drop=True)
    _CACHE[key] = (now, out)
    return out


def order_book_snapshot(symbol: str = "BTC/USDT", *, depth: int = 20) -> dict | None:
    """Live L2 snapshot → {mid, microprice, imbalance, spread}. None on failure."""
    try:
        ob = _binance().fetch_order_book(symbol, depth)
    except Exception:
        return None
    bids, asks = ob.get("bids") or [], ob.get("asks") or []
    if not bids or not asks:
        return None
    bid_p, bid_s = bids[0][0], sum(b[1] for b in bids)
    ask_p, ask_s = asks[0][0], sum(a[1] for a in asks)
    tot = (bid_s + ask_s) or 1.0
    imbalance = (bid_s - ask_s) / tot
    microprice = (bid_p * ask_s + ask_p * bid_s) / tot     # size-weighted toward the thin side
    return {"mid": (bid_p + ask_p) / 2.0, "microprice": microprice,
            "imbalance": imbalance, "spread": ask_p - bid_p, "bid": bid_p, "ask": ask_p}
