"""trading/evidence.py — W3 evidence lane: baselines, counterfactuals, autonomy gates,
blow-up watchdogs. (Owner goal 2026-07-07; videos vp0 §blind-copy-baseline +
missed-winners/avoided-losers + autonomy-earned, vp1 §fee-bleed/frozen-balance.)

Everything here is JUDGMENT of the trading system, not trading itself:

  observe_cycle()   — called by the funnel each cycle with the fused candidates +
                      what was actually entered. Records (a) BLIND-BASELINE virtual
                      entries: every non-neutral candidate, no gates — the "dumb copy"
                      the brain must beat; (b) SKIP counterfactuals: non-neutral
                      candidates the brain did NOT enter, so good-skip/bad-skip can be
                      judged later. Price snapshots ride the SAME cycle data (no extra
                      API calls — UI-only-data safe).
  autonomy_gates()  — vp0's earn-autonomy checklist per segment: ≥30 profitable paper
                      days, ≥100 trades, beats the blind baseline, no data failures,
                      drawdown sane. ALL must pass before any size-up/live promotion.
  watchdogs()       — fee-bleed ratio + frozen-activity detectors (the $50→$500→$0
                      lesson: death by a thousand small losses while nobody watched).

State: evidence_lane.json (bounded). No fabricated numbers: unresolved counterfactuals
report status "pending", baselines with no snapshots report "no-data".
"""
from __future__ import annotations

import time

from trading import state

_FILE = "evidence_lane.json"
_HORIZONS_H = (1.0, 6.0, 24.0)
_MAX_ITEMS = 4000


def _store() -> dict:
    d = state.load_json(_FILE, {})
    d.setdefault("baseline", [])       # virtual blind entries
    d.setdefault("skips", [])          # counterfactual skip records
    d.setdefault("failures", [])       # data-failure log (autonomy gate input)
    return d


def _save(d: dict) -> None:
    d["baseline"] = d["baseline"][-_MAX_ITEMS:]
    d["skips"] = d["skips"][-_MAX_ITEMS:]
    d["failures"] = d["failures"][-500:]
    state.save_json(_FILE, d)


def _norm(sig: dict) -> dict:
    """Accept BOTH shapes: the raw fuse() dict (tests/direct calls) and the funnel's
    wrapper {vote, indicator_fusion, ocular, ...} (live app_signals)."""
    if not isinstance(sig, dict):
        return {}
    fused = sig.get("indicator_fusion")
    if isinstance(fused, dict) and fused.get("available"):
        return fused
    if sig.get("available") is not None or sig.get("barriers"):
        return sig
    v = sig.get("vote") or {}
    if v.get("direction") in ("long", "short"):
        return {"available": True, "direction": v["direction"],
                "p_up": v.get("p_up"), "barriers": {}}
    return {}


def _price_of(sig: dict) -> float | None:
    try:
        p = ((_norm(sig).get("barriers") or {}).get("entry"))
        return float(p) if p else None
    except Exception:
        return None


# ── recording (called from the funnel cycle; zero extra I/O) ─────────────────────────
def observe_cycle(*, market: str, segment: str, signals: dict,
                  entered: list | None, vetoed: list | None = None) -> dict:
    """signals: {symbol: fused-decision-object}; entered: symbols actually entered.

    1. Every available non-neutral signal becomes a BLIND-BASELINE virtual trade
       (direction at current price) unless one for the symbol is still open.
    2. Non-neutral signals NOT entered are recorded as SKIPS (with the gate reason
       when known from `vetoed`).
    3. Every symbol's current price snapshot resolves any DUE pending items — the
       cycle itself is the price feed (no API polling).
    """
    now = time.time()
    entered = set(entered or [])
    veto_by_sym = {}
    for v in (vetoed or []):
        if isinstance(v, dict):
            veto_by_sym[v.get("symbol")] = v.get("reason") or v.get("gate") or "veto"
        elif isinstance(v, (list, tuple)) and v:
            veto_by_sym[v[0]] = str(v[1]) if len(v) > 1 else "veto"
    d = _store()
    open_baseline = {b["symbol"] for b in d["baseline"] if not b.get("resolved")}
    n_base = n_skip = 0
    for sym, raw in (signals or {}).items():
        sig = _norm(raw)
        if not sig.get("available"):
            continue
        price = _price_of(raw)
        direction = sig.get("direction")
        if price and direction in ("long", "short"):
            if sym not in open_baseline:
                d["baseline"].append({"symbol": sym, "market": market, "segment": segment,
                                      "direction": direction, "entry": price, "ts": now,
                                      "snaps": [], "resolved": False})
                n_base += 1
            if sym not in entered:
                d["skips"].append({"symbol": sym, "market": market, "segment": segment,
                                   "direction": direction, "price_at_skip": price,
                                   "reason": veto_by_sym.get(sym, "not selected"),
                                   "ts": now, "snaps": [], "outcomes": {},
                                   "verdict": "pending"})
                n_skip += 1
    resolved = _feed_snapshots(d, signals, now)
    _save(d)
    return {"baseline_opened": n_base, "skips_recorded": n_skip, "resolved": resolved}


