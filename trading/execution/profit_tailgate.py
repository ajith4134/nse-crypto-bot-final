"""trading/execution/profit_tailgate.py — adaptive trailing take-profit ("profit tailgating").

Owner's idea: a cutting-edge exit that TAILGATES the profit — it rides a winner as profit climbs,
then locks the gain the moment profit retraces too far from its PEAK (like a car tailgating: stay
close behind the peak, brake when it pulls away). Unlike a fixed trailing stop, the trailing
DISTANCE is LEARNED per (market, segment, regime) from real closed trades, so the brain improves
it over time — tighter in choppy regimes (lock fast), looser in trends (let it run).

Applies to BOTH crypto and NSE. Read-only advisory: `should_exit()` returns a signal the exec
layer acts on; it never places an order itself.

  should_exit(market, segment, profit_pct, peak_profit_pct) -> (exit: bool, distance_used, reason)
  learn(market, segment, peak_profit_pct, captured_pct, regime) -> updates the learned distance
"""
from __future__ import annotations

import os

from trading import state

_FILE = "profit_tailgate.json"
_LOCK_FILE = "profit_tailgate_locks.json"       # per-open-trade ratcheting locked-profit floor

# defaults before the brain has learned (sensible trailing distances by segment volatility)
_DEFAULT_DIST = {"futures": 0.30, "spot": 0.30, "options": 0.40, "prediction": 0.50,
                 "equity": 0.25, "commodities": 0.30}
# Only ARM the tailgate (start locking + trailing the peak) once the trade is up ≥ this %.
# Owner 2026-07-12: raised 0.5 → 3.0 — don't lock/trail until the trade clears +3% profit, so
# small noise wiggles below 3% never start the ratchet. Override via TAILGATE_ARM_PROFIT_PCT.
_MIN_ARM_PROFIT = float(__import__("os").environ.get("TAILGATE_ARM_PROFIT_PCT", "3.0") or 3.0)


def _key(market: str, segment: str, regime: str = "") -> str:
    return f"{(market or '').lower()}|{(segment or '').lower()}|{regime or 'any'}"


def _store() -> dict:
    return state.load_json(_FILE, {})


def learned_distance(market: str, segment: str, regime: str = "") -> float:
    """The trailing distance (fraction of the peak gain to give back before exiting) the brain has
    learned for this context, or the default. e.g. 0.30 → exit when profit falls to 70% of peak."""
    d = _store().get("dist", {})
    for k in (_key(market, segment, regime), _key(market, segment)):
        if k in d and d[k].get("n", 0) >= 5:      # need evidence before trusting a learned value
            return float(d[k]["value"])
    return _DEFAULT_DIST.get((segment or "").lower(), 0.30)


def _crypto_overrides(market: str) -> tuple[float | None, float | None]:
    """(arm_override, dist_cap) for CRYPTO only — the 2026-07-17 tailgate sweep
    (research/direction-brain-mission/experiments-20260717/e_tailgate_sweep.py) showed
    tighter-arm/tighter-giveback ranks better under BOTH the optimistic and pessimistic
    replay variants for crypto futures paths. Evidence is crypto-only, so the override is
    scoped to market='crypto' (NSE and sandbox keep the global behavior — market
    isolation). Env: TAILGATE_ARM_PROFIT_PCT_CRYPTO, TAILGATE_DIST_MAX_CRYPTO."""
    if (market or "").lower() != "crypto":
        return None, None
    arm = dist_cap = None
    try:
        v = os.environ.get("TAILGATE_ARM_PROFIT_PCT_CRYPTO")
        arm = float(v) if v else None
    except (TypeError, ValueError):
        arm = None
    try:
        v = os.environ.get("TAILGATE_DIST_MAX_CRYPTO")
        dist_cap = float(v) if v else None
    except (TypeError, ValueError):
        dist_cap = None
    return arm, dist_cap


