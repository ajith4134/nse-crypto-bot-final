"""trading/brain/apply.py — APPLY instruction neurons in the decision path.

Closes the loop the evolver needs: evolve -> APPLY -> grade -> promote. select() picks a
live instruction for the current context, epsilon-greedy over a matched recipe AND its
experimental CHILDREN, so a mutated child earns its OWN graded outcomes (without being
applied, a child can never accumulate the evidence to beat its parent, and evolution
stalls). The caller records the chosen id in its decision snapshot so the trade's outcome
grades exactly this instruction (attribution — no behavior change). A bounded confidence
tilt is provided too, but whether to actually move the decision is the caller's flagged
choice (default OFF = pure attribution). Fail-open: never breaks a decision cycle.
"""
from __future__ import annotations

import os
import random

EXPLORE = float(os.environ.get("INSTRUCTION_EXPLORE", "0.2"))   # P(explore a fresh variant)
TILT_CAP = 0.03                                                 # max |p_up| nudge (bounded)
MIN_EVIDENCE = 5                                                # "fresh" = fewer graded outcomes


def _evidence(n) -> int:
    return int(n.stats.get("wins", 0)) + int(n.stats.get("losses", 0))


def _in_market(n, market: str) -> bool:
    """A trade instruction belongs to `market` only if its identity says so — never let a
    crypto recipe match an NSE decision (or vice-versa). Non-trade instructions (e.g. nav)
    pass through unfiltered."""
    if not market:
        return True
    ref = str(getattr(n, "ref", "") or "")
    if ref.startswith("trade:"):
        return ref.startswith(f"trade:{market}")       # trade recipe: ref encodes market
    return f"[{market}]" in n.title or "[" not in n.title   # child/other: title tag


def select(query: str, *, market: str = "", explore: float | None = None,
           rng=None) -> dict | None:
    """Return {"id","title","confidence","tilt"} for the instruction to apply, or None.

    MARKET-SCOPED: when `market` is given, only instructions belonging to that market are
    eligible (a crypto recipe can never be applied to an NSE decision). tilt in
    [-TILT_CAP, +TILT_CAP], derived from the instruction's confidence (0.5 = flat).
    """
    explore = EXPLORE if explore is None else explore
    rng = rng or random
    try:
        from memory.neurons import get_store
        store = get_store()
        matched = [n for h in store.search(query, kind="instruction", k=12)
                   if (n := store.get(h["id"])) is not None and not n.stats.get("retired")
                   and _in_market(n, market)]
        if not matched:
            return None
        pool = {n.id: n for n in matched}
        for n in matched:                              # pull in experimental children
            for c in store.all_neurons():
                if (n.id in c.parents and c.kind == "instruction"
                        and not c.stats.get("retired")):
                    pool[c.id] = c
        cands = list(pool.values())
        under = [n for n in cands if _evidence(n) < MIN_EVIDENCE]
        if under and rng.random() < explore:
            choice = rng.choice(under)                 # EXPLORE: give a fresh variant evidence
        else:
            choice = max(cands, key=lambda n: n.confidence)   # EXPLOIT: best known recipe
        tilt = TILT_CAP * (choice.confidence - 0.5) / 0.5
        return {"id": choice.id, "title": choice.title, "confidence": choice.confidence,
                "tilt": round(max(-TILT_CAP, min(TILT_CAP, tilt)), 4)}
    except Exception:
        return None                                    # fail-open: no instruction applied
