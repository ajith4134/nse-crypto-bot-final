"""Tests for binance_stream price history + truth-ledger 100% price coverage (2026-07-13)."""
import unittest
from collections import deque
from unittest import mock

from trading.broker_sense.binance_stream import BinanceUniverseMirror
from trading.direction import truth_ledger as tl


class MirrorPriceTest(unittest.TestCase):
    def test_price_at_finds_closest_within_tolerance(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._hist["MAGMAUSDT"] = deque([(t - 300, 0.70), (t - 180, 0.72), (t - 60, 0.75)])
        self.assertEqual(m.price_at("MAGMAUSDT", t - 180), 0.72)   # exact-ish
        self.assertEqual(m.price_at("MAGMAUSDT", t - 70), 0.75)    # nearest
        self.assertIsNone(m.price_at("MAGMAUSDT", t - 9000))       # out of tolerance
        self.assertIsNone(m.price_at("UNSEENUSDT", t))            # no history

    def test_price_at_falls_back_to_latest_mark_when_fresh(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._mark["BTCUSDT"] = {"mark": 62000.0, "ts": t}
        self.assertEqual(m.price_at("BTCUSDT", t + 10), 62000.0)   # no hist, latest is close
        self.assertIsNone(m.price_at("BTCUSDT", t + 9000))         # latest too stale

    def test_resolver_prices_any_perp_via_mirror(self):
        m = BinanceUniverseMirror()
        t = 1_000_000.0
        m._hist["MAGMAUSDT"] = deque([(t, 0.72)])
        with mock.patch("trading.broker_sense.binance_stream.get_mirror", return_value=m):
            # ccxt-style perp symbol → flattened + priced from the all-market mirror
            self.assertEqual(tl._mirror_price("MAGMA/USDT:USDT", t), 0.72)

    def test_record_stamps_ref_price_from_mirror_at_decision_time(self):
        """100% coverage (2026-07-13): a fresh CRYPTO claim with no ref_price must lock
        the entry price from the live mirror mark AT record time — otherwise resolution
        depends on per-process in-RAM history at an old ts and the claim stays no_data."""
        with mock.patch.object(tl, "_mirror_price", return_value=0.352) as mp, \
             mock.patch.object(tl, "_enabled", return_value=True), \
             mock.patch.object(tl, "_pending_path") as pp:
            import tempfile, pathlib, json as _json
            f = pathlib.Path(tempfile.mkdtemp()) / "pending.jsonl"
            pp.return_value = f
            ok = tl.record(symbol="MAGMAUSDT", market="CRYPTO", segment="futures",
                           direction="LONG", source="filter:momentum", confidence=0.6)
            self.assertTrue(ok)
            row = _json.loads(f.read_text().strip().splitlines()[-1])
            self.assertEqual(row["ref_price"], 0.352)   # stamped, not null
            mp.assert_called()
        # NSE claims must NOT be mirror-stamped (mirror is crypto-only)
        with mock.patch.object(tl, "_mirror_price", return_value=0.352) as mp2, \
             mock.patch.object(tl, "_enabled", return_value=True), \
             mock.patch.object(tl, "_pending_path") as pp2:
            import tempfile, pathlib, json as _json
            f2 = pathlib.Path(tempfile.mkdtemp()) / "pending.jsonl"
            pp2.return_value = f2
            tl.record(symbol="RELIANCE", market="NSE", segment="equity",
                      direction="LONG", source="filter:momentum")
            row2 = _json.loads(f2.read_text().strip().splitlines()[-1])
            self.assertIsNone(row2["ref_price"])
            mp2.assert_not_called()


class CandleAggregationTest(unittest.TestCase):
    def test_roll_candles_buckets_ohlc_by_timeframe(self):
        m = BinanceUniverseMirror()
        # three ticks inside the same 60s bucket (999_960 = 999_960..1_000_019), then next bucket
        m._roll_candles("BTCUSDT", 100.0, 999_960.0)     # bucket 999_960, open
        m._roll_candles("BTCUSDT", 105.0, 999_970.0)     # high
        m._roll_candles("BTCUSDT", 98.0, 999_980.0)      # low, close
        bars = m.candles("BTCUSDT", tf=60, n=10)
        self.assertEqual(len(bars), 1)
        ts, o, h, l, c = bars[-1]
        self.assertEqual((ts, o, h, l, c), (999_960, 100.0, 105.0, 98.0, 98.0))
        m._roll_candles("BTCUSDT", 110.0, 1_000_030.0)   # next 60s bucket (1_000_020)
        bars = m.candles("BTCUSDT", tf=60, n=10)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[-1][1], 110.0)             # new bar opens at 110
        self.assertEqual(bars[-2][3], 98.0)              # prior bar low preserved

    def test_candles_unknown_symbol_or_tf_returns_empty(self):
        m = BinanceUniverseMirror()
        self.assertEqual(m.candles("NOPEUSDT", tf=60), [])
        m._roll_candles("BTCUSDT", 100.0, 1_000_000.0)
        self.assertEqual(m.candles("BTCUSDT", tf=99999), [])   # untracked tf


class LiquidationNormalizationTest(unittest.TestCase):
    def test_signals_reads_liquidations_from_mirror_with_correct_side(self):
        from trading.direction import app_signals as A
        m = BinanceUniverseMirror()
        # Binance forceOrder S="BUY" = a SHORT was force-bought (short liquidation)
        m._liqs.extend([
            {"symbol": "BTCUSDT", "side": "BUY", "pos_side": "short"},
            {"symbol": "BTCUSDT", "side": "BUY", "pos_side": "short"},
            {"symbol": "BTCUSDT", "side": "SELL", "pos_side": "long"},
        ])
        # ui_market returns nothing → signals() must fall back to the mirror
        fake_um = mock.MagicMock()
        fake_um.recent_liquidations.return_value = []
        for meth in ("funding", "taker", "book", "long_short", "open_interest", "option_chain"):
            getattr(fake_um, meth).return_value = None
        with mock.patch.dict("sys.modules", {"trading.broker_sense.ui_market": fake_um}), \
             mock.patch("trading.broker_sense.binance_stream.get_mirror", return_value=m):
            sigs = dict(A.signals("BTCUSDT", market="crypto", row={}))
        # 2 shorts liquidated of 3 → short-cascade → bullish lean p_up > 0.5
        self.assertIn("filter:liquidations", sigs)
        self.assertGreater(sigs["filter:liquidations"], 0.5)


if __name__ == "__main__":
    unittest.main()
