"""WS-mirror order-book depth (2026-07-12): the binance_stream mirror now streams 20-level partial
book for the top-N movers so psychology reads depth from RAM instead of a ~300ms REST fetch per
symbol. Locks the frame parse, the freshness-gated accessor, and the BookSnapshot integration.
"""
import time
import unittest

from trading.broker_sense import binance_stream as bs


class TestBinanceDepthMirror(unittest.TestCase):
    def _frame(self, sym="BTCUSDT"):
        return {"stream": f"{sym.lower()}@depth20@500ms",
                "data": {"s": sym,
                         "b": [["100.0", "2.0"], ["99.5", "1.0"]],
                         "a": [["100.5", "3.0"], ["101.0", "1.5"]]}}

    def test_frame_parse_and_book_accessor(self):
        m = bs.BinanceUniverseMirror()
        m._apply_depth_frame(self._frame())
        b = m.book("BTC/USDT:USDT")               # accessor normalizes the settle suffix + slash
        self.assertIsNotNone(b)
        self.assertEqual(b["bids"][0], [100.0, 2.0])
        self.assertEqual(b["asks"][0], [100.5, 3.0])

    def test_staleness_returns_none(self):
        m = bs.BinanceUniverseMirror()
        m._apply_depth_frame(self._frame())
        m._book["BTCUSDT"]["ts"] = time.time() - 99      # older than max_age_s
        self.assertIsNone(m.book("BTC/USDT:USDT"))

    def test_empty_side_ignored(self):
        m = bs.BinanceUniverseMirror()
        m._apply_depth_frame({"stream": "x@depth20@500ms",
                              "data": {"s": "XUSDT", "b": [], "a": [["1", "1"]]}})
        self.assertIsNone(m.book("X/USDT:USDT"))

    def test_snapshot_integration(self):
        from trading.brain.psychology import BookSnapshot
        m = bs.BinanceUniverseMirror()
        m._apply_depth_frame(self._frame("ETHUSDT"))
        snap = BookSnapshot.from_ccxt(m.book("ETH/USDT:USDT"))
        self.assertIsNotNone(snap)
        self.assertEqual(snap.mid, 100.25)        # mid is a property

    def test_status_reports_depth(self):
        m = bs.BinanceUniverseMirror()
        st = m.status()
        for k in ("depth_enabled", "depth_connected", "symbols_book", "depth_watch"):
            self.assertIn(k, st)


if __name__ == "__main__":
    unittest.main()
