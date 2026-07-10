"""Tests for the Broker-Sense Funnel (trading/broker_sense) — offline, STATE_DIR-isolated.

Covers: broker role enforcement (screening apps can never execute real money), the
credential-vault merge semantics (OTP answers never clobber saved logins), hot-watchlist
TTL, learning-column discovery, vision cache/dedup + screenshot deletion, book-monitor
accuracy gate + API fail-safe, funnel cycle completion within budget, and the exec
adapter's paper routing. No network, no browser: every external surface is stubbed.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state


class _IsolatedState(unittest.TestCase):
    """Every test runs against a throwaway STATE_DIR (never the live journal/wallets)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        # kill module-level singletons that captured the old dir
        import trading.broker_sense.learning_columns as lc
        import trading.broker_sense.app_explorer as ae
        lc._REG = None
        ae._CAT = None

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


class TestBrokerRoles(_IsolatedState):
    def test_screening_apps_cannot_execute_real(self):
        from trading.broker_sense.brokers import RoleViolation, assert_can_execute
        for name in ("bybit", "coinbase", "tradingview"):
            with self.assertRaises(RoleViolation):
                assert_can_execute(name, "crypto", live=True)

    def test_binance_is_the_only_real_crypto_broker(self):
        from trading.broker_sense.brokers import assert_can_execute
        assert_can_execute("binance", "crypto", live=True)     # must not raise

    def test_nse_real_requires_owner_pick(self):
        from trading.broker_sense.brokers import (RoleViolation, assert_can_execute,
                                                  real_broker, set_real_nse_broker)
        self.assertIsNone(real_broker("nse"))
        with self.assertRaises(RoleViolation):
            assert_can_execute("angelone", "nse", live=True)   # not picked yet
        set_real_nse_broker("upstox")
        assert_can_execute("upstox", "nse", live=True)
        with self.assertRaises(RoleViolation):
            assert_can_execute("groww", "nse", live=True)      # only the picked one
        with self.assertRaises(RoleViolation):
            set_real_nse_broker("bybit")                       # not an NSE candidate

    def test_paper_is_never_role_blocked(self):
        from trading.broker_sense.brokers import assert_can_execute
        assert_can_execute("zerodha-sandbox", "nse", live=False)


class TestVaultMerge(_IsolatedState):
    def test_otp_submit_keeps_saved_login(self):
        from trading.brain.credentials import CredentialVault
        v = CredentialVault()
        v.submit("angelone.in", {"username": "AB1234", "password": "pin"})
        v.submit("angelone.in", {"otp": "998877"})             # OTP-only answer
        creds = v.get("angelone.in")
        self.assertEqual(creds["username"], "AB1234")          # NOT clobbered
        self.assertEqual(creds["otp"], "998877")
        self.assertTrue(v.clear_field("angelone.in", "otp"))   # consumed one-time
        self.assertNotIn("otp", v.get("angelone.in"))


class TestWatchlist(_IsolatedState):
    def test_ttl_and_pinning(self):
        from trading.broker_sense.watchlist import HotWatchlist
        w = HotWatchlist(ttl_bars=2, max_hot=3)
        w.touch("AAA", score=5.0)
        w.touch("BBB", score=1.0)
        w.pin("OPEN")
        self.assertEqual(w.hot()[0], "OPEN")                   # pinned first
        self.assertIn("AAA", w.hot())
        # expire: shift last_seen 3 bars back → cold symbols drop, pinned stays
        for s in ("AAA", "BBB"):
            w.data[s]["last_seen_bar"] -= 3
        hot = w.hot()
        self.assertNotIn("AAA", hot)
        self.assertIn("OPEN", hot)

    def test_max_hot_bound(self):
        from trading.broker_sense.watchlist import HotWatchlist
        w = HotWatchlist(ttl_bars=5, max_hot=4)
        for i in range(20):
            w.touch(f"S{i}", score=i)
        self.assertEqual(len(w.hot()), 4)                      # saver E hard bound


