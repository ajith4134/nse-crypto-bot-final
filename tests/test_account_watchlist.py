"""Tests for the Brain-Open account-watchlist sync + human-UI JSON parsing (pure logic)."""
import unittest

from trading.broker_sense.account_watchlist import plan_sync
from trading.brain.vision.human_ui import _extract_json


class TestPlanSync(unittest.TestCase):
    def test_add_new_open_trades(self):
        p = plan_sync(desired=["RELIANCE", "INFY"], already=["RELIANCE"])
        self.assertEqual(p["add"], ["INFY"])
        self.assertEqual(p["remove"], [])

    def test_remove_closed_trades(self):
        p = plan_sync(desired=["RELIANCE"], already=["RELIANCE", "TCS"])
        self.assertEqual(p["add"], [])
        self.assertEqual(p["remove"], ["TCS"])

    def test_add_and_remove_together(self):
        p = plan_sync(desired=["A", "B"], already=["B", "C"])
        self.assertEqual(p["add"], ["A"])
        self.assertEqual(p["remove"], ["C"])
        self.assertEqual(p["unchanged"], ["B"])

    def test_in_sync_is_noop(self):
        p = plan_sync(desired=["A", "B"], already=["B", "A"])
        self.assertEqual(p["add"], [])
        self.assertEqual(p["remove"], [])

    def test_dedup_and_order_stable(self):
        p = plan_sync(desired=["A", "A", "B"], already=[])
        self.assertEqual(p["target"], ["A", "B"])
        self.assertEqual(p["add"], ["A", "B"])

    def test_empty_desired_removes_all(self):
        p = plan_sync(desired=[], already=["A", "B"])
        self.assertEqual(p["remove"], ["A", "B"])


class TestVisionJsonParse(unittest.TestCase):
    def test_plain_json_object(self):
        self.assertEqual(_extract_json('{"found": true, "x": 5, "y": 9}'),
                         {"found": True, "x": 5, "y": 9})

    def test_fenced_json(self):
        self.assertEqual(_extract_json('```json\n["A","B"]\n```'), ["A", "B"])

    def test_json_embedded_in_prose(self):
        self.assertEqual(_extract_json('Sure! Here it is: {"found": false} — hope that helps'),
                         {"found": False})

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_json("no json here"))
        self.assertIsNone(_extract_json(""))


if __name__ == "__main__":
    unittest.main()
