"""Tests for trading/direction/app_signals.py — every captured filter → a direction source."""
import unittest
from unittest import mock

from trading.direction import app_signals as asig


class _UM:
    """Fake ui_market with rich captures for one symbol."""
    def funding(self, s): return {"funding_rate": 0.0005}          # +funding → short lean
    def taker(self, s): return {"buy": 70, "sell": 30}             # buy-heavy → long
    def book(self, s): return {"bids": [[1, 60]], "asks": [[1, 40]]}  # bid-heavy → long
    def long_short(self, s): return {"ratio": 1.6}                 # crowded long → contrarian
    def open_interest(self, s): return {"change_pct": 8.0}         # OI rising
    def recent_liquidations(self, s, n=50): return [{"side": "short"}, {"side": "short"}]
    def option_chain(self, s): return {"pcr": 1.4}


class AppSignalsTest(unittest.TestCase):
    def test_all_filters_become_direction_sources(self):
        with mock.patch.dict("sys.modules", {"trading.broker_sense.ui_market": _UM()}):
            # patch the import target used inside signals()
            import trading.broker_sense.ui_market  # noqa
            with mock.patch("trading.broker_sense.ui_market.funding", _UM().funding), \
                 mock.patch("trading.broker_sense.ui_market.taker", _UM().taker), \
                 mock.patch("trading.broker_sense.ui_market.book", _UM().book), \
                 mock.patch("trading.broker_sense.ui_market.long_short", _UM().long_short), \
                 mock.patch("trading.broker_sense.ui_market.open_interest", _UM().open_interest), \
                 mock.patch("trading.broker_sense.ui_market.recent_liquidations", _UM().recent_liquidations), \
                 mock.patch("trading.broker_sense.ui_market.option_chain", _UM().option_chain):
                sigs = asig.signals("BTCUSDT", market="crypto", row={"pct_change": 3.0})
        names = {s for s, _ in sigs}
        # every captured filter is now a direction source — not just movement
        self.assertEqual(names, {"filter:momentum", "filter:funding", "filter:taker",
                                 "filter:book_imbalance", "filter:longshort",
                                 "filter:oi_trend", "filter:liquidations", "filter:pcr"})
        for _, p in sigs:
            self.assertTrue(0.02 <= p <= 0.98)                     # valid p_up

    def test_taker_buy_heavy_leans_long(self):
        with mock.patch("trading.broker_sense.ui_market.taker", lambda s: {"buy": 90, "sell": 10}), \
             mock.patch("trading.broker_sense.ui_market.funding", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.book", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.long_short", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.open_interest", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.recent_liquidations", lambda s, n=50: []), \
             mock.patch("trading.broker_sense.ui_market.option_chain", lambda s: None):
            sigs = dict(asig.signals("X", market="crypto"))
        self.assertGreater(sigs["filter:taker"], 0.5)              # buy-heavy → long


    def test_collect_reports_coverage_and_requests_missing(self):
        import tempfile
        from trading import state
        with mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(tempfile.mkdtemp())), \
             mock.patch("trading.broker_sense.ui_market.funding", lambda s: {"funding_rate": 0.0001}), \
             mock.patch("trading.broker_sense.ui_market.taker", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.book", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.long_short", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.open_interest", lambda s: None), \
             mock.patch("trading.broker_sense.ui_market.recent_liquidations", lambda s, n=50: []), \
             mock.patch("trading.broker_sense.ui_market.option_chain", lambda s: None):
            col = asig.collect("BTCUSDT", market="crypto", row={"pct_change": 2.0})
            cov = col["coverage"]
            self.assertEqual(cov["n_total"], len(asig.ALL_KINDS))
            self.assertIn("momentum", cov["present"])
            self.assertIn("funding", cov["present"])
            self.assertIn("book_imbalance", cov["missing"])       # not captured → requested
            self.assertLess(cov["n_present"], cov["n_total"])
            # missing kinds → a streaming want recorded for the funnel to pin
            w = state.load_json("direction_collect_wanted.json", {}) or {}
            self.assertIn("BTCUSDT", w.get("crypto", {}))


if __name__ == "__main__":
    unittest.main()
