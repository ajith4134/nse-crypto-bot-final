"""trading/journal/analytics.py — aggregate journal analytics (T5 §T5.5/6, blueprint §6).

Rolls a list of `ClosedTrade`s up into a single `JournalAnalytics` dataclass: headline
totals (win rate, profit factor, expectancy), win/loss streaks, win-rate/P&L broken
down by every classification dimension, an R-multiple histogram, and the raw MAE/MFE
scatter points the dashboard plots. `journal.py` calls `analyze_trades(trades)` and then
`.as_dict()` for a JSON-able payload.

Win/loss convention: a trade with net_pnl > 0 is a win, < 0 a loss, == 0 breakeven.
Breakeven trades count in the totals but not in win/loss streaks or win-rate numerator.

Everything is pure Python, deterministic and offline; the empty-trade-list case returns
all zeros / None with no division errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf


def _net(t) -> float:
    return float(getattr(t, "net_pnl", 0.0) or 0.0)


# R-multiple histogram buckets: (low_exclusive, high_inclusive, label)
_R_BUCKETS = [
    (-inf, -2.0, "(-inf,-2]"),
    (-2.0, -1.0, "(-2,-1]"),
    (-1.0, 0.0, "(-1,0]"),
    (0.0, 1.0, "(0,1]"),
    (1.0, 2.0, "(1,2]"),
    (2.0, inf, "(2,inf)"),
]

_DIMENSIONS = (
    "instrument_type",
    "strategy_name",
    "market_regime_entry",
    "day_of_week",
    "entry_hour",
)


@dataclass
class JournalAnalytics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0                       # %

    gross_profit: float = 0.0
    gross_loss: float = 0.0                     # positive number
    net_pnl: float = 0.0
    profit_factor: float | None = None

    avg_win: float = 0.0
    avg_loss: float = 0.0                       # positive number
    avg_trade: float = 0.0
    expectancy: float = 0.0                     # currency per trade

    max_win_streak: int = 0
    max_loss_streak: int = 0
    current_streak: int = 0                     # signed: + wins, − losses

    by_dimension: dict = field(default_factory=dict)
    r_multiple_distribution: dict = field(default_factory=dict)
    mae_mfe_scatter: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "breakeven": self.breakeven,
            "win_rate": self.win_rate,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "net_pnl": self.net_pnl,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_trade": self.avg_trade,
            "expectancy": self.expectancy,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
            "current_streak": self.current_streak,
            "by_dimension": self.by_dimension,
            "r_multiple_distribution": self.r_multiple_distribution,
            "mae_mfe_scatter": self.mae_mfe_scatter,
        }


def _bucket_r(r: float) -> str:
    for lo, hi, label in _R_BUCKETS:
        if lo < r <= hi:
            return label
    # r == -inf edge (won't happen with finite floats) — fall into first bucket
    return _R_BUCKETS[0][2]


def analyze_trades(trades) -> JournalAnalytics:
    """Aggregate a list of ClosedTrade into a JournalAnalytics. Empty-safe."""
    a = JournalAnalytics()
    a.r_multiple_distribution = {label: 0 for _, _, label in _R_BUCKETS}
    a.by_dimension = {dim: {} for dim in _DIMENSIONS}

    trades = list(trades or [])
    a.total_trades = len(trades)
    if not trades:
        return a

    win_pnls: list[float] = []
    loss_pnls: list[float] = []   # stored positive
    cur_win = cur_loss = 0

    for t in trades:
        net = _net(t)
        a.net_pnl += net

        if net > 0:
            a.wins += 1
            win_pnls.append(net)
            a.gross_profit += net
            cur_win += 1
            cur_loss = 0
        elif net < 0:
            a.losses += 1
            loss_pnls.append(-net)
            a.gross_loss += -net
            cur_loss += 1
            cur_win = 0
        else:
            a.breakeven += 1
            # breakeven does not extend or break a directional streak count,
            # but it does reset the *current* run (no signed direction).
            cur_win = cur_loss = 0

        a.max_win_streak = max(a.max_win_streak, cur_win)
        a.max_loss_streak = max(a.max_loss_streak, cur_loss)

        # ── per-dimension buckets ────────────────────────────────────────────────
        for dim in _DIMENSIONS:
            raw = getattr(t, dim, None)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            key = str(raw)
            bucket = a.by_dimension[dim].setdefault(
                key, {"trades": 0, "wins": 0, "win_rate": 0.0, "net_pnl": 0.0})
            bucket["trades"] += 1
            if net > 0:
                bucket["wins"] += 1
            bucket["net_pnl"] += net

        # ── R-multiple histogram ─────────────────────────────────────────────────
        rm = getattr(t, "r_multiple", None)
        if rm is not None:
            try:
                a.r_multiple_distribution[_bucket_r(float(rm))] += 1
            except (TypeError, ValueError):
                pass

        # ── MAE/MFE scatter point ────────────────────────────────────────────────
        mae = getattr(t, "mae", None)
        mfe = getattr(t, "mfe", None)
        if mae is not None and mfe is not None:
            a.mae_mfe_scatter.append({
                "mae": float(mae),
                "mfe": float(mfe),
                "r_multiple": float(rm) if rm is not None else None,
                "net_pnl": net,
            })

    # ── derived headline stats ───────────────────────────────────────────────────
    decided = a.wins + a.losses
    a.win_rate = (a.wins / decided * 100.0) if decided else 0.0
    a.profit_factor = (a.gross_profit / a.gross_loss) if a.gross_loss else None
    a.avg_win = (sum(win_pnls) / len(win_pnls)) if win_pnls else 0.0
    a.avg_loss = (sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0
    a.avg_trade = a.net_pnl / a.total_trades

    win_frac = (a.wins / decided) if decided else 0.0
    loss_frac = (a.losses / decided) if decided else 0.0
    a.expectancy = win_frac * a.avg_win - loss_frac * a.avg_loss

    a.current_streak = cur_win if cur_win else -cur_loss

    # finalise per-bucket win rates
    for dim_map in a.by_dimension.values():
        for bucket in dim_map.values():
            bucket["win_rate"] = (
                bucket["wins"] / bucket["trades"] * 100.0) if bucket["trades"] else 0.0

    return a
