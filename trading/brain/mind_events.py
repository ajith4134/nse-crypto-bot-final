"""trading/brain/mind_events.py — the brain-wide ULTRA event bus behind Stream of Mind.

Every subsystem that lives the brain's real life — the trading loops, the hypothesis ledger,
decision-memory reflections, the online researcher, the learning cycle, the R&D/invention drive
and the boss command engine — emits typed events here. The dashboard's Stream of Mind panel
polls them (GET /api/brain/mind/events) and renders them categorized, alongside the AG-UI
think-cycle stream. Honest wiring: an event is only ever emitted at the real code site where
the thing actually happened.

Pattern adapted from trading/brain/activity_feed.py (same atomic state-file ring buffer),
kept separate so the web-agent feed stays ephemeral while this is the durable mind stream.

Kinds (each gets its own color/icon in the panel):
  problem       — something is wrong in the loop (errors, gate blocks piling up, no data)
  discovery     — the brain found an edge (confirmed hypothesis, foundry winner, concept)
  trade_credit  — which learning/strategy helped open or close a (profitable) trade
  research      — it went online to learn something (need → search → finding)
  directive     — boss-command progress ("target 50 open futures → 23 open")
  learning      — a learning cycle ran (hypotheses tested, lessons written)
  invention     — the R&D drive invented/proposed a brand-new function or feature
  boss          — a boss command was received/executed
"""
from __future__ import annotations

import threading
import time

_FILE = "mind_events.json"
_TTL = 6 * 3600.0        # keep the mind stream for 6h — a working shift, not forever
_CAP = 500
_lock = threading.Lock()

KINDS = ("problem", "discovery", "trade_credit", "research", "directive",
         "learning", "invention", "boss", "thought")


def _load() -> dict:
    from trading import state
    return state.load_json(_FILE, {"seq": 0, "events": []})


def _save(d: dict) -> None:
    from trading import state
    state.save_json(_FILE, d)


def _expire(events: list) -> list:
    now = time.time()
    return [e for e in events if (now - e.get("ts", 0)) < _TTL][-_CAP:]


def emit(kind: str, text: str, *, detail: str = "", salience: float = 0.5,
         data: dict | None = None) -> dict:
    """Append one mind event. `text` is the one-liner the operator reads; `detail` is the
    longer honest context; `salience` ∈ [0,1] drives glow in the panel."""
    kind = kind if kind in KINDS else "thought"
    with _lock:
        d = _load()
        d["seq"] = int(d.get("seq", 0)) + 1
        ev = {"id": d["seq"], "ts": time.time(), "kind": kind,
              "text": str(text)[:300], "detail": str(detail)[:800],
              "salience": float(max(0.0, min(1.0, salience))), "data": data or {}}
        d["events"] = _expire(list(d.get("events", [])) + [ev])
        _save(d)
        return dict(ev)


def since(last_id: int = 0, limit: int = 120) -> list[dict]:
    """Events with id > last_id, oldest-first (the panel's incremental poll)."""
    with _lock:
        d = _load()
        events = _expire(d.get("events", []))
        return [dict(e) for e in events if e.get("id", 0) > int(last_id)][:limit]


def peek(limit: int = 80) -> list[dict]:
    """Newest-first snapshot."""
    with _lock:
        d = _load()
        return [dict(e) for e in reversed(_expire(d.get("events", []))[-limit:])]


def status() -> dict:
    with _lock:
        d = _load()
        events = _expire(d.get("events", []))
        by = {}
        for e in events:
            by[e.get("kind", "?")] = by.get(e.get("kind", "?"), 0) + 1
        return {"n": len(events), "last_id": int(d.get("seq", 0)), "by_kind": by}
