"""Tests for the FREE eyes' deterministic matcher + OCR-row parsing (pure, no browser/LLM)."""
import unittest

from trading.brain.vision.free_eyes import _score_match, _ocr_row, _tok_hit, Glance


class TestMatcher(unittest.TestCase):
    def test_exact_and_verbose_target(self):
        self.assertGreater(_score_match("the + button to Pin new symbols", "Pin new symbols"), 0.8)

    def test_plural_substring_tolerance(self):
        self.assertTrue(_tok_hit("symbol", {"symbols"}))
        self.assertTrue(_tok_hit("watchlist", {"watchlists"}))
        self.assertGreater(_score_match("add symbol", "Pin symbols"), 0.4)

    def test_symbol_row(self):
        self.assertGreater(_score_match("the watchlist row for RELIANCE", "RELIANCE"), 0.7)

    def test_rejects_unrelated(self):
        self.assertEqual(_score_match("buy button", "Pin new symbols"), 0.0)

    def test_order_control_not_matched_by_watchlist_target(self):
        # a watchlist target must not accidentally score a Buy/Sell control
        self.assertLess(_score_match("the pin symbol control", "Sell"), 0.45)


class TestOcrRow(unittest.TestCase):
    def test_box_to_center(self):
        row = _ocr_row([[10, 20], [110, 20], [110, 60], [10, 60]], "RELIANCE")
        self.assertEqual(row["text"], "RELIANCE")
        self.assertEqual(row["cx"], 60)          # 10 + 100/2
        self.assertEqual(row["cy"], 40)          # 20 + 40/2

    def test_bad_box_returns_none(self):
        self.assertIsNone(_ocr_row("garbage", "x"))


class TestGlanceText(unittest.TestCase):
    def test_dedup_and_join(self):
        g = Glance(controls=[{"label": "RELIANCE"}, {"label": "reliance"}, {"label": "TCS"}],
                   ocr=[{"text": "TCS"}, {"text": "NIFTY 24500"}])
        lines = g.text().splitlines()
        self.assertIn("RELIANCE", lines)
        self.assertIn("NIFTY 24500", lines)
        self.assertEqual(lines.count("TCS"), 1)   # de-duped across DOM + OCR


if __name__ == "__main__":
    unittest.main()
