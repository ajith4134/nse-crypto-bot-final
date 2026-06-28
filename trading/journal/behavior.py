"""trading/journal/behavior.py — behavioural trade screening (T5 §T5.8).

Pure, deterministic, offline screening of *behavioural* mistakes on a list of
closed trades:

  * revenge trading — re-entering quickly after taking a loss (account-wide,
    emotional chasing), and
  * overtrading — placing more trades on a calendar day than the configured
    daily limit.

`screen_behavior` mutates each ClosedTrade's `revenge_trade_flag` /
`overtrading_flag` IN PLACE (the journal relies on this side effect) and returns
a small summary dict. Every helper tolerates missing/blank ISO timestamps —
behaviour screening must never raise on partial data.
"""
from __future__ import annotations

from datetime import datetime


def _parse_dt(value) -> datetime | None:
    """Best-effort ISO parse; returns None for blank/invalid input (never raises)."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def flag_revenge_trade(trade, prior_trades, window_minutes: int = 5) -> bool:
    """True if `trade` was ENTERED within `window_minutes` after the EXIT of a
    LOSING prior trade (net_pnl < 0).

    Revenge trading is account-wide, so the symbol need not match (a loss on one
    symbol can trigger emotional chasing on another). Missing timestamps on the
    candidate trade or on every prior loss -> False.
    """
    entry = _parse_dt(getattr(trade, "entry_datetime", ""))
    if entry is None:
        return False
    window_sec = window_minutes * 60.0
    for prior in prior_trades:
        if prior is trade:
            continue
        if (getattr(prior, "net_pnl", 0.0) or 0.0) >= 0:
            continue  # only losing trades provoke revenge
        prior_exit = _parse_dt(getattr(prior, "exit_datetime", ""))
        if prior_exit is None:
            continue
        delta = (entry - prior_exit).total_seconds()
        if 0.0 <= delta <= window_sec:
            return True
    return False


def flag_overtrading(day_trade_count: int, daily_limit: int) -> bool:
    """True once the running count of trades on a calendar day exceeds the limit."""
    return day_trade_count > daily_limit


def screen_behavior(trades, *, daily_limit: int = 10,
                    revenge_window_min: int = 5) -> dict:
    """Screen a list of closed trades in time order, mutating flags in place.

    For each trade we set:
      * ``revenge_trade_flag`` — entered within ``revenge_window_min`` of a prior
        losing trade's exit (see :func:`flag_revenge_trade`).
      * ``overtrading_flag`` — the Nth+ trade on a given calendar day beyond
        ``daily_limit`` (grouped by ``entry_datetime`` date).

    Trades with unparseable entry timestamps are ordered last (their relative
    order is preserved) and never counted toward a day's overtrading tally.

    Returns ``{revenge_count, overtrading_count, flagged_trade_ids: [...]}``.
    """
    # Stable sort by entry time; trades without a parseable entry sink to the end.
    indexed = list(enumerate(trades))
    indexed.sort(key=lambda it: (
        _parse_dt(getattr(it[1], "entry_datetime", "")) or datetime.max,
        it[0],
    ))
    ordered = [t for _, t in indexed]

    per_day: dict = {}
    revenge_count = 0
    overtrading_count = 0
    flagged_ids: list = []

    for i, trade in enumerate(ordered):
        prior = ordered[:i]

        # revenge: against everything seen so far
        is_revenge = flag_revenge_trade(trade, prior, window_minutes=revenge_window_min)
        trade.revenge_trade_flag = is_revenge

        # overtrading: count per calendar day, flag beyond the limit
        entry = _parse_dt(getattr(trade, "entry_datetime", ""))
        is_over = False
        if entry is not None:
            day = entry.date()
            per_day[day] = per_day.get(day, 0) + 1
            is_over = flag_overtrading(per_day[day], daily_limit)
        trade.overtrading_flag = is_over

        if is_revenge:
            revenge_count += 1
        if is_over:
            overtrading_count += 1
        if is_revenge or is_over:
            flagged_ids.append(getattr(trade, "trade_id", "") or "")

    return {
        "revenge_count": revenge_count,
        "overtrading_count": overtrading_count,
        "flagged_trade_ids": flagged_ids,
    }
