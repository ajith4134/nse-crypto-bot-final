"""tests/test_kite_stream.py — Zerodha NSE in-RAM mirror, fed via OpenAlgo's unified WS.

Offline: feeds synthetic OpenAlgo market-data envelopes into _on_tick (the pure handler) — no
socket, no openalgo SDK, no network — and asserts the RAM read API (ticker, book, candles,
nse_rows, staleness, ohlcv adapter) plus the graceful no-op when the OpenAlgo key/SDK is absent.
"""
import json
import os
import time
import unittest
from collections import deque

from trading.broker_sense.kite_stream import KiteZerodhaMirror, _raw_feed_class


def _env(symbol, ltp, *, close=None, vol=0.0, oi=0.0, bid=None, ask=None, mode=3, exchange="NSE",
         vwap=None, buy_qty=None, sell_qty=None):
    """One OpenAlgo `market_data` envelope — the mode-3 "full" frame the server really sends
    (ltp+ohlc+volume+oi+vwap+depth together), as captured live off :8765 on 2026-07-16."""
    data = {"ltp": ltp, "open": ltp - 5, "high": ltp + 5, "low": ltp - 8,
            "close": close if close is not None else ltp - 2, "volume": vol, "oi": oi}
    for k, v in (("average_price", vwap), ("total_buy_quantity", buy_qty),
                 ("total_sell_quantity", sell_qty)):
        if v is not None:
            data[k] = v
    depth = {}
    if bid is not None:
        depth["buy"] = [{"price": bid, "quantity": 100, "orders": 3}]
    if ask is not None:
        depth["sell"] = [{"price": ask, "quantity": 120, "orders": 4}]
    if depth:
        data["depth"] = depth
    return {"type": "market_data", "symbol": symbol, "exchange": exchange, "mode": mode, "data": data}


class TestNSEMirrorTicks(unittest.TestCase):
    def setUp(self):
        self.m = KiteZerodhaMirror()

    def test_tick_populates_ticker_and_book(self):
        self.m._on_tick(_env("RELIANCE", 2500.0, close=2480.0, vol=1000.0, bid=2499.0, ask=2501.0))
        t = self.m.ticker("RELIANCE")
        self.assertIsNotNone(t)
        self.assertEqual(t["last"], 2500.0)
        self.assertEqual(t["close"], 2480.0)
        self.assertEqual(t["volume"], 1000.0)
        self.assertAlmostEqual(t["pct_change"], round((2500 - 2480) / 2480 * 100, 4), places=3)
        b = self.m.book("RELIANCE")
        self.assertEqual(b["bids"][0], [2499.0, 100.0])
        self.assertEqual(b["asks"][0], [2501.0, 120.0])
        self.assertIsNotNone(self.m.ticker("nse:reliance"))     # case/prefix-insensitive key

    def test_control_frames_ignored(self):
        for ctrl in ({"type": "auth", "status": "success", "broker": "zerodha"},
                     {"type": "subscribe", "status": "success"},
                     {"type": "heartbeat"}):
            self.m._on_tick(ctrl)
        self.assertEqual(self.m.status()["symbols_ticker"], 0)

    def test_candles_roll_and_volume_delta(self):
        self.m._on_tick(_env("RELIANCE", 2500.0, vol=1000.0))
        self.m._on_tick(_env("RELIANCE", 2510.0, vol=1075.0))
        c = self.m.candles("RELIANCE", 60, 5)
        self.assertTrue(c)
        bar = c[-1]
        self.assertEqual(len(bar), 6)                     # [ts,o,h,l,c,v]
        self.assertEqual(bar[1], 2500.0)                  # open = first tick
        self.assertEqual(bar[4], 2510.0)                  # close = last tick
        self.assertEqual(bar[2], 2510.0)                  # high
        self.assertEqual(bar[5], 75.0)                    # volume delta 1075-1000

    def test_partial_frame_merges_not_wipes(self):
        # a full frame then an ltp-only frame (no ohlc/volume) must keep the prior close/volume
        self.m._on_tick(_env("RELIANCE", 2500.0, close=2480.0, vol=1000.0))
        self.m._on_tick({"type": "market_data", "symbol": "RELIANCE", "exchange": "NSE",
                         "mode": 1, "data": {"ltp": 2505.0}})
        t = self.m.ticker("RELIANCE")
        self.assertEqual(t["last"], 2505.0)
        self.assertEqual(t["close"], 2480.0)              # preserved
        self.assertEqual(t["volume"], 1000.0)             # preserved

    def test_nse_rows_shape(self):
        self.m._on_tick(_env("RELIANCE", 2500.0, close=2480.0, vol=5000.0))
        self.m._on_tick(_env("INFY", 1500.0, close=1490.0, vol=3000.0))
        rows = {r["symbol"]: r for r in self.m.nse_rows()}
        self.assertEqual(set(rows), {"RELIANCE", "INFY"})
        self.assertEqual(rows["RELIANCE"]["ltp"], 2500.0)
        self.assertEqual(rows["RELIANCE"]["prev_close"], 2480.0)
        self.assertEqual(rows["RELIANCE"]["volume"], 5000.0)
        self.assertNotIn("INFY", {r["symbol"] for r in self.m.nse_rows(min_volume=4000.0)})

    def test_junk_never_raises(self):
        for junk in (None, {}, {"type": "market_data"}, {"type": "market_data", "data": None},
                     {"type": "market_data", "symbol": "X", "data": "nope"}):
            self.m._on_tick(junk)
        self.assertEqual(self.m.status()["symbols_ticker"], 0)

    def test_staleness_is_honest(self):
        self.m._on_tick(_env("RELIANCE", 2500.0))
        self.assertFalse(self.m.is_stale("RELIANCE"))
        self.m._ltp["RELIANCE"]["ts"] = time.time() - 999
        self.assertTrue(self.m.is_stale("RELIANCE"))

    def test_status_shape(self):
        st = self.m.status()
        for k in ("enabled", "running", "connected", "have_creds", "feed", "symbols_ticker",
                  "symbols_subscribed", "stale", "candle_tfs"):
            self.assertIn(k, st)
        self.assertEqual(st["feed"], "openalgo-ws")


