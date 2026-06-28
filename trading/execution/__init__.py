"""trading/execution/ — Trade Execution Engine (Phase T3).

Pure, deterministic, CPU-only trade-management logic built on the verified T1
(NSE) and T2 (Crypto) foundations. Every module here is network-INDEPENDENT and
fully unit-testable: market I/O (ticks, order dispatch) is injected by the caller,
so the same logic drives paper sim, live trading, and tests.

Pieces (blueprint §T3):
  order_state     — order lifecycle state machine (pending→partial→filled→cancelled)
  mae_mfe         — tick-by-tick MAE/MFE + R-multiple tracker (fills the vectorbt gap)
  trailing        — exponential / ATR / Parabolic-SAR / Chandelier trailing stops
                    + profit-lock-to-breakeven wrapper
  profit_booking  — partial profit-booking ladder (book X% at targets, trail rest)
  circuit_breaker — daily-loss circuit breaker (auto-flat + halt) + overtrading guard
  margin          — SEBI SPAN + Exposure margin estimator/check for NSE orders
  bracket         — bracket + cover order builders for NSE intraday
  kill_switch     — real-money kill-switch (cancel all + flatten all, idempotent)
  engine          — ExecutionEngine: composes the above + honest status() for the dashboard
"""
from __future__ import annotations

from trading.execution.bracket import bracket_order, cover_order
from trading.execution.circuit_breaker import DailyCircuitBreaker
from trading.execution.engine import ExecutionEngine, TradeManager
from trading.execution.kill_switch import KillSwitch
from trading.execution.mae_mfe import MAEMFE
from trading.execution.margin import MarginCheck, check_margin, nse_fo_margin, nse_intraday_margin
from trading.execution.order_state import InvalidTransition, Order, OrderStatus
from trading.execution.profit_booking import BookEvent, ProfitLadder, Rung
from trading.execution.trailing import (
    ATRTrailingStop,
    ChandelierExit,
    ExponentialTrailingStop,
    ParabolicSAR,
    ProfitLockTrailing,
    WilderATR,
)

__all__ = [
    "Order", "OrderStatus", "InvalidTransition",
    "MAEMFE",
    "WilderATR", "ExponentialTrailingStop", "ATRTrailingStop",
    "ChandelierExit", "ParabolicSAR", "ProfitLockTrailing",
    "ProfitLadder", "Rung", "BookEvent",
    "DailyCircuitBreaker",
    "nse_fo_margin", "nse_intraday_margin", "check_margin", "MarginCheck",
    "bracket_order", "cover_order",
    "KillSwitch",
    "ExecutionEngine", "TradeManager",
]
