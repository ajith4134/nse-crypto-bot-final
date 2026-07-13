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

The judgement pools ALL the clean fixed horizons (15m+1h+4h by default), never the
exit-path-polluted "exit" label. Pooling is what makes the "errors must be STABLE"
test real: a source only wrong at one horizon (e.g. funnel_mtf_vote, 30% at 1h but
~50% at 15m/4h) sees its combined CI widen back over the bar and is left alone, while
a source wrong at EVERY horizon (meanrev_stochrsi: 31/38/42%) pools to a tight
sub-chance CI and is confidently inverted. More evidence → tighter interval → the
gate acts only on stable, horizon-agnostic anti-signals.

Levers: MIRROR_GATE=0 disables (pass-through), MIRROR_MIN_N (default 30),
MIRROR_INVERT_CI (0.45), MIRROR_TRUST_CI (0.55), MIRROR_HORIZONS (default "15m,1h,4h",
the clean set the gate pools; "exit" is always dropped). MIRROR_HORIZON stays as a
back-compat single-horizon override for callers that pass an explicit horizon.
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
    """market → source → regime → horizon → {n, correct}, cached ~60s (gate runs per
    candidate). Market-nested so the gate never pools a source's crypto and NSE outcomes
    when judging one market's claim (isolation, 2026-07-13)."""
    now = time.time()
    if _CACHE["buckets"] is not None and now - _CACHE["ts"] < _CACHE_TTL_S:
        return _CACHE["buckets"]
    out: dict = {}
    for key, b in (state.load_json(_AGG, {}).get("buckets") or {}).items():
        try:
            source, market, regime, horizon = key.rsplit("|", 3)
        except ValueError:
            continue                                 # legacy 3-part key (pre-market) → skip
        out.setdefault(market.upper(), {}).setdefault(source, {}).setdefault(regime, {})[
            horizon] = {"n": int(b.get("n", 0)), "correct": int(b.get("correct", 0))}
    _CACHE.update(ts=now, buckets=out)
    return out


def _sources_for(market: str | None) -> dict:
    """source → regime → horizon map for one market, or all markets pooled when market is
    None (legacy back-compat; callers should pass a market to keep isolation)."""
    bmk = _buckets()
    if market:
        return bmk.get(market.upper(), {})
    merged: dict = {}
    for smap in bmk.values():                        # pool every market (legacy path only)
        for source, regs in smap.items():
            for reg, hz in regs.items():
                dst = merged.setdefault(source, {}).setdefault(reg, {})
                for h, v in hz.items():
                    cur = dst.setdefault(h, {"n": 0, "correct": 0})
                    cur["n"] += v["n"]
                    cur["correct"] += v["correct"]
    return merged


def _horizons() -> list[str]:
    """The clean fixed horizons the gate pools — "exit" is never one of them (its
    labels are polluted by exit timing, not the entry direction being judged)."""
    raw = os.environ.get("MIRROR_HORIZONS", "15m,1h,4h")
    hs = [h.strip() for h in raw.split(",") if h.strip() and h.strip() != "exit"]
    return hs or ["1h"]


def _lookup(source: str, regime: str | None, horizons: list[str],
            market: str | None = None) -> tuple[int, int, str]:
    """(n, correct, bucket_used) POOLED across the given clean horizons, WITHIN one market.
    Exact regime (summed over the horizons) first; else the source summed across regimes AND
    horizons — more evidence beats finer conditioning until the per-regime bucket has its own n."""
    src = _sources_for(market).get(source) or {}
    min_n = int(_env_f("MIRROR_MIN_N", 30))
    tag = "+".join(horizons)
    reg_map = src.get(regime or "") or {}
    en = ec = 0
    for hz in horizons:
        b = reg_map.get(hz)
        if b:
            en += b["n"]
            ec += b["correct"]
    if en >= min_n:
        return en, ec, f"{source}|{regime}|{tag}"
    n = c = 0
    for rm in src.values():
        for hz in horizons:
            b = rm.get(hz)
            if b:
                n += b["n"]
                c += b["correct"]
    return n, c, f"{source}|*|{tag}"


def decide(direction: str, *, source: str, regime: str | None = None,
           horizon: str | None = None, market: str | None = None) -> dict:
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
        # explicit horizon (or the MIRROR_HORIZON back-compat override) → judge that
        # single horizon; otherwise POOL the clean fixed horizons for a tighter interval.
        single = horizon or os.environ.get("MIRROR_HORIZON")
        horizons = [single] if single else _horizons()
        n, c, bucket = _lookup(str(source), regime, horizons, market)
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
    g = decide(direction, source=source, regime=regime, market=market)
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
    single = os.environ.get("MIRROR_HORIZON")
    horizons = [single] if single else _horizons()
    hz = "+".join(horizons)
    acts = []
    for market, smap in _buckets().items():
        for source, regs in smap.items():
            n = c = 0
            for reg_map in regs.values():
                for h in horizons:
                    b = reg_map.get(h)
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
                acts.append({"source": source, "market": market, "horizon": hz, "n": n,
                             "rate": round(rate, 4), "ci_low": round(lo, 4),
                             "ci_high": round(hi, 4), "action": action})
    acts.sort(key=lambda a: a["rate"])
    return {"enabled": _enabled(), "horizon": hz, "min_n": min_n,
            "invert_ci": invert_ci, "trust_ci": trust_ci, "active": acts}
