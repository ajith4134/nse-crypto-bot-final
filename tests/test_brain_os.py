"""Tests for trading/brain/brain_os.py — Brain-OS kernel + RAM working memory (OS-1)."""
import tempfile
import unittest
from unittest import mock

from memory.neurons import NeuronStore
from trading import state
from trading.brain.brain_os import BrainKernel, WorkingMemory


class WorkingMemoryTest(unittest.TestCase):
    def test_pin_is_never_evicted_under_pressure(self):
        wm = WorkingMemory(max_bytes=800)
        wm.pin("keep", {"id": "keep", "body": "x" * 100})
        for i in range(60):                              # flood the hot set
            wm.load(f"n{i}", {"id": f"n{i}", "body": "y" * 100})
        self.assertIsNotNone(wm.get("keep"))             # pinned survived
        self.assertGreater(wm.evictions, 0)              # eviction actually happened

    def test_hot_set_stays_within_byte_cap(self):
        wm = WorkingMemory(max_bytes=1000)
        for i in range(200):
            wm.load(f"n{i}", {"id": f"n{i}", "body": "z" * 50})
        # after each load the buffer is trimmed; allow one in-flight entry of slack
        self.assertLessEqual(wm.bytes_used(), 1000 + 200)

    def test_lru_keeps_recently_touched(self):
        wm = WorkingMemory(max_bytes=400)
        wm.load("a", {"id": "a", "b": "x" * 40})
        wm.load("b", {"id": "b", "b": "x" * 40})
        wm.get("a")                                      # touch a → b is now coldest
        wm.load("c", {"id": "c", "b": "x" * 40})
        self.assertIsNotNone(wm.get("a"))               # survived as recently used

    def test_focus_blackboard_and_rings(self):
        wm = WorkingMemory(ring=3)
        wm.set_focus(segment="crypto", goal="scalp")
        self.assertEqual(wm.focus["segment"], "crypto")
        wm.post("funnel", "opened BTC")
        self.assertEqual(wm.read("funnel")["msg"], "opened BTC")
        for i in range(5):
            wm.remember("decision", {"n": i})
        self.assertEqual(len(wm.recent("decision")), 3)  # ring bounded to maxlen
        self.assertEqual(wm.recent("decision")[-1]["item"]["n"], 4)
        with self.assertRaises(ValueError):
            wm.remember("bogus", {})

    def test_bytes_used_is_real(self):
        wm = WorkingMemory()
        self.assertEqual(wm.bytes_used(), _empty := wm.bytes_used())
        wm.load("a", {"id": "a", "body": "hello world" * 10})
        self.assertGreater(wm.bytes_used(), _empty)


class BrainKernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp_state = tempfile.mkdtemp()
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.tmp_state))
        p.start()
        self.addCleanup(p.stop)
        self.store = NeuronStore(tempfile.mkdtemp())
        self.n = self.store.add("fact", "BTC halving cuts issuance",
                                "Every ~4y block reward halves.",
                                "Use to reason about supply shocks. Verify on-chain.",
                                auto_link=False)

    def test_boot_is_idempotent_and_counts_boots(self):
        k1 = BrainKernel(self.store)
        top = k1.boot()
        self.assertTrue(top["booted"])
        self.assertEqual(top["boots"], 1)
        self.assertGreaterEqual(k1.uptime_secs(), 0.0)
        k2 = BrainKernel(self.store)                     # fresh kernel, same state file
        self.assertEqual(k2.boot()["boots"], 2)          # persisted boot count survived

    def test_syscall_recall_loads_into_ram(self):
        k = BrainKernel(self.store); k.boot()
        hits = k.syscall("recall", query="halving", k=3)
        self.assertTrue(any(h["id"] == self.n.id for h in hits))
        self.assertIsNotNone(k.wm.get(self.n.id))        # result is now RAM-resident

    def test_syscall_remember_adds_neuron(self):
        k = BrainKernel(self.store); k.boot()
        out = k.syscall("remember", kind="lesson", title="cut risk in chop",
                        body="1) detect chop\n2) halve size", action="apply when ADX<15")
        self.assertIsNotNone(self.store.get(out["id"]))
        self.assertIsNotNone(k.wm.get(out["id"]))

    def test_focus_and_pin_persist_across_reboot(self):
        k = BrainKernel(self.store); k.boot()
        k.syscall("focus", segment="crypto")
        self.assertTrue(k.syscall("pin", nid=self.n.id)["pinned"])
        k2 = BrainKernel(self.store); k2.boot()          # restart
        self.assertEqual(k2.wm.focus.get("segment"), "crypto")
        self.assertIsNotNone(k2.wm.get(self.n.id))       # re-pinned on boot

    def test_evolve_syscall_routes_and_unknown_raises(self):
        k = BrainKernel(self.store); k.boot()
        evo = k.syscall("evolve")
        self.assertIn("varied", evo)
        self.assertIn("promotions", evo)
        with self.assertRaises(ValueError):
            k.syscall("no_such_call")

    def test_top_reports_honest_numbers(self):
        k = BrainKernel(self.store); k.boot()
        top = k.top()
        self.assertEqual(top["store"]["neurons"], 1)
        self.assertTrue(top["store"]["ram_resident"])
        self.assertIn("recall", top["syscalls"])
        self.assertIn("bytes_used", top["working_memory"])
        self.assertTrue(any(p["name"] == "brain-kernel" for p in top["processes"]))

    def test_process_table_is_honest_about_missing_heartbeats(self):
        # isolated STATE_DIR has none of the lobe heartbeat files → they read STOPPED,
        # never a fabricated RUNNING; the in-process kernel is genuinely RUNNING.
        k = BrainKernel(self.store); k.boot()
        procs = {p["name"]: p for p in k.ps()}
        self.assertEqual(procs["brain-kernel"]["state"], "RUNNING")
        self.assertEqual(procs["crypto-funnel"]["state"], "STOPPED")
        self.assertIsNone(procs["crypto-funnel"]["age_secs"])

    def test_process_state_thresholds(self):
        from trading.brain.brain_os import _proc_state
        self.assertEqual(_proc_state(None, 100), "STOPPED")
        self.assertEqual(_proc_state(50, 100), "RUNNING")
        self.assertEqual(_proc_state(200, 100), "SLEEPING")
        self.assertEqual(_proc_state(400, 100), "DEAD")

    # ── OS-3: attention scheduler ─────────────────────────────────────────────
    def test_scheduler_follows_focus(self):
        k = BrainKernel(self.store); k.boot()
        k.syscall("focus", segment="crypto")
        self.assertEqual(k.next_lobe()["next"], "crypto-funnel")   # focus wins
        k.syscall("focus", segment="nse")
        self.assertEqual(k.next_lobe()["next"], "nse-funnel")      # order CHANGES with focus

    def test_tick_advances_and_records(self):
        k = BrainKernel(self.store); k.boot()
        t1 = k.tick()
        self.assertEqual(t1["tick"], 1)
        self.assertIsNotNone(t1["next"])
        self.assertEqual(k.wm.read("scheduler")["msg"]["next"], t1["next"])  # posted to blackboard

    def test_fairness_rotates_without_focus(self):
        k = BrainKernel(self.store); k.boot()          # no focus → fairness drives rotation
        picks = {k.tick()["next"] for _ in range(12)}
        self.assertGreater(len(picks), 1)              # not stuck on one lobe

    def test_scheduler_in_top(self):
        k = BrainKernel(self.store); k.boot()
        self.assertIn("scheduler", k.top())
        self.assertIn("ranking", k.top()["scheduler"])

    # ── OS-4: single kernel-routed call surface ───────────────────────────────
    def test_os4_consult_routes_through_kernel(self):
        import trading.brain.brain_os as bos
        seen = {}

        class FakeK:
            def syscall(self, name, **kw):
                seen["name"] = name; seen.update(kw); return {"ids": ["x"]}
        with mock.patch.object(bos, "get_kernel", lambda: FakeK()):
            out = bos.consult("q", domain="trading", k=2)
        self.assertEqual(seen["name"], "consult")
        self.assertEqual(seen["domain"], "trading")
        self.assertEqual(out, {"ids": ["x"]})

    def test_os4_falls_back_to_direct_bridge_when_kernel_down(self):
        import trading.brain.brain_os as bos
        import trading.brain.consult as c

        def boom():
            raise RuntimeError("no kernel")
        with mock.patch.object(bos, "get_kernel", boom), \
             mock.patch.object(c, "consult", lambda q, **kw: {"ids": ["fb"], "via": "direct"}):
            out = bos.consult("q", domain="trading")
        self.assertEqual(out["via"], "direct")           # hot path never regresses

    def test_os4_grade_routes_and_falls_back(self):
        import trading.brain.brain_os as bos
        import trading.brain.consult as c
        with mock.patch.object(bos, "get_kernel", lambda: (_ for _ in ()).throw(RuntimeError())), \
             mock.patch.object(c, "grade", lambda ids, **kw: 7):
            self.assertEqual(bos.grade(["a"], win=True, domain="trading"), 7)


if __name__ == "__main__":
    unittest.main()
