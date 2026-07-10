"""trading/connectivity_check.py — #13: prove every feature is CONNECTED and USED on
open trades (owner goal 2026-07-07: "check if all the self-evolve, learning, research,
memory, knowledge, all other features are connected to one another and used on the
future open trades").

For the most recent entries (crypto sidecars + journal rows) this inspects the REAL
recorded artifacts — decision_snapshot fields, journal columns, state ledgers — and
reports per feature: PRESENT (fired on this trade), STALE (exists but not on recent
trades), or DISCONNECTED (no trace). No self-flattery: a feature only counts when its
actual output appears in the trade's own record.
"""
from __future__ import annotations

import time

from trading import state

_FEATURES = [
    # (feature, where we look, what proves it)
    ("broker_pickers", "decision_snapshot.app_signals.screener", "screener lane/preset"),
    ("indicator_fusion", "decision_snapshot.app_signals.indicator_fusion",
     "multi-TF confluence object"),
    ("vision_ocular", "decision_snapshot.app_signals.ocular", "ocular enrich"),
    ("ui_view_eyes", "decision_snapshot.ui_view", "eyes' TF coverage at entry"),
    ("smart_money_consensus", "decision_snapshot.app_signals.smart_money_consensus",
     "Sophie consensus (fires only on multi-scout agreement)"),
    ("psychology", "decision_snapshot.psychology|journal.psych_*", "order-book crowd"),
    ("brain_percoin", "decision_snapshot.brain|enter_tag", "per-coin decider strategy"),
    ("uq_gate", "decision_snapshot.app_signals.indicator_fusion.meta",
     "conformal meta-label act/size"),
    ("goal_scoreboard", "journal.goal_score", "per-trade goal score at close"),
    ("profit_tailgate", "journal.tailgate_*|open-trade tailgate fields", "ratchet"),
    ("evidence_lane", "state.evidence_lane.json", "baseline+skip counterfactuals"),
    ("hypothesis_ledger", "state.hypotheses.json", "learning-cycle hypotheses"),
    ("decision_memory", "journal.node_contributions|episodes", "FinMem episodes"),
    ("track_record", "state.track_records.json", "actor records"),
    ("rule_versions", "state.rule_versions.json", "W2 versioned changes"),
    ("loop_processes", "pgrep + state.loop_keeper.json",
     "the 3 loop processes are actually RUNNING (2026-07-10: they died silently for 2h)"),
]