class TestLearningColumns(_IsolatedState):
    def test_discovery_registers_and_snapshots(self):
        from trading.broker_sense.learning_columns import discover_from_text, get_registry
        text = "Delivery Percentage: 63.4%\nOpen Interest 1,23,456\nAnalyst Rating 4.2"
        fresh = discover_from_text("groww", text, symbol="RELIANCE")
        self.assertTrue(fresh)                                 # new columns discovered
        snap = get_registry().snapshot("RELIANCE")
        self.assertTrue(any("delivery" in k for k in snap))
        # second sighting is not "new" but still updates values
        self.assertEqual(discover_from_text("groww", "Analyst Rating 4.5",
                                            symbol="TCS"), [])

    def test_stop_words_not_registered(self):
        from trading.broker_sense.learning_columns import discover_from_text, get_registry
        discover_from_text("app", "Close 101.5 Volume 999")
        self.assertNotIn("close", get_registry().columns)


class TestChartVision(_IsolatedState):
    def _fake_capture(self, sym="BTC/USDT:USDT", tf="5m"):
        # deterministic tiny png via matplotlib-free path: just bytes on disk
        from trading.broker_sense import chart_vision as cv
        p = cv._shot_dir() / f"x_{tf}.png"
        from PIL import Image
        Image.new("L", (20, 20), 128).save(p)
        return str(p), "screenshot:test"

    def test_dedup_cache_and_deletion(self):
        from trading.broker_sense import chart_vision as cv
        vis = cv.ChartVision(sessions=None)
        with mock.patch.object(cv.ChartVision, "_capture_app",
                               side_effect=lambda *a, **k: self._fake_capture()), \
             mock.patch("trading.broker_sense.cnn_direction.get_model") as gm, \
             mock.patch("trading.broker_sense.cnn_direction.llm_escalate",
                        return_value=None):
            gm.return_value.predict = lambda paths: [
                {"p_up": 0.7, "direction": "long", "source": "cnn", "escalate": False}
                for _ in paths]
            out1 = vis.read([{"symbol": "BTC/USDT:USDT", "lane": "binance"}], "crypto",
                            timeframes=("5m",))
            self.assertEqual(out1["BTC/USDT:USDT"]["5m"]["direction"], "long")
            out2 = vis.read([{"symbol": "BTC/USDT:USDT", "lane": "binance"}], "crypto",
                            timeframes=("5m",))
            self.assertTrue(out2["BTC/USDT:USDT"]["5m"].get("cached"))   # saver D
        # owner's step 7: nothing left on disk
        self.assertEqual(list(state._path(cv._SHOT_DIR).glob("*.png")), [])

    def test_total_miss_is_honest_neutral(self):
        from trading.broker_sense import chart_vision as cv
        vis = cv.ChartVision(sessions=None)
        with mock.patch.object(cv.ChartVision, "_capture_app", return_value=None), \
             mock.patch.object(cv.ChartVision, "_render_api", return_value=None):
            out = vis.read([{"symbol": "X/USDT:USDT"}], "crypto", timeframes=("5m",))
        self.assertEqual(out["X/USDT:USDT"]["5m"]["source"], "unavailable")


