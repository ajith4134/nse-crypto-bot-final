"""Tests for the App Driving School (trading/broker_sense/app_school) — offline, no browser.

Covers: AppMap route record/persist, goal coverage + missing, route_to (learned overrides seed),
curiosity ranking toward still-missing goals + forbidden-control skip, and the explore() driver
learning a route from the app's own captured traffic (fakes for sessions/cortex/recorder).
STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state
from trading.broker_sense import app_school as sch


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        sch._SCHOOL = None                     # reset singleton so it reloads from this STATE_DIR

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()
        sch._SCHOOL = None


class TestAppMap(_IsolatedState):
    def test_record_persist_and_no_generic_clobber(self):
        m = sch.AppMap()
        self.assertTrue(m.record("binance", "movers", url="https://x/markets", via="Markets",
                                 endpoint="x/api/movers"))
        # a second specific sighting must NOT clobber the learned url (only bump n)
        self.assertFalse(m.record("binance", "movers", url="https://x/other", via="Markets"))
        self.assertEqual(m.best("binance", "movers")["n"], 2)
        self.assertEqual(m.best("binance", "movers")["url"], "https://x/markets")
        m.save()
        self.assertEqual(sch.AppMap().best("binance", "movers")["url"], "https://x/markets")

    def test_home_route_upgrades_to_specific(self):
        m = sch.AppMap()
        m.record("binance", "movers", url="https://x/home", via="home")   # generic first
        m.record("binance", "movers", url="https://x/markets", via="Markets")   # specific → upgrade
        self.assertEqual(m.best("binance", "movers")["via"], "Markets")
        self.assertEqual(m.best("binance", "movers")["url"], "https://x/markets")

    def test_coverage_and_missing(self):
        m = sch.AppMap()
        m.record("binance", "movers", url="u", via="v")
        cov = m.coverage("binance")
        self.assertIn("movers", cov["learned"])
        self.assertIn("futures", cov["missing"])
        self.assertGreater(cov["pct"], 0)

    def test_visited_tracking(self):
        m = sch.AppMap()
        self.assertFalse(m.is_visited("binance", "Markets"))
        m.mark_visited("binance", "Markets")
        self.assertTrue(m.is_visited("binance", "Markets"))


class TestRouteTo(_IsolatedState):
    def test_seed_then_learned_override(self):
        s = sch.AppSchool(sessions=object(), cortex=object())
        r = s.route_to("binance", "movers")
        self.assertEqual(r["source"], "seed")          # cold start → seed fallback
        self.assertFalse(r["confirmed"])
        s.map.record("binance", "movers", url="https://learned/markets", via="Markets")
        r2 = s.route_to("binance", "movers")
        self.assertEqual(r2["source"], "learned")      # learned route overrides the seed
        self.assertEqual(r2["url"], "https://learned/markets")

    def test_unknown_kind_returns_none(self):
        s = sch.AppSchool(sessions=object(), cortex=object())
        self.assertIsNone(s.route_to("binance", "no_such_kind"))


class TestRanking(_IsolatedState):
    def test_missing_goal_labels_ranked_first_and_forbidden_skipped(self):
        s = sch.AppSchool(sessions=object(), cortex=object())
        controls = ["Buy", "Deposit", "Options", "Futures", "Help", "Markets", "Sell"]
        ranked = s._rank("binance", controls)
        self.assertNotIn("Buy", ranked)                # forbidden order controls skipped
        self.assertNotIn("Sell", ranked)
        self.assertNotIn("Deposit", ranked)
        # segment features that lead to missing goals come first
        self.assertTrue(set(["Options", "Futures", "Markets"]).issubset(set(ranked)))
        self.assertLess(ranked.index("Markets"), ranked.index("Help") if "Help" in ranked else 999)


class _FakePage:
    def __init__(self, url, controls):
        self.url = url
        self._controls = controls
        self.closed = False

    def wait_for_timeout(self, _ms):
        pass

    def close(self):
        self.closed = True


class _FakeCortex:
    def __init__(self, controls):
        self._controls = controls

    def perceive(self, broker, kind, *, page=None, url="", capture_screenshot=True):
        class F:
            dom_controls = [{"label": c} for c in (page._controls if page else self._controls)]
        return F()


class _FakeRegistry:
    def find(self, broker, kind):
        return [f"binance/api/{kind}"]


class _FakeRecorder:
    def __init__(self, fresh_kinds):
        self._fresh = fresh_kinds
        self.registry = _FakeRegistry()

    def latest(self, broker, kind, max_age_s=90):
        return {"data": 1} if kind in self._fresh else None


class TestExplore(_IsolatedState):
    def test_explore_learns_route_from_traffic(self):
        # home page exposes 'ticker' (→ movers/spot goals); clicking "Futures" exposes 'funding'
        page = _FakePage("https://www.binance.com/en", ["Futures", "Options", "Buy"])
        sessions = mock.MagicMock()
        sessions.page.return_value = page
        s = sch.AppSchool(sessions=sessions, cortex=_FakeCortex(["Futures", "Options", "Buy"]))
        # first harvest (home): ticker fresh → movers+spot; after a click: funding fresh → futures
        rec = _FakeRecorder({"ticker"})
        with mock.patch.object(s, "recorder", return_value=rec), \
             mock.patch("trading.brain.vision.computer_use._find_control",
                        return_value=mock.MagicMock()):
            # make 'funding' appear fresh only after the first click, to simulate navigation
            orig_latest = rec.latest

            def latest(broker, kind, max_age_s=90):
                if kind == "funding" and s.stats["clicks"] >= 1:
                    return {"f": 1}
                return orig_latest(broker, kind, max_age_s)
            rec.latest = latest
            rep = s.explore("binance", budget_s=30, max_clicks=5)
        self.assertIsNone(rep["error"])
        self.assertIn("movers", rep["goals_met"])          # learned from home traffic
        self.assertIn("futures", rep["goals_met"])         # learned after clicking Futures
        self.assertEqual(s.map.best("binance", "futures")["via"], "Futures")
        self.assertTrue(page.closed)

    def test_explore_not_logged_in(self):
        sessions = mock.MagicMock()
        sessions.page.return_value = None                  # login wall
        s = sch.AppSchool(sessions=sessions, cortex=_FakeCortex([]))
        rep = s.explore("binance")
        self.assertIn("not logged in", rep["error"])


class TestFastMovers(_IsolatedState):
    def test_fast_movers_sorted_and_formatted(self):
        s = sch.AppSchool(sessions=object(), cortex=object())
        ex = mock.MagicMock()
        ex.fetch_tickers.return_value = {
            "BTC/USDT:USDT": {"percentage": 1.2, "quoteVolume": 5e8},
            "DOGE/USDT:USDT": {"percentage": -18.5, "quoteVolume": 3e8},
            "ETH/USDT:USDT": {"percentage": 4.0, "quoteVolume": 4e8},
            "ILLIQ/USDT:USDT": {"percentage": 50.0, "quoteVolume": 1000},   # huge move but illiquid
            "BAD/USDT:USDT": {"percentage": None},          # skipped (no change)
        }
        with mock.patch("trading.broker_sense.app_school._ccxt_exchange", return_value=ex):
            rows = s.fast_movers("binance", "crypto", limit=2, segment="futures")
        self.assertEqual(len(rows), 2)                       # top-2 LIQUID by |change|
        self.assertEqual(rows[0]["symbol"], "DOGE/USDT:USDT")   # biggest LIQUID move first
        self.assertNotIn("ILLIQ/USDT:USDT", [r["symbol"] for r in rows])   # illiquid dropped
        self.assertEqual(rows[0]["change"], -18.5)
        self.assertEqual(rows[0]["preset"], "account_fast")

    def test_fast_movers_non_crypto_empty(self):
        s = sch.AppSchool(sessions=object(), cortex=object())
        self.assertEqual(s.fast_movers("angelone", "nse"), [])


class TestAccountScreenWiring(_IsolatedState):
    def test_account_screen_uses_fast_read_first(self):
        from trading.broker_sense import screeners
        from trading.broker_sense.brokers import REGISTRY
        with mock.patch("trading.brain.credentials.get_vault") as gv, \
             mock.patch("trading.broker_sense.app_school.AppSchool.fast_movers",
                        return_value=[{"symbol": "BTC/USDT:USDT", "change": 9.0, "lane": "binance"}]) as fm, \
             mock.patch.object(screeners, "_parse_screen_page") as parse:
            gv.return_value.get.return_value = {"username": "u", "password": "p"}
            rows = screeners.account_screen(REGISTRY["binance"], mock.MagicMock())
        self.assertEqual(rows[0]["symbol"], "BTC/USDT:USDT")
        fm.assert_called()
        parse.assert_not_called()                            # fast read → NO slow page render

    def test_account_screen_uses_learned_route_not_dashboard(self):
        from trading.broker_sense import app_school, screeners
        from trading.broker_sense.brokers import REGISTRY
        # brain has LEARNED the movers route → account_screen must open THAT, not home/dashboard
        app_school.get_school().map.record("binance", "movers",
                                           url="https://www.binance.com/en/markets/overview",
                                           via="Markets")
        captured = {}

        def fake_parse(broker, sessions, url, *, limit, preset):
            captured["url"] = url
            captured["preset"] = preset
            return [{"symbol": "BTC/USDT", "change": 5.0, "lane": broker.name}]

        with mock.patch("trading.brain.credentials.get_vault") as gv, \
             mock.patch("trading.broker_sense.app_school.AppSchool.fast_movers", return_value=[]), \
             mock.patch.object(screeners, "_parse_screen_page", side_effect=fake_parse):
            gv.return_value.get.return_value = {"username": "u", "password": "p"}
            rows = screeners.account_screen(REGISTRY["binance"], mock.MagicMock())
        self.assertEqual(captured["url"], "https://www.binance.com/en/markets/overview")
        self.assertEqual(captured["preset"], "account")
        self.assertEqual(rows[0]["symbol"], "BTC/USDT")


if __name__ == "__main__":
    unittest.main()
