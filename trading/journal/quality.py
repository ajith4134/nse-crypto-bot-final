"""trading/journal/quality.py — per-trade quality metrics (T5 §5, blueprint Trade Quality Metrics).

Scores a single CLOSED trade on the classic MAE/MFE/R-multiple family plus simple
timing fields. `trade_quality(trade)` returns a dict whose keys are valid `ClosedTrade`
attribute names; `journal.py` does `for k, v in trade_quality(trade).items(): setattr(...)`
so this module is the single source of truth for those derived columns.

Inputs come straight off the `ClosedTrade` record:
  • entry_price / exit_price / quantity / direction
  • initial_sl_price            → R-multiple risk leg
  • mae / mfe (₹/$ excursions, positive; per schema "₹/$ adverse/favourable excursion")
  • entry_datetime / exit_datetime (ISO strings)

Excursion convention (matches schema): `mae` and `mfe` are CURRENCY amounts for the
whole position (best favourable / worst adverse move × quantity, both positive). We
convert to a per-unit price move by dividing by quantity, then place them around the
entry to recover the post-entry price range:

  LONG : high = entry + mfe/qty,  low = entry − mae/qty,  realized = exit − entry
  SHORT: low  = entry − mfe/qty,  high= entry + mae/qty,  realized = entry − exit

Efficiency formulas (documented, both in %):
  • exit_efficiency  = realized_move / mfe_move × 100
        fraction of the favourable run (MFE) that was actually captured at exit.
        100% = exited at the best price; <100% = gave some back; can be negative
        if the trade closed below the entry despite a favourable excursion.
  • entry_efficiency = mfe_move / (mfe_move + mae_move) × 100
        of the total post-entry range the trade travelled, how much was favourable.
        A near-perfect entry (little adverse heat, lots of favourable run) → ~100%;
        an entry that suffered most of the range as drawdown → ~0%.

All math is defensive: any missing/zero leg yields None for the affected metric and
never raises on a sparse trade. Pure, deterministic, offline.
"""
from __future__ import annotations

from datetime import datetime


def r_multiple(net_pnl: float, entry_price: float, stop_price: float,
               quantity: float) -> float | None:
    """R-multiple = net P&L / initial risk, where initial_risk = |entry − stop| × qty.

    Returns None when the stop/qty are missing or the risk leg is zero (no division).
    """
    try:
        initial_risk = abs(float(entry_price) - float(stop_price)) * abs(float(quantity))
    except (TypeError, ValueError):
        return None
    if not initial_risk:
        return None
    return float(net_pnl) / initial_risk


def _parse(dt: str):
    if not dt:
        return None
    try:
        return datetime.fromisoformat(str(dt))
    except (TypeError, ValueError):
        return None


def _hms(seconds: float) -> str:
    secs = int(round(abs(seconds)))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def trade_quality(trade) -> dict:
    """Compute derived quality columns for one ClosedTrade. Returns a dict of
    attribute_name -> value (only keys that were computable are included)."""
    out: dict = {}

    entry = float(getattr(trade, "entry_price", 0) or 0)
    exit_ = float(getattr(trade, "exit_price", 0) or 0)
    qty = abs(float(getattr(trade, "quantity", 0) or 0))
    direction = (getattr(trade, "direction", "") or "").upper()
    is_short = direction == "SHORT"

    # ── R-multiple ───────────────────────────────────────────────────────────────
    sl = getattr(trade, "initial_sl_price", None)
    if sl is not None and entry and qty:
        rm = r_multiple(getattr(trade, "net_pnl", 0.0) or 0.0, entry, sl, qty)
        if rm is not None:
            out["r_multiple"] = rm

    # ── MAE/MFE based metrics ────────────────────────────────────────────────────
    mae = getattr(trade, "mae", None)
    mfe = getattr(trade, "mfe", None)

    if qty and entry:
        mae_move = abs(float(mae)) / qty if mae is not None else None   # price units
        mfe_move = abs(float(mfe)) / qty if mfe is not None else None   # price units

        if mae_move is not None:
            out["mae_pct"] = mae_move / entry * 100.0
        if mfe_move is not None:
            out["mfe_pct"] = mfe_move / entry * 100.0

        realized = (entry - exit_) if is_short else (exit_ - entry)

        # exit efficiency = captured fraction of the favourable run
        if mfe_move:
            out["exit_efficiency"] = realized / mfe_move * 100.0

        # entry efficiency = favourable share of the total post-entry range
        if mae_move is not None and mfe_move is not None:
            rng = mfe_move + mae_move
            if rng:
                out["entry_efficiency"] = mfe_move / rng * 100.0

    # ── timing ───────────────────────────────────────────────────────────────────
    t_in = _parse(getattr(trade, "entry_datetime", ""))
    t_out = _parse(getattr(trade, "exit_datetime", ""))
    if t_in and t_out:
        out["holding_duration"] = _hms((t_out - t_in).total_seconds())
    else:
        out["holding_duration"] = ""

    if t_in:
        out["day_of_week"] = t_in.strftime("%A")
        out["entry_hour"] = t_in.hour

    return out
