"""trading/execution/mae_mfe.py — tick-by-tick MAE/MFE tracker (T3 §2).

MAE (Maximum Adverse Excursion)  = worst unrealised move AGAINST the position.
MFE (Maximum Favourable Excursion) = best unrealised move IN FAVOUR.

vectorbt and most backtesters only give you entry/exit P&L; they do NOT tell you
how far a trade ran underwater before it worked, or how much open profit you gave
back. That per-trade excursion is the single most useful number for tuning stops
and targets, so we track it ourselves, tick by tick.

Everything is expressed both in price terms and as an R-multiple, where
    R = |entry - initial_stop|   (the risk taken per unit at entry).
R-multiples make MAE/MFE comparable across symbols and position sizes.

Pure Python, deterministic — feed it `update(price)` per tick; no I/O.
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


@dataclass
class MAEMFE:
    """Tracks adverse/favourable excursion for one open position."""

    side: str
    entry_price: float
    initial_stop: float | None = None     # to derive risk-per-unit (R)
    qty: float = 1.0

    # running extremes (price terms, signed P&L-per-unit basis)
    _best_favorable: float = field(default=0.0, init=False)   # >= 0
    _worst_adverse: float = field(default=0.0, init=False)    # <= 0
    _last_price: float = field(default=0.0, init=False)
    _max_price: float = field(default=float("-inf"), init=False)
    _min_price: float = field(default=float("inf"), init=False)
    _ticks: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._long = _is_long(self.side)
        if self.entry_price <= 0:
            raise ValueError("entry_price must be > 0")
        self._last_price = self.entry_price
        self.update(self.entry_price)

    @property
    def risk_per_unit(self) -> float | None:
        if self.initial_stop is None:
            return None
        r = abs(self.entry_price - self.initial_stop)
        return r if r > 0 else None

    def _pnl_per_unit(self, price: float) -> float:
        """Signed P&L per unit at `price` (positive = favourable)."""
        return (price - self.entry_price) if self._long else (self.entry_price - price)

    # ── feed ──────────────────────────────────────────────────────────────────
    def update(self, price: float) -> "MAEMFE":
        if price <= 0:
            raise ValueError("price must be > 0")
        pnl = self._pnl_per_unit(price)
        self._best_favorable = max(self._best_favorable, pnl)
        self._worst_adverse = min(self._worst_adverse, pnl)
        self._max_price = max(self._max_price, price)
        self._min_price = min(self._min_price, price)
        self._last_price = price
        self._ticks += 1
        return self

    # ── readouts (price terms) ──────────────────────────────────────────────────
    @property
    def mfe(self) -> float:
        """Max favourable excursion, price terms per unit (>= 0)."""
        return self._best_favorable

    @property
    def mae(self) -> float:
        """Max adverse excursion, price terms per unit, returned POSITIVE (>= 0)."""
        return -self._worst_adverse

    @property
    def current_pnl(self) -> float:
        """Open P&L for the whole position at the last seen price."""
        return self._pnl_per_unit(self._last_price) * self.qty

    @property
    def excursion_high(self) -> float:
        return self._max_price

    @property
    def excursion_low(self) -> float:
        return self._min_price

    # ── readouts (R-multiples) ──────────────────────────────────────────────────
    def _as_r(self, value_per_unit: float) -> float | None:
        r = self.risk_per_unit
        return None if r is None else value_per_unit / r

    @property
    def mfe_r(self) -> float | None:
        return self._as_r(self.mfe)

    @property
    def mae_r(self) -> float | None:
        return self._as_r(-self.mae)   # negative R = how deep underwater

    @property
    def current_r(self) -> float | None:
        return self._as_r(self._pnl_per_unit(self._last_price))

    @property
    def efficiency(self) -> float | None:
        """Captured fraction of the favourable run (current_pnl / mfe), 0..1.

        How much of the best open profit is still on the table right now — a low
        value means the trade ran up and gave it back. None until any MFE exists.
        """
        if self._best_favorable <= 0:
            return None
        return self._pnl_per_unit(self._last_price) / self._best_favorable

    def as_dict(self) -> dict:
        return {
            "side": "long" if self._long else "short",
            "entry_price": self.entry_price,
            "ticks": self._ticks,
            "mfe": self.mfe, "mae": self.mae,
            "mfe_r": self.mfe_r, "mae_r": self.mae_r,
            "current_pnl": self.current_pnl, "current_r": self.current_r,
            "efficiency": self.efficiency,
            "excursion_high": self.excursion_high, "excursion_low": self.excursion_low,
        }
