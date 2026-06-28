"""trading/execution/order_state.py — order lifecycle state machine (T3 §1).

A single Order object that enforces the legal lifecycle:

    PENDING ──fill(partial)──► PARTIAL ──fill(rest)──► FILLED   (terminal)
       │                          │
       └────────cancel────────────┴──► CANCELLED                (terminal)
       └────────reject─────────────────► REJECTED               (terminal)

Illegal transitions (e.g. filling a CANCELLED order, over-filling) raise
InvalidTransition rather than silently corrupting state. Fills accumulate a
size-weighted average price. Pure Python, no I/O — fully unit-testable; the
broker/paper layer feeds it fill callbacks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)

    @property
    def is_open(self) -> bool:
        return self in (OrderStatus.PENDING, OrderStatus.PARTIAL)


class InvalidTransition(RuntimeError):
    """Raised when an order is driven through an illegal state change."""


@dataclass
class Order:
    id: str
    symbol: str
    exchange: str
    side: str                       # "BUY" | "SELL"
    quantity: float                 # total requested
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fills: list[dict] = field(default_factory=list)

    EPS = 1e-9

    def __post_init__(self) -> None:
        self.side = self.side.upper()
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY/SELL, got {self.side!r}")
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")

    @property
    def remaining(self) -> float:
        return max(0.0, self.quantity - self.filled_qty)

    @property
    def is_open(self) -> bool:
        return self.status.is_open

    # ── transitions ───────────────────────────────────────────────────────────
    def fill(self, qty: float, price: float) -> "Order":
        """Apply a (partial) fill of `qty` at `price`. Transitions the status."""
        if not self.status.is_open:
            raise InvalidTransition(
                f"cannot fill order {self.id} in terminal state {self.status.value}"
            )
        if qty <= 0:
            raise ValueError("fill qty must be > 0")
        if qty > self.remaining + self.EPS:
            raise InvalidTransition(
                f"over-fill: order {self.id} has {self.remaining} remaining, got {qty}"
            )
        # Size-weighted average fill price.
        new_filled = self.filled_qty + qty
        self.avg_price = (self.avg_price * self.filled_qty + price * qty) / new_filled
        self.filled_qty = new_filled
        self.fills.append({"qty": qty, "price": price})
        self.status = (
            OrderStatus.FILLED if self.remaining <= self.EPS else OrderStatus.PARTIAL
        )
        return self

    def cancel(self) -> "Order":
        """Cancel an open (pending or partially filled) order."""
        if not self.status.is_open:
            raise InvalidTransition(
                f"cannot cancel order {self.id} in terminal state {self.status.value}"
            )
        self.status = OrderStatus.CANCELLED
        return self

    def reject(self, reason: str = "") -> "Order":
        """Mark a still-pending order rejected by the broker/risk layer."""
        if self.status is not OrderStatus.PENDING:
            raise InvalidTransition(
                f"only a PENDING order can be rejected; {self.id} is {self.status.value}"
            )
        self.status = OrderStatus.REJECTED
        if reason:
            self.fills.append({"rejected": reason})
        return self

    def as_dict(self) -> dict:
        return {
            "id": self.id, "symbol": self.symbol, "exchange": self.exchange,
            "side": self.side, "quantity": self.quantity, "status": self.status.value,
            "filled_qty": self.filled_qty, "remaining": self.remaining,
            "avg_price": self.avg_price,
        }
