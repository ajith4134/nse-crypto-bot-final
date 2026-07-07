"""trading/brain/briefing.py — W8 daily morning briefing (owner goal 2026-07-07;
video vp3's Hermes-trader template).

The structured brief an experienced analyst would hand the owner every morning:

  1. REGIME GATE   — goal-scoreboard verdicts + evidence watchdog alarms (the macro
                     go/no-go before anything else).
  2. POSITIONS     — every open trade (all engines) with peak/tailgate state.
  3. SETUPS        — freshest smart-money consensus events + top funnel candidates.
  4. CLEAR STANCE  — per segment: push / hold / stand-down, from the verdicts.
  5. SIZING MATH   — from OUR capital rules (goal.yaml capital_base × 1/2/3%).

Every number carries PROVENANCE ("sources checked: … as of …") — no vibes. Generated
once per day (IST morning) by the funnel loop, on demand via the API, and delivered to
the owner through the mind-events stream (Brain Chat shows it). Read-only: the briefing
never trades.
"""
from __future__ import annotations

import datetime as dt
import time

from trading import state

_FILE = "daily_briefing.json"


def _ist_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))


def due(hour_ist: int = 8, minute_ist: int = 45) -> bool:
    """True once per IST day after the trigger time."""
    last = (state.load_json(_FILE, {}) or {}).get("date")
    now = _ist_now()
    if now.hour * 60 + now.minute < hour_ist * 60 + minute_ist:
        return False
    return last != now.strftime("%Y-%m-%d")


def generate(deliver: bool = True) -> dict:
    """Build today's briefing from REAL state only. Never raises."""
    now = _ist_now()
    sources: list[str] = []
    brief: dict = {"date": now.strftime("%Y-%m-%d"),
                   "generated_at": now.isoformat(timespec="seconds"), "sections": {}}

    # 1 ── regime gate: goal verdicts + watchdogs
    try:
        from trading import goal
        sb = goal.last_scoreboard() or goal.scoreboard()
        verd = {k: v.get("verdict") for k, v in (sb.get("segments") or {}).items()}
        brief["sections"]["regime_gate"] = {
            "verdicts": verd,
            "read": ("stand-down segments: "
                     + ", ".join(k for k, v in verd.items()
                                 if v in ("failing", "drawdown-breach"))
                     if any(v in ("failing", "drawdown-breach") for v in verd.values())
                     else "no segment is in failure — normal paper deployment")}
        sources.append(f"goal scoreboard (window {sb.get('window_days')}d, "
                       f"computed {time.strftime('%H:%M UTC', time.gmtime(sb.get('generated_ts', 0)))})")
    except Exception as e:
        brief["sections"]["regime_gate"] = {"error": str(e)[:100]}
    try:
        from trading import evidence
        wd = evidence.watchdogs()
        brief["sections"]["watchdogs"] = {"alarms": wd.get("alarms") or ["none"],
                                          "fee_bleed": wd.get("fee_bleed"),
                                          "last_closed_trade_h_ago":
                                          wd.get("last_closed_trade_h_ago")}
        sources.append("evidence-lane watchdogs (live journal)")
    except Exception:
        pass

    # 2 ── open positions (Freqtrade + paper book via the unified view)
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        ots = CryptoEngineClient().open_trades()
        brief["sections"]["open_positions_crypto"] = [
            {"pair": t.get("pair"), "segment": t.get("bot_segment"),
             "profit_pct": t.get("profit_pct"),
             "open_date": t.get("open_date")} for t in (ots or [])[:20]]
        sources.append(f"Freqtrade /status ({len(ots or [])} open, live API)")
    except Exception as e:
        brief["sections"]["open_positions_crypto"] = [{"error": str(e)[:80]}]

    # 3 ── setups: consensus events + last funnel candidates
    try:
        from trading import scouts
        st = scouts.status()
        brief["sections"]["smart_money"] = {
            "recent_consensus": st.get("recent_consensus")[-5:],
            "active_scouts": st.get("active_scouts")}
        sources.append("scout consensus store")
    except Exception:
        pass
    try:
        bs = state.load_json("broker_sense_status.json", {})
        for mkt in ("crypto", "nse"):
            ex = ((bs.get(mkt) or {}).get("stages") or {}).get("execute") or {}
            brief["sections"][f"last_cycle_{mkt}"] = {
                "entered": ex.get("entered"), "exited": ex.get("exited"),
                "cycle_s": (bs.get(mkt) or {}).get("took_s")}
        sources.append("broker-sense funnel status (latest cycles)")
    except Exception:
        pass

    # 4+5 ── stance + sizing from OUR rules
    try:
        from trading import goal
        sizing = {}
        stance = {}
        for seg_key, seg in ((goal.last_scoreboard() or {}).get("segments") or {}).items():
            market, s = seg_key.split(".", 1)
            g = goal.segment_goal(market, s)
            base = float(g["capital_base"])
            sizing[seg_key] = {"1pct": round(base * 0.01, 2),
                               "2pct": round(base * 0.02, 2),
                               "3pct": round(base * 0.03, 2),
                               "currency": "USDT" if market == "crypto" else "INR"}
            v = seg.get("verdict")
            stance[seg_key] = ("push (paper lab; goal met — consider gate review)"
                               if v == "goal-met" else
                               "hold — toward goal" if v == "toward-goal" else
                               "stand-down sizing; review rules" if v in
                               ("failing", "drawdown-breach") else
                               "explore (no-data/off-track — paper learning mode)")
        brief["sections"]["stance"] = stance
        brief["sections"]["sizing_reference"] = sizing
    except Exception:
        pass

    # 6 ── connectivity proof (#13): which features actually fired on recent trades
    try:
        from trading.connectivity_check import check as _conn
        c = _conn()
        brief["sections"]["connectivity"] = {
            "present": c["summary"]["present"], "total": c["summary"]["total"],
            "missing": [k for k, v in c["features"].items()
                        if v["status"] == "MISSING"]}
        sources.append("connectivity check (recent entry sidecars + journal)")
    except Exception:
        pass

    brief["provenance"] = "sources checked: " + "; ".join(sources) if sources else \
        "no live sources reachable"
    state.save_json(_FILE, brief)
    if deliver:
        try:
            from trading.brain import mind_events
            head = brief["sections"].get("regime_gate", {}).get("read", "")
            alarms = brief["sections"].get("watchdogs", {}).get("alarms") or []
            mind_events.emit("briefing",
                             f"[MORNING BRIEF {brief['date']}] {head}. "
                             f"Alarms: {'; '.join(a[:80] for a in alarms[:2]) or 'none'}. "
                             f"Full brief: /api/trading/briefing. ({brief['provenance'][:140]})",
                             salience=0.8)
        except Exception:
            pass
    return brief


def latest() -> dict:
    return state.load_json(_FILE, {})
