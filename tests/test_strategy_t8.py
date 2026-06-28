"""Trading Phase T8.1 (Strategy-Evolution Engine) acceptance tests — fully offline.

Rewritten for the REUSE-FIRST T8.1 stack: features via **TA-Lib**
(trading/strategy/features.py), the genome + operators via **DEAP** genetic programming
(genome.py / operators.py), and the backtest via **vectorbt** (backtest.py). The old
hand-rolled API (Predicate / BoolNode / FEATURE_SPECS) is gone.

Every RNG is a seeded ``np.random.default_rng(<fixed int>)`` and the synthetic OHLCV is a
seeded geometric random walk, so the whole suite is deterministic + offline on every run.
"""
from __future__ import annotations

import math
import unittest
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from trading.strategy.backtest import backtest_signal, walk_forward_folds
from trading.strategy.features import FEATURE_NAMES, compute_features
from trading.strategy.genome import Strategy, random_strategy
from trading.strategy.operators import crossover, market_features, mutate

_SEED = 20260628


def _make_ohlcv(n: int = 700, seed: int = _SEED) -> pd.DataFrame:
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
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )
    # sanity: envelope invariants hold
    assert (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9).all()
    return df


# module-level cache so we compute features only once for the whole suite
_OHLCV = _make_ohlcv()
_FEAT = compute_features(_OHLCV)
_FEATURES = market_features("CRYPTO")


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.ohlcv = _OHLCV
        self.feat = _FEAT

    def test_missing_column_raises(self):
        with self.assertRaises(ValueError):
            compute_features(self.ohlcv.drop(columns=["volume"]))

    def test_missing_close_raises(self):
        with self.assertRaises(ValueError):
            compute_features(self.ohlcv.drop(columns=["close"]))

    def test_has_all_feature_columns(self):
        for name in FEATURE_NAMES:
            self.assertIn(name, self.feat.columns)

    def test_no_nans_after_warmup(self):
        self.assertFalse(self.feat[FEATURE_NAMES].isna().any().any())

    def test_warmup_rows_dropped(self):
        self.assertLess(len(self.feat), len(self.ohlcv))
        self.assertGreater(len(self.feat), 0)

    def test_rsi_bounded(self):
        self.assertGreaterEqual(self.feat["rsi"].min(), 0.0)
        self.assertLessEqual(self.feat["rsi"].max(), 100.0)

    def test_index_is_rangeindex(self):
        self.assertIsInstance(self.feat.index, pd.RangeIndex)
        self.assertEqual(self.feat.index[0], 0)
        self.assertEqual(list(self.feat.index), list(range(len(self.feat))))


class TestGenome(unittest.TestCase):
    def setUp(self):
        self.feat = _FEAT
        self.features = _FEATURES

    def test_random_strategy_seed_determinism(self):
        s1 = random_strategy(self.features, np.random.default_rng(123), market="CRYPTO")
        s2 = random_strategy(self.features, np.random.default_rng(123), market="CRYPTO")
        self.assertEqual(s1.to_dict(), s2.to_dict())

    def test_random_strategy_different_seeds_differ(self):
        s1 = random_strategy(self.features, np.random.default_rng(123), market="CRYPTO")
        s3 = random_strategy(self.features, np.random.default_rng(124), market="CRYPTO")
        self.assertNotEqual(s1.to_dict(), s3.to_dict())

    def test_signal_values_subset(self):
        s = random_strategy(self.features, np.random.default_rng(11), market="CRYPTO")
        sig = s.signal(self.feat)
        self.assertTrue(set(sig.unique()).issubset({-1, 0, 1}))

    def test_signal_has_no_nan(self):
        s = random_strategy(self.features, np.random.default_rng(11), market="CRYPTO")
        self.assertFalse(s.signal(self.feat).isna().any())

    def test_to_dict_has_long_src_and_features(self):
        s = random_strategy(self.features, np.random.default_rng(99), market="CRYPTO")
        d = s.to_dict()
        self.assertIn("long_src", d)
        self.assertIn("features", d)
        self.assertEqual(d["features"], list(self.features))

    def test_round_trip_to_from_dict_equal(self):
        s = random_strategy(self.features, np.random.default_rng(99), market="CRYPTO",
                            strat_id="x1")
        again = Strategy.from_dict(s.to_dict())
        self.assertEqual(again.to_dict(), s.to_dict())

    def test_round_trip_still_evaluable(self):
        s = random_strategy(self.features, np.random.default_rng(99), market="CRYPTO",
                            strat_id="x1")
        again = Strategy.from_dict(s.to_dict())
        sig = again.signal(self.feat)
        self.assertFalse(sig.isna().any())
        self.assertTrue(set(sig.unique()).issubset({-1, 0, 1}))


