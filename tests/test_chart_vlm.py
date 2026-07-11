"""Tests for trading/broker_sense/chart_vlm.py — Lane B VLM chart reader.

Covers: JSON parsing (clean / fenced / chatty / garbage), canonical normalization
(score↔direction derivation, clamping, p_up mapping), horizon tagging, and honest
degradation when no vision provider is configured or the model errors. No network:
core.llm.vision_chat / vision_available are stubbed.
"""
from __future__ import annotations

import unittest
from unittest import mock

from trading.broker_sense import chart_vlm


class TestParse(unittest.TestCase):
    def test_clean_json(self):
        o = chart_vlm._parse('{"direction":"long","score":0.7}')
        self.assertEqual(o["direction"], "long")

    def test_fenced_json(self):
        o = chart_vlm._parse('```json\n{"direction":"short","score":-0.4}\n```')
        self.assertEqual(o["score"], -0.4)

    def test_chatty_json(self):
        o = chart_vlm._parse('Sure! Here it is: {"direction":"flat","score":0.0} — hope it helps')
        self.assertEqual(o["direction"], "flat")

    def test_garbage_returns_none(self):
        self.assertIsNone(chart_vlm._parse("no json here"))
        self.assertIsNone(chart_vlm._parse(""))
        self.assertIsNone(chart_vlm._parse(None))


class TestNorm(unittest.TestCase):
    def test_full_shape(self):
        out = chart_vlm._norm({"direction": "long", "score": 0.6, "confidence": 0.8,
                               "patterns": ["hammer"], "indicators": {"RSI": "68"},
                               "rationale": "up"})
        self.assertEqual(out["direction"], "long")
        self.assertEqual(out["p_up"], 0.8)          # 0.5 + 0.6/2
        self.assertEqual(out["source"], "vlm")
        self.assertEqual(out["patterns"], ["hammer"])

    def test_score_clamped(self):
        self.assertEqual(chart_vlm._norm({"score": 5})["score"], 1.0)
        self.assertEqual(chart_vlm._norm({"score": -9})["score"], -1.0)

    def test_direction_derived_from_score(self):
        self.assertEqual(chart_vlm._norm({"score": 0.9})["direction"], "long")
        self.assertEqual(chart_vlm._norm({"score": -0.9})["direction"], "short")
        self.assertEqual(chart_vlm._norm({"score": 0.0})["direction"], "flat")

    def test_score_derived_from_direction(self):
        self.assertEqual(chart_vlm._norm({"direction": "short"})["score"], -0.5)

    def test_bad_types_never_raise(self):
        out = chart_vlm._norm({"score": "x", "confidence": None, "patterns": "hammer",
                               "indicators": "nope"})
        self.assertIsInstance(out["patterns"], list)
        self.assertIsInstance(out["indicators"], dict)


class TestReadChart(unittest.TestCase):
    def test_degrades_when_no_vision(self):
        with mock.patch("core.llm.vision_available", return_value=False):
            self.assertIsNone(chart_vlm.read_chart(b"\x89PNG", "BTC/USDT", "1h"))

    def test_reads_and_tags(self):
        with mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat",
                        return_value='{"direction":"long","score":0.5,"confidence":0.7}'):
            out = chart_vlm.read_chart(b"\x89PNG", "ETH/USDT", "4h")
        self.assertEqual(out["symbol"], "ETH/USDT")
        self.assertEqual(out["tf"], "4h")
        self.assertEqual(out["direction"], "long")
        self.assertEqual(out["p_up"], 0.75)

    def test_vision_error_degrades(self):
        with mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat", side_effect=RuntimeError("all throttled")):
            self.assertIsNone(chart_vlm.read_chart(b"\x89PNG", "BTC/USDT", "1h"))

    def test_unparseable_reply_degrades(self):
        with mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat", return_value="I cannot read this chart"):
            self.assertIsNone(chart_vlm.read_chart(b"\x89PNG", "BTC/USDT", "1h"))


class TestNode(unittest.TestCase):
    def test_node_registers(self):
        node = chart_vlm.register_chart_vlm_node()
        self.assertEqual(node.name, "chart_vlm")
        self.assertEqual(len(node.predict_proba([1, 2, 3])), 3)


if __name__ == "__main__":
    unittest.main()
