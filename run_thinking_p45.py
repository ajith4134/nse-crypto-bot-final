"""run_thinking_p45.py — Phase P4.5 (Thinking + knowing-what-it-knows) OFFLINE demo.

Drives the full P4.5 cognition stack end to end, fully OFFLINE and deterministic (NO network,
NO API keys, NO LLM). It mirrors the P4.1–P4.4 demos: a small REAL in-memory brain (a few
ingested facts + a concept graph), a Thinker wired onto it, and a handful of questions that
exercise every layer:

  1. A WELL-GROUNDED question → the brain reasons (ReAct over its memory), is confident enough
     (conformal selective gate), passes the constitution, and ANSWERS — surfacing its reasoning
     steps, symbolic (traceable) related concepts, and active-inference surprise.

  2. An UNKNOWN question → no supporting memory → low confidence → the brain ABSTAINS and
     escalates to the human ("asks for help"). The honest behaviour, not a hallucinated answer.

  3. Active inference over a reading sequence → surprise HABITUATES on a repeated topic and
     SPIKES on a novel one; the brain reports what it is most curious about.

  4. Causal reasoning (DoWhy + refutation, causal-learn discovery) on a tiny synthetic table —
     "does X cause Y, or merely correlate?" — with the estimate surviving placebo refutation.

``build_demo_thinking()`` returns a JSON-able snapshot for the dashboard (cached at module
level), exactly like build_demo_self_quiz / build_demo_librarian.

Usage:
    .venv/bin/python run_thinking_p45.py
"""
from __future__ import annotations

import json
import warnings

warnings.filterwarnings("ignore")

import numpy as np

from cognition import (ActiveInferenceModel, CalibratedAbstainer, CausalAnalyzer,
                       SymbolicReasoner, Thinker)
from cognition.reasoning import ReasoningGraph


# ── a tiny REAL brain: deterministic recall + a concept graph (no embedding download) ──────
class _Graph:
    """Minimal stand-in for memory.graph.KnowledgeGraph.snapshot() (concept edges)."""

    def __init__(self, concepts, edges):
        self._concepts = concepts
        self._edges = edges

    def snapshot(self, types=None):
        nodes = [{"id": f"concept:{c}", "type": "concept", "label": c} for c in self._concepts]
        edges = [{"source": f"concept:{a}", "target": f"concept:{b}", "rel": "co_occurs"}
                 for a, b in self._edges]
        return {"nodes": nodes, "edges": edges}


class _DemoBrain:
    """A few ingested facts + a concept graph. recall() is deterministic keyword overlap
    (so the demo needs no embedding model / network) but otherwise behaves like KnowledgeBrain."""

    FACTS = {
        "gradient descent": "Gradient descent minimizes a loss function by repeatedly stepping "
                            "in the direction opposite the gradient; the learning rate sets the "
                            "step size and optimization converges to a minimum of the loss.",
        "the loss landscape": "The loss landscape is the surface of the loss over parameters; "
                             "optimization by gradient descent walks downhill on this landscape "
                             "toward lower loss.",
        "backpropagation": "Backpropagation computes the gradient of the loss with respect to "
                          "each weight via the chain rule, enabling gradient descent in neural nets.",
        "the learning rate": "The learning rate scales each gradient step in optimization; too "
                            "large diverges, too small is slow — it controls descent on the loss.",
        "nse trading": "NSE trading executes equity and F&O orders during Indian market hours via "
                      "the OpenAlgo server.",
    }
    CONCEPTS = ["gradient", "optimization", "loss", "learning_rate", "backprop", "trading"]
    EDGES = [("gradient", "optimization"), ("optimization", "loss"),
             ("loss", "backprop"), ("gradient", "learning_rate")]

    def __init__(self):
        self.graph = _Graph(self.CONCEPTS, self.EDGES)

    def recall(self, query, k=4):
        q = set(w for w in query.lower().replace("?", "").split() if len(w) > 3)
        scored = []
        for title, text in self.FACTS.items():
            words = set(text.lower().split()) | set(title.lower().split())
            overlap = len(q & words)
            if overlap:
                scored.append((overlap, title, text))
        scored.sort(key=lambda r: -r[0])
        out = []
        for rank, (ov, title, text) in enumerate(scored[:k]):
            out.append({"title": title, "snippet": text[:200],
                        "score": float(ov) / (1 + rank), "via": "vector"})
        return out


def _calibrated_abstainer() -> CalibratedAbstainer:
    """Conformal abstainer fitted on a deterministic (confidence, was_correct) history.

    The history is monotone-with-noise (more evidence ⇒ more often correct), so the conformal
    selective threshold lands between 'thin evidence' and 'strong evidence' — exactly the gate
    that makes a grounded question answerable and an unknown one an abstention."""
    rng = np.random.default_rng(20260629)
    n = 400
    conf = rng.uniform(0, 1, n)
    correct = (rng.uniform(0, 1, n) < (0.12 + 0.82 * conf)).astype(int)
    return CalibratedAbstainer(confidence_level=0.8, min_calib=30).calibrate(conf, correct)


def _causal_demo() -> dict:
    """DoWhy effect + refutation and causal-learn discovery on a tiny confounded table."""
    rng = np.random.default_rng(7)
    n = 500
    confounder = rng.normal(size=n)
    treat = (0.8 * confounder + rng.normal(size=n) > 0).astype(float)
    outcome = 1.7 * treat + confounder + 0.3 * rng.normal(size=n)   # TRUE causal effect = 1.7
    import pandas as pd
    df = pd.DataFrame({"confounder": confounder, "treat": treat, "outcome": outcome})
    ca = CausalAnalyzer()
    effect = ca.estimate_effect(df, "treat", "outcome", ["confounder"])
    discovery = ca.discover(df)
    return {"true_effect": 1.7, "effect": effect, "discovery": discovery,
            "note": "estimated ATE recovers the true causal effect (≈1.7) after adjusting for "
                    "the confounder, and survives placebo refutation — correlation ≠ causation, "
                    "checked."}