class TestBookMonitor(_IsolatedState):
    def test_ocr_rejected_falls_back_to_api(self):
        from trading.broker_sense.book_monitor import BookMonitor
        bm = BookMonitor(sessions=None)
        api = {"bid": 100.0, "ask": 100.1, "source": "api:test"}
        bad = {"bid": 90.0, "ask": 130.0, "source": "screen:test"}      # misread digits
        with mock.patch("trading.broker_sense.data_failsafe.top_of_book",
                        return_value=api), \
             mock.patch.object(BookMonitor, "_ocr_book", return_value=bad):
            out = bm.top_of_book("BTC/USDT:USDT", "crypto")
        self.assertEqual(out["bid"], 100.0)                    # API number won
        self.assertFalse(out["consistent"])
        self.assertIn("screen_rejected", out)

    def test_consistent_screen_read_is_kept(self):
        from trading.broker_sense.book_monitor import BookMonitor
        bm = BookMonitor(sessions=None)
        api = {"bid": 100.0, "ask": 100.2, "source": "api:test"}
        scr = {"bid": 100.05, "ask": 100.15, "source": "screen:binance"}
        with mock.patch("trading.broker_sense.data_failsafe.top_of_book",
                        return_value=api), \
             mock.patch.object(BookMonitor, "_ocr_book", return_value=scr):
            out = bm.top_of_book("BTC/USDT:USDT", "crypto")
        self.assertEqual(out["source"], "screen:binance")
        self.assertTrue(out["consistent"])
        self.assertIsNotNone(out["spread_pct"])

    def test_no_screen_no_api_is_honest(self):
        from trading.broker_sense.book_monitor import BookMonitor
        bm = BookMonitor(sessions=None)
        with mock.patch("trading.broker_sense.data_failsafe.top_of_book",
                        return_value=None), \
             mock.patch.object(BookMonitor, "_ocr_book", return_value=None):
            out = bm.top_of_book("Z/USDT:USDT", "crypto")
        self.assertEqual(out["source"], "unavailable")


class TestExecAdapter(_IsolatedState):
    def test_crypto_paper_routes_to_freqtrade(self):
        from trading.broker_sense.exec_adapter import ExecAdapter
        cli = mock.Mock()
        cli.place_order.return_value = {"ok": True}
        ad = ExecAdapter(crypto_client=cli)
        r = ad.place(market="crypto", symbol="BTC/USDT:USDT", action="LONG",
                     segment="futures", enter_tag="broker_sense:test")
        self.assertTrue(r["placed"])
        self.assertFalse(r["live"])
        cli.place_order.assert_called_once()
        self.assertFalse(cli.place_order.call_args.kwargs["allow_live"])

    def test_nse_paper_routes_to_openalgo(self):
        from trading.broker_sense.exec_adapter import ExecAdapter
        cli = mock.Mock()
        cli.place_order.return_value = {"ok": True}
        ad = ExecAdapter(nse_client=cli)
        r = ad.place(market="nse", symbol="RELIANCE", action="BUY")
        self.assertTrue(r["placed"])
        self.assertEqual(r["broker"], "zerodha-sandbox")
        cli.place_order.assert_called_once()

    def test_live_without_env_flag_stays_paper(self):
        from trading.broker_sense.exec_adapter import ExecAdapter
        cli = mock.Mock()
        cli.place_order.return_value = {"ok": True}
        ad = ExecAdapter(crypto_client=cli)
        os.environ.pop("CRYPTO_ALLOW_LIVE", None)
        r = ad.place(market="crypto", symbol="BTC/USDT:USDT", action="LONG", live=True)
        self.assertFalse(r["live"])                            # hard paper gate


