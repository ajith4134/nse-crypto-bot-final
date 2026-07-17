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
        # hierarchical shrinkage (2026-07-17): a thin REGIME bucket borrows up to this many
        # pseudo-observations from the source's across-regime pool instead of the old cliff
        # (n<min_n ⇒ ignore regime entirely; n≥min_n ⇒ ignore the parent entirely). The regime
        # dimension was dead 07-12→07-17 (classifier starved of candles), so per-regime buckets
        # are young — without borrowing, fixing the classifier would have RESET every source to
        # unproven. 0 disables (restores the step fallback).
        "shrink_k": _f("LEARNED_DIR_SHRINK_K", 24),
    }


# ── reliability cache (truth_ledger reads the aggregate JSON each call; cache briefly) ─
_CACHE: dict[tuple, tuple[float, dict]] = {}


def _blend(child: dict, parent_rate: float, parent_n: int, k: float) -> dict | None:
    """One empirical-Bayes step: the child bucket + up to k pseudo-obs at the parent rate.
    None when there is nothing to borrow (child already ≥ parent evidence)."""
    n_c, c_c = int(child.get("n") or 0), int(child.get("correct") or 0)
    if k <= 0 or parent_n <= n_c:
        return None
    borrow = min(float(k), float(parent_n - n_c))
    bc = c_c + borrow * parent_rate
    bn = n_c + borrow
    rate, lo, hi = _tl._wilson(bc, bn)
    return {"n": int(round(bn)), "correct": int(round(bc)), "rate": round(rate, 4),
            "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "edge": round(rate - 0.5, 4), "n_child": n_c, "borrowed": int(round(borrow))}


def reliability(source: str, regime: str | None = None, market: str | None = None,
                conditioners: dict | None = None) -> dict:
    """Cached truth_ledger.source_reliability with a hierarchical shrinkage chain:
    global(market) → regime → conditioner (E8: liq / clock sub-buckets). Each thinner bucket
    borrows up to shrink_k pseudo-observations from its parent, so refinement never resets
    earned trust and rich buckets dominate their parents. `market` (CRYPTO|NSE) keeps crypto
    and NSE reliability APART (isolation, 2026-07-13). Returns the truth_ledger dict."""
    ttl = _cfg()["cache_ttl"]
    m = (market or "").upper() or None
    cond_key = tuple(sorted((conditioners or {}).items())) or None
    key = (source, (regime or "").lower() or None, m, cond_key)
    hit = _CACHE.get(key)
    if hit and (time.monotonic() - hit[0]) < ttl:
        return hit[1]
    rel = _tl.source_reliability(source, market=m, regime=regime, min_n=1)
    if regime:
        k = _cfg()["shrink_k"]
        allr = _tl.source_reliability(source, market=m, regime=None, min_n=1)
        n_r, c_r = int(rel.get("n") or 0), int(rel.get("correct") or 0)
        n_a = int(allr.get("n") or 0)
        if k > 0 and n_a > n_r and allr.get("rate") is not None:
            # empirical-Bayes blend: the regime bucket + up to `k` pseudo-observations at the
            # parent (across-regime, same-market) rate. A fresh regime bucket inherits the
            # source's EARNED edge (CONVENTIONS §16: the parent pool earned it — refining by
            # regime must not reset trust); as regime evidence accumulates it dominates.
            borrow = min(float(k), float(n_a - n_r))
            bc = c_r + borrow * float(allr["rate"])
            bn = n_r + borrow
            rate, lo, hi = _tl._wilson(bc, bn)
            rel = {"n": int(round(bn)), "correct": int(round(bc)),
                   "rate": round(rate, 4), "ci_low": round(lo, 4),
                   "ci_high": round(hi, 4), "edge": round(rate - 0.5, 4),
                   "n_regime": n_r, "borrowed": int(round(borrow))}
        elif k <= 0 and n_r < _cfg()["min_n"] and n_a > n_r:
            rel = allr                          # legacy step fallback (shrink disabled)
    if conditioners:
        # E8: refine by the decision-time conditioners (liq / clock). Sequential one-step
        # blends — an approximation of a full hierarchy, chosen because the sub-buckets are
        # deliberately tiny label sets and order (sorted by kind) is deterministic.
        k = _cfg()["shrink_k"]
        for kind in sorted(conditioners):
            val = conditioners.get(kind)
            if not val:
                continue
            try:
                cb = _tl.source_reliability_conditioned(
                    source, market=m, kind=str(kind), value=str(val))
            except Exception:
                continue
            if int(cb.get("n") or 0) <= 0 or rel.get("rate") is None:
                continue
            nxt = _blend(cb, float(rel["rate"]), int(rel.get("n") or 0), k)
            if nxt is not None:
                rel = nxt
            elif int(cb.get("n") or 0) >= int(rel.get("n") or 0):
                rel = cb                        # child evidence already dominates the parent
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
        # 🚨 SECOND INVERTER KILLED 2026-07-16 (evening). The morning fix below killed inversion
        # for CI-straddlers only; this branch kept flipping sources measured CONFIDENTLY below
        # 0.5 — and bucket accuracy is NON-STATIONARY here (persistence corr −0.214), so a
        # confident yesterday-anti is a coin flip today. Measured live the same evening: the
        # market dumped, momentum/direction_model/symbol_move_net honestly voted SHORT on
        # 40-45 of 50 candidates, this branch flipped them (river 0.4365/n=14.8k poisoned-era
        # bucket, momentum 0.4669 trend bucket), and the decider opened 27 LONGs into the dump:
        # −164 USDT open, 93% of the book's loss. CONVENTIONS §16: a measured-wrong source is
        # RETRAINED or RETIRED, never inverted — direction must be EARNED, on CLEAN eras.
        return 0.0, False
    else:
        # CI straddles 0.5 → the source is NOT measurably different from a coin flip.
        # 🚨 KILLED 2026-07-16 (owner: "kill that inverter"): this used to `return 0.0, (rate < 0.5)`
        # — weight zero but STILL inverting. That flag escapes to the caller, so a source sitting at
        # 0.4999 by pure noise had its direction FLIPPED. Every live source measured that day was in
        # exactly this band (river_online 0.4456, filter:momentum 0.4657, funnel_mtf_vote 0.4765,
        # direction_model 0.4895) and all were underpowered (n~260 → ~12% power; ~540 needed).
        # Result: the brain FLIPPED NOISE. In a tape where those sources lean long, flipping them
        # shorts everything — measured live: 31 SHORT vs 1 LONG, -112 P&L, coins that rose +13%
        # shorted alongside coins that fell -13%. The bias hid for months behind spot mode (which
        # refuses shorts outright) and only surfaced when futures was fixed.
        # An unproven source is IGNORED. It is never inverted. Absence of evidence that it is right
        # is NOT evidence that its opposite is right — that is the coin-flip fallacy this rule bans
        # (CONVENTIONS §16). See [[direction-premises-falsified-20260716]]: the "invertible
        # anti-signal" premise was already falsified as an era artifact.
        return 0.0, False
    if edge < cfg["min_edge"]:
        # Significant but the effect is too small to act on → ignore the source ENTIRELY. Do not
        # invert it either: a 0.49 source is not a 0.51 source wearing a mask.
        return 0.0, False
    return edge, invert


def _log(decision: dict, *, symbol: str, market: str, regime, seam: str,
         coverage: dict | None = None) -> None:
    """Record the direction rationale so every trade's direction is auditable (owner ask)."""
    try:
        from trading.brain import direction_ledger as _dl
        _dl.record(decision, symbol=symbol, market=market, regime=str(regime or ""),
                   seam=seam, coverage=coverage)
    except Exception:
        pass


def decide(readings, *, market: str = "", segment: str = "",
           regime: str | None = None, symbol: str = "", coverage: dict | None = None,
           log: bool = True) -> dict:
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
    cond = None
    if symbol:
        try:            # E8: decision-time conditioners refine every source's weight
            cond = _tl.current_conditioners(symbol, market or "CRYPTO") or None
        except Exception:
            cond = None
    for source, p_up in readings:
        if p_up is None:
            continue
        try:
            p = float(p_up)
        except (TypeError, ValueError):
            continue
        p = min(1.0, max(0.0, p))
        rel = reliability(source, regime, market, conditioners=cond)
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
        out = {"direction": "neutral", "p_up": 0.5, "confidence": round(tot_w, 4),
               "weights": weights, "abstained": True, "n_sources": len(weights)}
        if log:
            _log(out, symbol=symbol, market=market, regime=regime, seam="decide",
                 coverage=coverage)
        return out
    p_final = 0.5 + num / tot_w
    p_final = min(1.0, max(0.0, p_final))
    band = cfg["band"]
    if p_final > 0.5 + band:
        direction = "long"
    elif p_final < 0.5 - band:
        direction = "short"
    else:
        direction = "neutral"
    out = {"direction": direction, "p_up": round(p_final, 4),
           "confidence": round(tot_w, 4), "weights": weights,
           "abstained": direction == "neutral", "n_sources": len(weights)}
    if log:
        _log(out, symbol=symbol, market=market, regime=regime, seam="decide",
             coverage=coverage)
    return out


def correct_direction(direction: str, *, source: str, market: str = "",
                      segment: str = "", regime: str | None = None,
                      symbol: str = "") -> tuple[str, dict]:
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
        rel = reliability(source, regime, market)
        w, invert = _signed_weight(rel, _cfg())
        chosen = d
        if invert and w > 0.0:                       # significant, reliably-wrong source → flip
            chosen = "SHORT" if d == "LONG" else "LONG"
            info = {"action": "invert", "from": d, "source": source,
                    "rate": rel.get("rate"), "n": rel.get("n"), "regime": regime}
        else:
            info = {"action": "pass", "source": source, "rate": rel.get("rate"),
                    "n": rel.get("n")}
        _log({"direction": chosen.lower(), "p_up": None, "confidence": w,
              "weights": {source: {"w": round(w, 4), "invert": invert,
                                   "rate": rel.get("rate"), "n": rel.get("n")}},
              "abstained": False, "n_sources": 1},
             symbol=symbol, market=market, regime=regime, seam="correct")
        return chosen, info
    except Exception as e:
        return d, {"action": "pass", "error": str(e)[:120]}


# ── drop-in replacement for funnel._vote (cheap gate over the multi-TF chart) ─────────
def learned_vote(chart: dict, *, market: str = "crypto", segment: str = "futures",
                 regime: str | None = None, symbol: str = "") -> tuple[str, float]:
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
    out = decide([("funnel_mtf_vote", mean)], market=market, segment=segment,
                 regime=regime, symbol=symbol)
    if out["abstained"]:
        # no proven edge from the vote → stay neutral, but report the raw mean for ranking
        return "neutral", round(mean, 4)
    return out["direction"], out["p_up"]
