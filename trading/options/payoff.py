"""trading/options/payoff.py — multi-leg options payoff diagram (T4 §8 of features).

Build the expiry P&L curve for an arbitrary combination of option + underlying legs
(spreads, straddles, condors, covered calls, …): the per-price P&L, the breakeven
price(s), and the max profit / max loss across a scanned price band. This is the
data behind the dashboard's payoff chart.

A leg is a PayoffLeg(kind, position, strike, premium, qty, lot_size):
  • kind     : "call" | "put" | "underlying"
  • position : "long" | "short"
  • strike   : option strike, or for "underlying" the entry price
  • premium  : option premium paid/received (ignored for "underlying")
P&L is per the FULL leg (qty × lot_size). Pure Python, deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PayoffLeg:
    kind: str                  # call | put | underlying
    position: str              # long | short
    strike: float              # strike, or entry price for underlying
    premium: float = 0.0
    qty: float = 1.0
    lot_size: int = 1

    def __post_init__(self) -> None:
        if self.kind.lower() not in ("call", "put", "underlying"):
            raise ValueError(f"bad kind {self.kind!r}")
        if self.position.lower() not in ("long", "short"):
            raise ValueError(f"bad position {self.position!r}")

    @property
    def sign(self) -> int:
        return 1 if self.position.lower() == "long" else -1

    @property
    def multiplier(self) -> float:
        return self.qty * self.lot_size

    def pnl_at(self, price: float) -> float:
        k = self.kind.lower()
        if k == "call":
            intrinsic = max(0.0, price - self.strike)
            per_unit = self.sign * (intrinsic - self.premium)
        elif k == "put":
            intrinsic = max(0.0, self.strike - price)
            per_unit = self.sign * (intrinsic - self.premium)
        else:  # underlying: strike == entry price
            per_unit = self.sign * (price - self.strike)
        return per_unit * self.multiplier


def _price_grid(legs: list[PayoffLeg], lo: float | None, hi: float | None,
                steps: int) -> list[float]:
    strikes = [leg.strike for leg in legs] or [0.0]
    smin, smax = min(strikes), max(strikes)
    span = max(smax - smin, smax * 0.5, 1.0)
    lo = max(0.0, smin - span) if lo is None else lo
    hi = (smax + span) if hi is None else hi
    if steps < 2:
        steps = 2
    step = (hi - lo) / (steps - 1)
    return [lo + i * step for i in range(steps)]


def payoff_curve(legs: list[PayoffLeg], prices: list[float] | None = None, *,
                 lo: float | None = None, hi: float | None = None,
                 steps: int = 101) -> list[dict]:
    """P&L at each price. Auto-generates a grid around the strikes if none given."""
    if not legs:
        raise ValueError("need at least one leg")
    grid = prices if prices is not None else _price_grid(legs, lo, hi, steps)
    return [{"price": p, "pnl": sum(leg.pnl_at(p) for leg in legs)} for p in grid]


def _breakevens(curve: list[dict]) -> list[float]:
    bes = []
    for a, b in zip(curve, curve[1:]):
        pa, pb = a["pnl"], b["pnl"]
        if pa == 0.0:
            bes.append(a["price"])
        elif pa * pb < 0.0:                      # sign change → interpolate
            frac = (0.0 - pa) / (pb - pa)
            bes.append(a["price"] + frac * (b["price"] - a["price"]))
    # de-dup near-equal breakevens
    out: list[float] = []
    for x in bes:
        if not out or abs(x - out[-1]) > 1e-9:
            out.append(x)
    return out


def payoff_summary(legs: list[PayoffLeg], *, lo: float | None = None,
                   hi: float | None = None, steps: int = 201) -> dict:
    """Breakevens + max profit/loss + net premium across the scanned band."""
    curve = payoff_curve(legs, lo=lo, hi=hi, steps=steps)
    pnls = [pt["pnl"] for pt in curve]
    max_pt = max(curve, key=lambda c: c["pnl"])
    min_pt = min(curve, key=lambda c: c["pnl"])
    # Net premium: + = net credit received, − = net debit paid.
    net_premium = sum(
        (-leg.sign) * leg.premium * leg.multiplier
        for leg in legs if leg.kind.lower() != "underlying"
    )
    grid_lo, grid_hi = curve[0]["price"], curve[-1]["price"]
    # Bounded ⇔ both end "wings" are flat plateaus (P&L stops changing past the
    # scan edges). A naked/uncovered leg keeps sloping at an edge → unbounded there.
    flat_left = abs(pnls[0] - pnls[1]) <= 1e-9
    flat_right = abs(pnls[-1] - pnls[-2]) <= 1e-9
    return {
        "breakevens": _breakevens(curve),
        "max_profit": max(pnls),
        "max_profit_at": max_pt["price"],
        "max_loss": min(pnls),
        "max_loss_at": min_pt["price"],
        "net_premium": net_premium,
        "credit" if net_premium >= 0 else "debit": abs(net_premium),
        "scanned_range": [grid_lo, grid_hi],
        "bounded_below": flat_left,
        "bounded_above": flat_right,
        "bounded": flat_left and flat_right,
        "curve": curve,
    }
