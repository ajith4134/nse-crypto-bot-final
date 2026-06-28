"""trading/crypto/liquidation.py — liquidation-price estimator (T2).

Pure math (no network) so it is fully unit-testable. Implements the standard
linear-perpetual isolated-margin liquidation price, with a cross-margin variant
that folds extra wallet collateral into the position's effective margin.

These are ESTIMATES — they ignore funding accrual and taker fees-on-close, which
exchanges add to the maintenance requirement. They match exchange values to
within a few ticks for typical leverage; treat as guidance, not a guarantee.

Isolated, linear contract (collateral = position margin only):
    long  liq = entry * (1 - 1/L + mmr)
    short liq = entry * (1 + 1/L - mmr)
where L = leverage, mmr = maintenance-margin rate (fraction).
"""
from __future__ import annotations

from trading.crypto.config import DEFAULT_MMR


def liquidation_price(
    *,
    side: str,
    entry_price: float,
    leverage: float,
    mmr: float = DEFAULT_MMR,
    margin_mode: str = "isolated",
    extra_margin_ratio: float = 0.0,
) -> float:
    """Estimate the liquidation price for a linear-perp position.

    Args:
        side: "long"/"buy" or "short"/"sell".
        entry_price: average entry price (> 0).
        leverage: position leverage (>= 1).
        mmr: maintenance-margin rate as a fraction (e.g. 0.005 = 0.5%).
        margin_mode: "isolated" or "cross".
        extra_margin_ratio: for cross only — extra wallet collateral expressed as a
            fraction of position notional (pushes liquidation further away).

    Returns:
        Liquidation price (>= 0). 0.0 means "not liquidatable on the downside"
        (e.g. a fully-collateralised / 1x long can reach 0 but not be liquidated).
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be > 0")
    if leverage < 1:
        raise ValueError("leverage must be >= 1")
    s = side.lower()
    is_long = s in ("long", "buy", "b")
    is_short = s in ("short", "sell", "s")
    if not (is_long or is_short):
        raise ValueError(f"unknown side: {side!r}")

    # Initial margin ratio + (for cross) extra collateral buffer.
    imr = 1.0 / leverage
    if margin_mode.lower() == "cross":
        imr += max(0.0, extra_margin_ratio)

    if is_long:
        liq = entry_price * (1.0 - imr + mmr)
    else:
        liq = entry_price * (1.0 + imr - mmr)
    return max(0.0, liq)


def distance_to_liquidation(
    *, side: str, mark_price: float, liq_price: float
) -> float:
    """Fraction of mark price between current mark and liquidation (signed-safe).

    Returns a positive fraction (e.g. 0.12 = 12% away). 0 means at/!past liq.
    """
    if mark_price <= 0 or liq_price <= 0:
        return 0.0
    s = side.lower()
    if s in ("long", "buy", "b"):
        return max(0.0, (mark_price - liq_price) / mark_price)
    return max(0.0, (liq_price - mark_price) / mark_price)
