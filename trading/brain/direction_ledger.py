"""trading/brain/direction_ledger.py — the Direction Decision Ledger (owner ask 2026-07-13).

"The direction is still not accurate — on WHAT DATA each trade is using to decide direction."
The learned-direction decider already computes the full rationale (each source's measured
edge-weight, whether it was inverted, the p_up it contributed, the winning side) — but that
rationale was THROWN AWAY. This module records it, per decision, so every trade's direction
is auditable: which data drove it, how much each source was trusted, and whether it abstained.

Kept market-scoped (crypto vs nse stay separate). Fail-open — recording must NEVER affect or
break a trade decision. Read by /api/trading/direction/xray + the Direction X-Ray panel.
"""
from __future__ import annotations

import time

LEDGER_FILE = "direction_ledger.json"
CAP = 400                       # recent decisions kept (ring)


def record(decision: dict, *, symbol: str = "", market: str = "", regime: str = "",
           seam: str = "decide", coverage: dict | None = None,
           now: float | None = None) -> None:
    """Persist one direction decision's rationale. `decision` is a learned_direction.decide()
    result (direction/p_up/confidence/weights/abstained) — or a correct_direction() info dict."""
    try:
        from trading import state
        ts = time.time() if now is None else float(now)
        # keep the drivers that actually carried weight, sorted by influence
        weights = decision.get("weights") or {}
        drivers = sorted(
            ({"source": s, **(w if isinstance(w, dict) else {"w": w})}
             for s, w in weights.items()),
            key=lambda d: -float(d.get("w") or 0.0))
        rec = {"ts": round(ts, 1), "symbol": str(symbol or "?"),
               "market": str(market or "").lower(), "regime": str(regime or ""),
               "seam": seam, "direction": decision.get("direction"),
               "p_up": decision.get("p_up"), "confidence": decision.get("confidence"),
               "abstained": bool(decision.get("abstained")),
               "n_sources": decision.get("n_sources"),
               "coverage": coverage,               # which filters the brain collected this trade
               "drivers": drivers[:8]}

        def _upd(d):
            d = d or {"recent": [], "by_symbol": {}}
            recent = list(d.get("recent", []))
            recent.append(rec)
            d["recent"] = recent[-CAP:]
            by = d.get("by_symbol", {})
            by[rec["symbol"]] = rec                 # latest per symbol
            d["by_symbol"] = dict(list(by.items())[-300:])
            return d
        state.mutate_json(LEDGER_FILE, _upd, default={"recent": [], "by_symbol": {}})
    except Exception:
        pass                                        # fail-open: never touch the decision


def recent(n: int = 60) -> list[dict]:
    try:
        from trading import state
        return (state.load_json(LEDGER_FILE, {}) or {}).get("recent", [])[-int(n):][::-1]
    except Exception:
        return []


def by_symbol(symbol: str) -> dict | None:
    try:
        from trading import state
        return (state.load_json(LEDGER_FILE, {}) or {}).get("by_symbol", {}).get(str(symbol))
    except Exception:
        return None


def summary() -> dict:
    """Honest roll-up for the panel header: how many decisions recorded, abstain rate, and
    the direction-driver coverage (share of decisions that had ≥1 weighted source)."""
    rec = recent(CAP)
    if not rec:
        return {"decisions": 0, "abstain_rate": None, "with_driver_rate": None}
    ab = sum(1 for r in rec if r.get("abstained"))
    wd = sum(1 for r in rec if r.get("drivers") and any(
        float(d.get("w") or 0) > 0 for d in r["drivers"]))
    return {"decisions": len(rec), "abstain_rate": round(ab / len(rec), 3),
            "with_driver_rate": round(wd / len(rec), 3),
            "markets": sorted({r.get("market") for r in rec if r.get("market")})}
