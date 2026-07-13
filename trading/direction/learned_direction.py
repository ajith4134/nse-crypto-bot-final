"""trading/direction/learned_direction.py — D10: the learned direction DRIVER (goal Pillar 27).

Replaces the naive `funnel._vote` ("≥2 timeframes agree") — measured on the Truth Ledger as a
~47% near-random signal overall and a 38-42% *anti*-signal in trends — with a decision that is
weighted by how often each source has ACTUALLY been right.

The primitive is Hedge / multiplicative-weights (the literal "learn from being wrong in one
observation" rule, recommended by the 2026-07-12 SOTA research pass): every directional source
carries a weight = its Wilson-honest measured *edge* over 0.5 (from truth_ledger.source_reliability).

  • a source measured near 50% (the mtf vote) earns ~0 weight and stops driving trades;
  • a source measured reliably BELOW 50% is INVERTED (its p_up flips) and then contributes with
    positive weight — a proven anti-signal becomes a real signal;
  • a source measured reliably ABOVE 50% (venue_leadlag 0.54, funding_extreme/app_indicators 0.56)
    dominates in proportion to its edge;
  • when no source has a proven edge, the decider ABSTAINS (neutral) rather than force a coin-flip
    trade — the fix for "symbols that pass all votes open and lose".

As the ledger keeps scoring outcomes, the weights self-correct with no retraining: the gate gets
better at exactly the decisions it used to get wrong. Pure functions + a short reliability cache;
never raises, no network. `META_ENGINE`-style dials live in env (see _CFG).

Next-gen (research follow-on, not yet wired here): a River SRPClassifier learn_one per resolved
outcome for a faster online second opinion, and crepes online-conformal abstention at a risk α.
"""
from __future__ import annotations

import math
import os
import time

from trading.direction import truth_ledger as _tl


# ── tunables (env-overridable; sane measured defaults) ───────────────────────────────
def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _cfg() -> dict:
    return {
        # a source needs at least this many scored outcomes before we trust its edge
        "min_n": int(_f("LEARNED_DIR_MIN_N", 30)),
        # ignore edges smaller than this effect size — |rate-0.5| must clear it to earn weight
        # (0.03 ⇒ the ~47.3% near-random mtf vote is ignored; 54-56% lenses still count)
        "min_edge": _f("LEARNED_DIR_MIN_EDGE", 0.03),
        # total edge-weight below this ⇒ abstain (no proven signal at all)
        "min_total_w": _f("LEARNED_DIR_MIN_TOTAL_W", 0.015),
        # |p-0.5| must clear this band to call a side (else neutral)
        "band": _f("LEARNED_DIR_BAND", 0.02),
        # weight given to an UNPROVEN source (n<min_n) so early-life behaves like the old vote
        "unproven_w": _f("LEARNED_DIR_UNPROVEN_W", 0.01),
        "cache_ttl": _f("LEARNED_DIR_CACHE_TTL", 20.0),
    }


# ── reliability cache (truth_ledger reads the aggregate JSON each call; cache briefly) ─
_CACHE: dict[tuple, tuple[float, dict]] = {}


def reliability(source: str, regime: str | None = None) -> dict:
    """Cached truth_ledger.source_reliability(source, regime) with a regime→any fallback:
    prefer the regime-specific measurement, fall back to the across-regime rollup when the
    regime bucket is too thin. Returns the truth_ledger dict (rate/ci_low/ci_high/edge/n)."""
    ttl = _cfg()["cache_ttl"]
    key = (source, (regime or "").lower() or None)
    hit = _CACHE.get(key)
    if hit and (time.monotonic() - hit[0]) < ttl:
        return hit[1]
    rel = _tl.source_reliability(source, regime=regime, min_n=1)
    # thin regime bucket → back off to the source's across-regime measurement
    if (rel.get("n") or 0) < _cfg()["min_n"] and regime:
        allr = _tl.source_reliability(source, regime=None, min_n=1)
        if (allr.get("n") or 0) > (rel.get("n") or 0):
            rel = allr
    _CACHE[key] = (time.monotonic(), rel)
    return rel


def clear_cache() -> None:
    _CACHE.clear()


def _signed_weight(rel: dict, cfg: dict) -> tuple[float, bool]:
    """(weight, invert) for a source from its measured reliability.

    weight is the Wilson-HONEST edge magnitude (so small-n or wide-CI sources earn little);
    invert=True when the source is measured reliably below 0.5 (flip its p_up before use).
    Unproven (n<min_n) → tiny weight, no inversion (behave like the raw signal early)."""
    n = rel.get("n") or 0
    rate = rel.get("rate")
    if rate is None or n < cfg["min_n"]:
        return cfg["unproven_w"], False
    lo, hi = rel.get("ci_low"), rel.get("ci_high")
    lo = lo if lo is not None else rate
    hi = hi if hi is not None else rate
    # SIGNIFICANCE gate (Wilson): the CI must exclude 0.5, else the source is not measurably
    # different from a coin flip and earns no weight. Real trading edges are small, so the
    # weight MAGNITUDE is the point estimate |rate-0.5| (not the barely-clearing CI bound) —
    # gated by min_edge so a statistically-significant-but-tiny bias (the 47.3% vote) is dropped.
    if lo > 0.5:
        edge, invert = rate - 0.5, False          # reliably RIGHT
    elif hi < 0.5:
        edge, invert = 0.5 - rate, True           # reliably WRONG → invert its p_up
    else:
        return 0.0, (rate < 0.5)                  # CI straddles 0.5 → no significant edge
    if edge < cfg["min_edge"]:
        return 0.0, invert                        # significant but effect too small → ignore
    return edge, invert


