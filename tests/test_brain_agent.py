"""Phase P4.1 (LangGraph Brain Agent) acceptance tests — fully OFFLINE + deterministic.

Exercises core.brain_agent.BrainAgent end-to-end through its real compiled LangGraph
StateGraph (recall -> respond) WITHOUT ever touching a real LLM or the network: every
test injects a stub `brain` (recall) and/or a stub `llm_chat`, and forces the lazy
core.llm handle off (`agent._llm = None`) so no provider key is consulted.

Covers: LLM path (llm_used / used_memory / recalled titles / reply pass-through),
retrieval-augmented system prompt (recalled context reaches the model), history
threading, the offline memory-grounded template, the honest no-LLM/no-memory reply,
graceful fall-through when llm_chat raises, recall_k plumbing, status() shape +
JSON-ability, and determinism. Deterministic throughout; no disk/repo writes.
"""
from __future__ import annotations

import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from core.brain_agent import BrainAgent


# ── stubs ────────────────────────────────────────────────────────────────────
_HITS = [
    {"title": "CPU-first nodes", "snippet": "320 prediction-model nodes run on CPU.",
     "score": 0.91, "via": "embed"},
    {"title": "Learning brain", "snippet": "A brain agent routes and learns over nodes.",
     "score": 0.77, "via": "assoc"},
]


class StubBrain:
    """Returns two fixed hits; records the last (query, k) seen by recall()."""

    def __init__(self, hits=None):
        self.hits = list(_HITS if hits is None else hits)
        self.last_query = None
        self.last_k = None

    def recall(self, query, k=4):
        self.last_query = query
        self.last_k = k
        return [dict(h) for h in self.hits]


class RecorderChat:
    """Injected llm_chat that captures the messages and returns a fixed reply."""

    def __init__(self, reply="STUB-REPLY-42"):
        self.reply = reply
        self.messages = None
        self.calls = 0

    def __call__(self, messages):
        self.calls += 1
        self.messages = messages
        return self.reply


def _agent(brain=None, llm_chat=None, recall_k=4, force_no_llm=True):
    """Build a BrainAgent and (by default) kill the lazy core.llm handle for offline."""
    a = BrainAgent(brain, llm_chat=llm_chat, recall_k=recall_k)
    if force_no_llm:
        a._llm = None
    return a


# ── LLM path + retrieval augmentation ────────────────────────────────────────
class TestLLMPath(unittest.TestCase):
    def test_llm_used_and_memory_used(self):
        rec = RecorderChat()
        out = _agent(StubBrain(), llm_chat=rec).ask("what are the nodes?")
        self.assertTrue(out["llm_used"])
        self.assertTrue(out["used_memory"])

    def test_reply_passthrough(self):
        rec = RecorderChat("hello from the brain")
        out = _agent(StubBrain(), llm_chat=rec).ask("hi")
        self.assertEqual(out["reply"], "hello from the brain")

    def test_recalled_titles_surface(self):
        out = _agent(StubBrain(), llm_chat=RecorderChat()).ask("q")
        titles = [r["title"] for r in out["recalled"]]
        self.assertEqual(titles, ["CPU-first nodes", "Learning brain"])
        # recalled entries expose title/via/score (rounded float)
        self.assertEqual(out["recalled"][0]["via"], "embed")
        self.assertAlmostEqual(out["recalled"][0]["score"], 0.91, places=4)

    def test_recalled_context_in_system_prompt(self):
        rec = RecorderChat()
        _agent(StubBrain(), llm_chat=rec).ask("explain")
        self.assertEqual(rec.calls, 1)
        system = rec.messages[0]
        self.assertEqual(system["role"], "system")
        # the recalled title AND snippet must be grounded into the system message
        self.assertIn("CPU-first nodes", system["content"])
        self.assertIn("320 prediction-model nodes run on CPU.", system["content"])

    def test_user_message_is_last(self):
        rec = RecorderChat()
        _agent(StubBrain(), llm_chat=rec).ask("MY-QUESTION")
        last = rec.messages[-1]
        self.assertEqual(last["role"], "user")
        self.assertEqual(last["content"], "MY-QUESTION")


