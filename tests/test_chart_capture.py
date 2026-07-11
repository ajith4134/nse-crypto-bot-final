"""Tests for trading/broker_sense/chart_capture.py — GAP-E intelligent Binance chart capture.

Covers: open_chart, enable_all_indicators (counts the toggles it locates), set_timeframe, the full
capture flow (returns per-TF PNG bytes, honors the time budget), and honest degrade when the browser
won't cooperate. No live browser: HumanUI + page are fakes; locate() is controlled per-test.
"""
from __future__ import annotations

import unittest
from unittest import mock

from trading.broker_sense.chart_capture import IndicatorChartCapture, INDICATORS


class _Page:
    def __init__(self):
        self.url = "https://binance.com/en/trade/BTC_USDT"
        self.clicks = []
        self.goto_called = 0
        self.mouse = mock.MagicMock()
        self.keyboard = mock.MagicMock()

    def goto(self, url, **kw):
        self.goto_called += 1
        self.url = url

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self, **kw):
        return b"\x89PNG-fake"


class _UI:
    """Fake HumanUI: menu locatable iff `menu`; an indicator iff its QUOTED name is asked; a TF
    iff its label is asked. Quoted matching disambiguates MA from EMA (the real bug this guards)."""
    def __init__(self, *, menu=False, indicators=(), tfs=()):
        self.page = _Page()
        self.menu = menu
        self.indicators = {i.lower() for i in indicators}
        self.tfs = {t.lower() for t in tfs}

    def locate(self, target):
        t = target.lower()
        if "fx icon" in t or t == "indicators":
            return (10, 10) if self.menu else None
        if "timeframe button" in t:
            return (20, 20) if any(tf in t for tf in self.tfs) else None
        for ind in self.indicators:
            if f'"{ind}"' in t:                            # quoted → "ma" != "ema"
                return (30, 30)
        return None


class TestCapture(unittest.TestCase):
    def test_open_chart(self):
        ui = _UI()
        cap = IndicatorChartCapture(ui)
        self.assertTrue(cap.open_chart("BTC/USDT"))
        self.assertIn("BTC_USDT", ui.page.url)

    def test_enable_indicators_counts_located(self):
        ui = _UI(menu=True, indicators=("MA", "BOLL", "MACD"))
        cap = IndicatorChartCapture(ui)
        self.assertEqual(cap.enable_all_indicators(), 3)   # MA, BOLL, MACD; EMA not toggled
        self.assertEqual(cap.stats["indicators_on"], 3)

    def test_no_indicators_menu_degrades(self):
        cap = IndicatorChartCapture(_UI(menu=False))        # can't even find the menu button
        self.assertEqual(cap.enable_all_indicators(), 0)

    def test_capture_returns_per_tf_shots(self):
        ui = _UI(menu=True, indicators=("MA",), tfs=("15m", "1h"))
        cap = IndicatorChartCapture(ui)
        with mock.patch("trading.broker_sense.chart_capture.IndicatorChartCapture._shot",
                        return_value=b"PNG"):
            rep = cap.capture("BTC/USDT", timeframes=("15m", "1h"))
        self.assertEqual(set(rep["shots"].keys()), {"15m", "1h"})
        self.assertEqual(rep["stats"]["tf_shots"], 2)

    def test_capture_respects_budget(self):
        ui = _UI(tfs=("15m", "1h", "4h", "1d"))
        cap = IndicatorChartCapture(ui)
        rep = cap.capture("ETH/USDT", timeframes=("15m", "1h", "4h", "1d"), budget_s=0.0)
        self.assertEqual(rep["shots"], {})

    def test_open_chart_failure_degrades(self):
        ui = _UI()
        ui.page.goto = mock.MagicMock(side_effect=RuntimeError("nav blocked"))
        cap = IndicatorChartCapture(ui)
        rep = cap.capture("BTC/USDT")
        self.assertEqual(rep["shots"], {})
        self.assertIn("error", rep)


if __name__ == "__main__":
    unittest.main()
