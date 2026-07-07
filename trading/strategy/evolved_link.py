"""trading/strategy/evolved_link.py — the live wire between the self-evolving strategy
engine and the brain's decision pipeline.

The genetic CREATION / MUTATION / EVOLUTION engine (`evolve.py` = DEAP NSGA-II) and its
lifelong controller (`self_evolve.py` = evolve → admit guardrail-passed survivors into the
persisted SkillLibrary) already exist and are quality-gated. What was missing was the wire
that (a) actually BREEDS on the live loop and (b) feeds the best evolved Strategy into
`BrainTradingPipeline.evolved_strategy` — the pipeline field that was declared but never
populated (step 4 of `pipeline.decide()`: `evolved_strategy.signal(feats)`).

This module is that wire. It is gate-aware: with evolution disabled
(`trading.strategy.control`) `breed()` returns a clean `{"ran": False, "gated": True}` and
`best_evolved_strategy()` still serves whatever the library already holds. All calls are
best-effort and never raise into the trade loop.

  breed(ohlcv_by_market)      -> run one generation + reevaluate per market; admit winners
  best_evolved_strategy(mkt)  -> the top admitted Strategy for a market (cached, TTL), or None
  attach_to_pipeline(pipe,m)  -> set pipe.evolved_strategy from the library; returns bool
  status()                    -> live state for the dashboard (gate + library + best per mkt)

The SelfEvolvingLoop is a persisted singleton so the library compounds across cycles and the
breeder and the decider share ONE growing store (single source of truth).
"""
from __future__ import annotations

import time

from trading.strategy.control import evolution_enabled

# markets the genetic engine knows how to build feature genomes for (operators.market_features)
_MARKETS = ("CRYPTO", "NSE")

# one shared, persisted lifelong loop — breeder writes it, decider reads it
_LOOP = None
_PORTFOLIO = None
# best-strategy cache: market -> (built_at_monotonic, Strategy|None)
_BEST_CACHE: dict[str, tuple[float, object]] = {}
_BEST_TTL = 300.0          # re-read the library at most every 5 min (cheap; avoids per-tick IO)


def _loop():
    """The shared persisted SelfEvolvingLoop (lazy — pulls in numpy/deap)."""
    global _LOOP
    if _LOOP is None:
        from trading.strategy.self_evolve import SelfEvolvingLoop
        _LOOP = SelfEvolvingLoop(persist=True)
    return _LOOP


def _portfolio():
    """The shared StrategyPortfolio (lazy — builds only the generators whose deps are present)."""
    global _PORTFOLIO
    if _PORTFOLIO is None:
        from trading.strategy.generators import StrategyPortfolio
        _PORTFOLIO = StrategyPortfolio()
    return _PORTFOLIO


