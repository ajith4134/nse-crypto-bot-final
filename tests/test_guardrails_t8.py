"""Trading Phase T8.2 acceptance tests — journal-fitness + overfitting guardrails.

Fully OFFLINE + deterministic: every RNG is a seeded ``np.random.default_rng`` and
the synthetic OHLCV is a seeded geometric random walk (house idiom, mirrors
``tests/test_strategy_t8.py``). Plain unittest, no network, no files.

Covers:
  * PSR / DSR (probabilistic + deflated Sharpe, deflation monotonicity)
  * PBO via CSCV (no-skill ~0.5, constructed overfit ~1.0, bad-shape guards)
  * Information Coefficient (Spearman rank IC)
  * multi-objective fitness + journal blending
  * the ``passes_guardrails`` gate (+ JSON-serializable report)
"""
from __future__ import annotations

import json
import unittest
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from trading.strategy.features import compute_features
from trading.strategy.genome import random_strategy
from trading.strategy.operators import market_features
from trading.strategy.fitness import (
    evaluate_oos,
    fitness,
    journal_realized,
    multi_objective,
)
from trading.strategy.guardrails import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    information_coefficient,
    passes_guardrails,
    pbo_cscv,
    probabilistic_sharpe_ratio,
)

_SEED = 20260628


def _make_ohlcv(n: int = 900, seed: int = _SEED) -> pd.DataFrame:
    """Deterministic geometric random walk OHLCV (~n bars).

    high >= max(open, close) and low <= min(open, close) by construction.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.012, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    wig = np.abs(rng.normal(0.0, 0.004, n))
    high = np.maximum(open_, close) * (1.0 + wig)
    low = np.minimum(open_, close) * (1.0 - wig)
    volume = rng.uniform(1_000.0, 5_000.0, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


# module-level caches (compute once for the whole suite)
_OHLCV = _make_ohlcv()
_FEAT = compute_features(_OHLCV)
_FEATURES = market_features("CRYPTO")


# ── PSR / DSR ────────────────────────────────────────────────────────────────────
class TestProbabilisticDeflatedSharpe(unittest.TestCase):
    def test_psr_zero_sr_zero_benchmark_is_half(self):
        self.assertAlmostEqual(
            probabilistic_sharpe_ratio(0.0, 60, sr_benchmark=0.0), 0.5, places=6
        )

    def test_psr_monotone_increasing_in_sr(self):
        prev = -1.0
        for sr in (0.0, 0.1, 0.25, 0.5, 1.0):
            p = probabilistic_sharpe_ratio(sr, 60)
            self.assertGreater(p, prev)
            prev = p

    def test_psr_in_unit_interval(self):
        for sr in (-1.0, 0.0, 0.3, 2.0):
            p = probabilistic_sharpe_ratio(sr, 60)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_psr_too_short_sample_is_zero(self):
        self.assertEqual(probabilistic_sharpe_ratio(1.0, 1), 0.0)

    def test_strong_sample_dsr_near_one(self):
        rng = np.random.default_rng(_SEED)
        rets = rng.normal(0.01, 0.005, 60)  # sr ~ 2.0 per period
        d = deflated_sharpe_ratio(rets, n_trials=2)
        self.assertGreater(d["sr"], 1.0)
        self.assertGreater(d["dsr"], 0.8)

    def test_pure_noise_dsr_low(self):
        rng = np.random.default_rng(_SEED + 1)
        rets = rng.normal(0.0, 0.01, 60)
        d = deflated_sharpe_ratio(rets, n_trials=10)
        self.assertLess(d["dsr"], 0.5)

    def test_dsr_deflation_monotonic_in_n_trials(self):
        rng = np.random.default_rng(_SEED)
        rets = rng.normal(0.01, 0.005, 60)
        few = deflated_sharpe_ratio(rets, n_trials=2)
        many = deflated_sharpe_ratio(rets, n_trials=1000)
        self.assertLessEqual(many["dsr"], few["dsr"])

    def test_dsr_returns_documented_keys(self):
        rng = np.random.default_rng(_SEED)
        rets = rng.normal(0.01, 0.005, 60)
        d = deflated_sharpe_ratio(rets, n_trials=5)
        for k in ("sr", "psr", "dsr", "sr_benchmark", "n"):
            self.assertIn(k, d)

    def test_expected_max_sharpe_zero_below_two_trials(self):
        self.assertEqual(expected_max_sharpe(0.1, 1), 0.0)
        self.assertEqual(expected_max_sharpe(0.1, 0), 0.0)
        self.assertEqual(expected_max_sharpe(0.0, 100), 0.0)

    def test_expected_max_sharpe_increases_with_trials(self):
        prev = -1.0
        for nt in (2, 10, 100, 1000):
            v = expected_max_sharpe(0.1, nt)
            self.assertGreater(v, prev)
            prev = v


# ── PBO via CSCV ─────────────────────────────────────────────────────────────────
class TestPBO(unittest.TestCase):
    def test_no_skill_pbo_around_half(self):
        rng = np.random.default_rng(_SEED)
        M = rng.normal(0.0, 1.0, size=(20, 10))
        res = pbo_cscv(M)
        self.assertGreater(res["pbo"], 0.2)
        self.assertLess(res["pbo"], 0.8)
        self.assertGreater(res["n_combos"], 0)

    def test_constructed_overfit_high_pbo(self):
        # Each row de-meaned => row sum == 0 => OOS half-mean == -(IS half-mean)
        # exactly, so the IS-best config is the OOS-worst in EVERY split => pbo ~ 1.
        rng = np.random.default_rng(_SEED + 7)
        M = rng.normal(0.0, 1.0, size=(20, 10))
        M = M - M.mean(axis=1, keepdims=True)
        res = pbo_cscv(M)
        self.assertGreater(res["pbo"], 0.5)

    def test_odd_block_count_raises(self):
        rng = np.random.default_rng(_SEED)
        with self.assertRaises(ValueError):
            pbo_cscv(rng.normal(size=(5, 5)))

    def test_too_few_blocks_raises(self):
        rng = np.random.default_rng(_SEED)
        with self.assertRaises(ValueError):
            pbo_cscv(rng.normal(size=(5, 2)))

    def test_too_few_configs_raises(self):
        rng = np.random.default_rng(_SEED)
        with self.assertRaises(ValueError):
            pbo_cscv(rng.normal(size=(1, 8)))


# ── Information Coefficient ──────────────────────────────────────────────────────
class TestInformationCoefficient(unittest.TestCase):
    def test_perfect_rank_corr_ic_near_plus_one(self):
        x = np.arange(200, dtype=float)
        fwd = 3.0 * x + 5.0  # strictly monotone increasing
        self.assertAlmostEqual(information_coefficient(x, fwd), 1.0, places=6)

    def test_perfect_anti_corr_ic_near_minus_one(self):
        x = np.arange(200, dtype=float)
        self.assertAlmostEqual(information_coefficient(x, -x), -1.0, places=6)

    def test_noise_ic_near_zero(self):
        rng = np.random.default_rng(_SEED)
        a = rng.normal(size=400)
        b = rng.normal(size=400)
        self.assertLess(abs(information_coefficient(a, b)), 0.3)

    def test_too_short_returns_zero(self):
        self.assertEqual(information_coefficient([1.0], [2.0]), 0.0)


# ── multi-objective fitness + journal blend ──────────────────────────────────────
class TestFitness(unittest.TestCase):
    def setUp(self):
        self.ohlcv = _OHLCV
        self.feat = _FEAT
        self.strategy = random_strategy(
            _FEATURES, np.random.default_rng(11), market="CRYPTO"
        )

    def test_evaluate_oos_documented_keys(self):
        oos = evaluate_oos(self.strategy, self.ohlcv, features=self.feat)
        for k in (
            "oos_total_return", "oos_sharpe_mean", "n_trades", "expectancy",
            "win_rate", "profit_factor", "max_drawdown", "trade_returns", "n_folds",
        ):
            self.assertIn(k, oos)
        self.assertIsInstance(oos["trade_returns"], list)
        self.assertEqual(oos["n_folds"], 4)

    def test_multi_objective_no_trades_is_sentinel(self):
        empty = {
            "oos_total_return": 0.0, "oos_sharpe_mean": 0.0, "n_trades": 0,
            "expectancy": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
            "max_drawdown": 0.0,
        }
        score, objectives, components = multi_objective(empty)
        self.assertEqual(score, -1e9)
        self.assertEqual(len(objectives), 4)

    def test_fitness_objectives_is_four_tuple(self):
        fit = fitness(self.strategy, self.ohlcv, features=self.feat)
        self.assertIsInstance(fit.objectives, tuple)
        self.assertEqual(len(fit.objectives), 4)
        self.assertTrue(all(np.isfinite(o) for o in fit.objectives))

    def test_realized_blend_adds_component_and_changes_score(self):
        base = fitness(self.strategy, self.ohlcv, features=self.feat)
        blended = fitness(
            self.strategy, self.ohlcv, features=self.feat,
            realized_trade_returns=[0.02, -0.01, 0.03, 0.015],
        )
        self.assertIn("realized_expectancy", blended.components)
        self.assertNotIn("realized_expectancy", base.components)
        self.assertNotEqual(base.score, blended.score)
        self.assertIsNotNone(blended.realized)

    def test_journal_realized_none(self):
        self.assertIsNone(journal_realized(None))
        self.assertIsNone(journal_realized([]))

    def test_journal_realized_summary(self):
        d = journal_realized([0.01, -0.02, 0.03])
        for k in ("n", "expectancy", "win_rate", "profit_factor"):
            self.assertIn(k, d)
        self.assertEqual(d["n"], 3)
        self.assertAlmostEqual(d["win_rate"], 2 / 3 * 100.0, places=6)
        self.assertAlmostEqual(d["profit_factor"], 0.04 / 0.02, places=6)


# ── the guardrail gate ───────────────────────────────────────────────────────────
class TestGuardrailGate(unittest.TestCase):
    def setUp(self):
        self.ohlcv = _OHLCV
        self.feat = _FEAT
        self.strategy = random_strategy(
            _FEATURES, np.random.default_rng(11), market="CRYPTO"
        )

    def test_weak_strategy_fails_with_reasons(self):
        # Massive trial count deflates DSR below threshold => guaranteed failure.
        report = passes_guardrails(
            self.strategy, self.ohlcv, features=self.feat, n_trials=100_000
        )
        self.assertFalse(report.passed)
        self.assertGreater(len(report.reasons), 0)

    def test_report_is_json_serializable(self):
        report = passes_guardrails(
            self.strategy, self.ohlcv, features=self.feat, n_trials=100_000
        )
        d = report.as_dict()
        # round-trips with stdlib json => no numpy types leaking
        s = json.dumps(d)
        self.assertIsInstance(s, str)
        self.assertNotIn("trade_returns", d["oos"])

    def test_report_has_expected_shape(self):
        report = passes_guardrails(
            self.strategy, self.ohlcv, features=self.feat, n_trials=2
        )
        self.assertIsInstance(report.passed, bool)
        self.assertIsInstance(report.reasons, list)
        self.assertIn("dsr", report.dsr)
        self.assertIn("n_trades", report.oos)


if __name__ == "__main__":
    unittest.main()
