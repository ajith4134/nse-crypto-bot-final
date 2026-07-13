"""Tests for trading/brain/consult.py + the consult→grade wiring (R22, Phase 2)."""
import tempfile
import unittest
from unittest import mock

import memory.neurons as mn
from trading import state
from trading.brain import consult


class ConsultTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(state, "STATE_DIR",
                              type(state.STATE_DIR)(tempfile.mkdtemp()))
        p.start()
        self.addCleanup(p.stop)
        # point the process singleton at a temp store; restore after
        self.store = mn.get_store(tempfile.mkdtemp())
        self.addCleanup(lambda: setattr(mn, "_STORE", None))

    def test_consult_records_use_and_returns_actions(self):
        n = self.store.add("episode", "BTCUSDT LONG range vp bounce",
                           "BTCUSDT LONG in range regime bounced off VAL for +1.2R.",
                           "REPEAT this setup: BTCUSDT LONG at VAL in range regime.",
                           auto_link=False)
        out = consult.consult("BTCUSDT long range", domain="trading")
        self.assertIn(n.id, out["ids"])
        self.assertTrue(any("REPEAT" in a for a in out["actions"]))
        got = self.store.get(n.id)
        self.assertEqual(got.stats["times_used"], 1)
        self.assertEqual(got.stats["by_domain"]["trading"]["uses"], 1)
        self.assertEqual(got.stats["by_domain"]["trading"]["wins"], 0)  # win=None at consult

    def test_grade_closes_the_loop(self):
        n = self.store.add("episode", "ETHUSDT SHORT trend", "body text here ok",
                           "action facet", auto_link=False)
        out = consult.consult("ETHUSDT short trend", domain="trading")
        graded = consult.grade(out["ids"], win=True, pnl=2.5, domain="trading")
        self.assertEqual(graded, len(out["ids"]))
        got = self.store.get(n.id)
        self.assertEqual(got.stats["wins"], 1)
        self.assertEqual(got.stats["by_domain"]["trading"]["wins"], 1)
        self.assertAlmostEqual(got.stats["pnl"], 2.5)

    def test_fail_open_on_empty_and_bad_input(self):
        self.assertEqual(consult.consult("", domain="trading"),
                         {"ids": [], "actions": [], "titles": []})
        self.assertEqual(consult.grade(None, win=True, domain="trading"), 0)
        self.assertEqual(consult.grade(["n-nonexistent"], win=True, domain="x"), 0)

    def test_nav_brain_consults_and_grades(self):
        instr = self.store.add(
            "instruction", "navigate crypto futures markets tab",
            "1) click Futures tab 2) verify markets table visible",
            "Use when the goal mentions futures markets; verify table appears.",
            auto_link=False)
        from trading.broker_sense.nav_brain import NavBrain
        pages = iter([{"url": "a", "text": "home"}, {"url": "a", "text": "home"},
                      {"url": "b", "text": "futures tab markets"}] * 20)
        nav = NavBrain(lambda: next(pages), lambda a: None, market="crypto",
                       max_steps=3)
        with mock.patch.object(NavBrain, "allowed_segments", return_value={"futures"}):
            res = nav.navigate("open futures markets")
        self.assertIn(instr.id, res["neurons_consulted"])
        got = self.store.get(instr.id)
        self.assertEqual(got.stats["by_domain"]["navigation"]["uses"], 1)
        self.assertEqual(got.stats["wins"] + got.stats["losses"], 1)  # graded once

    def test_close_grading_from_decision_snapshot(self):
        n = self.store.add("episode", "SOLUSDT LONG episode", "body text here ok",
                           "action", auto_link=False)
        snap = {"app_signals": {"indicator_fusion": {"neurons": {"ids": [n.id]}}}}
        fus = ((snap.get("app_signals") or {}).get("indicator_fusion") or {})
        ids = ((fus.get("neurons") or {}).get("ids") or [])   # the ingest extraction
        self.assertEqual(consult.grade(ids, win=False, pnl=-1.0, domain="trading"), 1)
        self.assertEqual(self.store.get(n.id).stats["losses"], 1)


if __name__ == "__main__":
    unittest.main()
