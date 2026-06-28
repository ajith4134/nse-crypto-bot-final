"""trading/execution/margin.py — SEBI SPAN + Exposure margin check (T3 §8).

Indian F&O margin = SPAN margin (portfolio-risk based, from the exchange SPAN file)
+ Exposure margin (a flat % add-on). We CANNOT compute the exact SPAN number here —
that comes from the live SPAN file via the broker/OpenAlgo. What we provide is an
honest, conservative ESTIMATE plus the gate that blocks an order when estimated
required margin exceeds available funds.

For equity intraday (MIS) we use a simple leverage model. Numbers are tunable and
deliberately conservative; the real check should also consult the broker's margin
API when live. These functions are pure and unit-testable.

Defaults reflect typical post-2021 SEBI peak-margin regime:
  • Index/stock futures SPAN ≈ 10–12% of notional, exposure ≈ 3%.
  • Equity intraday leverage ≈ 5x (≈ 20% margin).
"""
from __future__ import annotations

from dataclasses import dataclass

# Conservative default rates (fractions of notional).
DEFAULT_SPAN_RATE = 0.12
DEFAULT_EXPOSURE_RATE = 0.03
DEFAULT_INTRADAY_LEVERAGE = 5.0


@dataclass(frozen=True)
class MarginCheck:
    required: float
    available: float
    ok: bool
    shortfall: float            # 0.0 when ok
    breakdown: dict

    def as_dict(self) -> dict:
        return {
            "required": self.required, "available": self.available, "ok": self.ok,
            "shortfall": self.shortfall, "breakdown": self.breakdown,
            "estimate": True,   # never claim this is the broker's exact SPAN
        }


def nse_fo_margin(notional: float, *, span_rate: float = DEFAULT_SPAN_RATE,
                  exposure_rate: float = DEFAULT_EXPOSURE_RATE) -> dict:
    """Estimate SPAN + Exposure margin for an NSE/NFO futures/options position."""
    if notional < 0:
        raise ValueError("notional must be >= 0")
    span = notional * span_rate
    exposure = notional * exposure_rate
    return {"span": span, "exposure": exposure, "total": span + exposure,
            "span_rate": span_rate, "exposure_rate": exposure_rate, "notional": notional}


def nse_intraday_margin(notional: float, *, leverage: float = DEFAULT_INTRADAY_LEVERAGE) -> dict:
    """Estimate equity intraday (MIS) margin from a simple leverage model."""
    if notional < 0:
        raise ValueError("notional must be >= 0")
    if leverage < 1:
        raise ValueError("leverage must be >= 1")
    total = notional / leverage
    return {"total": total, "leverage": leverage, "notional": notional}


def check_margin(required: float, available: float, *, breakdown: dict | None = None) -> MarginCheck:
    """Gate an order: pass only when available funds cover the required margin."""
    shortfall = max(0.0, required - available)
    return MarginCheck(
        required=required, available=available, ok=shortfall <= 0.0,
        shortfall=shortfall, breakdown=breakdown or {},
    )


def check_fo_order(*, quantity: float, price: float, lot_size: int, available: float,
                   span_rate: float = DEFAULT_SPAN_RATE,
                   exposure_rate: float = DEFAULT_EXPOSURE_RATE) -> MarginCheck:
    """Convenience: estimate F&O margin for `quantity` lots and check it."""
    notional = abs(quantity) * lot_size * price
    bd = nse_fo_margin(notional, span_rate=span_rate, exposure_rate=exposure_rate)
    return check_margin(bd["total"], available, breakdown=bd)
