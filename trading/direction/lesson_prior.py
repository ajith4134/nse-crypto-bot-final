"""trading/direction/lesson_prior.py — E4: closed-trade lessons distilled into a direction lens.

B2 found the brain writes an LLM lesson on every close and nothing read them; lesson_recall
(2026-07-16) gave the DEBATE a reader, but the debate only runs in the deep lane. This module
gives every lane a reader — as a measured lens, not prompt garnish.

Design constraints it satisfies:
  • No per-candidate LLM calls (the attribution-hotpath scar): distillation runs on the
    LEARNING cadence — one batched LLM call turns each symbol's recent lesson texts into a
    {side_hint, confidence} row, persisted to `lesson_prior.json`; the hot-path lens is an
    O(1) table read.
  • Not a duplicate of experience_recall (the B1 duplicate-lens scar): experience_recall
    aggregates OUTCOME stats; this lens extracts the REASONING in the lesson texts ("shorts
    keep getting squeezed", "entries chase the spike") — signal the stats can't see.
  • CONVENTIONS §16: emitted as truth-ledger source "lessons", weightless until it earns
    edge; a symbol with no distilled lean or a stale row (> LESSON_PRIOR_TTL_S) abstains.

Env: LESSON_PRIOR (1), LESSON_PRIOR_EVERY_S (3600), LESSON_PRIOR_TTL_S (86400),
     LESSON_PRIOR_BATCH (12 symbols per LLM call).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

from trading import state

_TABLE = "lesson_prior.json"


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default) in ("1", "true", "TRUE", "yes", "on")


def enabled() -> bool:
    return _flag("LESSON_PRIOR")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _hash(lessons: list[str]) -> str:
    return hashlib.sha1("\n".join(lessons).encode("utf-8", "replace")).hexdigest()[:12]


_PROMPT = """You read post-trade lessons written after closed crypto trades and extract ONLY
directional guidance per symbol. For each symbol below, decide whether the lessons argue the
NEXT trade should lean long, lean short, or carry no directional lesson.

Rules: base the lean ONLY on the lesson texts (not general market views); "none" is the
correct answer when lessons are about sizing/timing/process rather than direction.
Answer with STRICT JSON, no prose: {"SYMBOL": {"side": "long"|"short"|"none",
"confidence": 0.0-1.0, "why": "<8 words"}, ...}

Lessons:
"""


def distill(max_symbols: int | None = None) -> dict:
    """Batched LLM distillation of fresh lesson texts → the prior table. Skips symbols whose
    lesson set is unchanged (hash match). Returns {distilled, skipped, errors}."""
    if not enabled():
        return {"distilled": 0, "reason": "disabled"}
    try:
        from trading.brain import lesson_recall as _lr
        _lr._seed_once()
        with _lr._LOCK:
            all_lessons = {s: list(v) for s, v in _lr._LESSONS.items() if v}
    except Exception as e:
        return {"distilled": 0, "error": repr(e)}
    if not all_lessons:
        return {"distilled": 0, "reason": "no lessons"}
    table = state.load_json(_TABLE, {}) or {}
    todo = []
    for sym, lessons in all_lessons.items():
        h = _hash(lessons)
        if (table.get(sym) or {}).get("lesson_hash") == h:
            continue
        todo.append((sym, lessons, h))
    cap = int(max_symbols if max_symbols is not None
              else _f("LESSON_PRIOR_BATCH", 12))
    todo = todo[:max(1, cap)]
    if not todo:
        return {"distilled": 0, "reason": "all up to date"}
    prompt = _PROMPT + "\n".join(
        f"{sym}:\n" + "\n".join(f"  - {t[:300]}" for t in lessons)
        for sym, lessons, _ in todo)
    try:
        from core.llm import chat
        raw = chat([{"role": "user", "content": prompt}], max_tokens=700, temperature=0.1)
    except Exception as e:
        return {"distilled": 0, "error": f"llm: {e!r}"}
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {"distilled": 0, "error": "unparseable LLM reply"}
    try:
        parsed = json.loads(m.group(0))
    except ValueError:
        return {"distilled": 0, "error": "bad JSON from LLM"}
    now = time.time()
    n = 0
    for sym, lessons, h in todo:
        row = parsed.get(sym)
        if not isinstance(row, dict):
            continue
        side = str(row.get("side") or "none").lower()
        try:
            conf = min(1.0, max(0.0, float(row.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            conf = 0.0
        # p_up: none → 0.5 (abstain later); lean scaled into a modest band (max ±0.2 —
        # a text lesson is a prior, not a forecast)
        p = 0.5
        if side == "long":
            p = 0.5 + 0.2 * conf
        elif side == "short":
            p = 0.5 - 0.2 * conf
        table[sym] = {"p_up": round(p, 4), "side": side, "confidence": conf,
                      "why": str(row.get("why") or "")[:80],
                      "lesson_hash": h, "ts": now}
        n += 1
    if len(table) > 800:                              # bound the table
        for k in sorted(table, key=lambda k: table[k].get("ts") or 0)[:len(table) - 800]:
            table.pop(k, None)
    state.save_json(_TABLE, table)
    return {"distilled": n, "pending": max(0, len(all_lessons) - len(todo))}


_LAST_DISTILL = [0.0]


def maybe_distill() -> dict | None:
    """Learning-cadence gate (called from the funnel's learn worker)."""
    if not enabled():
        return None
    every = _f("LESSON_PRIOR_EVERY_S", 3600)
    if time.time() - _LAST_DISTILL[0] < every:
        return None
    _LAST_DISTILL[0] = time.time()
    return distill()


def readings(symbol: str, *, segment: str = "futures",
             regime: str | None = None, record: bool = True) -> list[tuple[str, float]]:
    """O(1) hot-path lens: the distilled prior for `symbol` (flat or slashed). Abstains on
    no row / no lean / stale row. Self-records to the truth ledger like every lens."""
    if not enabled():
        return []
    try:
        flat = (symbol or "").replace("/", "").split(":")[0].upper()
        row = (state.load_json(_TABLE, {}) or {}).get(flat)
        if not row:
            return []
        if time.time() - float(row.get("ts") or 0) > _f("LESSON_PRIOR_TTL_S", 86400):
            return []
        p = float(row.get("p_up") or 0.5)
        if abs(p - 0.5) < 1e-6:
            return []
        if record:
            try:
                from trading.direction import truth_ledger as _tl
                _tl.record(symbol=flat, market="CRYPTO", segment=segment or "futures",
                           direction=("LONG" if p >= 0.5 else "SHORT"), source="lessons",
                           confidence=(p if p >= 0.5 else 1.0 - p), regime=regime)
            except Exception:
                pass
        return [("lessons", p)]
    except Exception:
        return []


def status() -> dict:
    table = state.load_json(_TABLE, {}) or {}
    leans = sum(1 for r in table.values() if r.get("side") in ("long", "short"))
    return {"enabled": enabled(), "symbols": len(table), "with_lean": leans}
