"""candle_updater throttle — batched, de-prioritised OHLCV refresh.

A single download-data over all ~300 pairs bursts the exchange API and wedged the dashboard
(Cloudflare 524, 2026-07-03). These tests verify the fix: pairs are split into small batches
run back-to-back with a sleep between, full coverage preserved, no single giant call.
"""
from __future__ import annotations

import unittest
import warnings

warnings.simplefilter("ignore")

import trading.crypto.freqtrade.candle_updater as cu


class TestCandleUpdaterThrottle(unittest.TestCase):
    def test_batches_split_and_cover(self):
        pairs = [f"P{i}" for i in range(300)]
        b = cu._batches(pairs, 25)
        self.assertEqual(len(b), 12)
        self.assertTrue(all(len(x) <= 25 for x in b))
        self.assertEqual(sum(len(x) for x in b), 300)          # full coverage, nothing dropped
        self.assertEqual([p for batch in b for p in batch], pairs)  # order preserved

    def test_run_cycle_batches_downloads(self):
        calls, status, slept = [], [], []
        orig_top, orig_dl, orig_sleep, orig_ws = (
            cu._top_pairs, cu._download, cu.time.sleep, cu._write_status)
        try:
            cu._top_pairs = lambda n: [f"P{i}" for i in range(120)]
            cu._download = lambda batch: (calls.append(len(batch)) or 0)
            cu.time.sleep = lambda s: slept.append(s)
            cu._write_status = lambda uidir, **f: status.append(f.get("state"))
            cu.run_cycle("/tmp", 1)
        finally:
            cu._top_pairs, cu._download, cu.time.sleep, cu._write_status = (
                orig_top, orig_dl, orig_sleep, orig_ws)
        # 120 pairs / 25 = 5 batches, none bigger than the batch size, full coverage
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(c <= cu.BATCH for c in calls))
        self.assertEqual(sum(calls), 120)
        # slept between batches (one fewer than the number of batches)
        self.assertEqual(len(slept), 4)
        self.assertEqual(status[-1], "idle")
        self.assertIn("updating", status)

    def test_small_pairlist_errors_without_download(self):
        calls, status = [], []
        orig_top, orig_dl, orig_ws = cu._top_pairs, cu._download, cu._write_status
        try:
            cu._top_pairs = lambda n: ["ONLY", "TWO"]
            cu._download = lambda batch: (calls.append(1) or 0)
            cu._write_status = lambda uidir, **f: status.append(f.get("state"))
            cu.run_cycle("/tmp", 1)
        finally:
            cu._top_pairs, cu._download, cu._write_status = orig_top, orig_dl, orig_ws
        self.assertEqual(calls, [])                             # never downloads on a bad pairlist
        self.assertEqual(status[-1], "error")

    def test_throttle_knobs_sane(self):
        self.assertGreaterEqual(cu.BATCH, 1)
        self.assertLess(cu.BATCH, cu.N_PAIRS)                   # actually batches, not one call
        self.assertGreaterEqual(cu.NICE, 0)


if __name__ == "__main__":
    unittest.main()