class _FakeSDK:
    """Stand-in for the openalgo SDK's FeedAPI — records what the subclass delegates to it."""

    def __init__(self):
        self.delegated = []

    def _process_message(self, message_str):
        self.delegated.append(message_str)


class TestRawFeedOverride(unittest.TestCase):
    """_raw_feed_class bypasses the SDK's per-mode trimming (the volume-freeze root cause).

    Live 2026-07-16: openalgo 2.0.2 feed.py rebuilds a dict per subscription type — the mode-3
    branch keeps only {ltp, timestamp, depth}, dropping the volume/OHLC/OI the server DID send.
    These tests pin that we read the envelope raw and still delegate everything else to the SDK.
    """

    def setUp(self):
        self.cls = _raw_feed_class(_FakeSDK)

    def test_market_data_reaches_sink_untrimmed(self):
        f = self.cls()
        got = []
        f._sink = got.append
        f._process_message(json.dumps(_env("RELIANCE", 2500.0, vol=1000.0, oi=42.0,
                                           bid=2499.0, ask=2501.0, vwap=2495.5)))
        self.assertEqual(len(got), 1)
        d = got[0]["data"]
        for field in ("volume", "oi", "open", "high", "low", "close", "average_price", "depth"):
            self.assertIn(field, d, f"{field} must survive — the SDK's mode-3 branch drops it")
        self.assertEqual(d["volume"], 1000.0)
        self.assertEqual(f.delegated, [])          # never handed to the trimming base

    def test_control_frames_still_delegate_to_sdk(self):
        """auth/subscribe acks must reach the SDK — that's what drives reconnect + replay."""
        f = self.cls()
        f._sink = lambda m: self.fail("control frame must not reach the tick sink")
        for ctrl in ({"type": "auth", "status": "success"}, {"type": "subscribe", "status": "ok"}):
            f._process_message(json.dumps(ctrl))
        self.assertEqual(len(f.delegated), 2)

    def test_bad_json_delegates_and_never_raises(self):
        f = self.cls()
        f._sink = lambda m: self.fail("junk must not reach the tick sink")
        f._process_message("not-json{{")
        self.assertEqual(len(f.delegated), 1)

    def test_market_data_without_sink_never_raises(self):
        self.cls()._process_message(json.dumps(_env("RELIANCE", 2500.0)))


