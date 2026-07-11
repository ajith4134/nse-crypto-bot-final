"""Tests for trading/broker_sense/chart_render.py + chart_vision vision-escalation wiring.

chart_render: plain (CNN) + annotated (indicator) renders produce real PNGs on enough data
and degrade to None on too-few/empty. chart_vision._vision_escalate: renders the annotated
chart, hands it to the VLM, and deletes it — falling back honestly when data/VLM unavailable.
No network: data_failsafe / chart_vlm are stubbed.
"""
from __future__ import annotations

import math
import os
import unittest
from unittest import mock

from trading.broker_sense import chart_render, chart_vision


def _rows(n=140):
    rows, p = [], 100.0
    for i in range(n):
        p += math.sin(i / 9) * 0.8 + (0.15 if i > n // 2 else -0.05)
        o = p
        c = p + math.sin(i / 3) * 0.5
        rows.append([1_700_000_000_000 + i * 300_000, o, max(o, c) + 0.4,
                     min(o, c) - 0.4, c, 1000 + i * 3])
    return rows


class TestPlain(unittest.TestCase):
    def test_renders_png(self):
        path = chart_render.plain(_rows(30), "BTC/USDT", "5m")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.assertTrue(os.path.exists(path) and os.path.getsize(path) > 0)

    def test_empty_degrades(self):
        self.assertIsNone(chart_render.plain([], "x", "x"))


class TestAnnotated(unittest.TestCase):
    def test_renders_indicator_png(self):
        path = chart_render.annotated(_rows(140), "BTC/USDT", "1h")
        self.addCleanup(lambda: path and os.path.exists(path) and os.remove(path))
        self.assertIsNotNone(path)
        self.assertTrue(os.path.getsize(path) > 10_000)     # rich multi-panel chart

    def test_few_bars_degrades(self):
        self.assertIsNone(chart_render.annotated(_rows(10), "x", "x"))
        self.assertIsNone(chart_render.annotated([], "x", "x"))


class TestVisionEscalate(unittest.TestCase):
    def _cv(self):
        return chart_vision.ChartVision(sessions=None)

    def test_reads_and_deletes(self):
        cv = self._cv()
        fake_png = chart_render.plain(_rows(30), "tmp", "tmp")   # any real file to delete
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=_rows(140)), \
             mock.patch("trading.broker_sense.chart_render.annotated", return_value=fake_png), \
             mock.patch("trading.broker_sense.chart_vlm.read_chart",
                        return_value={"p_up": 0.7, "direction": "long", "source": "vlm"}):
            res = cv._vision_escalate("BTC/USDT", "crypto", "1h")
        self.assertEqual(res["source"], "vlm")
        self.assertFalse(os.path.exists(fake_png))              # deleted (owner step 7)

    def test_no_render_degrades(self):
        cv = self._cv()
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=[]), \
             mock.patch("trading.broker_sense.chart_render.annotated", return_value=None):
            self.assertIsNone(cv._vision_escalate("BTC/USDT", "crypto", "1h"))

    def test_vlm_none_degrades(self):
        cv = self._cv()
        fake_png = chart_render.plain(_rows(30), "tmp2", "tmp2")
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=_rows(140)), \
             mock.patch("trading.broker_sense.chart_render.annotated", return_value=fake_png), \
             mock.patch("trading.broker_sense.chart_vlm.read_chart", return_value=None):
            self.assertIsNone(cv._vision_escalate("BTC/USDT", "crypto", "1h"))
        self.assertFalse(os.path.exists(fake_png))             # still deleted


if __name__ == "__main__":
    unittest.main()
