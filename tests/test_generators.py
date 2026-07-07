"""tests/test_generators.py — the Strategy-Generator Portfolio (offline/CPU parts).

Covers the scaffold (candidate contract + rebuild round-trip + shared gate) and the generators
that need no network/Julia: gplearn symbolic regression, pyribs quality-diversity, Optuna tuning,
formulaic-alpha mining, and the family-wise (StepM) control. The LLM-mutation, PySR and RD-Agent
generators need a live LLM / Julia and are exercised by the live smoke tests, not here.
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import trading.state as state


def _synth(n=320, seed=3):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0006, 0.012, n) + 0.003 * np.sin(np.arange(n) / 18)))
    return pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996,
                         "close": close, "volume": rng.uniform(1e3, 9e3, n)})


class TestScaffold(unittest.TestCase):
    def setUp(self):
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="gen_test_"))
        self.ohlcv = _synth()
        from trading.strategy.features import compute_features
        self.feats = compute_features(self.ohlcv)

    def test_expression_candidate_and_rebuild(self):
        from trading.strategy.generators import ExpressionStrategy, rebuild
        c = ExpressionStrategy(market="CRYPTO", features=["close", "open"],
                               expr="Sub(close, Mean(close, 20))", kind="alpha", id="t1")
        sig = c.signal(self.feats)
        self.assertEqual(len(sig), len(self.feats))
        self.assertTrue(set(np.unique(sig)).issubset({-1, 0, 1}))
        c2 = rebuild(c.to_dict())
        self.assertEqual(type(c2).__name__, "ExpressionStrategy")
        self.assertEqual(c2.expr, c.expr)

    def test_genome_rebuild_default_type(self):
        from trading.strategy.generators import rebuild
        from trading.strategy.genome import random_strategy
        from trading.strategy.operators import market_features
        s = random_strategy(market_features("CRYPTO"), np.random.default_rng(1),
                            market="CRYPTO", strat_id="g1")
        r = rebuild(s.to_dict())                      # no __type__ → genome
        self.assertEqual(type(r).__name__, "Strategy")

    def test_shared_gate_admits_through_library(self):
        from trading.brain.skills import SkillLibrary
        from trading.strategy.generators import ExpressionStrategy, evaluate_and_admit
        lib = SkillLibrary(persist=False)
        c = ExpressionStrategy(market="CRYPTO", features=["close"],
                               expr="Div(Delta(close, 5), Std(close, 20))", kind="alpha", id="a1")
        res = evaluate_and_admit([c], self.ohlcv, library=lib, market="CRYPTO", features=self.feats)
        self.assertEqual(res["tested"], 1)
        self.assertIn("guardrail_passed", res)


class TestGenerators(unittest.TestCase):
    def setUp(self):
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="gen_test_"))
        self.ohlcv = _synth(seed=7)
        from trading.strategy.features import compute_features
        self.feats = compute_features(self.ohlcv)

    def _check(self, gen):
        self.assertTrue(gen.available())
        cands = gen.generate(self.ohlcv, "CRYPTO", features=self.feats, budget=5, seed=7)
        self.assertGreater(len(cands), 0, f"{gen.name} produced no candidates")
        s = cands[0].signal(self.feats)
        self.assertTrue(set(np.unique(s)).issubset({-1, 0, 1}))

    def test_gplearn(self):
        from trading.strategy.generators.symbolic import GplearnGenerator
        self._check(GplearnGenerator())

    def test_quality_diversity(self):
        from trading.strategy.generators.quality_diversity import QualityDiversityGenerator
        self._check(QualityDiversityGenerator())

    def test_optuna(self):
        from trading.strategy.generators.optuna_tune import OptunaGenerator
        self._check(OptunaGenerator())

    def test_alpha_mining(self):
        from trading.strategy.generators.alpha_mining import AlphaMiningGenerator
        self._check(AlphaMiningGenerator())


class TestFamilyWise(unittest.TestCase):
    def test_stepm_isolates_signal_from_noise(self):
        from trading.strategy.generators.stats_gate import family_wise_superior
        rng = np.random.default_rng(0)
        fr = {"good": [0.03, 0.05, 0.02, 0.04, 0.06, 0.03, 0.05, 0.04, 0.03, 0.05, 0.02, 0.04],
              "n1": list(rng.normal(0, 0.01, 12)), "n2": list(rng.normal(0, 0.01, 12)),
              "n3": list(rng.normal(0, 0.01, 12))}
        superior = family_wise_superior(fr)
        self.assertIn("good", superior)

    def test_stepm_fail_open_small_sample(self):
        from trading.strategy.generators.stats_gate import family_wise_superior
        fr = {"a": [0.01, 0.02], "b": [0.01, 0.0]}    # <8 paths → fail-open (all pass)
        self.assertEqual(family_wise_superior(fr), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
