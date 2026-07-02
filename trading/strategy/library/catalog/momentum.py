"""catalog/momentum.py — Momentum family (executable on OHLCV).

Buy strength / sell weakness (acceleration, not long-horizon trend): ROC & time-series
momentum, RSI/CMO/PPO/TRIX momentum, MACD-histogram acceleration, relative-volume &
OBV-confirmed momentum, momentum ignition, breakout momentum. Cross-sectional/sector
rotation (ranking many symbols) is data-gated → see statistical_arbitrage/event_macro.
OSS: AQR time-series-momentum, freqtrade-strategies, je-suis-tm/quant-trading.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, long_short

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _roc(f):
    return long_short(f["roc"] > 0, f["roc"] < 0, f.index)


def _tsmom(f):
    return long_short(f["mom"] > 0, f["mom"] < 0, f.index)


def _rsi_mom(f):  # RSI as a momentum (regime) signal, not reversion
    return long_short(f["rsi"] > 55, f["rsi"] < 45, f.index)


def _macd_accel(f):
    rising = f["macd_hist"] > f["macd_hist"].shift(1)
    return long_short((f["macd_hist"] > 0) & rising,
                      (f["macd_hist"] < 0) & ~rising, f.index)


def _cmo(f):
    return long_short(f["cmo"] > 25, f["cmo"] < -25, f.index)


def _ppo(f):
    return long_short(f["ppo"] > 0, f["ppo"] < 0, f.index)


def _trix(f):
    return long_short(f["trix"] > 0, f["trix"] < 0, f.index)


def _rvol_mom(f):
    spike = f["rvol"] > 1.5
    return long_short(spike & (f["ret"] > 0), spike & (f["ret"] < 0), f.index)


def _obv_mom(f):
    return long_short((f["obv_slope"] > 0) & (f["ret"] > 0),
                      (f["obv_slope"] < 0) & (f["ret"] < 0), f.index)


def _breakout_mom(f):
    return long_short((f["close"] > f["hh_20"]) & (f["roc"] > 0),
                      (f["close"] < f["ll_20"]) & (f["roc"] < 0), f.index)


def _ignition(f):
    # intraday momentum ignition: large directional body on a volume spike
    big = (f["body"].abs() > 1.5 * f["atr_pct"]) & (f["rvol"] > 2.0)
    return long_short(big & (f["body"] > 0), big & (f["body"] < 0), f.index)


def _stoch_mom(f):
    return long_short((f["stoch_k"] > f["stoch_d"]) & (f["stoch_k"] > 50),
                      (f["stoch_k"] < f["stoch_d"]) & (f["stoch_k"] < 50), f.index)


def _mk(name, family, logic, signal, oss, tf="intraday–swing", **params):
    return LibraryStrategy(name=name, category="momentum", family=family, logic=logic,
                           segments=_SEGS, timeframe=tf, signal=signal, oss_source=oss,
                           params=params)


STRATEGIES = [
    _mk("mom_roc", "roc", "Rate-of-change > 0 long / < 0 short.", _roc, "ROC momentum"),
    _mk("mom_timeseries", "tsmom", "Time-series momentum: sign of N-bar return (AQR TSMOM).",
        _tsmom, "AQR time-series-momentum", n=10, tf="swing"),
    _mk("mom_rsi_regime", "rsi", "RSI>55 long / <45 short — momentum (not reversion) read.",
        _rsi_mom, "RSI momentum"),
    _mk("mom_macd_histogram", "macd", "MACD histogram positive & rising → accelerating up.",
        _macd_accel, "MACD histogram acceleration"),
    _mk("mom_cmo", "cmo", "Chande Momentum Oscillator >+25 long / <-25 short.", _cmo,
        "Chande CMO"),
    _mk("mom_ppo", "ppo", "Percentage Price Oscillator sign (scale-free MACD).", _ppo, "PPO"),
    _mk("mom_trix", "trix", "TRIX (triple-smoothed ROC) sign → momentum.", _trix, "TRIX",
        tf="swing"),
    _mk("mom_relative_volume", "volume", "Relative-volume spike (>1.5×) in trade direction.",
        _rvol_mom, "relative-volume momentum", tf="intraday"),
    _mk("mom_obv_confirmed", "volume", "OBV slope confirms price momentum direction.",
        _obv_mom, "OBV momentum"),
    _mk("mom_breakout", "breakout", "20-bar breakout WITH positive ROC = momentum breakout.",
        _breakout_mom, "breakout momentum"),
    _mk("mom_ignition", "ignition", "Large directional candle on a 2× volume spike (ignition).",
        _ignition, "intraday momentum ignition", tf="intraday"),
    _mk("mom_stochastic", "stochastic", "Stoch %K>%D and >50 → momentum long (and inverse).",
        _stoch_mom, "stochastic momentum"),
]
