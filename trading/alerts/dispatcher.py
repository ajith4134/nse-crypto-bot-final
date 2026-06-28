"""trading/alerts/dispatcher.py — AlertDispatcher (T7).

The one entry point the engine calls: `dispatch(event, now)`. It runs the event through
the deduplicator, then delivers to every enabled channel, recording an honest audit
trail. Channels are duck-typed (anything with `.name`, `.enabled()`, `.send(event)`),
so the Telegram channel — or a test double — drops in unchanged. Time is injected for
deterministic dedup. No network of its own.
"""
from __future__ import annotations

from trading.alerts.dedup import Deduplicator


class AlertDispatcher:
    def __init__(self, channels: list, deduper: Deduplicator | None = None):
        self.channels = channels
        self.deduper = deduper or Deduplicator()
        self.log: list = []

    def dispatch(self, event, now: float = 0.0) -> dict:
        """Dedup then fan out to enabled channels. Returns a per-channel result dict."""
        if not self.deduper.should_send(event, now):
            entry = {"event": event.dedup_key, "deduped": True, "results": []}
            self.log.append(entry)
            return entry
        results = []
        for ch in self.channels:
            try:
                if not ch.enabled():
                    results.append({"channel": ch.name, "skipped": "disabled"})
                    continue
                results.append({"channel": ch.name, **ch.send(event)})
            except Exception as exc:
                results.append({"channel": getattr(ch, "name", "?"), "ok": False,
                                "detail": f"{type(exc).__name__}: {exc}"})
        entry = {"event": event.dedup_key, "deduped": False, "results": results}
        self.log.append(entry)
        return entry

    def status(self) -> dict:
        return {
            "channels": [c.as_dict() if hasattr(c, "as_dict")
                         else {"name": getattr(c, "name", "?"), "enabled": c.enabled()}
                         for c in self.channels],
            "dedup": self.deduper.as_dict(),
            "dispatched": len(self.log),
            "delivered": sum(1 for e in self.log if not e["deduped"]),
            "deduped": sum(1 for e in self.log if e["deduped"]),
        }
