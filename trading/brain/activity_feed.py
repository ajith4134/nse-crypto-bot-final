"""trading/brain/activity_feed.py — the brain's EPHEMERAL transparency feed (cross-process).

When the autonomous web agent does something the operator should see — "opened angelone.in,
read the BankNifty option chain, learned dealer-gamma is negative" — it appends an event here.
The dashboard shows these as a temporary chat that AUTO-CLEARS once viewed (operator's ask:
"a temporary chat which disappears after I viewed it").

FILE-BACKED (trading/state/activity_feed.json) so the emitter (web agent, which may run in the
brain-loop process) and the reader (dashboard drain) share one feed across processes. Two reads:
  • peek()   — snapshot WITHOUT clearing (live ticker).
  • drain()  — return unviewed events and REMOVE them (the "clears on view" call).
Events older than TTL are dropped even if never viewed, so the feed stays ephemeral.
"""
from __future__ import annotations

import threading
import time

_FILE = "activity_feed.json"
_TTL = 1800.0          # 30 min — ephemeral; unviewed events still expire
_CAP = 200
_lock = threading.Lock()


def _load() -> dict:
    from trading import state
    return state.load_json(_FILE, {"seq": 0, "events": []})


def _save(d: dict) -> None:
    from trading import state
    state.save_json(_FILE, d)


def _expire(events: list) -> list:
    now = time.time()
    return [e for e in events if (now - e.get("ts", 0)) < _TTL][-_CAP:]


def emit(kind: str, title: str, detail: str = "", *, site: str = "",
         learned: str = "", data: dict | None = None) -> dict:
    """Append an ephemeral event. `kind`: opened|read|learned|login_needed|action|note.
    `learned` = a one-line 'what I now know' the operator most wants to see."""
    with _lock:
        d = _load()
        d["seq"] = int(d.get("seq", 0)) + 1
        ev = {"id": d["seq"], "ts": time.time(), "kind": kind, "title": title,
              "detail": detail, "site": site, "learned": learned, "data": data or {},
              "viewed": False}
        d["events"] = _expire(list(d.get("events", [])) + [ev])
        _save(d)
        return dict(ev)


def peek(limit: int = 50) -> list[dict]:
    """Newest-first snapshot WITHOUT clearing."""
    with _lock:
        d = _load()
        return [dict(e) for e in reversed(_expire(d.get("events", []))[-limit:])]


def drain(limit: int = 100) -> list[dict]:
    """Return unviewed events (newest-first) and REMOVE them → they clear from the feed."""
    with _lock:
        d = _load()
        events = _expire(d.get("events", []))
        out = [dict(e) for e in reversed(events) if not e.get("viewed")][:limit]
        seen = {e["id"] for e in out}
        d["events"] = [e for e in events if e["id"] not in seen]
        _save(d)
        return out


def status() -> dict:
    with _lock:
        d = _load()
        events = _expire(d.get("events", []))
        return {"n_unviewed": sum(1 for e in events if not e.get("viewed")),
                "n_total": len(events), "ttl_sec": _TTL}
