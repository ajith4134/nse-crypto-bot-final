"""CORTEX fitness engine — mark-to-market scoring + honesty gates (B1, stitch-map rows 1-3).

Everything in CORTEX is judged by THIS module (design §6-B1: "the fitness
engine comes FIRST"). Built on **vectorbt 1.0** (installed OSS revival) —
Portfolio.from_signals with fees does the heavy lifting; we only add the
scorecard shape and the CANON gates. Reuse-first: nothing vectorbt or
dieboldmariano already implements is re-implemented here.

CANON coverage (research/video/MASTER-REQUIREMENTS.md):

* **CANON-39** — trading scorecard: Sharpe/Sortino/CAGR/max-drawdown/
  expectancy/win-rate + the per-trade economics headline ($/round-trip).
* **CANON-40** — cost-aware results: fees are applied inside the vectorbt
  portfolio, so EVERY number reported here is fee-inclusive.
* **CANON-41** — mark-to-market drawdown-aware fitness (the KRF/RBT rule):
  profit-per-trade from realized+unrealized equity × 1/(1+avg underwater
  depth) — quality over trade count; hidden open losses are impossible.
* **CANON-36** — naive-baseline honesty gates: a regressor must beat shift-1
  persistence (MSE + Diebold-Mariano significance, pip `dieboldmariano`);
  a classifier must beat the majority-class share.
* **CANON-38** — execution gate: the strategy's CAGR/MaxDD ratio must beat
  buy-and-hold's on the same series (same fees).

Honesty rule: gates return (passed, detail) and :func:`honest_report` includes
every failed gate verbatim — failures are surfaced, never hidden.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import vectorbt as vbt
from dieboldmariano import dm_test

#: default two-sided Diebold-Mariano significance level for persistence_gate
DM_P_MAX = 0.10


def _to_series(arr, index=None, name="close") -> pd.Series:
    if isinstance(arr, pd.Series):
        return arr
    s = pd.Series(np.asarray(arr), name=name)
    if index is not None:
        s.index = index
    return s


def _f(x, default=0.0) -> float:
    """NaN/inf-safe float for report dicts (0-trade portfolios yield NaN/inf)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


# ── engine ───────────────────────────────────────────────────────────────────

def run_signals(close, entries, exits, fee: float = 0.001, freq: str = "1D"
                ) -> "vbt.Portfolio":
    """Backtest boolean entry/exit signals → a vectorbt Portfolio (fee-inclusive).

    Thin wrapper over ``vectorbt.Portfolio.from_signals`` (stitch-map row 1);
    `fee` is the proportional fee per fill (CANON-40), `freq` the bar frequency
    used for annualization (ignored if `close` already carries an inferable
    DatetimeIndex frequency).
    """
    close = _to_series(close)
    entries = _to_series(entries, index=close.index, name="entries").astype(bool)
    exits = _to_series(exits, index=close.index, name="exits").astype(bool)
    pf = vbt.Portfolio.from_signals(close, entries, exits, fees=fee, freq=freq)
    pf._cortex_fee = fee                     # remembered so benchmark_gate is fee-fair
    return pf


def scorecard(pf) -> dict:
    """CANON-39/40 scorecard, all fee-inclusive, headline = $/round-trip.

    n_trades counts closed+open trades; profit_per_trade uses mark-to-market
    trade PnL (open trades included at current price), matching CANON-41.
    """
    trades = pf.trades
    n_trades = int(trades.count())
    pnl = trades.pnl.values
    return {
        "sharpe": _f(pf.sharpe_ratio()),
        "sortino": _f(pf.sortino_ratio()),
        "cagr": _f(pf.annualized_return()),
        "max_dd": _f(pf.max_drawdown()),
        "expectancy": _f(trades.expectancy()) if n_trades else 0.0,
        "win_rate": _f(trades.win_rate()) if n_trades else 0.0,
        "n_trades": n_trades,
        "profit_per_trade": _f(np.mean(pnl)) if n_trades else 0.0,  # $/round-trip headline
        "total_return": _f(pf.total_return()),
        "total_fees_paid": _f(pf.orders.fees.sum()) if pf.orders.count() else 0.0,
    }


def underwater_fitness(pf) -> float:
    """CANON-41 (KRF-10/RBT-03/RBT-12): profit-per-trade × 1/(1+avg underwater depth).

    * profit-per-trade is MARK-TO-MARKET: (final equity − initial equity) /
      max(1, n_trades) where equity = realized + unrealized value, so an open
      losing position lowers fitness (the KRF hidden-loss bug is impossible).
    * avg underwater depth = mean |drawdown| of the equity curve over ALL bars
      (0 when at a high-water mark), so a choppy path scores below a smooth
      path with the same profit — quality over trade count.
    """
    equity = pf.value()
    total_pnl = float(equity.iloc[-1] - pf.init_cash)
    n_trades = max(1, int(pf.trades.count()))
    profit_per_trade = total_pnl / n_trades
    avg_underwater = _f(-pf.drawdown().mean())          # drawdown series is ≤ 0
    return profit_per_trade * (1.0 / (1.0 + avg_underwater))


# ── honesty gates (each returns (passed: bool, detail: dict)) ────────────────

