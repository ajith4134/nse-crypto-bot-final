"""trading/options/ — Options Intelligence (Phase T4).

Pure, CPU-only, unit-testable options analytics built on the T1–T3 foundations.
Greeks use an exact analytic **Black-76** core (futures/forward options — the right
model for index/stock/MCX-commodity options on Indian exchanges), implemented on
scipy/numpy already in the venv. If `py_vollib_vectorized` (fast-vollib) is present
it can be used as an accelerated backend behind the SAME `get_all_greeks()` API; the
analytic path is always available so nothing here requires a network or a new dep.

Pieces (blueprint §T4):
  greeks   — Black-76 price + all Greeks; analytic + optional fast-vollib backend
  iv       — implied volatility solve, IV Rank, IV Percentile (52-wk rolling)
  max_pain — max-pain strike per expiry from open interest
  pcr      — Put/Call Ratio (OI + volume), per-strike and aggregate
  gex      — dealer Gamma Exposure per strike + zero-gamma (flip) level
  oi       — open-interest heatmap aggregation + OI-change tracker
  payoff   — multi-leg payoff diagram: breakevens, max profit/loss, P&L curve
  chain    — OptionsChain container tying a snapshot to all of the above + status()
"""
from __future__ import annotations

from trading.options.chain import OptionLeg, OptionQuote, OptionsChain
from trading.options.greeks import black76_price, get_all_greeks, implied_vol
from trading.options.gex import gamma_exposure, zero_gamma_level
from trading.options.iv import IVHistory, iv_percentile, iv_rank
from trading.options.max_pain import max_pain
from trading.options.oi import oi_heatmap, OITracker
from trading.options.payoff import PayoffLeg, payoff_curve, payoff_summary
from trading.options.pcr import put_call_ratio

__all__ = [
    "black76_price", "get_all_greeks", "implied_vol",
    "iv_rank", "iv_percentile", "IVHistory",
    "max_pain",
    "put_call_ratio",
    "gamma_exposure", "zero_gamma_level",
    "oi_heatmap", "OITracker",
    "payoff_curve", "payoff_summary", "PayoffLeg",
    "OptionsChain", "OptionQuote", "OptionLeg",
]
