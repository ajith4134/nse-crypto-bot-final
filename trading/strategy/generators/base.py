"""trading/strategy/generators/base.py — the Strategy-Generator Portfolio backbone.

Research (research/strategy-generation-sota-2026.md) said: our DEAP NSGA-II fixed-genome
evolver is a solid baseline but not the frontier; our CPCV+Deflated-Sharpe+PBO guardrail IS
SOTA. So the design is a PORTFOLIO of generators — DEAP, LLM-mutation, symbolic regression,
quality-diversity, formulaic-alpha mining, RD-Agent — that all emit CANDIDATES scored through
the SAME existing guardrail, so nothing is trusted until it clears the honest overfit gate.

The unifying seam is deliberately tiny: `evaluate_oos()` / `passes_guardrails()` only ever call
`candidate.signal(features_df) -> pd.Series[int in {-1,0,1}]`. So a *candidate* is any object
with `.signal()`, `.id`, `.market`, `.features`, `.to_dict()` (carrying a `__type__` tag) and a
`from_dict()`. The DEAP genome (`trading.strategy.genome.Strategy`) already satisfies this and is
the default type; new generators add `ExpressionStrategy` / `AlphaStrategy` etc.

  StrategyGenerator          — base: `.name`, `.generate(ohlcv, market, ...) -> [candidate]`
  register_candidate_type    — register a candidate class under its `__type__` tag (for rebuild)
  rebuild(payload)           — reconstruct a persisted candidate of ANY type from its dict
  evaluate_and_admit(...)    — the SHARED gate: guardrail every candidate → admit survivors to
                               the SkillLibrary (the same store evolved_link + the brain read)

All portfolio work is best-effort and CPU-only; a broken generator degrades the portfolio, it
never breaks the trade loop.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


# ── candidate protocol + type registry ───────────────────────────────────────────
@runtime_checkable
class Candidate(Protocol):
    """Anything the shared guardrail can score + the brain pipeline can trade."""
    id: str
    market: str
    features: list

    def signal(self, df: pd.DataFrame) -> pd.Series: ...
    def to_dict(self) -> dict: ...


# __type__ tag -> class (must expose classmethod from_dict). "genome" = the DEAP Strategy.
_CANDIDATE_TYPES: dict[str, type] = {}


def register_candidate_type(tag: str):
    """Class decorator: register a candidate class so rebuild() can reconstruct it by tag."""
    def _wrap(cls):
        _CANDIDATE_TYPES[tag] = cls
        cls.__candidate_type__ = tag
        return cls
    return _wrap


def rebuild(payload: dict):
    """Reconstruct a persisted candidate of ANY registered type from its to_dict() payload.

    Dispatches on payload['__type__']; defaults to the DEAP genome Strategy (which predates the
    tag and stores none). Returns None if the type is unknown or reconstruction fails."""
    if not isinstance(payload, dict):
        return None
    tag = payload.get("__type__", "genome")
    try:
        if tag == "genome":
            from trading.strategy.genome import Strategy
            return Strategy.from_dict(payload)
        cls = _CANDIDATE_TYPES.get(tag)
        if cls is None:
            return None
        return cls.from_dict(payload)
    except Exception:
        return None


# ── generator base ────────────────────────────────────────────────────────────────
class StrategyGenerator:
    """Base for every generator in the portfolio. Subclasses implement `generate()` to emit
    a list of candidates (each with `.signal()`); the portfolio scores them through the shared
    guardrail. `available()` lets a generator declare a missing dep/config without crashing."""

    name = "generator"

    def available(self) -> bool:
        return True

    def generate(self, ohlcv: pd.DataFrame, market: str, *, features: pd.DataFrame | None = None,
                 budget: int = 12, seed: int = 0, **kw) -> list:
        raise NotImplementedError


# ── the shared gate: guardrail → admit to the SkillLibrary ────────────────────────
def evaluate_and_admit(candidates: list, ohlcv: pd.DataFrame, *, library, market: str,
                       features: pd.DataFrame | None = None, source: str = "portfolio",
                       n_folds: int = 4, min_trades: int = 10, dsr_min: float = 0.6,
                       scheme: str = "cpcv") -> dict:
    """Score EVERY candidate through the existing CPCV + Deflated-Sharpe guardrail
    (trading.strategy.guardrails.passes_guardrails) and admit the survivors into `library`
    (a SkillLibrary). `n_trials` = the number of candidates tested this run (the DSR deflation
    benchmark — the more we try, the higher the bar). Returns a summary; never raises."""
    import os

    from trading.strategy.guardrails import passes_guardrails
    cands = [c for c in (candidates or []) if c is not None]
    n_trials = max(1, len(cands))
    tested = 0
    # pass 1: individual CPCV+DSR guardrail — collect survivors + their per-path OOS returns
    passed = []                                          # (candidate, metric, metrics, fold_returns)
    for c in cands:
        tested += 1
        try:
            rep = passes_guardrails(c, ohlcv, n_trials=n_trials, features=features,
                                    n_folds=n_folds, scheme=scheme, min_trades=min_trades,
                                    dsr_min=dsr_min)
        except Exception:
            continue
        if not rep.passed:
            continue
        metric = float(rep.dsr.get("dsr", 0.0))
        metrics = {"dsr": rep.dsr.get("dsr"), "psr": rep.dsr.get("psr"),
                   "oos_sharpe": rep.oos.get("oos_sharpe"),
                   "oos_total_return": rep.oos.get("oos_total_return"),
                   "n_trades": rep.oos.get("n_trades"), "source": source}
        # W5 LOOK-AHEAD TRIPWIRE (owner goal 2026-07-07; video vp1): results that look
        # TOO good are leakage suspects, not genius — auto-reject + log. Thresholds are
        # generous on purpose (real edges never test like this on OOS folds).
        try:
            _sh = float(metrics.get("oos_sharpe") or 0.0)
            _rt = float(metrics.get("oos_total_return") or 0.0)
            if _sh > 8.0 or _rt > 10.0:                  # >8 OOS Sharpe or >1000% return
                import time as _time

                from trading import state as _st
                _log = _st.load_json("leak_tripwire.json", [])
                _log.append({"ts": _time.time(), "id": getattr(c, "id", "?"),
                             "market": market, "source": source, "oos_sharpe": _sh,
                             "oos_total_return": _rt,
                             "verdict": "rejected: too-good-to-be-true (leak suspect)"})
                _st.save_json("leak_tripwire.json", _log[-200:])
                continue
        except Exception:
            pass
        passed.append((c, metric, metrics, rep.oos.get("fold_returns")))

    # pass 2 (⑥): family-wise error control — StepM keeps only candidates that beat a zero
    # benchmark after correcting for how many were tried. Hard gate when FWER_GATE=1 (default on);
    # fail-open on small samples so it never empties the portfolio spuriously.
    keep_ids = None
    fwer_on = os.environ.get("FWER_GATE", "1") in ("1", "true", "TRUE", "yes", "on")
    if fwer_on and len(passed) >= 2:
        try:
            from trading.strategy.generators.stats_gate import family_wise_superior
            fr = {getattr(c, "id", f"c{i}"): fr for i, (c, _, _, fr) in enumerate(passed)}
            keep_ids = family_wise_superior(fr)
        except Exception:
            keep_ids = None

    admitted, survivors = [], []
    for i, (c, metric, metrics, _fr) in enumerate(passed):
        cid = getattr(c, "id", f"c{i}")
        if keep_ids is not None and cid not in keep_ids:
            continue                                     # rejected by family-wise control
        metrics = {**metrics, "fwer_passed": keep_ids is not None}
        try:
            res = library.admit_strategy(c, metric, metrics=metrics, source=source)
        except Exception:
            continue
        if res.get("admitted"):
            admitted.append({"id": cid, "metric": round(metric, 4),
                             "improved": res.get("improved", False)})
            survivors.append(c)
            # W5 CHAMPION LINEAGE (videos vp1/vp5): a new champion per market only when
            # it beats the incumbent on ALL THREE metrics (DSR, OOS Sharpe, OOS return)
            # — the vp5 triple gate. Every generation (accepted or not) is recorded so
            # the Trading-Researcher view can show the score progression honestly.
            try:
                _update_champion(market, cid, metrics)
            except Exception:
                pass
    return {"generator": source, "market": market, "tested": tested,
            "n_trials": n_trials, "guardrail_passed": len(passed),
            "fwer_applied": keep_ids is not None,
            "admitted": len(admitted), "admitted_ids": admitted, "survivors": survivors}


def _update_champion(market: str, cid: str, metrics: dict) -> None:
    """Champion/challenger ledger per market (state: champion_lineage.json)."""
    import time as _time

    from trading import state as _st
    d = _st.load_json("champion_lineage.json", {})
    m = d.setdefault(market, {"generation": 0, "champion": None, "history": []})
    m["generation"] += 1
    cand = {"id": cid, "dsr": metrics.get("dsr"), "oos_sharpe": metrics.get("oos_sharpe"),
            "oos_total_return": metrics.get("oos_total_return"),
            "generation": m["generation"], "ts": _time.time()}
    champ = m.get("champion")

    def _f(x):
        return float(x) if x is not None else float("-inf")
    beats = champ is None or (
        _f(cand["dsr"]) > _f(champ.get("dsr"))
        and _f(cand["oos_sharpe"]) > _f(champ.get("oos_sharpe"))
        and _f(cand["oos_total_return"]) > _f(champ.get("oos_total_return")))
    entry = {**cand, "became_champion": bool(beats),
             "prior_champion": (champ or {}).get("id")}
    if beats:
        m["champion"] = cand
    m["history"] = (m.get("history") or [])[-199:] + [entry]
    _st.save_json("champion_lineage.json", d)