def _arm_for(atr_pct: float | None, market: str = "") -> float:
    """ATR/VOL-SCALED arm (idea ①, owner 2026-07-12): a fixed 3% arm is wrong for both a
    0.5%/day coin and a 20%/day one. Scale the arm by the symbol's ATR% vs a reference so a
    high-vol coin only arms after a bigger move and a calm coin arms sooner. Bounded 0.3×–3×.
    Levers: TAILGATE_REF_ATR_PCT (1.5), TAILGATE_ARM_ATR_MIN/MAX."""
    # `is not None`, not `or` (review fix): an explicit override of 0 means "arm
    # immediately" and must not silently revert to the 3% default
    _ov = _crypto_overrides(market)[0]
    base = _ov if _ov is not None else _MIN_ARM_PROFIT
    if atr_pct is None or atr_pct <= 0:
        return base
    ref = float(os.environ.get("TAILGATE_REF_ATR_PCT", "1.5") or 1.5)
    lo = float(os.environ.get("TAILGATE_ARM_ATR_MIN", "0.3") or 0.3)
    hi = float(os.environ.get("TAILGATE_ARM_ATR_MAX", "3.0") or 3.0)
    return base * max(lo, min(hi, atr_pct / ref))


def _regime_dist_mult(regime: str) -> float:
    """REGIME-AWARE trail (idea ②): in a TREND, give back MORE before exiting (ride the winner);
    in CHOP/mean-revert, give back LESS (grab the gain). Multiplies the learned trail distance."""
    r = (regime or "").lower()
    if any(k in r for k in ("trend", "up", "down", "bull", "bear", "momentum")):
        return float(os.environ.get("TAILGATE_TREND_MULT", "1.4") or 1.4)
    if any(k in r for k in ("chop", "range", "mean", "revert", "sideways", "neutral")):
        return float(os.environ.get("TAILGATE_CHOP_MULT", "0.6") or 0.6)
    return 1.0


def locked_profit(market: str, segment: str, *, trade_id: str, profit_pct: float,
                  peak_profit_pct: float, regime: str = "", atr_pct: float | None = None) -> dict:
    """The RATCHET (owner's spec): as profit climbs, the LOCKED profit floor moves UP with it and
    NEVER down — locking in an ever-higher guaranteed gain. Returns the current locked value + the
    exit decision. `tailgate_locked_profit_pct` = what the trades table shows. Persists per trade so
    the lock only increases across polls. `atr_pct`/`regime` scale the arm + trail (ideas ①/②)."""
    arm = _arm_for(atr_pct, market)
    dist = min(0.9, max(0.05, learned_distance(market, segment, regime)
                        * _regime_dist_mult(regime)))
    cap = _crypto_overrides(market)[1]
    if cap is not None:
        # the 0.05 giveback floor survives the cap (review fix: a cap of 0 would have
        # made the ratchet exit on the first adverse tick after arming)
        dist = max(0.05, min(dist, cap))
    locks = state.load_json(_LOCK_FILE, {})
    rec = locks.get(trade_id) or {}
    prev = float(rec.get("locked", 0.0))
    # the PEAK ratchets too: callers derive it from live data each poll, so a momentary dip
    # (or a caller sending a lower reading) must never shrink the stored peak below the lock
    prev_peak = float(rec.get("peak", 0.0))
    peak = max(prev_peak, peak_profit_pct) if peak_profit_pct is not None else prev_peak
    exit_now, reason = False, "riding"
    locked = prev
    if peak >= arm:
        floor = peak * (1.0 - dist)                # the tailgate floor for the current peak
        locked = max(prev, floor)                  # RATCHET UP only — never give back a locked gain
        # exit at/below the lock REGARDLESS of sign: if profit gapped through the lock into
        # the red between polls, holding on hoping is exactly what the ratchet must prevent
        if profit_pct is not None and locked > 0 and profit_pct <= locked:
            exit_now = True
            reason = (f"tailgate lock hit: profit {profit_pct:.2f}% fell to locked "
                      f"{locked:.2f}% (peak {peak:.2f}%, {dist*100:.0f}% trail)")
        locks[trade_id] = {"locked": round(locked, 4), "peak": round(peak, 4),
                           "dist": dist}
        state.save_json(_LOCK_FILE, locks)
    return {"locked_profit_pct": round(locked, 4), "distance_pct": round(dist, 4),
            "exit": exit_now, "reason": reason, "peak_profit_pct": round(peak, 4)}


def clear_lock(trade_id: str) -> None:
    """Drop a trade's ratchet state (call on close so the file doesn't grow unbounded)."""
    locks = state.load_json(_LOCK_FILE, {})
    if locks.pop(trade_id, None) is not None:
        state.save_json(_LOCK_FILE, locks)


