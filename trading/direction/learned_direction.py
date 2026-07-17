"""trading/direction/learned_direction.py — D10: the learned direction DRIVER (goal Pillar 27).

Replaces the naive `funnel._vote` ("≥2 timeframes agree") — measured on the Truth Ledger as a
~47% near-random signal overall and a 38-42% *anti*-signal in trends — with a decision that is
weighted by how often each source has ACTUALLY been right.

The primitive is Hedge / multiplicative-weights (the literal "learn from being wrong in one
observation" rule, recommended by the 2026-07-12 SOTA research pass): every directional source
carries a weight = its Wilson-honest measured *edge* over 0.5 (from truth_ledger.source_reliability).

  • a source measured near 50% (the mtf vote) earns ~0 weight and stops driving trades;
  • a source measured reliably BELOW 50% is RETIRED to zero weight — NEVER inverted (both
    inverters were killed 2026-07-16 after flipping noise lost −112 and −164 on live paper;
    CONVENTIONS §16: wrong = retrain/retire, accuracy here is non-stationary);
  • a source measured reliably ABOVE 50% dominates in proportion to its RECENT edge (X-A
    half-life day-buckets, 2026-07-17 — trust follows what is right NOW, not in a stale era);
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
        # MISSION X-A (2026-07-17): evidence half-life in days. Measured drift inside ONE clean
        # day (river 0.680→0.525, momentum 0.672→0.576 between ~6h halves) means cumulative
        # pools mis-weight everything; the decayed reader makes trust follow RECENT truth.
        # 0 disables (control variant / legacy behavior).
        "half_life_d": _f("LEDGER_HALF_LIFE_D", 2.0),
        # MISSION X-F (2026-07-17): cap each source's vote MAGNITUDE. Measured on 16,525
        # clean labels: claimed confidence is uninformative-to-ANTI-informative (claims of
        # ~0.95 realize 0.490; symbol_move_net at high confidence realizes 0.398) — only the
        # SIGN carries information, so a source contributes sign × measured weight, with at
        # most this much self-reported conviction. 0.5 ≈ off (control/legacy behavior).
        "mag_cap": _f("LEARNED_DIR_MAG_CAP", 0.10),
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
                conditioners: dict | None = None, *, horizon: str | None = None,
                decayed: bool = True) -> dict:
    """Cached reliability with a hierarchical shrinkage chain:
    recent(decayed, regime) → recent(decayed, all-regime) → cumulative all-era → conditioner.
    Each thinner/fresher pool borrows up to shrink_k pseudo-observations from its parent, so
    refinement never resets earned trust, RECENT truth outranks stale truth (X-A half-life),
    and rich pools dominate. `decayed=False` (the CONTROL variant) restores the pre-mission
    cumulative-only chain. `market` keeps crypto and NSE apart (isolation, 2026-07-13)."""
    cfg = _cfg()
    ttl = cfg["cache_ttl"]
    hl = cfg["half_life_d"] if decayed else 0.0
    m = (market or "").upper() or None
    cond_key = tuple(sorted((conditioners or {}).items())) or None
    key = (source, (regime or "").lower() or None, m, cond_key, horizon, hl > 0)
    hit = _CACHE.get(key)
    if hit and (time.monotonic() - hit[0]) < ttl:
        return hit[1]
    k = cfg["shrink_k"]
    era = _tl.source_reliability(source, market=m, regime=None, horizon=horizon, min_n=1)
    if hl > 0:
        rel = _tl.source_reliability_decayed(source, market=m, regime=regime,
                                             horizon=horizon, half_life_days=hl)
        # chain: decayed regime ← decayed all-regime ← cumulative all-era.
        # Rule: a level with ZERO evidence hands over to its parent VERBATIM (no pseudo-obs
        # blend — capping a rich parent at k pseudo-obs would demote every proven source to
        # "unproven" the moment day-buckets are cold); a level with SOME evidence blends.
        if regime and (rel.get("n") or 0) == 0:
            rel = _tl.source_reliability_decayed(source, market=m, regime=None,
                                                 horizon=horizon, half_life_days=hl)
        elif regime:
            all_dec = _tl.source_reliability_decayed(source, market=m, regime=None,
                                                     horizon=horizon, half_life_days=hl)
            if all_dec.get("rate") is not None:
                nxt = _blend(rel, float(all_dec["rate"]), int(all_dec.get("n") or 0), k)
                if nxt is not None:
                    rel = nxt
        if (rel.get("n") or 0) == 0:
            rel = era                           # no recent evidence at all → cumulative
        elif era.get("rate") is not None:
            nxt = _blend(rel, float(era["rate"]), int(era.get("n") or 0), k)
            if nxt is not None:
                rel = nxt
    else:
        rel = _tl.source_reliability(source, market=m, regime=regime,
                                     horizon=horizon, min_n=1)
        if regime:
            allr = era
            n_r, c_r = int(rel.get("n") or 0), int(rel.get("correct") or 0)
            n_a = int(allr.get("n") or 0)
            if k > 0 and n_a > n_r and allr.get("rate") is not None:
                borrow = min(float(k), float(n_a - n_r))
                bc = c_r + borrow * float(allr["rate"])
                bn = n_r + borrow
                rate, lo, hi = _tl._wilson(bc, bn)
                rel = {"n": int(round(bn)), "correct": int(round(bc)),
                       "rate": round(rate, 4), "ci_low": round(lo, 4),
                       "ci_high": round(hi, 4), "edge": round(rate - 0.5, 4),
                       "n_regime": n_r, "borrowed": int(round(borrow))}
            elif k <= 0 and n_r < cfg["min_n"] and n_a > n_r:
                rel = allr                      # legacy step fallback (shrink disabled)
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
           log: bool = True, variant: str = "live",
           extra_conditioners: dict | None = None) -> dict:
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
    _valid: list[tuple[str, float]] = []
    cond = None
    if symbol:
        try:            # E8: decision-time conditioners refine every source's weight;
            # X-D: callers add selection context (sel:<preset>) — WHY the scanner picked
            # this symbol is itself a measured conditioner (pct-change selection pressure,
            # research/audits/pct-change-is-contrarian-20260716.md).
            cond = {**(_tl.current_conditioners(symbol, market or "CRYPTO") or {}),
                    **(extra_conditioners or {})} or None
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
        rel = reliability(source, regime, market, conditioners=cond,
                          decayed=(variant != "control"))
        w, invert = _signed_weight(rel, cfg)
        if w <= 0.0:
            weights[source] = {"w": 0.0, "invert": invert, "rate": rel.get("rate"),
                               "n": rel.get("n")}
            continue
        p_cal = (1.0 - p) if invert else p
        _mc = cfg["mag_cap"] if variant != "control" else 0.5
        num += w * max(-_mc, min(_mc, p_cal - 0.5))
        tot_w += w
        weights[source] = {"w": round(w, 4), "invert": invert,
                           "rate": rel.get("rate"), "n": rel.get("n"),
                           "p_used": round(p_cal, 4)}
        _valid.append((source, p_cal))
    if tot_w < cfg["min_total_w"]:
        out = {"direction": "neutral", "p_up": 0.5, "confidence": round(tot_w, 4),
               "weights": weights, "abstained": True, "n_sources": len(weights),
               "variant": variant}
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
    # MISSION session 3 — HORIZON-SPECIALIZED fusion (the clean asymmetry made actionable:
    # 15m .518 / 1h .534 / 4h .594). Re-fuse the same readings under each horizon's OWN
    # recent reliability; the horizon whose fused read is strongest (weight × conviction)
    # OWNS the decision — sources good at 4h drive 4h-tagged trades instead of being
    # averaged into a pooled mush. Falls back to the pooled read when no horizon clears
    # the same abstention bars. Control variant stays pooled (the benchmark).
    h_mode = None
    if variant != "control" and _valid \
            and os.environ.get("HORIZON_SPECIALIZED", "1") in ("1", "true", "TRUE", "yes", "on"):
        try:
            best = None
            for h in ("15m", "1h", "4h"):
                num_h = tot_h = 0.0
                for _src, _p in _valid:
                    rel_h = reliability(_src, regime, market, conditioners=cond,
                                        horizon=h, decayed=True)
                    w_h, _ = _signed_weight(rel_h, cfg)
                    if w_h <= 0.0:
                        continue
                    _mc = cfg["mag_cap"]          # X-F: sign carries the information
                    num_h += w_h * max(-_mc, min(_mc, _p - 0.5))
                    tot_h += w_h
                if tot_h < cfg["min_total_w"]:
                    continue
                p_h = min(1.0, max(0.0, 0.5 + num_h / tot_h))
                if abs(p_h - 0.5) <= band:
                    continue
                score = tot_h * abs(p_h - 0.5)
                if best is None or score > best[0]:
                    best = (score, h, p_h, tot_h)
            if best is not None:
                _, _h, _ph, _th = best
                direction = "long" if _ph > 0.5 else "short"
                p_final, tot_w = _ph, _th
                h_mode = _h
        except Exception:
            h_mode = None
    out = {"direction": direction, "p_up": round(p_final, 4),
           "confidence": round(tot_w, 4), "weights": weights,
           "abstained": direction == "neutral", "n_sources": len(weights),
           "variant": variant}
    if h_mode is not None:
        out["horizon"] = h_mode
        out["horizon_mode"] = "specialized"
    if direction != "neutral" and h_mode is None:
        # MISSION X-B: a side without a horizon is half a decision (measured: 15m 0.518 /
        # 1h 0.534 / 4h 0.594 on the clean window). Emit the horizon at which the AGREEING
        # sources have their strongest recent edge; exits and validation consume it.
        try:
            want_long = direction == "long"
            scores: dict[str, float] = {}
            for h in ("15m", "1h", "4h"):
                tot = 0.0
                for src, meta in weights.items():
                    if (meta.get("w") or 0) <= 0 or meta.get("p_used") is None:
                        continue
                    if (meta["p_used"] >= 0.5) != want_long:
                        continue
                    rh = reliability(src, regime, market, horizon=h,
                                     decayed=(variant != "control"))
                    if rh.get("rate") is not None and rh.get("rate") > 0.5 \
                            and (rh.get("n") or 0) >= 20:
                        tot += rh["rate"] - 0.5
                scores[h] = round(tot, 4)
            if any(v > 0 for v in scores.values()):
                out["horizon"] = max(scores, key=scores.get)
                out["horizon_scores"] = scores
        except Exception:
            pass
    if log:
        _log(out, symbol=symbol, market=market, regime=regime, seam="decide",
             coverage=coverage)
    return out


# ── MISSION X-C: cost-aware NO-TRADE ─────────────────────────────────────────────────
_ATR_CACHE: dict[str, tuple[float, float]] = {}
_HBARS = {"15m": 3, "1h": 12, "4h": 48}


def _atr_pct(symbol: str, bars: int = 14) -> float | None:
    """5m ATR as a FRACTION of price, from the RAM mirror; 60s cache; None when cold."""
    flat = (symbol or "").replace("/", "").split(":")[0].upper()
    hit = _ATR_CACHE.get(flat)
    now = time.monotonic()
    if hit and now - hit[0] < 60:
        return hit[1]
    try:
        from trading.broker_sense.binance_stream import get_mirror
        rows = get_mirror().candles(flat, 300, bars + 1) or []
        if len(rows) < bars:
            return None
        trs = []
        prev_close = float(rows[0][4])
        for r in rows[1:]:
            h, l, c = float(r[2]), float(r[3]), float(r[4])
            trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
            prev_close = c
        price = float(rows[-1][4])
        if price <= 0 or not trs:
            return None
        atr = (sum(trs) / len(trs)) / price
        _ATR_CACHE[flat] = (now, atr)
        if len(_ATR_CACHE) > 400:
            for k in sorted(_ATR_CACHE, key=lambda k: _ATR_CACHE[k][0])[:100]:
                _ATR_CACHE.pop(k, None)
        return atr
    except Exception:
        return None


def cost_gate(p_up: float, *, symbol: str, horizon: str = "1h",
              cost_bps: float | None = None) -> dict:
    """MISSION X-C: an edge must clear costs or the honest call is NO-TRADE.

    EV_bps ≈ (2p−1) · E|move at horizon|_bps − round-trip cost. E|move| from the 5m ATR
    scaled √bars (diffusion approximation — crude but honest and stated). Cost defaults to
    2×FEE_BPS + SLIP_BPS (env; slippage is MEASURED in exec_choice_stats as it accrues).
    Fail-OPEN with reason when ATR is unavailable (a cold mirror must not silence the paper
    experiment — the miss is recorded so its cost is measurable)."""
    if os.environ.get("COST_GATE", "1") not in ("1", "true", "TRUE", "yes", "on"):
        return {"pass": True, "reason": "disabled"}
    try:
        cost = float(cost_bps) if cost_bps is not None else \
            2.0 * _f("FEE_BPS", 5.0) + _f("SLIP_BPS", 2.0)
        atr = _atr_pct(symbol)
        if atr is None:
            return {"pass": True, "reason": "no_atr", "cost_bps": cost}
        emove_bps = atr * 1e4 * (_HBARS.get(horizon, 12) ** 0.5)
        ev_bps = abs(2.0 * float(p_up) - 1.0) * emove_bps - cost
        return {"pass": ev_bps > 0.0, "reason": "ev",
                "ev_bps": round(ev_bps, 2), "emove_bps": round(emove_bps, 2),
                "cost_bps": round(cost, 2)}
    except Exception:
        return {"pass": True, "reason": "error_fail_open"}


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
        w, _ = _signed_weight(rel, _cfg())
        # MISSION session 3 (2026-07-17): the invert branch that used to live here was DEAD
        # (since the 2026-07-16 inverter kills _signed_weight can never return invert=True
        # with weight) but sat loaded for a future refactor to re-arm. Excised: this function
        # PASSES or (nothing else). A reliably-wrong source is retired inside decide()'s
        # weighting; a triggered pullback still opens so exploration keeps earning labels.
        info = {"action": "pass", "source": source, "rate": rel.get("rate"),
                "n": rel.get("n")}
        _log({"direction": d.lower(), "p_up": None, "confidence": w,
              "weights": {source: {"w": round(w, 4), "invert": False,
                                   "rate": rel.get("rate"), "n": rel.get("n")}},
              "abstained": False, "n_sources": 1},
             symbol=symbol, market=market, regime=regime, seam="correct")
        return d, info
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
