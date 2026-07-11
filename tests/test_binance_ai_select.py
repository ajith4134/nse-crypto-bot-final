"""tests/test_binance_ai_select.py — Binance built-in AI Select recommendations.

Offline: monkeypatch the recommended-assets endpoint per type (no network).
"""
import unittest
from unittest import mock

from trading.broker_sense import binance_ai_select as ai


def _fake(url):
    if "type=sentiment" in url:
        return {"data": {"items": [{"baseAsset": "ETH", "rank": 1}, {"baseAsset": "BTC", "rank": 2}]}}
    if "type=technical" in url:
        return {"data": {"items": [{"baseAsset": "SKL", "rank": 2}, {"baseAsset": "ETH", "rank": 5}]}}
    return None


class TestAISelect(unittest.TestCase):
    def setUp(self):
        ai.clear_cache()

    def test_picks_merge_and_rank(self):
        with mock.patch.object(ai, "_get_json", side_effect=_fake):
            ps = ai.picks()
        bym = {p["base"]: p for p in ps}
        self.assertIn("ETH", bym)
        self.assertEqual(bym["ETH"]["best_rank"], 1)                 # best rank across types
        self.assertEqual(set(bym["ETH"]["types"]), {"sentiment", "technical"})
        self.assertIn("SKL", bym)
        self.assertEqual(ps[0]["base"], "ETH")                       # ranked best-first

    def test_is_ai_selected_flag(self):
        with mock.patch.object(ai, "_get_json", side_effect=_fake):
            s = ai.is_ai_selected("SKL/USDT:USDT")
            self.assertTrue(s["ai_selected"])
            self.assertEqual(s["ai_rank"], 2)
            self.assertIn("technical", s["ai_types"])
            self.assertFalse(ai.is_ai_selected("DOGEUSDT")["ai_selected"])

    def test_disabled_is_honest(self):
        import os
        os.environ["BINANCE_AI_SELECT"] = "0"
        try:
            self.assertEqual(ai.picks(), [])
            self.assertFalse(ai.is_ai_selected("ETHUSDT")["ai_selected"])
        finally:
            os.environ.pop("BINANCE_AI_SELECT", None)


if __name__ == "__main__":
    unittest.main()
