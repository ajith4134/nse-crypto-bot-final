"""Tests for trading/brain/induction.py — AWM induction of instruction neurons (R7/R12/R13),
and the induction → evolution loop it feeds."""
import tempfile
import unittest
from unittest import mock

import trading.brain.induction as ind
from memory import neurons as neurons_mod
from memory.neurons import NeuronStore
from trading import state
from trading.brain.evolution import InstructionEvolver
from trading.brain.instructions import InstructionEngine


class InductionTest(unittest.TestCase):
    def setUp(self):
        self.tmp_state = tempfile.mkdtemp()
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.tmp_state))
        p.start(); self.addCleanup(p.stop)
        # induction + instructions call memory.neurons.get_store() → pin the singleton to a temp store
        self.store = NeuronStore(tempfile.mkdtemp())
        gp = mock.patch.object(neurons_mod, "_STORE", self.store)
        gp.start(); self.addCleanup(gp.stop)

    def test_trade_recipe_created_then_graded_idempotent(self):
        nid = ind.induce_from_trade(strategy="vp_reversion", regime="range",
                                    direction="long", win=True, net_pnl=12.0)
        self.assertIsNotNone(nid)
        n = self.store.get(nid)
        self.assertEqual(n.kind, "instruction")
        self.assertTrue(n.action.strip())                       # R24 action facet
        self.assertEqual(n.stats["wins"], 1)
        # same pattern again (a loss) → SAME neuron, evidence accrues, no dupe
        nid2 = ind.induce_from_trade(strategy="vp_reversion", regime="range",
                                     direction="long", win=False, net_pnl=-8.0)
        self.assertEqual(nid, nid2)
        n = self.store.get(nid)
        self.assertEqual(n.stats["wins"], 1)
        self.assertEqual(n.stats["losses"], 1)

    def test_trade_without_strategy_is_skipped(self):
        self.assertIsNone(ind.induce_from_trade(strategy="", regime="range",
                                                direction="long", win=True))

    def test_nav_route_induced_only_on_completion(self):
        trace = [{"action": {"target": "Trade menu"}, "ok": True},
                 {"action": {"target": "Spot"}, "ok": True},
                 {"action": {"target": "search box"}, "ok": False}]  # failed step excluded
        self.assertIsNone(ind.induce_from_nav("open spot chart", "binance", trace,
                                              completed=False))
        nid = ind.induce_from_nav("open spot chart", "binance", trace, completed=True)
        n = self.store.get(nid)
        self.assertIn("Trade menu", n.body)
        self.assertIn("Spot", n.body)
        self.assertNotIn("search box", n.body)                  # only OK steps
        self.assertEqual(n.stats["wins"], 1)

    def test_induction_feeds_the_evolver_end_to_end(self):
        # a recipe that wins once then loses repeatedly → underperformer WITH failure traces
        ind.induce_from_trade(strategy="rsi_cross", regime="trend", direction="long",
                              win=True, net_pnl=5.0)
        for _ in range(4):
            ind.induce_from_trade(strategy="rsi_cross", regime="trend", direction="long",
                                  win=False, net_pnl=-3.0)
        nid = ind._key("trade", "rsi_cross", "trend", "long")
        n = self.store.get(nid)
        self.assertLess(n.confidence, 0.5)                      # below the VARY floor
        self.assertGreaterEqual(n.stats["wins"] + n.stats["losses"], 5)
        self.assertTrue(InstructionEngine(self.store).traces(nid))   # loss left a trace
        # the evolver now has real material: it mutates this induced underperformer
        out = InstructionEvolver(InstructionEngine(self.store)).evolve_once()
        varied_parents = [v["parent"] for v in out["varied"]]
        self.assertIn(nid, varied_parents)                      # induction → evolution proven


if __name__ == "__main__":
    unittest.main()