class TestFunnelCycle(_IsolatedState):
    def test_cycle_completes_within_budget_and_wires_signals(self):
        """End-to-end (all externals stubbed): screen → heat → look → verify → execute;
        app_signals must reach the executor; screenshots wiped; budget respected."""
        from trading.broker_sense.funnel import BrokerSenseFunnel
        ex = mock.Mock()
        ex.client.return_value.open_pairs.return_value = []
        ex.run_once.return_value = {"entered": ["AAA/USDT:USDT"], "exited": [],
                                    "skipped": 0, "vetoes": []}
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock(), executor=ex)
        rows = [{"symbol": "AAA/USDT:USDT", "change": 4.2, "lane": "binance",
                 "preset": "momentum", "volume": 1e6}]
        charts = {"AAA/USDT:USDT": {
            "5m": {"p_up": 0.8, "direction": "long", "source": "cnn"},
            "15m": {"p_up": 0.75, "direction": "long", "source": "cnn"}}}
        book = {"bid": 10.0, "ask": 10.01, "spread_pct": 0.1, "source": "api:test",
                "consistent": True}
        with mock.patch("trading.broker_sense.funnel.screen_all", return_value=rows), \
             mock.patch("trading.broker_sense.fast_candles.read", return_value=charts), \
             mock.patch("trading.broker_sense.data_failsafe.top_of_book", return_value=book), \
             mock.patch.object(f.vision, "read", return_value=charts), \
             mock.patch.object(f.book, "top_of_book", return_value=book), \
             mock.patch.dict(os.environ, {"BROKER_SENSE_EXPLORE_WIDE_N": "0"}):
            rep = f.run_cycle(segment="futures")
        self.assertTrue(rep["completed_within_budget"])
        self.assertEqual(rep["stages"]["execute"]["entered"], ["AAA/USDT:USDT"])
        # the shortlist-only universe + app_signals actually reached the executor
        # (wide lane disabled above so the DEEP lane is asserted in isolation)
        self.assertEqual(ex._symbols, ["AAA/USDT:USDT"])
        sig = ex.extra_signals["AAA/USDT:USDT"]
        self.assertEqual(sig["vote"]["direction"], "long")
        self.assertEqual(sig["book"]["source"], "api:test")
        self.assertEqual(sig["screener"]["lane"], "binance")

    def test_explore_wide_lane_adds_light_candidates(self):
        """2026-07-07 throughput fix: in paper explore, screened rows beyond the deep
        shortlist become tradeable with an honest light signature (direction from the
        broker's own change%), and open positions don't consume shortlist slots."""
        from trading.broker_sense.funnel import BrokerSenseFunnel
        ex = mock.Mock()
        ex.client.return_value.open_pairs.return_value = ["OPEN/USDT:USDT"]
        ex.run_once.return_value = {"entered": [], "exited": [], "skipped": 0, "vetoes": []}
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock(), executor=ex)
        rows = [{"symbol": "AAA/USDT:USDT", "change": 4.2, "lane": "binance"},
                {"symbol": "BBB/USDT:USDT", "change": -3.1, "lane": "binance-losers"},
                {"symbol": "CCC/USDT:USDT", "change": 1.0, "lane": "binance"}]
        charts = {"AAA/USDT:USDT": {
            "5m": {"p_up": 0.8, "direction": "long", "source": "cnn"}}}
        book = {"bid": 10.0, "ask": 10.01, "spread_pct": 0.1, "source": "api:test",
                "consistent": True}
        with mock.patch("trading.broker_sense.funnel.screen_all", return_value=rows), \
             mock.patch("trading.broker_sense.fast_candles.read", return_value=charts), \
             mock.patch("trading.broker_sense.data_failsafe.top_of_book", return_value=book), \
             mock.patch.object(f.vision, "read", return_value=charts), \
             mock.patch.object(f.book, "top_of_book", return_value=book), \
             mock.patch.dict(os.environ, {"BROKER_SENSE_EXPLORE_WIDE_N": "16",
                                          "BRAIN_EXPLORE_OPEN_ALL": "1"}):
            rep = f.run_cycle(segment="futures")
        wide = rep["stages"].get("explore_wide", {})
        self.assertGreaterEqual(wide.get("added", 0), 2)       # BBB + CCC joined light
        self.assertIn("BBB/USDT:USDT", ex._symbols)
        self.assertIn("CCC/USDT:USDT", ex._symbols)
        sig_b = ex.extra_signals["BBB/USDT:USDT"]
        self.assertTrue(sig_b["light"])
        self.assertEqual(sig_b["vote"]["direction"], "short")  # negative change% → short
        # open position rides free: present in universe, not a consumed shortlist slot
        self.assertIn("OPEN/USDT:USDT", ex._symbols)
        self.assertEqual(rep["stages"]["heat"]["pinned_open"], 1)

    def test_wide_spread_is_culled_by_code_not_llm(self):
        from trading.broker_sense.funnel import BrokerSenseFunnel
        ex = mock.Mock()
        ex.client.return_value.open_pairs.return_value = []
        ex.run_once.return_value = {"entered": [], "exited": [], "skipped": 0, "vetoes": []}
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock(), executor=ex)
        rows = [{"symbol": "WIDE/USDT:USDT", "change": 9.9, "lane": "binance"}]
        charts = {"WIDE/USDT:USDT": {"5m": {"p_up": 0.9, "direction": "long",
                                            "source": "cnn"},
                                     "15m": {"p_up": 0.9, "direction": "long",
                                             "source": "cnn"}}}
        book = {"bid": 10.0, "ask": 11.0, "spread_pct": 9.5, "source": "api:test",
                "consistent": True}
        # explore-open-all makes spread ADVISORY in paper (owner 2026-07-06); pin it OFF
        # here so this test verifies the in-code spread-cull rule deterministically.
        with mock.patch.dict(os.environ, {"BRAIN_EXPLORE_OPEN_ALL": "0"}), \
             mock.patch("trading.broker_sense.funnel.screen_all", return_value=rows), \
             mock.patch("trading.broker_sense.fast_candles.read", return_value=charts), \
             mock.patch("trading.broker_sense.data_failsafe.top_of_book", return_value=book), \
             mock.patch.object(f.vision, "read", return_value=charts), \
             mock.patch.object(f.book, "top_of_book", return_value=book):
            f.run_cycle(segment="futures")
        self.assertEqual(ex._symbols, [])                      # spread rule culled it


