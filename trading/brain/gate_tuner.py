"""trading/brain/gate_tuner.py — off-policy gate threshold tuning (2026-07-10).

Because the paper lab runs EXPLORE-OPEN-ALL (gates advisory, nearly every candidate is
taken), the journal is an unbiased log with real outcomes on BOTH sides of any
threshold — so tuning is a direct counterfactual sweep, no importance weighting needed:

    value(θ) = mean r_multiple of closed trades whose gate score ≥ θ      (with n(θ))

Swept per gate signal actually recorded on rows:
    p_up        — conformal-UQ calibrated win probability (indicator_fusion.meta.p_up;
                  the UQ_GATE θ, currently hand-set 0.55)
    confidence  — brain_confidence_entry (the CRYPTO_MIN_SCORE lever's cousin)

Output → trading/state/gate_tuning.json + /api/trading/gate_tuning: the full sweep
(honesty: you see the whole curve, not just a headline), the recommended θ (best mean R
with a MIN_N support rail), and what the CURRENT hand-set θ scores. RECOMMENDATION-ONLY
on purpose: env gates stay owner-controlled; the funnel wiring to auto-consume this file
is one line once the sibling session's broker_sense edits land. Runs as a learn-loop
piggyback tick.
"""
from __future__ import annotations

import time

_STATE_FILE = "gate_tuning.json"
MIN_N = 40                      # a θ must keep at least this many trades to be trusted
_GRID = [round(0.05 * i, 2) for i in range(0, 20)]          # 0.00 … 0.95


def _current_levers() -> dict:
    """The LIVE hand-set gate levers, read from the same envs the gates read —
    a hardcoded copy went stale the moment the owner changed a lever (review fix).
    p_up mirrors trading/uq/conformal.py (UQ_P_UP_MIN, default 0.55); confidence
    mirrors the CRYPTO_MIN_SCORE family (percoin_decider default 0.5)."""
    import os
    try:
        p_up = float(os.environ.get("UQ_P_UP_MIN", 0.55))
    except (TypeError, ValueError):
        p_up = 0.55
    try:
        conf = float(os.environ.get("CRYPTO_MIN_SCORE", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return {"p_up": p_up, "confidence": conf}


def _dig(r: dict, *keys):
    cur = r
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def _score_of(row: dict, signal: str):
    if signal == "p_up":
        v = _dig(row, "decision_snapshot", "app_signals", "indicator_fusion", "meta")
        v = (v or {}).get("p_up")
    else:
        v = row.get("brain_confidence_entry")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v > 1.0:
        v /= 100.0
    return v if v > 0 else None            # <=0 = missing-value artifact (calibration rule)


def sweep(rows: list[dict], signal: str) -> dict | None:
    """Full threshold curve for one gate signal; None when too few scored rows."""
    pairs = []
    for r in rows:
        s = _score_of(r, signal)
        if s is None or r.get("r_multiple") is None:
            continue
        try:
            pairs.append((s, float(r["r_multiple"]), 1 if (r.get("net_pnl") or 0) > 0 else 0))
        except (TypeError, ValueError):
            continue
    if len(pairs) < MIN_N:
        return None
    curve = []
    for th in _GRID:
        kept = [(rm, w) for s, rm, w in pairs if s >= th]
        if not kept:
            break
        curve.append({"theta": th, "n": len(kept),
                      "mean_R": round(sum(rm for rm, _ in kept) / len(kept), 4),
                      "win_rate": round(sum(w for _, w in kept) / len(kept), 4)})
    supported = [c for c in curve if c["n"] >= MIN_N]
    best = max(supported, key=lambda c: c["mean_R"]) if supported else None
    cur_th = _current_levers().get(signal)
    current = next((c for c in curve if c["theta"] >= cur_th), None) if cur_th else None
    return {"signal": signal, "n_scored": len(pairs), "curve": curve,
            "recommended": best, "current_theta": cur_th, "current": current,
            "uplift_mean_R": (round(best["mean_R"] - current["mean_R"], 4)
                              if best and current else None)}


def tune_once(lookback: int = 1500) -> dict:
    """Sweep every recorded gate signal over the newest closed trades; persist."""
    from trading import state
    rows = [r for r in (state.load_json("journal.json", []) or [])
            if isinstance(r, dict)][-lookback:]
    out = {"ts": time.time(), "n_rows": len(rows), "min_n": MIN_N, "signals": {},
           "note": ("direct counterfactual sweep — valid because explore-open-all logs "
                    "outcomes on both sides of every θ; recommendation-only, env gates "
                    "stay owner-set")}
    for signal in ("p_up", "confidence"):
        sw = sweep(rows, signal)
        if sw:
            out["signals"][signal] = sw
        else:
            out["signals"][signal] = {"signal": signal, "available": False,
                                      "reason": f"fewer than {MIN_N} scored rows"}
    state.save_json(_STATE_FILE, out)
    return out


def status() -> dict:
    from trading import state
    return state.load_json(_STATE_FILE, {"ts": None, "signals": {},
                                         "note": "no tuning sweep has run yet"})
