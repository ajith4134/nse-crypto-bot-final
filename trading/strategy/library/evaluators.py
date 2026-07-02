"""trading/strategy/library/evaluators.py — backtest evaluators for data-backed strategies.

The OHLCV signal strategies score via `backtest_signal` (directional +1/-1/0). Data-backed
strategies have different P&L shapes — carry (funding accrual), basis convergence, spread/pairs
— so each gets an evaluator that returns the SAME metrics dict shape as `backtest_signal`
(sharpe/total_return/max_drawdown/n_trades/win_rate/profit_factor/expectancy), so they rank on
one honest leaderboard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def metrics_from_returns(rets: pd.Series | np.ndarray, *, periods_per_year: int = 365,
                         n_trades: int | None = None) -> dict:
    """Standard metrics from a per-period net-return series (the common reducer)."""
    r = np.asarray(pd.Series(rets).fillna(0.0), dtype=float)
    if len(r) == 0:
        return {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "n_trades": 0,
                "win_rate": 0.0, "profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "expectancy": 0.0}
    equity = np.cumprod(1.0 + r)
    std = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    sharpe = float(np.mean(r) / std * np.sqrt(periods_per_year)) if std > 0 else 0.0
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min()) if len(equity) else 0.0
    wins = r[r > 0]; losses = r[r < 0]
    gw = float(wins.sum()); gl = float(-losses.sum())
    pf = (min(gw / gl, 1e6) if gl > 0 else (1e6 if gw > 0 else 0.0))
    return {
        "total_return": float(equity[-1] - 1.0),
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "n_trades": int(n_trades if n_trades is not None else int((np.diff(np.sign(r)) != 0).sum() + 1)),
        "win_rate": float(len(wins) / len(r) * 100.0),
        "profit_factor": pf,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "expectancy": float(np.mean(r)),
    }


def carry_metrics(funding: pd.Series, *, fee_bps: float = 2.0, threshold: float = 0.0,
                  intervals_per_year: int = 1095) -> dict:
    """Funding-rate-arbitrage P&L: delta-neutral long-spot/short-perp collects funding.

    Per interval, a short-perp leg RECEIVES funding when the rate is positive. We enter only
    when |funding| exceeds `threshold` and take the sign that collects (short perp on +funding,
    long perp on −funding). Net per-interval return ≈ |funding| − rebalance fee; delta-neutral
    so price direction nets out. Binance perps fund 3×/day ⇒ ~1095 intervals/yr.
    """
    f = pd.Series(funding).dropna().astype(float)
    if f.empty:
        return metrics_from_returns([], periods_per_year=intervals_per_year)
    fee = (fee_bps / 1e4)
    # Classic positive-funding harvest: hold long-spot/short-perp (collects +funding) while
    # funding > threshold, else flat. Delta-neutral so price nets out; fee only on entry/exit.
    pos = (f > threshold).astype(int)
    rebalance = pos.diff().abs().fillna(pos)
    rets = f.clip(lower=0.0) * pos - rebalance * fee
    n_trades = int((rebalance > 0).sum())
    return metrics_from_returns(rets, periods_per_year=intervals_per_year, n_trades=n_trades)


def basis_convergence_metrics(basis: pd.Series, *, entry: float = 0.005, fee_bps: float = 2.0,
                              intervals_per_year: int = 8760) -> dict:
    """Cash-and-carry / basis arb: short perp when basis (perp>spot) is rich, capture convergence.

    Enter when |basis| > entry; P&L per interval = -Δbasis in the convergence direction
    (short rich basis profits as it shrinks). Hourly bars ⇒ 8760 intervals/yr.
    """
    b = pd.Series(basis).dropna().astype(float)
    if len(b) < 3:
        return metrics_from_returns([], periods_per_year=intervals_per_year)
    active = (b.abs() > entry)
    pos = -np.sign(b) * active.astype(int)            # short rich / long cheap basis
    dbasis = b.diff().fillna(0.0)
    fee = fee_bps / 1e4
    rebalance = pos.diff().abs().fillna(pos.abs())
    rets = pos.shift(1).fillna(0.0) * dbasis - rebalance * fee
    return metrics_from_returns(rets, periods_per_year=intervals_per_year,
                                n_trades=int((rebalance > 0).sum()))


def signal_returns_metrics(close: pd.Series, signal: pd.Series, *, fee_bps: float = 2.0,
                           periods_per_year: int = 8760) -> dict:
    """Directional P&L from a +1/-1/0 signal over a close series (next-bar execution)."""
    c = pd.Series(close).astype(float).reset_index(drop=True)
    s = pd.Series(signal).astype(float).reset_index(drop=True).reindex(range(len(c))).fillna(0.0)
    bar_ret = c.pct_change().fillna(0.0)
    target = s.shift(1).fillna(0.0)
    fee = fee_bps / 1e4
    rets = target * bar_ret - target.diff().abs().fillna(target.abs()) * fee
    return metrics_from_returns(rets, periods_per_year=periods_per_year,
                                n_trades=int((target.diff().abs() > 0).sum()))
