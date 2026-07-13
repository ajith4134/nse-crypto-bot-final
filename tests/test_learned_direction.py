"""Tests for trading/direction/learned_direction.py — the learned direction driver.

The decider must: trust proven-good sources, INVERT proven-wrong ones, zero out near-random
ones, and ABSTAIN when nothing has a measured edge. Reliability is injected (monkeypatched)
so the tests are deterministic and independent of the live truth-ledger aggregate.
"""
import unittest

from trading.direction import learned_direction as ld


def _rel(rate, n, half_ci=0.05):
    """Fake a truth_ledger.source_reliability() row with a symmetric CI of width 2*half_ci."""
    if n == 0 or rate is None:
        return {"n": n, "correct": 0, "rate": None, "ci_low": None,
                "ci_high": None, "edge": None}
    return {"n": n, "correct": int(round(rate * n)), "rate": rate,
            "ci_low": max(0.0, rate - half_ci), "ci_high": min(1.0, rate + half_ci),
            "edge": rate - 0.5}


class LearnedDirectionTest(unittest.TestCase):
    def setUp(self):
        ld.clear_cache()
        self._table = {}

        def fake_reliability(source, *, market=None, regime=None, min_n=1):
            return self._table.get(source, _rel(None, 0))

        self._orig = ld._tl.source_reliability
        ld._tl.source_reliability = fake_reliability

    def tearDown(self):
        ld._tl.source_reliability = self._orig
        ld.clear_cache()

    def _set(self, source, rate, n, half_ci=0.05):
        self._table[source] = _rel(rate, n, half_ci)
        ld.clear_cache()

    # ── weighting ────────────────────────────────────────────────────────────────
    def test_proven_good_source_drives_its_side(self):
        self._set("funding_extreme", 0.58, 300, half_ci=0.03)   # tight CI, real edge
        out = ld.decide([("funding_extreme", 0.8)])             # says LONG
        self.assertEqual(out["direction"], "long")
        self.assertFalse(out["abstained"])
        self.assertGreater(out["confidence"], 0.0)
        self.assertFalse(out["weights"]["funding_extreme"]["invert"])

    def test_proven_wrong_source_is_inverted(self):
        # a source that's right only 32% of the time, saying LONG (0.85), must push SHORT
        self._set("funnel_mtf_vote", 0.32, 400, half_ci=0.04)
        out = ld.decide([("funnel_mtf_vote", 0.85)])
        self.assertTrue(out["weights"]["funnel_mtf_vote"]["invert"])
        self.assertEqual(out["direction"], "short")

    def test_near_random_source_earns_no_weight_and_abstains(self):
        self._set("funnel_mtf_vote", 0.49, 12000, half_ci=0.01)  # measured, but ~coin flip
        out = ld.decide([("funnel_mtf_vote", 0.9)])
        self.assertEqual(out["weights"]["funnel_mtf_vote"]["w"], 0.0)
        self.assertTrue(out["abstained"])
        self.assertEqual(out["direction"], "neutral")

    def test_unproven_source_gets_only_tiny_weight(self):
        self._set("brand_new_lens", 0.9, 5)                      # n below min_n
        out = ld.decide([("brand_new_lens", 0.95)])
        w = out["weights"]["brand_new_lens"]["w"]
        self.assertLessEqual(w, ld._cfg()["unproven_w"])

    def test_good_lens_outweighs_random_vote(self):
        self._set("funnel_mtf_vote", 0.47, 12000, half_ci=0.01)  # ~0 weight
        self._set("venue_leadlag", 0.60, 300, half_ci=0.03)      # real edge, says SHORT
        out = ld.decide([("funnel_mtf_vote", 0.8), ("venue_leadlag", 0.2)])
        self.assertEqual(out["direction"], "short")

    def test_abstain_when_no_readings(self):
        out = ld.decide([])
        self.assertTrue(out["abstained"])
        self.assertEqual(out["direction"], "neutral")

    def test_none_p_up_is_skipped(self):
        self._set("funding_extreme", 0.58, 300, half_ci=0.03)
        out = ld.decide([("funding_extreme", None), ("funding_extreme", 0.8)])
        self.assertEqual(out["direction"], "long")

    # ── learned_vote drop-in ──────────────────────────────────────────────────────
    def test_learned_vote_inverts_trend_anti_vote(self):
        self._set("funnel_mtf_vote", 0.38, 200, half_ci=0.04)   # trend anti-signal
        chart = {"15m": {"p_up": 0.75, "source": "fast"},
                 "1h": {"p_up": 0.72, "source": "fast"}}
        direction, p = ld.learned_vote(chart, regime="trend_up")
        self.assertEqual(direction, "short")                    # long vote → inverted to short
        self.assertLess(p, 0.5)

    def test_learned_vote_abstains_on_random_vote(self):
        self._set("funnel_mtf_vote", 0.49, 12000, half_ci=0.01)
        chart = {"15m": {"p_up": 0.8, "source": "fast"}}
        direction, p = ld.learned_vote(chart)
        self.assertEqual(direction, "neutral")

    def test_learned_vote_empty_chart(self):
        self.assertEqual(ld.learned_vote({}), ("neutral", 0.5))
        chart = {"15m": {"p_up": 0.9, "source": "unavailable"}}
        self.assertEqual(ld.learned_vote(chart), ("neutral", 0.5))

    # ── correct_direction (Reflex/pullback lane) ──────────────────────────────────
    def test_correct_direction_inverts_reliably_wrong_source(self):
        self._set("pullback", 0.32, 400, half_ci=0.04)          # proven wrong
        newd, info = ld.correct_direction("LONG", source="pullback")
        self.assertEqual(newd, "SHORT")
        self.assertEqual(info["action"], "invert")

    def test_correct_direction_keeps_good_source(self):
        self._set("pullback", 0.60, 300, half_ci=0.03)          # proven right
        newd, info = ld.correct_direction("LONG", source="pullback")
        self.assertEqual(newd, "LONG")
        self.assertEqual(info["action"], "pass")

    def test_correct_direction_keeps_unproven_source_never_skips(self):
        self._set("pullback", 0.30, 8)                          # too few samples
        newd, info = ld.correct_direction("SHORT", source="pullback")
        self.assertEqual(newd, "SHORT")                          # never inverts on thin data
        self.assertEqual(info["action"], "pass")

    def test_correct_direction_near_random_source_keeps(self):
        self._set("pullback", 0.49, 12000, half_ci=0.01)        # significant but ~coin flip
        newd, info = ld.correct_direction("LONG", source="pullback")
        self.assertEqual(newd, "LONG")                          # no significant edge → keep
        self.assertEqual(info["action"], "pass")

    def test_correct_direction_passes_non_directional(self):
        newd, info = ld.correct_direction("FLAT", source="pullback")
        self.assertEqual(info["action"], "pass")


if __name__ == "__main__":
    unittest.main()
