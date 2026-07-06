"""Tests for the network-interception recorder + endpoint registry (offline, no browser).

Covers: URL patterning, data-kind classification (URL + body-shape), registry record/find/
persistence, the live-body cache with TTL staleness, and a fake Playwright response driven
through the recorder. STATE_DIR-isolated — never touches the live registry.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from unittest import mock

import trading.state as state
from trading.broker_sense import interception as ix


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


class TestUrlPattern(unittest.TestCase):
    def test_drops_query_and_templates_ids(self):
        self.assertEqual(ix._url_pattern("https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT"),
                         "fapi.binance.com/fapi/v1/depth")
        self.assertEqual(ix._url_pattern("https://x.com/api/order/123456/status"),
                         "x.com/api/order/{v}/status")

    def test_two_symbols_same_pattern(self):
        a = ix._url_pattern("https://api.x.com/quote?symbol=A")
        b = ix._url_pattern("https://api.x.com/quote?symbol=B")
        self.assertEqual(a, b)


class TestClassify(unittest.TestCase):
    def test_url_keywords(self):
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/depth?symbol=BTC"), "orderbook")
        self.assertEqual(ix.classify("https://x/api/klines?interval=5m"), "candles")
        self.assertEqual(ix.classify("https://nse/api/option-chain-v3?symbol=NIFTY"), "option_chain")
        self.assertEqual(ix.classify("https://fapi/fapi/v1/premiumIndex"), "funding")
        self.assertEqual(ix.classify("https://x/api/topGainers"), "movers")

    def test_body_shape_fallback(self):
        self.assertEqual(ix.classify("https://x/opaque", {"bids": [], "asks": []}), "orderbook")
        self.assertEqual(ix.classify("https://x/opaque", {"ltp": 100}), "ticker")
        self.assertEqual(ix.classify("https://x/opaque", [[1, 2, 3], [4, 5, 6]]), "candles")

    def test_unknown_stays_unknown(self):
        self.assertEqual(ix.classify("https://x/whatever", {"foo": 1}), "unknown")

    def test_new_per_symbol_kinds(self):
        # per-symbol decision kinds added 2026-07-06 for the indicator-fusion engine
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/aggTrades?symbol=BTC"),
                         "recent_trades")
        self.assertEqual(ix.classify("https://api.binance.com/api/v3/trades?symbol=BTC"),
                         "recent_trades")
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/markPriceKlines?s=BTC"),
                         "mark_price")
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/indexPriceKlines?pair=BTC"),
                         "index_price")
        self.assertEqual(ix.classify("https://x/bapi/futures/v1/public/future/data/basis?pair=BTC"),
                         "basis")
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/exchangeInfo"), "symbol_info")
        # ordering guards: klines/depth/funding must NOT be stolen by the new rules
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/klines?symbol=BTC"), "candles")
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/depth?symbol=BTC"), "orderbook")
        self.assertEqual(ix.classify("https://fapi.binance.com/fapi/v1/premiumIndex"), "funding")

    def test_new_kinds_body_shape(self):
        self.assertEqual(ix.classify("https://x/opaque", [{"price": "1", "qty": "2", "time": 9}]),
                         "recent_trades")
        self.assertEqual(ix.classify("https://x/opaque", [{"p": "1", "q": "2", "T": 9, "m": True}]),
                         "recent_trades")
        self.assertEqual(ix.classify("https://x/opaque", {"symbols": [1, 2]}), "symbol_info")
        self.assertEqual(ix.classify("https://x/opaque", {"markPrice": "1"}), "mark_price")


class TestRegistry(_IsolatedState):
    def test_record_find_and_persist(self):
        reg = ix.EndpointRegistry()
        reg.record("binance", "https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT",
                   content_type="application/json", body={"bids": [[1, 2]], "asks": [[3, 4]]})
        reg.record("binance", "https://fapi.binance.com/fapi/v1/depth?symbol=ETHUSDT",
                   body={"bids": [], "asks": []})
        pats = reg.find("binance", "orderbook")
        self.assertEqual(len(pats), 1)                       # both calls collapse to one pattern
        self.assertEqual(reg.known("binance")[pats[0]]["n_seen"], 2)
        reg.save()
        reg2 = ix.EndpointRegistry()                         # reload from disk
        self.assertEqual(reg2.find("binance", "orderbook"), pats)

    def test_unknown_then_upgraded(self):
        reg = ix.EndpointRegistry()
        reg.record("x", "https://x/opaque", body={"foo": 1})       # unknown
        reg.record("x", "https://x/opaque", body={"bids": [], "asks": []})  # now orderbook
        self.assertEqual(reg.find("x", "orderbook"), ["x/opaque"])


class _FakeRequest:
    def __init__(self, method="GET"):
        self.method = method


class _FakeResponse:
    def __init__(self, url, body, ct="application/json", length=None):
        self.url = url
        self._body = body
        self.headers = {"content-type": ct}
        if length is not None:
            self.headers["content-length"] = str(length)
        self.request = _FakeRequest()

    def body(self):
        if self._body is None:
            raise ValueError("no body")
        import json
        return json.dumps(self._body).encode()

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class TestRecorder(_IsolatedState):
    def test_capture_records_and_caches(self):
        rec = ix.NetworkRecorder()
        rec._handle(_FakeResponse("https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT",
                                  {"bids": [[100, 1]], "asks": [[101, 1]]}), "binance")
        self.assertEqual(rec.captured, 1)
        body = rec.latest("binance", "orderbook")
        self.assertEqual(body["bids"], [[100, 1]])
        self.assertIn("binance", rec.registry.status())

    def test_non_json_ignored(self):
        rec = ix.NetworkRecorder()
        rec._handle(_FakeResponse("https://x.com/app.js", None, ct="application/javascript"),
                    "binance")
        self.assertEqual(rec.captured, 0)

    def test_cache_ttl_staleness(self):
        rec = ix.NetworkRecorder()
        rec._handle(_FakeResponse("https://x/api/ticker24hr", {"ltp": 5}), "binance")
        self.assertIsNotNone(rec.latest("binance", "ticker", max_age_s=100))
        # force the cached ts into the past → stale
        rec._cache[("binance", "ticker")]["ts"] = time.time() - 500
        self.assertIsNone(rec.latest("binance", "ticker", max_age_s=90))

    def test_oversize_body_skipped_even_without_content_length(self):
        rec = ix.NetworkRecorder()
        with mock.patch.object(ix, "_MAX_BODY_BYTES", 10):     # tiny cap → this body is "huge"
            rec._handle(_FakeResponse("https://x/api/depth",
                                      {"bids": [[1, 2], [3, 4]], "asks": [[5, 6]]}), "binance")
        self.assertEqual(rec.captured, 1)                       # endpoint still recorded…
        self.assertIsNone(rec.latest("binance", "orderbook"))  # …but oversized body not cached

    def test_attach_is_safe_without_real_page(self):
        rec = ix.NetworkRecorder()

        class _Pg:
            def __init__(self):
                self.handlers = {}          # attach() registers BOTH "response" and "websocket"

            def on(self, event, fn):
                self.handlers[event] = fn

        pg = _Pg()
        rec.attach(pg, "binance")
        self.assertIn("response", pg.handlers)
        self.assertIn("websocket", pg.handlers)      # ws capture hooked too (liquidation feeds)
        # firing the response handler with a fake response should record without raising
        pg.handlers["response"](_FakeResponse("https://x/api/depth", {"bids": [], "asks": []}))
        self.assertEqual(rec.captured, 1)


if __name__ == "__main__":
    unittest.main()