def breed(ohlcv_by_market: dict, *, generations: int = 3, pop_size: int = 14,
          seed: int = 0, hypotheses=None) -> dict:
    """Run ONE evolution generation-batch per market on real OHLCV, admit guardrail-passed
    survivors into the persisted SkillLibrary, then re-evaluate/retire stale skills.

    `ohlcv_by_market` maps "CRYPTO"/"NSE" -> a pandas OHLCV frame (a representative series is
    enough — the genome's features are market-generic). Gate-aware and best-effort: returns a
    summary dict; on the gate being OFF returns `{"ran": False, "gated": True}` without running.
    """
    if not evolution_enabled():
        return {"ran": False, "gated": True,
                "reason": "strategy evolution gated OFF (trading.strategy.control)"}
    loop = _loop()
    if hypotheses is not None and getattr(loop, "hypotheses", None) is None:
        loop.hypotheses = hypotheses            # let confirmed edges bias admission
    out: dict = {"ran": True, "gated": False, "markets": {}}
    admitted_total = 0
    for market in _MARKETS:
        ohlcv = ohlcv_by_market.get(market)
        if ohlcv is None or len(ohlcv) < 60:
            out["markets"][market] = {"skipped": "insufficient OHLCV"}
            continue
        try:
            gen = loop.run_generation(ohlcv, market=market, generations=generations,
                                      pop_size=pop_size, seed=seed)
            rev = loop.reevaluate(ohlcv, market=market)
            admitted_total += int(gen.get("admitted", 0) or 0)
            out["markets"][market] = {
                "evaluated": gen.get("evaluated"), "promoted": gen.get("promoted"),
                "admitted": gen.get("admitted"), "best_score": gen.get("best_score"),
                "pbo": gen.get("pbo"), "retired": len(rev.get("retired", []))}
            _BEST_CACHE.pop(market, None)        # fresh winners → invalidate the read cache
        except Exception as e:                   # never break the learning loop
            out["markets"][market] = {"error": f"{type(e).__name__}: {e}"[:160]}
    # PORTFOLIO — run the complementary SOTA generators (LLM-mutation, symbolic regression,
    # quality-diversity, formulaic-alpha mining, RD-Agent) through the SAME guardrail into the
    # SAME library. DEAP above + these = the full generator portfolio. Best-effort.
    try:
        pf = _portfolio()
        if pf.generators:
            pres = pf.run(ohlcv_by_market, library=loop.library, seed=seed)
            out["portfolio"] = pres
            for mkt in _MARKETS:
                mres = pres.get("markets", {}).get(mkt)
                if isinstance(mres, dict):
                    for gres in mres.values():
                        admitted_total += int((gres or {}).get("admitted", 0) or 0)
            for m in _MARKETS:
                _BEST_CACHE.pop(m, None)
        else:
            out["portfolio"] = {"generators": [], "note": "no portfolio generators available"}
    except Exception as e:
        out["portfolio"] = {"error": f"{type(e).__name__}: {e}"[:160]}

    out["admitted_total"] = admitted_total
    out["library"] = loop.library.status()
    # dashboard-sync: keep the self-evolve node registered on the live graph
    try:
        from trading.strategy.self_evolve import register_self_evolve
        register_self_evolve(loop)
    except Exception:
        pass
    return out


def best_evolved_strategy(market: str):
    """The best admitted evolved `Strategy` for a market (reconstructed from the persisted
    SkillLibrary), or None. Cached with a short TTL so the live decider never hits disk per
    tick. Returns None cleanly when the library holds no strategy skill for the market."""
    m = (market or "").upper()
    now = time.monotonic()
    hit = _BEST_CACHE.get(m)
    if hit is not None and (now - hit[0]) < _BEST_TTL:
        return hit[1]
    strat = None
    try:
        from trading.strategy.generators.base import rebuild
        for skill in _loop().library.retrieve(market=m, k=10):
            if getattr(skill, "kind", "") != "strategy" or not skill.payload:
                continue
            strat = rebuild(skill.payload)       # dispatches on __type__ (genome/expression/…)
            if strat is not None:
                break                            # retrieve() is metric-sorted → first = best
    except Exception:
        strat = None
    _BEST_CACHE[m] = (now, strat)
    return strat


def attach_to_pipeline(pipeline, market: str) -> bool:
    """Point a BrainTradingPipeline at the current best evolved Strategy for its market.
    Sets `pipeline.evolved_strategy` (which pipeline.decide() step 4 turns into a signal).
    Returns True if a strategy was attached, False otherwise. Never raises."""
    try:
        strat = best_evolved_strategy(market)
        if strat is not None:
            pipeline.evolved_strategy = strat
            return True
    except Exception:
        pass
    return False


def status() -> dict:
    """Live state for the dashboard: real gate status + persisted library + best per market."""
    enabled = evolution_enabled()
    try:
        loop = _loop()
        best = {}
        for m in _MARKETS:
            s = best_evolved_strategy(m)
            best[m] = getattr(s, "id", None) if s is not None else None
        try:
            generators = ["deap_nsga2"] + _portfolio().names()
        except Exception:
            generators = ["deap_nsga2"]
        return {"enabled": enabled, "wired": True, "best_by_market": best,
                "generators": generators, **loop.status()}
    except Exception as e:
        return {"enabled": enabled, "wired": True,
                "error": f"{type(e).__name__}: {e}"[:160]}
