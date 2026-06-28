"""trading/execution/engine.py — ExecutionEngine + TradeManager (T3 composition).

Ties the T3 pieces into one honest, market-agnostic engine:

  Order registry (order_state)         — every live order's lifecycle
  TradeManager per open position       — MAE/MFE + trailing stop + profit ladder
  DailyCircuitBreaker                  — global daily-loss / overtrading governor
  KillSwitch                           — panic flatten

The engine holds NO market connection. Ticks are pushed in via `on_bar`, and order
dispatch / flattening are injected callables (NSESession.place_order for live,
PaperEngine for crypto, or a test double). `status()` returns a JSON-able snapshot
the dashboard renders — real state only, never decorative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from trading.execution.circuit_breaker import DailyCircuitBreaker
from trading.execution.kill_switch import KillSwitch
from trading.execution.mae_mfe import MAEMFE
from trading.execution.order_state import Order, OrderStatus
from trading.execution.profit_booking import BookEvent, ProfitLadder
from trading.execution.trailing import TrailingStop


@dataclass
class TradeManager:
    """Owns the post-entry lifecycle of ONE position: excursion + stop + ladder."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    trailing: TrailingStop
    ladder: ProfitLadder | None = None
    initial_stop: float | None = None

    closed: bool = field(default=False, init=False)
    exit_reason: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.mae_mfe = MAEMFE(self.side, self.entry_price,
                              initial_stop=self.initial_stop, qty=self.quantity)
        self.open_qty = self.quantity

    def on_bar(self, high: float, low: float | None = None, close: float | None = None) -> dict:
        """Feed one bar/tick; return the resulting actions (stop move, bookings, exit)."""
        price = high if close is None else close
        result: dict = {"symbol": self.symbol, "book_events": [], "exit": False}
        if self.closed:
            result["closed"] = True
            return result

        self.mae_mfe.update(price)
        stop = self.trailing.update(high, low, close)
        result["stop"] = stop

        # Partial profit booking first (reduces open qty).
        if self.ladder is not None:
            events: list[BookEvent] = self.ladder.update(price)
            for ev in events:
                self.open_qty = max(0.0, self.open_qty - ev.qty)
            result["book_events"] = [
                {"label": ev.rung.label, "price": ev.price, "qty": ev.qty,
                 "remaining_after": ev.remaining_after} for ev in events
            ]

        # Trailing-stop exit closes whatever remains.
        if self.trailing.exit_triggered(price):
            self.closed = True
            self.exit_reason = "trailing_stop"
            result.update(exit=True, exit_reason=self.exit_reason, exit_price=stop,
                          exit_qty=self.open_qty)
            self.open_qty = 0.0
        elif self.open_qty <= 1e-12:
            self.closed = True
            self.exit_reason = "fully_booked"
            result.update(closed=True, exit_reason=self.exit_reason)
        return result

    def status(self) -> dict:
        return {
            "symbol": self.symbol, "side": self.side, "entry_price": self.entry_price,
            "quantity": self.quantity, "open_qty": self.open_qty,
            "closed": self.closed, "exit_reason": self.exit_reason,
            "stop": self.trailing.stop,
            "mae_mfe": self.mae_mfe.as_dict(),
            "ladder": self.ladder.as_dict() if self.ladder else None,
        }


class ExecutionEngine:
    """Composes orders + trade managers + circuit breaker + kill switch."""

    def __init__(self, *, circuit_breaker: DailyCircuitBreaker | None = None,
                 cancel_all: Callable[[], object] | None = None,
                 flatten_all: Callable[[], object] | None = None,
                 max_daily_loss: float = 10_000.0):
        self.orders: dict[str, Order] = {}
        self.managers: dict[str, TradeManager] = {}
        self.breaker = circuit_breaker or DailyCircuitBreaker(
            max_daily_loss=max_daily_loss, persist=False)
        self.kill = KillSwitch(
            cancel_all=cancel_all or (lambda: self._cancel_all_orders()),
            flatten_all=flatten_all or (lambda: self._flatten_all_managers()),
        )

    # ── orders ────────────────────────────────────────────────────────────────
    def register_order(self, order: Order) -> Order:
        self.breaker.assert_allowed()
        self.orders[order.id] = order
        return order

    def on_fill(self, order_id: str, qty: float, price: float) -> Order:
        return self.orders[order_id].fill(qty, price)

    def _cancel_all_orders(self) -> list[str]:
        cancelled = []
        for oid, o in self.orders.items():
            if o.is_open:
                o.cancel()
                cancelled.append(oid)
        return cancelled

    # ── positions / trade managers ──────────────────────────────────────────────
    def open_trade(self, key: str, manager: TradeManager) -> TradeManager:
        self.breaker.assert_allowed()
        self.managers[key] = manager
        self.breaker.record_trade(0.0)
        return manager

    def _flatten_all_managers(self) -> list[str]:
        flat = []
        for key, m in self.managers.items():
            if not m.closed:
                m.closed = True
                m.exit_reason = "kill_switch"
                m.open_qty = 0.0
                flat.append(key)
        return flat

    def on_bar(self, key: str, high: float, low: float | None = None,
               close: float | None = None) -> dict:
        """Drive one position's manager and fold open P&L into the breaker."""
        m = self.managers.get(key)
        if m is None:
            return {"error": f"no manager for {key!r}"}
        result = m.on_bar(high, low, close)
        # Aggregate open P&L across all live managers for the breaker.
        open_pnl = sum(mm.mae_mfe.current_pnl for mm in self.managers.values() if not mm.closed)
        if self.breaker.mark_open_pnl(open_pnl):
            report = self.kill.engage(reason=self.breaker.trip_reason)
            result["circuit_breaker_tripped"] = True
            result["kill_report"] = report
        return result

    def panic(self, reason: str = "manual") -> dict:
        return self.kill.engage(reason=reason)

    # ── honest status for the dashboard ─────────────────────────────────────────
    def status(self) -> dict:
        return {
            "orders": {
                "total": len(self.orders),
                "open": sum(1 for o in self.orders.values() if o.is_open),
                "by_status": {
                    s.value: sum(1 for o in self.orders.values() if o.status is s)
                    for s in OrderStatus
                },
                "list": [o.as_dict() for o in self.orders.values()],
            },
            "positions": [m.status() for m in self.managers.values()],
            "open_positions": sum(1 for m in self.managers.values() if not m.closed),
            "circuit_breaker": self.breaker.as_dict(),
            "kill_switch": self.kill.as_dict(),
        }
