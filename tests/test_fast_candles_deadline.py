"""Regression: fast_candles.read must enforce its deadline PER JOB (2026-07-12).

The LOOK-stage candle fetch used to run all picks×timeframes ccxt fetches to completion even after
the budget deadline passed (only checked once at entry), blowing the funnel cycle to 400s+ and
starving the VERIFY/fusion stage — so no indicator_fusion claims + no entries accrued, and the
stacking meta-learner never received its lens features. read() now skips the fetch once the
deadline is past.
"""
import time
import unittest

from trading.broker_sense import fast_candles as fc


class TestFastCandlesDeadline(unittest.TestCase):
    def test_no_fetch_past_deadline(self):
        called = {"n": 0}
        orig = fc._ohlcv_fast
        fc._ohlcv_fast = lambda s, m, t: called.__setitem__("n", called["n"] + 1) or None
        try:
            picks = [{"symbol": f"C{i}/USDT"} for i in range(40)]
            t0 = time.monotonic()
            out = fc.read(picks, "crypto", timeframes=("5m", "15m", "1h"),
                          deadline=time.monotonic() - 1)   # already expired
            elapsed = time.monotonic() - t0
        finally:
            fc._ohlcv_fast = orig
        self.assertEqual(called["n"], 0, "must not fetch after the deadline")
        self.assertLess(elapsed, 1.0, "past-deadline read must return promptly")
        for p in picks:
            for tf in ("5m", "15m", "1h"):
                self.assertEqual(out[p["symbol"]][tf]["source"], "unavailable")

    def test_hard_bound_under_hung_fetches(self):
        # a rate-limited venue makes fetches hang with no timeout; read() must still return near
        # its deadline (not wait for the slowest straggler) — the real cause of 400-540s cycles.
        orig = fc._ohlcv_fast

        def slow(s, m, t):
            time.sleep(8)
            return None

        fc._ohlcv_fast = slow
        try:
            picks = [{"symbol": f"C{i}/USDT"} for i in range(30)]
            t0 = time.monotonic()
            out = fc.read(picks, "crypto", timeframes=("5m", "15m", "1h"),
                          deadline=time.monotonic() + 0.6)
            elapsed = time.monotonic() - t0
        finally:
            fc._ohlcv_fast = orig
        self.assertLess(elapsed, 3.0, "must return near the deadline, not block on 8s hangs")
        for p in picks:                                  # unfinished jobs keep the honest default
            self.assertEqual(out[p["symbol"]]["5m"]["source"], "unavailable")


if __name__ == "__main__":
    unittest.main()
