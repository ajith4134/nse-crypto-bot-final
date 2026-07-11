"""Tests for trading/broker_sense/chart_yolo.py — Lane C YOLOv8 pattern detection.

Covers: Buy/Sell detection aggregation → bounded score, direction thresholds, honest degrade
when the model is unavailable, and the per-symbol cache (write + staleness). No real model:
chart_yolo._model / ultralytics are stubbed; state is redirected to a temp dir.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from trading import state
from trading.broker_sense import chart_yolo


class _Boxes:
    def __init__(self, cls, conf):
        self.cls = _Arr(cls)
        self.conf = _Arr(conf)


class _Arr(list):
    def tolist(self):
        return list(self)


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes


def _fake_model(cls, conf):
    m = mock.MagicMock()
    m.names = {0: "Buy", 1: "Sell"}
    m.predict.return_value = [_Result(_Boxes(cls, conf))]
    return m


class TestDetect(unittest.TestCase):
    def test_bullish_aggregate(self):
        with mock.patch.object(chart_yolo, "_model",
                               return_value=_fake_model([0, 0], [0.8, 0.6])):   # two Buy
            r = chart_yolo.detect("x.png", symbol="BTC/USDT", tf="1h")
        self.assertEqual(r["direction"], "long")
        self.assertEqual(r["n_buy"], 2)
        self.assertEqual(r["n_sell"], 0)
        self.assertGreater(r["score"], 0)
        self.assertEqual(r["source"], "yolo")

    def test_bearish_aggregate(self):
        with mock.patch.object(chart_yolo, "_model",
                               return_value=_fake_model([1, 1, 0], [0.7, 0.6, 0.2])):
            r = chart_yolo.detect("x.png")
        self.assertEqual(r["direction"], "short")
        self.assertLess(r["score"], 0)

    def test_no_detections_flat(self):
        with mock.patch.object(chart_yolo, "_model", return_value=_fake_model([], [])):
            r = chart_yolo.detect("x.png")
        self.assertEqual(r["direction"], "flat")
        self.assertEqual(r["score"], 0.0)

    def test_model_unavailable_degrades(self):
        with mock.patch.object(chart_yolo, "_model", return_value=None):
            self.assertIsNone(chart_yolo.detect("x.png"))

    def test_score_bounded(self):
        with mock.patch.object(chart_yolo, "_model",
                               return_value=_fake_model([0] * 20, [0.99] * 20)):   # saturate
            r = chart_yolo.detect("x.png")
        self.assertLessEqual(r["score"], 1.0)
        self.assertEqual(r["direction"], "long")


class TestCache(unittest.TestCase):
    def setUp(self):
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="yolo_test_"))

    def tearDown(self):
        state.STATE_DIR = self._orig

    def test_detect_and_cache_roundtrip(self):
        with mock.patch.object(chart_yolo, "_model", return_value=_fake_model([0], [0.9])):
            wrote = chart_yolo.detect_and_cache("ETH/USDT", "x.png", tf="15m")
        self.assertIsNotNone(wrote)
        got = chart_yolo.cached("ETH/USDT")
        self.assertEqual(got["direction"], "long")

    def test_cache_staleness(self):
        state.save_json(chart_yolo._CACHE_FILE,
                        {"AAA": {"ts": time.time() - 5000, "read": {"direction": "long"}}})
        self.assertIsNone(chart_yolo.cached("AAA"))
        self.assertIsNotNone(chart_yolo.cached("AAA", max_age=1e9))

    def test_cached_absent(self):
        self.assertIsNone(chart_yolo.cached("NOPE"))


class TestNode(unittest.TestCase):
    def test_node_registers(self):
        node = chart_yolo.register_chart_yolo_node()
        self.assertEqual(node.name, "chart_yolo")
        self.assertEqual(len(node.predict_proba([1, 2])), 2)


if __name__ == "__main__":
    unittest.main()