class TestNSEFullFrameExtras(unittest.TestCase):
    """The mode-3 frame's extras (vwap + total resting buy/sell qty) land in RAM."""

    def test_extras_captured_and_merged(self):
        m = KiteZerodhaMirror()
        m._on_tick(_env("RELIANCE", 2500.0, vol=1000.0, vwap=2495.5,
                        buy_qty=638072.0, sell_qty=1080403.0))
        t = m.ticker("RELIANCE")
        self.assertEqual((t["vwap"], t["buy_qty"], t["sell_qty"]), (2495.5, 638072.0, 1080403.0))
        m._on_tick({"type": "market_data", "symbol": "RELIANCE", "exchange": "NSE",
                    "mode": 1, "data": {"ltp": 2505.0}})          # partial frame
        t = m.ticker("RELIANCE")
        self.assertEqual(t["vwap"], 2495.5)                        # preserved, not wiped
        self.assertEqual(t["buy_qty"], 638072.0)

    def test_candle_volume_accumulates_within_a_bar(self):
        """Regression: the old "both"-mode subscribe froze cumulative volume at its subscribe-time
        snapshot, so every bar's delta stayed 0.0 — while looking populated. Volume must MOVE."""
        m = KiteZerodhaMirror()
        for cum in (1000.0, 1075.0, 1200.0):
            m._on_tick(_env("RELIANCE", 2500.0, vol=cum))
        bar = m.candles("RELIANCE", 60, 5)[-1]
        self.assertEqual(bar[5], 200.0)                            # 1200 - 1000, not 0.0
        self.assertGreater(bar[5], 0.0)


class TestNSEMirrorGracefulNoop(unittest.TestCase):
    """No openalgo SDK / no OPENALGO_API_KEY → every module-level read is a safe no-op."""

    def setUp(self):
        import trading.broker_sense.kite_stream as ks
        ks._MIRROR = None
        self._ks = ks
        self._saved = {k: os.environ.get(k) for k in ("OPENALGO_API_KEY", "KITE_STREAM")}
        os.environ.pop("OPENALGO_API_KEY", None)
        os.environ["KITE_STREAM"] = "1"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._ks._MIRROR = None

    def test_reads_return_empty_without_key(self):
        ks = self._ks
        self.assertIsNone(ks.ohlcv("RELIANCE", "5m"))
        self.assertIsNone(ks.ticker("RELIANCE"))
        self.assertIsNone(ks.book("RELIANCE"))
        self.assertEqual(ks.nse_rows(), [])
        st = ks.status()
        self.assertFalse(st["have_creds"])
        self.assertFalse(st["connected"])
        ks.get_kite_mirror().start()                      # no-op, never raises, without a key
        self.assertFalse(ks.get_kite_mirror()._running)

    def test_kill_switch(self):
        ks = self._ks
        os.environ["KITE_STREAM"] = "0"
        self.assertFalse(ks.enabled())
        self.assertIsNone(ks.ticker("RELIANCE"))
        self.assertEqual(ks.nse_rows(), [])


class _FakeHistOA:
    """Stand-in OpenAlgoClient.history — records calls, returns synthetic NSE bars."""
    calls = []

    def __init__(self, *a, **k):
        pass

    def history(self, symbol, exchange="NSE", *, interval, start_date, end_date):
        _FakeHistOA.calls.append((symbol, interval))
        base = 1_700_000_000
        step = {"1m": 60, "5m": 300, "15m": 900}[interval]
        return {"data": [{"timestamp": base + i * step, "open": 100.0 + i, "high": 101.0 + i,
                          "low": 99.0 + i, "close": 100.5 + i, "volume": 10.0 * i}
                         for i in range(40)]}


