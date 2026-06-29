"""Phase P4.6 (Stream-of-Mind + observability) acceptance tests — fully offline.

Proves the brain's visible working-memory → long-term-memory pipeline and its durable
observability, all deterministic and network-free: a STUB brain (recall + writable
ingest_text, no embeddings/disk), an injected logical clock, no LLM, and Langfuse in its
offline no-op mode (no keys). Each test pins a real reused piece:

  * GlobalWorkspace — salience fuses GA poignancy + pymdp surprise/curiosity/confidence;
    per-tick competition picks the winner; salient winners consolidate to the brain.
  * StreamOfMind — one real Thinker.think() cycle → ordered thought-events; salient ones
    land in long-term memory, boilerplate fades.
  * core.observability (Langfuse) — trace()/span()/flush() are safe no-ops offline.
  * AG-UI — the protocol encoder emits valid SSE frames for the /api/agui transport.

Mirrors tests/test_thinking_p45.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import itertools
import warnings

warnings.filterwarnings("ignore")

import unittest

import numpy as np

from cognition import CalibratedAbstainer, Thinker
from cognition.stream_of_mind import GlobalWorkspace, StreamOfMind, Thought


class _Brain:
    """Recall (deterministic keyword overlap) + writable long-term store (ingest_text)."""

    class _Graph:
        def snapshot(self, types=None):
            return {"nodes": [{"id": f"concept:{c}", "type": "concept", "label": c}
                              for c in ("gradient", "optimization", "loss")],
                    "edges": [{"source": "concept:gradient", "target": "concept:optimization",
                               "rel": "co_occurs"},
                              {"source": "concept:optimization", "target": "concept:loss",
                               "rel": "co_occurs"}]}

    # 4 overlapping facts so a grounded query retrieves enough evidence to clear the
    # abstention gate (be confident) and consolidate — matching run_stream_of_mind._DemoBrain.
    DB = {"gradient descent": "Gradient descent minimizes a loss by stepping opposite the gradient; "
                             "the learning rate sets the step size.",
          "the loss surface": "Optimization walks downhill on the loss surface toward lower loss.",
          "backpropagation": "Backpropagation computes the gradient of the loss for each weight.",
          "the learning rate": "The learning rate scales each gradient step in optimization."}

    def __init__(self):
        self.graph = self._Graph()
        self.long_term = []

    def recall(self, query, k=4):
        q = {w for w in query.lower().split() if len(w) > 3}
        out = []
        for title, text in self.DB.items():
            if q & (set(text.lower().split()) | set(title.lower().split())):
                out.append({"title": title, "snippet": text, "score": 1.0 / (1 + len(out))})
        return out[:k]

    def ingest_text(self, title, text):
        self.long_term.append((title, text))
        return "doc:" + title


def _abstainer():
    rng = np.random.default_rng(20260629)
    n = 400
    conf = rng.uniform(0, 1, n)
    correct = (rng.uniform(0, 1, n) < (0.12 + 0.82 * conf)).astype(int)
    return CalibratedAbstainer(confidence_level=0.8, min_calib=30).calibrate(conf, correct)


def _som(brain):
    th = Thinker.from_brain(brain, abstainer=_abstainer(), recall_k=4)
    ticks = itertools.count(1)
    return StreamOfMind(th, brain=brain, clock=lambda: next(ticks) * 1000)


class TestGlobalWorkspace(unittest.TestCase):
    def test_salience_rewards_surprise_over_trivia(self):
        hi = GlobalWorkspace.salience("Surprise updating beliefs", surprise=0.9, confidence=0.7)
        lo = GlobalWorkspace.salience("Goal: answer the question", surprise=0.0, confidence=0.2)
        self.assertGreater(hi, lo)

    def test_competition_picks_highest_and_consolidates(self):
        brain = _Brain()
        gw = GlobalWorkspace(brain, consolidate_threshold=0.5, broadcast_bandwidth=1)
        lo = Thought("a", "trivia", "goal", 0.2, 1000)
        hi = Thought("b", "a salient insight", "verdict", 0.8, 1000)
        winners = gw.compete([lo, hi])
        self.assertEqual(winners[0].id, "b")          # highest salience wins the broadcast slot
        self.assertTrue(winners[0].consolidated)      # above threshold → written to long-term
        self.assertEqual(len(brain.long_term), 1)

    def test_below_threshold_does_not_consolidate(self):
        brain = _Brain()
        gw = GlobalWorkspace(brain, consolidate_threshold=0.6)
        gw.compete([Thought("a", "weak", "react", 0.3, 1000)])
        self.assertEqual(len(brain.long_term), 0)


class TestStreamOfMind(unittest.TestCase):
    def test_think_streams_real_thoughts(self):
        som = _som(_Brain())
        out = som.think("How does gradient descent reduce the loss during optimization?")
        kinds = {t["kind"] for t in out["thoughts"]}
        self.assertTrue({"goal", "react", "verdict"} <= kinds)   # real cycle decomposed
        self.assertGreaterEqual(out["n_thoughts"], 4)

    def test_grounded_consolidates_to_long_term(self):
        brain = _Brain()
        som = _som(brain)
        out = som.think("How does gradient descent reduce the loss during optimization?")
        self.assertGreaterEqual(out["n_consolidated"], 1)        # salient thought → long-term
        self.assertGreaterEqual(len(brain.long_term), 1)

    def test_recent_buffer_and_status(self):
        som = _som(_Brain())
        som.think("How does gradient descent reduce the loss?")
        self.assertTrue(som.recent_thoughts())
        st = som.status()
        self.assertEqual(st["cycles"], 1)
        self.assertIn("workspace", st)

    def test_stream_generator_yields_done(self):
        som = _som(_Brain())
        evs = list(som.stream("How does gradient descent reduce the loss?"))
        self.assertEqual(evs[-1]["type"], "done")
        self.assertTrue(any(e["type"] == "thought" for e in evs))
        self.assertTrue(any(e["type"] == "answer" for e in evs))


class TestObservability(unittest.TestCase):
    def test_offline_noop_trace(self):
        from core import observability as obs
        st = obs.status()
        self.assertEqual(st["engine"], "langfuse")
        self.assertIn(st["mode"], ("offline-noop", "durable-trace"))
        # trace/span/flush must never raise offline
        with obs.trace("t", x=1) as tr:
            with tr.span("child", k=2) as s:
                s.update(output="ok")
            tr.event("tick", v=1)
        obs.flush()


class TestAGUI(unittest.TestCase):
    def test_agui_encoder_emits_sse_frames(self):
        from ag_ui.core import (EventType, RunStartedEvent, TextMessageContentEvent)
        from ag_ui.encoder import EventEncoder
        enc = EventEncoder()
        self.assertEqual(enc.get_content_type(), "text/event-stream")
        frame = enc.encode(TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT, message_id="m1", delta="a thought"))
        self.assertTrue(frame.startswith("data: "))
        self.assertIn("\"delta\":\"a thought\"", frame)
        # run lifecycle event uses camelCase aliases the JS client expects
        run = enc.encode(RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r"))
        self.assertIn("threadId", run)


class TestDemo(unittest.TestCase):
    def test_build_demo_snapshot(self):
        import json

        from run_stream_of_mind import build_demo_thinking, live_stream
        snap = build_demo_thinking()
        self.assertEqual(snap["phase"], "P4.6")
        self.assertGreaterEqual(snap["grounded"]["n_consolidated"], 1)
        self.assertTrue(snap["unknown"]["abstained"])
        self.assertGreaterEqual(snap["long_term_memory_grew_to"], 1)
        json.dumps(snap, default=str)                  # dashboard endpoint serialisable
        # live_stream (used by /api/agui) yields thought + done events
        evs = list(live_stream("how does gradient descent work"))
        self.assertEqual(evs[-1]["type"], "done")


if __name__ == "__main__":
    unittest.main(verbosity=2)
