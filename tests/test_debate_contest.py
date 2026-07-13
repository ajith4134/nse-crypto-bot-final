"""Tests for debate_gate.contest() — the debate as a DIRECTIONAL contest (proposal E)."""
import unittest
from unittest import mock

from trading.brain.debate_gate import DebateGate


def _assess(verdict, flip, reward):
    return lambda symbol, direction, features=None: {
        "approved": verdict == "yes", "confidence": 0.5,
        "decision_snapshot": {"debate_verdict": verdict, "flip_rate": flip,
                              "process_reward": reward, "arguments": {"bull": "up thesis",
                                                                      "bear": "down thesis"}}}


class DebateContestTest(unittest.TestCase):
    def setUp(self):
        self.g = DebateGate()
        self.g._contest_cache.clear()

    def test_strong_yes_on_long_is_long(self):
        with mock.patch.object(self.g, "assess", _assess("yes", 0.0, 1.0)):   # unanimous, verified
            c = self.g.contest("BTCUSDT", "long")
        self.assertEqual(c["direction"], "long")
        self.assertGreater(c["p_up"], 0.9)                    # consensus×reward = strong long

    def test_rejected_long_flips_to_short(self):
        with mock.patch.object(self.g, "assess", _assess("no", 0.0, 1.0)):    # debate rejects long
            c = self.g.contest("BTCUSDT", "long")
        self.assertEqual(c["direction"], "short")             # rejection → other side
        self.assertLess(c["p_up"], 0.1)

    def test_short_proposal_yes_is_short(self):
        with mock.patch.object(self.g, "assess", _assess("yes", 0.0, 1.0)):
            c = self.g.contest("ETHUSDT", "short")
        self.assertEqual(c["direction"], "short")
        self.assertLess(c["p_up"], 0.1)

    def test_split_room_is_neutral(self):
        with mock.patch.object(self.g, "assess", _assess("yes", 1.0, 1.0)):   # maximally split
            c = self.g.contest("BTCUSDT", "long")
        self.assertEqual(c["direction"], "neutral")           # no conviction → neutral (no drive)
        self.assertAlmostEqual(c["p_up"], 0.5, delta=0.05)

    def test_cached_within_ttl(self):
        calls = []
        def _a(symbol, direction, features=None):
            calls.append(1)
            return {"decision_snapshot": {"debate_verdict": "yes", "flip_rate": 0.0,
                                          "process_reward": 1.0, "arguments": {}}}
        with mock.patch.object(self.g, "assess", _a):
            self.g.contest("BTCUSDT", "long")
            self.g.contest("BTCUSDT", "long")                 # within 60s → cached
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
