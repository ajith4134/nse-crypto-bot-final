"""Phase P4.2 HybridMemory acceptance tests — fully OFFLINE + deterministic.

Exercises the rebuilt HybridMemory (memory/hybrid_memory.py), which fuses the REAL
vendored Stanford Generative-Agents memory stream (vendor/generative_agents_memory),
the project's HumanMemory (Ebbinghaus decay / dream), real Letta tiered core-memory
(embedded), and an optional mem0 store — all powered by an injected LLM.

Everything here is hermetic:
  * a STUB brain replaces KnowledgeBrain so NO embedding model is downloaded;
  * a STUB llm_chat replaces core.llm so there is NO network;
  * datetimes are injected for GA recency and epoch floats for Ebbinghaus decay.
Same stubs + same injected times => identical importance + recall channels.

Run:
    . .venv/bin/activate && PYTHONPATH=. \
        python -m unittest discover -s tests -p test_hybrid_memory.py -v
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")  # silence Letta / mem0 / dep import chatter

import datetime
import json
import unittest

from memory.hybrid_memory import HybridMemory


# --------------------------------------------------------------------------- #
# Stubs: no model download (brain), no network (llm_chat).                     #
# --------------------------------------------------------------------------- #
class StubBrain:
    """Minimal KnowledgeBrain stand-in: chunk dict + ingest_text + recall.

    HumanMemory reads ``getattr(brain, "mem", brain).chunks`` and keys memory
    units on the chunk ``title`` (recall() returns titles), so .mem points back
    at self and recall() emits title-keyed 'vector' hits.
    """

    def __init__(self):
        self.mem = self
        self.chunks: dict[str, dict] = {}
        self._n = 0
        self.ingest_calls = 0

    def ingest_text(self, title, text):
        self.ingest_calls += 1
        self._n += 1
        cid = f"doc_{self._n}"
        self.chunks[cid] = {"title": title, "text": text, "counts": {}}
        return cid

    def recall(self, query, k=4):
        hits = []
        for ch in self.chunks.values():               # title-keyed -> cid == title
            hits.append({"title": ch["title"], "snippet": ch["text"],
                         "score": 1.0, "via": "vector"})
        return hits[:k]


def stub_llm(messages):
    """Deterministic, offline llm_chat(messages)->str.

    Branches on the system prompt: importance/poignancy -> a fixed integer;
    the reflection prompt (mentions INSIGHTS) -> two newline-separated insights;
    anything else -> 'ok'.
    """
    content = messages[0].get("content", "") if messages else ""
    if "importance" in content or "poignancy" in content:
        return "8"
    if "INSIGHTS" in content:
        return "Insight one: discipline compounds\nInsight two: cut losers fast"
    return "ok"


# fixed injected clocks
_T0 = datetime.datetime(2026, 1, 1, 9, 0, 0)
_NOW = 1_700_000_000.0
_BIG_NOW = _NOW + 365 * 86400.0          # ~1 year later -> heavy Ebbinghaus decay


def _hybrid(**kw):
    """HybridMemory wired to the stubs; mem0 off, reranker off (default)."""
    kw.setdefault("llm_chat", stub_llm)
    return HybridMemory(StubBrain(), **kw)


def _seed(hm, n=3):
    """Add a few observations with the stub LLM rating importance, return titles."""
    titles = []
    for i in range(n):
        t = f"trade memo {i}"
        hm.add(t, f"profit alert {i}: won a breakout, big win critical", created=_T0, now=_NOW)
        titles.append(t)
    return titles


# --------------------------------------------------------------------------- #
class TestAdd(unittest.TestCase):
    def test_add_returns_rated_record(self):
        hm = _hybrid()
        res = hm.add("breakout win", "won a profitable breakout trade",
                     created=_T0, now=_NOW)
        self.assertEqual(res["poignancy"], 8)                     # stub rated '8'
        self.assertAlmostEqual(res["importance"], 0.8, places=6)  # 8 / 10
        self.assertFalse(res["mem0"])                             # mem0 off by default
        self.assertTrue(res["doc_id"])
        json.dumps(res)                                           # JSON-able record

    def test_add_calls_brain_ingest(self):
        hm = _hybrid()
        before = hm.brain.ingest_calls
        res = hm.add("alpha", "captured alpha on the open", created=_T0, now=_NOW)
        self.assertEqual(hm.brain.ingest_calls, before + 1)       # ingest_text called
        self.assertIn(res["doc_id"], hm.brain.chunks)             # chunk added
        self.assertEqual(hm.brain.chunks[res["doc_id"]]["title"], "alpha")

    def test_add_records_in_human_memory(self):
        hm = _hybrid()
        hm.add("alpha", "captured alpha on the open", created=_T0, now=_NOW)
        meta = hm.human.meta["alpha"]                             # keyed by title
        self.assertAlmostEqual(meta.importance, 0.8, places=6)    # remembered w/ importance

    def test_add_fallback_heuristic_without_llm(self):
        hm = _hybrid(llm_chat=None)
        hm._llm = None                                            # no llm_chat AND no core.llm
        res = hm.add("loss day", "lost on a bad trade, painful loss",
                     created=_T0, now=_NOW)
        self.assertIsInstance(res["poignancy"], int)             # vendored heuristic int
        self.assertGreaterEqual(res["poignancy"], 1)
        self.assertLessEqual(res["poignancy"], 10)
        self.assertGreater(res["importance"], 0.0)               # 0 < imp <= 1, no crash
        self.assertLessEqual(res["importance"], 1.0)


class TestRecall(unittest.TestCase):
    def test_recall_returns_both_channels(self):
        hm = _hybrid()
        _seed(hm, 2)
        hits = hm.recall("breakout", k=4, now=_NOW, curr_time=_T0)
        self.assertTrue(hits)                                     # non-empty
        vias = {h["via"] for h in hits}
        self.assertIn("generative-agents", vias)                 # GA stream channel
        self.assertIn("vector", vias)                            # decay/associative channel

    def test_recall_hits_are_json_able(self):
        hm = _hybrid()
        _seed(hm, 2)
        hits = hm.recall("win", k=3, now=_NOW, curr_time=_T0)
        for h in hits:
            json.dumps(h)                                         # each hit serialisable
            self.assertIn("via", h)

    def test_recall_bounded_and_nonempty(self):
        hm = _hybrid()
        _seed(hm, 3)
        hits = hm.recall("trade", k=2, now=_NOW, curr_time=_T0)
        self.assertGreater(len(hits), 0)
        self.assertLessEqual(len(hits), 2 * 6)                   # ~ k*small factor

    def test_recall_empty_when_no_memories(self):
        hm = _hybrid()
        hits = hm.recall("anything", k=4, now=_NOW, curr_time=_T0)
        self.assertEqual(hits, [])                               # no crash, empty list


class TestReflect(unittest.TestCase):
    def test_reflect_dedupes_and_persists(self):
        hm = _hybrid()
        _seed(hm, 3)
        before_ingest = hm.brain.ingest_calls
        before_refl = len(hm.reflections)
        out = hm.reflect(curr_time=_T0, now=_NOW)
        self.assertTrue(out["reflected"])
        self.assertTrue(out["insights"])
        self.assertEqual(len(out["insights"]), len(set(out["insights"])))   # DEDUPED
        self.assertEqual(len(hm.reflections), before_refl + 1)              # recorded
        self.assertGreater(hm.brain.ingest_calls, before_ingest)           # insights stored
        json.dumps(out)

    def test_reflect_empty_when_no_memories(self):
        hm = _hybrid()
        out = hm.reflect(curr_time=_T0, now=_NOW)                 # nothing added
        self.assertFalse(out["reflected"])
        self.assertEqual(out.get("insights", []), [])

    def test_reflect_no_llm_no_crash(self):
        hm = _hybrid(llm_chat=None)
        hm._llm = None
        out = hm.reflect(curr_time=_T0, now=_NOW)                 # no memories, no llm
        self.assertFalse(out["reflected"])

    def test_reflect_insight_count_matches_stub(self):
        hm = _hybrid()
        _seed(hm, 3)
        out = hm.reflect(curr_time=_T0, now=_NOW)
        # stub synthesizer yields 2 distinct insight lines; GA reflects over
        # multiple focal points but HybridMemory dedups -> exactly 2 survive.
        self.assertEqual(len(out["insights"]), 2)


class TestDream(unittest.TestCase):
    def test_dream_returns_report(self):
        hm = _hybrid()
        _seed(hm, 3)
        report = hm.dream(_BIG_NOW)
        for key in ("forgotten", "promoted", "consolidated", "remaining"):
            self.assertIn(key, report)
        self.assertIsInstance(report["remaining"], int)
        self.assertGreaterEqual(report["remaining"], 0)
        json.dumps(report)


class TestMem0Gating(unittest.TestCase):
    def test_mem0_off_by_default(self):
        hm = _hybrid()
        self.assertIsNone(hm._mem0)                              # not constructed
        self.assertFalse(hm.status(_NOW)["mem0"])
        res = hm.add("x", "y", created=_T0, now=_NOW)
        self.assertFalse(res["mem0"])                            # add reports no mem0 write


class TestStatus(unittest.TestCase):
    def test_status_shape_and_components(self):
        hm = _hybrid()
        hm._llm = None                                           # keep llm field None -> JSON-able
        _seed(hm, 2)
        st = hm.status(_NOW)
        json.dumps(st)                                           # fully serialisable
        self.assertTrue(st["letta"])                            # Letta importable -> True
        self.assertFalse(st["mem0"])                           # mem0 off (default)
        self.assertIn("generative-agents(vendored real)", st["components"])
        self.assertIn("human_memory(ebbinghaus decay/dream)", st["components"])
        self.assertIn("human", st)
        self.assertIn("ga_stream", st)

    def test_status_ga_stream_grows(self):
        hm = _hybrid()
        hm._llm = None
        self.assertEqual(hm.status(_NOW)["ga_stream"]["n"], 0)
        _seed(hm, 3)
        self.assertEqual(hm.status(_NOW)["ga_stream"]["n"], 3)   # 3 events in the stream

    def test_status_reflections_count(self):
        hm = _hybrid()
        _seed(hm, 3)
        self.assertEqual(hm.status(_NOW)["reflections"], 0)
        hm.reflect(curr_time=_T0, now=_NOW)
        self.assertEqual(hm.status(_NOW)["reflections"], 1)


class TestDeterminism(unittest.TestCase):
    def test_same_stubs_same_times_same_results(self):
        a, b = _hybrid(), _hybrid()
        ra = a.add("memo", "won big profit, critical win", created=_T0, now=_NOW)
        rb = b.add("memo", "won big profit, critical win", created=_T0, now=_NOW)
        self.assertEqual(ra["importance"], rb["importance"])     # same rated importance
        self.assertEqual(ra["poignancy"], rb["poignancy"])
        _seed(a, 2)
        _seed(b, 2)
        va = {h["via"] for h in a.recall("win", k=4, now=_NOW, curr_time=_T0)}
        vb = {h["via"] for h in b.recall("win", k=4, now=_NOW, curr_time=_T0)}
        self.assertEqual(va, vb)                                 # same recall channels


if __name__ == "__main__":
    unittest.main()
