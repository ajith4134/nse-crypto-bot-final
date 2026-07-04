"""trading/brain/rnd.py — the AUTONOMOUS R&D DRIVE: the brain invents its own new
functions and features to broaden its horizon (operator mandate 2026-07-04).

Interval-gated cycle (default every 2h, RND_SEC override), run from the brain loop after the
learning cycle. Each round the brain:

  1. PICKS a frontier topic — from recent PROBLEMS in the mind stream (fix what hurts),
     the boss's standing goals (serve the mission), or a curiosity list of frontier
     capabilities it does not have yet.
  2. RESEARCHES it online (AutonomousResearcher: ddgs + LLM synthesis).
  3. INVENTS a concrete proposal — a new tradeable hypothesis seeded into the
     HypothesisLedger (tested against real journal outcomes forever after) and, when the
     LLM can express one, a named feature idea recorded in the invention log.
  4. REPORTS the invention in the mind stream + durable memory, so learning that started
     as an invention can later be credited when it helps open/close profitable trades.

Honest wiring: every artifact is real — proposals land in the same ledger the executor's
veto/support reads, research summaries go into KnowledgeBrain, and nothing is emitted
unless the step actually ran.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

from trading.brain import mind_events

_FILE = "rnd_state.json"

CURIOSITY = [
    "volatility regime detection improvements for crypto intraday trading",
    "order flow imbalance features that predict short term price moves",
    "funding rate signals for perpetual futures entries",
    "cross-exchange lead-lag signals crypto",
    "options implied volatility signals for directional trading",
    "position sizing methods beyond fixed fractional kelly",
    "market microstructure features from level 2 order books",
    "news sentiment features for intraday NSE equity trading",
    "overnight gap prediction NSE futures",
    "trade exit optimization trailing methods research",
]


def _load() -> dict:
    from trading import state
    return state.load_json(_FILE, {"last_run": 0.0, "inventions": [], "topic_i": 0})


def _save(d: dict) -> None:
    from trading import state
    d["inventions"] = (d.get("inventions") or [])[-100:]
    state.save_json(_FILE, d)


def _interval() -> float:
    try:
        return max(300.0, float(os.environ.get("RND_SEC", "7200")))
    except Exception:
        return 7200.0


def _pick_topic(d: dict) -> tuple[str, str]:
    """(topic, origin) — problems first, then boss goals, then the curiosity frontier."""
    problems = [e for e in mind_events.peek(60) if e.get("kind") == "problem"]
    if problems and random.random() < 0.5:
        p = problems[0]
        return (f"how to fix in an algorithmic trading system: {p['text']}", "problem")
    try:
        from trading.brain import boss
        goals = [g for g in boss.directives().get("standing_goals", []) if g.get("active")]
        if goals and random.random() < 0.5:
            g = random.choice(goals)
            return (f"techniques to achieve: {g['text']} (algorithmic trading)", "goal")
    except Exception:
        pass
    i = int(d.get("topic_i", 0)) % len(CURIOSITY)
    d["topic_i"] = i + 1
    return (CURIOSITY[i], "curiosity")


_INVENT_SYS = (
    "You are the R&D engine of an autonomous trading brain. From the research summary, "
    "invent ONE concrete, testable improvement. Respond ONLY with JSON: "
    '{"feature_name": "snake_case_name", "description": "1-2 sentences", '
    '"hypothesis": {"field": "<one of: strategy, direction, segment, market_regime_entry, '
    'day_of_week, exchange>", "op": "==", "value": "<value>", '
    '"statement": "trades where <field>==<value> have higher r_multiple"}} — the hypothesis '
    "must be checkable against a trade journal with those exact fields; if none fits, use "
    'null for "hypothesis".')


def _invent_from(topic: str, summary: str) -> dict:
    """LLM step: turn a research summary into a named feature + testable hypothesis."""
    try:
        from core import llm
        if not llm.active_model():
            return {}
        raw = llm.chat([{"role": "system", "content": _INVENT_SYS},
                        {"role": "user", "content": f"Topic: {topic}\n\nResearch:\n{summary[:2500]}"}],
                       max_tokens=300, temperature=0.6)
        j = re.search(r"\{.*\}", raw, re.S)
        return json.loads(j.group(0)) if j else {}
    except Exception:
        return {}


def run_once() -> dict:
    """One full invent cycle (topic → research → propose → seed → report). Never raises."""
    d = _load()
    topic, origin = _pick_topic(d)
    mind_events.emit("invention", f"R&D drive: exploring '{topic[:120]}' (from {origin})",
                     salience=0.6)
    try:
        from trading.brain.researcher import AutonomousResearcher
        res = AutonomousResearcher().research(topic)
    except Exception as e:
        mind_events.emit("problem", f"R&D research failed: {e}", salience=0.5)
        return {"ok": False, "error": str(e)[:200]}
    if not res.get("available"):
        mind_events.emit("problem", f"R&D found no sources for: {topic[:100]}", salience=0.4)
        d["last_run"] = time.time()
        _save(d)
        return {"ok": False, "error": "no sources"}

    idea = _invent_from(topic, res.get("summary") or "")
    inv = {"ts": time.time(), "topic": topic, "origin": origin,
           "n_sources": res.get("n_sources"),
           "feature_name": idea.get("feature_name"),
           "description": idea.get("description"),
           "hypothesis_seeded": False}

    # seed a REAL testable hypothesis into the same ledger the executor consults
    hyp = idea.get("hypothesis")
    if isinstance(hyp, dict) and hyp.get("field") and hyp.get("value") is not None:
        try:
            from trading.brain.hypothesis import Hypothesis, HypothesisLedger
            led = HypothesisLedger(persist=True)
            h = Hypothesis(field=str(hyp["field"]), op=str(hyp.get("op", "==")),
                           value=hyp["value"],
                           statement=str(hyp.get("statement") or
                                         f"R&D: {hyp['field']}=={hyp['value']} improves R"))
            led.hypotheses[h.hid] = h
            led._save()
            inv["hypothesis_seeded"] = True
            inv["hid"] = h.hid
        except Exception:
            pass

    # durable memory: the invention + its research brief
    try:
        from memory.brain import get_brain
        get_brain().ingest_text(f"rnd-invention: {inv.get('feature_name') or topic[:60]}",
                                f"{idea.get('description') or ''}\n\n{res.get('summary')}"[:4000])
    except Exception:
        pass

    d["inventions"] = (d.get("inventions") or []) + [inv]
    d["last_run"] = time.time()
    _save(d)
    name = inv.get("feature_name") or "(research brief only)"
    mind_events.emit(
        "invention",
        f"Invented: {name} — {str(inv.get('description') or topic)[:150]}"
        + (" · hypothesis seeded into ledger, will be tested on real trades"
           if inv["hypothesis_seeded"] else ""),
        detail=(res.get("summary") or "")[:800], salience=0.85, data={"origin": origin})
    return {"ok": True, **inv}


def maybe_run() -> dict | None:
    """Interval-gated entry point for the brain loop. RND_LOOP=0 disables."""
    if os.environ.get("RND_LOOP", "1") in ("0", "false", "no"):
        return None
    d = _load()
    if time.time() - float(d.get("last_run", 0)) < _interval():
        return None
    return run_once()


def status() -> dict:
    d = _load()
    return {"last_run": d.get("last_run"), "interval_sec": _interval(),
            "n_inventions": len(d.get("inventions") or []),
            "recent": list(reversed((d.get("inventions") or [])[-5:]))}