class TestCnnModel(unittest.TestCase):
    def test_warm_start_and_batched_shapes(self):
        from trading.broker_sense.cnn_direction import get_model
        m = get_model()
        with tempfile.TemporaryDirectory() as d:
            from PIL import Image
            paths = []
            for i in range(3):
                p = os.path.join(d, f"c{i}.png")
                Image.new("L", (64, 64), 40 * i).save(p)
                paths.append(p)
            out = m.predict(paths)
        self.assertEqual(len(out), 3)
        self.assertTrue(m.warm_started, "vendored cnn.pkl must load strict")
        for r in out:
            self.assertIn(r["direction"], ("long", "short", "neutral"))
            self.assertEqual(r["source"], "cnn")


class TestOtpBoxDetection(unittest.TestCase):
    """2026-07-06 regression: Angel One's step-1 mobile input is inputmode=numeric, so a
    REJECTED step 1 false-flagged as 'OTP sent' (no SMS was ever sent). The predicate must
    tell identity fields apart from real one-time-code boxes."""

    def test_mobile_number_field_is_not_an_otp_box(self):
        from trading.broker_sense.sessions import _otp_attrs_are_code_box
        self.assertFalse(_otp_attrs_are_code_box({"placeholder": "Mobile Number"}))
        self.assertFalse(_otp_attrs_are_code_box({"aria-label": "Enter your Client ID"}))
        self.assertFalse(_otp_attrs_are_code_box({"name": "email"}))
        self.assertFalse(_otp_attrs_are_code_box({}))            # unlabeled full-width numeric

    def test_real_code_boxes_detected(self):
        from trading.broker_sense.sessions import _otp_attrs_are_code_box
        self.assertTrue(_otp_attrs_are_code_box({"autocomplete": "one-time-code"}))
        self.assertTrue(_otp_attrs_are_code_box({"name": "otp1"}))
        self.assertTrue(_otp_attrs_are_code_box({"id": "verification-code"}))
        self.assertTrue(_otp_attrs_are_code_box({"maxlength": "6"}))  # short bare numeric box


