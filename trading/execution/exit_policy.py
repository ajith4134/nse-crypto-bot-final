"""trading/execution/exit_policy.py — E2: ONE learned exit policy per trade (Thompson bandit).

WHY (direction program, 2026-07-16): entry-sign accuracy is ~0.52 while realized P&L stays
negative — the measured leak is selection/timing/EXIT. The repo has five exit mechanisms
(profit-tailgate ratchet, dir_exit thesis-flip, smart-exit forecast, the video-A value-area
trail, partial scale-out) but they were either hard-wired in a fixed stack or shadow-gated.
This module makes the choice LEARNED: each new trade is assigned one exit ARM by Thompson
sampling over Beta(win) posteriors keyed (arm, regime), the arm ALONE manages that trade,
and the realized outcome updates the posterior on close. Paper is the experiment
(CONVENTIONS §15): every arm ACTS — no shadow assignments.

Arms:
  ratchet            profit-tailgate only (the winner-manager)
  direction          dir_exit only (cut when the calibrated direction read flips)
  ratchet_direction  both — the pre-E2 live behavior, kept as the CONTROL arm
  forecast           smart_exit acting (symbol-move-net forecast against the position)
  va_trail           video-A trail: arm after the price moves `XP_TRAIL_ARM_PCT` in favor,
                     then trail the prior closed 5m bar's low (long) / high (short); exit
                     on breach. RAM candles only.
  scale_out          close XP_SCALE_FRACTION at +1R (R = entry ATR%, fallback
                     XP_SCALE_TARGET_PCT), then va_trail the remainder.
  early_abort        E6b (experiments-20260717): winners bounce (35bps median adverse
                     excursion) while losers run (202bps median) — abort the moment the
                     PRICE moves XP_ABORT_BPS against entry (leverage-independent), and
                     manage survivors with the normal profit-tailgate ratchet. The offline
                     counterfactual at 50bps turned the clean window's −1,979 into −316;
                     this arm makes that claim EARN its place in the live bandit.

State (all in trading/state/): exit_policy_bandit.json  {"arm|regime": {a, b, n, capture_sum}}
                               exit_policy_assign.json  {trade_id: {arm, regime, lane, ts, …}}
Env: EXIT_POLICY (1 = on), XP_TRAIL_ARM_PCT (0.4), XP_SCALE_FRACTION (0.34),
     XP_SCALE_TARGET_PCT (1.2), XP_PRIOR_A/B (1/1), XP_ABORT_BPS (50).

The bandit updates on CLOSE via freqtrade_ingest._learn_from_close (once per trade).
`random` is seeded from os.urandom per process — Thompson needs real randomness.
"""
from __future__ import annotations

import os
import random
import time

from trading import state

_BANDIT = "exit_policy_bandit.json"
_ASSIGN = "exit_policy_assign.json"
ARMS = ("ratchet", "direction", "ratchet_direction", "forecast", "va_trail", "scale_out",
        "early_abort")
_CONTROL = "ratchet_direction"
_MAX_ASSIGN = 4000                      # prune closed/stale assignments beyond this


