"""trading/execution/exec_choice.py — E7: learned-measurable execution timing (limit vs market).

The audit found the RL execution island (rl_execution.py PPO slicer + ExecutionEnv) built and
never plugged. HONESTY CALL: that agent emits multi-slice SCHEDULES, and the engine's only
door is a single Freqtrade forceenter — wiring a schedule to a one-shot order would be
decorative (anti-pattern: fake connectivity). What the door DOES support per order is
order_type + price. So E7 ships the measurable half: a per-entry microstructure chooser
(market vs limit-at-touch) over the RAM mirror's live 20-level book, with every choice logged
and every fill graded (realized slippage vs decision-time mid) so the choice quality is a
MEASURED fact. The PPO slicer stays the trainer for a future slicing door; grading data this
module accumulates is exactly what that door will need.

Choice logic (standard microstructure, no magic):
  • spread ≤ EXEC_LIMIT_MIN_SPREAD_BPS (2 bps) → market (a limit saves less than the queue risk)
  • short-term drift AGAINST the entry side (price coming to us) → limit at touch (patient)
  • drift WITH the entry side (running away) → market (chase risk > spread cost)
  • otherwise: wide spread → limit at touch, else market
  • no fresh book (symbol unwatched / stream cold) → market + reason "no_book" (never guess)

RANDOMIZED A/B (EXEC_AB, 2026-07-18)
The rules above are a POLICY, not an experiment: limit is chosen exactly when drift is
"coming_to_us", i.e. when price is already moving toward our resting price. So the
measured limit-vs-market slippage gap (-2.905 vs +3.845 bps on 2026-07-18) is selected,
not causal — and grade_fills() only ever sees orders that BECAME trades, so it is also
conditional on fill. Neither confound is fixable by analysis; it needs randomization.

EXEC_AB=1 overrides the policy on a random EXEC_AB_FRAC of decisions with a fair coin,
so limit-vs-market becomes independent of drift/spread and the comparison is causal.
Randomization happens ONLY where a live book exists — where both arms are actually
feasible. A `no_book` decision cannot be a maker order at all, so including it would
compare a policy against itself. The arm is recorded on every row.

The coin is deterministic in (symbol, side, minute) rather than random.random(), so a
retry of the same signal inside a minute cannot re-roll into the other arm and count
twice — and any row can be re-derived offline from the log.

HONEST LIMIT: paper CANNOT settle maker fill rate. Freqtrade's dry-run fills a resting
limit with no queue position, full size, the instant the far side crosses it
(exchange.py:1288) and never expires it without unfilledtimeout — measured 99.9% fill,
median wait 27s, max 34.6 HOURS. Treat any paper maker fill rate as an upper bound; the
trustworthy paper number is slippage conditional on fill, against a real recorded mid.

State: exec_choice_log.jsonl (choices), exec_choice_stats.json (per-order-type slippage).
Env: EXEC_CHOICE (1), EXEC_LIMIT_MIN_SPREAD_BPS (2), EXEC_DRIFT_BPS (5),
     EXEC_AB (0), EXEC_AB_FRAC (1.0).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from trading import state

_LOG = "exec_choice_log.jsonl"
_STATS = "exec_choice_stats.json"
_MAX_LOG_LINES = 20_000


def enabled() -> bool:
    return os.environ.get("EXEC_CHOICE", "1") in ("1", "true", "TRUE", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _flat(symbol: str) -> str:
    return (symbol or "").replace("/", "").split(":")[0].upper()


def ab_enabled() -> bool:
    return os.environ.get("EXEC_AB", "0") in ("1", "true", "TRUE", "yes", "on")


def _ab_arm(symbol: str, side: str) -> str | None:
    """Deterministic fair coin over (symbol, side, minute) → "limit" | "market" | None.

    Keyed on the minute so a retried signal keeps its arm instead of re-rolling (which
    would let one decision enter both arms). Uses sha256 rather than hash() because
    PYTHONHASHSEED randomizes str hashing per process — the arm has to be reproducible
    offline from the log, and across restarts, or the experiment cannot be audited.
    """
    if not ab_enabled():
        return None
    frac = max(0.0, min(1.0, _f("EXEC_AB_FRAC", 1.0)))
    key = f"{_flat(symbol)}|{(side or '').lower()}|{int(time.time() // 60)}"
    h = hashlib.sha256(key.encode()).digest()
    # byte 1 decides participation, byte 0 decides the arm — independent draws
    if frac < 1.0 and (h[1] / 255.0) > frac:
        return None
    return "limit" if (h[0] & 1) else "market"


def _drift_bps(flat: str) -> float | None:
    """Signed 3-minute drift in bps from the mirror's 1m bars (+ = rising)."""
    try:
        from trading.broker_sense.binance_stream import get_mirror
        rows = get_mirror().candles(flat, 60, 4) or []
        if len(rows) < 3:
            return None
        a, b = float(rows[-3][4]), float(rows[-1][4])
        if a <= 0:
            return None
        return (b - a) / a * 1e4
    except Exception:
        return None


