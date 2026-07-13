"""Tests for trading/brain/self_evaluation.py (R3, R22, R23, R28, time horizon)."""
import tempfile
import unittest
from unittest import mock

from memory.neurons import NeuronStore
from trading import state
from trading.brain.self_evaluation import GAP_SECS, SelfEvaluation


class _FakeLibrarian:
    def discover(self, topic, max_per=5):
        return [{"title": f"{topic} explained", "url": "https://x/1",
                 "text": f"A thorough explanation of {topic}: the mechanism depends on "
                         f"liquidity and participation, and reverses when flows fade."},
                {"title": f"{topic} pitfalls", "url": "https://x/2",
                 "text": f"Common pitfalls when applying {topic}: overfitting the "
                         f"threshold and ignoring the regime context."}]


class SelfEvaluationTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(state, "STATE_DIR",
                              type(state.STATE_DIR)(tempfile.mkdtemp()))
        p.start()
        self.addCleanup(p.stop)
        self.store = NeuronStore(tempfile.mkdtemp())

    def test_independent_learning_r3(self):
        ev = SelfEvaluation(self.store, llm=lambda p: None,
                            librarian=_FakeLibrarian())
        r = ev.independent_learning_test("kyle lambda impact")
        self.assertTrue(r["ok"])
        self.assertEqual(r["neurons_created"], 2)
        instr = self.store.get(r["instruction"])
        self.assertEqual(instr.kind, "instruction")
        self.assertTrue(any(l["rel"] == "derived-from" for l in instr.links))
        self.assertIsNotNone(r["quiz_score"])          # quizzed on what it learned

    def test_independent_learning_refuses_known_topic(self):
        self.store.add("fact", "RSI oversold", "RSI below 30 marks oversold zones "
                       "in ranging markets for liquid symbols.",
                       "Use RSI<30 with regime filter.", auto_link=False)
        ev = SelfEvaluation(self.store, llm=lambda p: None,
                            librarian=_FakeLibrarian())
        r = ev.independent_learning_test("RSI oversold")
        self.assertFalse(r["ok"])                      # not a zero-knowledge topic

    def test_genius_use_counts_all_domains_r22(self):
        n1 = self.store.add("fact", "vp value area", "b" * 50, "act", auto_link=False)
        n2 = self.store.add("instruction", "nav route", "1) x", "act", auto_link=False)
        self.store.record_use(n1.id, win=True, domain="trading")
        self.store.record_use(n2.id, win=True, domain="navigation")
        out = SelfEvaluation(self.store, llm=lambda p: None).genius_use()
        self.assertEqual(set(out["by_domain"]), {"trading", "navigation"})
        self.assertEqual(out["neurons_ever_used"], 2)

    def test_llm_parity_r23(self):
        for i in range(4):
            self.store.add("fact", f"gamma exposure pinning {i}",
                           "Dealer gamma exposure near large strikes pins price into "
                           "expiry as hedging flows dampen movement around the strike.",
                           "Near big OI strikes into expiry, expect pinning: fade moves "
                           "away from the strike and verify with dealer positioning data.",
                           auto_link=False)
        ev = SelfEvaluation(self.store,
                            llm=lambda p: "fade moves near strike into expiry and "
                                          "verify dealer positioning")
        out = ev.llm_parity(n=4)
        self.assertTrue(out["ok"])
        self.assertIsInstance(out["brain_score"], float)
        self.assertIsInstance(out["llm_score"], float)
        self.assertIn(out["parity"], (True, False))
        out2 = ev.llm_parity(n=4)                      # persisted report merged
        self.assertTrue((state.load_json("self_evaluation.json", {}) or {})["llm_parity"])

    def test_time_horizon_from_heartbeats(self):
        t0 = 1_000_000.0
        events = [{"ts": t0 + i * 60} for i in range(10)]          # 9min run
        events += [{"ts": t0 + 5000 + i * 60} for i in range(5)]   # gap then 4min run
        state.save_json("mind_events.json", {"events": events})
        out = SelfEvaluation(self.store, llm=lambda p: None).time_horizon(
            now=t0 + 5000 + 4 * 60 + 30)
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["longest_run_secs"], 540)
        self.assertEqual(out["runs"], 2)
        self.assertLess(out["last_event_age_secs"], GAP_SECS)

    def test_accumulation_r28(self):
        self.store.add("fact", "alpha", "b" * 50, "act", auto_link=False)
        state.save_json("school.json", {"exams": [
            {"level": "L0", "track_a": {"score": 0.9}},
            {"level": "L0", "track_a": {"score": 0.6}},
        ]})
        out = SelfEvaluation(self.store, llm=lambda p: None).accumulation()
        self.assertTrue(out["exam_trends"]["L0"]["decayed"])       # honest decay flag
        self.assertGreaterEqual(out["neurons_last7d"], 1)


if __name__ == "__main__":
    unittest.main()
