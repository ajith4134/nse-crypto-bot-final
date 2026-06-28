"""Trading Phase T8.8 (skill library + observability + self-improvement) tests — offline.

Pins KNOWN-VALUE assertions against the pure-Python brain skill/telemetry/optimiser
modules so CI passes with no broker/LLM/network access:

  • SkillLibrary — Voyager-style quality-gated, growing, persisted skill store
  • BrainTracer — in-memory Stream-of-Mind span recorder (Langfuse export gated OFF)
  • SelfImprover — deterministic CPU hill-climb optimiser
  • DSPyOptimizer — gated DSPy/GEPA LLM optimiser, tested on the disabled path

Every SkillLibrary is built with persist=False EXCEPT the one persistence test, which
targets a unique file under trading/state/ and cleans up after itself. The tracer uses
an injected deterministic clock and the optimiser an injected seeded rng, so everything
is deterministic + fully offline. dspy/langfuse may be installed but are NOT enabled.
"""
from __future__ import annotations

import itertools
import os
import warnings

warnings.filterwarnings("ignore")

import unittest

import numpy as np

from trading import state
from trading.brain.observability import BrainTracer, Span
from trading.brain.selfimprove import DSPyOptimizer, SelfImprover
from trading.brain.skills import Skill, SkillLibrary


def _skill(name="alpha", market="NSE", metric=1.0, **kw):
    return Skill(id=kw.get("id", name), name=name, kind=kw.get("kind", "strategy"),
                 market=market, payload=kw.get("payload", {"p": 1}), metric=metric,
                 metrics=kw.get("metrics", {}), source=kw.get("source", ""),
                 generation=kw.get("generation", 0))


class TestSkillRoundTrip(unittest.TestCase):
    def test_to_from_dict_round_trips(self):
        s = _skill(name="x", market="CRYPTO", metric=0.5, metrics={"sharpe": 1.2})
        again = Skill.from_dict(s.to_dict())
        self.assertEqual(again.to_dict(), s.to_dict())


class TestSkillLibraryGate(unittest.TestCase):
    def test_admit_above_gate(self):
        lib = SkillLibrary(min_metric=0.5, persist=False)
        res = lib.admit(_skill(metric=0.9))
        self.assertTrue(res["admitted"])
        self.assertEqual(len(lib), 1)

    def test_admit_below_gate_rejected_with_reason(self):
        lib = SkillLibrary(min_metric=0.5, persist=False)
        res = lib.admit(_skill(metric=0.1))
        self.assertFalse(res["admitted"])
        self.assertIn("reason", res)
        self.assertEqual(len(lib), 0)

    def test_same_name_not_beating_rejected(self):
        lib = SkillLibrary(min_metric=0.0, persist=False)
        self.assertTrue(lib.admit(_skill(name="a", metric=0.8))["admitted"])
        res = lib.admit(_skill(name="a", metric=0.5))
        self.assertFalse(res["admitted"])
        self.assertIn("reason", res)
        # the worse duplicate did not replace the incumbent
        self.assertAlmostEqual(lib.best().metric, 0.8, places=9)
        self.assertEqual(len(lib), 1)

    def test_same_name_equal_metric_rejected(self):
        lib = SkillLibrary(min_metric=0.0, persist=False)
        self.assertTrue(lib.admit(_skill(name="a", metric=0.8))["admitted"])
        res = lib.admit(_skill(name="a", metric=0.8))
        self.assertFalse(res["admitted"])

    def test_same_name_beating_admitted_and_improved(self):
        lib = SkillLibrary(min_metric=0.0, persist=False)
        lib.admit(_skill(name="a", metric=0.5))
        res = lib.admit(_skill(name="a", metric=0.9))
        self.assertTrue(res["admitted"])
        self.assertTrue(res["improved"])
        self.assertAlmostEqual(lib.best().metric, 0.9, places=9)
        # still a single unique name
        self.assertEqual(len(lib), 1)

    def test_len_counts_unique_names(self):
        lib = SkillLibrary(persist=False)
        lib.admit(_skill(name="a", metric=1.0))
        lib.admit(_skill(name="b", metric=2.0))
        lib.admit(_skill(name="a", metric=0.1))  # rejected (worse)
        self.assertEqual(len(lib), 2)