def choose(symbol: str, side: str) -> dict:
    """→ {order_type, price, mid, spread_bps, drift_bps, reason}. Never raises;
    the fallback is always a market order (the pre-E7 behavior)."""
    out = {"order_type": "market", "price": None, "mid": None,
           "spread_bps": None, "drift_bps": None, "reason": "default_market"}
    if not enabled():
        out["reason"] = "disabled"
        return out
    try:
        from trading.broker_sense.binance_stream import get_mirror
        flat = _flat(symbol)
        # touch() = 20-level depth if this symbol is subscribed, else the all-market
        # !bookTicker BBO. Previously this called book() alone, which is None for anything
        # outside the ~200-symbol depth subscription — measured 53% of entries returning
        # "no_book" and silently defaulting to market, so half the lane could never be a
        # maker order and was invisible to the entry A/B.
        t = get_mirror().touch(flat)
        if not t:
            out["reason"] = "no_book"
            return out
        bid, ask = float(t["bid"]), float(t["ask"])
        out["book_src"] = t.get("src")
        if bid <= 0 or ask <= bid:
            out["reason"] = "bad_book"
            return out
        mid = (bid + ask) / 2.0
        spread_bps = (ask - bid) / mid * 1e4
        drift = _drift_bps(flat)
        long_side = (side or "long").lower() != "short"
        out.update({"mid": mid, "spread_bps": round(spread_bps, 3),
                    "drift_bps": round(drift, 3) if drift is not None else None})
        # ── randomized arm (EXEC_AB): overrides the policy, but only here — past the book
        # checks, so every randomized decision is one where BOTH arms were possible.
        arm = _ab_arm(symbol, side)
        if arm:
            out["arm"] = arm
            if arm == "limit":
                out.update({"order_type": "limit",
                            "price": bid if long_side else ask,
                            "reason": "ab_limit"})
            else:
                out.update({"order_type": "market", "price": None, "reason": "ab_market"})
            return out

        min_spread = _f("EXEC_LIMIT_MIN_SPREAD_BPS", 2.0)
        drift_thr = _f("EXEC_DRIFT_BPS", 5.0)
        if spread_bps <= min_spread:
            out["reason"] = "tight_spread"
            return out
        if drift is not None and ((long_side and drift > drift_thr)
                                  or (not long_side and drift < -drift_thr)):
            out["reason"] = "running_away"          # chasing: pay the spread, get filled
            return out
        out["order_type"] = "limit"
        out["price"] = bid if long_side else ask    # join the touch, earn the spread
        out["reason"] = ("coming_to_us" if drift is not None and
                         ((long_side and drift < -drift_thr) or
                          (not long_side and drift > drift_thr)) else "wide_spread")
        return out
    except Exception:
        out["reason"] = "error_fallback"
        return out


_LAST: dict[tuple[str, str], dict] = {}      # (symbol, side) -> {**choice, "ts"}
_LAST_MAX = 512


