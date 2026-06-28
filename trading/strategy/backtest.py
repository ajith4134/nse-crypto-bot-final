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


def _safe(fn, default=0.0):
    try:
        v = fn()
        v = float(v)
        return v if np.isfinite(v) else default
    except Exception:
        return default


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

    trades_rec = pf.trades.records_readable
    trade_rets = []
    if len(trades_rec):
        col = "Return" if "Return" in trades_rec.columns else (
            "Return [%]" if "Return [%]" in trades_rec.columns else None)
        if col:
            vals = trades_rec[col].to_numpy(dtype=float)
            trade_rets = (vals / 100.0 if "%" in col else vals).tolist()
    trades = [{"side": 1, "ret": r} for r in trade_rets]

    wins = [r for r in trade_rets if r > 0]
    losses = [r for r in trade_rets if r < 0]
    gross_win = float(sum(wins))
    gross_loss = float(-sum(losses))
    metrics = {
        "total_return": _safe(pf.total_return),
        "sharpe": _safe(pf.sharpe_ratio),
        "max_drawdown": _safe(pf.max_drawdown),
        "n_trades": int(len(trade_rets)),
        "win_rate": (len(wins) / len(trade_rets) * 100.0) if trade_rets else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0
        else (float("inf") if gross_win > 0 else 0.0),
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
               "profit_factor": (gw / gl) if gl > 0 else (float("inf") if gw > 0 else 0.0),
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
