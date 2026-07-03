"""Cloud-LLM telemetry (core/llm_telemetry.py) + LLMForecastNode (nodes/llm_forecast_node.py)."""
from __future__ import annotations

import os
import tempfile
import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


class TestLLMTelemetry(unittest.TestCase):
    def setUp(self):
        from core import llm_telemetry as LT
        self.LT = LT
        self._orig = LT._PATH
        LT._PATH = os.path.join(tempfile.mkdtemp(), "t.json")
        LT.reset()

    def tearDown(self):
        self.LT._PATH = self._orig

    def test_record_and_snapshot(self):
        LT = self.LT
        LT.record("groq", True, 120.0, None)
        LT.record("groq", True, 90.0, None)
        LT.record("groq", False, 30.0, "429 rate limit exceeded")
        LT.record("cerebras", False, 5.0, "connection timeout")
        snap = LT.snapshot(["groq", "cerebras", "gemini"])
        g = next(p for p in snap["providers"] if p["provider"] == "groq")
        self.assertEqual(g["calls"], 3)
        self.assertEqual(g["hits"], 2)
        self.assertEqual(g["rate_limited"], 1)
        self.assertEqual(g["status"], "cooling")          # rate-limit sets a cooldown
        self.assertGreater(g["reload_in_sec"], 0)
        self.assertAlmostEqual(g["hit_rate"], 2 / 3, places=2)
        # a never-called configured provider shows as idle
        gm = next(p for p in snap["providers"] if p["provider"] == "gemini")
        self.assertEqual(gm["status"], "idle")
        self.assertEqual(snap["totals"]["calls"], 4)

    def test_success_clears_cooldown(self):
        LT = self.LT
        LT.record("groq", False, 10.0, "quota exceeded")
        self.assertEqual(LT.snapshot(["groq"])["providers"][0]["status"], "cooling")
        LT.record("groq", True, 50.0, None)               # a later success un-cools it
        self.assertEqual(LT.snapshot(["groq"])["providers"][0]["status"], "active")


class TestLLMForecastNode(unittest.TestCase):
    def test_node_contract_offline_fallback(self):
        # No network call needed: with MAX_CALLS tiny + likely-unconfigured LLM, the node
        # falls back to its momentum heuristic and must still satisfy NodeProtocol.
        from nodes.llm_forecast_node import LLMForecastNode
        rng = np.random.default_rng(7)
        n = 80
        ys = np.cumsum(rng.standard_normal(n)) * 0.5
        X = [[float(ys[i]), float(np.mean(ys[max(0, i - 5):i + 1]))] for i in range(n)]
        y = [1 if v > 0 else 0 for v in np.diff(ys, append=ys[-1])]
        nd = LLMForecastNode()
        nd.task = "binary"
        nd.MAX_CALLS = 1
        nd.fit(X[:64], y[:64])
        p = nd.predict_proba(X[64:])
        self.assertEqual(len(p), len(X[64:]))
        self.assertTrue(all(np.isfinite(v) and 0.0 <= v <= 1.0 for v in p))

    def test_parse_directional_json(self):
        from nodes.llm_forecast_node import LLMForecastNode
        self.assertGreater(LLMForecastNode._parse('{"dir": 0.8, "conf": 1.0}'), 0)
        self.assertLess(LLMForecastNode._parse('{"dir": -0.6, "conf": 1.0}'), 0)
        self.assertGreater(LLMForecastNode._parse("looks bullish to me"), 0)


if __name__ == "__main__":
    unittest.main()
