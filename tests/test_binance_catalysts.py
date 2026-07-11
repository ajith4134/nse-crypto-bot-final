"""tests/test_binance_catalysts.py — Binance-native listing catalysts.

Hermetic: STATE_DIR monkeypatched to a temp dir (seen-symbols file isolation), announcements
monkeypatched (no network), mirror seeded in-RAM. No unlock fabrication is asserted.
"""
import pathlib
import tempfile
import time
import unittest
from unittest import mock

from trading.broker_sense import binance_catalysts as bc
from trading.broker_sense.binance_stream import get_mirror


_FAKE_ANN = {"data": {"catalogs": [{"articles": [
    {"title": "Binance Futures Will Launch USDⓈ-Margined SKHYUSDT Perpetual Contract", "id": 1},
    {"title": "Binance Adds ANTA, CBRS and QNT on Binance Stock Trading", "id": 2},
]}]}}


class TestCatalysts(unittest.TestCase):
    def setUp(self):
        import trading.state as state
        self._tmp = tempfile.TemporaryDirectory()
        state.STATE_DIR = pathlib.Path(self._tmp.name)
        bc._cache.clear()

    def tearDown(self):
        self._tmp.cleanup()

    def test_announcement_symbol_extraction(self):
        with mock.patch.object(bc, "_get_json", return_value=_FAKE_ANN):
            anns = bc.announcements()
        titles = {a["title"][:20]: a["symbols"] for a in anns}
        # perp launch → base ticker pulled from SKHYUSDT
        self.assertIn("SKHY", sum((a["symbols"] for a in anns), []))
        # "Adds ANTA, CBRS and QNT" → those tickers extracted
        adds = next(a for a in anns if "Adds" in a["title"])
        for t in ("ANTA", "CBRS", "QNT"):
            self.assertIn(t, adds["symbols"])

    def test_new_listing_diff_seeds_then_flags(self):
        m = get_mirror()
        with m._lock:
            m._ticker.clear()
            m._ticker.update({"BTCUSDT": {"quote_volume": 1e9, "pct_change": 1.0, "ts": time.time()},
                              "ETHUSDT": {"quote_volume": 1e9, "pct_change": 1.0, "ts": time.time()}})
        bc.refresh_new_listings()                     # first run → seeds, nothing is "new"
        self.assertEqual(bc.new_listings(), [])
        # a brand-new perp appears
        with m._lock:
            m._ticker["NEWXUSDT"] = {"quote_volume": 5e6, "pct_change": 30.0, "ts": time.time()}
        fresh = bc.new_listings()
        self.assertEqual([f["raw"] for f in fresh], ["NEWXUSDT"])

    def test_catalyst_combines_flags(self):
        m = get_mirror()
        with m._lock:
            m._ticker.clear()
            m._ticker.update({"BTCUSDT": {"quote_volume": 1e9, "pct_change": 1.0, "ts": time.time()}})
        bc.refresh_new_listings()
        with m._lock:
            m._ticker["SKHYUSDT"] = {"quote_volume": 5e6, "pct_change": 40.0, "ts": time.time()}
        bc.refresh_new_listings()                     # SKHY now flagged new
        with mock.patch.object(bc, "_get_json", return_value=_FAKE_ANN):
            c = bc.catalyst("SKHY/USDT:USDT")
        self.assertTrue(c["is_new_listing"])
        self.assertTrue(c["listing_announced"])       # also in the announcement feed
        self.assertIn("SKHYUSDT", c["announcement_title"])

    def test_disabled_and_empty_are_honest(self):
        import os
        os.environ["BINANCE_CATALYSTS"] = "0"
        try:
            self.assertEqual(bc.announcements(), [])
            self.assertFalse(bc.catalyst("BTCUSDT")["is_new_listing"])
        finally:
            os.environ.pop("BINANCE_CATALYSTS", None)


if __name__ == "__main__":
    unittest.main()