class TestSkillLibraryRetrieval(unittest.TestCase):
    def _lib(self):
        lib = SkillLibrary(persist=False)
        lib.admit(_skill(name="n1", market="NSE", metric=1.0))
        lib.admit(_skill(name="n2", market="NSE", metric=3.0))
        lib.admit(_skill(name="n3", market="NSE", metric=2.0))
        lib.admit(_skill(name="c1", market="CRYPTO", metric=5.0))
        return lib

    def test_retrieve_sorted_desc(self):
        got = self._lib().retrieve(k=5)
        metrics = [s.metric for s in got]
        self.assertEqual(metrics, sorted(metrics, reverse=True))
        self.assertAlmostEqual(metrics[0], 5.0, places=9)

    def test_retrieve_filters_by_market(self):
        got = self._lib().retrieve(market="nse", k=10)  # case-insensitive
        self.assertEqual(len(got), 3)
        self.assertTrue(all(s.market == "NSE" for s in got))
        self.assertEqual([s.metric for s in got], [3.0, 2.0, 1.0])

    def test_retrieve_k_caps(self):
        got = self._lib().retrieve(k=2)
        self.assertEqual(len(got), 2)

    def test_best_overall_and_per_market(self):
        lib = self._lib()
        self.assertAlmostEqual(lib.best().metric, 5.0, places=9)
        self.assertAlmostEqual(lib.best(market="NSE").metric, 3.0, places=9)

    def test_best_none_when_empty(self):
        self.assertIsNone(SkillLibrary(persist=False).best())

    def test_status_keys(self):
        st = self._lib().status()
        for key in ("n_skills", "min_metric", "by_market", "top"):
            self.assertIn(key, st)
        self.assertEqual(st["n_skills"], 4)
        self.assertEqual(st["by_market"], {"NSE": 3, "CRYPTO": 1})
        self.assertLessEqual(len(st["top"]), 5)


class TestAdmitStrategy(unittest.TestCase):
    def test_admit_strategy_object_with_to_dict(self):
        class FakeStrategy:
            def to_dict(self):
                return {"id": "evo_1", "market": "CRYPTO",
                        "provenance": {"generation": 3}}

        lib = SkillLibrary(persist=False)
        res = lib.admit_strategy(FakeStrategy(), 0.7, metrics={"oos": 0.7},
                                 source="evolution")
        self.assertTrue(res["admitted"])
        sk = lib.best()
        self.assertEqual(sk.name, "evo_1")
        self.assertEqual(sk.market, "CRYPTO")
        self.assertEqual(sk.generation, 3)
        self.assertEqual(sk.source, "evolution")
        self.assertAlmostEqual(sk.metric, 0.7, places=9)

    def test_admit_strategy_plain_dict(self):
        lib = SkillLibrary(persist=False)
        res = lib.admit_strategy({"id": "d1", "market": "NSE"}, 1.5)
        self.assertTrue(res["admitted"])
        self.assertEqual(lib.best().name, "d1")


class TestSkillPersistence(unittest.TestCase):
    def setUp(self):
        self.state_file = f"test_skills_{os.getpid()}.json"

    def tearDown(self):
        p = state.STATE_DIR / self.state_file
        if p.exists():
            p.unlink()

    def test_admit_persists_and_reloads(self):
        lib = SkillLibrary(state_file=self.state_file, persist=True)
        # start clean even if a stale file lingered
        self.assertTrue(lib.admit(_skill(name="persisted", metric=2.5))["admitted"])
        # a brand-new library pointed at the same file must see the skill
        reloaded = SkillLibrary(state_file=self.state_file, persist=True)
        names = [s.name for s in reloaded.retrieve(k=10)]
        self.assertIn("persisted", names)
        best = reloaded.best(market="NSE")
        self.assertEqual(best.name, "persisted")
        self.assertAlmostEqual(best.metric, 2.5, places=9)


class TestBrainTracer(unittest.TestCase):
    def test_record_uses_deterministic_clock(self):
        tr = BrainTracer(clock=itertools.count().__next__)
        sp = tr.record("step", inputs={"x": 1}, outputs={"y": 2})
        self.assertIsInstance(sp, Span)
        self.assertEqual(sp.ts, 0.0)        # first tick of the counter
        self.assertEqual(sp.name, "step")
        self.assertEqual(sp.outputs, {"y": 2})
        self.assertEqual(tr.status()["n_spans"], 1)

    def test_trace_context_records_outputs_and_duration(self):
        clock = itertools.count(step=2).__next__   # 0, 2, 4, ... seconds
        tr = BrainTracer(clock=clock)
        with tr.trace("decide", symbol="BTC") as box:
            box["outputs"] = {"decision": "UP"}
        spans = tr.recent(5)
        self.assertEqual(len(spans), 1)
        sp = spans[0]
        self.assertEqual(sp["name"], "decide")
        self.assertEqual(sp["inputs"], {"symbol": "BTC"})
        self.assertEqual(sp["outputs"], {"decision": "UP"})
        # t0=0 captured, record() reads clock again at 2s -> 2000 ms
        self.assertAlmostEqual(sp["duration_ms"], 2000.0, places=6)

    def test_recent_caps_at_n(self):
        tr = BrainTracer(clock=itertools.count().__next__)
        for i in range(5):
            tr.record(f"s{i}")
        self.assertEqual(len(tr.recent(3)), 3)

    def test_stream_of_mind_returns_strings_with_names(self):
        tr = BrainTracer(clock=itertools.count().__next__)
        tr.record("plan", outputs={"goal": "scan"})
        tr.record("act", outputs={"order": "buy"})
        lines = tr.stream_of_mind(10)
        self.assertLessEqual(len(lines), 10)
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(isinstance(x, str) for x in lines))
        self.assertTrue(any("plan" in x for x in lines))
        self.assertTrue(any("act" in x for x in lines))

    def test_maxlen_truncation(self):
        tr = BrainTracer(maxlen=5, clock=itertools.count().__next__)
        for i in range(20):
            tr.record(f"s{i}")
        self.assertEqual(tr.status()["n_spans"], 5)
        # the ring keeps the most recent ones
        self.assertEqual(tr.recent(5)[-1]["name"], "s19")

    def test_backend_local_when_langfuse_off(self):
        tr = BrainTracer(enabled_langfuse=False, clock=itertools.count().__next__)
        self.assertEqual(tr.backend, "local")
        st = tr.status()
        self.assertEqual(st["backend"], "local")
        self.assertTrue(st["langfuse_installed"])  # installed but not enabled


