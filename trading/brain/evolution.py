"""trading/brain/evolution.py — the instruction EVOLUTION loop (R8/R9/R26).

Turns the InstructionEngine operators (mutate / edit / crossover / spawn / retire, in
trading/brain/instructions.py) into a scheduled, self-driving cycle and PROVES the
requirement the operators alone cannot: a mutated child that *measurably beats its
parent* on real graded evidence is auto-promoted, the parent retired, and the full
lineage recorded (Brain Ultra Upgrade GOAL.md Pillar 4, acceptance item 5 & 16).

Each cycle does two honest passes over the live instruction neurons:

  VARY   — every underperformer with enough evidence and no live experiment yet gets
           ONE mutation child (GEPA-style reflective mutation; deterministic trace-
           derived guard-step fallback when no LLM is reachable). Capped per cycle so
           the neuron web cannot runaway-grow.
  SELECT — any child that has earned >= MIN_EVIDENCE of its OWN graded outcomes and now
           beats a parent's confidence by PROMOTE_MARGIN is promoted; the parent is
           retired (its record kept as a lesson neuron — negative knowledge is knowledge).

Nothing here fabricates a win: children start at their parent's confidence and only rise
through record_use() outcomes fed by the live consult/grade seams. The child-beats-parent
ledger persists in trading/state/instruction_evolution.json (isolate in tests by
monkeypatching trading.state.STATE_DIR).
"""
from __future__ import annotations

import time

from trading import state
from trading.brain.instructions import InstructionEngine

LEDGER_FILE = "instruction_evolution.json"

CONF_FLOOR = 0.5        # confidence below this = underperformer worth mutating
MIN_EVIDENCE = 5        # graded outcomes (wins+losses) before a verdict is trusted
PROMOTE_MARGIN = 0.05   # a child must beat its parent's confidence by at least this
MAX_VARY_PER_CYCLE = 3  # cap new instruction neurons created per cycle (runaway guard)


class InstructionEvolver:
    """Scheduled driver over InstructionEngine. One per process is plenty."""

    def __init__(self, engine: InstructionEngine | None = None):
        self.engine = engine or InstructionEngine()
        self.store = self.engine.store

    # ── helpers ────────────────────────────────────────────────────────────────
    def _live_instructions(self) -> list:
        return [n for n in self.store.all_neurons()
                if n.kind == "instruction" and not n.stats.get("retired")]

    @staticmethod
    def _evidence(n) -> int:
        return int(n.stats.get("wins", 0)) + int(n.stats.get("losses", 0))

    @staticmethod
    def _has_live_child(parent_id: str, pool: list) -> bool:
        return any(parent_id in n.parents and not n.stats.get("retired") for n in pool)

    # ── one evolution cycle (also used directly by tests) ─────────────────────
    def evolve_once(self, *, now: float | None = None) -> dict:
        now = time.time() if now is None else float(now)
        pool = self._live_instructions()

        # VARY: mutate underperforming ORIGINALS that have no live experiment yet.
        candidates = sorted(
            (n for n in pool
             if not n.parents                            # evolve originals, not experiments
             and self._evidence(n) >= MIN_EVIDENCE
             and n.confidence < CONF_FLOOR
             and not self._has_live_child(n.id, pool)),
            key=lambda n: (n.confidence, -self._evidence(n)))
        varied = []
        for n in candidates[:MAX_VARY_PER_CYCLE]:
            child = self.engine.mutate(n.id, now=now)     # falls back to trace-derived edit
            if child is not None:
                varied.append({"parent": n.id, "child": child.id,
                               "parent_conf": n.confidence})

        # SELECT: promote children that measurably beat a parent, retire the parent.
        promotions = []
        for child in self._live_instructions():           # refresh: new children included
            if (not child.parents or child.stats.get("promoted")
                    or self._evidence(child) < MIN_EVIDENCE):
                continue
            for pid in child.parents:
                parent = self.store.get(pid)
                if parent is None or parent.stats.get("retired"):
                    continue
                if child.confidence >= parent.confidence + PROMOTE_MARGIN:
                    self._promote(child, parent, now=now)
                    promotions.append({
                        "child": child.id, "parent": pid,
                        "child_conf": child.confidence, "parent_conf": parent.confidence,
                        "child_record": [int(child.stats.get("wins", 0)),
                                         int(child.stats.get("losses", 0))],
                        "ts": now})
                    break

        summary = {"ts": now, "varied": varied, "promotions": promotions,
                   "live_instructions": len(self._live_instructions())}
        self._record(summary)
        return summary

    def _promote(self, child, parent, *, now: float) -> None:
        with self.store._lock:                            # _persist only under the store lock
            child.stats["promoted"] = now
            child.updated = now
            self.store._persist(child)
        self.engine.retire(
            parent.id,
            f"superseded by evolved child {child.id} "
            f"(confidence {child.confidence} > {parent.confidence})",
            now=now)

    # ── ledger + observability ─────────────────────────────────────────────────
    def _record(self, summary: dict) -> None:
        def _upd(d):
            d = d or {"lineage": [], "cycles": 0}
            d["cycles"] = int(d.get("cycles", 0)) + 1
            d["last"] = summary
            d["lineage"] = (d.get("lineage", []) + summary["promotions"])[-100:]
            return d
        state.mutate_json(LEDGER_FILE, _upd, default={"lineage": [], "cycles": 0})

    def status(self) -> dict:
        led = state.load_json(LEDGER_FILE, {}) or {}
        return {"cycles": led.get("cycles", 0),
                "proven_lineages": len(led.get("lineage", [])),
                "recent_promotions": led.get("lineage", [])[-5:],
                "live_instructions": len(self._live_instructions()),
                "pareto_front": self.engine.pareto_archive(k=20),
                "last": led.get("last")}


_EVOLVER: InstructionEvolver | None = None


def get_evolver() -> InstructionEvolver:
    global _EVOLVER
    if _EVOLVER is None:
        _EVOLVER = InstructionEvolver()
    return _EVOLVER
