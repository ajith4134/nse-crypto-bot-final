"""trading/brain/surface.py — W2 scientific-method rails for EVERY self-tuning optimizer.

Owner goal 2026-07-07 (videos: self-improving-agent §surface-split + one-variable;
vp0 §versioned rules): the brain has MANY optimizers (tailgate learner, self-evolve,
foundry, per-coin decider, funnel adaptive budget, picker weights…). Without rails two
of them can fight over the same knob, changes are unattributed, and multi-variable
jumps make outcomes unexplainable. This module gives every optimizer:

  1. OWNERSHIP — a declared parameter surface (dotted knob patterns) per optimizer;
     writes outside your surface are refused (Hermes-vs-Cornelius split).
  2. MODE — read_only | live per optimizer. NEW optimizers default to read_only
     (their first cycles produce reviews, not writes) until the owner/boss flips them.
  3. ONE-VARIABLE-ONLY — within one reflection window (goal.yaml `reflection_every_days`,
     default 7) an optimizer may change ONE distinct knob per market.segment scope —
     the scientific method: otherwise you can't attribute the outcome.
  4. RULE VERSIONS — every accepted change is a versioned ledger entry
     (vN → vN+1, old, new, evidence, reason) in state:rule_versions.json —
     "the dashboard shows the old rule, the new rule and the evidence" (vp0).

Usage (an optimizer wraps its knob write):

    from trading.brain import surface
    ok = surface.record_change("tailgate-learner", knob="tailgate.distance_pct.crypto.futures",
                               old=0.5, new=0.44, evidence={"n_trades": 31, "capture": 0.62},
                               reason="captured/peak below target — tighten trail")
    if ok["allowed"]:
        ... apply the write ...

Honesty rules: refusals are RECORDED (refused_log) not silent; enforcement never raises
(a broken rail must not take down a trading loop) — on internal error it allows the
write but flags {"rail_error": ...} so the gap is visible, never hidden.
"""
from __future__ import annotations

import fnmatch
import time

from trading import state

_LEDGER_FILE = "rule_versions.json"
_MODES_FILE = "optimizer_modes.json"
_REFUSED_FILE = "surface_refusals.json"

# ── THE ownership map (single source of truth; extend when a new optimizer is born) ──
# knob patterns are dotted, fnmatch-style. NO two optimizers may match the same knob.
OWNERSHIP: dict[str, list[str]] = {
    # ratcheting locked-profit exit — owns its trail distances only
    "tailgate-learner":   ["tailgate.distance_pct.*"],
    # DEAP/NSGA-II + generator portfolio — owns admitted-strategy params + retirement
    "self-evolve":        ["strategy.evolved.*", "skill_library.retire.*"],
    # institutional strategy foundry — owns its per-segment strategy rankings
    "foundry":            ["strategy.foundry.*"],
    # per-coin decider — owns per-coin strategy choice weights
    "percoin-decider":    ["percoin.choice.*", "percoin.brain_weight.*"],
    # broker-picker fusion — owns regime-aware picker weights
    "picker-weights":     ["funnel.picker_weight.*"],
    # funnel budget governor — owns its own adaptive shortlist size
    "funnel-budget":      ["funnel.shortlist_n.*"],
    # conformal gate calibration — owns its abstention thresholds
    "uq-calibrator":      ["uq.threshold.*"],
    # the human owner via dashboard/boss — owns capital, live flags, goal numbers
    "boss":               ["goal.*", "capital.*", "live.*", "segments.*"],
}

# optimizers that already ran in production BEFORE the rails existed keep working
# (grandfathered to live); anything not listed starts read_only.
_GRANDFATHERED_LIVE = {"tailgate-learner", "self-evolve", "foundry", "percoin-decider",
                       "picker-weights", "funnel-budget", "uq-calibrator", "boss"}


# ── ownership / mode ──────────────────────────────────────────────────────────────────
def owner_of(knob: str) -> str | None:
    for opt, pats in OWNERSHIP.items():
        if any(fnmatch.fnmatch(knob, p) for p in pats):
            return opt
    return None


def can_write(optimizer: str, knob: str) -> tuple[bool, str]:
    own = owner_of(knob)
    if own is None:
        return False, f"knob '{knob}' is unowned — add it to surface.OWNERSHIP first"
    if own != optimizer:
        return False, f"knob '{knob}' is owned by '{own}' (surface split)"
    if mode(optimizer) != "live":
        return False, f"optimizer '{optimizer}' is read_only (first-cycle review mode)"
    return True, "ok"


def mode(optimizer: str) -> str:
    modes = state.load_json(_MODES_FILE, {})
    if optimizer in modes:
        return str(modes[optimizer])
    return "live" if optimizer in _GRANDFATHERED_LIVE else "read_only"