class TestOperators(unittest.TestCase):
    def setUp(self):
        self.feat = _FEAT
        self.features = _FEATURES

    def test_market_features_nonempty(self):
        feats = market_features("CRYPTO")
        self.assertIsInstance(feats, list)
        self.assertGreater(len(feats), 0)

    def test_mutate_returns_new_object(self):
        s = random_strategy(self.features, np.random.default_rng(7), market="CRYPTO",
                            strat_id="s0")
        child = mutate(s, self.features, np.random.default_rng(8))
        self.assertIsNot(child, s)

    def test_mutate_leaves_original_unchanged(self):
        s = random_strategy(self.features, np.random.default_rng(7), market="CRYPTO",
                            strat_id="s0")
        before = s.to_dict()
        mutate(s, self.features, np.random.default_rng(8))
        self.assertEqual(s.to_dict(), before)

    def test_mutate_evaluable(self):
        s = random_strategy(self.features, np.random.default_rng(7), market="CRYPTO",
                            strat_id="s0")
        child = mutate(s, self.features, np.random.default_rng(8))
        self.assertFalse(child.signal(self.feat).isna().any())

    def test_mutate_bumps_generation(self):
        s = random_strategy(self.features, np.random.default_rng(7), market="CRYPTO",
                            strat_id="s0")
        before_gen = s.provenance["generation"]
        child = mutate(s, self.features, np.random.default_rng(8))
        self.assertEqual(child.provenance["generation"], before_gen + 1)
        self.assertIn("s0", child.provenance["parents"])

    def test_mutate_stress_all_children_evaluable(self):
        """Guard the DEAP typed-GP generation pitfall: many seeds must all stay valid."""
        s = random_strategy(self.features, np.random.default_rng(7), market="CRYPTO",
                            strat_id="s0")
        for seed in range(30):
            child = mutate(s, self.features, np.random.default_rng(1000 + seed))
            sig = child.signal(self.feat)
            self.assertFalse(sig.isna().any(), f"seed {seed} produced NaN signal")
            self.assertTrue(set(sig.unique()).issubset({-1, 0, 1}))

    def test_crossover_children_evaluable_and_provenance(self):
        a = random_strategy(self.features, np.random.default_rng(1), market="CRYPTO",
                            strat_id="a")
        b = random_strategy(self.features, np.random.default_rng(2), market="CRYPTO",
                            strat_id="b")
        ca, cb = crossover(a, b, np.random.default_rng(3))
        self.assertFalse(ca.signal(self.feat).isna().any())
        self.assertFalse(cb.signal(self.feat).isna().any())
        self.assertEqual(set(ca.provenance["parents"]), {"a", "b"})
        self.assertEqual(set(cb.provenance["parents"]), {"a", "b"})

    def test_crossover_mismatched_features_raises(self):
        a = random_strategy(self.features, np.random.default_rng(1), market="CRYPTO",
                            strat_id="a")
        b = random_strategy(self.features[:-1], np.random.default_rng(2), market="CRYPTO",
                            strat_id="b")
        with self.assertRaises(ValueError):
            crossover(a, b, np.random.default_rng(3))


class TestBacktest(unittest.TestCase):
    def setUp(self):
        self.feat = _FEAT

    def test_all_zero_signal(self):
        sig = pd.Series(np.zeros(len(self.feat)))
        res = backtest_signal(sig, self.feat, fee_bps=0, slippage_bps=0)
        self.assertEqual(res.metrics["total_return"], 0.0)
        self.assertEqual(res.metrics["n_trades"], 0)

    def test_all_metric_keys_present_and_finite(self):
        s = random_strategy(_FEATURES, np.random.default_rng(5), market="CRYPTO")
        res = backtest_signal(s.signal(self.feat), self.feat)
        keys = ("total_return", "sharpe", "max_drawdown", "n_trades", "win_rate",
                "profit_factor", "avg_win", "avg_loss", "expectancy",
                "gross_win", "gross_loss")
        for key in keys:
            self.assertIn(key, res.metrics)
            v = res.metrics[key]
            # profit_factor may legitimately be +inf in the zero-loss case only
            if key == "profit_factor" and math.isinf(v):
                self.assertEqual(res.metrics["gross_loss"], 0.0)
                continue
            self.assertTrue(np.isfinite(v), f"{key} not finite: {v}")

    def test_perfect_foresight_is_profitable(self):
        """A signal that knows NEXT bar's return should make money + trade."""
        close = self.feat["close"].reset_index(drop=True)
        # position at bar t (= signal.shift(1)) should equal sign of return into bar t,
        # so signal[i] = sign(close[i+1]/close[i] - 1)
        nxt_ret = close.shift(-1) / close - 1.0
        sig = np.sign(nxt_ret).fillna(0.0).astype(int)
        res = backtest_signal(sig, self.feat, fee_bps=0, slippage_bps=0)
        self.assertGreater(res.metrics["total_return"], 0.0)
        self.assertGreater(res.metrics["n_trades"], 0)


class TestWalkForward(unittest.TestCase):
    def test_rolling_folds_contiguous_and_causal(self):
        n_rows, n_folds = 600, 4
        folds = walk_forward_folds(n_rows, n_folds=n_folds, scheme="rolling")
        self.assertEqual(len(folds), n_folds)
        prev_test_end = None
        for f in folds:
            tr_s, tr_e = f["train"]
            te_s, te_e = f["test"]
            self.assertLessEqual(tr_e, te_s)          # train precedes test
            self.assertLess(tr_s, tr_e)               # non-empty train
            self.assertLess(te_s, te_e)               # non-empty test
            if prev_test_end is not None:
                self.assertEqual(te_s, prev_test_end)  # contiguous, non-overlapping
            prev_test_end = te_e
        self.assertEqual(folds[-1]["test"][1], n_rows)  # tail coverage

    def test_anchored_train_starts_at_zero(self):
        folds = walk_forward_folds(600, n_folds=4, scheme="anchored")
        for f in folds:
            self.assertEqual(f["train"][0], 0)
            self.assertLessEqual(f["train"][1], f["test"][0])

    def test_too_many_folds_raises(self):
        with self.assertRaises(ValueError):
            walk_forward_folds(5, n_folds=4)


if __name__ == "__main__":
    unittest.main()