def _feed_snapshots(d: dict, signals: dict, now: float) -> int:
    """Give every pending item the current cycle's price for its symbol; finalize
    horizons that are due. Returns how many horizon outcomes got resolved."""
    prices = {s: _price_of(sig) for s, sig in (signals or {}).items()
              if isinstance(sig, dict)}
    n = 0
    for coll, kind in (("skips", "skip"), ("baseline", "baseline")):
        for it in d[coll]:
            if it.get("resolved"):
                continue
            p = prices.get(it["symbol"])
            if p:
                it["snaps"] = (it.get("snaps") or [])[-48:] + [[round(now), p]]
            age_h = (now - it["ts"]) / 3600.0
            base = it.get("price_at_skip") or it.get("entry")
            sign = 1.0 if it.get("direction") == "long" else -1.0
            outcomes = it.setdefault("outcomes", {})
            for hz in _HORIZONS_H:
                key = f"h{int(hz)}"
                if key in outcomes or age_h < hz:
                    continue
                snap = _nearest_snap(it.get("snaps") or [], it["ts"] + hz * 3600.0)
                if snap is None:
                    outcomes[key] = None          # honest: no price seen near horizon
                    continue
                outcomes[key] = round(sign * (snap - base) / base * 100.0, 4)
                n += 1
            if age_h >= max(_HORIZONS_H):
                it["resolved"] = True
                if kind == "skip":
                    moves = [v for v in outcomes.values() if v is not None]
                    if not moves:
                        it["verdict"] = "unresolved"
                    else:
                        best = max(moves)
                        it["verdict"] = ("bad-skip (missed winner)" if best > 1.0 else
                                         "good-skip (avoided loser)" if best < -0.2 else
                                         "neutral-skip")
    return n


def _nearest_snap(snaps: list, target_ts: float) -> float | None:
    best, bd = None, 1800.0                        # within ±30min of the horizon
    for ts, p in snaps:
        dd = abs(ts - target_ts)
        if dd < bd:
            best, bd = p, dd
    return best


def record_data_failure(source: str, detail: str) -> None:
    d = _store()
    d["failures"].append({"ts": time.time(), "source": source, "detail": detail[:160]})
    _save(d)


# ── judgment ──────────────────────────────────────────────────────────────────────────
def baseline_stats(market: str, segment: str, window_days: float = 30.0) -> dict:
    d = _store()
    cut = time.time() - window_days * 86400
    rows = [b for b in d["baseline"]
            if b["market"] == market and b["segment"] == segment and b["ts"] >= cut]
    done = [b for b in rows if b.get("resolved") and (b.get("outcomes") or {}).get("h24")
            is not None]
    if not done:
        return {"n": len(rows), "resolved": 0, "verdict": "no-data"}
    rets = [b["outcomes"]["h24"] for b in done]
    return {"n": len(rows), "resolved": len(done),
            "mean_ret_24h_pct": round(sum(rets) / len(rets), 4),
            "win_rate": round(sum(1 for r in rets if r > 0) / len(rets), 4),
            "sum_ret_pct": round(sum(rets), 3)}


def skip_stats(market: str, segment: str, window_days: float = 30.0) -> dict:
    d = _store()
    cut = time.time() - window_days * 86400
    rows = [s for s in d["skips"]
            if s["market"] == market and s["segment"] == segment and s["ts"] >= cut]
    res = [s for s in rows if s.get("resolved")]
    good = sum(1 for s in res if str(s.get("verdict", "")).startswith("good"))
    bad = sum(1 for s in res if str(s.get("verdict", "")).startswith("bad"))
    return {"n": len(rows), "resolved": len(res), "good_skips": good,
            "bad_skips_missed_winners": bad,
            "pending": len(rows) - len(res)}


