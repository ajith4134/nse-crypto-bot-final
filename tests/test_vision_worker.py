"""Tests for trading/broker_sense/vision_worker.py — async deep chart-vision worker.

Covers: read_symbol renders+reads+caches, same-bar dedup skips the expensive read, cached_read
honors max_age, deep_vision assembles the fuse() vision dict, and everything degrades honestly
when data/VLM are unavailable. No network / no VLM: data_failsafe / chart_render / chart_vlm are
stubbed, and state is redirected to a temp dir.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest import mock

from trading import state
from trading.broker_sense import vision_worker as vw


def _rows(bar_ts=1_700_000_000_000):
    return [[bar_ts + i * 900_000, 100, 101, 99, 100, 1000] for i in range(130)]


class VWTest(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self._tmp = tempfile.mkdtemp()
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp)

    def tearDown(self):
        state.STATE_DIR = self._orig

    def _read_patches(self, read_val, rows=None):
        import contextlib
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch("trading.broker_sense.data_failsafe.ohlcv",
                                       return_value=rows if rows is not None else _rows()))
        stack.enter_context(mock.patch("trading.broker_sense.chart_render.annotated",
                                       return_value="/tmp/x.png"))
        stack.enter_context(mock.patch("trading.broker_sense.volume_profile.features",
                                       return_value={"available": False}))
        stack.enter_context(mock.patch("os.remove", return_value=None))
        stack.enter_context(mock.patch("trading.broker_sense.chart_vlm.read_chart",
                                       return_value=read_val))
        return stack

    def test_read_symbol_caches(self):
        read = {"direction": "long", "p_up": 0.7, "source": "vlm"}
        with self._read_patches(read):
            out = vw.read_symbol("BTC/USDT", "crypto", timeframes=("15m",))
        self.assertEqual(out["cached_writes"], 1)
        self.assertEqual(vw.cached_read("BTC/USDT", "15m")["direction"], "long")

    def test_same_bar_dedup_skips_read(self):
        read = {"direction": "short", "p_up": 0.3}
        rows = _rows(bar_ts=1_700_000_500_000)
        rc = mock.patch("trading.broker_sense.chart_vlm.read_chart", return_value=read)
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=rows), \
             mock.patch("trading.broker_sense.chart_render.annotated", return_value="/tmp/x.png"), \
             mock.patch("trading.broker_sense.volume_profile.features", return_value={"available": False}), \
             mock.patch("os.remove"), rc as m:
            vw.read_symbol("ETH/USDT", "crypto", timeframes=("1h",))
            vw.read_symbol("ETH/USDT", "crypto", timeframes=("1h",))     # same bar → no 2nd read
        self.assertEqual(m.call_count, 1)

    def test_cached_read_staleness(self):
        state.save_json(vw._CACHE_FILE,
                        {"AAA|15m": {"ts": time.time() - 5000, "bar_ts": 1, "read": {"direction": "long"}}})
        self.assertIsNone(vw.cached_read("AAA", "15m"))                  # older than _MAX_AGE
        self.assertIsNotNone(vw.cached_read("AAA", "15m", max_age=1e9))

    def test_deep_vision_shape(self):
        state.save_json(vw._CACHE_FILE, {
            "BTC/USDT|15m": {"ts": time.time(), "bar_ts": 1,
                             "read": {"direction": "long", "p_up": 0.66}},
        })
        dv = vw.deep_vision("BTC/USDT", timeframes=("15m", "1h"))
        self.assertEqual(dv["15m"]["direction"], "long")
        self.assertEqual(dv["15m"]["source"], "vlm_deep")
        self.assertNotIn("1h", dv)                                       # no cache for 1h

    def test_no_data_degrades(self):
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=None):
            out = vw.read_symbol("X/USDT", "crypto", timeframes=("15m",))
        self.assertEqual(out["cached_writes"], 0)
        self.assertIsNone(vw.deep_vision("X/USDT"))


if __name__ == "__main__":
    unittest.main()
