"""Tests for trading/execution/exec_choice.py (E7 — measured limit/market execution choice)."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        # Pin the A/B off: EXEC_AB lives in .env (loaded at import), and when it is on the
        # randomized arm REPLACES the policy — so these policy assertions would depend on a
        # coin flip. Tests that exercise the randomizer set it themselves.
        self._ab = mock.patch.dict(os.environ, {"EXEC_AB": "0"})
        self._ab.start()

    def tearDown(self):
        self._ab.stop()
        self._p.stop()
        self._tmp.cleanup()

    def _mirror(self, bid, ask, closes=None):
        m = mock.Mock()
        m.book.return_value = {"bids": [[bid, 5]], "asks": [[ask, 5]], "ts": time.time()}
        # exec_choice reads the touch, not the depth ladder: touch() falls back to the
        # all-market bookTicker BBO when a symbol is outside the depth subscription, which
        # is what stopped 53% of entries returning "no_book". A bare Mock would return a
        # truthy Mock here and float() it into error_fallback, so stub it explicitly.
        m.touch.return_value = {"bid": bid, "ask": ask, "src": "depth20"}
        rows = [[0, c, c, c, c] for c in (closes or [100, 100, 100, 100])]
        m.candles.return_value = rows
        return m

    def _mirror_no_book(self):
        """Mirror with neither depth nor BBO — the only case that may still go market blind."""
        m = mock.Mock()
        m.book.return_value = None
        m.touch.return_value = None
        m.candles.return_value = []
        return m


class TestChoose(_Base):
    def test_wide_spread_flat_drift_joins_touch(self):
        from trading.execution import exec_choice as xc
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(100.0, 100.2)):
            ch = xc.choose("AKE/USDT:USDT", "long")
        self.assertEqual(ch["order_type"], "limit")
        self.assertEqual(ch["price"], 100.0)                    # long joins the bid
        self.assertEqual(ch["reason"], "wide_spread")

    def test_tight_spread_goes_market(self):
        from trading.execution import exec_choice as xc
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(100.0, 100.001)):
            ch = xc.choose("AKEUSDT", "long")
        self.assertEqual(ch["order_type"], "market")
        self.assertEqual(ch["reason"], "tight_spread")

    def test_price_running_away_goes_market(self):
        from trading.execution import exec_choice as xc
        rising = [100, 100.5, 101, 101.5]                       # strong up-drift, long entry
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(101.0, 101.3, closes=rising)):
            ch = xc.choose("AKEUSDT", "long")
        self.assertEqual(ch["order_type"], "market")
        self.assertEqual(ch["reason"], "running_away")

    def test_short_joins_ask(self):
        from trading.execution import exec_choice as xc
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(100.0, 100.3)):
            ch = xc.choose("AKEUSDT", "short")
        self.assertEqual(ch["order_type"], "limit")
        self.assertEqual(ch["price"], 100.3)

    def test_no_book_falls_back_to_market(self):
        from trading.execution import exec_choice as xc
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror_no_book()):
            ch = xc.choose("AKEUSDT", "long")
        self.assertEqual(ch["order_type"], "market")
        self.assertEqual(ch["reason"], "no_book")

    def test_bbo_fallback_when_depth_is_cold(self):
        """A symbol outside the 20-level depth subscription must STILL get a real choice.

        This is the regression that mattered: book() alone was None for ~53% of entries, so
        they silently went to market with reason "no_book" and could never be a maker order.
        touch() answers from the all-market bookTicker BBO instead.
        """
        from trading.execution import exec_choice as xc
        m = mock.Mock()
        m.book.return_value = None                       # not in the depth subscription
        m.touch.return_value = {"bid": 100.0, "ask": 100.2, "src": "bookTicker"}
        m.candles.return_value = [[0, c, c, c, c] for c in (100, 100, 100, 100)]
        with mock.patch("trading.broker_sense.binance_stream.get_mirror", return_value=m):
            ch = xc.choose("FOLKSUSDT", "long")
        self.assertEqual(ch["order_type"], "limit")      # 20 bps spread is worth joining
        self.assertEqual(ch["price"], 100.0)             # join the bid
        self.assertEqual(ch["book_src"], "bookTicker")
        self.assertNotEqual(ch["reason"], "no_book")

    def test_disabled(self):
        from trading.execution import exec_choice as xc
        os.environ["EXEC_CHOICE"] = "0"
        try:
            self.assertEqual(xc.choose("AKEUSDT", "long")["reason"], "disabled")
        finally:
            os.environ.pop("EXEC_CHOICE", None)


class TestGradeFills(_Base):
    def test_grades_fill_against_logged_mid_once(self):
        from trading import state
        from trading.execution import exec_choice as xc
        now = time.time()
        xc.log_choice("AKEUSDT", "long",
                      {"order_type": "limit", "price": 100.0, "mid": 100.1,
                       "spread_bps": 20, "drift_bps": 0, "reason": "wide_spread"})
        trades = [{"trade_id": 7, "pair": "AKE/USDT:USDT", "open_rate": 100.0,
                   "open_timestamp": (now + 5) * 1000, "is_short": False}]
        self.assertEqual(xc.grade_fills(trades), 1)
        self.assertEqual(xc.grade_fills(trades), 0)             # idempotent by trade id
        st = state.load_json("exec_choice_stats.json", {})
        b = st["by_type"]["limit"]
        self.assertEqual(b["n"], 1)
        self.assertLess(b["slip_bps_sum"], 0)                   # filled BETTER than mid

    def test_no_nearby_choice_row_skips(self):
        from trading.execution import exec_choice as xc
        xc.log_choice("AKEUSDT", "long",
                      {"order_type": "market", "price": None, "mid": 100.0,
                       "spread_bps": 1, "drift_bps": 0, "reason": "tight_spread"})
        trades = [{"trade_id": 8, "pair": "AKE/USDT:USDT", "open_rate": 100.0,
                   "open_timestamp": (time.time() + 900) * 1000, "is_short": False}]
        self.assertEqual(xc.grade_fills(trades), 0)


if __name__ == "__main__":
    unittest.main()
