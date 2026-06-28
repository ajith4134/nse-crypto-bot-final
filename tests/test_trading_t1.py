"""Trading Phase T1 (NSE Foundation) acceptance tests.

Exercises all server-INDEPENDENT logic so CI passes without a running OpenAlgo
server: config resolution, squareoff scheduling math, master-toggle persistence
and the zero-activity contract, watchlist persistence, and instrument parsing.

Live order/feed paths are verified separately by run_trading.py against a real
OpenAlgo server (they require a broker connection and cannot run in CI).
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import trading.state as state
from trading import squareoff
from trading.config import TradingConfig
from trading.instruments import Instrument
from trading.market_toggle import MarketOff, MasterToggle
from trading.watchlist import Watchlist

IST = timezone(timedelta(hours=5, minutes=30))


class _IsolatedState(unittest.TestCase):
    """Redirect trading state to a fresh temp dir for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._orig
        self._tmp.cleanup()


class TestConfig(unittest.TestCase):
    def test_defaults_paper_and_safe(self):
        cfg = TradingConfig(mode="paper", openalgo_host="http://127.0.0.1:5000",
                            openalgo_ws_url="ws://127.0.0.1:8765", _api_key=None)
        self.assertFalse(cfg.is_live)
        self.assertFalse(cfg.is_configured)
        self.assertEqual(cfg.redacted_key, "<absent>")
        with self.assertRaises(RuntimeError):
            cfg.require_key()

    def test_key_is_redacted_never_full(self):
        cfg = TradingConfig(mode="live", openalgo_host="h", openalgo_ws_url="w",
                            _api_key="ABCD1234SECRET")
        self.assertTrue(cfg.is_live)
        self.assertIn("…", cfg.redacted_key)
        self.assertNotIn("SECRET", cfg.redacted_key)
        # The full key must never appear in the dashboard status payload.
        self.assertNotIn("ABCD1234SECRET", str(cfg.as_status()))

    def test_squareoff_for_known_exchanges(self):
        cfg = TradingConfig(mode="paper", openalgo_host="h", openalgo_ws_url="w")
        self.assertEqual(cfg.squareoff_for("NSE"), "15:15")
        self.assertEqual(cfg.squareoff_for("mcx"), "23:30")
        self.assertEqual(cfg.squareoff_for("CDS"), "16:45")
        self.assertIsNone(cfg.squareoff_for("XXX"))


class TestSquareoff(unittest.TestCase):
    def test_nse_due_after_action_time(self):
        # 15:14 IST = action time for NSE (15:15 deadline minus 1 min lead).
        before = datetime(2026, 6, 28, 15, 0, tzinfo=IST)
        after = datetime(2026, 6, 28, 15, 20, tzinfo=IST)
        self.assertNotIn("NSE", squareoff.due_exchanges(before))
        self.assertIn("NSE", squareoff.due_exchanges(after))

    def test_mcx_late_evening(self):
        # MCX squares off 23:30 — not due at 16:00, due at 23:40.
        self.assertFalse(squareoff.is_squareoff_due(
            "MCX", datetime(2026, 6, 28, 16, 0, tzinfo=IST)))
        self.assertTrue(squareoff.is_squareoff_due(
            "MCX", datetime(2026, 6, 28, 23, 40, tzinfo=IST)))

    def test_action_time_leads_deadline(self):
        rules = squareoff.build_rules()
        self.assertEqual(rules["NSE"].deadline.strftime("%H:%M"), "15:15")
        self.assertEqual(rules["NSE"].action_time.strftime("%H:%M"), "15:14")


class TestMasterToggle(_IsolatedState):
    def test_default_off_and_guard(self):
        t = MasterToggle("NSE")
        self.assertFalse(t.is_on)
        with self.assertRaises(MarketOff):
            t.assert_on()

    def test_start_stop_callbacks_fire_once(self):
        events = []
        t = MasterToggle("NSE",
                         on_start=lambda: events.append("start"),
                         on_stop=lambda: events.append("stop"))
        self.assertTrue(t.turn_on())
        self.assertFalse(t.turn_on())   # idempotent — no second start
        t.assert_on()                   # no raise when ON
        self.assertTrue(t.turn_off())
        self.assertFalse(t.turn_off())  # idempotent
        self.assertEqual(events, ["start", "stop"])

    def test_state_persists_across_instances(self):
        MasterToggle("NSE").turn_on()
        self.assertTrue(MasterToggle("NSE").is_on)  # fresh instance reads persisted ON


class _FakeFeed:
    """Records subscribe/unsubscribe so we can assert feed wiring without a server."""

    def __init__(self):
        self.subs: set[str] = set()

    def subscribe(self, symbol, exchange="NSE"):
        self.subs.add(f"{exchange.upper()}:{symbol.upper()}")

    def unsubscribe(self, symbol, exchange="NSE"):
        self.subs.discard(f"{exchange.upper()}:{symbol.upper()}")


class TestWatchlist(_IsolatedState):
    def test_add_remove_dedup_and_feed_wiring(self):
        feed = _FakeFeed()
        wl = Watchlist(feed=feed)
        self.assertTrue(wl.add("RELIANCE"))
        self.assertFalse(wl.add("reliance"))         # dedup, case-insensitive
        self.assertEqual(len(wl), 1)
        self.assertIn("NSE:RELIANCE", feed.subs)      # feed subscribed
        self.assertTrue(wl.remove("RELIANCE"))
        self.assertNotIn("NSE:RELIANCE", feed.subs)   # feed unsubscribed
        self.assertFalse(wl.remove("RELIANCE"))       # absent

    def test_persistence_resubscribes_on_reload(self):
        Watchlist(feed=_FakeFeed()).add("INFY")
        feed2 = _FakeFeed()
        wl2 = Watchlist(feed=feed2)                    # fresh load from disk
        self.assertEqual(len(wl2), 1)
        self.assertIn("NSE:INFY", feed2.subs)          # re-subscribed on reload


class TestInstrumentParsing(unittest.TestCase):
    def test_tolerant_key_variants(self):
        inst = Instrument.from_openalgo({
            "tradingsymbol": "NIFTY28JUN24C24000", "exch": "NFO",
            "instrument_type": "CE", "strike_price": "24000", "lot": "50",
        })
        self.assertEqual(inst.symbol, "NIFTY28JUN24C24000")
        self.assertEqual(inst.exchange, "NFO")
        self.assertEqual(inst.instrument_type, "CE")
        self.assertEqual(inst.strike, 24000.0)
        self.assertEqual(inst.lot_size, 50)


if __name__ == "__main__":
    unittest.main()