def last_choice(symbol: str, side: str = "", *, max_age_s: float = 30.0) -> dict | None:
    """The choice just made for this entry, or None if older than max_age_s / unknown.

    Exists because the order type is decided HERE (engine_client, at submit time) but is
    needed by entry_meta.record() two layers up, which had no way to learn it and so
    hardcoded entry_type="taker" on every crypto entry — including the limit ones. Threading
    it through four call layers would touch every caller; this is read within milliseconds of
    the write, in the same entry flow, so the 30s TTL is a tight join rather than the ±300s
    fuzzy window grade_fills() uses.
    """
    now = time.time()
    for key in ((_flat(symbol), (side or "").lower()), (_flat(symbol), "")):
        v = _LAST.get(key)
        if v and (now - v["ts"]) <= max_age_s:
            return dict(v)
    return None


def log_choice(symbol: str, side: str, choice: dict, *, enter_tag: str = "") -> None:
    """Append the choice for later fill-grading. Best-effort, bounded, never raises."""
    try:
        if len(_LAST) > _LAST_MAX:                 # bounded: this is a hand-off, not a store
            _LAST.clear()
        _LAST[(_flat(symbol), (side or "").lower())] = {**choice, "ts": time.time()}
        p = Path(state.STATE_DIR) / _LOG
        row = {"ts": round(time.time(), 3), "symbol": _flat(symbol), "side": side,
               "enter_tag": enter_tag, **{k: choice.get(k) for k in
               ("order_type", "price", "mid", "spread_bps", "drift_bps", "reason", "arm",
                "book_src")}}
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        if p.stat().st_size > _MAX_LOG_LINES * 200:
            lines = p.read_text(encoding="utf-8").splitlines()[-_MAX_LOG_LINES // 2:]
            tmp = p.with_suffix(".tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(p)
    except Exception:
        pass


def grade_fills(trades: list) -> int:
    """Join open trades' realized open_rate against the logged decision-time mid → signed
    slippage bps per order type (negative = we did BETTER than mid). Idempotent by trade_id;
    aggregates land in exec_choice_stats.json. Called from the executor's exit pass with the
    trade list it already holds."""
    if not enabled() or not trades:
        return 0
    try:
        rows = []
        p = Path(state.STATE_DIR) / _LOG
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines()[-4000:]:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        if not rows:
            return 0
        by_sym: dict[str, list] = {}
        for r in rows:
            by_sym.setdefault(r.get("symbol") or "", []).append(r)
        graded = 0

        def _m(d: dict) -> dict:
            nonlocal graded
            seen = d.setdefault("graded_ids", [])
            seen_set = set(seen)
            agg = d.setdefault("by_type", {})
            for t in trades:
                if not isinstance(t, dict):
                    continue
                tid = str(t.get("trade_id") or "")
                sym = _flat(t.get("pair") or "")
                rate = t.get("open_rate")
                ots = t.get("open_timestamp")
                if not tid or tid in seen_set or not rate or not ots:
                    continue
                ots = float(ots) / (1000.0 if float(ots) > 1e12 else 1.0)
                best = None
                for r in by_sym.get(sym, []):
                    if abs(float(r["ts"]) - ots) <= 300 and r.get("mid"):
                        if best is None or abs(float(r["ts"]) - ots) < abs(float(best["ts"]) - ots):
                            best = r
                if best is None:
                    continue
                mid = float(best["mid"])
                sgn = -1.0 if (t.get("is_short")) else 1.0
                slip_bps = sgn * (float(rate) - mid) / mid * 1e4   # + = paid worse than mid
                b = agg.setdefault(str(best.get("order_type") or "market"),
                                   {"n": 0, "slip_bps_sum": 0.0})
                b["n"] += 1
                b["slip_bps_sum"] = round(b["slip_bps_sum"] + slip_bps, 4)
                seen.append(tid)
                seen_set.add(tid)
                graded += 1
            del seen[:-4000]
            return d
        state.mutate_json(_STATS, _m, default={})
        return graded
    except Exception:
        return 0


def status() -> dict:
    st = state.load_json(_STATS, {}) or {}
    out = {"enabled": enabled(), "by_type": {}}
    for ot, b in (st.get("by_type") or {}).items():
        n = int(b.get("n") or 0)
        out["by_type"][ot] = {"n": n,
                              "slip_bps_mean": round(b.get("slip_bps_sum", 0.0) / n, 3)
                              if n else None}
    return out
