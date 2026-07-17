"""trading/brain/graveyard.py — the strategy/lane cause-of-death ledger.

Closed-loop gap (2026-07-17 review): the brain KILLS lanes, strategies and lenses
(lane_gate retirement, tournament culls, the foundry DSR gate) but recorded ZERO about
*why* or *at which stage* they died — grep found no graveyard anywhere. A reference build
("Threepio") treats died-at-stage accounting as a first-class artifact; a silent kill is
data thrown away.

This is that ledger. `record_death()` is idempotent per (entity, kind) — the caller may be a
hot predicate fired every cycle, so we store the FIRST death, bump a `seen` counter, and keep
the latest metric/detail. Bounded. Read via `deaths()` / `status()` for the dashboard and for
future learning (e.g. "lanes that die at lane_kill with |edge|<x → don't re-breed that family").
"""
from __future__ import annotations

import time

from trading import state

_FILE = "strategy_graveyard.json"
_MAX = 2000                                   # bound the ledger


def _key(entity: str, kind: str) -> str:
    return f"{kind}:{entity}"


def record_death(entity: str, *, kind: str = "strategy", stage: str = "",
                 metric: float | None = None, detail: str = "",
                 market: str = "", bred_ts: float | None = None) -> None:
    """Log that `entity` (a lane tag / strategy name / lens) died. Idempotent per
    (entity, kind): first death is preserved, later calls bump `seen` + refresh metric/detail.
    Fail-open — a bookkeeping ledger must never break the kill path that calls it."""
    try:
        now = time.time()
        k = _key(str(entity), str(kind))

        def _m(d: dict) -> dict:
            graves = d.setdefault("graves", {})
            row = graves.get(k)
            if row is None:
                graves[k] = {"entity": str(entity), "kind": str(kind), "stage": str(stage),
                             "metric": metric, "detail": str(detail)[:160], "market": str(market),
                             "bred_ts": bred_ts, "died_ts": now, "last_ts": now, "seen": 1}
            else:
                row["seen"] = int(row.get("seen") or 0) + 1
                row["last_ts"] = now
                row["stage"] = str(stage) or row.get("stage")
                if metric is not None:
                    row["metric"] = metric
                if detail:
                    row["detail"] = str(detail)[:160]
            if len(graves) > _MAX:            # evict oldest deaths
                for kk in sorted(graves, key=lambda x: graves[x].get("died_ts") or 0)[:len(graves) - _MAX]:
                    graves.pop(kk, None)
            return d

        state.mutate_json(_FILE, _m, default={})
    except Exception:
        pass


def deaths(*, kind: str | None = None, limit: int = 200) -> list[dict]:
    """Most-recently-dead first, optionally filtered by kind."""
    d = state.load_json(_FILE, {}) or {}
    rows = list((d.get("graves") or {}).values())
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    rows.sort(key=lambda r: r.get("last_ts") or 0, reverse=True)
    return rows[:limit]


def status() -> dict:
    """Dashboard summary: counts by kind and by died-at-stage, plus the recent tail."""
    rows = deaths(limit=10_000)
    by_kind: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    for r in rows:
        by_kind[r.get("kind") or "?"] = by_kind.get(r.get("kind") or "?", 0) + 1
        by_stage[r.get("stage") or "?"] = by_stage.get(r.get("stage") or "?", 0) + 1
    return {"total": len(rows), "by_kind": by_kind, "by_stage": by_stage,
            "recent": rows[:20]}
