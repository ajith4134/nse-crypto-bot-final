"""trading/alerts/scheduler.py — scheduled reports (T7 §3, §4).

Decides WHEN daily / weekly reports are due and runs their callbacks. Deterministic and
offline-testable: there is NO background thread or sleeping — the caller pumps it with
`run_due(now)` (epoch seconds, e.g. once a minute from the live loop), and the scheduler
fires any report whose scheduled time has passed since it last ran. A report callback
typically builds a tearsheet and dispatches it to Telegram.

Cadence:
  • daily  — fires at/after `at_hour` (UTC) each day.
  • weekly — fires at/after `at_hour` on `weekday` (0=Mon) each week.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable


@dataclass
class Report:
    name: str
    cadence: str                 # "daily" | "weekly"
    callback: Callable[[], object]
    at_hour: int = 18            # UTC hour to fire
    weekday: int = 0             # for weekly: 0=Mon
    last_run_day: str = ""       # ISO date string of last fire (dedup within a day)


@dataclass
class ReportScheduler:
    reports: dict = field(default_factory=dict, init=False)
    log: list = field(default_factory=list, init=False)

    def add(self, name: str, cadence: str, callback: Callable[[], object], *,
            at_hour: int = 18, weekday: int = 0) -> "ReportScheduler":
        if cadence not in ("daily", "weekly"):
            raise ValueError("cadence must be 'daily' or 'weekly'")
        self.reports[name] = Report(name, cadence, callback, at_hour, weekday)
        return self

    @staticmethod
    def _dt(now: float) -> datetime:
        return datetime.fromtimestamp(now, tz=timezone.utc)

    def _is_due(self, r: Report, now: float) -> bool:
        dt = self._dt(now)
        today = dt.date().isoformat()
        if r.last_run_day == today:
            return False                      # already ran today
        if dt.hour < r.at_hour:
            return False                      # too early in the day
        if r.cadence == "weekly" and dt.weekday() != r.weekday:
            return False
        return True

    def due(self, now: float) -> list[str]:
        return [name for name, r in self.reports.items() if self._is_due(r, now)]

    def run_due(self, now: float) -> list[dict]:
        """Fire every due report's callback once; record + return the results."""
        fired = []
        dt_today = self._dt(now).date().isoformat()
        for name in self.due(now):
            r = self.reports[name]
            try:
                result = r.callback()
                entry = {"report": name, "ok": True, "result": result, "day": dt_today}
            except Exception as exc:
                entry = {"report": name, "ok": False,
                         "error": f"{type(exc).__name__}: {exc}", "day": dt_today}
            r.last_run_day = dt_today
            self.log.append(entry)
            fired.append(entry)
        return fired

    def status(self) -> dict:
        return {
            "reports": [{"name": r.name, "cadence": r.cadence, "at_hour": r.at_hour,
                         "weekday": r.weekday, "last_run_day": r.last_run_day}
                        for r in self.reports.values()],
            "fired": len(self.log),
        }
