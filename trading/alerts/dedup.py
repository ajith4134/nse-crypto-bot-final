"""trading/alerts/dedup.py — smart alert deduplication (T7 §5).

Suppresses repeat alerts for the same logical event within a TTL window, so a flapping
condition (e.g. the circuit breaker re-evaluating every tick) doesn't spam Telegram.
Dedup identity is the event's `dedup_key`. Time is INJECTED (`now` epoch seconds) so
the policy is fully deterministic and unit-testable — no wall-clock, no sleeping.

Policy: an event is allowed if its key hasn't been seen, or the last time it was sent
is older than `ttl_seconds`. Allowing an event records its timestamp. Critical events
can optionally bypass dedup (always delivered).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Deduplicator:
    ttl_seconds: float = 300.0
    always_send_critical: bool = True
    _last_sent: dict = field(default_factory=dict, init=False)
    suppressed: int = field(default=0, init=False)
    allowed: int = field(default=0, init=False)

    def should_send(self, event, now: float) -> bool:
        """Decide + RECORD in one call: True = deliver, False = suppress as duplicate."""
        if self.always_send_critical and getattr(event, "severity", "") == "critical":
            self._last_sent[event.dedup_key] = now
            self.allowed += 1
            return True
        last = self._last_sent.get(event.dedup_key)
        if last is None or (now - last) >= self.ttl_seconds:
            self._last_sent[event.dedup_key] = now
            self.allowed += 1
            return True
        self.suppressed += 1
        return False

    def reset(self) -> None:
        self._last_sent.clear()
        self.suppressed = 0
        self.allowed = 0

    def as_dict(self) -> dict:
        return {"ttl_seconds": self.ttl_seconds, "tracked_keys": len(self._last_sent),
                "allowed": self.allowed, "suppressed": self.suppressed}
