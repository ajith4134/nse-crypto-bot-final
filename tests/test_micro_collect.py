"""Tests for trading/broker_sense/micro_collect.py — active microstructure collection."""
import unittest
from unittest import mock

from trading.broker_sense import micro_collect as mc


class _Page:
    def __init__(self): self.urls = []
    def evaluate(self, js, url):
        self.urls.append(url)
        return {"symbol": "BTCUSDT", "openInterest": "123.0"}   # any non-None body


class _Sessions:
    def __init__(self): self.page_obj = _Page()
    def page(self, broker, url, timeout_ms=0): return self.page_obj


class MicroCollectTest(unittest.TestCase):
    def setUp(self):
        mc._last.clear()

    def test_flat_symbol(self):
        self.assertEqual(mc._flat("BTC/USDT:USDT"), "BTCUSDT")
        self.assertEqual(mc._flat("ethusdt"), "ETHUSDT")

    def test_collect_fetches_missing_kinds_and_ingests(self):
        sess = _Sessions()
        with mock.patch.dict("os.environ", {"MICRO_COLLECT": "1"}), \
             mock.patch.object(mc, "_missing_kinds", lambda s: ["open_interest", "orderbook"]), \
             mock.patch("trading.broker_sense.ui_market.feed_capture", return_value=1) as fc:
            rep = mc.collect(["BTC/USDT:USDT"], sess, broker="binance")
        self.assertEqual(rep["fetched"], 2)               # 2 missing kinds fetched
        self.assertEqual(rep["stored"], 2)                # both ingested via feed_capture
        self.assertTrue(any("BTCUSDT" in u for u in sess.page_obj.urls))   # flat symbol in URL
        self.assertTrue(any("openInterest" in u for u in sess.page_obj.urls))
        self.assertEqual(fc.call_count, 2)

    def test_throttled_second_call_skips(self):
        sess = _Sessions()
        with mock.patch.dict("os.environ", {"MICRO_COLLECT": "1"}), \
             mock.patch.object(mc, "_missing_kinds", lambda s: ["open_interest"]), \
             mock.patch("trading.broker_sense.ui_market.feed_capture", return_value=1):
            mc.collect(["BTCUSDT"], sess, broker="binance")
            rep2 = mc.collect(["BTCUSDT"], sess, broker="binance")   # within TTL
        self.assertEqual(rep2["fetched"], 0)              # throttled — no re-fetch

    def test_kill_switch(self):
        with mock.patch.dict("os.environ", {"MICRO_COLLECT": "0"}):
            self.assertFalse(mc.enabled())
            rep = mc.collect(["BTCUSDT"], _Sessions(), broker="binance")
        self.assertEqual(rep["fetched"], 0)


if __name__ == "__main__":
    unittest.main()
