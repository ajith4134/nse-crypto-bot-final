"""data_sources/multi_asset.py — REAL multi-symbol crypto price panel (Wave 1C).

Fetches aligned daily close prices for a basket of liquid crypto via ccxt (free), so the
multi-asset stat-arb family (pairs, cointegration, correlation, cross-sectional momentum / mean
reversion, relative strength, market-neutral) can be backtested for REAL. Cached; offline-safe
(empty frame on failure → bt_* functions tag the reason).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

# liquid majors that share enough history for cross-sectional / pairs work
_BASKET = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
           "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "LTC/USDT"]
_CACHE: dict = {}


def load_panel(symbols: list | None = None, *, exchange: str = "binance",
               timeframe: str = "1d", days: int = 180) -> pd.DataFrame:
    """Aligned close-price panel: DataFrame indexed 0..N, columns = symbols. Empty on failure."""
    symbols = symbols or _BASKET
    key = f"panel:{exchange}:{timeframe}:{days}:{','.join(symbols)}"
    hit = _CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < 600:
        return hit[1]
    try:
        import ccxt
        ex = getattr(ccxt, exchange)({"enableRateLimit": True})
        cols = {}
        for s in symbols:
            raw = ex.fetch_ohlcv(s, timeframe, limit=days + 5)
            if raw:
                df = pd.DataFrame(raw, columns=["t", "o", "h", "l", "c", "v"])
                cols[s] = pd.Series(df["c"].to_numpy(), index=df["t"].to_numpy())
        if not cols:
            return pd.DataFrame()
        panel = pd.DataFrame(cols).dropna().reset_index(drop=True).tail(days).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()
    _CACHE[key] = (now, panel)
    return panel
