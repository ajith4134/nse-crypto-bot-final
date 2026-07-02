"""data_sources/crypto_deriv.py — ccxt crypto-derivatives data (funding, OHLCV, OI, basis).

Downloads REAL data via ccxt (free public endpoints, no keys) and caches it as parquet/csv to
data/strategy_library/. Builds a `MarketData` with spot+perp bars, the funding-rate history,
open-interest history and the computed basis — the inputs the funding-arb / basis / OI / carry
strategies need. Reuses the repo's `trading.crypto.exchange_client.ExchangeClient` for the ccxt
client + key handling; falls back gracefully (returns what it could fetch) when offline.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from trading.strategy.library.data_sources import cache_path
from trading.strategy.library.marketdata import MarketData

_DAY_MS = 86_400_000


def _ccxt(exchange: str, market_type: str):
    """Raw ccxt client via the repo's ExchangeClient (rate-limited, key-aware)."""
    from trading.crypto.exchange_client import ExchangeClient
    return ExchangeClient(exchange=exchange, market_type=market_type)._client()


def _ohlcv_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["ts"], unit="ms")
    return df[["time", "open", "high", "low", "close", "volume"]]


def fetch_ohlcv(symbol: str, *, exchange: str = "binance", market_type: str = "spot",
                timeframe: str = "1h", days: int = 60, use_cache: bool = True) -> pd.DataFrame:
    """Download OHLCV (cached). market_type 'spot' or 'swap' (perp)."""
    key = f"ohlcv_{exchange}_{market_type}_{symbol.replace('/', '_').replace(':', '-')}_{timeframe}_{days}d.parquet"
    path = cache_path(key)
    if use_cache:
        try:
            return pd.read_parquet(path)
        except Exception:
            pass
    ex = _ccxt(exchange, market_type)
    sym = f"{symbol}:{symbol.split('/')[1]}" if (market_type == "swap" and ":" not in symbol) else symbol
    since = ex.milliseconds() - days * _DAY_MS
    out: list = []
    while since < ex.milliseconds():
        batch = ex.fetch_ohlcv(sym, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        out += batch
        since = batch[-1][0] + 1
        if len(batch) < 1000:
            break
        time.sleep(ex.rateLimit / 1000.0)
    df = _ohlcv_df(out).drop_duplicates("time").reset_index(drop=True)
    try:
        df.to_parquet(path)
    except Exception:
        pass
    return df


def fetch_funding_history(symbol: str, *, exchange: str = "binance", days: int = 60,
                          use_cache: bool = True) -> pd.Series:
    """Download perp funding-rate history → Series(rate fraction) indexed by time (cached)."""
    key = f"funding_{exchange}_{symbol.replace('/', '_')}_{days}d.parquet"
    path = cache_path(key)
    if use_cache:
        try:
            s = pd.read_parquet(path)["rate"]
            s.index = pd.read_parquet(path)["time"]
            return s
        except Exception:
            pass
    ex = _ccxt(exchange, "swap")
    sym = f"{symbol}:{symbol.split('/')[1]}" if ":" not in symbol else symbol
    since = ex.milliseconds() - days * _DAY_MS
    rows: list = []
    while since < ex.milliseconds():
        batch = ex.fetch_funding_rate_history(sym, since=since, limit=1000)
        if not batch:
            break
        rows += batch
        since = batch[-1]["timestamp"] + 1
        if len(batch) < 1000:
            break
        time.sleep(ex.rateLimit / 1000.0)
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame([{"time": pd.to_datetime(r["timestamp"], unit="ms"),
                        "rate": float(r["fundingRate"])} for r in rows]).drop_duplicates("time")
    try:
        df.to_parquet(path)
    except Exception:
        pass
    return df.set_index("time")["rate"]


def fetch_open_interest_history(symbol: str, *, exchange: str = "binance", timeframe: str = "1h",
                                days: int = 30, use_cache: bool = True) -> pd.Series:
    """Download open-interest history → Series indexed by time (cached). Empty if unsupported."""
    key = f"oi_{exchange}_{symbol.replace('/', '_')}_{timeframe}_{days}d.parquet"
    path = cache_path(key)
    if use_cache:
        try:
            d = pd.read_parquet(path)
            return pd.Series(d["oi"].values, index=d["time"])
        except Exception:
            pass
    ex = _ccxt(exchange, "swap")
    sym = f"{symbol}:{symbol.split('/')[1]}" if ":" not in symbol else symbol
    try:
        if not ex.has.get("fetchOpenInterestHistory"):
            return pd.Series(dtype=float)
        since = ex.milliseconds() - days * _DAY_MS
        rows = ex.fetch_open_interest_history(sym, timeframe=timeframe, since=since, limit=500)
    except Exception:
        return pd.Series(dtype=float)
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame([{"time": pd.to_datetime(r["timestamp"], unit="ms"),
                        "oi": float(r.get("openInterestAmount") or r.get("openInterestValue") or 0.0)}
                       for r in rows]).drop_duplicates("time")
    try:
        df.to_parquet(path)
    except Exception:
        pass
    return pd.Series(df["oi"].values, index=df["time"])


def load_market(symbol: str = "BTC/USDT", *, exchange: str = "binance", timeframe: str = "1h",
                days: int = 60, want_oi: bool = True) -> MarketData:
    """Build a MarketData with spot+perp bars, funding history, OI and basis (real, cached)."""
    spot = fetch_ohlcv(symbol, exchange=exchange, market_type="spot", timeframe=timeframe, days=days)
    perp = fetch_ohlcv(symbol, exchange=exchange, market_type="swap", timeframe=timeframe, days=days)
    funding = fetch_funding_history(symbol, exchange=exchange, days=days)
    oi = fetch_open_interest_history(symbol, exchange=exchange, timeframe=timeframe,
                                     days=min(days, 30)) if want_oi else pd.Series(dtype=float)

    basis = None
    if spot is not None and perp is not None and len(spot) and len(perp):
        m = pd.merge(spot[["time", "close"]].rename(columns={"close": "spot"}),
                     perp[["time", "close"]].rename(columns={"close": "perp"}), on="time", how="inner")
        if len(m):
            basis = pd.Series(((m["perp"] - m["spot"]) / m["spot"]).values, index=m["time"])
    return MarketData(symbol=symbol, market="crypto_futures", ohlcv=spot, perp_ohlcv=perp,
                      funding=(funding if len(funding) else None),
                      open_interest=(oi if len(oi) else None), basis=basis,
                      meta={"exchange": exchange, "timeframe": timeframe, "days": days})
