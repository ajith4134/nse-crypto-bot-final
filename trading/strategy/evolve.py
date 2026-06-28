"""trading/strategy/evolve.py — DEAP NSGA-II evolution loop (T8.3).

Runs a population of Strategy genomes through mutation/crossover → OUT-OF-SAMPLE
multi-objective fitness (T8.2) → **DEAP NSGA-II** Pareto selection across generations,
then applies the T8.2 overfitting guardrails and PROMOTES survivors to NodeProtocol
nodes (T8.3 registry) the brain can route/ensemble.

Reuse-first: selection = `deap.tools.selNSGA2`, Pareto extraction = `tools.sortNondominated`;
our glue is the toolbox wiring to our genome + fitness + guardrails + promotion. The loop
is a (μ+λ) NSGA-II: parents vary into offspring, then NSGA-II reselects the next generation
from parents+offspring (so the Pareto front never regresses). Deterministic (seeded) + offline.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from deap import base, creator, tools

from trading.strategy.features import compute_features
from trading.strategy.fitness import fitness
from trading.strategy.genome import Strategy, random_strategy
from trading.strategy.guardrails import passes_guardrails, pbo_cscv
from trading.strategy.operators import crossover, market_features, mutate
from trading.strategy.registry import StrategyRegistry, promote

# NSGA-II fitness: maximise (expectancy, OOS Sharpe, -|maxDD|, -trade-penalty)
if not hasattr(creator, "StratFitness"):
    creator.create("StratFitness", base.Fitness, weights=(1.0, 1.0, 1.0, 1.0))


@dataclass
class EvolutionResult:
    best: list                          # top strategies by scalar fitness
    pareto: list                        # non-dominated front (Strategy list)
    promoted: list                      # StrategyNode list (guardrail-passed)
    registry: StrategyRegistry
    history: list                       # per-generation stats
    n_evaluated: int = 0
    pbo: dict = field(default_factory=dict)   # population-level overfitting (CSCV)

    def as_dict(self) -> dict:
        return {
            "history": self.history,
            "n_evaluated": self.n_evaluated,
            "pbo": self.pbo,
            "pareto_size": len(self.pareto),
            "n_promoted": len(self.promoted),
            "best": [{"id": s.id, "market": s.market,
                      "score": round(s._fit.score, 4),
                      "oos": {k: (round(v, 4) if isinstance(v, float) else v)
                              for k, v in s._fit.oos_metrics.items()}}
                     for s in self.best],
            "registry": self.registry.status(),
        }


def _assign_fitness(strat: Strategy, ohlcv, feats, n_folds: int) -> Strategy:
    f = fitness(strat, ohlcv, features=feats, n_folds=n_folds)
    strat._fit = f                                       # cache full Fitness (score + metrics)
    strat.fitness = creator.StratFitness()
    strat.fitness.values = f.objectives
    return strat


def evolve(ohlcv: pd.DataFrame, *, market: str = "CRYPTO", features: pd.DataFrame | None = None,
           pop_size: int = 24, generations: int = 6, seed: int = 0, n_folds: int = 4,
           cx_pb: float = 0.6, mut_pb: float = 0.4, promote_top: int = 10,
           dsr_min: float = 0.6, min_trades: int = 10,
           guardrail_trials: int | None = None) -> EvolutionResult:
    """Evolve a population for `generations` and promote guardrail-passing survivors."""
    rng = np.random.default_rng(seed)
    feats = features if features is not None else compute_features(ohlcv)
    flist = market_features(market)
    evaluated = 0

    pop = [random_strategy(flist, rng, market=market, strat_id=f"g0_{i}")
           for i in range(pop_size)]
    for ind in pop:
        _assign_fitness(ind, ohlcv, feats, n_folds)
        evaluated += 1

    history = []
    for gen in range(generations):
        # ── variation: parents (shuffled) → offspring via crossover/mutation ──
        parents = list(pop)
        order = rng.permutation(len(parents))
        offspring = []
        for k in range(0, len(order) - 1, 2):
            a, b = parents[order[k]], parents[order[k + 1]]
            if rng.random() < cx_pb and a.features == b.features:
                try:
                    c1, c2 = crossover(a, b, rng)
                except Exception:
                    c1, c2 = copy.deepcopy(a), copy.deepcopy(b)
            else:
                c1, c2 = mutate(a, flist, rng), mutate(b, flist, rng)
            for c in (c1, c2):
                if rng.random() < mut_pb:
                    c = mutate(c, flist, rng)
                c.id = f"g{gen + 1}_{len(offspring)}"
                _assign_fitness(c, ohlcv, feats, n_folds)
                evaluated += 1
                offspring.append(c)

        # ── environmental selection: NSGA-II over parents + offspring ──
        pop = tools.selNSGA2(pop + offspring, pop_size)
        scores = [s._fit.score for s in pop]
        best = max(pop, key=lambda s: s._fit.score)
        history.append({
            "gen": gen + 1,
            "best_score": round(best._fit.score, 4),
            "mean_score": round(float(np.mean(scores)), 4),
            "best_oos_sharpe": round(best._fit.oos_metrics.get("oos_sharpe_mean", 0.0), 4),
            "best_oos_return": round(best._fit.oos_metrics.get("oos_total_return", 0.0), 4),
        })

    pareto = tools.sortNondominated(pop, len(pop), first_front_only=True)[0]
    ranked = sorted(pop, key=lambda s: s._fit.score, reverse=True)

    # ── population-level overfitting (PBO via CSCV) + cross-trial Sharpe variance ──
    # var_sr is the variance of Sharpe ACROSS the trial population — the quantity the
    # Deflated-Sharpe deflation benchmark actually requires (not a single-strategy proxy).
    pop_sharpes = [s._fit.oos_metrics.get("oos_sharpe", 0.0) for s in pop]
    var_sr = float(np.var(pop_sharpes)) if len(pop_sharpes) > 1 else None
    # Per-strategy × per-fold OOS-return matrix → PBO (needs >=2 configs, even >=4 folds).
    pbo = {}
    fold_mat = [s._fit.oos_metrics.get("fold_returns", []) for s in pop]
    width = min((len(r) for r in fold_mat), default=0)
    if width >= 4 and len(fold_mat) >= 2:
        w = width if width % 2 == 0 else width - 1
        try:
            pbo = pbo_cscv(np.array([r[:w] for r in fold_mat], dtype=float))
        except Exception:
            pbo = {}
    pop_overfit = pbo.get("pbo", 0.0) > 0.5      # population looks overfit → don't promote

    # ── guardrails → promotion ──
    trials = guardrail_trials or evaluated
    registry = StrategyRegistry()
    promoted = []
    for s in ranked[:promote_top]:
        rep = passes_guardrails(s, ohlcv, n_trials=trials, features=feats, n_folds=n_folds,
                                min_trades=min_trades, dsr_min=dsr_min, var_sr=var_sr)
        if rep.passed and not pop_overfit:
            node = promote(s, flist, metrics={**s._fit.oos_metrics, "dsr": rep.dsr.get("dsr")})
            registry.add(node)
            promoted.append(node)

    return EvolutionResult(best=ranked[:5], pareto=list(pareto), promoted=promoted,
                           registry=registry, history=history, n_evaluated=evaluated, pbo=pbo)