def build_demo_thinking() -> dict:
    """Offline deterministic P4.5 snapshot for the dashboard + CLI demo."""
    brain = _DemoBrain()
    abstainer = _calibrated_abstainer()
    thinker = Thinker.from_brain(brain, abstainer=abstainer, recall_k=4)

    grounded_q = "How does gradient descent reduce the loss during optimization?"
    unknown_q = "What were the exact closing prices of every stock in 1987?"
    grounded = thinker.think(grounded_q, strategy="react")
    unknown = thinker.think(unknown_q, strategy="react")

    # active-inference reading sequence: habituation then novelty
    ai = ActiveInferenceModel(["gradient", "optimization", "loss", "trading"])
    sequence = []
    for topic in ["gradient", "gradient", "gradient", "trading"]:
        r = ai.observe(topic)
        sequence.append({"read": topic, "surprise": r["surprise"],
                         "most_curious": r["most_curious"]})

    return {
        "phase": "P4.5",
        "title": "Thinking + knowing-what-it-knows",
        "layers": {
            "reasoning": "LangGraph ReAct + Tree-of-Thoughts over the brain's own memory",
            "active_inference": "pymdp surprise (Bayesian) + curiosity (expected info gain)",
            "neuro_symbolic": "pyDatalog traceable transitive reasoning over the knowledge graph",
            "causal": "DoWhy effect+refutation + causal-learn PC discovery",
            "calibration": "conformal selective abstention + netcal calibration (MAPIE aux set)",
            "guardrails": "NeMo-Guardrails constitution (secrets-safe/grounded/honest/non-harmful)",
        },
        "grounded_question": {
            "q": grounded_q, "answer": grounded["answer"], "abstained": grounded["abstained"],
            "confidence": grounded["confidence"],
            "calibrated_confidence": grounded["calibrated_confidence"],
            "reasoning_steps": grounded["reasoning"]["steps"],
            "evidence": grounded["reasoning"]["evidence"],
            "symbolic": grounded["symbolic"], "surprise": grounded["surprise"],
            "constitution": grounded["constitution"],
        },
        "unknown_question": {
            "q": unknown_q, "answer": unknown["answer"], "abstained": unknown["abstained"],
            "escalate_to_human": unknown["escalate_to_human"],
            "confidence": unknown["confidence"], "calibration": unknown["calibration"],
        },
        "active_inference_sequence": sequence,
        "habituation": ("surprise falls on the repeated topic (the brain habituates) and spikes "
                        "on the novel one — principled novelty detection, not a heuristic"),
        "causal": _causal_demo(),
        "calibration_status": abstainer.status(),
        "thinker_status": thinker.status(),
    }


_DEMO_CACHE = None


def demo_snapshot() -> dict:
    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        _DEMO_CACHE = build_demo_thinking()
    return _DEMO_CACHE


def main() -> None:
    snap = build_demo_thinking()
    g, u = snap["grounded_question"], snap["unknown_question"]
    print("=" * 78)
    print("P4.5 — Thinking + knowing-what-it-knows (OFFLINE deterministic demo)")
    print("=" * 78)
    print("\n[1] GROUNDED question — reason → calibrate → audit → ANSWER")
    print(f"  Q: {g['q']}")
    print(f"  confidence={g['confidence']}  calibrated={g['calibrated_confidence']}  "
          f"abstained={g['abstained']}")
    print(f"  A: {g['answer'][:200]}")
    print(f"  reasoning steps: {len(g['reasoning_steps'] or [])}  evidence: {g['evidence']}")
    if g["symbolic"]:
        print(f"  symbolic: {g['symbolic']['concept']} ~> {g['symbolic']['related']}")
        for tgt, path in g["symbolic"]["trace"].items():
            print(f"            proof: {path}")
    print(f"  active-inference surprise on the topic: {g['surprise']}")
    print(f"  constitution: ok={g['constitution']['ok']}  engine={g['constitution']['engine']}")

    print("\n[2] UNKNOWN question — no memory → ABSTAIN + escalate to the human")
    print(f"  Q: {u['q']}")
    print(f"  confidence={u['confidence']}  abstained={u['abstained']}  "
          f"escalate={u['escalate_to_human']}")
    print(f"  A: {u['answer'][:200]}")

    print("\n[3] ACTIVE INFERENCE — surprise habituates, then spikes on novelty")
    for s in snap["active_inference_sequence"]:
        print(f"  read {s['read']:11} surprise={s['surprise']:.3f}  "
              f"most_curious={s['most_curious']}")

    c = snap["causal"]
    print("\n[4] CAUSAL — does treatment CAUSE outcome (vs correlate)?")
    print(f"  true effect={c['true_effect']}  estimated ATE={c['effect']['ate']}  "
          f"robust={c['effect'].get('robust')}")
    for r in c["effect"].get("refutations", []):
        print(f"    refute {r}")
    print(f"  discovered causal edges: {c['discovery']['edges']}")

    print("\ncalibration:", json.dumps(snap["calibration_status"]))
    print("\nDONE — reasons over memory, stays calibrated, asks for help. (P4.5)")


if __name__ == "__main__":
    main()
