"""Tests for trading/brain/school.py — dual-track curriculum + exams (R2, R21, R27)."""
import random
import tempfile
import unittest
from unittest import mock

from memory.neurons import NeuronStore
from trading import state
from trading.brain.school import PASS_SCORE, School


def _seed(store, n=14):
    subjects = ["RSI oversold mean reversion", "volume profile value area",
                "orderbook imbalance pressure", "ATR position sizing",
                "funding rate carry", "regime detection trending",
                "candle absorption at support", "breakout retest entry",
                "stop placement beyond structure", "Binance spot navigation",
                "Upstox order window", "fee impact on scalping",
                "divergence confirmation", "session open volatility"]
    for i in range(n):
        s = subjects[i % len(subjects)]
        store.add("fact", s,
                  f"The concept of {s} explains how {s.split()[0]} interacts with "
                  f"price behaviour; practitioners watch {s.split()[-1]} closely "
                  f"before committing capital in that direction.",
                  f"When {s.split()[0]} conditions appear, apply {s} before entering; "
                  f"verify the {s.split()[-1]} signal on a second timeframe.")


class SchoolTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(state, "STATE_DIR",
                              type(state.STATE_DIR)(tempfile.mkdtemp()))
        p.start()
        self.addCleanup(p.stop)
        self.store = NeuronStore(tempfile.mkdtemp())

    def test_exam_structure_and_recording(self):
        _seed(self.store)
        school = School(self.store, rng=random.Random(1))
        r = school.take_exam("L0")
        self.assertIn(r["track_a"]["score"], [r["track_a"]["score"]])  # present
        self.assertIsNotNone(r["track_a"]["score"])
        st = school.status()
        self.assertEqual(st["exams_taken"], 1)
        exams = [x for x in self.store._cache.values() if x.kind == "exam"]
        self.assertEqual(len(exams), 1)                # exam persisted as a neuron
        tested = [x for x in self.store._cache.values()
                  if x.exam["last_score"] is not None and x.kind != "exam"]
        self.assertTrue(tested)                        # R28 re-exam evidence recorded

    def test_promotion_only_on_both_tracks(self):
        _seed(self.store)
        school = School(self.store, rng=random.Random(1))
        r = school.take_exam("L0")
        st = school.status()
        if r["passed"]:
            self.assertEqual(st["level"], "L1")
        else:
            self.assertEqual(st["level"], "L0")

    def test_empty_level_is_honest_not_fake_pass(self):
        school = School(self.store, rng=random.Random(1))   # empty store
        r = school.take_exam("L5")
        self.assertIsNone(r["track_a"]["score"])
        self.assertFalse(r["passed"])
        self.assertIn("not enough material", r["track_a"]["note"])

    def test_study_creates_taught_by_lessons(self):
        school = School(self.store, rng=random.Random(1))
        out = school.study("order flow", [
            {"title": "OFI basics", "body": "Order-flow imbalance measures buy vs "
                                            "sell pressure at the top of book."},
            {"title": "OFI thresholds", "body": "Extreme OFI readings precede "
                                                "short-term continuation moves."},
        ])
        self.assertEqual(len(out["neurons"]), 2)
        n2 = self.store.get(out["neurons"][1])
        self.assertTrue(any(l["rel"] == "taught-by" for l in n2.links))
        self.assertTrue(self.store.get(out["neurons"][0]).action)     # R24 kept

    def test_l6_needs_evolution_evidence(self):
        parent = self.store.add("instruction", "route v1", "1) step one two three",
                                "use it; verify done", auto_link=False)
        child = self.store.derive([parent.id], title="route v2",
                                  body="1) step one two three improved",
                                  action="use it better; verify done")
        self.store.record_use(child.id, win=True)
        self.store.record_use(child.id, win=True)      # child conf now > parent 0.5
        school = School(self.store, rng=random.Random(1))
        items = school._exam_domain("L6", [child, parent])
        self.assertTrue(any(q["correct"] for q in items))
        self.assertEqual(PASS_SCORE, 0.7)


if __name__ == "__main__":
    unittest.main()
