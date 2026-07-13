"""tests/test_binance_stream.py — Binance all-market in-RAM mirror.

Offline: feeds synthetic combined-stream frames into _apply_frame (the pure parser) — no socket,
no network — and asserts the RAM read API (funding, ticker, movers, liquidations, staleness).
"""
import os
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

    def test_futures_rows_raw_to_ccxt_conversion(self):
        self.m._apply_frame(_ticker_frame([
            ("BTCUSDT", "64000", "1.2", "65000", "63000", "5000000000", 900000),
            ("1000PEPEUSDT", "0.01", "3.0", "0.011", "0.009", "300000000", 120000),
            ("BTCUSDC", "64000", "1.0", "65000", "63000", "1000000", 5000),   # non-USDT → skipped
        ]))
        self.m._apply_frame(_mark_frame([("BTCUSDT", "64000", "0.0001", 1)]))
        rows = {r["raw"]: r for r in self.m.futures_rows()}
        self.assertEqual(rows["BTCUSDT"]["symbol"], "BTC/USDT:USDT")
        self.assertEqual(rows["1000PEPEUSDT"]["symbol"], "1000PEPE/USDT:USDT")
        self.assertEqual(rows["BTCUSDT"]["funding_rate"], 0.0001)
        self.assertNotIn("BTCUSDC", rows)        # non-USDT perp skipped for now


class TestScreenerMirrorMigration(unittest.TestCase):
    """screen_crypto_futures sources the universe from the mirror when warm (not ccxt)."""

    def test_screens_from_mirror_when_warm(self):
        from trading.broker_sense.binance_stream import get_mirror
        from trading.screener.screener import screen_crypto_futures
        m = get_mirror()
        with m._lock:
            m._ticker.update({
                "BTCUSDT": {"last": 64000.0, "pct_change": 1.2, "high": 65000.0, "low": 63000.0,
                            "quote_volume": 5e9, "count": 9, "ts": time.time()},
                "ETHUSDT": {"last": 3500.0, "pct_change": 5.5, "high": 3600.0, "low": 3300.0,
                            "quote_volume": 2e9, "count": 4, "ts": time.time()},
            })
            m._mark["BTCUSDT"] = {"mark": 64000.0, "funding_rate": 0.0001,
                                  "next_funding_ts": 1, "ts": time.time()}
        cands = screen_crypto_futures(source=None, limit=5)   # source=None → ccxt path would crash
        self.assertTrue(cands)
        syms = {c["symbol"] for c in cands}
        self.assertTrue({"BTC/USDT:USDT", "ETH/USDT:USDT"} & syms)
        self.assertTrue(all(c["metrics"]["source"] == "binance-mirror" for c in cands))


class TestMirrorOHLCVAdapter(unittest.TestCase):
    """binance_stream.ohlcv() serves in-RAM multi-TF candles in ccxt shape (no API)."""

    def _seed(self, m, flat="ZZZUSDT", tf=60, n=60):
        from collections import deque
        base = 1_700_000_000
        with m._lock:
            m._candles[flat] = {60: deque(maxlen=240), 300: deque(maxlen=240),
                                900: deque(maxlen=240)}
            for i in range(n):
                p = 100.0 + i * 0.1
                m._candles[flat][tf].append([base + i * tf, p, p + 0.5, p - 0.5, p + 0.2])

    def test_ohlcv_returns_ccxt_shape(self):
        from trading.broker_sense import binance_stream as bs
        os.environ["MIRROR_CANDLES"] = "1"
        m = bs.get_mirror()
        self._seed(m)
        rows = bs.ohlcv("ZZZ/USDT:USDT", "1m", 220)
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 60)
        self.assertEqual(len(rows[0]), 6)                 # [ms, o, h, l, c, v]
        self.assertEqual(rows[0][0] % 1000, 0)            # ms epoch
        self.assertEqual(rows[0][5], 0.0)                 # mark-price candles carry no volume

    def test_ohlcv_misses_fall_back_to_none(self):
        from trading.broker_sense import binance_stream as bs
        os.environ["MIRROR_CANDLES"] = "1"
        m = bs.get_mirror()
        self._seed(m)
        self.assertIsNone(bs.ohlcv("ZZZ/USDT:USDT", "1h"))     # TF not aggregated
        self.assertIsNone(bs.ohlcv("NOPE/USDT:USDT", "1m"))    # symbol not in RAM
        self.assertIsNone(bs.ohlcv("ZZZ/USDT:USDT", "wat"))    # unknown TF string

    def test_kill_switch(self):
        from trading.broker_sense import binance_stream as bs
        m = bs.get_mirror()
        self._seed(m)
        os.environ["MIRROR_CANDLES"] = "0"
        try:
            self.assertIsNone(bs.ohlcv("ZZZ/USDT:USDT", "1m"))
        finally:
            os.environ["MIRROR_CANDLES"] = "1"


if __name__ == "__main__":
    unittest.main()
