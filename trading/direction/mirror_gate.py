"""trading/direction/mirror_gate.py — D2: the Mirror Gate (goal Pillar 27).

Turns the Truth Ledger's measurements into a live correction at every entry decision:
a signal source whose measured direction accuracy is RELIABLY below chance gets its
vote INVERTED (a 30%-accurate source pointed the other way is a 70%-accurate source);
a source PROVEN to be a coin flip gets ABSTAINED; everything else passes through —
including unproven sources, because blocking exploration would starve the very ledger
that proves things (paper mode's job is to learn).

The statistics are deliberately conservative (SOTA research note, area 5: blanket
inversion only works when errors are STABLE — so we demand the whole Wilson interval,
not the point rate, to clear the bar):
  INVERT  — n ≥ MIRROR_MIN_N and CI_HIGH < MIRROR_INVERT_CI (default 0.45): even the
            optimistic read says it's wrong → flip the direction.
  ABSTAIN — n ≥ 4×MIRROR_MIN_N and the ENTIRE CI inside (INVERT_CI, TRUST_CI): a
            proven coin flip teaches nothing and costs fees → skip the entry.
  PASS    — everything else (trusted or not-yet-proven).

Inverted decisions are re-recorded in the Truth Ledger under source "mirror:<source>"
so the flipped signal must EARN its own measured track record — the gate never grades
its own homework.

Levers: MIRROR_GATE=0 disables (pass-through), MIRROR_MIN_N (default 30),
MIRROR_INVERT_CI (0.45), MIRROR_TRUST_CI (0.55), MIRROR_HORIZON (1h — the gate judges
sources on fixed-horizon truth, never the exit-path-polluted "exit" labels).
"""
from __future__ import annotations

import os
import time

from trading import state

_AGG = "direction_truth.json"                  # written by truth_ledger
_CACHE: dict = {"ts": 0.0, "buckets": None}
_CACHE_TTL_S = 60.0


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _enabled() -> bool:
    return os.environ.get("MIRROR_GATE", "1") in ("1", "true", "TRUE", "yes", "on")


def _buckets() -> dict:
    """source → regime → horizon → {n, correct}, cached ~60s (gate runs per candidate)."""
    now = time.time()
    if _CACHE["buckets"] is not None and now - _CACHE["ts"] < _CACHE_TTL_S:
        return _CACHE["buckets"]
    out: dict = {}
    for key, b in (state.load_json(_AGG, {}).get("buckets") or {}).items():
        try:
            source, regime, horizon = key.rsplit("|", 2)
        except ValueError:
            continue
        out.setdefault(source, {}).setdefault(regime, {})[horizon] = {
            "n": int(b.get("n", 0)), "correct": int(b.get("correct", 0))}
    _CACHE.update(ts=now, buckets=out)
    return out


def _lookup(source: str, regime: str | None, horizon: str) -> tuple[int, int, str]:
    """(n, correct, bucket_used). Exact regime bucket first; else the source's counts
    summed across regimes at that horizon (more evidence beats finer conditioning
    until the per-regime bucket has its own n)."""
    src = _buckets().get(source) or {}
    exact = (src.get(regime or "") or {}).get(horizon)
    min_n = int(_env_f("MIRROR_MIN_N", 30))
    if exact and exact["n"] >= min_n:
        return exact["n"], exact["correct"], f"{source}|{regime}|{horizon}"
    n = c = 0
    for reg_map in src.values():
        b = reg_map.get(horizon)
        if b:
            n += b["n"]
            c += b["correct"]
    return n, c, f"{source}|*|{horizon}"


def decide(direction: str, *, source: str, regime: str | None = None,
           horizon: str | None = None) -> dict:
    """Gate one directional claim. Returns
    {"direction": "LONG"/"SHORT"/None, "action": pass|invert|abstain|off,
     "rate", "ci_low", "ci_high", "n", "bucket"} — direction=None means abstain.
    Never raises; unknown inputs pass through unchanged (the honest default)."""
    d = (direction or "").upper()
    out = {"direction": d if d in ("LONG", "SHORT") else None, "action": "pass",
           "rate": None, "ci_low": None, "ci_high": None, "n": 0, "bucket": None}
    try:
        if d not in ("LONG", "SHORT"):
            return out
        if not _enabled():
            out["action"] = "off"
            return out
        from trading.direction.truth_ledger import _wilson
        hz = horizon or os.environ.get("MIRROR_HORIZON", "1h")
        n, c, bucket = _lookup(str(source), regime, hz)
        out["bucket"] = bucket
        out["n"] = n
        min_n = int(_env_f("MIRROR_MIN_N", 30))
        if n < min_n:
            return out                              # unproven → let it explore
        rate, lo, hi = _wilson(c, n)
        invert_ci = _env_f("MIRROR_INVERT_CI", 0.45)
        trust_ci = _env_f("MIRROR_TRUST_CI", 0.55)
        out.update(rate=round(rate, 4), ci_low=round(lo, 4), ci_high=round(hi, 4))
        if hi < invert_ci:                          # reliably wrong → mirror it
            out["direction"] = "SHORT" if d == "LONG" else "LONG"
            out["action"] = "invert"
        elif n >= 4 * min_n and lo > invert_ci and hi < trust_ci:
            out["direction"] = None                 # proven coin flip → don't pay fees
            out["action"] = "abstain"
        return out
    except Exception:
        return out                                  # trading loop safety: pass-through


def apply(direction: str, *, source: str, symbol: str = "", market: str = "CRYPTO",
          segment: str = "futures", regime: str | None = None,
          confidence: float | None = None) -> tuple[str | None, dict]:
    """decide() + the self-measuring loop: an INVERTED claim is recorded in the Truth
    Ledger as source "mirror:<source>" so the flip earns its own track record.
    Returns (final_direction_or_None, gate_info)."""
    g = decide(direction, source=source, regime=regime)
    if g["action"] == "invert" and g["direction"] and symbol:
        try:
            from trading.direction import truth_ledger
            truth_ledger.record(symbol=symbol, market=market, segment=segment,
                                direction=g["direction"], source=f"mirror:{source}",
                                confidence=confidence, regime=regime)
        except Exception:
            pass
    return g["direction"], g


def status() -> dict:
    """Dashboard/inspection: current thresholds + every bucket the gate would act on."""
    from trading.direction.truth_ledger import _wilson
    min_n = int(_env_f("MIRROR_MIN_N", 30))
    invert_ci = _env_f("MIRROR_INVERT_CI", 0.45)
    trust_ci = _env_f("MIRROR_TRUST_CI", 0.55)
    hz = os.environ.get("MIRROR_HORIZON", "1h")
    acts = []
    for source, regs in _buckets().items():
        n = c = 0
        for reg_map in regs.values():
            b = reg_map.get(hz)
            if b:
                n += b["n"]
                c += b["correct"]
        if n < min_n:
            continue
        rate, lo, hi = _wilson(c, n)
        action = ("invert" if hi < invert_ci else
                  "abstain" if n >= 4 * min_n and lo > invert_ci and hi < trust_ci
                  else "trusted" if lo > trust_ci else "pass")
        if action != "pass":
            acts.append({"source": source, "horizon": hz, "n": n,
                         "rate": round(rate, 4), "ci_low": round(lo, 4),
                         "ci_high": round(hi, 4), "action": action})
    acts.sort(key=lambda a: a["rate"])
    return {"enabled": _enabled(), "horizon": hz, "min_n": min_n,
            "invert_ci": invert_ci, "trust_ci": trust_ci, "active": acts}
