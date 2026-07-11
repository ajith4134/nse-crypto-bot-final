"""tests/test_binance_sectors.py — Binance-native sector taxonomy + rotation.

Offline: monkeypatch the products endpoint + seed the WS mirror in RAM. No network.
"""
import time
import unittest
from unittest import mock

from trading.broker_sense import binance_sectors as sec
from trading.broker_sense.binance_stream import get_mirror


_FAKE_PRODUCTS = {"data": [
    {"b": "BTC", "tags": ["Layer1_Layer2", "pos"]},
    {"b": "FET", "tags": ["AI", "Infrastructure"]},
    {"b": "RENDER", "tags": ["AI"]},
    {"b": "PEPE", "tags": ["Meme"]},
]}


class TestSectors(unittest.TestCase):
    def setUp(self):
        sec.clear_cache()
        m = get_mirror()
        with m._lock:
            m._ticker.clear()
            for raw, pc, qv in [("FETUSDT", 8.0, 5e7), ("RENDERUSDT", 6.0, 4e7),
                                ("PEPEUSDT", -3.0, 3e7), ("BTCUSDT", 0.5, 9e9)]:
                m._ticker[raw] = {"pct_change": pc, "quote_volume": qv, "ts": time.time()}

    def test_tags_for_symbol_via_base(self):
        with mock.patch.object(sec, "_get_json", return_value=_FAKE_PRODUCTS):
            self.assertIn("AI", sec.tags_for("FET/USDT:USDT"))
            self.assertIn("Meme", sec.tags_for("PEPEUSDT"))
            self.assertEqual(sec.tags_for("NOTACOIN"), [])

    def test_sector_rotation_ranks_hot_sectors(self):
        with mock.patch.object(sec, "_get_json", return_value=_FAKE_PRODUCTS):
            rot = sec.sector_rotation(min_members=2)
        # AI has FET(+8) & RENDER(+6) → avg +7, the hottest 2-member sector
        ai = next((r for r in rot if r["sector"] == "AI"), None)
        self.assertIsNotNone(ai)
        self.assertEqual(ai["members"], 2)
        self.assertAlmostEqual(ai["avg_pct_change"], 7.0)
        self.assertEqual(rot[0]["sector"], "AI")            # ranked hottest first

    def test_sector_signal_tilt(self):
        with mock.patch.object(sec, "_get_json", return_value=_FAKE_PRODUCTS):
            s = sec.sector_signal("FET/USDT:USDT")
        self.assertEqual(s["sector"], "AI")
        self.assertGreater(s["tilt"], 0)                    # AI sector up → long-favourable
        self.assertIn("AI", s["tags"])

    def test_disabled_is_honest(self):
        import os
        os.environ["BINANCE_SECTORS"] = "0"
        try:
            self.assertEqual(sec.tags_for("BTCUSDT"), [])
            self.assertEqual(sec.sector_rotation(), [])
        finally:
            os.environ.pop("BINANCE_SECTORS", None)


if __name__ == "__main__":
    unittest.main()
