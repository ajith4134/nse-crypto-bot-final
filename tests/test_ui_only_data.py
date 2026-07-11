"""UI-only data mode tests (owner 2026-07-07) — capture parsing + honest misses."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


def _klines(n=30, t0=None, tf_ms=300_000, price=100.0):
    t0 = t0 or int((time.time() - n * tf_ms / 1000) * 1000)
    return [[t0 + i * tf_ms, price + i * 0.1, price + i * 0.1 + 0.5,
             price + i * 0.1 - 0.5, price + i * 0.1 + 0.2, 10.0] for i in range(n)]


class UiOnlyDataTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        from trading.broker_sense import ui_data
        ui_data._STORE.clear()
        ui_data._HITS.update({"served": 0, "missed": 0, "fed": 0})

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()
        os.environ.pop("UI_ONLY_DATA", None)

    def test_feed_capture_binance_klines(self):
        from trading.broker_sense import ui_data
        url = "https://www.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=500"
        self.assertTrue(ui_data.feed_capture("binance", url, _klines()))
        rows = ui_data.ui_ohlcv("BTC/USDT:USDT", timeframe="5m")
        self.assertIsNotNone(rows)                    # slash/colon spelling resolves
        self.assertEqual(len(rows[0]), 6)

    def test_feed_capture_tv_dict(self):
        from trading.broker_sense import ui_data
        n = 20
        t0 = int(time.time()) - n * 60
        body = {"t": [t0 + i * 60 for i in range(n)],
                "o": [100.0] * n, "h": [101.0] * n, "l": [99.0] * n,
                "c": [100.5] * n, "v": [5.0] * n, "s": "ok"}
        url = "https://upstox.example/history?instrument_key=NSE_EQ|RELIANCE&resolution=1"
        self.assertTrue(ui_data.feed_capture("upstox", url, body))
        self.assertIsNotNone(ui_data.ui_ohlcv("NSE_EQ|RELIANCE", timeframe="1m"))

    def test_rejects_garbage(self):
        from trading.broker_sense import ui_data
        url = "https://x/klines?symbol=BAD&interval=5m"
        rows = _klines()
        rows[3][0] = rows[10][0]                      # non-monotonic
        self.assertFalse(ui_data.feed_capture("binance", url, rows))
        self.assertFalse(ui_data.feed_capture("binance", url, {"nope": 1}))

    def test_stale_capture_is_honest_miss(self):
        from trading.broker_sense import ui_data
        url = "https://x/klines?symbol=OLDUSDT&interval=1m"
        old = _klines(tf_ms=60_000)
        self.assertTrue(ui_data.feed_capture("binance", url, old))
        ui_data._STORE[("OLDUSDT", "1m")]["ts"] = time.time() - 999
        self.assertIsNone(ui_data.ui_ohlcv("OLDUSDT", timeframe="1m"))

    def test_fusion_fetch_ui_only_records_failure(self):
        from trading import state
        os.environ["UI_ONLY_DATA"] = "1"
        from trading.broker_sense.indicator_fusion import _fetch
        self.assertIsNone(_fetch("NEVERSEEN/USDT:USDT", "crypto", "5m"))
        d = state.load_json("evidence_lane.json", {})
        self.assertTrue(any("NEVERSEEN" in f["detail"] for f in d.get("failures", [])))

    def test_failsafe_ui_only_no_api(self):
        from trading.broker_sense import data_failsafe, ui_data
        os.environ["UI_ONLY_DATA"] = "1"
        self.assertIsNone(data_failsafe.top_of_book("BTC/USDT:USDT", "crypto"))
        url = "https://www.binance.com/fapi/v1/klines?symbol=ETHUSDT&interval=1m"
        ui_data.feed_capture("binance", url, _klines(tf_ms=60_000))
        q = data_failsafe.quote("ETH/USDT:USDT", "crypto")
        self.assertEqual(q["source"], "ui:capture")
        self.assertGreater(q["last"], 0)

    def test_coverage_meter(self):
        from trading.broker_sense import ui_data
        url = "https://www.binance.com/fapi/v1/klines?symbol=SOLUSDT&interval=5m"
        ui_data.feed_capture("binance", url, _klines())
        cov = ui_data.coverage()
        self.assertEqual(cov["symbols"], 1)
        self.assertEqual(cov["fed"], 1)


if __name__ == "__main__":
    unittest.main()


class AutoFlipGovernorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        from trading.broker_sense import ui_data
        ui_data._STORE.clear()
        ui_data._HITS.update({"served": 0, "missed": 0, "fed": 0})
        os.environ.pop("UI_ONLY_DATA", None)

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()
        os.environ.pop("UI_ONLY_DATA", None)

    def test_no_flip_when_cold(self):
        from trading.broker_sense import ui_data
        r = ui_data.maybe_auto_flip(["BTC/USDT:USDT"])
        self.assertFalse(r["enabled"])
        self.assertFalse(ui_data.enabled())

    def test_flips_durably_when_warm(self):
        from trading import state
        from trading.broker_sense import ui_data
        syms = [f"C{i}USDT" for i in range(10)]
        for s in syms:
            url = f"https://x/klines?symbol={s}&interval=5m"
            self.assertTrue(ui_data.feed_capture("binance", url, _klines()))
            ui_data.ui_ohlcv(s, timeframe="5m")          # build served hit-rate
        r = ui_data.maybe_auto_flip(syms)
        self.assertTrue(r["enabled"])
        # durable: enabled() true WITHOUT the env var; idempotent on re-call
        self.assertTrue(ui_data.enabled())
        self.assertTrue(ui_data.maybe_auto_flip(syms)["already"])
        self.assertTrue(state.load_json("ui_only_mode.json", {}).get("enabled"))
        # recorded through the surface rails
        led = state.load_json("rule_versions.json", [])
        self.assertTrue(any(e["knob"] == "data.ui_only.mode" for e in led))


class TestCrawlUrlNormalization(unittest.TestCase):
    """Pickers surface regional-book symbols (ADA/RUB) — the crawler must study the
    engine-tradeable USDT book or its captures are useless for the shortlist."""

    def test_dead_quote_books_rewrite_to_usdt(self):
        from trading.broker_sense.ui_crawl import _binance_url
        self.assertIn("/trade/ALGOUSDT?", _binance_url("ALGO/RUB"))
        self.assertIn("/trade/ADAUSDT?", _binance_url("ADARUB"))
        self.assertIn("/trade/BSWUSDT?", _binance_url("BSW/TRY"))

    def test_usdt_and_futures_untouched(self):
        from trading.broker_sense.ui_crawl import _binance_url
        self.assertIn("/trade/ETHUSDT?", _binance_url("ETH/USDT"))
        self.assertIn("/futures/ETHUSDT", _binance_url("ETH/USDT:USDT"))
