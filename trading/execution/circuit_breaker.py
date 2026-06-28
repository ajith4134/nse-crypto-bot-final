"""trading/execution/circuit_breaker.py — daily-loss circuit breaker (T3 §7).

A hard risk governor: track the day's running P&L (realised + open) and, the moment
the loss breaches the configured limit, TRIP — which (a) demands every position be
flattened and (b) blocks any new entry for the rest of the trading day. An optional
overtrading guard caps trades/day. State is persisted (per trading day, IST) so a
process restart cannot "forget" that the breaker already tripped today.

Pure logic + JSON persistence (reuses trading.state). The engine injects the actual
flatten callback; this module only decides WHEN to flatten and WHETHER to allow the
next order. Time is passed in (IST date) so it is fully deterministic in tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading import state
from trading.squareoff import now_ist

_CB_FILE = "circuit_breaker.json"


@dataclass
class DailyCircuitBreaker:
    """Daily loss / overtrading governor for one trading account."""

    max_daily_loss: float                 # positive number; loss limit in quote ccy
    max_trades: int | None = None         # optional overtrading cap
    persist: bool = True
    _day: str = field(default="", init=False)
    realized_pnl: float = field(default=0.0, init=False)
    open_pnl: float = field(default=0.0, init=False)
    trade_count: int = field(default=0, init=False)
    tripped: bool = field(default=False, init=False)
    trip_reason: str = field(default="", init=False)

    def __post_init__(self) -> None:
        if self.max_daily_loss <= 0:
            raise ValueError("max_daily_loss must be a positive number")
        self._day = self._today()
        if self.persist:
            self._load()

    @staticmethod
    def _today() -> str:
        return now_ist().date().isoformat()

    # ── persistence ─────────────────────────────────────────────────────────────
    def _load(self) -> None:
        data = state.load_json(_CB_FILE, {})
        if isinstance(data, dict) and data.get("day") == self._day:
            self.realized_pnl = float(data.get("realized_pnl", 0.0))
            self.trade_count = int(data.get("trade_count", 0))
            self.tripped = bool(data.get("tripped", False))
            self.trip_reason = str(data.get("trip_reason", ""))

    def _save(self) -> None:
        if not self.persist:
            return
        state.save_json(_CB_FILE, {
            "day": self._day, "realized_pnl": self.realized_pnl,
            "trade_count": self.trade_count, "tripped": self.tripped,
            "trip_reason": self.trip_reason,
        })

    def _rollover_if_new_day(self) -> None:
        today = self._today()
        if today != self._day:
            self._day = today
            self.realized_pnl = 0.0
            self.open_pnl = 0.0
            self.trade_count = 0
            self.tripped = False
            self.trip_reason = ""
            self._save()

    # ── feed ────────────────────────────────────────────────────────────────────
    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.open_pnl

    def _check_trip(self) -> None:
        if self.tripped:
            return
        if self.total_pnl <= -self.max_daily_loss:
            self.tripped = True
            self.trip_reason = (
                f"daily loss {self.total_pnl:.2f} breached limit -{self.max_daily_loss:.2f}"
            )
        elif self.max_trades is not None and self.trade_count >= self.max_trades:
            self.tripped = True
            self.trip_reason = f"trade count {self.trade_count} hit cap {self.max_trades}"
        if self.tripped:
            self._save()

    def record_trade(self, realized_delta: float = 0.0) -> bool:
        """Record a closed trade's realised P&L. Returns True if this TRIPS the breaker."""
        self._rollover_if_new_day()
        was = self.tripped
        self.realized_pnl += realized_delta
        self.trade_count += 1
        self._check_trip()
        self._save()
        return self.tripped and not was

    def mark_open_pnl(self, open_pnl: float) -> bool:
        """Update live unrealised P&L (drives intrabar trips). Returns True if it TRIPS."""
        self._rollover_if_new_day()
        was = self.tripped
        self.open_pnl = open_pnl
        self._check_trip()
        return self.tripped and not was

    # ── gate ─────────────────────────────────────────────────────────────────────
    def allow_new_order(self) -> bool:
        self._rollover_if_new_day()
        return not self.tripped

    def assert_allowed(self) -> None:
        if not self.allow_new_order():
            raise CircuitBreakerTripped(self.trip_reason or "circuit breaker tripped")

    def reset(self) -> None:
        """Manual reset (e.g. next day, or supervised override)."""
        self.realized_pnl = 0.0
        self.open_pnl = 0.0
        self.trade_count = 0
        self.tripped = False
        self.trip_reason = ""
        self._day = self._today()
        self._save()

    def as_dict(self) -> dict:
        return {
            "day": self._day, "max_daily_loss": self.max_daily_loss,
            "max_trades": self.max_trades, "realized_pnl": self.realized_pnl,
            "open_pnl": self.open_pnl, "total_pnl": self.total_pnl,
            "trade_count": self.trade_count, "tripped": self.tripped,
            "trip_reason": self.trip_reason, "allow_new_order": not self.tripped,
        }


class CircuitBreakerTripped(RuntimeError):
    """Raised when an order is attempted after the daily breaker has tripped."""
