"""trading/strategy/generators/portfolio.py — runs the whole generator portfolio.

`StrategyPortfolio.run()` fans a market's OHLCV across every AVAILABLE generator, collects the
candidates each produces, and funnels them all through the shared guardrail
(`evaluate_and_admit`) into ONE SkillLibrary — the same store `evolved_link` + the brain read.
A generator that is missing a dep/config (its `available()` is False) or that raises is simply
skipped; the portfolio degrades, it never breaks the loop.

Generators are built LAZILY via factories so heavy/optional deps (Julia for PySR, vendored
AlphaGen / RD-Agent, an LLM key) are only imported when that generator actually runs. Each
factory returns a `StrategyGenerator` or None.
"""
from __future__ import annotations

import pandas as pd

from trading.strategy.generators.base import evaluate_and_admit


def _try(factory):
    """Build a generator from a factory, returning None on any import/build failure."""
    try:
        g = factory()
        return g if (g is not None and g.available()) else None
    except Exception:
        return None


def default_generators() -> list:
    """The portfolio's generators, best-effort — only the ones whose deps/config are present.

    DEAP genetic evolution is intentionally NOT here: it is driven by SelfEvolvingLoop (which
    also persists history + reevaluates) and admits into the SAME library, so evolved_link.breed
    runs DEAP and then this portfolio for the complementary generators.
    """
    factories = []
    # ② LLM-as-mutation-operator
    try:
        from trading.strategy.generators.llm_mutation import LLMMutationGenerator
        factories.append(LLMMutationGenerator)
    except Exception:
        pass
    # ③ symbolic regression (both gplearn + PySR — each is its own generator)
    try:
        from trading.strategy.generators.symbolic import GplearnGenerator, PysrGenerator
        factories.append(GplearnGenerator)
        factories.append(PysrGenerator)
    except Exception:
        pass
    # ④ quality-diversity archive (pyribs MAP-Elites/MOME)
    try:
        from trading.strategy.generators.quality_diversity import QualityDiversityGenerator
        factories.append(QualityDiversityGenerator)
    except Exception:
        pass
    # ⑥ Optuna NSGA-II linear-alpha tuner (family-wise error control is applied in the gate)
    try:
        from trading.strategy.generators.optuna_tune import OptunaGenerator
        factories.append(OptunaGenerator)
    except Exception:
        pass
    # ⑤ formulaic-alpha mining (AlphaGen / AlphaForge, vendored)
    try:
        from trading.strategy.generators.alpha_mining import AlphaMiningGenerator
        factories.append(AlphaMiningGenerator)
    except Exception:
        pass
    # ⑦ RD-Agent(Q) + Qlib autonomous researcher (vendored, heaviest)
    try:
        from trading.strategy.generators.rd_agent import RDAgentGenerator
        factories.append(RDAgentGenerator)
    except Exception:
        pass
    return [g for g in (_try(f) for f in factories) if g is not None]


class StrategyPortfolio:
    """Fan OHLCV across all available generators → shared guardrail → shared SkillLibrary."""

    def __init__(self, generators: list | None = None):
        self.generators = generators if generators is not None else default_generators()

    def names(self) -> list:
        return [g.name for g in self.generators]

    def run(self, ohlcv_by_market: dict, *, library, budget: int = 12, seed: int = 0,
            min_trades: int = 10, dsr_min: float = 0.6) -> dict:
        """Generate + gate + admit across every market and generator. Returns a summary."""
        out: dict = {"generators": self.names(), "markets": {}}
        for market, ohlcv in (ohlcv_by_market or {}).items():
            if ohlcv is None or len(ohlcv) < 60:
                out["markets"][market] = {"skipped": "insufficient OHLCV"}
                continue
            from trading.strategy.features import compute_features
            try:
                feats = compute_features(ohlcv)
            except Exception:
                feats = None
            per_gen = {}
            for g in self.generators:
                try:
                    cands = g.generate(ohlcv, market, features=feats, budget=budget, seed=seed)
                    res = evaluate_and_admit(cands, ohlcv, library=library, market=market,
                                             features=feats, source=g.name,
                                             min_trades=min_trades, dsr_min=dsr_min)
                    per_gen[g.name] = {"tested": res["tested"], "admitted": res["admitted"],
                                       "admitted_ids": res["admitted_ids"]}
                except Exception as e:
                    per_gen[g.name] = {"error": f"{type(e).__name__}: {e}"[:160]}
            out["markets"][market] = per_gen
        return out
