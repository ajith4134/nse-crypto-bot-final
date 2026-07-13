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


if __name__ == "__main__":
    unittest.main()
