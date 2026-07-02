"""catalog/volatility.py — realized-volatility regime family (executable on OHLCV).

True volatility TRADING (long/short *implied* vol, variance swaps, vol carry) needs options
IV → catalogued data-gated in catalog/options.py. What IS expressible on bars is
*realized-volatility regime* logic: only take trend breakouts when volatility is expanding,
only mean-revert when volatility is low/compressed, and Bollinger-width expansion. These are
the OHLCV-side of the volatility playbook (regime gating that pro desks layer under every
directional book).
OSS: TTM squeeze, Bollinger-width, NATR regime gating.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, long_short, stateful_band

_SEGS = ("nse_intraday", "nse_futures", "mcx_commodities", "crypto_spot", "crypto_futures")


def _vol_expansion_trend(f):
    rising_vol = f["natr"] > f["natr"].rolling(20).mean()
    return long_short(rising_vol & (f["close"] > f["donchian_hi"]),
                      rising_vol & (f["close"] < f["donchian_lo"]), f.index)


def _lowvol_meanrev(f):
    low_vol = f["natr"] < f["natr"].rolling(50).quantile(0.4)
    return stateful_band(low_vol & (f["zscore"] < -1.5), f["zscore"] > 0,
                         low_vol & (f["zscore"] > 1.5), f["zscore"] < 0, index=f.index)


def _bb_width_expansion(f):
    expanding = f["bb_width"] > 1.5 * f["bb_width"].rolling(30).mean()
    return long_short(expanding & (f["close"] > f["bb_mid"]),
                      expanding & (f["close"] < f["bb_mid"]), f.index)


def _vol_compression_anticipation(f):
    # buy compression breakout (vol cycles: low vol precedes expansion)
    compressed = f["bb_width"] < f["bb_width"].rolling(50).quantile(0.2)
    fire_up = compressed.shift(1).fillna(False) & (f["close"] > f["donchian_hi"])
    fire_dn = compressed.shift(1).fillna(False) & (f["close"] < f["donchian_lo"])
    return stateful_band(fire_up, f["close"] < f["ema_fast"],
                         fire_dn, f["close"] > f["ema_fast"], index=f.index)


def _mk(name, family, logic, signal, oss, tf="intraday–swing", **params):
    return LibraryStrategy(name=name, category="volatility", family=family, logic=logic,
                           segments=_SEGS, timeframe=tf, signal=signal, oss_source=oss,
                           params=params, notes="realized-vol regime (OHLCV side of vol trading)")


STRATEGIES = [
    _mk("vol_expansion_trend", "regime",
        "Take Donchian breakouts only when NATR is expanding (vol-confirmed trend).",
        _vol_expansion_trend, "NATR regime gating"),
    _mk("vol_lowvol_meanrevert", "regime",
        "Mean-revert z-score extremes only in low-volatility regimes.",
        _lowvol_meanrev, "low-vol mean-reversion gate"),
    _mk("vol_bb_width_expansion", "expansion",
        "Bollinger width >1.5× its 30-bar avg = volatility expansion; trade with the mid.",
        _bb_width_expansion, "Bollinger-width expansion"),
    _mk("vol_compression_breakout", "compression",
        "Buy the breakout after a volatility compression (bottom-quintile BB width).",
        _vol_compression_anticipation, "volatility-cycle compression→expansion"),
]
