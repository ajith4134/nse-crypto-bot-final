"""Per-symbol recall of closed-trade LESSONS — the reader exit reflections never had.

B2 (2026-07-16) measured that every close writes an LLM lesson (journal fields
``exit_reflection`` / ``lesson_learned``) and nothing anywhere read them back. This module is
the consumer: an in-RAM per-symbol ring of the most recent lesson texts, surfaced into the
debate gate's context on the money path (brain_executor deep lane), so the room argues WITH
the memory of how trades on this symbol actually ended.

Cost discipline (the TradeJournal-reload-per-entry scar, commit 6f75790): ONE bounded scan of
the journal tail at first use, then O(1) ``note()`` updates from the close path — never a
journal reload on the hot path.
"""
from __future__ import annotations

import threading
import time

_LOCK = threading.RLock()
_MAX_PER_SYMBOL = 3
_SCAN_TAIL_ROWS = 2000
_LESSONS: dict[str, list[str]] = {}
_SEEDED = False


def _seed_once() -> None:
    global _SEEDED
    if _SEEDED:
        return
    with _LOCK:
        if _SEEDED:
            return
        _SEEDED = True
        try:
            from trading import state
            journal = state.load_json("journal.json", None)
            rows = journal if isinstance(journal, list) else (journal or {}).get("trades", [])
            for r in list(rows)[-_SCAN_TAIL_ROWS:]:
                txt = r.get("exit_reflection") or r.get("lesson_learned")
                sym = r.get("symbol")
                if txt and sym:
                    _LESSONS.setdefault(str(sym), []).append(str(txt).strip())
            for sym in _LESSONS:
                _LESSONS[sym] = _LESSONS[sym][-_MAX_PER_SYMBOL:]
        except Exception:
            pass


def note(symbol: str, lesson: str | None) -> None:
    """O(1) close-path hook: remember this symbol's newest lesson. Never raises."""
    if not lesson or not symbol:
        return
    try:
        with _LOCK:
            ring = _LESSONS.setdefault(str(symbol), [])
            ring.append(str(lesson).strip())
            del ring[:-_MAX_PER_SYMBOL]
    except Exception:
        pass


def recent(symbol: str, k: int = 2) -> list[str]:
    """The k most recent lessons for this symbol (newest last). Never raises."""
    try:
        _seed_once()
        with _LOCK:
            return list(_LESSONS.get(str(symbol), []))[-max(1, int(k)):]
    except Exception:
        return []