def decide(readings, *, market: str = "", segment: str = "",
           regime: str | None = None) -> dict:
    """Fuse directional lens readings into ONE learned decision, weighting each by measured edge.

    readings: iterable of (source, p_up) — p_up in [0,1], the source's probability of LONG.
              `source` must be a Truth-Ledger source name (indicator_fusion, venue_leadlag,
              funding_extreme, strategy_library, app_indicators, funnel_mtf_vote, …).

    Returns {direction: long|short|neutral, p_up, confidence, weights, abstained, n_sources}.
    confidence is the total honest edge-weight; abstained=True ⇒ no proven signal → do not trade.
    """
    cfg = _cfg()
    num = 0.0          # Σ w·(p_cal - 0.5)
    tot_w = 0.0
    weights: dict[str, dict] = {}
    for source, p_up in readings:
        if p_up is None:
            continue
        try:
            p = float(p_up)
        except (TypeError, ValueError):
            continue
        p = min(1.0, max(0.0, p))
        rel = reliability(source, regime)
        w, invert = _signed_weight(rel, cfg)
        if w <= 0.0:
            weights[source] = {"w": 0.0, "invert": invert, "rate": rel.get("rate"),
                               "n": rel.get("n")}
            continue
        p_cal = (1.0 - p) if invert else p
        num += w * (p_cal - 0.5)
        tot_w += w
        weights[source] = {"w": round(w, 4), "invert": invert,
                           "rate": rel.get("rate"), "n": rel.get("n"),
                           "p_used": round(p_cal, 4)}
    if tot_w < cfg["min_total_w"]:
        return {"direction": "neutral", "p_up": 0.5, "confidence": round(tot_w, 4),
                "weights": weights, "abstained": True, "n_sources": len(weights)}
    p_final = 0.5 + num / tot_w
    p_final = min(1.0, max(0.0, p_final))
    band = cfg["band"]
    if p_final > 0.5 + band:
        direction = "long"
    elif p_final < 0.5 - band:
        direction = "short"
    else:
        direction = "neutral"
    return {"direction": direction, "p_up": round(p_final, 4),
            "confidence": round(tot_w, 4), "weights": weights,
            "abstained": direction == "neutral", "n_sources": len(weights)}


def correct_direction(direction: str, *, source: str, market: str = "",
                      segment: str = "", regime: str | None = None) -> tuple[str, dict]:
    """Single-claim correction for lanes that carry an already-chosen direction (the Reflex
    fast lane / armed pullbacks), where the rich multi-lens fusion isn't available at fire time.

    INVERTS the direction only when its SOURCE is measured reliably WRONG with a significant edge
    (the same Wilson-honest bar as decide()); otherwise passes it through unchanged. It never
    ABSTAINS here on purpose: a triggered pullback whose source has no proven edge still opens
    (exploration earns the source its track record), so this only fixes proven anti-signals and
    never reduces trade flow. Returns (direction, info). Never raises.
    """
    d = (direction or "").upper()
    if d not in ("LONG", "SHORT"):
        return direction, {"action": "pass", "reason": "non-directional"}
    try:
        rel = reliability(source, regime)
        w, invert = _signed_weight(rel, _cfg())
        if invert and w > 0.0:                       # significant, reliably-wrong source → flip
            newd = "SHORT" if d == "LONG" else "LONG"
            return newd, {"action": "invert", "from": d, "source": source,
                          "rate": rel.get("rate"), "n": rel.get("n"),
                          "regime": regime}
        return d, {"action": "pass", "source": source, "rate": rel.get("rate"),
                   "n": rel.get("n")}
    except Exception as e:
        return d, {"action": "pass", "error": str(e)[:120]}


# ── drop-in replacement for funnel._vote (cheap gate over the multi-TF chart) ─────────
def learned_vote(chart: dict, *, market: str = "crypto", segment: str = "futures",
                 regime: str | None = None) -> tuple[str, float]:
    """Same signature as funnel._vote → (direction, p_up), but the mtf reading is passed through
    the learned decider as the `funnel_mtf_vote` source. Because that source measures ~47%
    (near-random) / trend-anti, this attenuates or INVERTS it instead of trading it raw — the
    cheap gate stops forcing losing trades while still handing the deep-verify lenses candidates.

    Neutral/degenerate charts and a genuinely no-edge vote both return ('neutral', mean).
    """
    ps = [c["p_up"] for c in chart.values()
          if isinstance(c, dict) and c.get("source") != "unavailable"
          and c.get("p_up") is not None]
    if not ps:
        return "neutral", 0.5
    mean = sum(ps) / len(ps)
    out = decide([("funnel_mtf_vote", mean)], market=market, segment=segment, regime=regime)
    if out["abstained"]:
        # no proven edge from the vote → stay neutral, but report the raw mean for ranking
        return "neutral", round(mean, 4)
    return out["direction"], out["p_up"]
