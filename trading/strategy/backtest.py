"""trading/strategy/backtest.py — backtest via vectorbt + walk-forward (T8.1, reuse-first).

The backtest engine is **vectorbt** (Numba-vectorized; the right tool for scoring whole
evolved populations fast). We only do the glue: map a +1/-1/0 target-position signal to
vectorbt orders with NO lookahead (signal shifted one bar → executed next bar), then read
back the metrics the T8 fitness function needs into our stable BacktestResult shape.
`walk_forward_folds` (pure index splitting) stays ours — it's the OOS scaffolding the
guardrails (T8.2) build on. Falls back to a small pandas backtest if vectorbt is absent,
so the module always imports.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import vectorbt as vbt
    _HAVE_VBT = True
except Exception:  # pragma: no cover
    _HAVE_VBT = False


@dataclass
class BacktestResult:
    metrics: dict
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    n_bars: int = 0

    def as_dict(self) -> dict:
        return {"metrics": self.metrics, "n_trades": len(self.trades), "n_bars": self.n_bars}


# Cap for "no losing trades" — a finite sentinel keeps metrics JSON-safe (no inf) while
# still ranking a lossless strategy as best. >= this value means "no losses in sample".
PF_CAP = 1e6


def _profit_factor(gross_win: float, gross_loss: float) -> float:
    if gross_loss > 0:
        return min(gross_win / gross_loss, PF_CAP)
    return PF_CAP if gross_win > 0 else 0.0


def _safe(fn, default=0.0):
    try:
        v = fn()
        v = float(v)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _segment_trades(target: "np.ndarray", close: "np.ndarray", cost_rate: float) -> list[dict]:
    """Round-trip trades from a ±1/0 target-position series: each maximal run of a constant
    nonzero target is one trade; ret = side * (exit/entry - 1) - 2*cost_rate."""
    out: list[dict] = []
    n = min(len(target), len(close))
    i = 0
    while i < n:
        side = target[i]
        if side == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and target[j + 1] == side:
            j += 1
        entry, exit_ = float(close[i]), float(close[j])
        if entry > 0:
            ret = float(side) * (exit_ / entry - 1.0) - 2.0 * cost_rate
            out.append({"side": int(side), "ret": ret})
        i = j + 1
    return out


def backtest_signal(signal: pd.Series, ohlcv: pd.DataFrame, *, fee_bps: float = 2.0,
                    slippage_bps: float = 1.0, periods_per_year: int = 252) -> BacktestResult:
    """Backtest a +1/-1/0 target-position signal on `ohlcv` (needs 'close')."""
    close = ohlcv["close"].reset_index(drop=True).astype(float)
    sig = signal.reset_index(drop=True).fillna(0).astype(float)
    if len(sig) != len(close):
        raise ValueError("signal and ohlcv length mismatch")
    cost_rate = (fee_bps + slippage_bps) / 1e4
    target = sig.shift(1).fillna(0.0)                       # next-bar execution (no lookahead)

    if not _HAVE_VBT:  # pragma: no cover
        return _pandas_backtest(close, target, cost_rate, periods_per_year)

    # Give vectorbt a datetime index so it can annualise (freq=1D ⇒ periods_per_year≈252).
    idx = pd.date_range("2020-01-01", periods=len(close), freq="D")
    close_v = pd.Series(close.to_numpy(), index=idx)
    target_v = pd.Series(target.to_numpy(), index=idx)
    pf = vbt.Portfolio.from_orders(
        close_v, size=target_v, size_type="targetpercent", direction="both",
        fees=cost_rate, freq="1D", init_cash=100.0,
    )

    # Per-trade returns from the SIGNAL SEGMENTS, not vectorbt's trade records.
    # B4 root cause (2026-07-16, PROMOTED=0): with from_orders(size_type="targetpercent")
    # the records_readable "Return" column is an order-pairing cash-flow artifact — SHORT
    # winners came back NEGATIVE (measured: a 60%-accurate short-only oracle showed only
    # 41.5% positive trade returns while its equity rose). Every DSR was computed on that
    # corrupted series, so no candidate could ever clear the promotion gate. A maximal run
    # of constant nonzero target IS the round trip: its directional return is exact for
    # full-allocation target positions, and both sides pay entry+exit costs.
    trades = _segment_trades(target.to_numpy(), close.to_numpy(), cost_rate)
    trade_rets = [t["ret"] for t in trades]

    wins = [r for r in trade_rets if r > 0]
    losses = [r for r in trade_rets if r < 0]
    gross_win = float(sum(wins))
    gross_loss = float(-sum(losses))
    # Sharpe computed from per-period portfolio returns honouring periods_per_year
    # (vectorbt's own sharpe_ratio annualises by calendar freq=365, ignoring the param
    #  and diverging from the pandas fallback — compute it ourselves for consistency).
    try:
        rets_arr = pf.returns().to_numpy(dtype=float)
        rstd = float(np.std(rets_arr, ddof=1)) if len(rets_arr) > 1 else 0.0
        sharpe = float(np.mean(rets_arr) / rstd * np.sqrt(periods_per_year)) if rstd > 0 else 0.0
    except Exception:
        sharpe = 0.0
    metrics = {
        "total_return": _safe(pf.total_return),
        "sharpe": sharpe,
        "max_drawdown": _safe(pf.max_drawdown),
        "n_trades": int(len(trade_rets)),
        "win_rate": (len(wins) / len(trade_rets) * 100.0) if trade_rets else 0.0,
        "profit_factor": _profit_factor(gross_win, gross_loss),
        "avg_win": float(np.mean(wins)) if wins else 0.0,
        "avg_loss": float(np.mean(losses)) if losses else 0.0,
        "expectancy": float(np.mean(trade_rets)) if trade_rets else 0.0,
        "gross_win": gross_win, "gross_loss": gross_loss,
    }
    equity = _safe(lambda: pf.value(), default=None)
    try:
        equity_curve = pf.value().to_numpy().tolist()
    except Exception:
        equity_curve = []
    return BacktestResult(metrics=metrics, trades=trades,
                          equity_curve=equity_curve, n_bars=len(close))


def _pandas_backtest(close, target, cost_rate, periods_per_year):  # pragma: no cover
    """Minimal fallback if vectorbt is unavailable (numerically close, not identical)."""
    bar_ret = close.pct_change().fillna(0.0)
    gross = target * bar_ret
    cost = target.diff().abs().fillna(target.abs()) * cost_rate
    net = (gross - cost).to_numpy()
    equity = np.cumprod(1.0 + net)
    std = float(np.std(net, ddof=1)) if len(net) > 1 else 0.0
    sharpe = float(np.mean(net) / std * np.sqrt(periods_per_year)) if std > 0 else 0.0
    peak = np.maximum.accumulate(equity) if len(equity) else np.array([1.0])
    max_dd = float(((equity - peak) / peak).min()) if len(equity) else 0.0
    # crude per-trade split on position runs
    pos = target.to_numpy(); trades = []; i = 0
    while i < len(pos):
        if pos[i] == 0:
            i += 1; continue
        j = i
        while j < len(pos) and pos[j] == pos[i]:
            j += 1
        trades.append({"side": int(pos[i]), "ret": float(np.prod(1 + net[i:j]) - 1)})
        i = j
    rets = [t["ret"] for t in trades]
    wins = [r for r in rets if r > 0]; losses = [r for r in rets if r < 0]
    gw = float(sum(wins)); gl = float(-sum(losses))
    metrics = {"total_return": float(equity[-1] - 1) if len(equity) else 0.0, "sharpe": sharpe,
               "max_drawdown": max_dd, "n_trades": len(rets),
               "win_rate": (len(wins) / len(rets) * 100) if rets else 0.0,
               "profit_factor": _profit_factor(gw, gl),
               "avg_win": float(np.mean(wins)) if wins else 0.0,
               "avg_loss": float(np.mean(losses)) if losses else 0.0,
               "expectancy": float(np.mean(rets)) if rets else 0.0,
               "gross_win": gw, "gross_loss": gl}
    return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity.tolist(),
                          n_bars=len(close))


def walk_forward_folds(n_rows: int, *, n_folds: int = 4, scheme: str = "rolling",
                       min_train: int | None = None) -> list[dict]:
    """Split [0, n_rows) into OOS folds: {train:(s,e), test:(s,e)} half-open ranges."""
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    if n_rows < n_folds * 2:
        raise ValueError(f"need >= {n_folds * 2} rows for {n_folds} folds, got {n_rows}")
    block = n_rows // (n_folds + 1)
    min_train = min_train or block
    folds = []
    for k in range(1, n_folds + 1):
        test_start = block * k
        test_end = block * (k + 1) if k < n_folds else n_rows
        if scheme == "anchored":
            train_start, train_end = 0, test_start
        else:
            train_start, train_end = max(0, test_start - max(min_train, block)), test_start
        if train_end - train_start < 2:
            train_start = 0
        folds.append({"train": (train_start, train_end), "test": (test_start, test_end)})
    return folds