def set_mode(optimizer: str, new_mode: str, *, by: str = "owner") -> dict:
    """Flip read_only|live (dashboard/boss action). Recorded in the ledger."""
    assert new_mode in ("read_only", "live")
    modes = state.load_json(_MODES_FILE, {})
    old = mode(optimizer)
    modes[optimizer] = new_mode
    state.save_json(_MODES_FILE, modes)
    _append_ledger({"ts": time.time(), "optimizer": optimizer, "knob": f"mode.{optimizer}",
                    "old": old, "new": new_mode, "evidence": {"by": by},
                    "reason": "mode flip", "version": None})
    return {"optimizer": optimizer, "mode": new_mode, "was": old}


# ── one-variable-only window ──────────────────────────────────────────────────────────
def _window_days() -> float:
    try:
        from trading import goal
        g = goal.load_goals()
        return float((g.get("defaults") or {}).get("reflection_every_days", 7))
    except Exception:
        return 7.0


def _one_variable_enabled() -> bool:
    try:
        from trading import goal
        return bool((goal.load_goals().get("defaults") or {}).get("one_variable_only", True))
    except Exception:
        return True


def _scope_of(knob: str) -> str:
    """one-variable scope = the trailing market/segment qualifier when present,
    else the knob family — e.g. tailgate.distance_pct.crypto.futures → crypto.futures."""
    parts = knob.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 4 else ".".join(parts[:2])


def _recent_changes(optimizer: str, since_s: float) -> list[dict]:
    led = state.load_json(_LEDGER_FILE, [])
    return [e for e in led
            if e.get("optimizer") == optimizer and e.get("ts", 0) >= since_s
            and e.get("version") is not None]


# ── the write gate + ledger ───────────────────────────────────────────────────────────
def _append_ledger(entry: dict) -> None:
    led = state.load_json(_LEDGER_FILE, [])
    led.append(entry)
    state.save_json(_LEDGER_FILE, led[-2000:])          # bounded, newest kept


def record_change(optimizer: str, *, knob: str, old, new, evidence: dict | None = None,
                  reason: str = "") -> dict:
    """THE gate every optimizer calls BEFORE writing a knob.

    Returns {"allowed": bool, "reason": str, "version": int|None}. Refusals are logged
    (surface_refusals.json) so the dashboard can show what was blocked and why."""
    try:
        ok, why = can_write(optimizer, knob)
        if ok and _one_variable_enabled():
            window_s = _window_days() * 86400.0
            scope = _scope_of(knob)
            recent = [e for e in _recent_changes(optimizer, time.time() - window_s)
                      if _scope_of(e.get("knob", "")) == scope
                      and e.get("knob") != knob]
            if recent:
                ok = False
                why = (f"one-variable-only: '{recent[-1]['knob']}' already changed in "
                       f"scope '{scope}' this {_window_days():g}-day window")
        if not ok:
            ref = state.load_json(_REFUSED_FILE, [])
            ref.append({"ts": time.time(), "optimizer": optimizer, "knob": knob,
                        "old": old, "new": new, "reason": why})
            state.save_json(_REFUSED_FILE, ref[-500:])
            return {"allowed": False, "reason": why, "version": None}
        prior = [e for e in state.load_json(_LEDGER_FILE, [])
                 if e.get("knob") == knob and e.get("version") is not None]
        version = (prior[-1]["version"] + 1) if prior else 1
        _append_ledger({"ts": time.time(), "optimizer": optimizer, "knob": knob,
                        "old": old, "new": new, "evidence": evidence or {},
                        "reason": reason, "version": version})
        try:                        # W7 meta-article: rule changes compound into memory
            from trading.brain import track_record as _tr
            _tr.bump(f"optimizer:{optimizer}", kind="optimizer",
                     note=f"{knob} v{version}: {old}→{new}")
            _tr.meta_note(f"optimizer:{optimizer}",
                          what=f"changed {knob} from {old} to {new} (v{version})",
                          why=reason, cost=str(evidence or ""))
        except Exception:
            pass
        return {"allowed": True, "reason": "ok", "version": version}
    except Exception as e:                        # a broken rail must never stop trading
        return {"allowed": True, "reason": "ok", "version": None,
                "rail_error": f"{type(e).__name__}: {e}"[:120]}


def status() -> dict:
    """Dashboard feed: ownership map, modes, last changes, last refusals."""
    led = state.load_json(_LEDGER_FILE, [])
    return {"ownership": OWNERSHIP,
            "modes": {opt: mode(opt) for opt in OWNERSHIP},
            "one_variable_only": _one_variable_enabled(),
            "window_days": _window_days(),
            "recent_changes": led[-25:],
            "recent_refusals": state.load_json(_REFUSED_FILE, [])[-25:]}