def should_exit(market: str, segment: str, profit_pct: float, peak_profit_pct: float,
                *, regime: str = "") -> tuple:
    """Tailgate decision for an OPEN trade. Arms only once the trade has been up ≥ _MIN_ARM_PROFIT
    and has a positive peak; then exits when the profit has retraced `distance` of the peak gain.
    Returns (exit: bool, distance_used: float, reason: str)."""
    dist = learned_distance(market, segment, regime)
    arm_ov, cap = _crypto_overrides(market)
    if cap is not None:
        dist = max(0.05, min(dist, cap))
    _arm = arm_ov if arm_ov is not None else _MIN_ARM_PROFIT
    if peak_profit_pct is None or peak_profit_pct < _arm:
        return False, dist, "not armed (peak below arm threshold)"
    # exit line = peak × (1 - distance). profit dropping below it locks the gain —
    # even if it gapped straight through into the red between polls.
    exit_line = peak_profit_pct * (1.0 - dist)
    if profit_pct is not None and profit_pct <= exit_line:
        return True, dist, (f"tailgate: profit {profit_pct:.2f}% retraced to {exit_line:.2f}% "
                            f"({dist*100:.0f}% off peak {peak_profit_pct:.2f}%)")
    return False, dist, "riding (still near peak)"


def learn(market: str, segment: str, *, peak_profit_pct: float, captured_pct: float,
          regime: str = "") -> None:
    """Improve the learned distance from a CLOSED trade. If we captured a poor fraction of the peak
    (gave too much back) → tighten (smaller distance). If we exited with lots of peak left unrealised
    on a trade that then reversed → we were about right. EMA update, bounded [0.1, 0.6]."""
    if not peak_profit_pct or peak_profit_pct <= 0:
        return
    realized_frac = max(0.0, min(1.0, (captured_pct or 0) / peak_profit_pct))
    d = _store()
    dist = d.setdefault("dist", {})
    # W2 rails: the trail distance is a LEARNED KNOB. The regime-refined and the general
    # key move together as ONE logical change, gated ONCE through the surface (ownership
    # + one-variable-only + versioned rule ledger). A refusal skips the write honestly
    # (n still counts the observation); the refusal itself is logged for the dashboard.
    gen = dist.setdefault(_key(market, segment),
                          {"value": _DEFAULT_DIST.get(segment.lower(), 0.30), "n": 0})
    if realized_frac < 0.6:
        delta = -0.06                              # tighten: gave too much of the peak back
    elif realized_frac > 0.85:
        delta = +0.03                              # loosen: let winners run further
    else:
        delta = 0.0
    n_new = gen["n"] + 1
    alpha = min(0.3, 3.0 / (n_new + 2))
    tgt = max(0.1, min(0.6, gen["value"] + delta))
    new_gen = round((1 - alpha) * gen["value"] + alpha * tgt, 4)
    allowed = True
    if abs(new_gen - gen["value"]) >= 1e-6:
        try:
            from trading.brain import surface
            allowed = surface.record_change(
                "tailgate-learner",
                knob=f"tailgate.distance_pct.{market.lower()}.{segment.lower()}",
                old=gen["value"], new=new_gen,
                evidence={"n_trades": n_new, "realized_frac": round(realized_frac, 3),
                          "peak_profit_pct": round(peak_profit_pct, 3),
                          "regime": regime or None},
                reason=("tighten: gave back too much of peak" if delta < 0 else
                        "loosen: captured nearly all — let winners run" if delta > 0
                        else "hold")).get("allowed", True)
        except Exception:
            allowed = True
    for k in (_key(market, segment, regime), _key(market, segment)):
        cur = dist.setdefault(k, {"value": _DEFAULT_DIST.get(segment.lower(), 0.30), "n": 0})
        if allowed and abs(new_gen - gen["value"]) >= 1e-6:
            t2 = max(0.1, min(0.6, cur["value"] + delta))
            a2 = min(0.3, 3.0 / (cur["n"] + 3))
            cur["value"] = round((1 - a2) * cur["value"] + a2 * t2, 4)
        cur["n"] = cur["n"] + 1
    state.save_json(_FILE, d)


def status() -> dict:
    """Dashboard snapshot: learned distances per context + defaults."""
    d = _store().get("dist", {})
    rows = [{"context": k, "distance_pct": round(v["value"] * 100, 1), "n": v["n"]}
            for k, v in d.items()]
    return {"learned": sorted(rows, key=lambda r: -r["n"]), "defaults_pct":
            {s: round(x * 100) for s, x in _DEFAULT_DIST.items()}, "arm_profit_pct": _MIN_ARM_PROFIT}
