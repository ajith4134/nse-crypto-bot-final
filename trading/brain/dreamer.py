"""trading/brain/dreamer.py — Counterfactual Dream-Trainer (invented 2026-07-10).

Owner ask: "make the brain improve its intelligence — something entirely different to
what we invented till now." Everything built so far learns from what DID happen; the
dreamer learns from what DIDN'T: after each batch of closed trades it "dreams" the
counterfactual versions of each trade off the journal's own excursion columns and
decomposes the REGRET — the profit left on the table — into three named causes:

  direction regret   — |MAE| far above MFE on a loser: the OPPOSITE side was the trade.
  exit-timing regret — MFE well above the realized capture: we had it and gave it back.
  capture regret     — tailgate peak vs what the tailgate actually locked.

Aggregated per (strategy, market), the dominant regret source becomes a plain-language
LESSON (e.g. "breakout/CRYPTO loses mainly to exit timing: realized 0.4% of a 2.1% MFE")
persisted to trading/state/dream_lessons.json, surfaced at /api/trading/dreams, and fed
to the learn-loop's error-driven topic picker so the brain literally studies its own
dreams. Pure journal-column math — no fabrication, no LLM, no network; runs as a cheap
piggyback tick inside the learn loop. (Phase 2, ledger 2026-07-10: replay through the
world-model ImaginationPlanner for path-level counterfactuals.)
"""
from __future__ import annotations

import time

_STATE_FILE = "dream_lessons.json"
_MIN_GROUP = 8          # trades before a group's regret is trusted (same bar as
                        # learn_loop.mistake_topics — one shared convention)


def _pct(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def _dream_trade(r: dict) -> dict | None:
    """Counterfactual regret decomposition for ONE closed journal row.

    Uses only real recorded excursions: mfe/mae (peak favorable/adverse move) and the
    tailgate columns. Returns None when the row lacks the excursion data to dream on."""
    mfe = _pct(r.get("mfe"))
    mae = _pct(r.get("mae"))
    if mfe is None or mae is None:
        return None
    pnl = _pct(r.get("net_pnl")) or 0.0
    won = pnl > 0
    realized = _pct(r.get("exit_efficiency"))
    # exit-timing regret: share of the peak favorable excursion we failed to keep, from
    # the journaled exit_efficiency (realized/MFE). No efficiency recorded → claim 0
    # rather than inventing one (pnl is currency, mfe is %, their ratio means nothing).
    if realized is not None and realized > 1.0:
        realized /= 100.0                      # 0–100-scaled efficiency → fraction
    exit_regret = (max(0.0, mfe) * (1.0 - max(0.0, min(1.0, realized)))
                   if realized is not None else 0.0)
    # direction regret: on a loser whose adverse excursion dwarfed the favorable one,
    # the opposite side had the move. Sized by the excess |MAE| over MFE.
    direction_regret = max(0.0, abs(mae) - max(0.0, mfe)) if not won else 0.0
    # capture regret: the tailgate saw a peak but locked less.
    tg_peak = _pct(r.get("tailgate_peak_profit_pct"))
    tg_lock = _pct(r.get("tailgate_locked_profit_pct"))
    capture_regret = max(0.0, (tg_peak or 0.0) - max(0.0, tg_lock or 0.0)) \
        if tg_peak is not None else 0.0
    return {"symbol": r.get("symbol"), "won": won,
            "strategy": (r.get("strategy_name") or r.get("enter_tag") or "?"),
            "market": ("CRYPTO" if "/" in str(r.get("symbol") or "") else "NSE"),
            "exit_regret": round(exit_regret, 4),
            "direction_regret": round(direction_regret, 4),
            "capture_regret": round(capture_regret, 4)}


def dream_once(lookback: int = 300) -> dict:
    """Dream over the newest `lookback` closed trades; persist + return the lessons."""
    from trading import state
    rows = state.load_json("journal.json", []) or []
    rows = [r for r in rows if isinstance(r, dict)][-lookback:]
    dreams = [d for d in (_dream_trade(r) for r in rows) if d]
    groups: dict[tuple, dict] = {}
    for d in dreams:
        g = groups.setdefault((d["strategy"], d["market"]),
                              {"n": 0, "exit": 0.0, "direction": 0.0, "capture": 0.0})
        g["n"] += 1
        g["exit"] += d["exit_regret"]
        g["direction"] += d["direction_regret"]
        g["capture"] += d["capture_regret"]
    lessons = []
    for (strat, market), g in groups.items():
        if g["n"] < _MIN_GROUP:
            continue
        means = {k: g[k] / g["n"] for k in ("exit", "direction", "capture")}
        dom = max(means, key=means.get)
        if means[dom] <= 0:
            continue
        # journal excursions are % on crypto but raw price POINTS on NSE rows — label
        # honestly instead of claiming % everywhere (units are consistent WITHIN a group,
        # so the dominant-regret ranking itself is unit-safe)
        unit = "%" if means[dom] < 50 else " pts"
        text = {"exit": (f"{strat}/{market}: biggest regret is EXIT TIMING — on average "
                         f"{means['exit']:.2f}{unit} of peak profit given back per trade"),
                "direction": (f"{strat}/{market}: biggest regret is DIRECTION — losers ran "
                              f"{means['direction']:.2f}{unit} further against us than the "
                              f"trade ever went in our favor (the opposite side had the move)"),
                "capture": (f"{strat}/{market}: biggest regret is TAILGATE CAPTURE — peaks "
                            f"exceeded the locked floor by {means['capture']:.2f}{unit} "
                            f"on average")
                }[dom]
        lessons.append({"strategy": strat, "market": market, "n": g["n"],
                        "dominant_regret": dom,
                        "mean_regret_pct": {k: round(v, 3) for k, v in means.items()},
                        "lesson": text})
    lessons.sort(key=lambda x: -max(x["mean_regret_pct"].values()))
    out = {"ts": time.time(), "n_dreamed": len(dreams), "n_rows": len(rows),
           "lessons": lessons,
           "note": "counterfactual regret decomposition off real journal excursions"}
    state.save_json(_STATE_FILE, out)
    return out


def study_topics(max_topics: int = 1) -> list[str]:
    """Research topics distilled from the freshest dream lessons (learn-loop food)."""
    from trading import state
    d = state.load_json(_STATE_FILE, {}) or {}
    topics = {"exit": "optimal trade exit timing trailing stop research",
              "direction": "trend direction detection avoiding countertrend entries",
              "capture": "profit taking trailing distance optimization"}
    out = []
    for les in (d.get("lessons") or [])[:max_topics]:
        base = topics.get(les.get("dominant_regret"))
        if base:
            out.append(f"{base} for {les.get('strategy')} strategies")
    return out


def status() -> dict:
    from trading import state
    return state.load_json(_STATE_FILE, {"ts": None, "lessons": [],
                                         "note": "no dream cycle has run yet"})
