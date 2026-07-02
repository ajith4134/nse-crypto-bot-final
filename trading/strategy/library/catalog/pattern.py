"""catalog/pattern.py — candlestick / price-action family (executable on OHLCV).

Reversal & continuation candle patterns built from the causal candle-anatomy columns
(body, upper_wick, lower_wick, gap) so they run with or without TA-Lib: engulfing, hammer/
shooting-star pin bars, doji-then-break, three-bar reversal, marubozu continuation, harami.
Entries are stateful (hold until an EMA-mid exit) so a one-bar pattern produces a tradeable
position.
OSS: TA-Lib CDL* pattern set (mirrored), Bulkowski pattern stats.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, stateful_band

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _bull_engulf(f):
    prev_red = f["body"].shift(1) < 0
    cur_green = f["body"] > 0
    engulf_up = prev_red & cur_green & (f["close"] > f["open"].shift(1)) & (f["open"] < f["close"].shift(1))
    prev_green = f["body"].shift(1) > 0
    cur_red = f["body"] < 0
    engulf_dn = prev_green & cur_red & (f["close"] < f["open"].shift(1)) & (f["open"] > f["close"].shift(1))
    return stateful_band(engulf_up, f["close"] < f["ema_fast"],
                         engulf_dn, f["close"] > f["ema_fast"], index=f.index)


def _hammer(f):
    # hammer: small body, long lower wick, near recent lows → bullish; inverse = shooting star
    small_body = f["body"].abs() < 0.6 * f["range_pct"]
    hammer = small_body & (f["lower_wick"] > 2.0 * f["body"].abs()) & (f["close"] < f["sma_slow"])
    star = small_body & (f["upper_wick"] > 2.0 * f["body"].abs()) & (f["close"] > f["sma_slow"])
    return stateful_band(hammer, f["close"] < f["ema_fast"],
                         star, f["close"] > f["ema_fast"], index=f.index)


def _doji_break(f):
    doji = f["body"].abs() < 0.1 * f["range_pct"]
    up = doji.shift(1).fillna(False) & (f["close"] > f["high"].shift(1))
    dn = doji.shift(1).fillna(False) & (f["close"] < f["low"].shift(1))
    return stateful_band(up, f["close"] < f["ema_fast"], dn, f["close"] > f["ema_fast"],
                         index=f.index)


def _three_bar_reversal(f):
    down3 = (f["body"] < 0) & (f["body"].shift(1) < 0) & (f["body"].shift(2) < 0)
    up3 = (f["body"] > 0) & (f["body"].shift(1) > 0) & (f["body"].shift(2) > 0)
    return stateful_band(down3.shift(1).fillna(False) & (f["body"] > 0), f["close"] < f["ema_fast"],
                         up3.shift(1).fillna(False) & (f["body"] < 0), f["close"] > f["ema_fast"],
                         index=f.index)


def _marubozu(f):
    maru_up = (f["body"] > 0.8 * f["range_pct"]) & (f["upper_wick"] < 0.1 * f["range_pct"])
    maru_dn = (f["body"] < -0.8 * f["range_pct"]) & (f["lower_wick"] < 0.1 * f["range_pct"])
    return stateful_band(maru_up, f["close"] < f["ema_fast"],
                         maru_dn, f["close"] > f["ema_fast"], index=f.index)


def _harami(f):
    inside = (f["high"] < f["high"].shift(1)) & (f["low"] > f["low"].shift(1))
    bull = inside & (f["body"].shift(1) < 0) & (f["body"] > 0)
    bear = inside & (f["body"].shift(1) > 0) & (f["body"] < 0)
    return stateful_band(bull, f["close"] < f["ema_fast"], bear, f["close"] > f["ema_fast"],
                         index=f.index)


def _mk(name, family, logic, signal, oss):
    return LibraryStrategy(name=name, category="mean_reversion", family=family, logic=logic,
                           segments=_SEGS, timeframe="intraday–swing", signal=signal,
                           oss_source=oss, notes="candlestick / price-action pattern")


STRATEGIES = [
    _mk("pattern_engulfing", "engulfing", "Bullish/bearish engulfing reversal at the slow MA.",
        _bull_engulf, "TA-Lib CDLENGULFING"),
    _mk("pattern_hammer_star", "pin_bar", "Hammer (long lower wick) / shooting-star reversal.",
        _hammer, "TA-Lib CDLHAMMER / CDLSHOOTINGSTAR"),
    _mk("pattern_doji_breakout", "doji", "Doji indecision then break of its high/low.",
        _doji_break, "TA-Lib CDLDOJI + break"),
    _mk("pattern_three_bar_reversal", "reversal", "Three down-bars then an up-bar (and inverse).",
        _three_bar_reversal, "three-bar reversal"),
    _mk("pattern_marubozu", "continuation", "Full-body Marubozu = strong continuation.",
        _marubozu, "TA-Lib CDLMARUBOZU"),
    _mk("pattern_harami", "harami", "Inside-bar Harami reversal after an opposite candle.",
        _harami, "TA-Lib CDLHARAMI"),
]
