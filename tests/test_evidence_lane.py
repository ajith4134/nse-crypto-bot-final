"""W3 evidence lane tests — isolated STATE_DIR, synthetic cycles."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


def _sig(direction="long", price=100.0):
    return {"available": True, "direction": direction,
            "barriers": {"entry": price}, "p_up": 0.7}


class EvidenceLaneTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._patch = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_observe_records_baseline_and_skips(self):
        from trading import evidence
        r = evidence.observe_cycle(market="crypto", segment="futures",
                                   signals={"BTC/USDT:USDT": _sig(),
                                            "ETH/USDT:USDT": _sig("short", 50.0),
                                            "FLAT/USDT:USDT": _sig("neutral")},
                                   entered=["BTC/USDT:USDT"])
        self.assertEqual(r["baseline_opened"], 2)      # both non-neutral
        self.assertEqual(r["skips_recorded"], 1)       # ETH skipped
        st = evidence.status()
        seg = st["segments"]["crypto.futures"]
        self.assertEqual(seg["skips"]["n"], 1)
        self.assertEqual(seg["baseline"]["verdict"], "no-data")   # unresolved yet

    def test_counterfactual_resolution_verdicts(self):
        from trading import state, evidence
        evidence.observe_cycle(market="crypto", segment="futures",
                               signals={"X/USDT:USDT": _sig("long", 100.0)}, entered=[])
        d = state.load_json("evidence_lane.json", {})
        # time-travel the skip 25h into the past and plant snapshots near each horizon
        s = d["skips"][0]
        t0 = time.time() - 25 * 3600
        s["ts"] = t0
        s["snaps"] = [[t0 + 3600, 103.0], [t0 + 6 * 3600, 105.0], [t0 + 24 * 3600, 108.0]]
        d["baseline"][0]["ts"] = t0
        d["baseline"][0]["snaps"] = s["snaps"]
        state.save_json("evidence_lane.json", d)
        evidence.observe_cycle(market="crypto", segment="futures",
                               signals={"X/USDT:USDT": _sig("long", 108.0)}, entered=[])
        d2 = state.load_json("evidence_lane.json", {})
        sk = [s for s in d2["skips"] if s.get("resolved")][0]
        self.assertEqual(sk["verdict"], "bad-skip (missed winner)")   # +8% ran away
        self.assertAlmostEqual(sk["outcomes"]["h24"], 8.0, places=1)
        base = [b for b in d2["baseline"] if b.get("resolved")]
        self.assertTrue(base)

    def test_autonomy_gates_shape(self):
        from trading import evidence
        g = evidence.autonomy_gates("crypto", "futures")
        self.assertIn("all_pass", g)
        self.assertEqual(set(g["gates"]) ,
                         {"paper_days_30_positive", "min_100_trades",
                          "beats_blind_baseline", "no_recent_data_failures",
                          "drawdown_sane"})
        self.assertFalse(g["all_pass"])                # empty state can't pass

    def test_data_failures_gate(self):
        from trading import evidence
        evidence.record_data_failure("test-source", "boom")
        g = evidence.autonomy_gates("crypto", "futures")
        self.assertFalse(g["gates"]["no_recent_data_failures"])


if __name__ == "__main__":
    unittest.main()
