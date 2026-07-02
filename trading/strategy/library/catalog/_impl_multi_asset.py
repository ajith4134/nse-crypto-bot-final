"""catalog/_impl_multi_asset.py — REAL backtests for multi-asset crypto stat-arb (Wave 1C).

Data: data_sources/multi_asset (free ccxt close-price panel of liquid majors). Two real evaluators:
  • PAIRS spread (optionally cointegration-selected via statsmodels) — z-score mean reversion P&L.
  • CROSS-SECTIONAL long-short — rank the basket by trailing return, dollar/market-neutral book.
Offline-safe: empty panel → zero-metrics dict tagged with the reason (never fabricated).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([]); m["note"] = reason; return m


def _panel(days: int = 180):
    from trading.strategy.library.data_sources import multi_asset as ma
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ma.load_panel(days=days)


def _nse_panel():
    """Real NSE large-cap close panel (free yfinance) for NSE multi-asset stat-arb."""
    from trading.strategy.library.data_sources import nse_fundamentals as nf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return nf.price_panel(period="1y")


# ── PAIRS / COINTEGRATION ───────────────────────────────────────────────────────
def _best_pair(logp: pd.DataFrame, *, coint: bool):
    cols = list(logp.columns)
    best, best_score = None, (1e9 if coint else -1.0)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = logp[cols[i]], logp[cols[j]]
            if coint:
                try:
                    from statsmodels.tsa.stattools import coint as _coint
                    p = _coint(a, b)[1]
                except Exception:
                    p = 1.0
                if p < best_score:
                    best_score, best = p, (cols[i], cols[j])
            else:
                c = float(np.corrcoef(a, b)[0, 1])
                if c > best_score:
                    best_score, best = c, (cols[i], cols[j])
    return best


def _pairs_metrics(*, coint: bool, entry: float = 1.5, window: int = 20, panel=None) -> dict:
    panel = _panel() if panel is None else panel
    if panel is None or panel.shape[0] < 40 or panel.shape[1] < 2:
        return _empty("no multi-asset panel")
    logp = np.log(panel)
    pair = _best_pair(logp, coint=coint)
    if pair is None:
        return _empty("no cointegrated/correlated pair")
    a, b = logp[pair[0]], logp[pair[1]]
    beta = float(np.polyfit(b, a, 1)[0])              # OLS hedge ratio
    spread = (a - beta * b).reset_index(drop=True)
    z = (spread - spread.rolling(window).mean()) / spread.rolling(window).std()
    pos = pd.Series(0.0, index=spread.index)
    pos[z > entry] = -1.0                              # spread rich → short it (expect revert down)
    pos[z < -entry] = 1.0                              # spread cheap → long it
    pnl = pos.shift(1).fillna(0.0) * spread.diff().fillna(0.0)
    sd = spread.diff().std() or 1.0
    return ev.metrics_from_returns((pnl / sd).tolist(), periods_per_year=365)


def bt_pairs_trading(md=None) -> dict:        return _pairs_metrics(coint=False)
def bt_cointegration(md=None) -> dict:        return _pairs_metrics(coint=True)
def bt_correlation(md=None) -> dict:          return _pairs_metrics(coint=False, entry=2.0)


# ── CROSS-SECTIONAL long-short (market/dollar neutral) ──────────────────────────
def _cross_sectional(*, lookback: int = 10, direction: int = 1, panel=None) -> dict:
    """direction +1 = momentum (long winners), -1 = mean reversion (long losers)."""
    panel = _panel() if panel is None else panel
    if panel is None or panel.shape[0] < lookback + 20 or panel.shape[1] < 4:
        return _empty("no multi-asset panel")
    ret1 = panel.pct_change()
    mom = panel.pct_change(lookback)
    w = mom.sub(mom.mean(axis=1), axis=0)             # cross-sectional demean → market neutral
    w = w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)   # gross-normalized book
    port = (direction * w.shift(1) * ret1).sum(axis=1)
    return ev.metrics_from_returns(port.fillna(0.0).tolist(), periods_per_year=365)


def bt_cross_sectional_momentum(md=None) -> dict:        return _cross_sectional(direction=1)
def bt_cross_sectional_mean_reversion(md=None) -> dict:  return _cross_sectional(direction=-1, lookback=3)
def bt_relative_strength_ranking(md=None) -> dict:       return _cross_sectional(direction=1, lookback=14)
def bt_long_short_market_neutral(md=None) -> dict:       return _cross_sectional(direction=1, lookback=7)


# ── Wave 2: NSE-panel variants (free yfinance large-cap panel) ──────────────────
def bt_nse_basket(md=None) -> dict:                  return _pairs_metrics(coint=False, panel=_nse_panel())
def bt_nse_correlation_breakdown(md=None) -> dict:   return _pairs_metrics(coint=False, entry=2.0, panel=_nse_panel())
def bt_nse_leader_laggard(md=None) -> dict:          return _cross_sectional(direction=1, lookback=5, panel=_nse_panel())
def bt_nse_sector_rotation(md=None) -> dict:         return _cross_sectional(direction=1, lookback=20, panel=_nse_panel())
def bt_nse_dollar_neutral(md=None) -> dict:          return _cross_sectional(direction=1, lookback=10, panel=_nse_panel())
def bt_nse_beta_neutral(md=None) -> dict:            return _cross_sectional(direction=1, lookback=10, panel=_nse_panel())
def bt_nse_cross_sectional_momentum(md=None) -> dict: return _cross_sectional(direction=1, panel=_nse_panel())
def bt_nse_cross_sectional_mr(md=None) -> dict:      return _cross_sectional(direction=-1, lookback=3, panel=_nse_panel())
