"""Tests for trading/brain/apply.py — applying instruction neurons in the decision path."""
import tempfile
import unittest
from unittest import mock

import trading.brain.apply as ap
from memory import neurons as neurons_mod
from memory.neurons import NeuronStore
from trading.brain.instructions import InstructionEngine


class _RNG:
    """Deterministic stand-in: fixed random() value, choice() takes the first item."""
    def __init__(self, r): self._r = r
    def random(self): return self._r
    def choice(self, seq): return seq[0]


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.store = NeuronStore(tempfile.mkdtemp())
        gp = mock.patch.object(neurons_mod, "_STORE", self.store)
        gp.start(); self.addCleanup(gp.stop)
        self.eng = InstructionEngine(self.store)
        # a well-evidenced winning recipe (high confidence)
        self.good = self.store.add("instruction", "Enter long in range via vp",
                                   "1) x", "use when vp fires. verify fill", auto_link=False)
        for _ in range(6):
            self.eng.grade(self.good.id, success=True, domain="trading")
        # a weaker recipe, same context
        self.weak = self.store.add("instruction", "Enter long in range via rsi",
                                   "1) y", "use when rsi crosses. verify", auto_link=False)
        for _ in range(4):
            self.eng.grade(self.weak.id, success=False, domain="trading")

    def test_exploit_picks_highest_confidence(self):
        out = ap.select("enter long in range", explore=0.0, rng=_RNG(0.9))
        self.assertEqual(out["id"], self.good.id)                # best known recipe
        self.assertGreater(out["confidence"], 0.6)

    def test_tilt_is_bounded(self):
        out = ap.select("enter long in range", explore=0.0, rng=_RNG(0.9))
        self.assertLessEqual(abs(out["tilt"]), ap.TILT_CAP)      # never exceeds the cap

    def test_explore_gives_a_fresh_variant_evidence(self):
        # a freshly-evolved child (no evidence yet) must be reachable so it can be graded
        child = self.store.derive([self.good.id], title="Enter long in range via vp (guarded)",
                                  body="1) x\n2) guard", action="use when vp fires. verify")
        out = ap.select("enter long in range", explore=1.0, rng=_RNG(0.0))  # force explore
        under = out["id"]
        n = self.store.get(under)
        self.assertLess(n.stats.get("wins", 0) + n.stats.get("losses", 0),
                        ap.MIN_EVIDENCE)                         # chose an under-evidenced one
        self.assertIn(under, {child.id, self.weak.id})

    def test_no_match_returns_none(self):
        self.assertIsNone(ap.select("navigate binance spot", explore=0.0, rng=_RNG(0.9)))

    def test_retired_is_excluded(self):
        self.eng.retire(self.good.id, "test")
        out = ap.select("enter long in range", explore=0.0, rng=_RNG(0.9))
        self.assertNotEqual(out["id"], self.good.id)            # retired never applied


if __name__ == "__main__":
    unittest.main()
