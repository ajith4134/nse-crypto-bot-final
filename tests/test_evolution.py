"""Tests for trading/brain/evolution.py — the instruction evolution loop (R8/R9/R26).

Proves the requirement the operators alone cannot: a mutated child that measurably beats
its parent on graded evidence is auto-promoted and the parent retired, with lineage kept.
All offline/deterministic (llm=None) — the deterministic trace-derived mutation path.
"""
import json
import tempfile
import unittest
from unittest import mock

from memory.neurons import NeuronStore
from trading import state
from trading.brain.evolution import (CONF_FLOOR, MIN_EVIDENCE, InstructionEvolver)
from trading.brain.instructions import InstructionEngine


def _fake_llm(reply=None):
    return lambda prompt: json.dumps(reply) if reply else None


class EvolutionTest(unittest.TestCase):
    def setUp(self):
        self.tmp_state = tempfile.mkdtemp()
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.tmp_state))
        p.start()
        self.addCleanup(p.stop)
        self.store = NeuronStore(tempfile.mkdtemp())
        self.eng = InstructionEngine(self.store, llm=_fake_llm(None))  # deterministic
        self.evo = InstructionEvolver(self.eng)
        # an underperforming original: 1W/4L → confidence 2/7 ≈ 0.286 (< CONF_FLOOR),
        # with a real failure trace so the offline mutation has something to guard against.
        self.parent = self.store.add(
            "instruction", "Enter on RSI cross",
            "1) wait for RSI to cross 30\n2) buy market",
            "Use in a ranging market. Verify: fill confirmed.", auto_link=False)
        self.eng.grade(self.parent.id, success=True, domain="trading")
        for _ in range(4):
            self.eng.grade(self.parent.id, success=False, domain="trading",
                           failure_reason="entered into a downtrend, no trend filter")

    def test_underperformer_is_varied(self):
        self.assertLess(self.store.get(self.parent.id).confidence, CONF_FLOOR)
        out = self.evo.evolve_once()
        self.assertEqual(len(out["varied"]), 1)
        child_id = out["varied"][0]["child"]
        child = self.store.get(child_id)
        self.assertEqual(child.parents, [self.parent.id])        # lineage recorded
        self.assertEqual(child.version, 2)
        self.assertEqual(out["promotions"], [])                  # no evidence yet → no promote

    def test_child_that_beats_parent_is_promoted_parent_retired(self):
        child_id = self.evo.evolve_once()["varied"][0]["child"]
        # the mutation earns its OWN winning record (this is what live consult/grade feeds)
        for _ in range(MIN_EVIDENCE + 1):
            self.eng.grade(child_id, success=True, domain="trading")
        child = self.store.get(child_id)
        self.assertGreater(child.confidence, self.store.get(self.parent.id).confidence)

        out = self.evo.evolve_once()
        self.assertEqual(len(out["promotions"]), 1)
        prom = out["promotions"][0]
        self.assertEqual(prom["child"], child_id)
        self.assertEqual(prom["parent"], self.parent.id)
        self.assertTrue(self.store.get(child_id).stats.get("promoted"))
        self.assertTrue(self.store.get(self.parent.id).stats.get("retired"))
        # parent's retirement is preserved as knowledge, lineage still walks to it
        lineage_ids = [e["id"] for e in self.store.lineage(child_id)]
        self.assertIn(self.parent.id, lineage_ids)

    def test_no_second_child_while_experiment_is_live(self):
        self.evo.evolve_once()                                   # creates one child
        out = self.evo.evolve_once()                             # parent still has live child
        self.assertEqual(out["varied"], [])

    def test_no_mutation_without_evidence(self):
        weak = self.store.add("instruction", "thin", "1) x", "use. verify y",
                              auto_link=False)
        self.eng.grade(weak.id, success=False, domain="trading",
                       failure_reason="lost")                    # only 1 outcome (< MIN_EVIDENCE)
        out = self.evo.evolve_once()
        self.assertNotIn(weak.id, [v["parent"] for v in out["varied"]])

    def test_ledger_persists_proven_lineage(self):
        child_id = self.evo.evolve_once()["varied"][0]["child"]
        for _ in range(MIN_EVIDENCE + 1):
            self.eng.grade(child_id, success=True, domain="trading")
        self.evo.evolve_once()
        st = self.evo.status()
        self.assertEqual(st["proven_lineages"], 1)
        self.assertEqual(st["recent_promotions"][0]["child"], child_id)


if __name__ == "__main__":
    unittest.main()
