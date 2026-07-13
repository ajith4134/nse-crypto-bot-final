"""trading/brain/consult.py — the brain USES its web of neurons before acting (R22).

The one thin bridge every decision surface calls:

  consult(query, domain=…)  → recall the most relevant neurons, record the use
                              (times_used + per-domain evidence), return their ids +
                              instruction-shaped action facets for the caller to ride
                              in its snapshot/prompt.
  grade(ids, win=…, pnl=…)  → close the loop: outcome evidence flows back into the
                              exact neurons that were consulted (Laplace confidence +
                              per-domain wins/losses — the genius-use metric's food).

Wired seams (Phase 2, 2026-07-13): indicator_fusion.fuse() consults per decision and
freqtrade_ingest._learn_from_close grades from the decision_snapshot (trading);
nav_brain.navigate() consults learned routes and grades on completion (navigation);
AutonomousResearcher.research() consults before searching (research).

Fail-open by design: a memory problem must NEVER break a trading/navigation cycle —
every call returns a usable empty result on any error. The store singleton loads once
per process (~1s for ~7k neurons); callers are long-lived loop processes, not
dashboard request threads (those have their own warming guards).
"""
from __future__ import annotations

MAX_ACTIONS = 3


def consult(query: str, *, domain: str, k: int = 3, kind: str | None = None) -> dict:
    """Recall + record use. Returns {"ids": [...], "actions": [...], "titles": [...]}."""
    out = {"ids": [], "actions": [], "titles": []}
    q = str(query or "").strip()
    if not q:
        return out
    try:
        from memory.neurons import get_store
        store = get_store()
        for hit in store.search(q, k=k, kind=kind):
            store.record_use(hit["id"], win=None, domain=domain)
            out["ids"].append(hit["id"])
            out["titles"].append(hit["title"][:80])
            if len(out["actions"]) < MAX_ACTIONS and hit.get("action"):
                out["actions"].append(hit["action"][:240])
    except Exception:
        return {"ids": [], "actions": [], "titles": []}   # fail-open, never raises
    return out


def grade(ids, *, win: bool, pnl: float = 0.0, domain: str) -> int:
    """Outcome credit for previously-consulted neurons. Returns #graded (0 on error)."""
    graded = 0
    try:
        from memory.neurons import get_store
        store = get_store()
        for nid in list(ids or [])[:12]:
            if isinstance(nid, str) and store.record_use(
                    nid, win=bool(win), pnl=float(pnl or 0.0), domain=domain,
                    count_use=False):                 # outcome only; use was counted at consult
                graded += 1
    except Exception:
        return graded                                     # fail-open
    return graded
