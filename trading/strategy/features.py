"""trading/strategy/features.py — OHLCV → feature frame via TA-Lib (T8.1, reuse-first).

Indicator math is delegated to **TA-Lib** (the battle-tested C library, 150+ indicators)
instead of hand-rolled formulas. We only do the glue: choose the feature set the genome
references, name the columns, and the few ratio features TA-Lib doesn't provide
(ret/atr_pct/zscore/range_pct/rvol) via pandas. All features are causal (TA-Lib
indicators use only past/current bars); the backtest executes signals on the next bar.

Falls back to pandas-only computation if TA-Lib is unavailable, so the module always
imports (the fallback is numerically close, not identical).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import talib
    _HAVE_TALIB = True
except Exception:  # pragma: no cover - env-dependent
    _HAVE_TALIB = False

FEATURE_NAMES: list[str] = [
    "ret", "sma_fast", "sma_slow", "ema", "rsi", "atr", "atr_pct",
    "mom", "vol", "zscore", "range_pct", "rvol",
]

# Binance-filter / order-flow building blocks (owner 2026-07-12): the app's OWN screener
# signals captured from the web account (orderflow_store._FIELDS). compute_features NaN-fills
# these when the real values weren't spliced (a plain OHLCV frame, or a symbol with no
# capture), so a genome that references one NEVER KeyErrors — it just sees NaN, which the
# generators ignore. autoresearch._frame splices the real values in for crypto research.
CRYPTO_EXTRA_FEATURES: list[str] = [
    "of_taker_ratio", "of_crowd_long", "of_smart_long", "of_oi",
    "of_funding", "of_liq_skew", "of_gofi",
]


def _talib_feats(df, close, high, low, fast, slow, mom_n):
    df["sma_fast"] = talib.SMA(close, timeperiod=fast)
    df["sma_slow"] = talib.SMA(close, timeperiod=slow)
    df["ema"] = talib.EMA(close, timeperiod=fast)
    df["rsi"] = talib.RSI(close, timeperiod=14)
    df["atr"] = talib.ATR(high, low, close, timeperiod=14)
    df["mom"] = talib.ROCP(close, timeperiod=mom_n)        # rate-of-change (fraction)


def _pandas_feats(df, close_s, fast, slow, mom_n):
    df["sma_fast"] = close_s.rolling(fast).mean()
    df["sma_slow"] = close_s.rolling(slow).mean()
    df["ema"] = close_s.ewm(span=fast, adjust=False).mean()
    delta = close_s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    # avg-loss == 0 with positive gains is a pure uptrend → RSI 100 (not neutral 50)
    df["rsi"] = rsi.mask((loss == 0) & (gain > 0), 100.0).fillna(50.0)
    prev = close_s.shift(1)
    tr = pd.concat([(df["high"] - df["low"]), (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["mom"] = close_s / close_s.shift(mom_n) - 1.0


def compute_features(ohlcv: pd.DataFrame, *, fast: int = 10, slow: int = 30,
                     mom_n: int = 10) -> pd.DataFrame:
    """OHLCV (open/high/low/close/volume) -> feature frame (TA-Lib), NaNs dropped."""
    need = {"open", "high", "low", "close", "volume"}
    missing = need - set(ohlcv.columns)
    if missing:
        raise ValueError(f"ohlcv missing columns: {sorted(missing)}")
    df = ohlcv.copy()
    close_s, high_s, low_s, vol_s = df["close"], df["high"], df["low"], df["volume"]

    if _HAVE_TALIB:
        c, h, l = (close_s.to_numpy(dtype="float64"), high_s.to_numpy(dtype="float64"),
                   low_s.to_numpy(dtype="float64"))
        _talib_feats(df, c, h, l, fast, slow, mom_n)
    else:  # pragma: no cover
        _pandas_feats(df, close_s, fast, slow, mom_n)

    # ratio/statistical features (pandas — not in TA-Lib)
    df["ret"] = close_s.pct_change()
    df["atr_pct"] = df["atr"] / close_s
    df["vol"] = df["ret"].rolling(slow).std()
    df["zscore"] = (close_s - df["sma_slow"]) / close_s.rolling(slow).std()
    df["range_pct"] = (high_s - low_s) / close_s
    df["rvol"] = vol_s / vol_s.rolling(slow).mean()

    # Drop warm-up NaNs on the BASE features only — NOT the Binance-filter extras, whose NaN
    # (a symbol/frame with no captured order-flow) is legitimate and must not delete every row.
    base = [c for c in FEATURE_NAMES if c in df.columns]
    df = df.dropna(subset=base).reset_index(drop=True)
    # guarantee every declared Binance-filter column exists so a genome referencing one sees
    # NaN (ignored) instead of KeyError when the real order-flow wasn't spliced onto this frame
    for f in CRYPTO_EXTRA_FEATURES:
        if f not in df.columns:
            df[f] = np.nan
    return df
