"""trading/execution/profit_booking.py — partial profit-booking ladder (T3 §6).

Book a fraction of the position at each target, then let the remainder ride on a
trailing stop. Targets can be given as absolute prices OR as R-multiples (R = the
risk taken at entry); R-multiples are the idiomatic way to say "book 50% at +1R,
trail the rest to +2R".

Pure Python, deterministic — feed it `update(price)` per tick; it returns a list of
BookEvents (usually empty) describing what to sell/cover and how much. Each rung
fires at most once. No I/O — the engine turns BookEvents into real orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _is_long(side: str) -> bool:
    s = side.lower()
    if s in ("long", "buy", "b"):
        return True
    if s in ("short", "sell", "s"):
        return False
    raise ValueError(f"unknown side: {side!r}")


@dataclass(frozen=True)
class Rung:
    """One ladder step: book `fraction` of the ORIGINAL qty at `target`."""
    target: float                 # price, or R-multiple if as_r=True
    fraction: float               # 0..1 of original quantity
    as_r: bool = False
    label: str = ""


@dataclass(frozen=True)
class BookEvent:
    rung: Rung
    price: float                  # the price at which the rung triggered
    qty: float                    # actual base qty to book now
    remaining_after: float        # position qty left open after this booking


@dataclass
class ProfitLadder:
    """Triggers partial exits as price advances through the configured rungs."""

    side: str
    entry_price: float
    quantity: float
    rungs: list[Rung]
    initial_stop: float | None = None     # required if any rung uses as_r=True

    _fired: set = field(default_factory=set, init=False)
    _booked_qty: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._long = _is_long(self.side)
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        total_frac = sum(r.fraction for r in self.rungs)
        if total_frac > 1.0 + 1e-9:
            raise ValueError(f"rung fractions sum to {total_frac} > 1.0")
        if any(r.as_r for r in self.rungs):
            if self.initial_stop is None or abs(self.entry_price - self.initial_stop) <= 0:
                raise ValueError("R-multiple rungs require a non-trivial initial_stop")
        # Sort rungs in trigger order (nearest target first by direction).
        self._ordered = sorted(self.rungs, key=lambda r: self._target_price(r),
                               reverse=not self._long)

    @property
    def risk_per_unit(self) -> float | None:
        if self.initial_stop is None:
            return None
        r = abs(self.entry_price - self.initial_stop)
        return r if r > 0 else None

    def _target_price(self, rung: Rung) -> float:
        if not rung.as_r:
            return rung.target
        r = self.risk_per_unit or 0.0
        return (self.entry_price + rung.target * r) if self._long \
            else (self.entry_price - rung.target * r)

    @property
    def remaining_qty(self) -> float:
        return max(0.0, self.quantity - self._booked_qty)

    def _reached(self, target_price: float, price: float) -> bool:
        return price >= target_price if self._long else price <= target_price

    def update(self, price: float) -> list[BookEvent]:
        """Return BookEvents for every rung newly triggered by `price`."""
        events: list[BookEvent] = []
        for i, rung in enumerate(self._ordered):
            if i in self._fired:
                continue
            tp = self._target_price(rung)
            if not self._reached(tp, price):
                continue
            qty = min(self.quantity * rung.fraction, self.remaining_qty)
            self._fired.add(i)
            if qty <= 0:
                continue
            self._booked_qty += qty
            events.append(BookEvent(rung=rung, price=price, qty=qty,
                                    remaining_after=self.remaining_qty))
        return events

    @property
    def done(self) -> bool:
        return self.remaining_qty <= 1e-12 or len(self._fired) >= len(self._ordered)

    def as_dict(self) -> dict:
        return {
            "side": "long" if self._long else "short",
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "remaining_qty": self.remaining_qty,
            "rungs": [
                {"target_price": self._target_price(r), "fraction": r.fraction,
                 "as_r": r.as_r, "label": r.label, "fired": i in self._fired}
                for i, r in enumerate(self._ordered)
            ],
        }
