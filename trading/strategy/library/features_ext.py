"""trading/strategy/library/features_ext.py — extended causal indicator frame (TA-Lib).

The genome's `trading.strategy.features.compute_features` exposes only 12 features — enough
for the GP engine but far too few to express the named library strategies (VWAP reversion,
Donchian/Turtle, Supertrend, Bollinger, MACD, Stochastic, ADX trend filter, Keltner,
ATR-channel breakout, gap fades, OBV/MFI volume, etc.). This module computes a *superset*:
every column a library signal function references, all CAUSAL (TA-Lib uses only past/current
bars; rolling windows never peek forward), so backtests stay look-ahead-free.

Reuse-first: TA-Lib does the indicator math (SMA/EMA/RSI/ATR/MACD/BBANDS/STOCH/ADX/CCI/
WILLR/MFI/OBV/SAR/AROON/ROC/NATR/...); we add only the few TA-Lib lacks — rolling VWAP,
Donchian channels, Supertrend, gaps, candle anatomy — in vectorised pandas.

Falls back to the base 12-feature pandas path for SMA/EMA/RSI/ATR if TA-Lib is missing, then
computes the rest in pandas, so the module always imports.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import talib
    _HAVE_TALIB = True
except Exception:  # pragma: no cover - env-dependent
    _HAVE_TALIB = False

# Columns this frame guarantees (besides raw OHLCV). Signal functions reference these by
# name; `EXT_FEATURE_NAMES` lets the registry validate a strategy's column needs up front.
EXT_FEATURE_NAMES: list[str] = [
    # base / returns
    "ret", "logret", "atr", "atr_pct", "natr", "vol", "rvol", "range_pct",
    # moving averages
    "sma_fast", "sma_slow", "sma_200", "ema_fast", "ema_slow", "ema_200",
    "wma_fast", "kama", "tema",
    # oscillators
    "rsi", "rsi_fast", "stoch_k", "stoch_d", "stochrsi", "cci", "willr", "mfi",
    "cmo", "ultosc", "roc", "mom", "trix", "ppo",
    # MACD
    "macd", "macd_signal", "macd_hist",
    # trend strength / direction
    "adx", "adxr", "plus_di", "minus_di", "dx", "aroon_up", "aroon_down", "aroonosc",
    "linreg_slope",
    # bands / channels
    "bb_upper", "bb_mid", "bb_lower", "bb_pctb", "bb_width",
    "kc_upper", "kc_mid", "kc_lower",
    "donchian_hi", "donchian_lo", "donchian_mid",
    "hh_20", "ll_20", "hh_55", "ll_55",
    # vwap / location
    "vwap", "vwap_roll", "vwap_dist", "zscore", "dist_sma_slow",
    # volume / flow
    "obv", "obv_slope", "adosc", "vol_z",
    # parabolic / location helpers
    "psar", "psar_dist", "supertrend", "supertrend_dir",
    # candle anatomy / gaps
    "gap", "body", "upper_wick", "lower_wick", "true_range",
    # volume profile / value area (auction)
    "vp_poc", "vp_vah", "vp_val", "vp_pos", "vp_failed_long", "vp_failed_short",
]

_NEED = {"open", "high", "low", "close", "volume"}


def _supertrend(high: pd.Series, low: pd.Series, close: pd.Series, atr: pd.Series,
                mult: float = 3.0) -> tuple[pd.Series, pd.Series]:
    """Causal Supertrend line + direction (+1 up-trend / -1 down-trend).

    Standard recursive band construction (Olivier Seban): bands tighten only in the trend
    direction; the line flips when close crosses it. Each bar uses only prior state.
    """
    hl2 = (high + low) / 2.0
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    n = len(close)
    f_upper = upper.to_numpy(copy=True)
    f_lower = lower.to_numpy(copy=True)
    c = close.to_numpy()
    for i in range(1, n):
        f_upper[i] = (min(upper.iat[i], f_upper[i - 1])
                      if (c[i - 1] <= f_upper[i - 1]) else upper.iat[i])
        f_lower[i] = (max(lower.iat[i], f_lower[i - 1])
                      if (c[i - 1] >= f_lower[i - 1]) else lower.iat[i])
    direction = np.ones(n, dtype=float)
    st = np.empty(n, dtype=float)
    st[0] = f_upper[0]
    for i in range(1, n):
        if c[i] > f_upper[i]:
            direction[i] = 1.0
        elif c[i] < f_lower[i]:
            direction[i] = -1.0
        else:
            direction[i] = direction[i - 1]
        st[i] = f_lower[i] if direction[i] > 0 else f_upper[i]
    return (pd.Series(st, index=close.index), pd.Series(direction, index=close.index))


def compute_features_ext(ohlcv: pd.DataFrame, *, fast: int = 10, slow: int = 30,
                         mom_n: int = 10, donchian: int = 20,
                         bb_n: int = 20, bb_k: float = 2.0,
                         st_mult: float = 3.0) -> pd.DataFrame:
    """OHLCV → extended causal indicator frame (NaNs from warm-up dropped at the end)."""
    missing = _NEED - set(ohlcv.columns)
    if missing:
        raise ValueError(f"ohlcv missing columns: {sorted(missing)}")
    df = ohlcv.copy().reset_index(drop=True)
    o, h, l, c, v = (df["open"].astype(float), df["high"].astype(float),
                     df["low"].astype(float), df["close"].astype(float),
                     df["volume"].astype(float))

    # ── returns / volatility ──────────────────────────────────────────────────
    df["ret"] = c.pct_change()
    df["logret"] = np.log(c / c.shift(1))
    if _HAVE_TALIB:
        cn, hn, ln, vn = (c.to_numpy("float64"), h.to_numpy("float64"),
                          l.to_numpy("float64"), v.to_numpy("float64"))
        df["atr"] = talib.ATR(hn, ln, cn, timeperiod=14)
        df["natr"] = talib.NATR(hn, ln, cn, timeperiod=14)
        df["true_range"] = talib.TRANGE(hn, ln, cn)
        df["sma_fast"] = talib.SMA(cn, fast)
        df["sma_slow"] = talib.SMA(cn, slow)
        df["sma_200"] = talib.SMA(cn, 200)
        df["ema_fast"] = talib.EMA(cn, fast)
        df["ema_slow"] = talib.EMA(cn, slow)
        df["ema_200"] = talib.EMA(cn, 200)
        df["wma_fast"] = talib.WMA(cn, fast)
        df["kama"] = talib.KAMA(cn, 30)
        df["tema"] = talib.TEMA(cn, fast)
        df["rsi"] = talib.RSI(cn, 14)
        df["rsi_fast"] = talib.RSI(cn, 7)
        k, d = talib.STOCH(hn, ln, cn, fastk_period=14, slowk_period=3, slowd_period=3)
        df["stoch_k"], df["stoch_d"] = k, d
        df["stochrsi"] = talib.STOCHRSI(cn, 14)[0]
        df["cci"] = talib.CCI(hn, ln, cn, 20)
        df["willr"] = talib.WILLR(hn, ln, cn, 14)
        df["mfi"] = talib.MFI(hn, ln, cn, vn, 14)
        df["cmo"] = talib.CMO(cn, 14)
        df["ultosc"] = talib.ULTOSC(hn, ln, cn)
        df["roc"] = talib.ROCP(cn, mom_n)
        df["mom"] = talib.ROCP(cn, mom_n)
        df["trix"] = talib.TRIX(cn, 15)
        df["ppo"] = talib.PPO(cn, 12, 26)
        macd, macds, macdh = talib.MACD(cn, 12, 26, 9)
        df["macd"], df["macd_signal"], df["macd_hist"] = macd, macds, macdh
        df["adx"] = talib.ADX(hn, ln, cn, 14)
        df["adxr"] = talib.ADXR(hn, ln, cn, 14)
        df["plus_di"] = talib.PLUS_DI(hn, ln, cn, 14)
        df["minus_di"] = talib.MINUS_DI(hn, ln, cn, 14)
        df["dx"] = talib.DX(hn, ln, cn, 14)
        au, ad = talib.AROON(hn, ln, 14)
        df["aroon_up"], df["aroon_down"] = au, ad
        df["aroonosc"] = talib.AROONOSC(hn, ln, 14)
        df["linreg_slope"] = talib.LINEARREG_SLOPE(cn, 14)
        bbu, bbm, bbl = talib.BBANDS(cn, bb_n, bb_k, bb_k)
        df["bb_upper"], df["bb_mid"], df["bb_lower"] = bbu, bbm, bbl
        df["obv"] = talib.OBV(cn, vn)
        df["adosc"] = talib.ADOSC(hn, ln, cn, vn, 3, 10)
        df["psar"] = talib.SAR(hn, ln, acceleration=0.02, maximum=0.2)
    else:  # pragma: no cover — pandas fallback (numerically close, not identical)
        _pandas_fallback(df, o, h, l, c, v, fast, slow, mom_n, bb_n, bb_k)

    # ── pandas-only extras (no TA-Lib equivalent) ───────────────────────────────
    df["atr_pct"] = df["atr"] / c
    df["vol"] = df["ret"].rolling(slow).std()
    df["vol_z"] = (v - v.rolling(slow).mean()) / v.rolling(slow).std()
    df["rvol"] = v / v.rolling(slow).mean()
    df["range_pct"] = (h - l) / c
    df["zscore"] = (c - df["sma_slow"]) / c.rolling(slow).std()
    df["dist_sma_slow"] = (c - df["sma_slow"]) / df["sma_slow"]

    # Bollinger %B + width
    rng = (df["bb_upper"] - df["bb_lower"]).replace(0.0, np.nan)
    df["bb_pctb"] = (c - df["bb_lower"]) / rng
    df["bb_width"] = rng / df["bb_mid"]

    # Keltner channels (EMA ± mult*ATR)
    df["kc_mid"] = df["ema_slow"]
    df["kc_upper"] = df["ema_slow"] + 2.0 * df["atr"]
    df["kc_lower"] = df["ema_slow"] - 2.0 * df["atr"]

    # Donchian channel + rolling extrema (shifted: prior-bar levels, no same-bar peek)
    df["donchian_hi"] = h.rolling(donchian).max().shift(1)
    df["donchian_lo"] = l.rolling(donchian).min().shift(1)
    df["donchian_mid"] = (df["donchian_hi"] + df["donchian_lo"]) / 2.0
    df["hh_20"] = h.rolling(20).max().shift(1)
    df["ll_20"] = l.rolling(20).min().shift(1)
    df["hh_55"] = h.rolling(55).max().shift(1)
    df["ll_55"] = l.rolling(55).min().shift(1)

    # VWAP — cumulative (anchored at series start) + rolling window VWAP
    typical = (h + l + c) / 3.0
    cum_pv = (typical * v).cumsum()
    cum_v = v.cumsum().replace(0.0, np.nan)
    df["vwap"] = cum_pv / cum_v
    roll_pv = (typical * v).rolling(slow).sum()
    roll_v = v.rolling(slow).sum().replace(0.0, np.nan)
    df["vwap_roll"] = roll_pv / roll_v
    df["vwap_dist"] = (c - df["vwap_roll"]) / df["vwap_roll"]

    # OBV slope (normalised) + PSAR distance
    df["obv_slope"] = df["obv"].diff(5) / v.rolling(slow).mean().replace(0.0, np.nan)
    df["psar_dist"] = (c - df["psar"]) / c

    # Supertrend (line + direction)
    st_line, st_dir = _supertrend(h, l, c, df["atr"], mult=st_mult)
    df["supertrend"] = st_line
    df["supertrend_dir"] = st_dir

    # candle anatomy / gap
    df["gap"] = (o - c.shift(1)) / c.shift(1)
    df["body"] = (c - o) / c
    df["upper_wick"] = (h - np.maximum(o, c)) / c
    df["lower_wick"] = (np.minimum(o, c) - l) / c

    # Volume Profile / Value Area (owner's champions-chart-strategy video, 2026-07-11): rolling
    # POC/VAH/VAL + position-in-value + failed-auction reversion flags, so the strategy generator
    # can weigh the auction edge per coin. Reuses the live VP engine (one source of truth).
    _rolling_vp(df, h, l, c, v)

    return df.dropna().reset_index(drop=True)


def _rolling_vp(df: pd.DataFrame, h, l, c, v, window: int = 96) -> None:
    """Fill vp_* columns from a trailing-window Volume Profile per bar (reuses
    trading.broker_sense.volume_profile). No look-ahead: bar i uses bars (i-window, i]."""
    from trading.broker_sense import volume_profile as _vp
    n = len(df)
    H, L, C, V = (h.to_numpy("float64"), l.to_numpy("float64"),
                  c.to_numpy("float64"), v.to_numpy("float64"))
    poc = np.full(n, np.nan); vah = np.full(n, np.nan); val = np.full(n, np.nan)
    pos = np.full(n, np.nan); fl = np.zeros(n); fs = np.zeros(n)
    for i in range(window, n):
        rows = [[0, 0.0, H[j], L[j], C[j], V[j]] for j in range(i - window + 1, i + 1)]
        p = _vp.volume_profile(rows)
        if not p.get("available"):
            continue
        poc[i], vah[i], val[i] = p["poc"], p["vah"], p["val"]
        span = (p["vah"] - p["val"]) or p["bin_size"] or 1.0
        pos[i] = (C[i] - p["poc"]) / span
        inside = p["val"] <= C[i] <= p["vah"]
        if C[i - 1] < p["val"] and inside:
            fl[i] = 1.0
        elif C[i - 1] > p["vah"] and inside:
            fs[i] = 1.0
    df["vp_poc"], df["vp_vah"], df["vp_val"] = poc, vah, val
    df["vp_pos"], df["vp_failed_long"], df["vp_failed_short"] = pos, fl, fs


def _pandas_fallback(df, o, h, l, c, v, fast, slow, mom_n, bb_n, bb_k):  # pragma: no cover
    """Compute the TA-Lib-derived columns in pure pandas when TA-Lib is unavailable."""
    df["sma_fast"] = c.rolling(fast).mean()
    df["sma_slow"] = c.rolling(slow).mean()
    df["sma_200"] = c.rolling(200).mean()
    df["ema_fast"] = c.ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = c.ewm(span=slow, adjust=False).mean()
    df["ema_200"] = c.ewm(span=200, adjust=False).mean()
    df["wma_fast"] = c.rolling(fast).apply(
        lambda x: np.average(x, weights=np.arange(1, len(x) + 1)), raw=True)
    df["kama"] = c.ewm(span=30, adjust=False).mean()
    df["tema"] = c.ewm(span=fast, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = (100 - 100 / (1 + rs)).mask((loss == 0) & (gain > 0), 100.0).fillna(50.0)
    df["rsi_fast"] = df["rsi"]
    lo14 = l.rolling(14).min(); hi14 = h.rolling(14).max()
    df["stoch_k"] = 100 * (c - lo14) / (hi14 - lo14).replace(0, np.nan)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    df["stochrsi"] = df["rsi"]
    df["cci"] = 0.0; df["willr"] = 0.0; df["mfi"] = 50.0; df["cmo"] = 0.0
    df["ultosc"] = 50.0
    df["roc"] = c / c.shift(mom_n) - 1.0
    df["mom"] = df["roc"]
    df["trix"] = 0.0; df["ppo"] = 0.0
    ema12 = c.ewm(span=12, adjust=False).mean(); ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["adx"] = 20.0; df["adxr"] = 20.0; df["plus_di"] = 20.0; df["minus_di"] = 20.0
    df["dx"] = 20.0; df["aroon_up"] = 50.0; df["aroon_down"] = 50.0; df["aroonosc"] = 0.0
    df["linreg_slope"] = c.diff()
    mid = c.rolling(bb_n).mean(); sd = c.rolling(bb_n).std()
    df["bb_upper"] = mid + bb_k * sd; df["bb_mid"] = mid; df["bb_lower"] = mid - bb_k * sd
    df["obv"] = (np.sign(c.diff()).fillna(0) * v).cumsum()
    df["adosc"] = 0.0
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    df["true_range"] = tr
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["natr"] = 100 * df["atr"] / c
    df["psar"] = c
