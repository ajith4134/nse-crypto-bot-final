"""Trading Phase T8.3 (DEAP NSGA-II evolution loop + promotion) acceptance tests — offline.

Drives the REUSE-FIRST evolution stack end to end: a population of DEAP-GP genomes is
evolved through NSGA-II (trading/strategy/evolve.py) under OUT-OF-SAMPLE multi-objective
fitness, then guardrail-passing survivors are PROMOTED to NodeProtocol nodes
(trading/strategy/registry.py) the brain can route/ensemble.

Everything is seeded + offline: the synthetic OHLCV is a seeded geometric random walk WITH
positive drift (so an edge can exist), and ``evolve()`` is run ONCE in ``setUpClass`` and
reused across assertions to keep the suite fast (evolution runs many vectorbt backtests).
"""
from __future__ import annotations

import json
import unittest

from trading.strategy.control import set_evolution_enabled
set_evolution_enabled(True)   # engine-internals tests: arm the (deliberately OFF) gate
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from core.node_protocol import NodeProtocol
from trading.strategy.evolve import EvolutionResult, evolve
from trading.strategy.features import compute_features
from trading.strategy.operators import market_features
from trading.strategy.registry import StrategyNode, StrategyRegistry, promote

_SEED = 7
_POP = 10
_GENS = 3
_FOLDS = 3


def _make_ohlcv(n: int = 800, seed: int = 20260628) -> pd.DataFrame:
    """Deterministic geometric random walk OHLCV with positive drift (~n bars).

    high >= max(open, close) and low <= min(open, close) by construction.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0006, 0.012, n)          # positive drift so an edge can exist
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    wig = np.abs(rng.normal(0.0, 0.004, n))
    high = np.maximum(open_, close) * (1.0 + wig)
    low = np.minimum(open_, close) * (1.0 - wig)
    volume = rng.uniform(1_000.0, 5_000.0, n)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all()
    return df


# module-level OHLCV + features computed once for the whole suite
_OHLCV = _make_ohlcv()
_FEAT = compute_features(_OHLCV)
_FEATURES = market_features("CRYPTO")
_HIST_KEYS = {"gen", "best_score", "mean_score", "best_oos_sharpe", "best_oos_return"}


def _run_evolve() -> EvolutionResult:
    return evolve(_OHLCV, market="CRYPTO", features=_FEAT, pop_size=_POP,
                  generations=_GENS, seed=_SEED, n_folds=_FOLDS, dsr_min=0.3,
                  min_trades=5)


class TestEvolveRuns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _run_evolve()

    def test_result_type(self):
        self.assertIsInstance(self.result, EvolutionResult)

    def test_history_length_matches_generations(self):
        self.assertEqual(len(self.result.history), _GENS)

    def test_history_entry_keys(self):
        for entry in self.result.history:
            self.assertEqual(set(entry.keys()), _HIST_KEYS)

    def test_history_gen_numbers_are_sequential(self):
        gens = [e["gen"] for e in self.result.history]
        self.assertEqual(gens, list(range(1, _GENS + 1)))

    def test_n_evaluated_at_least_pop_size(self):
        self.assertGreater(self.result.n_evaluated, 0)
        self.assertGreaterEqual(self.result.n_evaluated, _POP)

    def test_best_score_monotonic_non_decreasing(self):
        # NSGA-II (μ+λ) reselects from parents+offspring, so the best never regresses.
        first = self.result.history[0]["best_score"]
        last = self.result.history[-1]["best_score"]
        self.assertGreaterEqual(last, first - 1e-9)

    def test_pareto_front_non_empty(self):
        self.assertGreater(len(self.result.pareto), 0)

    def test_best_non_empty(self):
        self.assertGreater(len(self.result.best), 0)

    def test_best_sorted_by_score_descending(self):
        scores = [s._fit.score for s in self.result.best]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_as_dict_is_json_serializable(self):
        d = self.result.as_dict()
        text = json.dumps(d)                       # raises if numpy types leak
        self.assertIsInstance(text, str)
        self.assertIn("history", d)
        self.assertIn("n_evaluated", d)

    def test_promoted_is_list(self):
        self.assertIsInstance(self.result.promoted, list)

    def test_promoted_are_node_protocol_or_empty(self):
        # Honest: strict guardrails may legitimately promote 0 strategies.
        if self.result.promoted:
            for node in self.result.promoted:
                self.assertIsInstance(node, NodeProtocol)
                self.assertEqual(node.kind, "strategy")
        else:
            self.assertEqual(self.result.promoted, [])


class TestEvolveDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        r1 = _run_evolve()
        r2 = _run_evolve()
        self.assertEqual(r1.history[-1]["best_score"], r2.history[-1]["best_score"])
        self.assertEqual(r1.n_evaluated, r2.n_evaluated)


class TestPromotionNodeProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _run_evolve()
        cls.features = market_features("CRYPTO")
        cls.strat = cls.result.best[0]
        cls.node = promote(cls.strat, cls.features)
        cls.X = _FEAT[cls.features].head(30).values.tolist()

    def test_promote_returns_strategy_node(self):
        self.assertIsInstance(self.node, StrategyNode)

    def test_node_is_node_protocol(self):
        self.assertIsInstance(self.node, NodeProtocol)

    def test_node_kind_is_strategy(self):
        self.assertEqual(self.node.kind, "strategy")

    def test_schema_input_dim_matches_features(self):
        self.assertEqual(self.node.schema.input_dim, len(self.features))

    def test_predict_proba_values_in_allowed_set(self):
        proba = self.node.predict_proba(self.X)
        self.assertEqual(len(proba), len(self.X))
        for p in proba:
            self.assertIsInstance(p, float)
            self.assertIn(p, {0.1, 0.5, 0.9})

    def test_predict_returns_binary_ints(self):
        labels = self.node.predict(self.X)
        self.assertEqual(len(labels), len(self.X))
        for y in labels:
            self.assertIn(int(y), (0, 1))

    def test_fit_is_noop_returns_self(self):
        self.assertIs(self.node.fit(self.X), self.node)
        self.assertIs(self.node.fit(self.X, None), self.node)


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _run_evolve()
        cls.features = market_features("CRYPTO")
        cls.node = promote(cls.result.best[0], cls.features)

    def test_add_and_names(self):
        reg = StrategyRegistry()
        reg.add(self.node)
        self.assertIn(self.node.name, reg.names())
        self.assertEqual(len(reg.names()), 1)

    def test_status_reflects_node(self):
        reg = StrategyRegistry()
        reg.add(self.node)
        status = reg.status()
        self.assertEqual(status["n_promoted"], 1)
        self.assertEqual(status["nodes"][0]["name"], self.node.name)

    def test_status_is_json_serializable(self):
        reg = StrategyRegistry()
        reg.add(self.node)
        text = json.dumps(reg.status())
        self.assertIsInstance(text, str)


if __name__ == "__main__":
    unittest.main()