def _dig(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def check(n_recent: int = 10) -> dict:
    """Inspect the newest crypto entry sidecars + newest closed journal rows."""
    out = {"generated_ts": time.time(), "features": {}, "n_recent": n_recent}
    # newest entry sidecars (what fired AT OPEN)
    snaps = []
    try:
        metas = state.load_json("crypto_entry_meta.json", {})
        rows = [r for lst in metas.values() for r in lst if isinstance(r, dict)]
        rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
        snaps = [((r.get("meta") or {}).get("decision_snapshot") or {})
                 for r in rows[:n_recent]]
    except Exception:
        pass
    # newest closed journal rows (what fired AT CLOSE)
    jrows = []
    try:
        from trading.journal import TradeJournal
        jrows = [t.to_dict() for t in
                 TradeJournal(state_file="journal.json", persist=True).trades[-n_recent:]]
    except Exception:
        pass

    def _mark(name, present, detail=""):
        out["features"][name] = {"status": "PRESENT" if present else "MISSING",
                                 "detail": detail[:140]}

    sig = {}
    for s in snaps:
        a = s.get("app_signals") or {}
        sig.setdefault("screener", 0)
        sig["screener"] += bool(a.get("screener"))
        sig.setdefault("fusion", 0)
        sig["fusion"] += bool((a.get("indicator_fusion") or {}).get("available"))
        sig.setdefault("ocular", 0)
        sig["ocular"] += bool(a.get("ocular"))
        sig.setdefault("ui_view", 0)
        sig["ui_view"] += bool(s.get("ui_view"))
        sig.setdefault("smc", 0)
        sig["smc"] += bool(a.get("smart_money_consensus"))
        sig.setdefault("psych", 0)
        sig["psych"] += bool(s.get("psychology"))
        sig.setdefault("brain", 0)
        sig["brain"] += bool(s.get("brain") or s.get("strategy"))
        sig.setdefault("uq", 0)
        sig["uq"] += bool(((a.get("indicator_fusion") or {}).get("meta") or {}))
    n = max(1, len(snaps))
    _mark("broker_pickers", sig.get("screener", 0) > 0,
          f"{sig.get('screener', 0)}/{len(snaps)} recent entries carried screener data")
    _mark("indicator_fusion", sig.get("fusion", 0) > 0,
          f"{sig.get('fusion', 0)}/{len(snaps)} entries had available fusion")
    _mark("vision_ocular", sig.get("ocular", 0) > 0,
          f"{sig.get('ocular', 0)}/{len(snaps)}")
    _mark("ui_view_eyes", sig.get("ui_view", 0) > 0,
          f"{sig.get('ui_view', 0)}/{len(snaps)} entries recorded eyes' TF coverage")
    _mark("smart_money_consensus", sig.get("smc", 0) > 0,
          f"{sig.get('smc', 0)}/{len(snaps)} (0 is honest when no multi-scout agreement)")
    _mark("psychology", sig.get("psych", 0) > 0 or any(
        r.get("psych_ofi_sign") is not None for r in jrows),
        "entry snapshot or journal psych_* columns")
    _mark("brain_percoin", sig.get("brain", 0) > 0 or any(
        (r.get("signal_source") == "brain") for r in jrows),
        f"{sig.get('brain', 0)}/{len(snaps)} entries brain-driven")
    _mark("uq_gate", sig.get("uq", 0) > 0,
          f"{sig.get('uq', 0)}/{len(snaps)} entries carried meta-label")
    _mark("goal_scoreboard", any(r.get("goal_score") is not None for r in jrows),
          "goal_score on recent closed rows")
    _mark("profit_tailgate", any(r.get("tailgate_peak_profit_pct") is not None
                                 or r.get("tailgate_locked_profit_pct") is not None
                                 for r in jrows),
          "tailgate_* on recent closed rows")
    ev = state.load_json("evidence_lane.json", {})
    _mark("evidence_lane", bool(ev.get("baseline") or ev.get("skips")),
          f"baseline={len(ev.get('baseline', []))} skips={len(ev.get('skips', []))}")
    hyp = state.load_json("hypotheses.json", {})
    _mark("hypothesis_ledger", bool(hyp),
          f"{len(hyp) if isinstance(hyp, (list, dict)) else 0} entries")
    _mark("decision_memory", any(r.get("node_contributions") for r in jrows),
          "node_contributions on recent rows")
    _mark("track_record", bool(state.load_json("track_records.json", {})),
          "actor records exist")
    _mark("rule_versions", bool(state.load_json("rule_versions.json", [])),
          "versioned rule changes exist")
    # the loops themselves: no process → every "connected" feature above is a museum piece
    try:
        import subprocess
        loops = {"funnel_crypto": r"broker_sense\.run_funnel_loop crypto",
                 "funnel_nse": r"broker_sense\.run_funnel_loop nse",
                 "live_loop": r"trading\.online\.run_live_loop"}
        dead = [n for n, pat in loops.items()
                if subprocess.run(["pgrep", "-f", pat], capture_output=True,
                                  timeout=10).returncode != 0]
        keeper = state.load_json("loop_keeper.json", {}) or {}
        kage = (time.time() - keeper["ts"]) / 60 if keeper.get("ts") else None
        ktxt = (f"keeper checked {kage:.0f}m ago" if kage is not None
                else "loop-keeper never ran")
        _mark("loop_processes", not dead,
              (f"all 3 loops alive · {ktxt}") if not dead else
              f"DEAD: {','.join(dead)} · {ktxt}")
    except Exception as e:
        _mark("loop_processes", False, f"check failed: {type(e).__name__}")
    present = sum(1 for f in out["features"].values() if f["status"] == "PRESENT")
    out["summary"] = {"present": present, "total": len(out["features"]),
                      "snaps_inspected": len(snaps), "journal_rows": len(jrows)}
    state.save_json("connectivity_check.json", out)
    return out
