"""Phase P4.5 (Thinking + knowing-what-it-knows) acceptance tests — fully offline.

Proves the brain reasons, stays calibrated, and asks for help. Everything here is
deterministic and network-free: STUB brains replace the real KnowledgeBrain (no recall
index, no embeddings, no disk), no LLM is configured, and the conformal abstainer is fit
on a seeded synthetic history. Each test pins a real reused engine:

  * ActiveInferenceModel (pymdp) — Bayesian surprise habituates on a repeated topic and
    spikes on a novel one; curiosity points at under-explored topics.
  * ReasoningGraph (LangGraph) — ReAct multi-steps over memory; ToT branches/scores.
  * SymbolicReasoner (pyDatalog) — transitive concept reasoning WITH a derivation trace.
  * CausalAnalyzer (DoWhy + causal-learn) — recovers a known effect and survives placebo
    refutation; PC discovery finds the true edges.
  * CalibratedAbstainer (conformal + netcal) — answers when confident, abstains + escalates
    when not; calibration lowers ECE.
  * Constitution (NeMo-Guardrails) — redacts secrets, flags ungrounded/overconfident output.
  * Thinker — the orchestrator: grounded → answer, unknown → abstain + escalate.

Mirrors the idiom of tests/test_self_quiz.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import unittest

import numpy as np

from cognition import (ActiveInferenceModel, CalibratedAbstainer, CausalAnalyzer,
                       Constitution, SymbolicReasoner, Thinker)
from cognition.reasoning import ReasoningGraph


# ── stub brain (no embeddings / disk / network) ────────────────────────────────────
class _Graph:
    def snapshot(self, types=None):
        return {
            "nodes": [{"id": f"concept:{c}", "type": "concept", "label": c}
                      for c in ("gradient", "optimization", "loss", "trading")],
            "edges": [{"source": "concept:gradient", "target": "concept:optimization", "rel": "co_occurs"},
                      {"source": "concept:optimization", "target": "concept:loss", "rel": "co_occurs"}],
        }


class _Brain:
    graph = _Graph()
    DB = {
        "gradient descent": "Gradient descent minimizes a loss by stepping opposite the gradient.",
        "the loss surface": "The loss surface is walked downhill by optimization toward lower loss.",
        "backprop": "Backpropagation computes the gradient of the loss for each weight.",
        "learning rate": "The learning rate scales each gradient step in optimization.",
    }

    def recall(self, query, k=4):
        q = {w for w in query.lower().split() if len(w) > 3}
        out = []
        for rank, (title, text) in enumerate(self.DB.items()):
            if q & (set(text.lower().split()) | set(title.lower().split())):
                out.append({"title": title, "snippet": text, "score": 1.0 / (1 + len(out))})
        return out[:k]


def _abstainer(level=0.8):
    rng = np.random.default_rng(20260629)
    n = 400
    conf = rng.uniform(0, 1, n)
    correct = (rng.uniform(0, 1, n) < (0.12 + 0.82 * conf)).astype(int)
    return CalibratedAbstainer(confidence_level=level, min_calib=30).calibrate(conf, correct)


class TestActiveInference(unittest.TestCase):
    def test_surprise_habituates_then_spikes(self):
        m = ActiveInferenceModel(["gradient", "optimization", "loss", "trading"])
        s = [m.observe("gradient")["surprise"] for _ in range(3)]
        self.assertGreater(s[0], s[1])           # habituation: surprise falls on repeats
        self.assertGreater(s[1], s[2])
        novel = m.observe("trading")["surprise"]
        self.assertGreater(novel, s[2])          # novelty: surprise spikes on a new topic

    def test_engine_is_pymdp(self):
        m = ActiveInferenceModel(["a", "b", "c"])
        self.assertEqual(m.status()["engine"], "pymdp")

    def test_curiosity_points_at_unexplored(self):
        m = ActiveInferenceModel(["gradient", "trading", "memory"])
        for _ in range(4):
            m.observe("gradient")
        self.assertNotEqual(m.most_curious_topic(), "gradient")


class TestReasoning(unittest.TestCase):
    def test_react_multisteps_and_grounds(self):
        g = ReasoningGraph(_Brain(), recall_k=4, max_steps=3)
        r = g.react("how does gradient optimization reduce loss")
        self.assertEqual(r["strategy"], "react")
        self.assertGreaterEqual(r["n_steps"], 1)
        self.assertTrue(r["recalled"])           # gathered supporting evidence

    def test_tree_of_thoughts_branches_and_scores(self):
        g = ReasoningGraph(_Brain(), recall_k=4)
        r = g.tree_of_thoughts("gradient descent optimization")
        self.assertEqual(r["strategy"], "tree-of-thoughts")
        self.assertTrue(r["branches"])
        # branches are ordered by score (best first)
        scores = [b["score"] for b in r["branches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestSymbolic(unittest.TestCase):
    def test_transitive_with_trace(self):
        sr = SymbolicReasoner([("ml", "optimization"), ("optimization", "calculus"),
                               ("calculus", "limits")])
        r = sr.related("ml")
        self.assertIn("limits", r["related"])    # transitive closure ml→…→limits
        self.assertEqual(r["trace"]["limits"], "ml -> optimization -> calculus -> limits")

    def test_from_brain_reads_graph(self):
        sr = SymbolicReasoner.from_brain(_Brain())
        r = sr.related("gradient")
        self.assertIn("loss", r["related"])      # gradient→optimization→loss via the KG


class TestCausal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pandas as pd
        rng = np.random.default_rng(7)
        n = 500
        v = rng.normal(size=n)
        t = (0.8 * v + rng.normal(size=n) > 0).astype(float)
        y = 1.7 * t + v + 0.3 * rng.normal(size=n)
        cls.df = pd.DataFrame({"confounder": v, "treat": t, "outcome": y})

    def test_effect_recovered_and_robust(self):
        eff = CausalAnalyzer().estimate_effect(self.df, "treat", "outcome", ["confounder"])
        self.assertAlmostEqual(eff["ate"], 1.7, delta=0.25)   # recovers the true effect
        self.assertTrue(eff["robust"])                        # survives placebo + random-cause

    def test_discovery_finds_edges(self):
        disc = CausalAnalyzer().discover(self.df)
        self.assertIn(("treat", "outcome"), disc["edges"])


class TestCalibration(unittest.TestCase):
    def test_monotone_gate_and_calibration_helps(self):
        ab = _abstainer()
        st = ab.status()
        self.assertEqual(st["engine"], "conformal+netcal")
        self.assertLessEqual(st["ece_calibrated"], st["ece_raw"])      # calibration lowers ECE
        self.assertLessEqual(st["empirical_risk"], 0.2 + 1e-9)         # risk ≤ α
        self.assertFalse(ab.decide(0.05)["answer"])                   # low conf → abstain
        self.assertTrue(ab.decide(0.95)["answer"])                    # high conf → answer

    def test_abstain_escalates(self):
        ab = _abstainer()
        d = ab.decide(0.05)
        self.assertTrue(d["abstain"])
        self.assertTrue(d["escalate_to_human"])


class TestConstitution(unittest.TestCase):
    def setUp(self):
        self.con = Constitution()

    def test_redacts_secrets(self):
        r = self.con.audit("your key is api_key=sk-live-abcd1234efgh5678")
        self.assertFalse(r["ok"])
        self.assertNotIn("sk-live-abcd1234efgh5678", r["safe_text"])
        self.assertIn("[REDACTED]", r["safe_text"])

    def test_flags_ungrounded_confident_claim(self):
        r = self.con.audit("The answer is definitely 42 and absolutely certain.", grounded_in=[])
        self.assertFalse(r["ok"])

    def test_passes_honest_escalation(self):
        r = self.con.audit("I'm not confident — escalating to you.", abstained=True)
        self.assertTrue(r["ok"])


class TestThinker(unittest.TestCase):
    def test_grounded_answers(self):
        th = Thinker.from_brain(_Brain(), abstainer=_abstainer())
        r = th.think("How does gradient descent reduce the loss during optimization?")
        self.assertFalse(r["abstained"])
        self.assertTrue(r["constitution"]["ok"])
        self.assertTrue(r["symbolic"])                 # symbolic enrichment present
        self.assertIsNotNone(r["surprise"])            # reflected via active inference

    def test_unknown_abstains_and_escalates(self):
        th = Thinker.from_brain(_Brain(), abstainer=_abstainer())
        r = th.think("What were the exact closing prices of every stock in 1987?")
        self.assertTrue(r["abstained"])
        self.assertTrue(r["escalate_to_human"])

    def test_status_reports_all_layers(self):
        th = Thinker.from_brain(_Brain(), abstainer=_abstainer())
        st = th.status()
        for layer in ("reasoner", "active_inference", "symbolic", "calibration", "constitution"):
            self.assertIn(layer, st)


class TestBrainAgentIntegration(unittest.TestCase):
    def test_agent_think_delegates_to_thinker(self):
        from core.brain_agent import BrainAgent
        agent = BrainAgent(_Brain(), recall_k=4)
        agent.attach_thinker(Thinker.from_brain(_Brain(), abstainer=_abstainer()))
        out = agent.think("How does gradient descent reduce the loss?")
        self.assertTrue(out["thinking"])
        self.assertIn("answer", out)
        self.assertTrue(agent.status()["thinking"])

    def test_agent_without_thinker_falls_back(self):
        from core.brain_agent import BrainAgent
        agent = BrainAgent(_Brain(), recall_k=4)
        out = agent.think("anything")
        self.assertFalse(out["thinking"])


class TestDemo(unittest.TestCase):
    def test_build_demo_thinking_snapshot(self):
        import json

        from run_thinking_p45 import build_demo_thinking
        snap = build_demo_thinking()
        self.assertEqual(snap["phase"], "P4.5")
        self.assertFalse(snap["grounded_question"]["abstained"])
        self.assertTrue(snap["unknown_question"]["abstained"])
        # the snapshot must be JSON-serialisable for the dashboard endpoint
        json.dumps(snap, default=str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