# ── history threading ────────────────────────────────────────────────────────
class TestHistory(unittest.TestCase):
    def test_history_threaded_between_system_and_user(self):
        rec = RecorderChat()
        history = [{"role": "user", "content": "earlier-q"},
                   {"role": "assistant", "content": "earlier-a"}]
        _agent(StubBrain(), llm_chat=rec).ask("new-q", history=history)
        msgs = rec.messages
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1], {"role": "user", "content": "earlier-q"})
        self.assertEqual(msgs[2], {"role": "assistant", "content": "earlier-a"})
        self.assertEqual(msgs[-1], {"role": "user", "content": "new-q"})

    def test_no_history_means_system_then_user(self):
        rec = RecorderChat()
        _agent(StubBrain(), llm_chat=rec).ask("solo")
        self.assertEqual(len(rec.messages), 2)


# ── offline fallback (no LLM) ────────────────────────────────────────────────
class TestOfflineFallback(unittest.TestCase):
    def test_memory_grounded_template(self):
        out = _agent(StubBrain(), llm_chat=None).ask("anything")
        self.assertFalse(out["llm_used"])
        self.assertTrue(out["used_memory"])
        # honest no-LLM marker + the recalled memory text in the reply
        self.assertIn("no LLM", out["reply"])
        self.assertIn("CPU-first nodes", out["reply"])
        self.assertIn("320 prediction-model nodes run on CPU.", out["reply"])

    def test_no_memory_no_llm_is_honest(self):
        out = _agent(None, llm_chat=None).ask("hello?")
        self.assertFalse(out["llm_used"])
        self.assertFalse(out["used_memory"])
        self.assertEqual(out["recalled"], [])
        self.assertIn("no LLM", out["reply"])
        self.assertIn("no", out["reply"].lower())
        self.assertIn("memory", out["reply"].lower())

    def test_llm_chat_raising_falls_through_to_template(self):
        def boom(messages):
            raise RuntimeError("provider down")
        # no exception escapes; degrades to offline memory template
        out = _agent(StubBrain(), llm_chat=boom).ask("q")
        self.assertFalse(out["llm_used"])
        self.assertTrue(out["used_memory"])
        self.assertIn("CPU-first nodes", out["reply"])


# ── plumbing: recall_k ───────────────────────────────────────────────────────
class TestRecallK(unittest.TestCase):
    def test_recall_k_default_passed(self):
        b = StubBrain()
        _agent(b, llm_chat=RecorderChat()).ask("q")
        self.assertEqual(b.last_k, 4)

    def test_recall_k_custom_passed(self):
        b = StubBrain()
        _agent(b, llm_chat=RecorderChat(), recall_k=9).ask("q")
        self.assertEqual(b.last_k, 9)

    def test_query_reaches_brain(self):
        b = StubBrain()
        _agent(b, llm_chat=RecorderChat()).ask("FIND-THIS")
        self.assertEqual(b.last_query, "FIND-THIS")


# ── status() ─────────────────────────────────────────────────────────────────
class TestStatus(unittest.TestCase):
    def test_status_shape_with_memory(self):
        st = _agent(StubBrain(), recall_k=4).status()
        self.assertEqual(st["engine"], "langgraph")
        self.assertTrue(st["has_memory"])
        self.assertEqual(st["recall_k"], 4)
        self.assertIn("llm", st)

    def test_status_no_memory_flag(self):
        self.assertFalse(_agent(None).status()["has_memory"])

    def test_status_is_json_able(self):
        json.dumps(_agent(StubBrain()).status())
        json.dumps(_agent(None).status())


# ── determinism ──────────────────────────────────────────────────────────────
class TestDeterminism(unittest.TestCase):
    def test_identical_inputs_identical_reply_llm(self):
        r1 = _agent(StubBrain(), llm_chat=RecorderChat()).ask("same")
        r2 = _agent(StubBrain(), llm_chat=RecorderChat()).ask("same")
        self.assertEqual(r1, r2)

    def test_identical_inputs_identical_reply_offline(self):
        r1 = _agent(StubBrain(), llm_chat=None).ask("same")
        r2 = _agent(StubBrain(), llm_chat=None).ask("same")
        self.assertEqual(r1["reply"], r2["reply"])


if __name__ == "__main__":
    unittest.main()
