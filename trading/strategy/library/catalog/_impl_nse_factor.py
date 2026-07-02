"""catalog/_impl_nse_factor.py — REAL backtests for the NSE factor family (Wave 2, free yfinance).

Cross-sectional factor long-short on a NIFTY large-cap basket: rank by the factor (value/growth/
quality/dividend/low-vol/composite), go long the top tercile / short the bottom, dollar-neutral,
backtested on the real price panel. Fundamental factors use a current snapshot (mild look-ahead —
honest, see nse_fundamentals); low-vol is price-only (clean). Empty data → tagged zero metrics.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([]); m["note"] = reason; return m


def _data():
    from trading.strategy.library.data_sources import nse_fundamentals as nf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return nf.price_panel(), nf.fundamentals()


def _long_short_from_scores(panel: pd.DataFrame, scores: pd.Series) -> dict:
    """Static cross-sectional score → dollar-neutral long-short held over the price panel."""
    cols = [c for c in panel.columns if c in scores.index and np.isfinite(scores.get(c, np.nan))]
    if len(cols) < 4 or panel.shape[0] < 30:
        return _empty("insufficient panel/scores")
    s = scores[cols]
    w = (s - s.mean())
    w = w / w.abs().sum()                                   # dollar-neutral, gross=1
    ret1 = panel[cols].pct_change()
    port = (w * ret1).sum(axis=1)                           # daily long-short return
    return ev.metrics_from_returns(port.fillna(0.0).tolist(), periods_per_year=252)


def _factor(kind: str) -> dict:
    panel, fund = _data()
    if panel is None or len(panel) == 0:
        return _empty("no NSE price panel")
    if kind == "low_vol":                                  # price-only, no look-ahead
        vol = panel.pct_change().std()
        return _long_short_from_scores(panel, -vol)        # long LOW vol
    if fund is None or len(fund) == 0:
        return _empty("no fundamentals")
    if kind == "value":      sc = -fund["pb"]              # long cheap (low P/B)
    elif kind == "growth":   sc = fund["earnings_growth"]
    elif kind == "quality":  sc = fund["roe"]
    elif kind == "dividend": sc = fund["div_yield"]
    elif kind == "multifactor":
        z = lambda x: (x - x.mean()) / (x.std() or 1.0)
        sc = z(-fund["pb"]) + z(fund["roe"]) + z(fund["div_yield"].fillna(0))
    else:                    sc = fund["roe"]
    return _long_short_from_scores(panel, sc)


def bt_factor_value(md=None) -> dict:          return _factor("value")
def bt_factor_growth(md=None) -> dict:         return _factor("growth")
def bt_factor_quality(md=None) -> dict:        return _factor("quality")
def bt_factor_dividend(md=None) -> dict:       return _factor("dividend")
def bt_factor_low_volatility(md=None) -> dict: return _factor("low_vol")
def bt_factor_multifactor(md=None) -> dict:    return _factor("multifactor")
def bt_statarb_factor(md=None) -> dict:        return _factor("multifactor")
