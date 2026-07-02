"""catalog/trend.py — Trend-Following family (executable on OHLCV).

Capture large directional moves: MA crossovers, Donchian/Turtle breakouts, Supertrend,
ADX/DI trend, MACD trend, Aroon, PSAR, KAMA/TEMA, regression-slope trend. Mirrors the
classic CTA / systematic-macro playbook (Turtle, Seban Supertrend, Wilder ADX).
OSS: freqtrade/freqtrade-strategies, je-suis-tm/quant-trading, Zerodha Varsity TA.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import DataReq, LibraryStrategy, long_short

_ALL_TREND_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
                   "crypto_spot", "crypto_futures")


def _ma_cross(fast: str, slow: str):
    def fn(f: pd.DataFrame) -> pd.Series:
        return long_short(f[fast] > f[slow], f[fast] < f[slow], f.index)
    return fn


def _sig_supertrend(f):
    return long_short(f["supertrend_dir"] > 0, f["supertrend_dir"] < 0, f.index)


def _sig_adx_di(f):
    trend = f["adx"] > 25
    return long_short(trend & (f["plus_di"] > f["minus_di"]),
                      trend & (f["minus_di"] > f["plus_di"]), f.index)


def _sig_macd(f):
    return long_short(f["macd"] > f["macd_signal"], f["macd"] < f["macd_signal"], f.index)


def _sig_macd_zero(f):
    return long_short((f["macd"] > 0) & (f["macd_hist"] > 0),
                      (f["macd"] < 0) & (f["macd_hist"] < 0), f.index)


def _sig_donchian(f):
    return long_short(f["close"] > f["donchian_hi"], f["close"] < f["donchian_lo"], f.index)


def _sig_turtle_55(f):
    return long_short(f["close"] > f["hh_55"], f["close"] < f["ll_55"], f.index)


def _sig_aroon(f):
    return long_short((f["aroon_up"] > 70) & (f["aroon_down"] < 30),
                      (f["aroon_down"] > 70) & (f["aroon_up"] < 30), f.index)


def _sig_psar(f):
    return long_short(f["close"] > f["psar"], f["close"] < f["psar"], f.index)


def _sig_slope(f):
    return long_short(f["linreg_slope"] > 0, f["linreg_slope"] < 0, f.index)


def _sig_sma200(f):
    # long-only regime filter: hold long while price > 200-SMA (classic CTA filter)
    return long_short(f["close"] > f["sma_200"], pd.Series(False, index=f.index), f.index)


def _sig_kama(f):
    return long_short(f["close"] > f["kama"], f["close"] < f["kama"], f.index)


def _sig_tema(f):
    return long_short(f["close"] > f["tema"], f["close"] < f["tema"], f.index)


def _sig_triple_ma(f):
    up = (f["ema_fast"] > f["ema_slow"]) & (f["ema_slow"] > f["ema_200"])
    dn = (f["ema_fast"] < f["ema_slow"]) & (f["ema_slow"] < f["ema_200"])
    return long_short(up, dn, f.index)


def _sig_st_macd(f):
    up = (f["supertrend_dir"] > 0) & (f["macd"] > f["macd_signal"])
    dn = (f["supertrend_dir"] < 0) & (f["macd"] < f["macd_signal"])
    return long_short(up, dn, f.index)


STRATEGIES = [
    LibraryStrategy(
        name="trend_sma_crossover", category="trend_following", family="ma_crossover",
        logic="Fast SMA above slow SMA → long; below → short (Dual Moving Average).",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_ma_cross("sma_fast", "sma_slow"),
        oss_source="je-suis-tm/quant-trading; freqtrade-strategies",
        params={"fast": 10, "slow": 30}),
    LibraryStrategy(
        name="trend_ema_crossover", category="trend_following", family="ma_crossover",
        logic="Fast EMA / slow EMA crossover — faster reaction than SMA.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_ma_cross("ema_fast", "ema_slow"),
        oss_source="freqtrade-strategies (EMA cross)", params={"fast": 10, "slow": 30}),
    LibraryStrategy(
        name="trend_golden_death_cross", category="trend_following", family="ma_crossover",
        logic="Price vs 200-SMA golden/death-cross regime (long-bias trend filter).",
        segments=_ALL_TREND_SEGS, timeframe="swing–positional",
        signal=_sig_sma200, allow_short=False,
        oss_source="classic CTA filter", params={"ma": 200}),
    LibraryStrategy(
        name="trend_triple_ma_stack", category="trend_following", family="ma_stack",
        logic="EMA fast>slow>200 stacked up → long; stacked down → short.",
        segments=_ALL_TREND_SEGS, timeframe="swing",
        signal=_sig_triple_ma, oss_source="GMMA / triple-MA",
        params={"emas": [10, 30, 200]}),
    LibraryStrategy(
        name="trend_supertrend", category="trend_following", family="supertrend",
        logic="Follow Supertrend direction flip (ATR-band trailing trend).",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_sig_supertrend, oss_source="Olivier Seban Supertrend; Zerodha Varsity",
        params={"atr": 14, "mult": 3.0}),
    LibraryStrategy(
        name="trend_adx_di", category="trend_following", family="adx",
        logic="ADX>25 confirms trend; +DI/-DI cross gives direction (Wilder DMS).",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_sig_adx_di, oss_source="Wilder DMS / ADX", params={"adx": 14, "thr": 25}),
    LibraryStrategy(
        name="trend_macd", category="trend_following", family="macd",
        logic="MACD line above/below signal line → long/short.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_sig_macd, oss_source="freqtrade-strategies (MACD)",
        params={"fast": 12, "slow": 26, "signal": 9}),
    LibraryStrategy(
        name="trend_macd_zero_line", category="trend_following", family="macd",
        logic="MACD above zero AND histogram positive → strong-trend long (vice-versa).",
        segments=_ALL_TREND_SEGS, timeframe="swing",
        signal=_sig_macd_zero, oss_source="MACD zero-line", params={}),
    LibraryStrategy(
        name="trend_donchian_breakout", category="trend_following", family="donchian",
        logic="Close breaks 20-bar Donchian high → long; 20-bar low → short.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing",
        signal=_sig_donchian, oss_source="Donchian channel breakout",
        params={"n": 20}),
    LibraryStrategy(
        name="trend_turtle_55", category="trend_following", family="turtle",
        logic="Turtle System-2: 55-bar high/low breakout entries.",
        segments=_ALL_TREND_SEGS, timeframe="swing–positional",
        signal=_sig_turtle_55, oss_source="Turtle Trading rules", params={"n": 55}),
    LibraryStrategy(
        name="trend_aroon", category="trend_following", family="aroon",
        logic="Aroon-Up>70 & Aroon-Down<30 → fresh up-trend (and symmetric).",
        segments=_ALL_TREND_SEGS, timeframe="swing", signal=_sig_aroon,
        oss_source="Chande Aroon", params={"n": 14}),
    LibraryStrategy(
        name="trend_parabolic_sar", category="trend_following", family="psar",
        logic="Price above/below Parabolic SAR dots → long/short trailing trend.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing", signal=_sig_psar,
        oss_source="Wilder Parabolic SAR", params={"af": 0.02, "max": 0.2}),
    LibraryStrategy(
        name="trend_linreg_slope", category="trend_following", family="regression",
        logic="Sign of 14-bar linear-regression slope → trend direction.",
        segments=_ALL_TREND_SEGS, timeframe="swing", signal=_sig_slope,
        oss_source="LINEARREG_SLOPE (TA-Lib)", params={"n": 14}),
    LibraryStrategy(
        name="trend_kama", category="trend_following", family="adaptive_ma",
        logic="Kaufman Adaptive MA — price above/below KAMA (noise-adaptive trend).",
        segments=_ALL_TREND_SEGS, timeframe="swing", signal=_sig_kama,
        oss_source="Kaufman KAMA (TA-Lib)", params={"n": 30}),
    LibraryStrategy(
        name="trend_tema", category="trend_following", family="adaptive_ma",
        logic="Triple-EMA (low-lag) crossover of price.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing", signal=_sig_tema,
        oss_source="TEMA (TA-Lib)", params={"n": 10}),
    LibraryStrategy(
        name="trend_supertrend_macd_combo", category="trend_following", family="combo",
        logic="Supertrend direction confirmed by MACD line/signal — fewer whipsaws.",
        segments=_ALL_TREND_SEGS, timeframe="intraday–swing", signal=_sig_st_macd,
        oss_source="composite trend filter", params={}),
]
