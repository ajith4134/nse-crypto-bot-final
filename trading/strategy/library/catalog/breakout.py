"""catalog/breakout.py — Breakout / volatility-expansion family (executable on OHLCV).

Trade the release of compressed ranges and channel breaks: Bollinger squeeze, TTM squeeze
(BB inside Keltner), ATR-channel breakout, Larry-Williams volatility breakout, range-
expansion, inside-bar/NR7 break, gap-and-go. Session-anchored breakouts (Opening-Range,
CPR/pivot) need an intraday-session / prior-day frame → catalogued data-gated (MULTI_TF).
OSS: je-suis-tm/quant-trading (ORB), TTM squeeze, Larry Williams volatility breakout.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import DataReq, LibraryStrategy, long_short, stateful_band

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _bb_squeeze(f):
    squeeze = f["bb_width"] < f["bb_width"].rolling(50).quantile(0.25)
    fired_up = squeeze.shift(1).fillna(False) & (f["close"] > f["bb_upper"])
    fired_dn = squeeze.shift(1).fillna(False) & (f["close"] < f["bb_lower"])
    return stateful_band(fired_up, f["close"] < f["bb_mid"],
                         fired_dn, f["close"] > f["bb_mid"], index=f.index)


def _ttm_squeeze(f):
    # TTM squeeze: BB inside Keltner = compression; fire on release in momentum direction
    inside = (f["bb_upper"] < f["kc_upper"]) & (f["bb_lower"] > f["kc_lower"])
    rel = inside.shift(1).fillna(False) & ~inside
    return stateful_band(rel & (f["macd_hist"] > 0), f["macd_hist"] < 0,
                         rel & (f["macd_hist"] < 0), f["macd_hist"] > 0, index=f.index)


def _atr_channel(f):
    up = f["close"] > (f["close"].shift(1) + 1.5 * f["atr"])
    dn = f["close"] < (f["close"].shift(1) - 1.5 * f["atr"])
    return stateful_band(up, f["close"] < f["ema_fast"],
                         dn, f["close"] > f["ema_fast"], index=f.index)


def _lw_volatility(f):
    # Larry Williams: break of open ± k×(prior bar range)
    prior_range = (f["high"].shift(1) - f["low"].shift(1))
    up = f["high"] > (f["open"] + 0.5 * prior_range)
    dn = f["low"] < (f["open"] - 0.5 * prior_range)
    return stateful_band(up, f["close"] < f["open"], dn, f["close"] > f["open"],
                         index=f.index)


def _range_expansion(f):
    wide = f["range_pct"] > 1.8 * f["range_pct"].rolling(20).mean()
    return long_short(wide & (f["body"] > 0), wide & (f["body"] < 0), f.index)


def _inside_bar(f):
    inside = (f["high"] < f["high"].shift(1)) & (f["low"] > f["low"].shift(1))
    brk_up = inside.shift(1).fillna(False) & (f["close"] > f["high"].shift(1))
    brk_dn = inside.shift(1).fillna(False) & (f["close"] < f["low"].shift(1))
    return stateful_band(brk_up, f["close"] < f["ema_fast"],
                         brk_dn, f["close"] > f["ema_fast"], index=f.index)


def _gap_and_go(f):
    up = (f["gap"] > 0.01) & (f["close"] > f["open"])
    dn = (f["gap"] < -0.01) & (f["close"] < f["open"])
    return long_short(up, dn, f.index)


def _donchian_stop(f):
    # breakout entry with mid-channel trailing exit (vs the always-in trend version)
    return stateful_band(f["close"] > f["donchian_hi"], f["close"] < f["donchian_mid"],
                         f["close"] < f["donchian_lo"], f["close"] > f["donchian_mid"],
                         index=f.index)


def _mk(name, family, logic, signal, oss, tf="intraday–swing", **params):
    return LibraryStrategy(name=name, category="trend_following", family=family, logic=logic,
                           segments=_SEGS, timeframe=tf, signal=signal, oss_source=oss,
                           params=params, notes="breakout / volatility-expansion")


STRATEGIES = [
    _mk("breakout_bollinger_squeeze", "squeeze",
        "Low Bollinger width (bottom quartile) then band break = squeeze release.",
        _bb_squeeze, "Bollinger squeeze", tf="intraday"),
    _mk("breakout_ttm_squeeze", "squeeze",
        "TTM squeeze: BB inside Keltner compresses; fire on release per MACD-hist sign.",
        _ttm_squeeze, "John Carter TTM Squeeze"),
    _mk("breakout_atr_channel", "atr_channel",
        "Close breaks ±1.5 ATR from prior close; exit on EMA cross.",
        _atr_channel, "ATR channel breakout"),
    _mk("breakout_lw_volatility", "volatility_breakout",
        "Larry-Williams: break open ±0.5× prior-bar range (intraday volatility breakout).",
        _lw_volatility, "Larry Williams volatility breakout", tf="intraday"),
    _mk("breakout_range_expansion", "range_expansion",
        "Range >1.8× its 20-bar avg in trade direction (expansion bar).",
        _range_expansion, "range-expansion", tf="intraday"),
    _mk("breakout_inside_bar", "inside_bar",
        "Inside-bar compression then break of the mother-bar high/low.",
        _inside_bar, "inside-bar / NR7 breakout"),
    _mk("breakout_gap_and_go", "gap",
        "Gap >1% that holds direction into the bar close (Gap-and-Go).",
        _gap_and_go, "Gap-and-Go", tf="intraday"),
    _mk("breakout_donchian_trailing", "donchian",
        "Donchian high/low entry with mid-channel trailing exit.",
        _donchian_stop, "Donchian breakout w/ trailing"),
    # ── session-anchored breakouts: need intraday-session / prior-day frame ──
    LibraryStrategy(
        name="breakout_opening_range", category="trend_following", family="orb",
        logic="Opening-Range Breakout: break of the first N-min session range.",
        segments=("nse_intraday", "crypto_spot", "crypto_futures", "mcx_commodities"),
        timeframe="intraday", data_req=(DataReq.OHLCV, DataReq.VOLUME, DataReq.MULTI_TF),
        signal=None, oss_source="je-suis-tm/quant-trading (ORB)",
        notes="needs intraday session-open anchoring (first 15–30m range)"),
    LibraryStrategy(
        name="breakout_cpr_pivot", category="trend_following", family="pivot",
        logic="Central-Pivot-Range / floor-pivot breakout (prior-day OHLC pivots).",
        segments=("nse_intraday", "nse_futures", "mcx_commodities"),
        timeframe="intraday", data_req=(DataReq.OHLCV, DataReq.MULTI_TF),
        signal=None, oss_source="CPR/pivot (Frank Ochoa)",
        notes="needs prior-day OHLC to compute pivots"),
]


# ── Wave 2: real OHLCV signals for the session-anchored breakouts (no new data) ──
def _opening_range_sig(f):
    """Opening-Range Breakout: break of the recent 20-bar session range (Donchian proxy)."""
    hi, lo = f["hh_20"].shift(1), f["ll_20"].shift(1)
    return long_short(f["close"] > hi, f["close"] < lo, f.index)


def _cpr_pivot_sig(f):
    """Central-Pivot-Range breakout: long above the rolling floor pivot, short below."""
    piv = ((f["high"] + f["low"] + f["close"]) / 3.0).rolling(15).mean().shift(1)
    return long_short(f["close"] > piv, f["close"] < piv, f.index)


for _s in STRATEGIES:
    if _s.name == "breakout_opening_range":
        _s.signal = _opening_range_sig; _s.notes = "REAL: 20-bar range breakout"
    elif _s.name == "breakout_cpr_pivot":
        _s.signal = _cpr_pivot_sig; _s.notes = "REAL: floor-pivot breakout"
