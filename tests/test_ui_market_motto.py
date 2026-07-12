"""THE MOTTO build tests (2026-07-12): ui_market superstore, WS-kline upsert,
interception forwarding, tab pool, Upstox protobuf decode, and the API-path gates."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        # ignore_cleanup_errors: the doors' snapshot DAEMON threads write into the
        # patched STATE_DIR (path resolved at spawn — the live-state-leak fix) and can
        # race this directory's teardown
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        from trading.broker_sense import ui_data, ui_market
        ui_market._STORE.clear()
        ui_market._LIQS.clear()
        ui_market._HITS.update({"fed": 0, "served": 0, "missed": 0})
        ui_data._STORE.clear()
        ui_data._HITS.update({"served": 0, "missed": 0, "fed": 0})

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()
        for k in ("UI_ONLY_DATA", "UI_TAB_POOL"):
            os.environ.pop(k, None)


class UiMarketTest(_Base):
    def test_orderbook_rest_and_ws_shapes(self):
        from trading.broker_sense import ui_market
        url = "https://www.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=20"
        body = {"bids": [["50000.5", "2.0"], ["50000.0", "1.0"]],
                "asks": [["50001.0", "3.0"]]}
        self.assertEqual(ui_market.feed_capture("binance", "orderbook", url, body), 1)
        bk = ui_market.book("BTC/USDT:USDT")
        self.assertAlmostEqual(bk["bid"], 50000.5)
        self.assertAlmostEqual(bk["ask"], 50001.0)
        # bookTicker WS shape (b/a are price strings)
        ws = {"u": 1, "s": "ETHUSDT", "b": "3000.1", "B": "5", "a": "3000.2", "A": "7"}
        self.assertEqual(ui_market.feed_capture("binance", "orderbook", "wss://x", ws), 1)
        self.assertAlmostEqual(ui_market.book("ETHUSDT")["bid"], 3000.1)

    def test_depth_diff_frames_are_not_books(self):
        from trading.broker_sense import ui_market
        # plain @depth stream = DIFF: its levels are updates, NOT top-of-book
        diff = {"stream": "btcusdt@depth", "data": {
            "e": "depthUpdate", "s": "BTCUSDT", "U": 1, "u": 2, "pu": 0,
            "b": [["1000.0", "3.0"]], "a": []}}
        self.assertEqual(ui_market.feed_capture("binance", "orderbook", "wss://s", diff), 0)
        # @depth20 partial stream = top-20 SNAPSHOT: trusted
        snap = {"stream": "btcusdt@depth20@500ms", "data": {
            "e": "depthUpdate", "s": "BTCUSDT", "U": 3, "u": 4, "pu": 2,
            "b": [["64000.0", "2.0"]], "a": [["64000.5", "1.0"]]}}
        self.assertEqual(ui_market.feed_capture("binance", "orderbook", "wss://s", snap), 1)
        self.assertAlmostEqual(ui_market.book("BTCUSDT")["bid"], 64000.0)
        # eventful frame with NO stream info → origin unknown → not trusted
        bare = {"e": "depthUpdate", "s": "ETHUSDT", "U": 1, "u": 2,
                "b": [["1.0", "1"]], "a": []}
        self.assertEqual(ui_market.feed_capture("binance", "orderbook", "wss://s", bare), 0)

    def test_mark_price_array_merges_funding(self):
        from trading.broker_sense import ui_market
        arr = [{"e": "markPriceUpdate", "s": "BTCUSDT", "p": "50100.0", "r": "0.0001",
                "T": 1800000000000},
               {"e": "markPriceUpdate", "s": "ETHUSDT", "p": "3001.0", "r": "-0.0002",
                "T": 1800000000000}]
        self.assertEqual(ui_market.feed_capture("binance", "mark_price", "wss://f", arr), 2)
        f = ui_market.funding("BTCUSDT")
        self.assertAlmostEqual(f["mark"], 50100.0)
        self.assertAlmostEqual(f["funding_rate"], 0.0001)
        # a funding-only REST row must MERGE, not wipe the mark
        rest = {"symbol": "BTCUSDT", "lastFundingRate": "0.0003"}
        ui_market.feed_capture("binance", "funding", "https://f/premiumIndex", rest)
        f2 = ui_market.funding("BTCUSDT")
        self.assertAlmostEqual(f2["funding_rate"], 0.0003)
        self.assertAlmostEqual(f2["mark"], 50100.0)

    def test_ticker_movers_and_freshness(self):
        from trading.broker_sense import ui_market
        arr = [{"e": "24hrTicker", "s": "AUSDT", "c": "1.0", "P": "12.5", "q": "9e6"},
               {"e": "24hrTicker", "s": "BUSDT", "c": "2.0", "P": "-20.0", "q": "5e6"},
               {"e": "24hrTicker", "s": "CUSDT", "c": "3.0", "P": "3.0", "q": "1e6"}]
        self.assertEqual(ui_market.feed_capture("binance", "ticker", "wss://t", arr), 3)
        mv = ui_market.movers(2)
        self.assertEqual([m["symbol"] for m in mv], ["BUSDT", "AUSDT"])
        # stale entries serve honest None
        ui_market._STORE[("ticker", "AUSDT")]["ts"] -= 10_000
        self.assertIsNone(ui_market.ticker("AUSDT"))

    def test_positioning_and_liquidations(self):
        from trading.broker_sense import ui_market
        ls = [{"symbol": "BTCUSDT", "longShortRatio": "1.4", "longAccount": "0.58",
               "timestamp": 1}]
        ui_market.feed_capture("binance", "long_short",
                               "https://f/futures/data/globalLongShortAccountRatio", ls)
        self.assertAlmostEqual(ui_market.long_short("BTCUSDT")["long_pct"], 0.58)
        smart = [{"symbol": "BTCUSDT", "longShortRatio": "2.0", "longAccount": "0.66"}]
        ui_market.feed_capture("binance", "long_short",
                               "https://f/futures/data/topLongShortPositionRatio", smart)
        self.assertAlmostEqual(ui_market.long_short("BTCUSDT", smart=True)["ratio"], 2.0)
        self.assertAlmostEqual(ui_market.long_short("BTCUSDT")["ratio"], 1.4)  # distinct
        tk = [{"symbol": "BTCUSDT", "buySellRatio": "1.2", "buyVol": "10", "sellVol": "8"}]
        ui_market.feed_capture("binance", "taker_volume", "https://f/taker", tk)
        self.assertAlmostEqual(ui_market.taker("BTCUSDT")["buy_sell_ratio"], 1.2)
        liq = {"e": "forceOrder", "o": {"s": "BTCUSDT", "S": "SELL", "q": "0.5",
                                        "ap": "49000"}}
        ui_market.feed_capture("binance", "liquidation", "wss://f", liq)
        self.assertEqual(len(ui_market.recent_liquidations("BTC/USDT:USDT")), 1)

    def test_snapshot_hydrate_cross_process(self):
        from trading.broker_sense import ui_market
        ui_market.feed_capture("binance", "ticker", "wss://t",
                               {"s": "XUSDT", "c": "5.0", "P": "1.0"})
        ui_market._write_snapshot(
            {f"{k}|{s}": {"ts": r["ts"], "broker": r["broker"], "data": r["data"]}
             for (k, s), r in ui_market._STORE.items()}, {})
        # simulate a reader process: cold store, no feeds
        ui_market._STORE.clear()
        ui_market._HITS["fed"] = 0
        globals()["_"] = ui_market._hydrate_from_snapshot()
        self.assertIsNotNone(ui_market.ticker("XUSDT"))


class WsKlineUpsertTest(_Base):
    def _seed(self, sym="BTCUSDT", tf="5m", n=30):
        from trading.broker_sense import ui_data
        t0 = int((time.time() - n * 300) * 1000)
        rows = [[t0 + i * 300_000, 100.0, 101.0, 99.0, 100.5, 10.0] for i in range(n)]
        url = f"https://b/fapi/v1/klines?symbol={sym}&interval={tf}"
        self.assertTrue(ui_data.feed_capture("binance", url, rows))
        return t0 + (n - 1) * 300_000

    def test_ws_updates_last_bar_and_appends(self):
        from trading.broker_sense import ui_data
        last_t = self._seed()
        frame = {"stream": "btcusdt@kline_5m",
                 "data": {"e": "kline", "s": "BTCUSDT",
                          "k": {"t": last_t, "o": 100.5, "h": 102.0, "l": 100.0,
                                "c": 101.7, "v": 12.0, "i": "5m"}}}
        self.assertTrue(ui_data.feed_ws_kline("binance", "wss://k", frame))
        rows = ui_data.ui_ohlcv("BTCUSDT", "5m")
        self.assertAlmostEqual(rows[-1][4], 101.7)          # same bar replaced
        n_before = len(rows)
        frame["data"]["k"]["t"] = last_t + 300_000          # next bar appends
        self.assertTrue(ui_data.feed_ws_kline("binance", "wss://k", frame))
        self.assertEqual(len(ui_data.ui_ohlcv("BTCUSDT", "5m")), n_before + 1)
        # out-of-order and nonsense are rejected
        frame["data"]["k"]["t"] = last_t - 300_000
        self.assertFalse(ui_data.feed_ws_kline("binance", "wss://k", frame))
        bad = {"e": "kline", "s": "BTCUSDT",
               "k": {"t": last_t + 600_000, "o": 1, "h": 1, "l": 2, "c": 1, "i": "5m"}}
        self.assertFalse(ui_data.feed_ws_kline("binance", "wss://k", bad))


class InterceptionForwardTest(_Base):
    def test_ws_frames_reach_the_doors_per_symbol(self):
        from trading.broker_sense import interception, ui_market
        rec = interception.NetworkRecorder(interception.EndpointRegistry())
        f1 = '{"e":"markPriceUpdate","s":"BTCUSDT","p":"50000","r":"0.0001"}'
        f2 = '{"e":"markPriceUpdate","s":"ETHUSDT","p":"3000","r":"0.0002"}'
        rec._handle_ws("wss://fstream/x", f1, "binance")
        rec._handle_ws("wss://fstream/x", f2, "binance")   # different symbol → NOT throttled
        self.assertIsNotNone(ui_market.funding("BTCUSDT"))
        self.assertIsNotNone(ui_market.funding("ETHUSDT"))
        # same symbol inside the window IS throttled (frame dropped)
        before = ui_market._HITS["fed"]
        rec._handle_ws("wss://fstream/x", f1, "binance")
        self.assertEqual(ui_market._HITS["fed"], before)

    def test_rest_body_forwards_non_candle_kind(self):
        from trading.broker_sense import interception, ui_market
        rec = interception.NetworkRecorder(interception.EndpointRegistry())
        rec._forward("binance", "orderbook",
                     "https://www.binance.com/fapi/v1/depth?symbol=SOLUSDT",
                     {"bids": [["100.0", "1"]], "asks": [["100.1", "2"]]})
        self.assertIsNotNone(ui_market.book("SOLUSDT"))

    def test_ws_kline_frame_reaches_ui_data(self):
        from trading.broker_sense import interception, ui_data
        rec = interception.NetworkRecorder(interception.EndpointRegistry())
        t = int(time.time() * 1000)
        frame = ('{"stream":"solusdt@kline_5m","data":{"e":"kline","s":"SOLUSDT",'
                 '"k":{"t":%d,"o":100,"h":101,"l":99,"c":100.5,"v":3,"i":"5m"}}}' % t)
        rec._handle_ws("wss://fstream/kline", frame, "binance")
        self.assertIn(("SOLUSDT", "5m"), ui_data._STORE)


class _FakeLocator:
    def __init__(self, visible=True):
        self._v = visible
        self.first = self

    def all(self):
        return [self]

    def is_visible(self, timeout=0):
        return self._v

    def click(self, timeout=0):
        pass


class _FakePage:
    def __init__(self):
        self.closed = False
        self.shots = 0

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True

    def locator(self, sel):
        return _FakeLocator()

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self, **kw):
        self.shots += 1
        return b"\xff\xd8\xfffakejpeg"


class _FakeSessions:
    def __init__(self):
        self.opened = []

    def page(self, broker, url=None, timeout_ms=0):
        self.opened.append(url)
        return _FakePage()


class TabPoolTest(_Base):
    def test_reconcile_open_close_snap(self):
        from trading.broker_sense import tab_pool
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        with mock.patch.dict(os.environ, {"UI_TAB_POOL_N": "3",
                                          "UI_TAB_OPEN_PER_CALL": "3",
                                          "UI_TAB_SNAP_S": "0"}):
            rep = pool.ensure(["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
                               "XRP/USDT:USDT"])
            self.assertEqual(len(rep["opened"]), 3)          # capped at pool N
            self.assertEqual(rep["snaps"], 4)   # 3 park snaps + 1 rotation-TF snap
            # shortlist rotates → dropped symbol's tab closes, new one opens
            rep2 = pool.ensure(["ETH/USDT:USDT", "SOL/USDT:USDT", "ADA/USDT:USDT"])
            self.assertIn("BTCUSDT", rep2["closed"])
            self.assertIn("ADAUSDT", rep2["opened"])
        # screenshots persisted for the vision lane
        self.assertTrue(tab_pool.charts("ETH/USDT:USDT"))

    def test_refresh_snaps_and_heals_parked_tabs(self):
        from trading.broker_sense import tab_pool
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        with mock.patch.dict(os.environ, {"UI_TAB_POOL_N": "2",
                                          "UI_TAB_OPEN_PER_CALL": "2",
                                          "UI_TAB_SNAP_S": "0"}):
            pool.ensure(["BTC/USDT:USDT", "ETH/USDT:USDT"])
            # simulate the starved-open case: a tab left with tf unset, snap overdue
            for t in pool._tabs.values():
                t["tf"], t["last_snap"] = "?", 0.0
            rep = pool.refresh()
        self.assertTrue(rep["snapped"])                 # mirror keeps moving between cycles
        self.assertTrue(rep["healed"])                  # tf='?' repaired to primary
        self.assertTrue(all(t["tf"] == "5m" for t in pool._tabs.values()))

    def test_refresh_yields_to_operator_login(self):
        from trading.broker_sense import tab_pool
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        with mock.patch.dict(os.environ, {"UI_TAB_OPEN_PER_CALL": "1", "UI_TAB_SNAP_S": "0"}):
            pool.ensure(["BTC/USDT:USDT"])
        with mock.patch("trading.broker_sense.sessions.login_in_progress",
                        return_value=True):
            rep = pool.refresh()
        self.assertEqual(rep["snapped"], [])            # never touches the browser mid-login

    def test_kill_switch_and_login_yield(self):
        from trading.broker_sense import tab_pool
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        with mock.patch.dict(os.environ, {"UI_TAB_POOL": "0"}):
            self.assertIn("disabled (UI_TAB_POOL=0)",
                          pool.ensure(["BTC/USDT:USDT"])["errors"])
        with mock.patch("trading.broker_sense.sessions.login_in_progress",
                        return_value=True):
            rep = pool.ensure(["BTC/USDT:USDT"])
            self.assertIn("yielded to operator login", rep["errors"])
            self.assertEqual(pool._tabs, {})


class UpstoxFeedTest(_Base):
    def _pb(self):
        from trading.broker_sense import upstox_feed
        mods = upstox_feed._pb_modules()
        self.assertTrue(mods, "vendored upstox pb2 modules missing")
        return mods[0]

    def test_decode_full_feed(self):
        from trading.broker_sense import upstox_feed, ui_data, ui_market
        pb = self._pb()
        fr = pb.FeedResponse()
        feed = fr.feeds["NSE_EQ|INE002A01018"]
        ff = feed.fullFeed.marketFF
        ff.ltpc.ltp, ff.ltpc.cp = 2500.5, 2450.0
        q = ff.marketLevel.bidAskQuote.add()
        q.bidQ, q.bidP, q.askQ, q.askP = 100, 2500.0, 50, 2501.0
        bar = ff.marketOHLC.ohlc.add()
        bar.interval, bar.ts = "I1", int(time.time() * 1000)
        bar.open, bar.high, bar.low, bar.close, bar.vol = 2490, 2505, 2489, 2500.5, 999
        ff.oi = 12345.0
        raw = fr.SerializeToString()
        n = upstox_feed.decode_frame("upstox", "wss://market-data.upstox.com/feeder", raw)
        self.assertGreaterEqual(n, 4)
        self.assertIsNotNone(ui_market.ticker("NSE_EQ|INE002A01018"))
        self.assertIsNotNone(ui_market.book("NSE_EQ|INE002A01018"))
        self.assertIsNotNone(ui_market.open_interest("NSE_EQ|INE002A01018"))
        self.assertIn(("NSE_EQ|INE002A01018", "1m"), ui_data._STORE)

    def test_garbage_frame_is_honest_zero(self):
        from trading.broker_sense import upstox_feed
        self.assertEqual(upstox_feed.decode_frame("upstox", "wss://x", b"\x00\x01garbage"), 0)
        self.assertTrue(upstox_feed.matches(
            "wss://market-data.upstox.com/market-data-feeder/v2/feeds"))
        self.assertFalse(upstox_feed.matches("wss://stream.binance.com/ws"))


class GateTest(_Base):
    def test_fast_candles_prefers_door(self):
        from trading.broker_sense import fast_candles, ui_data
        n = 30
        t0 = int((time.time() - n * 300) * 1000)
        rows = [[t0 + i * 300_000, 100.0, 101.0, 99.0, 100.5, 10.0] for i in range(n)]
        ui_data.feed_capture(
            "binance", "https://b/fapi/v1/klines?symbol=BTCUSDT&interval=5m", rows)
        got = fast_candles._ohlcv_fast("BTC/USDT:USDT", "crypto", "5m")
        self.assertEqual(len(got), n)                       # served from the door, no API

    def test_fast_candles_ui_only_never_ccxt(self):
        from trading.broker_sense import fast_candles
        os.environ["UI_ONLY_DATA"] = "1"
        with mock.patch("trading.crypto.exchange_pool.get_pool",
                        side_effect=AssertionError("API leak")), \
             mock.patch("trading.broker_sense.app_school._ccxt_exchange",
                        side_effect=AssertionError("API leak")):
            self.assertIsNone(fast_candles._ohlcv_fast("NOCAP/USDT:USDT", "crypto", "5m"))

    def test_top_of_book_serves_captured_depth(self):
        from trading.broker_sense import data_failsafe, ui_market
        ui_market.feed_capture("binance", "orderbook",
                               "https://b/fapi/v1/depth?symbol=BTCUSDT",
                               {"bids": [["50000", "1"]], "asks": [["50001", "1"]]})
        bk = data_failsafe.top_of_book("BTC/USDT:USDT", "crypto")
        self.assertEqual(bk["source"], "ui:capture")
        self.assertAlmostEqual(bk["bid"], 50000.0)

    def test_orderflow_prefers_captures_and_ui_only_skips_rest(self):
        from trading.broker_sense import binance_orderflow as of
        from trading.broker_sense import ui_market
        of.clear_cache()
        ui_market.feed_capture("binance", "mark_price", "wss://f",
                               {"e": "markPriceUpdate", "s": "BTCUSDT", "p": "50000",
                                "r": "0.0005", "T": int(time.time() * 1000) + 3_600_000})
        ui_market.feed_capture(
            "binance", "taker_volume", "https://f/futures/data/taker-long-short-ratio",
            [{"symbol": "BTCUSDT", "buySellRatio": "1.1"}])
        os.environ["UI_ONLY_DATA"] = "1"
        with mock.patch.object(of, "_get_json",
                               side_effect=AssertionError("REST leak in UI-only")):
            f = of.features("BTC/USDT:USDT")
        self.assertAlmostEqual(f["funding_rate"], 0.0005)
        self.assertAlmostEqual(f["taker_buy_sell_ratio"], 1.1)
        self.assertEqual(f["source"], "ui:capture")


if __name__ == "__main__":
    unittest.main()


class StealthTest(unittest.TestCase):
    """THE MOTTO anti-CAPTCHA (2026-07-12): the browser must not fingerprint as a VM/bot,
    or Binance throws a 'Security Verification' puzzle that stalls the web-nav data path."""

    def test_script_patches_the_known_tells(self):
        from trading.broker_sense import stealth
        s = stealth._script()
        for needle in ("navigator,'webdriver'", "window.chrome", "navigator,'plugins'",
                       "37445", "37446", "navigator,'languages'"):
            self.assertIn(needle, s, needle)

    def test_apply_injects_and_respects_kill_switch(self):
        from trading.broker_sense import stealth
        calls = []

        class _Ctx:
            def add_init_script(self, s): calls.append(s)
        with mock.patch.dict(os.environ, {"BROKER_STEALTH": "1"}):
            self.assertTrue(stealth.apply(_Ctx()))
            self.assertEqual(len(calls), 1)
        with mock.patch.dict(os.environ, {"BROKER_STEALTH": "0"}):
            self.assertFalse(stealth.apply(_Ctx()))
            self.assertEqual(len(calls), 1)                 # unchanged — disabled

    def test_context_fp_regionalizes_by_broker(self):
        from trading.broker_sense import sessions
        with mock.patch.dict(os.environ, {"BROKER_STEALTH": "1"}):
            fp = sessions._context_fp("binance")
            self.assertEqual(fp.get("timezone_id"), "Asia/Kolkata")
            self.assertEqual(fp.get("locale"), "en-IN")
        with mock.patch.dict(os.environ, {"BROKER_STEALTH": "0"}):
            self.assertEqual(sessions._context_fp("binance"), {})


class StreamPumpTest(_Base):
    def test_pump_processes_open_tabs_and_skips_dead(self):
        from trading.broker_sense import tab_pool

        class _Pg:
            def __init__(self, closed=False): self._c = closed; self.waited = 0
            def is_closed(self): return self._c
            def wait_for_timeout(self, ms): self.waited += ms
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        pool._tabs = {"BTCUSDT": {"page": _Pg(), "tf": "5m", "opened_ts": 0.0,
                                  "last_snap": 0.0},
                      "ETHUSDT": {"page": _Pg(closed=True), "tf": "5m",
                                  "opened_ts": 0.0, "last_snap": 0.0}}
        with mock.patch.dict(os.environ, {"UI_TAB_POOL": "1"}):
            self.assertEqual(pool.pump(), 1)          # live tab pumped, dead one skipped
        self.assertGreater(pool._tabs["BTCUSDT"]["page"].waited, 0)

    def test_pump_yields_to_operator_login(self):
        from trading.broker_sense import tab_pool

        class _Pg:
            def is_closed(self): return False
            def wait_for_timeout(self, ms): pass
        pool = tab_pool.TabPool(_FakeSessions(), "binance")
        pool._tabs = {"BTCUSDT": {"page": _Pg(), "tf": "5m", "opened_ts": 0.0,
                                  "last_snap": 0.0}}
        with mock.patch("trading.broker_sense.sessions.login_in_progress",
                        return_value=True):
            self.assertEqual(pool.pump(), 0)          # never touches browser mid-login


class RollingTabTest(_Base):
    def test_rolling_window_sweeps_universe_keeps_pins(self):
        from trading.broker_sense import tab_pool

        class _Pg:
            def __init__(s): s._c = False
            def is_closed(s): return s._c
            def close(s): s._c = True
            def locator(s, x):
                class L:
                    def all(s2): return []
                return L()
            def wait_for_timeout(s, ms): pass
            def screenshot(s, **k): return b"\xff\xd8\xff"

        class _S:
            def page(s, b, u=None, timeout_ms=0): return _Pg()
        pool = tab_pool.TabPool(_S(), "binance")
        universe = [f"C{i}/USDT:USDT" for i in range(12)]
        with mock.patch.dict(os.environ, {"UI_TAB_ROLLING": "1", "UI_TAB_POOL_N": "4",
                                          "UI_TAB_OPEN_PER_CALL": "4", "UI_TAB_SNAP_S": "0"}):
            seen = set()
            for _ in range(6):
                pool.ensure(universe, pins={"C0/USDT:USDT"})
                seen |= set(pool._tabs)
            self.assertEqual(len(seen), 12)                 # every symbol covered over the sweep
            self.assertIn("C0USDT", pool._tabs)             # pinned open trade never rolls off
            # roll() advances the window using the remembered shortlist
            r = pool.roll()
            self.assertTrue(r.get("rolled"))
