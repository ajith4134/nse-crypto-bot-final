"""Tests for tv_feed (adopt item 6a) — TradingView-WS SUPPLEMENTARY lane: default-OFF, NSE
motto-gated, hard-timeout-bounded so a stale TradingView protocol can never wedge a cycle."""
import os
import time
import unittest

from trading.broker_sense import tv_feed as tv


class _Base(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("TV_WS_LANE", "TV_WS_NSE", "TV_WS_TIMEOUT")}
        self._fetch = tv._fetch_blocking

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        tv._fetch_blocking = self._fetch


class TestGating(_Base):
    def test_default_off(self):
        os.environ.pop("TV_WS_LANE", None)
        self.assertIsNone(tv.quote("BTC/USDT:USDT", "crypto"))

    def test_enabled_crypto(self):
        os.environ["TV_WS_LANE"] = "1"
        tv._fetch_blocking = lambda s, m: {"last": 63000.0, "pct_change": 1.5}
        q = tv.quote("BTC/USDT:USDT", "crypto")
        self.assertEqual(q["last"], 63000.0)
        self.assertEqual(q["source"], "tv:ws")

    def test_nse_motto_gated(self):
        os.environ["TV_WS_LANE"] = "1"
        os.environ.pop("TV_WS_NSE", None)
        tv._fetch_blocking = lambda s, m: {"last": 2900.0}
        self.assertIsNone(tv.quote("RELIANCE", "nse"))          # NSE stays Upstox-pure
        os.environ["TV_WS_NSE"] = "1"
        self.assertIsNotNone(tv.quote("RELIANCE", "nse"))       # explicit opt-in


class TestSafety(_Base):
    def test_hang_is_bounded_not_wedged(self):
        os.environ["TV_WS_LANE"] = "1"
        os.environ["TV_WS_TIMEOUT"] = "1"
        tv._fetch_blocking = lambda s, m: time.sleep(30)        # simulate a stale hung protocol
        t0 = time.monotonic()
        r = tv.quote("BTC/USDT:USDT", "crypto")
        self.assertIsNone(r)
        self.assertLess(time.monotonic() - t0, 3.0)            # returned ~1s, never wedged

    def test_ticker_mapping(self):
        self.assertEqual(tv._tv_ticker("BTC/USDT:USDT"), "BTCUSDT")
        self.assertEqual(tv._tv_ticker("RELIANCE"), "RELIANCE")


if __name__ == "__main__":
    unittest.main()
