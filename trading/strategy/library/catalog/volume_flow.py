"""catalog/volume_flow.py — volume / money-flow family (executable on OHLCV+volume).

The *bar-level* slice of order-flow: OBV trend, Chaikin A/D oscillator, MFI, volume-breakout,
relative-volume shock, VWAP-trend (institutional footprint), accumulation/distribution. True
tick/footprint order-flow (CVD, absorption, iceberg, aggressor) needs trade-level data →
catalogued data-gated in catalog/order_flow.py.
OSS: TA-Lib OBV/AD/ADOSC/MFI, VWAP execution alpha.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, long_short, stateful_band

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _obv_trend(f):
    return long_short(f["obv_slope"] > 0, f["obv_slope"] < 0, f.index)


def _adosc(f):
    return long_short(f["adosc"] > 0, f["adosc"] < 0, f.index)


def _volume_breakout(f):
    shock = f["vol_z"] > 2.0
    return long_short(shock & (f["close"] > f["close"].shift(1)),
                      shock & (f["close"] < f["close"].shift(1)), f.index)


def _rvol_shock(f):
    # relative-volume shock: current vol vs expected (rolling) — directional with the bar
    shock = f["rvol"] > 2.5
    return long_short(shock & (f["body"] > 0), shock & (f["body"] < 0), f.index)


def _vwap_trend(f):
    # institutional footprint: stay long above cumulative VWAP, short below
    return long_short(f["close"] > f["vwap"], f["close"] < f["vwap"], f.index)


def _mfi_trend(f):
    return long_short((f["mfi"] > 50) & (f["mfi"] > f["mfi"].shift(1)),
                      (f["mfi"] < 50) & (f["mfi"] < f["mfi"].shift(1)), f.index)


def _accumulation(f):
    # price flat-to-up while OBV rising sharply = accumulation → long
    return stateful_band((f["obv_slope"] > 0.5) & (f["close"] > f["ema_slow"]),
                         f["close"] < f["ema_slow"],
                         (f["obv_slope"] < -0.5) & (f["close"] < f["ema_slow"]),
                         f["close"] > f["ema_slow"], index=f.index)


def _vp_failed_auction(f):
    # Owner's champions-chart-strategy: price closed outside the value area then back inside →
    # failed auction → reversion INTO value. Long exits at VAH (target), short exits at VAL.
    return stateful_band(f["vp_failed_long"] > 0.5, f["close"] >= f["vp_vah"],
                         f["vp_failed_short"] > 0.5, f["close"] <= f["vp_val"], index=f.index)


def _vp_value_position(f):
    # Auction acceptance: hold long while price is accepted ABOVE the POC (pos>0), short below —
    # a value-migration trend-follow complementing the reversion strategy above.
    return long_short(f["vp_pos"] > 0.15, f["vp_pos"] < -0.15, f.index)


def _mk(name, family, logic, signal, oss, tf="intraday–swing", **params):
    return LibraryStrategy(name=name, category="order_flow", family=family, logic=logic,
                           segments=_SEGS, timeframe=tf, signal=signal, oss_source=oss,
                           params=params, notes="bar-level volume/flow (tick footprint is data-gated)")


STRATEGIES = [
    _mk("flow_obv_trend", "obv", "On-Balance-Volume slope sign → flow-confirmed direction.",
        _obv_trend, "Granville OBV"),
    _mk("flow_chaikin_adosc", "chaikin", "Chaikin A/D oscillator sign (accum/distrib momentum).",
        _adosc, "Chaikin A/D oscillator"),
    _mk("flow_volume_breakout", "volume_breakout",
        "Volume z-score >2 in the bar's direction = volume-backed breakout.",
        _volume_breakout, "volume breakout", tf="intraday"),
    _mk("flow_rvol_shock", "rvol",
        "Relative-volume shock (>2.5× expected) with the candle body (RVOL model).",
        _rvol_shock, "relative-volume shock model", tf="intraday"),
    _mk("flow_vwap_trend", "vwap",
        "Hold long above cumulative VWAP / short below (institutional VWAP footprint).",
        _vwap_trend, "VWAP execution alpha", tf="intraday"),
    _mk("flow_mfi_trend", "mfi", "Money-Flow-Index>50 & rising → buying pressure trend.",
        _mfi_trend, "MFI trend"),
    _mk("flow_accumulation", "accumulation",
        "Rising OBV above the slow EMA = accumulation (Wyckoff-style) long.",
        _accumulation, "accumulation/distribution"),
    _mk("flow_vp_failed_auction", "volume_profile",
        "Volume-Profile failed auction: price closes back inside the Value Area after poking "
        "out → reversion (long from below VAL / short from above VAH), target the opposite edge.",
        _vp_failed_auction, "market-profile auction theory (owner champions-chart video)",
        tf="intraday–swing", window=96),
    _mk("flow_vp_value_position", "volume_profile",
        "Value-area acceptance: hold long while price is accepted above the POC, short below "
        "(value migration trend-follow).",
        _vp_value_position, "market-profile value migration", tf="intraday–swing"),
]
