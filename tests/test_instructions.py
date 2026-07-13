"""Tests for trading/brain/instructions.py — instruction lifecycle (R7-R9, R26)."""
import json
import tempfile
import unittest
from unittest import mock

from memory.neurons import NeuronStore
from trading import state
from trading.brain.instructions import InstructionEngine, parse_steps


def _fake_llm(reply: dict | None):
    return lambda prompt: json.dumps(reply) if reply else None


class InstructionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp_state = tempfile.mkdtemp()
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.tmp_state))
        p.start()
        self.addCleanup(p.stop)
        self.store = NeuronStore(tempfile.mkdtemp())
        self.n = self.store.add(
            "instruction", "Binance spot nav",
            "1) open binance.com\n2) click Trade\n3) click Spot",
            "Use when a spot chart is needed. Verify: symbol search box visible.",
            auto_link=False)

    def test_follow_parses_steps_and_verify(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        got = eng.follow(self.n.id)
        self.assertEqual(len(got["steps"]), 3)
        self.assertTrue(any("verify" in v.lower() for v in got["verify"]))

    def test_grade_records_traces_and_confidence(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        eng.grade(self.n.id, success=True, domain="navigation")
        eng.grade(self.n.id, success=False, failure_reason="cookie banner blocked click",
                  domain="navigation")
        self.assertEqual(len(eng.traces(self.n.id)), 1)
        self.assertEqual(self.store.get(self.n.id).stats["times_used"], 2)

    def test_edit_uses_llm_when_available(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(
            {"title": "Binance spot nav v2",
             "body": "1) dismiss cookie banner\n2) open binance.com\n3) Trade>Spot",
             "action": "Use for spot charts. Verify: search box visible."}))
        eng.grade(self.n.id, success=False, failure_reason="cookie banner blocked click")
        child = eng.edit(self.n.id)
        self.assertIn("cookie", child.body)
        self.assertEqual(child.parents, [self.n.id])
        self.assertEqual(child.version, 2)

    def test_edit_deterministic_fallback_uses_real_trace(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        eng.grade(self.n.id, success=False, failure_reason="cookie banner blocked click")
        child = eng.edit(self.n.id)
        self.assertIn("cookie banner blocked click", child.body.lower())

    def test_edit_refuses_without_evidence(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        self.assertIsNone(eng.edit(self.n.id))       # no traces, no feedback → no edit

    def test_crossover_deterministic_splice(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        other = self.store.add(
            "instruction", "Binance nav with captcha handling",
            "1) open binance.com\n2) if captcha appears trigger handoff\n3) click Trade",
            "Use when captchas are frequent. Verify: no challenge visible.",
            auto_link=False)
        child = eng.crossover(self.n.id, other.id)
        steps = parse_steps(child.body)
        self.assertIn(self.n.id, child.parents)
        self.assertIn(other.id, child.parents)
        self.assertTrue(any("captcha" in s for s in steps))   # B's unique step spliced
        self.assertEqual(len(steps), len(set(s.lower() for s in steps)))  # deduped

    def test_spawn_and_retire(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        sib = eng.spawn(self.n.id, "Upstox web app")
        self.assertIn("Upstox", sib.title)
        out = eng.retire(self.n.id, "superseded by guarded v2")
        self.assertTrue(self.store.get(self.n.id).stats["retired"])
        lesson = self.store.get(out["lesson"])
        self.assertIn("superseded", lesson.body)
        self.assertTrue(eng.follow(self.n.id)["retired"])     # follow refuses retired

    def test_pareto_archive_non_dominated(self):
        eng = InstructionEngine(self.store, llm=_fake_llm(None))
        strong = self.store.add("instruction", "strong", "1) x", "use. verify y",
                                auto_link=False)
        for _ in range(5):
            eng.grade(strong.id, success=True)
        weak = self.store.add("instruction", "weak", "1) x", "use. verify y",
                              auto_link=False)
        eng.grade(weak.id, success=False, failure_reason="lost")
        ids = [e["id"] for e in eng.pareto_archive()]
        self.assertIn(strong.id, ids)
        self.assertNotIn(weak.id, ids)                        # dominated by strong


if __name__ == "__main__":
    unittest.main()
