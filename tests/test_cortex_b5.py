"""CORTEX B5 acceptance tests — evolution lane + SimLab.

Covers signal construction, the zero-cost triage gate, the neat-python lane (fitness
improves, backtests are counted), the REINFORCE edge learner, the grow/prune controller,
and the psychology-free order-matching SimLab (both backends + determinism).
"""
from __future__ import annotations

import unittest

import numpy as np

from nodes.neat_lane import (GrowPruneController, NeatLane, ReinforceEdgeLearner,
                             signals_from_scores, zero_cost_triage)
from trading.simlab import SimLab


def _sim_close(seed=1, n=150):
    close = SimLab(seed=seed).price_series(n)
    feats = np.column_stack([close, np.gradient(close), np.abs(np.gradient(close))])
    return feats, close


class TestSignals(unittest.TestCase):
    def test_edge_triggered(self):
        scores = np.array([-1, -1, 0.5, 0.6, 0.6, -0.5, -0.5, 0.4])
        entries, exits = signals_from_scores(scores)
        self.assertEqual(int(entries.sum()), 2)      # two long entries
        self.assertEqual(int(exits.sum()), 1)        # one exit between them
        # entry precedes its exit
        self.assertLess(np.argmax(entries), np.argmax(exits))

    def test_no_double_entry_while_in_position(self):
        scores = np.array([0.9, 0.9, 0.9, 0.9])
        entries, _ = signals_from_scores(scores)
        self.assertEqual(int(entries.sum()), 1)


class TestZeroCostTriage(unittest.TestCase):
    def test_rejects_dead_signal(self):
        ok, info = zero_cost_triage(np.full(50, -1.0), np.linspace(100, 101, 50))
        self.assertFalse(ok)
        self.assertEqual(info["reason"], "degenerate_activity")

    def test_rejects_saturated_signal(self):
        ok, _ = zero_cost_triage(np.full(50, 1.0), np.linspace(100, 101, 50))
        self.assertFalse(ok)

    def test_accepts_live_signal(self):
        rng = np.random.default_rng(0)
        close = np.cumsum(rng.normal(0, 1, 100)) + 100
        scores = np.tanh(np.gradient(close))          # some activity, some corr
        ok, info = zero_cost_triage(scores, close)
        self.assertTrue(ok)
        self.assertIn("proxy_corr", info)


class TestNeatLane(unittest.TestCase):
    def test_evolve_improves_and_counts_backtests(self):
        feats, close = _sim_close()
        lane = NeatLane(feats, close, pop_size=25, seed=0)
        best, tel = lane.evolve(n_generations=5)
        self.assertIsNotNone(best)
        self.assertGreater(tel.backtests_run, 0)              # backtests are counted
        self.assertEqual(len(tel.history), 5)
        # best-so-far fitness is monotonic non-decreasing across generations
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(tel.history, tel.history[1:])))

    def test_features_must_align(self):
        with self.assertRaises(ValueError):
            NeatLane(np.zeros((10, 3)), np.zeros(9))

    def test_complexity_reported(self):
        feats, close = _sim_close()
        best, _ = NeatLane(feats, close, pop_size=15, seed=1).evolve(2)
        c = NeatLane.complexity(best)
        self.assertIn("nodes", c)
        self.assertIn("connections", c)

    def test_telemetry_savings_fraction(self):
        feats, close = _sim_close()
        _, tel = NeatLane(feats, close, pop_size=20, seed=2).evolve(3)
        d = tel.as_dict()
        self.assertGreaterEqual(d["triage_savings"], 0.0)
        self.assertLessEqual(d["triage_savings"], 1.0)


class TestReinforceEdgeLearner(unittest.TestCase):
    def test_converges_to_high_reward_edges(self):
        rl = ReinforceEdgeLearner(6, lr=0.3, seed=0)
        rl.optimize(lambda a: float(a[:3].mean()), iters=150)
        p = rl.probs()
        self.assertGreater(float(p[:3].mean()), float(p[3:].mean()))

    def test_baseline_warm_start(self):
        rl = ReinforceEdgeLearner(4, seed=0)
        rl.update(np.array([1, 0, 1, 0]), 5.0)
        self.assertAlmostEqual(rl._baseline, 5.0)     # first reward seeds the baseline

    def test_theta_bounded(self):
        rl = ReinforceEdgeLearner(3, lr=5.0, seed=0)
        for _ in range(50):
            rl.update(np.ones(3), 100.0)
        self.assertTrue(np.all(np.abs(rl.theta) <= 10.0 + 1e-9))


class TestGrowPruneController(unittest.TestCase):
    def test_should_grow_on_plateau(self):
        gp = GrowPruneController(patience=3, plateau_eps=1e-3)
        self.assertTrue(gp.should_grow([1.0, 0.5, 0.4, 0.4, 0.4, 0.4]))

    def test_no_grow_while_improving(self):
        gp = GrowPruneController(patience=3, plateau_eps=1e-3)
        self.assertFalse(gp.should_grow([1.0, 0.8, 0.6, 0.4, 0.2, 0.05]))

    def test_gradmax_output_preserving(self):
        w_in, w_out = GrowPruneController.gradmax_init(5, 3, seed=0)
        self.assertEqual(w_in.shape, (5,))
        self.assertTrue(np.all(w_out == 0.0))         # outgoing zero => no output change
        self.assertAlmostEqual(float(np.linalg.norm(w_in)), 1.0, places=5)

    def test_prune_keeps_fraction(self):
        w = np.array([0.1, -0.9, 0.2, 0.8, -0.05])
        pruned = GrowPruneController.prune(w, keep_frac=0.4)
        self.assertEqual(int(np.sum(pruned != 0)), 2)  # keeps the 2 largest-|w|
        self.assertNotEqual(pruned[1], 0.0)            # -0.9 kept
        self.assertEqual(pruned[4], 0.0)               # -0.05 pruned


class TestSimLab(unittest.TestCase):
    def test_produces_price_path(self):
        res = SimLab(seed=1).run(120)
        self.assertEqual(len(res.mid), 120)
        self.assertGreater(res.n_trades, 0)
        self.assertTrue(np.all(np.isfinite(res.mid)))

    def test_deterministic_by_seed(self):
        a = SimLab(seed=7).price_series(80)
        b = SimLab(seed=7).price_series(80)
        np.testing.assert_array_equal(a, b)

    def test_numpy_backend_standalone(self):
        sim = SimLab(seed=3)
        res = sim._run_numpy(100)
        self.assertEqual(len(res.mid), 100)
        self.assertTrue(np.all(np.isfinite(res.mid)))

    def test_different_seeds_differ(self):
        a = SimLab(seed=1).price_series(80)
        b = SimLab(seed=2).price_series(80)
        self.assertFalse(np.array_equal(a, b))


if __name__ == "__main__":
    unittest.main()