def persistence_gate(y_true, y_pred, p_max: float = DM_P_MAX) -> tuple[bool, dict]:
    """CANON-36 regression gate: beat shift-1 persistence on MSE *significantly*.

    Persistence forecast = y[t-1] (the naive "tomorrow == today" baseline the
    TFM/LSTM videos failed to beat). Passing requires BOTH a lower MSE than
    persistence AND Diebold-Mariano (pip `dieboldmariano`, Harvey-corrected)
    two-sided p < `p_max` — i.e. the improvement is statistically real, not
    noise.
    """
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    if yt.shape[0] != yp.shape[0] or yt.shape[0] < 3:
        raise ValueError("y_true/y_pred must be equal-length with >= 3 samples")
    actual, model, persistence = yt[1:], yp[1:], yt[:-1]
    mse_model = float(np.mean((actual - model) ** 2))
    mse_persistence = float(np.mean((actual - persistence) ** 2))
    try:
        dm_stat, dm_p = dm_test(actual.tolist(), model.tolist(), persistence.tolist(),
                                one_sided=False)
        dm_stat, dm_p = float(dm_stat), float(dm_p)
    except Exception as exc:                 # zero-variance loss diff etc. → no evidence
        dm_stat, dm_p = float("nan"), 1.0
        detail_err = str(exc)
    else:
        detail_err = None
    passed = mse_model < mse_persistence and dm_p < p_max
    detail = {"mse_model": mse_model, "mse_persistence": mse_persistence,
              "dm_stat": dm_stat, "dm_p": dm_p, "p_max": p_max}
    if detail_err:
        detail["dm_error"] = detail_err
    return passed, detail


def majority_gate(y_true, y_pred_cls) -> tuple[bool, dict]:
    """CANON-36 classification gate: accuracy must beat the majority-class share.

    An "accurate" model that just parrots the dominant class (the PNP-15
    pitfall) scores accuracy == majority share and FAILS (strict >)."""
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred_cls)
    if yt.shape[0] != yp.shape[0] or yt.shape[0] == 0:
        raise ValueError("y_true/y_pred_cls must be equal-length and non-empty")
    accuracy = float(np.mean(yt == yp))
    _, counts = np.unique(yt, return_counts=True)
    majority_share = float(counts.max() / yt.shape[0])
    passed = accuracy > majority_share
    return passed, {"accuracy": accuracy, "majority_share": majority_share}


def benchmark_gate(pf, close, fee: float | None = None) -> tuple[bool, dict]:
    """CANON-38 execution gate: CAGR/MaxDD must beat buy-and-hold's ratio.

    Buy-and-hold is simulated on the SAME series with the SAME fee model
    (vectorbt from_holding), so the comparison is fee-honest. A zero-drawdown
    leg gets ratio = +inf CAGR-sign-aware (monotonic buy-and-hold is an
    honest, nearly unbeatable benchmark — that is the point of the gate).
    """
    close = _to_series(close)
    fees = float(fee if fee is not None else getattr(pf, "_cortex_fee", 0.0))
    bh = vbt.Portfolio.from_holding(close, fees=fees, freq=pf.wrapper.freq)

    def _ratio(p) -> float:
        cagr = _f(p.annualized_return())
        max_dd = abs(_f(p.max_drawdown()))
        if max_dd == 0.0:
            return math.inf if cagr > 0 else (0.0 if cagr == 0 else -math.inf)
        return cagr / max_dd

    model_ratio, bh_ratio = _ratio(pf), _ratio(bh)
    passed = model_ratio > bh_ratio
    return passed, {"model_cagr_over_maxdd": model_ratio,
                    "buy_hold_cagr_over_maxdd": bh_ratio,
                    "model_cagr": _f(pf.annualized_return()),
                    "model_max_dd": _f(pf.max_drawdown()),
                    "buy_hold_cagr": _f(bh.annualized_return()),
                    "buy_hold_max_dd": _f(bh.max_drawdown())}


def honest_report(pf=None, close=None, y_true=None, y_pred=None,
                  y_true_cls=None, y_pred_cls=None) -> dict:
    """One honest verdict: scorecard + fitness + every applicable gate (CANON-36/38-41).

    Runs whichever gates the provided inputs allow (regression pair →
    persistence_gate; class pair → majority_gate; pf+close → benchmark_gate)
    and NEVER hides a failure: every gate's passed flag + full detail is in
    the report, and ``all_passed`` is the AND over the gates that ran.
    """
    report: dict = {"gates": {}}
    if pf is not None:
        report["scorecard"] = scorecard(pf)
        report["underwater_fitness"] = underwater_fitness(pf)
    if y_true is not None and y_pred is not None:
        passed, detail = persistence_gate(y_true, y_pred)
        report["gates"]["persistence"] = {"passed": passed, **detail}
    if y_true_cls is not None and y_pred_cls is not None:
        passed, detail = majority_gate(y_true_cls, y_pred_cls)
        report["gates"]["majority"] = {"passed": passed, **detail}
    if pf is not None and close is not None:
        passed, detail = benchmark_gate(pf, close)
        report["gates"]["benchmark"] = {"passed": passed, **detail}
    report["all_passed"] = all(g["passed"] for g in report["gates"].values()) \
        if report["gates"] else False
    return report
