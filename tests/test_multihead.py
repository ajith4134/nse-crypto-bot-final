"""Acceptance test (multi-output): every output head must beat its task baseline.

Guards the plan's output-LAYER realignment — the network predicts several targets
at once (binary direction, multiclass regime, regression magnitude), and each
head's meta must outperform the honest per-task baseline (majority for
classification, mean-predictor for regression) under walk-forward evaluation.
Also checks the multi-output structure (one ŷ output node per head, per-node
head/task binding) the dashboard relies on.
"""
from __future__ import annotations

import unittest

import run_multi


class TestMultiHead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # smaller n keeps the CI gate fast while preserving real signal
        cls.state = run_multi.main("mackey_glass", n=900)

    def test_three_heads_present(self):
        names = {h["name"] for h in self.state["heads"]}
        self.assertEqual(names, {"direction", "regime", "magnitude"})
        self.assertTrue(self.state.get("multi_output"))

    def test_every_head_beats_its_baseline(self):
        for h in self.state["heads"]:
            self.assertGreater(
                h["value"], h["baseline"],
                f"head '{h['name']}' ({h['metric']}={h['value']}) did not beat "
                f"baseline {h['baseline']}")

    def test_one_real_output_node_per_head(self):
        outs = [n for n in self.state["nodes"] if n["kind"] == "output"]
        self.assertEqual(len(outs), 3)
        # each output is bound to its head and fed by a real upstream meta
        for o in outs:
            self.assertIn(o["head"], {"direction", "regime", "magnitude"})
            self.assertTrue(o["upstream"], f"output {o['name']} has no real upstream")

    def test_per_node_head_and_task_binding(self):
        # regression head's nodes must be tagged task=regression; classification not
        mag = [n for n in self.state["nodes"] if n["head"] == "magnitude" and n["kind"] != "output"]
        self.assertTrue(mag)
        self.assertTrue(all(n["task"] == "regression" for n in mag))
        regime = [n for n in self.state["nodes"] if n["head"] == "regime" and n["kind"] == "base"]
        self.assertTrue(all(n["task"] == "multiclass" for n in regime))


if __name__ == "__main__":
    unittest.main()