class TestSelfImprover(unittest.TestCase):
    def _concave(self):
        # peak at a=0.7, b=-1.2 ; maximum value 0
        return lambda p: -((p["a"] - 0.7) ** 2 + (p["b"] + 1.2) ** 2)

    def test_maximize_improves_to_peak(self):
        space = {"a": (-2.0, 2.0), "b": (-2.0, 2.0)}
        res = SelfImprover(n_iter=200).optimize(
            space, self._concave(), rng=np.random.default_rng(0))
        self.assertTrue(res["improved"])
        self.assertGreater(res["best_score"], res["start_score"])
        self.assertAlmostEqual(res["best_params"]["a"], 0.7, delta=0.2)
        self.assertAlmostEqual(res["best_params"]["b"], -1.2, delta=0.2)

    def test_history_length_and_monotone_for_maximize(self):
        space = {"a": (-2.0, 2.0), "b": (-2.0, 2.0)}
        res = SelfImprover(n_iter=50).optimize(
            space, self._concave(), rng=np.random.default_rng(1))
        self.assertEqual(len(res["history"]), 51)   # n_iter + 1
        for prev, cur in zip(res["history"], res["history"][1:]):
            self.assertGreaterEqual(cur, prev)      # non-decreasing for maximize

    def test_minimize_finds_minimum(self):
        # convex bowl, minimum 0 at a=0.3
        convex = lambda p: (p["a"] - 0.3) ** 2
        res = SelfImprover(n_iter=200, maximize=False).optimize(
            {"a": (-2.0, 2.0)}, convex, rng=np.random.default_rng(2))
        self.assertTrue(res["improved"])
        self.assertLess(res["best_score"], res["start_score"])
        self.assertAlmostEqual(res["best_params"]["a"], 0.3, delta=0.2)
        # non-increasing history for minimise
        for prev, cur in zip(res["history"], res["history"][1:]):
            self.assertLessEqual(cur, prev)

    def test_deterministic_same_seed(self):
        space = {"a": (-2.0, 2.0), "b": (-2.0, 2.0)}
        m = self._concave()
        r1 = SelfImprover(n_iter=80).optimize(space, m, rng=np.random.default_rng(7))
        r2 = SelfImprover(n_iter=80).optimize(space, m, rng=np.random.default_rng(7))
        self.assertEqual(r1["best_score"], r2["best_score"])
        self.assertEqual(r1["best_params"], r2["best_params"])
        self.assertEqual(r1["history"], r2["history"])


class TestDSPyOptimizerGatedOff(unittest.TestCase):
    def setUp(self):
        # make absolutely sure the gate is OFF regardless of ambient env
        self._saved = os.environ.pop("DSPY_ENABLED", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["DSPY_ENABLED"] = self._saved

    def test_not_available(self):
        self.assertFalse(DSPyOptimizer(enabled=False).available())

    def test_build_decider_none(self):
        self.assertIsNone(DSPyOptimizer(enabled=False).build_decider())

    def test_optimize_returns_unavailable_note(self):
        res = DSPyOptimizer(enabled=False).optimize([], None)
        self.assertFalse(res["available"])
        self.assertIn("note", res)

    def test_status_unavailable(self):
        st = DSPyOptimizer(enabled=False).status()
        self.assertFalse(st["available"])
        self.assertIn("note", st)

    def test_env_default_is_off(self):
        # with DSPY_ENABLED unset, the env-driven default must stay disabled
        self.assertFalse(DSPyOptimizer().available())


if __name__ == "__main__":
    unittest.main()
