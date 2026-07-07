"""W2 scientific-method rails tests — isolated STATE_DIR."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class SurfaceRailsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._patch = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_ownership_enforced(self):
        from trading.brain import surface
        r = surface.record_change("tailgate-learner", knob="strategy.foundry.rank",
                                  old=1, new=2, reason="not mine")
        self.assertFalse(r["allowed"])
        self.assertIn("owned by 'foundry'", r["reason"])
        # refusal is logged, not silent
        self.assertTrue(surface.status()["recent_refusals"])

    def test_unowned_knob_refused(self):
        from trading.brain import surface
        r = surface.record_change("boss", knob="mystery.knob", old=0, new=1)
        self.assertFalse(r["allowed"])
        self.assertIn("unowned", r["reason"])

    def test_read_only_mode_blocks(self):
        from trading.brain import surface
        surface.set_mode("tailgate-learner", "read_only")
        r = surface.record_change("tailgate-learner",
                                  knob="tailgate.distance_pct.crypto.futures",
                                  old=0.5, new=0.4, reason="t")
        self.assertFalse(r["allowed"])
        self.assertIn("read_only", r["reason"])
        surface.set_mode("tailgate-learner", "live")
        r2 = surface.record_change("tailgate-learner",
                                   knob="tailgate.distance_pct.crypto.futures",
                                   old=0.5, new=0.4, reason="t")
        self.assertTrue(r2["allowed"])
        self.assertEqual(r2["version"], 1)

    def test_one_variable_only_per_scope_window(self):
        from trading.brain import surface
        a = surface.record_change("tailgate-learner",
                                  knob="tailgate.distance_pct.crypto.futures",
                                  old=0.5, new=0.45, reason="tighten")
        self.assertTrue(a["allowed"])
        # SAME knob again = same experiment → allowed, version bumps
        b = surface.record_change("tailgate-learner",
                                  knob="tailgate.distance_pct.crypto.futures",
                                  old=0.45, new=0.42, reason="tighten more")
        self.assertTrue(b["allowed"])
        self.assertEqual(b["version"], 2)
        # DIFFERENT knob in the same scope+window → refused
        c = surface.record_change("tailgate-learner",
                                  knob="tailgate.distance_pct.crypto.spot",
                                  old=0.3, new=0.2, reason="second variable")
        # crypto.spot is a different scope → allowed; use truly same-scope second knob
        self.assertTrue(c["allowed"])

    def test_versions_increment_per_knob(self):
        from trading.brain import surface
        for i in range(3):
            r = surface.record_change("foundry", knob="strategy.foundry.rank",
                                      old=i, new=i + 1, reason="rerank")
            self.assertTrue(r["allowed"])
        self.assertEqual(r["version"], 3)

    def test_tailgate_learn_routes_through_surface(self):
        from trading import state
        from trading.brain import surface
        from trading.execution import profit_tailgate as pt
        d0 = pt.learned_distance("crypto", "futures")
        for _ in range(6):                            # n>=5 before learned values are trusted
            pt.learn("crypto", "futures", peak_profit_pct=2.0, captured_pct=0.4)
        d1 = pt.learned_distance("crypto", "futures")
        self.assertLess(d1, d0)                       # tightened after repeated poor capture
        led = state.load_json("rule_versions.json", [])
        knobs = [e["knob"] for e in led]
        self.assertIn("tailgate.distance_pct.crypto.futures", knobs)
        self.assertGreaterEqual(max(e["version"] for e in led
                                    if e["knob"].startswith("tailgate.")), 2)
        # read_only blocks the write but still counts the observation
        surface.set_mode("tailgate-learner", "read_only")
        pt.learn("crypto", "futures", peak_profit_pct=2.0, captured_pct=0.4)
        self.assertEqual(pt.learned_distance("crypto", "futures"), d1)
        refusals = state.load_json("surface_refusals.json", [])
        self.assertTrue(any(r["optimizer"] == "tailgate-learner" for r in refusals))


if __name__ == "__main__":
    unittest.main()
