"""Tests for fast candle direction (trading/broker_sense/fast_candles) + crypto order type.

fast_candles: EMA/RSI/momentum direction from OHLCV, honest 'unavailable' on missing data,
same output shape as ChartVision.read, deadline-bounded. order type: MARKET default + override.
"""
from __future__ import annotations

import unittest
from unittest import mock

from trading.broker_sense import fast_candles as fc


def _uptrend(n=50, start=100.0, step=1.0):
    return [[i, start + i * step, start + i * step + 0.5, start + i * step - 0.5,
             start + i * step, 1000] for i in range(n)]


def _downtrend(n=50, start=200.0, step=1.0):
    return [[i, start - i * step, start - i * step + 0.5, start - i * step - 0.5,
             start - i * step, 1000] for i in range(n)]


class TestDirection(unittest.TestCase):
    def test_uptrend_is_long(self):
        d = fc.direction_from_ohlcv(_uptrend())
        self.assertEqual(d["direction"], "long")
        self.assertGreater(d["p_up"], 0.55)
        self.assertEqual(d["source"], "fast:ohlcv")

    def test_downtrend_is_short(self):
        d = fc.direction_from_ohlcv(_downtrend())
        self.assertEqual(d["direction"], "short")
        self.assertLess(d["p_up"], 0.45)

    def test_insufficient_data_unavailable(self):
        d = fc.direction_from_ohlcv([[0, 1, 1, 1, 1, 1]])
        self.assertEqual(d["source"], "unavailable")
        self.assertEqual(d["p_up"], 0.5)

    def test_malformed_rows_no_crash(self):
        d = fc.direction_from_ohlcv([None, [1, 2], "bad"])
        self.assertEqual(d["source"], "unavailable")


class TestRead(unittest.TestCase):
    def test_read_shape_and_uses_ohlcv(self):
        # _ohlcv_fast tries a LIVE ccxt fetch before the data_failsafe fallback — mock
        # BOTH so this unit test never depends on the real market's current direction
        # (it flaked 'short' whenever real BTC trended down, 2026-07-10 fix)
        with mock.patch("trading.broker_sense.app_school._ccxt_exchange",
                        side_effect=RuntimeError("no network in unit tests")), \
             mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=_uptrend()):
            out = fc.read([{"symbol": "BTC/USDT:USDT"}], "crypto", timeframes=("5m", "1h"))
        self.assertIn("BTC/USDT:USDT", out)
        self.assertEqual(set(out["BTC/USDT:USDT"]), {"5m", "1h"})
        self.assertEqual(out["BTC/USDT:USDT"]["5m"]["direction"], "long")

    def test_read_missing_ohlcv_is_unavailable(self):
        # isolate the added multi-venue-pool data path (2026-07-12) so this exercises the
        # data_failsafe fallback exactly as before; also bypass the per-bar memo.
        with mock.patch("trading.crypto.exchange_pool.pool_enabled", return_value=False), \
                mock.patch("trading.broker_sense.fast_candles._ohlcv_fast", return_value=None):
            out = fc.read([{"symbol": "X/USDT"}], "crypto", timeframes=("5m",))
        self.assertEqual(out["X/USDT"]["5m"]["source"], "unavailable")

    def test_deadline_stops_fetching(self):
        import time
        called = []

        def slow(*a, **k):
            called.append(1)
            return _uptrend()
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", side_effect=slow):
            out = fc.read([{"symbol": "A"}], "crypto", timeframes=("5m", "1h"),
                          deadline=time.monotonic() - 1)   # already past → no fetches
        self.assertEqual(called, [])
        self.assertEqual(out["A"]["5m"]["source"], "unavailable")


class TestOrderType(unittest.TestCase):
    def test_default_market_and_override(self):
        from trading.crypto.engine_client import _order_type
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("CRYPTO_ORDER_TYPE", None)
            self.assertEqual(_order_type(), "market")       # owner's default preference
        with mock.patch.dict("os.environ", {"CRYPTO_ORDER_TYPE": "limit"}):
            self.assertEqual(_order_type(), "limit")
        with mock.patch.dict("os.environ", {"CRYPTO_ORDER_TYPE": "market"}):
            self.assertEqual(_order_type(), "market")


if __name__ == "__main__":
    unittest.main()
