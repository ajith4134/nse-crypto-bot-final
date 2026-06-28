"""trading/execution/kill_switch.py — real-money safety kill-switch (T3 §10).

ONE action, maximum safety: cancel every open order, then flatten every open
position. Used as the dashboard's red "PANIC" button and by the circuit breaker
when it trips. The two side-effects (cancel-all, flatten-all) are INJECTED as
callables, so the same switch drives NSE (OpenAlgo), crypto (paper/ccxt), or a
test double — and the module has zero network code of its own.

Guarantees:
  • Cancel BEFORE flatten (so resting orders can't re-fill mid-flatten).
  • Idempotent: a second engage() while already engaged is a no-op that returns the
    original report (you can't double-fire it by mashing the button).
  • Best-effort + honest: if flatten raises, the error is captured in the report and
    `engaged` still latches True — the engine must treat an engaged switch as halted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class KillSwitch:
    """Composable panic switch. `cancel_all`/`flatten_all` return JSON-able reports."""

    cancel_all: Callable[[], object]
    flatten_all: Callable[[], object]
    on_engage: Callable[[str], None] | None = None

    engaged: bool = field(default=False, init=False)
    _report: dict | None = field(default=None, init=False)

    def engage(self, reason: str = "manual") -> dict:
        """Cancel all orders, then flatten all positions. Idempotent."""
        if self.engaged and self._report is not None:
            return {**self._report, "already_engaged": True}

        self.engaged = True             # latch first — never leave it ambiguous
        report: dict = {"engaged": True, "reason": reason, "errors": []}
        try:
            report["cancelled"] = self.cancel_all()
        except Exception as exc:        # capture, keep going to flatten
            report["errors"].append(f"cancel_all: {type(exc).__name__}: {exc}")
            report["cancelled"] = None
        try:
            report["flattened"] = self.flatten_all()
        except Exception as exc:
            report["errors"].append(f"flatten_all: {type(exc).__name__}: {exc}")
            report["flattened"] = None
        report["ok"] = not report["errors"]
        self._report = report
        if self.on_engage:
            try:
                self.on_engage(reason)
            except Exception:           # notification failure must not mask the kill
                pass
        return report

    def reset(self) -> None:
        """Re-arm the switch after a supervised review (does NOT re-open positions)."""
        self.engaged = False
        self._report = None

    def as_dict(self) -> dict:
        return {"engaged": self.engaged, "last_report": self._report}
