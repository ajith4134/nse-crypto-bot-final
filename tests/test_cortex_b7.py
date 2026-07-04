"""CORTEX B7 tests — run_network.py generator + /api/network/* server helpers.

The generator is exercised as a real SUBPROCESS on the tiny pool
(ML_NETWORK_TINY=1) writing to a temp path (never the repo's live
network_state.json), then the JSON schema is validated: honest edge weights
(finite, in [0,1]), column/segment/stage/tier on every node, reflex compute
stats present. Server routes are covered via their PURE helper functions
(_network_state_payload / _network_trust_payload / _network_refresh_allowed) —
the test_scorecard.py spec-load pattern.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "dash_server_b7_test", os.path.join(_ROOT, "dashboard", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunNetwork(unittest.TestCase):
    """run_network.py produces a valid network_state.json on a tiny pool."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.tmp.name, "network_state.json")
        env = dict(os.environ,
                   ML_NETWORK_TINY="1",
                   ML_NETWORK_STATE_PATH=cls.out,
                   # isolate trust state — never touch the live ledger
                   MLNB_TRUST_PATH=os.path.join(cls.tmp.name, "trust.json"))
        env.pop("ML_COLUMNS_FULL", None)
        r = subprocess.run([sys.executable, os.path.join(_ROOT, "run_network.py")],
                           cwd=_ROOT, env=env, capture_output=True, text=True,
                           timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"run_network.py failed:\n{r.stdout}\n{r.stderr}")
        with open(cls.out, encoding="utf-8") as f:
            cls.state = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_schema_keys_present(self):
        for key in ("generated_at", "nodes", "edges", "communities",
                    "active_subnet", "firing", "compute", "columns",
                    "segments", "trust"):
            self.assertIn(key, self.state, f"missing top-level key: {key}")
        self.assertGreater(len(self.state["nodes"]), 0)
        self.assertGreater(len(self.state["edges"]), 0)

    def test_edges_honest_weights(self):
        """Every edge weight is a finite float in [0,1] (real gate weights)."""
        for e in self.state["edges"]:
            self.assertIn("source", e)
            self.assertIn("target", e)
            w = e["weight"]
            self.assertIsInstance(w, float)
            self.assertEqual(w, w, "NaN edge weight")  # NaN != NaN
            self.assertGreaterEqual(w, 0.0)
            self.assertLessEqual(w, 1.0)

    def test_nodes_enriched(self):
        """Every node carries column, segment, stage and tier tags."""
        from core.segments import SEGMENT_KEYS, STAGES
        from core.columns import COLUMN_KEYS
        for nd in self.state["nodes"]:
            self.assertIn(nd["column"], COLUMN_KEYS, nd["name"])
            self.assertIn(nd["segment"], SEGMENT_KEYS, nd["name"])
            self.assertIn(nd["stage"], STAGES, nd["name"])
            self.assertIn(nd["tier"], (1, 2), nd["name"])
            self.assertIn("community", nd)
            self.assertIn("usage", nd)
            self.assertIn("mean_weight", nd)
            self.assertTrue(nd["kept"])

    def test_layouts_populated(self):
        self.assertGreater(len(self.state["columns"]), 0)
        self.assertGreater(len(self.state["segments"]), 0)
        col_members = {m for c in self.state["columns"] for m in c["members"]}
        seg_members = {m for s in self.state["segments"] for m in s["members"]}
        expert_names = {nd["name"] for nd in self.state["nodes"]
                        if nd["kind"] == "base"}
        self.assertEqual(expert_names, col_members)
        self.assertEqual(expert_names, seg_members)
        for s in self.state["segments"]:
            self.assertIn("stage", s)

    def test_compute_tier_stats(self):
        c = self.state["compute"]
        self.assertIn("tier_counts", c)
        self.assertIn("escalation_rate", c)
        self.assertGreater(sum(c["tier_counts"].values()), 0)
        self.assertGreaterEqual(c["escalation_rate"], 0.0)
        self.assertLessEqual(c["escalation_rate"], 1.0)
        self.assertEqual(c["n_inputs"], sum(c["tier_counts"].values()))

    def test_firing_records_contract(self):
        firing = self.state["firing"]
        self.assertGreater(len(firing), 0)
        self.assertLessEqual(len(firing), 48)
        n_experts = sum(1 for nd in self.state["nodes"] if nd["kind"] == "base")
        for f in firing[:5]:
            self.assertIn("active", f)
            self.assertIn("weights", f)
            self.assertIn("correct", f)
            self.assertIn("community_path", f)
            for i in f["active"]:
                self.assertLess(i, n_experts)


class TestServerHelpers(unittest.TestCase):
    """/api/network/* route logic via the pure helper functions."""

    @classmethod
    def setUpClass(cls):
        cls.srv = _load_server()

    def test_state_payload_missing(self):
        out = self.srv._network_state_payload(path="/nonexistent/nope.json")
        self.assertIn("note", out)
        self.assertEqual(out["nodes"], [])

    def test_state_payload_age(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ns.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"nodes": [{"name": "a"}], "edges": []}, f)
            mt = os.path.getmtime(p)
            out = self.srv._network_state_payload(path=p, now=mt + 120.0)
            self.assertEqual(out["state_age_s"], 120.0)
            self.assertEqual(out["nodes"], [{"name": "a"}])

    def test_state_payload_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bad.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{not json")
            out = self.srv._network_state_payload(path=p)
            self.assertIn("note", out)
            self.assertEqual(out["nodes"], [])

    def test_trust_payload(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "trust.json")
            blob = {"losses": {"sk_logreg": 0.4}, "counts": {"sk_logreg": 3}}
            with open(p, "w", encoding="utf-8") as f:
                json.dump(blob, f)
            self.assertEqual(self.srv._network_trust_payload(path=p), blob)
            miss = self.srv._network_trust_payload(path=os.path.join(td, "x.json"))
            self.assertIn("note", miss)

    def test_refresh_throttle(self):
        allowed = self.srv._network_refresh_allowed
        ok, _ = allowed(now=1000.0, last=0.0, running=False)
        self.assertTrue(ok)
        ok, note = allowed(now=1000.0, last=990.0, running=False)
        self.assertFalse(ok)
        self.assertIn("throttled", note)
        ok, note = allowed(now=1000.0, last=0.0, running=True)
        self.assertFalse(ok)
        self.assertIn("running", note)
        ok, _ = allowed(now=1000.0, last=939.0, running=False)  # 61s > 60s
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
