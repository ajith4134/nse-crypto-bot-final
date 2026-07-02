"""trading/strategy/ — Strategy creation / mutation / evolution engine (Phase T8).

Reuse-first: the heavy engines are battle-tested OSS wrapped behind thin adapters —
**TA-Lib** (features), **DEAP** (genetic-programming genome + operators), **vectorbt**
(vectorized backtest). Our own code is the glue: the trading primitive set, the
genome↔signal/NodeProtocol bridge, and journal-driven fitness (T8.2+). DEAP-based
genomes and vectorbt backtests run on CPU; gplearn/Qlib/FinRL slot in at later phases.

See t8-stitch-blueprint.md (repo root) and research/ for the full design.

T8.1 pieces:
  features  — OHLCV → feature frame via TA-Lib (SMA/EMA/RSI/ATR/ROC + pandas ratios)
  genome    — DEAP typed-GP strategy genome → vectorized +1/-1/0 signal
  operators — DEAP cxOnePoint / mutUniform / mutNodeReplacement + market-legal features
  backtest  — vectorbt signal backtest → metrics; walk-forward fold splitter (ours)
"""
from __future__ import annotations

from trading.strategy.backtest import BacktestResult, backtest_signal, walk_forward_folds
from trading.strategy.control import (
    StrategyEvolutionDisabled,
    evolution_enabled,
    require_evolution_enabled,
    set_evolution_enabled,
)
from trading.strategy.features import FEATURE_NAMES, compute_features
from trading.strategy.genome import (
    Strategy,
    compile_signal,
    get_pset,
    random_strategy,
    random_tree,
)
from trading.strategy.operators import crossover, market_features, mutate
from trading.strategy.fitness import Fitness, evaluate_oos, fitness, multi_objective
from trading.strategy.guardrails import (
    GuardrailReport,
    deflated_sharpe_ratio,
    information_coefficient,
    passes_guardrails,
    pbo_cscv,
    probabilistic_sharpe_ratio,
)

__all__ = [
    "compute_features", "FEATURE_NAMES",
    "Strategy", "random_strategy", "random_tree", "get_pset", "compile_signal",
    "mutate", "crossover", "market_features",
    "backtest_signal", "walk_forward_folds", "BacktestResult",
    "fitness", "Fitness", "evaluate_oos", "multi_objective",
    "passes_guardrails", "GuardrailReport", "deflated_sharpe_ratio",
    "probabilistic_sharpe_ratio", "pbo_cscv", "information_coefficient",
    "evolve", "EvolutionResult", "promote", "StrategyNode", "StrategyRegistry",
    "evolution_enabled", "set_evolution_enabled", "require_evolution_enabled",
    "StrategyEvolutionDisabled",
]

from trading.strategy.evolve import EvolutionResult, evolve
from trading.strategy.registry import StrategyNode, StrategyRegistry, promote
