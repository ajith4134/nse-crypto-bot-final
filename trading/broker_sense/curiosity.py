"""trading/broker_sense/curiosity.py — curiosity-driven feature discovery on app screens
(owner goal 2026-07-07: "each and every data the trade has on the trading account web
page"; invent-beyond idea #1).

The eyes already DISCOVER labelled numbers on broker pages (learning_columns +
trade_columns). Curiosity adds the missing selective pressure: score each discovered
field by NOVELTY × INFORMATIVENESS so the brain spends attention on the fields that are
genuinely new and that VARY (a constant or ever-present field teaches nothing; a
rarely-seen field that moves is a candidate edge). High-curiosity fields are
auto-proposed as trade columns and surfaced to the owner.

  curiosity(name)   — novelty (how recently first seen, how rarely) × informativeness
                      (coefficient of variation of observed values). ∈ [0,1].
  rank()            — all discovered fields ranked by curiosity, with the reason.
  harvest()         — auto-accept the top novel+informative fields as real trade columns
                      (bounded per call; announces via mind-events). Idempotent.

Pure-stdlib over the existing ColumnRegistry; no scraping here (reads what the eyes
already recorded). Honest: a field with too few observations reports curiosity None
(unknown), never a fabricated score.
"""
from __future__ import annotations

import math
import time

from trading import state

_STATE = "curiosity.json"
_MIN_OBS = 4
_HARVEST_MAX = 3
_CURIOSITY_MIN = 0.55


def _registry():
    from trading.broker_sense.learning_columns import get_registry
    return get_registry()


def _field_stats() -> dict:
    """{name: {n, mean, cv, first_seen, source}} from the ColumnRegistry.

    The registry keeps the LATEST value per (symbol, column) in `.values`, so a field's
    informativeness = its CROSS-SYMBOL spread (does it differ across coins/stocks, or is
    it a constant?). n = how many symbols currently carry it."""
    reg = _registry()
    cols = getattr(reg, "columns", {}) or {}
    values = getattr(reg, "values", {}) or {}
    out: dict = {}
    for name, meta in cols.items():
        vals = []
        for _sym, cmap in values.items():
            if not isinstance(cmap, dict):
                continue
            v = cmap.get(name)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        n = len(vals)
        mean = sum(vals) / n if n else 0.0
        cv = None
        if n >= 2 and abs(mean) > 1e-9:
            var = sum((x - mean) ** 2 for x in vals) / (n - 1)
            cv = math.sqrt(var) / abs(mean)
        out[name] = {"n": n, "mean": round(mean, 6),
                     "cv": round(cv, 4) if cv is not None else None,
                     "first_seen": (meta.get("first_seen") if isinstance(meta, dict)
                                    else None),
                     "n_seen": (meta.get("n_seen") if isinstance(meta, dict) else None),
                     "source": (meta.get("source") if isinstance(meta, dict) else None)}
    return out


def curiosity(name: str, stats: dict | None = None) -> dict:
    st = (stats or _field_stats()).get(name)
    if not st or st["n"] < _MIN_OBS:
        return {"name": name, "curiosity": None,
                "reason": f"too few observations ({(st or {}).get('n', 0)}/{_MIN_OBS})"}
    # novelty: recently first-seen fields are more curious (decays over ~14 days)
    fs = st.get("first_seen") or time.time()
    age_days = max(0.0, (time.time() - float(fs)) / 86400.0)
    novelty = math.exp(-age_days / 14.0)
    # informativeness: values that VARY carry signal (squashed CV)
    cv = st.get("cv") or 0.0
    informative = 1.0 - math.exp(-2.5 * cv)
    score = round(0.5 * novelty + 0.5 * informative, 4)
    return {"name": name, "curiosity": score, "novelty": round(novelty, 3),
            "informativeness": round(informative, 3), "n": st["n"], "cv": cv,
            "reason": f"novelty {novelty:.2f} × informativeness {informative:.2f}"}


def rank() -> list[dict]:
    stats = _field_stats()
    scored = [curiosity(n, stats) for n in stats]
    scored = [s for s in scored if s.get("curiosity") is not None]
    return sorted(scored, key=lambda s: -s["curiosity"])


def harvest(max_accept: int = _HARVEST_MAX) -> dict:
    """Auto-accept the top curious fields as real trade columns (bounded; idempotent)."""
    from trading.broker_sense import trade_columns
    already = set(trade_columns.accepted() if hasattr(trade_columns, "accepted") else [])
    ranked = [s for s in rank()
              if s["curiosity"] >= _CURIOSITY_MIN and s["name"] not in already]
    accepted = []
    for s in ranked[:max_accept]:
        try:
            if hasattr(trade_columns, "accept"):
                trade_columns.accept(s["name"])
            accepted.append(s["name"])
        except Exception:
            continue
    st = state.load_json(_STATE, {})
    st["last_harvest"] = {"ts": time.time(), "accepted": accepted,
                          "considered": len(ranked)}
    state.save_json(_STATE, st)
    if accepted:
        try:
            from trading.brain import mind_events
            mind_events.emit("curiosity",
                             f"Curiosity harvested {len(accepted)} high-novelty data "
                             f"field(s) into trade columns: {', '.join(accepted)} — the "
                             f"eyes found data worth learning from.", salience=0.75)
        except Exception:
            pass
    return {"accepted": accepted, "considered": len(ranked),
            "top": ranked[:8]}


def status() -> dict:
    top = rank()[:12]
    return {"discovered_fields": len(_field_stats()), "top_curious": top,
            "last_harvest": state.load_json(_STATE, {}).get("last_harvest"),
            "curiosity_min": _CURIOSITY_MIN}
