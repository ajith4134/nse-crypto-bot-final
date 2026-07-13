"""Tests for nav_brain._followed_plan — the brain FOLLOWS proven route instructions (proposal F)."""
import tempfile
import unittest
from unittest import mock

from memory import neurons as neurons_mod
from memory.neurons import NeuronStore
from trading.broker_sense.nav_brain import NavBrain


class NavFollowTest(unittest.TestCase):
    def setUp(self):
        self.store = NeuronStore(tempfile.mkdtemp())
        gp = mock.patch.object(neurons_mod, "_STORE", self.store)
        gp.start(); self.addCleanup(gp.stop)
        # allow all segments so the gate passes the followed actions
        bp = mock.patch("trading.brain.boss.active_segments", lambda m: ["futures", "spot"])
        bp.start(); self.addCleanup(bp.stop)
        self.nav = NavBrain(lambda: {"url": "x"}, lambda a: None, market="crypto")

    def test_follows_a_proven_instruction(self):
        instr = self.store.add(
            "instruction", "Nav [crypto] binance: reach futures",
            "1) open the futures view\n2) click the order book\n3) read the depth",
            "Use to reach futures on binance. Verify: depth visible.", auto_link=False)
        self.store.record_use(instr.id, win=True, domain="navigation")   # confidence > 0.5
        self.nav._consulted = {"ids": [instr.id], "actions": [], "titles": []}
        plan = self.nav._followed_plan()
        self.assertIsNotNone(plan)
        self.assertEqual(self.nav._following, instr.id)                  # recorded what it follows
        targets = [a["target"] for a in plan]
        self.assertTrue(any("order book" in t for t in targets))         # the proven steps
        self.assertTrue(all(a["type"] == "click" for a in plan))

    def test_no_proven_instruction_falls_back(self):
        weak = self.store.add("instruction", "unproven route", "1) x",
                              "use. verify", auto_link=False)             # confidence 0.5 default...
        self.store.record_use(weak.id, win=False, domain="navigation")   # → below 0.5
        self.nav._consulted = {"ids": [weak.id]}
        self.assertIsNone(self.nav._followed_plan())                     # → planner takes over

    def test_no_consult_returns_none(self):
        self.nav._consulted = None
        self.assertIsNone(self.nav._followed_plan())


if __name__ == "__main__":
    unittest.main()
