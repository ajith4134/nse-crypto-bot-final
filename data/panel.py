"""Multi-asset PANEL data — a universe of timestamp-aligned series.

Enables CROSS-SECTIONAL nodes (WorldQuant 101 rank-alphas, cross-sectional
z-scoring, market factor / betting-against-beta, HRP/portfolio allocation) that
rank or allocate ACROSS many assets at each timestamp — which single-series nodes
can't do. The target asset (index 0 by default) is what the heads predict; the
rest of the universe is context. Loaders return (time, close, volume) tuples.
"""
from __future__ import annotations

import numpy as np

CRYPTO_UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                   "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "TRXUSDT"]
INDIAN_UNIVERSE = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
                   "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS", "AXISBANK.NS"]


def _load_one(symbol: str, source: str):
    if source == "crypto":
        from data.binance import load_klines
        rows = load_klines(symbol, "1h")
    else:
        from data.external import load_indian_equity
        rows = load_indian_equity(symbol)
    return [float(r[1]) for r in rows], [float(r[2]) for r in rows]   # close, volume


def make_panel(source: str = "crypto", target: int = 0) -> dict:
    """Universe panel aligned to a common length. Returns close[T,N], volume[T,N],
    log-returns[T-1,N], symbols, and the target column index."""
    universe = CRYPTO_UNIVERSE if source == "crypto" else INDIAN_UNIVERSE
    closes, vols, syms = [], [], []
    for s in universe:
        try:
            c, v = _load_one(s, source)
            if len(c) > 200:
                closes.append(c); vols.append(v); syms.append(s)
        except Exception:
            continue
    if len(syms) < 3:
        raise RuntimeError(f"panel needs >=3 assets, got {len(syms)} for {source}")
    T = min(len(c) for c in closes)
    close = np.asarray([c[-T:] for c in closes], dtype=float).T          # [T, N]
    volume = np.asarray([v[-T:] for v in vols], dtype=float).T           # [T, N]
    returns = np.diff(np.log(np.clip(close, 1e-9, None)), axis=0)        # [T-1, N]
    return {"symbols": syms, "close": close, "volume": volume,
            "returns": returns, "target": int(target), "T": T, "N": len(syms)}
