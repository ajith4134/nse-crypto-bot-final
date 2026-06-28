"""trading/strategy/fitness.py — journal/backtest-driven multi-objective fitness (T8.2).

Fitness is measured OUT-OF-SAMPLE only (via the T8.1 walk-forward folds) and is
MULTI-OBJECTIVE so the evolution never optimises one number into overfit oblivion.
Objectives are returned both scalarised (for ranking/printing) and as a raw tuple
(for DEAP NSGA-II in T8.3). When real journal trades exist for a strategy, their
realised net P&L is blended in so the score reflects live behaviour, not just backtest.

Reuse-first: backtest = vectorbt (T8.1 `backtest_signal`); per-trade analytics reuse the
same expectancy/profit-factor definitions as `trading.journal.analytics`. No new deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trading.strategy.backtest import _profit_factor, backtest_signal, walk_forward_folds
from trading.strategy.features import compute_features
from trading.strategy.genome import Strategy


@dataclass
class Fitness:
    score: float                       # scalarised fitness (higher = better)
    objectives: tuple                  # (expectancy, sharpe, -|maxDD|, -trade_penalty) maximise-form
    components: dict                   # weighted contributions (for transparency)
    oos_metrics: dict                  # pooled out-of-sample metrics
    realized: dict | None = None       # journal-based metrics if available

    def as_dict(self) -> dict:
        return {"score": self.score, "objectives": list(self.objectives),
                "components": self.components, "oos_metrics": self.oos_metrics,
                "realized": self.realized}


def evaluate_oos(strategy: Strategy, ohlcv: pd.DataFrame, *, features: pd.DataFrame | None = None,
                 n_folds: int = 4, scheme: str = "rolling", **bt_kw) -> dict:
    """Backtest a strategy on each walk-forward TEST block; pool the results (OOS only).

    Indicators are computed on the full causal history; only the test-block slice of the
    signal is scored, so there is no in-sample leakage into the OOS metrics.
    """
    feats = features if features is not None else compute_features(ohlcv)
    sig = strategy.signal(feats)
    folds = walk_forward_folds(len(feats), n_folds=n_folds, scheme=scheme)

    ppy = bt_kw.get("periods_per_year", 252)
    pooled_trades: list[float] = []
    pooled_bar_returns: list[float] = []          # per-bar OOS returns across all folds
    fold_returns: list[float] = []
    worst_dd = 0.0
    for f in folds:
        s, e = f["test"]
        sl_sig = sig.iloc[s:e].reset_index(drop=True)
        sl_px = feats.iloc[s:e].reset_index(drop=True)
        res = backtest_signal(sl_sig, sl_px, **bt_kw)
        pooled_trades += [t["ret"] for t in res.trades]
        eq = res.equity_curve
        pooled_bar_returns += [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq))
                               if eq[i - 1]]
        fold_returns.append(res.metrics["total_return"])
        worst_dd = min(worst_dd, res.metrics["max_drawdown"])

    rets = np.array(pooled_trades, dtype=float)
    n = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    oos_total = float(np.prod([1.0 + r for r in fold_returns]) - 1.0) if fold_returns else 0.0
    # pooled OOS Sharpe from the concatenated per-bar returns (Sharpe is a ratio — averaging
    # per-fold Sharpes is statistically invalid; pool the returns and compute once).
    bar = np.array(pooled_bar_returns, dtype=float)
    bstd = float(np.std(bar, ddof=1)) if len(bar) > 1 else 0.0
    oos_sharpe = float(np.mean(bar) / bstd * np.sqrt(ppy)) if bstd > 0 else 0.0
    return {
        "oos_total_return": oos_total,
        "oos_sharpe": oos_sharpe,
        "oos_sharpe_mean": oos_sharpe,            # kept key for back-compat (now pooled)
        "n_trades": n,
        "expectancy": float(rets.mean()) if n else 0.0,
        "win_rate": float(len(wins) / n * 100.0) if n else 0.0,
        "profit_factor": _profit_factor(gross_win, gross_loss),
        "max_drawdown": worst_dd,
        "trade_returns": pooled_trades,
        "fold_returns": fold_returns,             # per-fold OOS total return (for PBO/CSCV)
        "n_folds": len(folds),
    }


def multi_objective(oos: dict, *, weights: dict | None = None,
                    target_trades: int = 30) -> tuple[float, tuple, dict]:
    """Turn OOS metrics into (scalar score, NSGA-II objective tuple, components).

    Objectives (all maximise-form): expectancy, OOS Sharpe, -|max drawdown|,
    -trade-count penalty (penalise both over-trading churn and too-few-trades noise).
    """
    w = {"expectancy": 1.0, "sharpe": 0.5, "drawdown": 0.5, "trades": 0.2}
    if weights:
        w.update(weights)
    expectancy = oos.get("expectancy", 0.0)
    sharpe = oos.get("oos_sharpe_mean", 0.0)
    dd = -abs(oos.get("max_drawdown", 0.0))
    n = oos.get("n_trades", 0)
    # penalty: 0 at target_trades, rising as it deviates (and hard 0 if no trades)
    trade_pen = -abs(np.log((n + 1) / (target_trades + 1)))
    pf = oos.get("profit_factor", 0.0)
    pf = 0.0 if not np.isfinite(pf) else pf

    objectives = (float(expectancy), float(sharpe), float(dd), float(trade_pen))
    components = {
        "expectancy": w["expectancy"] * expectancy * 100.0,   # scale to comparable magnitude
        "sharpe": w["sharpe"] * sharpe,
        "drawdown": w["drawdown"] * dd,
        "trades": w["trades"] * trade_pen,
    }
    # strategies with no trades are worthless regardless of other terms
    score = float(sum(components.values())) if n > 0 else -1e9
    return score, objectives, components


def journal_realized(realized_trade_returns: list[float] | None) -> dict | None:
    """Summarise realised journal trade returns (the sim-to-real anchor), if any."""
    if not realized_trade_returns:
        return None
    r = np.array(realized_trade_returns, dtype=float)
    wins = r[r > 0]
    losses = r[r < 0]
    gl = float(-losses.sum())
    return {
        "n": int(len(r)), "expectancy": float(r.mean()),
        "win_rate": float(len(wins) / len(r) * 100.0),
        "profit_factor": float(wins.sum() / gl) if gl > 0 else float("inf"),
    }


def fitness(strategy: Strategy, ohlcv: pd.DataFrame, *, features: pd.DataFrame | None = None,
            n_folds: int = 4, scheme: str = "rolling", weights: dict | None = None,
            realized_trade_returns: list[float] | None = None,
            realized_weight: float = 0.5, **bt_kw) -> Fitness:
    """Full multi-objective fitness for one strategy (OOS backtest + optional journal blend)."""
    oos = evaluate_oos(strategy, ohlcv, features=features, n_folds=n_folds,
                       scheme=scheme, **bt_kw)
    score, objectives, components = multi_objective(oos, weights=weights)
    realized = journal_realized(realized_trade_returns)
    if realized is not None:
        # blend realised expectancy into the score (live behaviour dominates as it accrues)
        blended = (1 - realized_weight) * score + realized_weight * (realized["expectancy"] * 100.0)
        score = float(blended)
        components["realized_expectancy"] = realized_weight * realized["expectancy"] * 100.0
    return Fitness(score=score, objectives=objectives, components=components,
                   oos_metrics={k: v for k, v in oos.items() if k != "trade_returns"},
                   realized=realized)
