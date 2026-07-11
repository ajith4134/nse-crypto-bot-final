"""tests/test_binance_stream.py — Binance all-market in-RAM mirror.

Offline: feeds synthetic combined-stream frames into _apply_frame (the pure parser) — no socket,
no network — and asserts the RAM read API (funding, ticker, movers, liquidations, staleness).
"""
import time
import unittest

from trading.broker_sense.binance_stream import BinanceUniverseMirror


def _mark_frame(rows):
    return {"stream": "!markPrice@arr", "data": [
        {"e": "markPriceUpdate", "s": s, "p": p, "r": r, "T": t} for (s, p, r, t) in rows]}


def _ticker_frame(rows):
    return {"stream": "!ticker@arr", "data": [
        {"e": "24hrTicker", "s": s, "c": c, "P": P, "h": h, "l": l, "q": q, "n": n}
        for (s, c, P, h, l, q, n) in rows]}


def _liq_frame(sym, side, qty, price, ts_ms):
    return {"stream": "!forceOrder@arr",
            "data": {"e": "forceOrder", "o": {"s": sym, "S": side, "q": qty, "p": price, "T": ts_ms}}}


class TestBinanceMirror(unittest.TestCase):
    def setUp(self):
        self.m = BinanceUniverseMirror()

    def test_markprice_funding_parsed(self):
        self.m._apply_frame(_mark_frame([("BTCUSDT", "64000.0", "0.0001", 1783000000000)]))
        f = self.m.funding("btcusdt")            # case-insensitive read
        self.assertIsNotNone(f)
        self.assertEqual(f["mark"], 64000.0)
        self.assertEqual(f["funding_rate"], 0.0001)
        self.assertEqual(f["next_funding_ts"], 1783000000000)

    def test_ticker_and_movers_rank_on_binance_numbers(self):
        self.m._apply_frame(_ticker_frame([
            ("BTCUSDT", "64000", "1.2", "65000", "63000", "5000000000", 900000),
            ("ETHUSDT", "3500", "5.5", "3600", "3300", "2000000000", 400000),
            ("PEPEUSDT", "0.00001", "22.0", "0.000012", "0.000009", "300000000", 120000),
        ]))
        # by liquidity → BTC first
        top_vol = self.m.movers(2, by="quote_volume")
        self.assertEqual([r["symbol"] for r in top_vol], ["BTCUSDT", "ETHUSDT"])
        # by gainers → PEPE first
        top_gain = self.m.movers(1, by="pct_change")
        self.assertEqual(top_gain[0]["symbol"], "PEPEUSDT")
        # min_quote_volume filter drops the micro-cap
        liquid = self.m.movers(10, by="pct_change", min_quote_volume=1_000_000_000)
        self.assertNotIn("PEPEUSDT", [r["symbol"] for r in liquid])

    def test_liquidations_buffer_and_filter(self):
        self.m._apply_frame(_liq_frame("BTCUSDT", "SELL", "1.5", "63900", 1783000000000))
        self.m._apply_frame(_liq_frame("ETHUSDT", "BUY", "10", "3510", 1783000001000))
        self.assertEqual(len(self.m.recent_liquidations()), 2)
        btc = self.m.recent_liquidations("BTCUSDT")
        self.assertEqual(len(btc), 1)
        self.assertEqual(btc[0]["side"], "SELL")
        self.assertEqual(btc[0]["qty"], 1.5)

    def test_staleness_flag_is_honest(self):
        self.m._apply_frame(_mark_frame([("BTCUSDT", "64000", "0.0001", 1)]))
        self.assertFalse(self.m.is_stale("BTCUSDT"))          # just updated
        # backdate the field → must report stale, never serve it as fresh
        self.m._mark["BTCUSDT"]["ts"] = time.time() - 999
        self.assertTrue(self.m.is_stale("BTCUSDT"))

    def test_status_shape(self):
        self.m._apply_frame(_ticker_frame([("BTCUSDT", "64000", "1.2", "65000", "63000", "5e9", 9)]))
        st = self.m.status()
        for k in ("enabled", "running", "connected", "symbols_ticker", "stale", "reconnects"):
            self.assertIn(k, st)
        self.assertEqual(st["symbols_ticker"], 1)

    def test_bad_frame_never_raises(self):
        for junk in ({}, {"stream": "!ticker@arr", "data": None}, {"stream": "x"}, {"data": []}):
            self.m._apply_frame(junk)            # must not raise
        self.assertEqual(self.m.status()["symbols_ticker"], 0)


if __name__ == "__main__":
    unittest.main()