class TestNSEBackfill(unittest.TestCase):
    """One-shot history seed so the funnel can decide on a COLD mirror.

    Root cause it fixes (live 2026-07-16): with no seed, ohlcv() serves a TF only at >=15 rolled
    bars — 15/75/225 min for 1m/5m/15m — and funnel._vote needs >=2 AGREEING TFs, so every NSE
    symbol voted neutral and nothing opened (look.read=40, cands=[], non_neutral=0).
    """

    def setUp(self):
        import trading.broker_sense.kite_stream as ks
        import trading.openalgo_client as oac
        self.ks, self.oac = ks, oac
        ks._MIRROR = None
        _FakeHistOA.calls = []
        self._saved_cls = oac.OpenAlgoClient
        oac.OpenAlgoClient = _FakeHistOA
        self._saved = {k: os.environ.get(k) for k in ("OPENALGO_API_KEY", "KITE_STREAM",
                                                      "KITE_BACKFILL", "KITE_BACKFILL_SLEEP_S")}
        os.environ.update({"OPENALGO_API_KEY": "test-key", "KITE_STREAM": "1",
                           "KITE_BACKFILL_SLEEP_S": "0"})

    def tearDown(self):
        self.oac.OpenAlgoClient = self._saved_cls
        self.ks._MIRROR = None
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_backfill_seeds_every_tf_so_reads_work_cold(self):
        m = self.ks.get_kite_mirror()
        m.subscribe_symbols(["RELIANCE"])
        m._running = True
        seeded = m._backfill_history()
        self.assertEqual(seeded, 3)                        # 1 symbol × 3 TFs
        self.assertTrue(m.status()["backfilled"])
        self.assertEqual({iv for _, iv in _FakeHistOA.calls}, {"1m", "5m", "15m"})
        rows = self.ks.ohlcv("RELIANCE", "1m", 220)        # was None until 15 live minutes
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 40)
        self.assertEqual(len(rows[0]), 6)                  # ccxt shape [ms,o,h,l,c,v]

    def test_backfill_never_clobbers_the_live_bar(self):
        """Ticks already rolled must survive — the seed only fills bars OLDER than the live one."""
        m = self.ks.get_kite_mirror()
        m.subscribe_symbols(["RELIANCE"])
        m._running = True
        m._on_tick(_env("RELIANCE", 2500.0, vol=1000.0))   # live bar at ~now
        live = m.candles("RELIANCE", 60, 5)[-1]
        m._backfill_history()
        bars = m.candles("RELIANCE", 60, 999)
        self.assertEqual(bars[-1][:5], live[:5])           # live bar still last, untouched
        self.assertGreater(len(bars), 1)                   # history seeded behind it
        self.assertTrue(all(b[0] < bars[-1][0] for b in bars[:-1]))   # strictly older, ordered

    def test_kill_switch_disables_backfill(self):
        self.ks._BACKFILL_ON = False
        try:
            m = self.ks.get_kite_mirror()
            m.subscribe_symbols(["RELIANCE"])
            m._running = True
            self.assertEqual(m._backfill_history(), 0)
            self.assertEqual(_FakeHistOA.calls, [])        # zero REST calls
        finally:
            self.ks._BACKFILL_ON = True

    def test_epoch_parses_every_timestamp_shape(self):
        import datetime
        from trading.broker_sense.kite_stream import _epoch
        self.assertEqual(_epoch(1_700_000_000), 1_700_000_000)
        self.assertEqual(_epoch(1_700_000_000_000), 1_700_000_000)      # ms → s
        dt = datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc)
        self.assertEqual(_epoch(dt), dt.timestamp())                    # datetime/pandas Timestamp
        self.assertEqual(_epoch("2023-11-14T22:13:20+00:00"), dt.timestamp())
        self.assertIsNone(_epoch(None))
        self.assertIsNone(_epoch("not-a-time"))


class TestNSEOHLCVAdapter(unittest.TestCase):
    """kite_stream.ohlcv() serves in-RAM multi-TF candles in ccxt shape (no API)."""

    def _seed(self, m, sym="RELIANCE", tf=60, n=40):
        base = 1_700_000_000
        with m._lock:
            m._candles[sym] = {60: deque(maxlen=240), 300: deque(maxlen=240), 900: deque(maxlen=240)}
            for i in range(n):
                p = 100.0 + i * 0.1
                m._candles[sym][tf].append([base + i * tf, p, p + 0.5, p - 0.5, p + 0.2, 10.0 * i, 0.0])

    def setUp(self):
        import trading.broker_sense.kite_stream as ks
        ks._MIRROR = None
        self.ks = ks
        os.environ["KITE_STREAM"] = "1"

    def tearDown(self):
        self.ks._MIRROR = None

    def test_ohlcv_returns_ccxt_shape(self):
        m = self.ks.get_kite_mirror()
        self._seed(m)
        rows = self.ks.ohlcv("RELIANCE", "1m", 220)
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 40)
        self.assertEqual(len(rows[0]), 6)                 # [ms,o,h,l,c,v]
        self.assertEqual(rows[0][0] % 1000, 0)            # ms epoch
        self.assertEqual(rows[-1][5], 10.0 * 39)          # volume carried through

    def test_ohlcv_misses_fall_back_to_none(self):
        m = self.ks.get_kite_mirror()
        self._seed(m, n=40)
        self.assertIsNone(self.ks.ohlcv("RELIANCE", "1h"))     # TF not aggregated
        self.assertIsNone(self.ks.ohlcv("NOPE", "1m"))         # symbol not in RAM
        self.assertIsNone(self.ks.ohlcv("RELIANCE", "wat"))    # unknown TF string

    def test_ohlcv_cold_bars_none(self):
        m = self.ks.get_kite_mirror()
        self._seed(m, n=5)                                     # <15 bars → not warm enough
        self.assertIsNone(self.ks.ohlcv("RELIANCE", "1m"))


if __name__ == "__main__":
    unittest.main()
