"""data_sources/deribit_options.py — REAL free Deribit option-chain + IV/RV data (Wave 1B).

Deribit's public API (no keys) provides the live BTC/ETH option chain (strikes/expiries, mark
price, mark_iv, full greeks) and the DVOL implied-volatility index history. Combined with realized
vol from the spot OHLCV (binance), this is enough to backtest the crypto-options strategy family
(VRP / IV-RV / straddle-strangle income / long-vol / skew / structure payoffs) for REAL — no
fabricated numbers. Offline-safe: fetch failures return empty frames the bt_* functions tag.

    chain = load_chain("BTC")          # live chain DataFrame (+ greeks)
    s = iv_rv_series("BTC", days=30)   # DataFrame{implied_vol, realized_vol} time series
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

_CACHE: dict = {}          # key -> (monotonic_ts, value)


def _ccxt_deribit():
    import ccxt
    ex = ccxt.deribit({"enableRateLimit": True})
    return ex


def _cached(key: str, ttl: float, fn):
    hit = _CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (now, val)
    return val


def load_chain(currency: str = "BTC") -> pd.DataFrame:
    """Live Deribit option chain for `currency` → DataFrame with strike, expiry, type, mark_iv,
    mark_price, underlying, delta/gamma/vega/theta. Empty DataFrame on failure."""
    def _fetch():
        d = _ccxt_deribit()
        d.load_markets()
        syms = [s for s, v in d.markets.items()
                if v.get("option") and v.get("base") == currency and v.get("active")]
        tickers = d.fetch_tickers(syms[:600])      # cap for latency
        rows = []
        for sym, t in tickers.items():
            info = t.get("info", {}) or {}
            mk = d.markets.get(sym, {})
            g = info.get("greeks", {}) or {}
            rows.append({
                "symbol": sym,
                "type": "C" if mk.get("optionType") == "call" else "P",
                "strike": float(mk.get("strike") or 0.0),
                "expiry": mk.get("expiry"),
                "mark_iv": float(info.get("mark_iv") or 0.0) / 100.0,   # → fraction
                "mark_price": float(info.get("mark_price") or 0.0),
                "underlying": float(info.get("underlying_price") or info.get("index_price") or 0.0),
                "delta": float(g.get("delta") or 0.0), "gamma": float(g.get("gamma") or 0.0),
                "vega": float(g.get("vega") or 0.0), "theta": float(g.get("theta") or 0.0),
                "oi": float(info.get("open_interest") or 0.0),
            })
        return pd.DataFrame(rows)
    try:
        return _cached(f"chain:{currency}", 300, _fetch)
    except Exception:
        return pd.DataFrame()


def _dvol(currency: str = "BTC") -> pd.Series:
    """Deribit DVOL implied-vol index history (fraction) indexed by ms timestamp."""
    d = _ccxt_deribit()
    vh = d.fetch_volatility_history(currency)
    if not vh:
        return pd.Series(dtype=float)
    s = pd.Series({int(p["timestamp"]): float(p["volatility"]) / 100.0 for p in vh})
    return s.sort_index()


def _realized_vol(currency: str = "BTC", *, days: int = 30) -> pd.Series:
    """Annualised realized vol from binance spot daily returns (rolling 10d), ms-indexed."""
    import ccxt
    b = ccxt.binance({"enableRateLimit": True})
    raw = b.fetch_ohlcv(f"{currency}/USDT", "1d", limit=max(40, days + 12))
    if not raw:
        return pd.Series(dtype=float)
    df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
    ret = np.log(df["close"] / df["close"].shift(1))
    rv = ret.rolling(10).std() * np.sqrt(365.0)
    return pd.Series(rv.to_numpy(), index=df["time"].astype(int).to_numpy()).dropna()


def iv_rv_series(currency: str = "BTC", *, days: int = 30) -> pd.DataFrame:
    """Aligned {implied_vol (DVOL), realized_vol} daily series — the real basis for vol backtests."""
    def _fetch():
        iv = _dvol(currency)
        rv = _realized_vol(currency, days=days)
        if iv.empty or rv.empty:
            return pd.DataFrame()
        # resample DVOL (hourly) to daily, align to RV's daily timestamps by nearest
        iv_daily = iv.groupby(iv.index // 86_400_000).last()
        rv_daily = rv.groupby(rv.index // 86_400_000).last()
        df = pd.DataFrame({"implied_vol": iv_daily, "realized_vol": rv_daily}).dropna()
        return df.tail(days).reset_index(drop=True)
    try:
        return _cached(f"ivrv:{currency}:{days}", 600, _fetch)
    except Exception:
        return pd.DataFrame()
