"""catalog/multi_indicator.py — multi-indicator confluence family (executable on OHLCV).

Composite setups pros actually trade: trend+pullback continuation, ADX-gated MA crossover,
Elder triple-screen, Bollinger+RSI, Supertrend+RSI, VWAP+RSI intraday, EMA-cloud
(Ichimoku-lite), trend-day vs reversal-day, plus the crypto-spot staples DCA (accumulate
below the long MA) and grid (mean-revert inside a range). Confluence filters cut the
whipsaw that single-indicator versions suffer.
OSS: Elder triple-screen, freqtrade-strategies, NostalgiaForInfinity (multi-TF confluence).
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, long_short, stateful_band

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _rsi_macd(f):
    up = (f["rsi"] > 50) & (f["macd"] > f["macd_signal"])
    dn = (f["rsi"] < 50) & (f["macd"] < f["macd_signal"])
    return long_short(up, dn, f.index)


def _pullback_cont(f):
    up_trend = (f["close"] > f["ema_200"]) & (f["ema_fast"] > f["ema_slow"])
    dn_trend = (f["close"] < f["ema_200"]) & (f["ema_fast"] < f["ema_slow"])
    return stateful_band(up_trend & (f["rsi"] < 40), f["rsi"] > 60,
                         dn_trend & (f["rsi"] > 60), f["rsi"] < 40, index=f.index)


def _adx_gated_cross(f):
    trending = f["adx"] > 20
    return long_short(trending & (f["ema_fast"] > f["ema_slow"]),
                      trending & (f["ema_fast"] < f["ema_slow"]), f.index)


def _triple_screen(f):
    # Elder: long-term tide (200-EMA) + medium oscillator (MACD-hist) entry
    tide_up = f["close"] > f["ema_200"]
    tide_dn = f["close"] < f["ema_200"]
    return stateful_band(tide_up & (f["macd_hist"] > 0) & (f["macd_hist"].shift(1) <= 0),
                         f["macd_hist"] < 0,
                         tide_dn & (f["macd_hist"] < 0) & (f["macd_hist"].shift(1) >= 0),
                         f["macd_hist"] > 0, index=f.index)


def _bb_rsi(f):
    up = (f["close"] < f["bb_lower"]) & (f["rsi"] < 35)
    dn = (f["close"] > f["bb_upper"]) & (f["rsi"] > 65)
    return stateful_band(up, f["close"] > f["bb_mid"], dn, f["close"] < f["bb_mid"],
                         index=f.index)


def _supertrend_rsi(f):
    up = (f["supertrend_dir"] > 0) & (f["rsi"] > 50)
    dn = (f["supertrend_dir"] < 0) & (f["rsi"] < 50)
    return long_short(up, dn, f.index)


def _vwap_rsi(f):
    up = (f["close"] > f["vwap"]) & (f["rsi"] > 50)
    dn = (f["close"] < f["vwap"]) & (f["rsi"] < 50)
    return long_short(up, dn, f.index)


def _ema_cloud(f):
    # Ichimoku-lite: price above fast & slow EMA "cloud" → long
    cloud_top = pd.concat([f["ema_fast"], f["ema_slow"]], axis=1).max(axis=1)
    cloud_bot = pd.concat([f["ema_fast"], f["ema_slow"]], axis=1).min(axis=1)
    return long_short(f["close"] > cloud_top, f["close"] < cloud_bot, f.index)


def _trend_day(f):
    # trend-day: strong directional body + close in top/bottom of range + above VWAP
    strong_up = (f["body"] > 1.0 * f["atr_pct"]) & (f["close"] > f["vwap"])
    strong_dn = (f["body"] < -1.0 * f["atr_pct"]) & (f["close"] < f["vwap"])
    return long_short(strong_up, strong_dn, f.index)


def _dca_accumulate(f):
    # DCA / accumulation: long-only, accumulate while price is below the long MA (value zone)
    return stateful_band(f["close"] < f["sma_200"], f["close"] > f["sma_fast"] * 1.05,
                         index=f.index)


def _grid_range(f):
    # grid trading proxy: in a non-trending (low-ADX) range, fade band extremes
    ranging = f["adx"] < 20
    return stateful_band(ranging & (f["bb_pctb"] < 0.2), f["bb_pctb"] > 0.5,
                         ranging & (f["bb_pctb"] > 0.8), f["bb_pctb"] < 0.5, index=f.index)


def _mk(name, family, logic, signal, oss, cat="momentum", tf="intraday–swing",
        segs=_SEGS, short=True, **params):
    return LibraryStrategy(name=name, category=cat, family=family, logic=logic,
                           segments=segs, timeframe=tf, signal=signal, oss_source=oss,
                           params=params, allow_short=short, notes="multi-indicator confluence")


STRATEGIES = [
    _mk("combo_rsi_macd", "confluence", "RSI>50 AND MACD>signal → long (dual confirmation).",
        _rsi_macd, "RSI+MACD confluence"),
    _mk("combo_pullback_continuation", "pullback",
        "In an established trend, buy the RSI<40 pullback / sell the RSI>60 bounce.",
        _pullback_cont, "Pullback Continuation", cat="trend_following"),
    _mk("combo_adx_gated_cross", "filtered_trend",
        "Trade the EMA crossover only when ADX>20 (filters range-bound whipsaw).",
        _adx_gated_cross, "ADX-gated MA cross", cat="trend_following"),
    _mk("combo_elder_triple_screen", "triple_screen",
        "Elder triple-screen: 200-EMA tide + MACD-hist trigger in the tide's direction.",
        _triple_screen, "Elder Triple Screen", cat="trend_following"),
    _mk("combo_bollinger_rsi", "confluence",
        "Lower-band + RSI<35 long / upper-band + RSI>65 short (band+oscillator).",
        _bb_rsi, "Bollinger+RSI", cat="mean_reversion"),
    _mk("combo_supertrend_rsi", "confluence",
        "Supertrend direction confirmed by RSI>50/<50.",
        _supertrend_rsi, "Supertrend+RSI", cat="trend_following"),
    _mk("combo_vwap_rsi", "confluence",
        "Price vs cumulative VWAP confirmed by RSI side (intraday).",
        _vwap_rsi, "VWAP+RSI", cat="trend_following", tf="intraday",
        segs=("nse_intraday", "crypto_spot", "crypto_futures", "mcx_commodities")),
    _mk("combo_ema_cloud", "ichimoku_lite",
        "Price above/below the fast/slow EMA 'cloud' (Ichimoku-lite).",
        _ema_cloud, "EMA cloud / Ichimoku-lite", cat="trend_following"),
    _mk("combo_trend_day", "trend_day",
        "Trend-Day: strong directional body holding above/below VWAP.",
        _trend_day, "Trend Day strategy", cat="momentum", tf="intraday",
        segs=("nse_intraday", "crypto_spot", "crypto_futures")),
    _mk("spot_dca_accumulate", "dca",
        "Dollar-cost-average / accumulate long while price sits below the 200-SMA value zone.",
        _dca_accumulate, "DCA accumulation", cat="mean_reversion", tf="positional",
        segs=("crypto_spot", "nse_cash"), short=False),
    _mk("spot_grid_range", "grid",
        "Grid trading: in a low-ADX range, fade Bollinger %B extremes back to mid.",
        _grid_range, "grid trading", cat="mean_reversion", tf="intraday",
        segs=("crypto_spot", "crypto_futures")),
]
