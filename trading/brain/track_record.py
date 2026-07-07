"""trading/brain/track_record.py — W7 track records + rule-of-three + meta-articles.

Owner goal 2026-07-07 (video vp4, Dennis Yu RSI): every agent/strategy/scout/optimizer
keeps a RUNNING TRACK RECORD (runs, wins, losses, cost) — "agent A₁ has done this 1,000
times, A₂ 200, A₃ 50" — and writes a META-ARTICLE (self-note) for significant
executions. Trust follows the record, not the code:

  bump()          — increment an actor's record (outcome optional; cost optional).
  rule_of_three() — an actor may auto-scale ONLY after ≥3 SUPERVISED successes
                    ("don't release an agent that does crap"; vp4/vp0's earn-trust).
  meta_note()     — append a meta-article into brain_memory (via trading.brain.ultra)
                    so the definitive record of HOW work is done compounds.
  report_card()   — per-actor summary for the dashboard.

State: track_records.json. Honest: actors with no record report trust "unproven".
"""
from __future__ import annotations

import time

from trading import state

_FILE = "track_records.json"


def _store() -> dict:
    return state.load_json(_FILE, {})


def bump(actor: str, *, kind: str = "run", win: bool | None = None,
         cost_cpu_s: float | None = None, note: str = "") -> dict:
    """One execution for `actor` (strategy name, scout name, optimizer, node…)."""
    d = _store()
    r = d.setdefault(actor, {"runs": 0, "wins": 0, "losses": 0,
                             "supervised_ok": 0, "cost_cpu_s": 0.0,
                             "first_ts": time.time(), "last_ts": None,
                             "kind": kind})
    r["runs"] += 1
    if win is True:
        r["wins"] += 1
    elif win is False:
        r["losses"] += 1
    if cost_cpu_s:
        r["cost_cpu_s"] = round(r["cost_cpu_s"] + float(cost_cpu_s), 2)
    r["last_ts"] = time.time()
    if note:
        r["last_note"] = note[:160]
    state.save_json(_FILE, d)
    return r


def mark_supervised_success(actor: str) -> dict:
    """A human (or the review gate) confirmed one run was good — rule-of-three input."""
    d = _store()
    r = d.setdefault(actor, {"runs": 0, "wins": 0, "losses": 0,
                             "supervised_ok": 0, "cost_cpu_s": 0.0,
                             "first_ts": time.time(), "last_ts": time.time(),
                             "kind": "run"})
    r["supervised_ok"] += 1
    state.save_json(_FILE, d)
    return r


def rule_of_three(actor: str) -> dict:
    """May this actor auto-scale? Only after ≥3 supervised successes (vp4)."""
    r = _store().get(actor) or {}
    ok = (r.get("supervised_ok", 0) >= 3)
    return {"actor": actor, "allowed": ok,
            "supervised_ok": r.get("supervised_ok", 0),
            "reason": ("proven (3+ supervised successes)" if ok else
                       f"needs {3 - r.get('supervised_ok', 0)} more supervised successes")}


def trust(actor: str) -> dict:
    """Trust weight from the record: unproven <10 runs; then win-rate-shaded [0.5,1.5]."""
    r = _store().get(actor) or {}
    n = r.get("runs", 0)
    decided = r.get("wins", 0) + r.get("losses", 0)
    if n < 10 or decided < 5:
        return {"actor": actor, "trust": 1.0, "label": "unproven", "runs": n}
    wr = r["wins"] / decided
    return {"actor": actor, "trust": round(0.5 + wr, 3),
            "label": "proven" if n >= 100 else "developing",
            "runs": n, "win_rate": round(wr, 4)}


def meta_note(actor: str, *, what: str, why: str = "", edge_case: str = "",
              cost: str = "") -> bool:
    """The vp4 meta-article: after doing something, the agent writes down what it did,
    why, edge cases hit, and what it cost.

    HOT-PATH SAFE: appends to a lightweight queue (meta_articles.json) — it must NEVER
    boot the associative-memory stack synchronously (ultra.remember loads embedding
    models; doing that inside a knob-write stalled a test run for minutes). The
    continuous-learning daemon drains the queue into brain_memory via
    drain_meta_queue()."""
    try:
        r = _store().get(actor) or {}
        q = state.load_json("meta_articles.json", [])
        q.append({"ts": time.time(), "actor": actor, "what": what[:300],
                  "why": why[:300], "edge_case": edge_case[:200], "cost": cost[:120],
                  "record": f"{r.get('runs', 0)} runs "
                            f"{r.get('wins', 0)}W/{r.get('losses', 0)}L"})
        state.save_json("meta_articles.json", q[-1000:])
        return True
    except Exception:
        return False


def drain_meta_queue(max_items: int = 20) -> int:
    """Move queued meta-articles into brain_memory (called from the learning daemon,
    where booting the memory stack is expected). Returns how many were written."""
    q = state.load_json("meta_articles.json", [])
    if not q:
        return 0
    n = 0
    try:
        from trading.brain import ultra
        for item in q[:max_items]:
            body = (f"**What:** {item['what']}\n**Why:** {item.get('why', '')}\n"
                    f"**Edge case:** {item.get('edge_case', '')}\n"
                    f"**Cost:** {item.get('cost', '')}\n"
                    f"**Track record then:** {item.get('record', '')}\n")
            ultra.remember(f"meta-{item['actor']}-{int(item['ts'])}",
                           f"meta-article: {item['actor']} — {item['what'][:60]}",
                           body, type="meta")
            n += 1
        state.save_json("meta_articles.json", q[n:])
    except Exception:
        pass
    return n


def report_card() -> dict:
    d = _store()
    rows = []
    for actor, r in sorted(d.items(), key=lambda kv: -kv[1].get("runs", 0)):
        decided = r.get("wins", 0) + r.get("losses", 0)
        rows.append({"actor": actor, "kind": r.get("kind"), "runs": r.get("runs", 0),
                     "wins": r.get("wins", 0), "losses": r.get("losses", 0),
                     "win_rate": round(r["wins"] / decided, 4) if decided else None,
                     "supervised_ok": r.get("supervised_ok", 0),
                     "rule_of_three": r.get("supervised_ok", 0) >= 3,
                     "trust": trust(actor)["trust"],
                     "cost_cpu_s": r.get("cost_cpu_s", 0.0),
                     "last_note": r.get("last_note")})
    return {"actors": rows, "n": len(rows)}
