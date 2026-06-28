"""trading/squareoff.py — exchange auto-squareoff rule engine (T1 §8).

Indian brokers force-close intraday positions at fixed IST times per exchange
(NSE/BSE/NFO 15:15, CDS 16:45, MCX 23:30). We mirror those deadlines so our
system squares off slightly BEFORE the broker does, avoiding broker auto-squareoff
charges and slippage.

This module is pure scheduling logic (no orders): it tells you, for a given IST
'now', which exchanges are at/over their squareoff deadline. The execution engine
(T3) consumes these decisions to flatten positions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from trading.config import SQUAREOFF_TIMES_IST, TradingConfig, trading_config

IST = timezone(timedelta(hours=5, minutes=30))

# Square off this many minutes BEFORE the broker's hard deadline.
SAFETY_LEAD_MINUTES = 1


@dataclass(frozen=True)
class SquareoffRule:
    exchange: str
    deadline: time          # IST deadline (broker hard squareoff)
    action_time: time       # when WE act (deadline - safety lead)


def _parse(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def _minus_minutes(t: time, minutes: int) -> time:
    base = datetime(2000, 1, 1, t.hour, t.minute, tzinfo=IST)
    return (base - timedelta(minutes=minutes)).timetz().replace(tzinfo=None)


def build_rules(config: TradingConfig | None = None) -> dict[str, SquareoffRule]:
    cfg = config or trading_config
    times = cfg.squareoff_times or SQUAREOFF_TIMES_IST
    rules: dict[str, SquareoffRule] = {}
    for exch, hhmm in times.items():
        deadline = _parse(hhmm)
        rules[exch] = SquareoffRule(
            exchange=exch,
            deadline=deadline,
            action_time=_minus_minutes(deadline, SAFETY_LEAD_MINUTES),
        )
    return rules


def now_ist() -> datetime:
    return datetime.now(IST)


def due_exchanges(when: datetime | None = None, config: TradingConfig | None = None) -> list[str]:
    """Exchanges whose squareoff action_time has been reached at `when` (IST).

    `when` must be timezone-aware; defaults to now in IST.
    """
    when = when or now_ist()
    if when.tzinfo is None:
        when = when.replace(tzinfo=IST)
    when_ist = when.astimezone(IST).timetz().replace(tzinfo=None)
    due = []
    for exch, rule in build_rules(config).items():
        if when_ist >= rule.action_time:
            due.append(exch)
    return due


def is_squareoff_due(exchange: str, when: datetime | None = None,
                     config: TradingConfig | None = None) -> bool:
    return exchange.upper() in due_exchanges(when, config)


def next_squareoff(exchange: str, config: TradingConfig | None = None) -> time | None:
    rule = build_rules(config).get(exchange.upper())
    return rule.action_time if rule else None


if __name__ == "__main__":
    n = now_ist()
    print(f"IST now: {n.strftime('%H:%M:%S')}")
    for exch, rule in build_rules().items():
        flag = "DUE" if is_squareoff_due(exch, n) else "—"
        print(f"  {exch:6s} deadline {rule.deadline.strftime('%H:%M')} "
              f"act {rule.action_time.strftime('%H:%M')}  [{flag}]")
