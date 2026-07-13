"""Tests for binance_stream price history + truth-ledger 100% price coverage (2026-07-13)."""
import unittest
from collections import deque
from unittest import mock

from trading.broker_sense.binance_stream import BinanceUniverseMirror
from trading.direction import truth_ledger as tl


class MirrorPriceTest(unittest.TestCase):
    def test_price_at_finds_closest_within_tolerance(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._hist["MAGMAUSDT"] = deque([(t - 300, 0.70), (t - 180, 0.72), (t - 60, 0.75)])
        self.assertEqual(m.price_at("MAGMAUSDT", t - 180), 0.72)   # exact-ish
        self.assertEqual(m.price_at("MAGMAUSDT", t - 70), 0.75)    # nearest
        self.assertIsNone(m.price_at("MAGMAUSDT", t - 9000))       # out of tolerance
        self.assertIsNone(m.price_at("UNSEENUSDT", t))            # no history

    def test_price_at_falls_back_to_latest_mark_when_fresh(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._mark["BTCUSDT"] = {"mark": 62000.0, "ts": t}
        self.assertEqual(m.price_at("BTCUSDT", t + 10), 62000.0)   # no hist, latest is close
        self.assertIsNone(m.price_at("BTCUSDT", t + 9000))         # latest too stale

    def test_resolver_prices_any_perp_via_mirror(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._hist["MAGMAUSDT"] = deque([(t, 0.72)])
        with mock.patch("trading.broker_sense.binance_stream.get_mirror", return_value=m):
            # ccxt-style perp symbol → flattened + priced from the all-market mirror
            self.assertEqual(tl._mirror_price("MAGMA/USDT:USDT", t), 0.72)


if __name__ == "__main__":
    unittest.main()
