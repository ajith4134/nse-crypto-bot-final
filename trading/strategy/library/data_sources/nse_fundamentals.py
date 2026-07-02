"""data_sources/nse_fundamentals.py — REAL NSE fundamentals + price panel (Wave 2, free via yfinance).

A NIFTY large-cap basket's fundamentals (P/E, P/B, ROE, dividend yield, earnings growth, market cap)
+ aligned daily close panel — enough to backtest the factor family (value / growth / quality /
dividend / low-vol / multifactor) and factor-neutral stat-arb for REAL, no API key.

Caveat (honest): yfinance `.info` is a CURRENT snapshot, not point-in-time, so fundamental-factor
backtests carry mild look-ahead — the cross-sectional RANK + long-short construction is real; strict
point-in-time fundamentals need a paid source. Low-vol uses price only (no look-ahead). Cached.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

# liquid NIFTY large caps (.NS = NSE on yfinance)
_BASKET = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
           "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS",
           "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS"]
_CACHE: dict = {}
_FIELDS = {"trailingPE": "pe", "priceToBook": "pb", "returnOnEquity": "roe",
           "dividendYield": "div_yield", "earningsGrowth": "earnings_growth",
           "marketCap": "market_cap", "profitMargins": "margin"}


def price_panel(tickers: list | None = None, *, period: str = "1y") -> pd.DataFrame:
    """Aligned daily close panel (columns = tickers). One batched yfinance download. Empty on fail."""
    tickers = tickers or _BASKET
    key = f"px:{period}:{','.join(tickers)}"
    hit = _CACHE.get(key); now = time.monotonic()
    if hit and now - hit[0] < 1800:
        return hit[1]
    try:
        import yfinance as yf
        data = yf.download(tickers, period=period, interval="1d", progress=False,
                           auto_adjust=True)["Close"]
        panel = data.dropna(how="all").ffill().dropna().reset_index(drop=True)
    except Exception:
        return pd.DataFrame()
    _CACHE[key] = (now, panel)
    return panel


def fundamentals(tickers: list | None = None) -> pd.DataFrame:
    """Per-ticker fundamentals (pe/pb/roe/div_yield/earnings_growth/market_cap/margin). Cached 1h."""
    tickers = tickers or _BASKET
    key = f"fund:{','.join(tickers)}"
    hit = _CACHE.get(key); now = time.monotonic()
    if hit and now - hit[0] < 3600:
        return hit[1]
    try:
        import yfinance as yf
        rows = {}
        for tk in tickers:
            try:
                info = yf.Ticker(tk).info
                rows[tk] = {v: info.get(k) for k, v in _FIELDS.items()}
            except Exception:
                continue
        df = pd.DataFrame(rows).T.apply(pd.to_numeric, errors="coerce")
    except Exception:
        return pd.DataFrame()
    _CACHE[key] = (now, df)
    return df
