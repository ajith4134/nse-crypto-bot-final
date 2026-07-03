"""Optuna HPO utility (core/hpo.py, Tier-2/3 infra group H)."""
from __future__ import annotations

import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")

from core.hpo import optimize, tune_node


class TestHPO(unittest.TestCase):
    def test_optimize_finds_optimum(self):
        # maximize -(x-3)^2 + (y=="b") ; optimum near x=3, y="b"
        space = {"x": ("float", 0.0, 6.0), "y": ("cat", ["a", "b"])}
        res = optimize(lambda p: -((p["x"] - 3.0) ** 2) + (1.0 if p["y"] == "b" else 0.0),
                       space, n_trials=40, seed=1)
        self.assertIn(res["backend"], ("optuna", "random"))
        self.assertLess(abs(res["params"]["x"] - 3.0), 1.2)
        self.assertEqual(res["params"]["y"], "b")

    def test_optimize_int_space(self):
        res = optimize(lambda p: -abs(p["k"] - 7), {"k": ("int", 1, 15)}, n_trials=30, seed=2)
        self.assertLessEqual(abs(res["params"]["k"] - 7), 2)

    def test_tune_node_classification(self):
        # separable-ish synthetic tabular problem; tune a KNN node's k
        try:
            from nodes.oss_nodes import knn_node
        except Exception:
            self.skipTest("oss knn node absent")
        rng = np.random.default_rng(0)
        n = 200
        X = rng.standard_normal((n, 4)).tolist()
        y = [1 if (row[0] + row[1]) > 0 else 0 for row in X]
        res = tune_node(lambda k=5: knn_node(int(k), f"knn{int(k)}"),
                        space={"k": ("int", 3, 25)}, X=X, y=y, n_trials=8, task="binary")
        self.assertIn("params", res)
        self.assertGreaterEqual(res["score"], 0.5)   # beats coin flip on separable data
        self.assertIn(res["params"]["k"], range(3, 26))


if __name__ == "__main__":
    unittest.main()
