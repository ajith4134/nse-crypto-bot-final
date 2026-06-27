"""Acceptance test (hardening): the router-grown brain must beat the naive
baseline on average across seeds — guards against regressions in growth/routing.
"""
from __future__ import annotations

import unittest

import run_robust


class TestRobust(unittest.TestCase):
    def test_beats_baseline_across_seeds(self):
        s = run_robust.main(seeds=[1, 2, 3])
        self.assertGreater(
            s["mean"], s["baseline_mean"] + 0.08,
            f"grown brain mean {s['mean']} not clearly above baseline {s['baseline_mean']}: {s}")

    def test_stable_and_every_seed_beats_baseline(self):
        s = run_robust.main(seeds=[1, 2, 3])
        self.assertLess(s["std"], 0.1, f"unstable across seeds: {s}")
        for r in s["runs"]:
            self.assertGreater(r["test"], r["baseline"] + 0.1,
                               f"seed {r['seed']} did not beat baseline: {r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
