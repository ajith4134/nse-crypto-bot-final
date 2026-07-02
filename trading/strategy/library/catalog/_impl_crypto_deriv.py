"""catalog/_impl_crypto_deriv.py — REAL backtest functions for crypto-derivatives strategies.

Each `bt_*` downloads its own data via data_sources/crypto_deriv (cached) and returns a metrics
dict (same shape as backtest_signal) using the carry/basis/directional evaluators. Self-
contained: the runner just calls them. Offline-safe: a fetch failure returns a zero-metrics
dict tagged with the reason (honest — no fabricated numbers).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev

_SYMBOL = "BTC/USDT"
_EXCHANGE = "binance"
_DAYS = 60


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([])
    m["note"] = reason
    return m


def _load(want_oi=False):
    from trading.strategy.library.data_sources import crypto_deriv
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return crypto_deriv.load_market(_SYMBOL, exchange=_EXCHANGE, timeframe="1h",
                                        days=_DAYS, want_oi=want_oi)


def bt_funding_arb(md=None) -> dict:
    """Delta-neutral long-spot/short-perp funding harvest on real funding-rate history."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.funding is None or len(md.funding) == 0:
        return _empty("no funding history available")
    return ev.carry_metrics(md.funding, fee_bps=1.0, threshold=0.0)


def bt_funding_momentum(md=None) -> dict:
    """Trade the perp in the direction of the funding-rate trend (real funding + perp bars)."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.funding is None or md.perp_ohlcv is None or len(md.funding) == 0:
        return _empty("no funding/perp data")
    f = md.funding.copy()
    sig = np.sign(f.diff().fillna(0.0))                  # funding rising → long, falling → short
    perp = md.perp_ohlcv.set_index("time")["close"]
    aligned = pd.DataFrame({"close": perp}).join(pd.DataFrame({"sig": sig}), how="left")
    aligned["sig"] = aligned["sig"].ffill().fillna(0.0)
    return ev.signal_returns_metrics(aligned["close"], aligned["sig"], periods_per_year=8760)


def bt_basis_arb(md=None) -> dict:
    """Cash-and-carry: short rich perp/long cheap spot, capture basis convergence (real basis)."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.basis is None or len(md.basis) < 3:
        return _empty("no spot/perp basis available")
    return ev.basis_convergence_metrics(md.basis, entry=0.0005, fee_bps=1.0)


def bt_cash_carry(md=None) -> dict:
    """Cash-and-carry basis lock — same convergence engine, wider entry band."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.basis is None or len(md.basis) < 3:
        return _empty("no spot/perp basis available")
    return ev.basis_convergence_metrics(md.basis, entry=0.001, fee_bps=1.0)


def bt_basis_trading(md=None) -> dict:
    """Basis trading: fade rich/cheap spot-vs-perp basis back to fair (real ccxt basis)."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.basis is None or len(md.basis) < 3:
        return _empty("no spot/perp basis available")
    return ev.basis_convergence_metrics(md.basis, entry=0.0008, fee_bps=1.0)


def bt_calendar_spread(md=None) -> dict:
    """Calendar/term-structure spread — perp-vs-spot basis term structure as the tradable spread
    (real basis; proxy for near-vs-far when dated futures aren't loaded). Convergence engine."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.basis is None or len(md.basis) < 3:
        return _empty("no basis term-structure available")
    return ev.basis_convergence_metrics(md.basis, entry=0.0012, fee_bps=1.0)


def bt_roll_yield_harvesting(md=None) -> dict:
    """Roll-yield harvest: collect the funding/basis carry over time (real funding-rate history)."""
    try:
        md = md or _load()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.funding is None or len(md.funding) == 0:
        return _empty("no funding/roll history available")
    return ev.carry_metrics(md.funding, fee_bps=1.0, threshold=0.0)


def bt_oi_breakout(md=None) -> dict:
    """Long when perp breaks its 20-bar high WITH rising open interest (real OI + perp bars)."""
    try:
        md = md or _load(want_oi=True)
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if md.open_interest is None or md.perp_ohlcv is None or len(md.open_interest) == 0:
        return _empty("no open-interest history (exchange unsupported)")
    perp = md.perp_ohlcv.set_index("time")
    oi = md.open_interest.reindex(perp.index).ffill()
    hh = perp["high"].rolling(20).max().shift(1)
    ll = perp["low"].rolling(20).min().shift(1)
    oi_rising = oi.diff().fillna(0.0) > 0
    sig = pd.Series(0, index=perp.index)
    sig[(perp["close"] > hh) & oi_rising] = 1
    sig[(perp["close"] < ll) & oi_rising] = -1
    return ev.signal_returns_metrics(perp["close"], sig, periods_per_year=8760)
