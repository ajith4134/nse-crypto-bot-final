"""Tests for trading/brain/flow_health.py — loop stitch monitor (R1)."""
import os
import tempfile
import time
import unittest
from unittest import mock

from trading import state
from trading.brain import flow_health


class FlowHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.tmp))
        p.start()
        self.addCleanup(p.stop)

    def test_missing_files_are_honest_not_ok(self):
        out = flow_health.flow_status()
        perceive = next(s for s in out["stages"] if s["key"] == "perceive")
        self.assertFalse(perceive["ok"])
        self.assertFalse(out["flowing"])
        self.assertTrue(all(not e["exists"] for e in perceive["evidence"]))

    def test_fresh_file_turns_stage_ok_and_edges_follow(self):
        now = time.time()
        for name in ("ui_market.json", "associative_notes.json"):
            path = os.path.join(self.tmp, name)
            with open(path, "w") as f:
                f.write("{}")
        out = flow_health.flow_status(now=now)
        by = {s["key"]: s for s in out["stages"]}
        self.assertTrue(by["perceive"]["ok"])
        self.assertTrue(by["recall"]["ok"])
        edge = next(e for e in out["edges"]
                    if e["src"] == "perceive" and e["dst"] == "recall")
        self.assertTrue(edge["ok"])
        self.assertEqual(out["healthy_stages"],
                         sum(1 for s in out["stages"] if s["ok"]))

    def test_stale_file_fails_budget(self):
        path = os.path.join(self.tmp, "ui_market.json")
        with open(path, "w") as f:
            f.write("{}")
        old = time.time() - 3 * 3600                    # perceive budget is 30min
        os.utime(path, (old, old))
        out = flow_health.flow_status()
        perceive = next(s for s in out["stages"] if s["key"] == "perceive")
        self.assertFalse(perceive["ok"])
        self.assertGreater(perceive["freshest_secs"], perceive["budget_secs"])

    def test_loop_closes_teach_self_to_perceive(self):
        out = flow_health.flow_status()
        self.assertEqual(out["edges"][-1]["src"], "teach_self")
        self.assertEqual(out["edges"][-1]["dst"], "perceive")


if __name__ == "__main__":
    unittest.main()