class TestWedgeRegressions(_IsolatedState):
    """The 2026-07-05 run_cycle wedge, pinned: (1) _brain_net refetched the FULL closed-trade
    history per strategy × per symbol; (2) run_once had no deadline; (3) core.llm.chat's
    failover chain ignored the caller's wall-clock budget."""

    def test_brain_net_fetches_closed_trades_once_within_ttl(self):
        from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider

        class _CountingClient:
            calls = 0
            def closed_trades(self):
                _CountingClient.calls += 1
                return []

        d = PerCoinBrainDecider(use_brain=True)
        d._brain_client = _CountingClient()
        for _ in range(5):
            d._brain_net()
        self.assertEqual(_CountingClient.calls, 1, "TTL must stop the per-call HTTP refetch")
        d._net_ts = float("-inf")                     # TTL expired → exactly one more fetch
        d._brain_net()
        self.assertEqual(_CountingClient.calls, 2)

    def test_run_once_deadline_defers_symbols(self):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        decider = mock.Mock()
        cli = mock.Mock()
        cli.open_pairs.return_value = []
        ex = BrainExecutor(decider=decider, client=cli,
                           symbols=["A/USDT:USDT", "B/USDT:USDT", "C/USDT:USDT"])
        res = ex.run_once(deadline=time.monotonic() - 1)      # budget already gone
        decider.decide.assert_not_called()
        self.assertEqual(res["deadline_deferred"], 3)
        self.assertEqual(res["entered"], [])

    def test_status_serves_freshest_cycle_across_processes(self):
        """The panel must show the DRIVER process's persisted cycle when it's newer than
        the dashboard instance's own in-memory one (dashboard-sync)."""
        from trading.broker_sense.funnel import BrokerSenseFunnel
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock(), executor=mock.Mock())
        f.last = {"cycle": 1, "took_s": 55.0, "ts": 100.0}
        state.save_json("broker_sense_status.json",
                        {"crypto": {"cycle": 7, "took_s": 51.2, "ts": 200.0}})
        self.assertEqual(f.status()["last_cycle"]["cycle"], 7)
        state.save_json("broker_sense_status.json",
                        {"crypto": {"cycle": 3, "took_s": 60.0, "ts": 50.0}})
        self.assertEqual(f.status()["last_cycle"]["cycle"], 1)   # own report is fresher

    def test_chat_total_timeout_bounds_the_failover_chain(self):
        from core import llm

        def slow_fail(**kw):
            time.sleep(0.15)
            raise RuntimeError("provider down")

        cands = [("openai/one", {}), ("openai/two", {}), ("openai/three", {})]
        with mock.patch.object(llm, "_candidates", return_value=cands), \
             mock.patch("litellm.completion", side_effect=slow_fail) as comp:
            with self.assertRaises(RuntimeError):
                llm.chat([{"role": "user", "content": "hi"}], total_timeout=0.1)
        self.assertEqual(comp.call_count, 1,
                         "chain must stop once the total budget is exhausted")


class TestExecutorPerSegment(_IsolatedState):
    """Regression 2026-07-10: a single cached executor baked in whichever segment asked
    first — the options/prediction drivers got the FUTURES executor back, so options
    cycles opened futures trades under a [funnel:crypto:options] log label."""

    def test_each_segment_gets_its_own_executor(self):
        from trading.broker_sense.funnel import BrokerSenseFunnel
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock())
        made = []

        class _FakeExec:
            def __init__(self, segment=None):
                self.segment = segment
                made.append(segment)

        with mock.patch("trading.crypto.freqtrade.brain_executor.BrainExecutor",
                        _FakeExec):
            fut = f.executor("futures")
            opt = f.executor("options")
        self.assertIsNot(fut, opt, "options must not reuse the futures executor")
        self.assertEqual(fut.segment, "futures")
        self.assertEqual(opt.segment, "options")
        self.assertIs(f.executor("futures"), fut)     # still cached per segment
        self.assertIs(f.executor("options"), opt)
        self.assertEqual(made, ["futures", "options"])

    def test_injected_executor_still_overrides_all_segments(self):
        from trading.broker_sense.funnel import BrokerSenseFunnel
        ex = mock.Mock()
        f = BrokerSenseFunnel("crypto", sessions=mock.Mock(), executor=ex)
        self.assertIs(f.executor("futures"), ex)
        self.assertIs(f.executor("options"), ex)


if __name__ == "__main__":
    unittest.main()
