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

from trading import state

_FILE = "profit_tailgate.json"
_LOCK_FILE = "profit_tailgate_locks.json"       # per-open-trade ratcheting locked-profit floor

# defaults before the brain has learned (sensible trailing distances by segment volatility)
_DEFAULT_DIST = {"futures": 0.30, "spot": 0.30, "options": 0.40, "prediction": 0.50,
                 "equity": 0.25, "commodities": 0.30}
_MIN_ARM_PROFIT = 0.5          # only arm the tailgate once the trade is up ≥ this % (else noise)


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


def locked_profit(market: str, segment: str, *, trade_id: str, profit_pct: float,
                  peak_profit_pct: float, regime: str = "") -> dict:
    """The RATCHET (owner's spec): as profit climbs, the LOCKED profit floor moves UP with it and
    NEVER down — locking in an ever-higher guaranteed gain. Returns the current locked value + the
    exit decision. `tailgate_locked_profit_pct` = what the trades table shows. Persists per trade so
    the lock only increases across polls."""
    dist = learned_distance(market, segment, regime)
    locks = state.load_json(_LOCK_FILE, {})
    rec = locks.get(trade_id) or {}
    prev = float(rec.get("locked", 0.0))
    # the PEAK ratchets too: callers derive it from live data each poll, so a momentary dip
    # (or a caller sending a lower reading) must never shrink the stored peak below the lock
    prev_peak = float(rec.get("peak", 0.0))
    peak = max(prev_peak, peak_profit_pct) if peak_profit_pct is not None else prev_peak
    exit_now, reason = False, "riding"
    locked = prev
    if peak >= _MIN_ARM_PROFIT:
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
    if peak_profit_pct is None or peak_profit_pct < _MIN_ARM_PROFIT:
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
