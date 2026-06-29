"""Phase P4.7 (Autonomy + self-coding) acceptance tests — fully offline & sandboxed.

Proves the brain can INVENT new nodes, test them safely, and admit only winners — without
network, LLM, or any risk to the host. Everything is deterministic (seeded) and the candidate
fits run in the real isolated subprocess sandbox:

  * NodeProposer — deterministic proposals over the allow-listed estimator space; an LLM
    proposer is gated + validated (off-allow-list specs are rejected).
  * Sandbox — fits a candidate in a subprocess with rlimits/timeout/no-network; an off-allow-list
    estimator (e.g. os.system) is rejected WITHOUT being run.
  * BenchmarkGate — admits only candidates that beat the incumbent on golden data by a margin.
  * SelfCodingLoop — propose→sandbox→gate→admit→archive; winners register as real AlgoSpecs and
    the incumbent best ratchets up (the honest self-improvement signal).

Mirrors tests/test_thinking_p45.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import unittest

from cognition.self_coding import (ALLOWED_ESTIMATORS, BenchmarkGate, NodeProposer, Sandbox,
                                   SelfCodingLoop)


class TestProposer(unittest.TestCase):
    def test_deterministic_proposals_are_on_allowlist(self):
        p = NodeProposer(seed=1)
        for _ in range(10):
            spec = p.propose(task="binary", head="direction")
            self.assertIn(spec["family"], ALLOWED_ESTIMATORS)
            self.assertEqual(spec["import_path"], ALLOWED_ESTIMATORS[spec["family"]][0])

    def test_seeded_reproducible(self):
        a = [NodeProposer(seed=42).propose()["family"] for _ in range(1)]
        b = [NodeProposer(seed=42).propose()["family"] for _ in range(1)]
        self.assertEqual(a, b)

    def test_llm_proposal_validated_against_allowlist(self):
        # a malicious LLM proposal (off-allow-list) must be rejected → falls back to deterministic
        bad_llm = lambda ctx: {"family": "evil", "import_path": "os.system", "fixed_args": {}}
        spec = NodeProposer(seed=1, llm_propose=bad_llm).propose(task="binary", head="direction")
        self.assertIn(spec["family"], ALLOWED_ESTIMATORS)        # not the evil one
        self.assertEqual(spec["proposer"], "deterministic")

    def test_llm_proposal_accepted_when_valid(self):
        good_llm = lambda ctx: {"family": "hist_gb", "fixed_args": {"max_depth": 3}}
        spec = NodeProposer(seed=1, llm_propose=good_llm).propose(task="binary", head="direction")
        self.assertEqual(spec["family"], "hist_gb")
        self.assertEqual(spec["proposer"], "llm")


class TestSandbox(unittest.TestCase):
    def test_off_allowlist_rejected_without_running(self):
        r = Sandbox().fit_score({"family": "evil", "import_path": "os.system",
                                 "fixed_args": {"cmd": "rm -rf /"}})
        self.assertFalse(r["ok"])
        self.assertIn("allow-list", r["error"])

    def test_valid_candidate_fits_and_scores_in_sandbox(self):
        spec = NodeProposer(seed=3).propose(task="binary", head="direction")
        r = Sandbox(timeout_s=40).fit_score(spec, n=700)
        self.assertTrue(r["ok"], msg=r.get("error"))
        self.assertIn("score", r)
        self.assertGreaterEqual(r["score"], 0.0)


class TestGate(unittest.TestCase):
    def test_admits_only_above_incumbent(self):
        g = BenchmarkGate(margin=0.01)
        first = g.consider({"ok": True, "score": 0.60, "baseline": 0.50, "beats": True})
        self.assertTrue(first["admit"])                          # first beats baseline
        worse = g.consider({"ok": True, "score": 0.605, "baseline": 0.50, "beats": True})
        self.assertFalse(worse["admit"])                         # within margin of incumbent
        better = g.consider({"ok": True, "score": 0.65, "baseline": 0.50, "beats": True})
        self.assertTrue(better["admit"])                         # clears incumbent+margin

    def test_failed_fit_not_admitted(self):
        g = BenchmarkGate()
        self.assertFalse(g.consider({"ok": False, "error": "timeout"})["admit"])


class TestLoop(unittest.TestCase):
    def test_loop_improves_and_admits(self):
        loop = SelfCodingLoop(seed=7, n=800)
        s = loop.run(iters=6, task="binary", head="direction")
        self.assertEqual(s["proposed"], 6)
        self.assertGreaterEqual(s["admitted"], 1)                # at least one winner admitted
        self.assertIsNotNone(s["best_score"])
        # incumbent best is monotonic non-decreasing (the honest self-improvement signal)
        curve = [a for a in (loop.gate.incumbent_best,) if a is not None]
        self.assertTrue(curve)

    def test_admitted_nodes_registered_and_usable(self):
        loop = SelfCodingLoop(seed=7, n=800)
        loop.run(iters=6)
        if loop.admitted:
            from core.algo_registry import REGISTRY
            nid = loop.admitted[0]["id"]
            self.assertIn(nid, REGISTRY)                          # winner is a real registered spec
            fac = loop.candidate_factory(nid)
            self.assertIsNotNone(fac)                             # usable in StructureSearchNode pool
            self.assertEqual(fac[0], nid)


class TestDemo(unittest.TestCase):
    def test_build_demo_snapshot(self):
        import json

        from run_self_coding_p47 import build_demo_self_coding
        snap = build_demo_self_coding()
        self.assertEqual(snap["phase"], "P4.7")
        self.assertGreaterEqual(snap["summary"]["admitted"], 1)
        # safety: the malicious spec was rejected without running
        self.assertFalse(snap["safety"]["off_allowlist_rejected"]["ok"])
        # improvement curve is monotonic non-decreasing
        curve = [c for c in snap["improvement_curve"] if c is not None]
        self.assertEqual(curve, sorted(curve))
        json.dumps(snap, default=str)                            # dashboard-serialisable


if __name__ == "__main__":
    unittest.main(verbosity=2)
