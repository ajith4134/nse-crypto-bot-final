"""trading/brain/instructions.py — the instruction lifecycle: follow, grade, edit,
mutate, crossover, merge, spawn, retire (Brain Ultra Upgrade R7–R9, R26).

Instructions are neurons (kind="instruction") in memory/neurons.py — this module is the
brain's hands on its own knowledge. Lifecycle (GOAL.md Pillar 4):

  acquire → FOLLOW (parse steps + verification) → GRADE (outcome evidence updates the
  neuron's stats/confidence, failures append a trace) → EDIT (reflective rewrite from
  the traces) → MUTATE / CROSSOVER / MERGE / SPAWN (GEPA-style reflective evolution —
  targeted semantic changes derived from real failure traces, never random) → RETIRE
  (loser demoted, reason preserved as a lesson neuron — negative knowledge is knowledge).

A Pareto archive keeps diverse working variants (never converge to one winner). LLM
mutations go through core.llm.chat (12-provider failover, local free floor); when no LLM
is reachable the DETERMINISTIC fallback still produces a real, trace-derived semantic
mutation: the most frequent failure reason becomes a guard step. Nothing here fabricates
data — every edit/mutation is grounded in recorded traces.

Failure traces persist in trading/state/instruction_traces.json (isolate in tests by
monkeypatching trading.state.STATE_DIR).
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter

from memory.neurons import Neuron, NeuronStore, get_store
from trading import state

TRACES_FILE = "instruction_traces.json"
MAX_TRACES_PER_INSTRUCTION = 30

_STEP = re.compile(r"^\s*(?:\d+[).]|[-*•])\s*(.+)$")


def _default_llm(prompt: str) -> str | None:
    try:
        from core.llm import chat
        return chat([{"role": "user", "content": prompt}], max_tokens=700,
                    temperature=0.4)
    except Exception:
        return None                                   # honest: caller falls back


def parse_steps(text: str) -> list[str]:
    """Numbered/bulleted lines become executable steps; falls back to sentences."""
    steps = [m.group(1).strip() for ln in str(text).splitlines()
             if (m := _STEP.match(ln))]
    if steps:
        return steps
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", str(text)) if s.strip()][:12]


class InstructionEngine:
    """Follow/grade/evolve instruction neurons. One engine per process is plenty."""

    def __init__(self, store: NeuronStore | None = None, llm=None):
        self.store = store or get_store()
        self.llm = llm or _default_llm

    # ── FOLLOW (R7): executable view of an instruction neuron ─────────────────
    def follow(self, nid: str) -> dict | None:
        n = self.store.get(nid)
        if n is None or n.kind != "instruction":
            return None
        if n.stats.get("retired"):
            return {"id": n.id, "retired": True, "steps": [],
                    "note": "retired — use a live variant from the archive"}
        steps = parse_steps(n.body)
        verify = [s for s in parse_steps(n.action) if "verify" in s.lower()] or \
                 parse_steps(n.action)[-1:]
        return {"id": n.id, "title": n.title, "version": n.version, "steps": steps,
                "verify": verify, "action": n.action, "confidence": n.confidence}

    # ── GRADE (R7): outcome evidence + failure traces ──────────────────────────
    def grade(self, nid: str, *, success: bool, pnl: float = 0.0, domain: str = "",
              failure_reason: str = "", now: float | None = None) -> dict | None:
        n = self.store.record_use(nid, win=success, pnl=pnl, domain=domain, now=now)
        if n is None:
            return None
        if not success and failure_reason.strip():
            def _append(d):
                d = d or {}
                traces = d.setdefault(nid, [])
                traces.append({"ts": time.time() if now is None else now,
                               "reason": failure_reason.strip()[:400],
                               "domain": domain})
                d[nid] = traces[-MAX_TRACES_PER_INSTRUCTION:]
                return d
            state.mutate_json(TRACES_FILE, _append, default={})
        return {"id": n.id, "confidence": n.confidence, "stats": n.stats}

    def traces(self, nid: str) -> list[dict]:
        return (state.load_json(TRACES_FILE, {}) or {}).get(nid, [])

    # ── EDIT (R8): reflective rewrite grounded in traces ───────────────────────
    def edit(self, nid: str, *, feedback: str = "", now: float | None = None) -> Neuron | None:
        n = self.store.get(nid)
        if n is None:
            return None
        traces = self.traces(nid)
        reasons = [t["reason"] for t in traces[-8:]]
        if feedback.strip():
            reasons.append(feedback.strip())
        if not reasons:
            return None                               # nothing real to edit from
        prompt = (
            "You maintain executable instructions for a trading brain. Rewrite this "
            "instruction to fix the recorded failures. Keep it stepwise (numbered), "
            "keep what works, change only what the failures implicate. Return JSON "
            '{"title": str, "body": str (numbered steps), "action": str (when to use '
            '+ how to verify)}.\n'
            f"CURRENT TITLE: {n.title}\nCURRENT STEPS:\n{n.body}\n"
            f"WHEN/VERIFY: {n.action}\nRECORDED FAILURES:\n- " + "\n- ".join(reasons))
        out = self._llm_json(prompt)
        if out:
            child = self.store.derive([nid], title=out["title"][:200], body=out["body"],
                                      action=out["action"], now=now)
        else:                                         # deterministic trace-derived edit
            guard = Counter(r.lower()[:120] for r in reasons).most_common(1)[0][0]
            child = self.store.derive(
                [nid], title=f"{n.title} (guarded)"[:200],
                body=f"{n.body}\n{len(parse_steps(n.body)) + 1}) Guard: before "
                     f"finishing, check the known failure — {guard}",
                action=f"{n.action} Abort if the guard condition appears: {guard}.",
                now=now)
        return child

    # ── MUTATE (R9): reflective semantic mutation (GEPA-style) ────────────────
    def mutate(self, nid: str, *, now: float | None = None) -> Neuron | None:
        n = self.store.get(nid)
        if n is None:
            return None
        traces = self.traces(nid)
        prompt = (
            "Propose ONE targeted semantic mutation of this instruction that could "
            "outperform it (change strategy of approach, reorder, tighten a threshold, "
            "add a precondition). Ground it in the failure traces when present; if none, "
            "strengthen its weakest step. Return JSON "
            '{"title": str, "body": str (numbered steps), "action": str, '
            '"rationale": str}.\n'
            f"TITLE: {n.title}\nSTEPS:\n{n.body}\nWHEN/VERIFY: {n.action}\n"
            f"WIN/LOSS: {n.stats.get('wins', 0)}/{n.stats.get('losses', 0)}\n"
            "FAILURES:\n- " + ("\n- ".join(t["reason"] for t in traces[-6:]) or "(none)"))
        out = self._llm_json(prompt)
        if out:
            return self.store.derive([nid], title=out["title"][:200], body=out["body"],
                                     action=out["action"], now=now)
        if traces:                                    # deterministic: guard-step mutation
            return self.edit(nid, now=now)
        return None                                   # no LLM + no traces → no honest mutation

    # ── CROSSOVER / MERGE (R26) ────────────────────────────────────────────────
    def crossover(self, nid_a: str, nid_b: str, *, now: float | None = None) -> Neuron | None:
        a, b = self.store.get(nid_a), self.store.get(nid_b)
        if a is None or b is None:
            return None
        prompt = (
            "Splice the best parts of these two working instructions into ONE stronger "
            'instruction. Return JSON {"title": str, "body": str (numbered steps), '
            '"action": str}.\n'
            f"A ({a.stats.get('wins', 0)}W/{a.stats.get('losses', 0)}L): {a.title}\n"
            f"{a.body}\n---\n"
            f"B ({b.stats.get('wins', 0)}W/{b.stats.get('losses', 0)}L): {b.title}\n{b.body}")
        out = self._llm_json(prompt)
        if out:
            return self.store.derive([nid_a, nid_b], title=out["title"][:200],
                                     body=out["body"], action=out["action"],
                                     rel="crossover-of", now=now)
        # deterministic splice: A's steps + B's steps A lacks, verify from the stronger
        sa, sb = parse_steps(a.body), parse_steps(b.body)
        seen = {s.lower() for s in sa}
        merged = sa + [s for s in sb if s.lower() not in seen]
        stronger = a if a.confidence >= b.confidence else b
        return self.store.derive(
            [nid_a, nid_b], title=f"{a.title} × {b.title}"[:200],
            body="\n".join(f"{i + 1}) {s}" for i, s in enumerate(merged)),
            action=stronger.action, rel="crossover-of", now=now)

    merge = crossover                                 # merge = crossover of near-twins

    # ── SPAWN (R26): sibling for a new context ─────────────────────────────────
    def spawn(self, nid: str, context: str, *, now: float | None = None) -> Neuron | None:
        n = self.store.get(nid)
        if n is None or not context.strip():
            return None
        prompt = (
            f"Adapt this instruction to a NEW context: {context.strip()[:200]}. Keep the "
            'proven structure, change only context-specific parts. Return JSON '
            '{"title": str, "body": str (numbered steps), "action": str}.\n'
            f"TITLE: {n.title}\nSTEPS:\n{n.body}\nWHEN/VERIFY: {n.action}")
        out = self._llm_json(prompt)
        if out:
            return self.store.derive([nid], title=out["title"][:200], body=out["body"],
                                     action=out["action"], now=now)
        return self.store.derive(
            [nid], title=f"{n.title} [for {context.strip()[:60]}]"[:200], body=n.body,
            action=f"{n.action} Context: adapted for {context.strip()[:120]} — verify "
                   f"each step still matches this context before trusting it.", now=now)

    # ── RETIRE (R26): demote, keep the reason as knowledge ─────────────────────
    def retire(self, nid: str, reason: str, *, now: float | None = None) -> dict | None:
        n = self.store.get(nid)
        if n is None:
            return None
        ts = time.time() if now is None else now
        with self.store._lock:                        # _persist only under the store lock
            n.stats["retired"] = True
            n.updated = ts
            self.store._persist(n)
        lesson = self.store.add(
            "lesson", f"RETIRED: {n.title}"[:200],
            f"Instruction {n.id} v{n.version} retired. Reason: {reason.strip()[:400]}. "
            f"Record: {n.stats.get('wins', 0)}W/{n.stats.get('losses', 0)}L "
            f"pnl={n.stats.get('pnl', 0.0):.2f}.",
            f"Do not resurrect {n.id} as-is; if this approach resurfaces, address the "
            f"retirement reason first: {reason.strip()[:200]}",
            origin="evolution", ref=n.id, now=ts, auto_link=False)
        self.store.link(lesson.id, nid, "derived-from", now=ts)
        return {"retired": nid, "lesson": lesson.id}

    # ── Pareto archive: diverse working variants (R9/R26) ─────────────────────
    def pareto_archive(self, *, k: int = 20) -> list[dict]:
        """Non-dominated live instructions by (confidence, times_used)."""
        live = [n for n in self.store.all_neurons()
                if n.kind == "instruction" and not n.stats.get("retired")]
        front = []
        for n in live:
            dominated = any(
                o.confidence >= n.confidence
                and o.stats.get("times_used", 0) >= n.stats.get("times_used", 0)
                and (o.confidence > n.confidence
                     or o.stats.get("times_used", 0) > n.stats.get("times_used", 0))
                for o in live if o.id != n.id)
            if not dominated:
                front.append(n)
        front.sort(key=lambda x: (x.confidence, x.stats.get("times_used", 0)),
                   reverse=True)
        return [{"id": n.id, "title": n.title, "version": n.version,
                 "confidence": n.confidence, "used": n.stats.get("times_used", 0),
                 "wins": n.stats.get("wins", 0), "losses": n.stats.get("losses", 0)}
                for n in front[:k]]

    def status(self) -> dict:
        instr = [n for n in self.store.all_neurons() if n.kind == "instruction"]
        retired = sum(1 for n in instr if n.stats.get("retired"))
        evolved = sum(1 for n in instr if n.parents)
        return {"instructions": len(instr), "retired": retired, "evolved": evolved,
                "pareto_front": len(self.pareto_archive(k=100)),
                "traced": len(state.load_json(TRACES_FILE, {}) or {})}

    # ── helpers ────────────────────────────────────────────────────────────────
    def _llm_json(self, prompt: str) -> dict | None:
        reply = self.llm(prompt)
        if not reply:
            return None
        m = re.search(r"\{.*\}", reply, re.S)
        if not m:
            return None
        try:
            out = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        if all(isinstance(out.get(k), str) and out[k].strip()
               for k in ("title", "body", "action")):
            return out
        return None