def autonomy_gates(market: str, segment: str) -> dict:
    """vp0's earn-autonomy checklist. ALL gates must pass before size-up/live."""
    from trading import goal
    sb = goal.last_scoreboard() or goal.scoreboard()
    seg = (sb.get("segments") or {}).get(f"{market}.{segment}", {})
    base = baseline_stats(market, segment)
    d = _store()
    recent_failures = [f for f in d["failures"] if f["ts"] >= time.time() - 7 * 86400]
    # brain return vs blind baseline mean (both as window returns; baseline is per-trade
    # mean — beats-baseline means positive AND better than taking everything blindly)
    brain_ret = seg.get("return_window")
    blind = base.get("mean_ret_24h_pct")
    beats = (brain_ret is not None and blind is not None
             and brain_ret > 0 and brain_ret * 100 > blind)
    gates = {
        "paper_days_30_positive": seg.get("verdict") in ("toward-goal", "goal-met"),
        "min_100_trades": (seg.get("n_trades") or 0) >= 100,
        "beats_blind_baseline": bool(beats),
        "no_recent_data_failures": len(recent_failures) == 0,
        "drawdown_sane": (seg.get("max_drawdown") is not None
                          and seg.get("max_drawdown") <= seg.get("dd_limit", 0.2)),
    }
    return {"market": market, "segment": segment, "gates": gates,
            "all_pass": all(gates.values()),
            "detail": {"scoreboard": seg, "baseline": base,
                       "recent_data_failures": len(recent_failures)}}


def watchdogs() -> dict:
    """Fee-bleed + frozen-activity alarms over the canonical journal (vp1's lessons)."""
    out = {"generated_ts": time.time(), "alarms": []}
    try:
        from trading.journal import TradeJournal
        rows = [t.to_dict() for t in
                TradeJournal(state_file="journal.json", persist=True).trades]
    except Exception as e:
        return {"error": f"journal unavailable: {e!r}"[:120], "alarms": []}
    cut = time.time() - 7 * 86400
    import datetime as dt

    def _ts(r):
        try:
            return dt.datetime.strptime(str(r.get("exit_datetime"))[:19],
                                        "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            return 0
    recent = [r for r in rows if _ts(r) >= cut]
    fees = sum(abs(float(r.get("total_charges") or 0)) for r in recent)
    gross = sum(abs(float(r.get("gross_pnl") or 0)) for r in recent)
    net = sum(float(r.get("net_pnl") or 0) for r in recent)
    if gross > 0:
        ratio = fees / gross
        out["fee_bleed"] = {"fees_7d": round(fees, 2), "gross_7d": round(gross, 2),
                            "net_7d": round(net, 2), "fee_ratio": round(ratio, 4)}
        if ratio > 0.35 and net < 0:
            out["alarms"].append(
                f"FEE BLEED: fees are {ratio:.0%} of gross P&L and net is negative "
                f"({net:.2f}) — the slow-leak failure mode (vp1). Review trade frequency.")
    last_ts = max((_ts(r) for r in rows), default=0)
    idle_h = (time.time() - last_ts) / 3600 if last_ts else None
    out["last_closed_trade_h_ago"] = round(idle_h, 2) if idle_h is not None else None
    if idle_h is not None and idle_h > 24:
        out["alarms"].append(
            f"FROZEN ACTIVITY: no closed trade in {idle_h:.0f}h while loops run — "
            "check funnels/engines (the balance-stopped-changing failure mode).")
    try:
        from trading.brain import mind_events
        for a in out["alarms"]:
            mind_events.emit("alarm", a, salience=0.9)
    except Exception:
        pass
    return out


def status() -> dict:
    d = _store()
    segs = sorted({(b["market"], b["segment"]) for b in d["baseline"]}
                  | {(s["market"], s["segment"]) for s in d["skips"]})
    return {"segments": {f"{m}.{s}": {"baseline": baseline_stats(m, s),
                                      "skips": skip_stats(m, s),
                                      "autonomy": autonomy_gates(m, s)}
                         for m, s in segs},
            "watchdogs": watchdogs(),
            "n_baseline": len(d["baseline"]), "n_skips": len(d["skips"])}