def enabled() -> bool:
    return os.environ.get("EXIT_POLICY", "1") in ("1", "true", "TRUE", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _key(arm: str, regime: str | None) -> str:
    return f"{arm}|{(regime or 'unknown').lower()}"


# ── choice + assignment ─────────────────────────────────────────────────────────────

def choose(regime: str | None = None) -> str:
    """Thompson-sample an arm for a NEW trade. Every arm keeps a live posterior per regime;
    the prior (a=b=1) makes unexplored arms compete immediately — exploration is the point."""
    if not enabled():
        return _CONTROL
    bd = state.load_json(_BANDIT, {}) or {}
    pa, pb = _f("XP_PRIOR_A", 1.0), _f("XP_PRIOR_B", 1.0)
    best, best_draw = _CONTROL, -1.0
    for arm in ARMS:
        b = bd.get(_key(arm, regime)) or bd.get(_key(arm, None)) or {}
        a = pa + float(b.get("a") or 0.0)
        bb = pb + float(b.get("b") or 0.0)
        draw = random.betavariate(a, bb)
        if draw > best_draw:
            best, best_draw = arm, draw
    return best


def assign(trade_id: str, *, regime: str | None = None, lane: str = "",
           symbol: str = "", atr_pct: float | None = None,
           horizon: str | None = None) -> str:
    """Pick + persist the exit arm for a just-opened trade. Returns the arm.
    `horizon` (MISSION X-B) is the direction brain's emitted holding period — recorded so
    the arms and the post-mortem can honor/mine it (a correct 4h call must not be managed
    like a 15m scalp)."""
    arm = choose(regime)
    if not trade_id:
        return arm

    def _m(d: dict) -> dict:
        d[str(trade_id)] = {"arm": arm, "regime": (regime or "unknown").lower(),
                            "lane": lane, "symbol": symbol, "ts": time.time(),
                            "atr_pct": atr_pct, "horizon": horizon,
                            "trail": None, "partial_done": False}
        if len(d) > _MAX_ASSIGN:                     # oldest out
            for k in sorted(d, key=lambda k: d[k].get("ts") or 0)[:len(d) - _MAX_ASSIGN]:
                d.pop(k, None)
        return d
    try:
        state.mutate_json(_ASSIGN, _m, default={})
    except Exception:
        pass
    return arm


def assignment(trade_id: str) -> dict | None:
    if not enabled() or not trade_id:
        return None
    return (state.load_json(_ASSIGN, {}) or {}).get(str(trade_id))


# ── the two arms this module executes itself (trail / scale-out) ────────────────────

def _prev_bar(symbol: str) -> tuple[float, float] | None:
    """(low, high) of the last CLOSED 5m bar from the RAM mirror; None when unavailable."""
    try:
        from trading.broker_sense.binance_stream import get_mirror
        flat = (symbol or "").replace("/", "").split(":")[0].upper()
        rows = get_mirror().candles(flat, 300, 3) or []
        if len(rows) < 2:
            return None
        prev = rows[-2]                              # [-1] is the forming bar
        return float(prev[3]), float(prev[2])
    except Exception:
        return None


def evaluate_trail(trade_id: str, *, symbol: str, direction: str,
                   profit_pct: float | None, price: float | None) -> dict:
    """va_trail / scale_out per-poll logic. → {exit, partial, reason, trail}.

    Trail semantics (video A, research/video/vp-first-candle-value): once armed, the stop
    ratchets to each prior closed bar's low (long) / high (short) and NEVER loosens; a
    breach exits. scale_out first takes XP_SCALE_FRACTION off at +1R, then trails the rest."""
    out = {"exit": False, "partial": 0.0, "reason": "", "trail": None}
    rec = assignment(trade_id)
    if not rec or rec.get("arm") not in ("va_trail", "scale_out") or price is None:
        return out
    arm = rec["arm"]
    long_side = (direction or "LONG").upper() != "SHORT"
    arm_pct = _f("XP_TRAIL_ARM_PCT", 0.4)
    changed = False
    if arm == "scale_out" and not rec.get("partial_done"):
        r_pct = float(rec.get("atr_pct") or 0.0) or _f("XP_SCALE_TARGET_PCT", 1.2)
        if profit_pct is not None and profit_pct >= r_pct:
            rec["partial_done"] = True
            changed = True
            out["partial"] = min(0.9, max(0.05, _f("XP_SCALE_FRACTION", 0.34)))
            out["reason"] = f"scale_out: +{profit_pct:.2f}% ≥ 1R ({r_pct:.2f}%)"
    trail = rec.get("trail")
    armed = trail is not None or (profit_pct is not None and profit_pct >= arm_pct)
    if armed:
        pb = _prev_bar(rec.get("symbol") or symbol)
        if pb is not None:
            lo, hi = pb
            new = lo if long_side else hi
            if trail is None or (long_side and new > trail) or (not long_side and new < trail):
                trail = new                          # ratchet only, never loosen
                rec["trail"] = trail
                changed = True
        if trail is not None:
            out["trail"] = trail
            if (long_side and float(price) < trail) or \
               (not long_side and float(price) > trail):
                out["exit"] = True
                out["reason"] = out["reason"] or (
                    f"{arm}: price {price} breached trail {trail}")
    if changed:
        def _m(d: dict) -> dict:
            if str(trade_id) in d:
                d[str(trade_id)] = rec
            return d
        try:
            state.mutate_json(_ASSIGN, _m, default={})
        except Exception:
            pass
    return out


def evaluate_abort(trade_id: str, *, direction: str, open_rate: float | None,
                   price: float | None) -> dict:
    """early_abort per-poll logic → {exit, reason}.

    Fires when the PRICE has moved ≥ XP_ABORT_BPS against the entry — price-based bps,
    NOT profit_ratio, so leverage never scales the trigger (the E6b measurement was on
    price excursions). No minimum hold: the measured loser signature is an early adverse
    run, and waiting is exactly the leak this arm exists to cut. Missing/zero inputs →
    no exit (a measurement gap must never close a trade)."""
    out = {"exit": False, "reason": ""}
    rec = assignment(trade_id)
    if not rec or rec.get("arm") != "early_abort":
        return out
    try:
        op, px = float(open_rate or 0.0), float(price or 0.0)
    except (TypeError, ValueError):
        return out
    if op <= 0 or px <= 0:
        return out
    long_side = (direction or "LONG").upper() != "SHORT"
    adverse_bps = ((op - px) if long_side else (px - op)) / op * 1e4
    limit = _f("XP_ABORT_BPS", 50.0)
    if adverse_bps >= limit:
        out["exit"] = True
        out["reason"] = (f"early_abort: adverse {adverse_bps:.0f}bps ≥ {limit:.0f}bps "
                         f"(open {op}, now {px})")
    return out


# ── learning (called once per CLOSED trade by freqtrade_ingest) ─────────────────────

def learn(trade_id: str, *, profit_pct: float | None) -> dict | None:
    """Beta update for the closed trade's arm: success = profit > 0. Removes the
    assignment. Returns what was learned (None when the trade wasn't assigned)."""
    rec = assignment(trade_id)
    if rec is None or profit_pct is None:
        return None
    key = _key(rec["arm"], rec.get("regime"))
    win = float(profit_pct) > 0.0

    def _mb(d: dict) -> dict:
        b = d.setdefault(key, {"a": 0, "b": 0, "n": 0, "capture_sum": 0.0})
        b["a"] = int(b.get("a") or 0) + (1 if win else 0)
        b["b"] = int(b.get("b") or 0) + (0 if win else 1)
        b["n"] = int(b.get("n") or 0) + 1
        b["capture_sum"] = round(float(b.get("capture_sum") or 0.0) + float(profit_pct), 4)
        return d

    def _ma(d: dict) -> dict:
        d.pop(str(trade_id), None)
        return d
    try:
        state.mutate_json(_BANDIT, _mb, default={})
        state.mutate_json(_ASSIGN, _ma, default={})
    except Exception:
        return None
    return {"arm": rec["arm"], "regime": rec.get("regime"), "win": win,
            "profit_pct": profit_pct}


def status() -> dict:
    """Dashboard snapshot: per-arm posteriors rolled up across regimes."""
    bd = state.load_json(_BANDIT, {}) or {}
    arms: dict[str, dict] = {}
    for key, b in bd.items():
        arm = key.split("|", 1)[0]
        m = arms.setdefault(arm, {"a": 0, "b": 0, "n": 0, "capture_sum": 0.0})
        m["a"] += int(b.get("a") or 0)
        m["b"] += int(b.get("b") or 0)
        m["n"] += int(b.get("n") or 0)
        m["capture_sum"] = round(m["capture_sum"] + float(b.get("capture_sum") or 0.0), 4)
    for m in arms.values():
        n = m["n"]
        m["win_rate"] = round(m["a"] / n, 4) if n else None
        m["capture_mean_pct"] = round(m["capture_sum"] / n, 4) if n else None
    open_assign = len(state.load_json(_ASSIGN, {}) or {})
    return {"enabled": enabled(), "arms": arms, "open_assignments": open_assign,
            "control_arm": _CONTROL}
