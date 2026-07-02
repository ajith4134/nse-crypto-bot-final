"""catalog/mean_reversion.py — Mean-Reversion family (executable on OHLCV).

Bet price returns to an equilibrium: RSI/Stoch/Williams/CCI oversold-overbought, Bollinger
& Keltner band fades, z-score & VWAP reversion, Connors RSI-2, MFI. Most are STATEFUL
(enter at the extreme, hold until reversion to the mean) — modelled with `stateful_band`.
OSS: freqtrade-strategies (BB/RSI), Connors RSI-2, je-suis-tm/quant-trading.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.library.base import LibraryStrategy, stateful_band

_SEGS = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
         "crypto_spot", "crypto_futures")


def _rsi_rev(f):
    return stateful_band(f["rsi"] < 30, f["rsi"] > 50, f["rsi"] > 70, f["rsi"] < 50,
                         index=f.index)


def _rsi2_connors(f):
    # Connors RSI-2: long-only, trade dips inside an up-trend (close>200SMA)
    up = f["close"] > f["sma_200"]
    return stateful_band((f["rsi_fast"] < 10) & up, f["close"] > f["sma_fast"],
                         index=f.index)


def _bb_rev(f):
    return stateful_band(f["close"] < f["bb_lower"], f["close"] >= f["bb_mid"],
                         f["close"] > f["bb_upper"], f["close"] <= f["bb_mid"],
                         index=f.index)


def _pctb_rev(f):
    return stateful_band(f["bb_pctb"] < 0.0, f["bb_pctb"] > 0.5,
                         f["bb_pctb"] > 1.0, f["bb_pctb"] < 0.5, index=f.index)


def _zscore_rev(f):
    return stateful_band(f["zscore"] < -2.0, f["zscore"] > 0.0,
                         f["zscore"] > 2.0, f["zscore"] < 0.0, index=f.index)


def _vwap_rev(f):
    return stateful_band(f["vwap_dist"] < -0.01, f["vwap_dist"] >= 0.0,
                         f["vwap_dist"] > 0.01, f["vwap_dist"] <= 0.0, index=f.index)


def _stoch_rev(f):
    return stateful_band(f["stoch_k"] < 20, f["stoch_k"] > 50,
                         f["stoch_k"] > 80, f["stoch_k"] < 50, index=f.index)


def _stochrsi_rev(f):
    return stateful_band(f["stochrsi"] < 20, f["stochrsi"] > 50,
                         f["stochrsi"] > 80, f["stochrsi"] < 50, index=f.index)


def _willr_rev(f):
    return stateful_band(f["willr"] < -80, f["willr"] > -50,
                         f["willr"] > -20, f["willr"] < -50, index=f.index)


def _cci_rev(f):
    return stateful_band(f["cci"] < -100, f["cci"] > 0,
                         f["cci"] > 100, f["cci"] < 0, index=f.index)


def _mfi_rev(f):
    return stateful_band(f["mfi"] < 20, f["mfi"] > 50,
                         f["mfi"] > 80, f["mfi"] < 50, index=f.index)


def _keltner_rev(f):
    return stateful_band(f["close"] < f["kc_lower"], f["close"] >= f["kc_mid"],
                         f["close"] > f["kc_upper"], f["close"] <= f["kc_mid"],
                         index=f.index)


def _atr_overext(f):
    # fade moves > 2.5 ATR% away from the slow mean
    far = 2.5 * f["atr_pct"]
    return stateful_band(f["dist_sma_slow"] < -far, f["dist_sma_slow"] > 0,
                         f["dist_sma_slow"] > far, f["dist_sma_slow"] < 0, index=f.index)


def _ultosc_rev(f):
    return stateful_band(f["ultosc"] < 30, f["ultosc"] > 50,
                         f["ultosc"] > 70, f["ultosc"] < 50, index=f.index)


def _mk(name, family, logic, signal, oss, tf="intraday–swing", **params):
    return LibraryStrategy(name=name, category="mean_reversion", family=family, logic=logic,
                           segments=_SEGS, timeframe=tf, signal=signal, oss_source=oss,
                           params=params)


STRATEGIES = [
    _mk("meanrev_rsi", "rsi", "RSI<30 long until RSI>50; RSI>70 short until RSI<50.",
        _rsi_rev, "freqtrade-strategies (RSI)", lo=30, hi=70),
    _mk("meanrev_connors_rsi2", "rsi", "Connors RSI-2: buy 2-period RSI<10 dips above 200-SMA.",
        _rsi2_connors, "Larry Connors RSI-2", n=2, filt=200),
    _mk("meanrev_bollinger", "bollinger", "Buy lower band, exit mid; sell upper band, exit mid.",
        _bb_rev, "freqtrade-strategies (Bollinger)", n=20, k=2.0),
    _mk("meanrev_bb_pctb", "bollinger", "Bollinger %B<0 long / %B>1 short, exit at %B=0.5.",
        _pctb_rev, "%B reversion", n=20),
    _mk("meanrev_zscore", "zscore", "Price z-score<-2 long / >+2 short, exit at z=0.",
        _zscore_rev, "z-score reversion", n=30),
    _mk("meanrev_vwap", "vwap", "Fade >1% deviation from rolling VWAP back to VWAP.",
        _vwap_rev, "VWAP reversion (institutional footprint)", tf="intraday"),
    _mk("meanrev_stochastic", "stochastic", "Stochastic %K<20 long / >80 short, exit at 50.",
        _stoch_rev, "Lane Stochastic", k=14),
    _mk("meanrev_stochrsi", "stochastic", "StochRSI<20 long / >80 short, exit at 50.",
        _stochrsi_rev, "StochRSI", n=14),
    _mk("meanrev_williams_r", "williams", "Williams %R<-80 long / >-20 short, exit -50.",
        _willr_rev, "Williams %R", n=14),
    _mk("meanrev_cci", "cci", "CCI<-100 long / >+100 short, exit at 0.",
        _cci_rev, "Lambert CCI", n=20),
    _mk("meanrev_mfi", "mfi", "Money-Flow-Index<20 long / >80 short (volume-weighted RSI).",
        _mfi_rev, "MFI", n=14),
    _mk("meanrev_keltner", "keltner", "Fade Keltner-channel touches back to the EMA mid.",
        _keltner_rev, "Keltner channel", n=20),
    _mk("meanrev_atr_overextension", "atr", "Fade moves >2.5 ATR% from the slow mean.",
        _atr_overext, "ATR reversion", k=2.5),
    _mk("meanrev_ultimate_osc", "oscillator", "Ultimate Oscillator<30 long / >70 short.",
        _ultosc_rev, "Williams Ultimate Oscillator"),
]
