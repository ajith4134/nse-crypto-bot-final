"""run_stream_of_mind.py — Phase P4.6 (Stream-of-Mind + observability) OFFLINE demo.

Drives the P4.6 stack end to end, fully OFFLINE and deterministic (NO network, NO API keys,
NO LLM). It mirrors the P4.1–P4.5 demos and shows the brain's live "state of mind" + the
visible working-memory → long-term-memory pipeline:

  1. A real Thinker (P4.5) thinks about a grounded question. StreamOfMind turns that ONE think
     cycle into a stream of REAL thought-events (goal, ReAct steps, pymdp surprise/curiosity,
     symbolic insight, calibrated verdict).
  2. Each thought enters the GlobalWorkspace competition: per tick the highest-salience thought
     wins the single broadcast slot; a winner above the consolidation threshold is WRITTEN to
     long-term memory (KnowledgeBrain.ingest_text). Boilerplate fades; salient thoughts persist —
     the working→long-term pipeline, made visible.
  3. Each cycle is also recorded as a durable Langfuse trace (core.observability) — a silent
     no-op offline, a replayable thought-history when LANGFUSE_* keys are set.

The dashboard renders these thoughts live through the AG-UI protocol (POST /api/agui →
@ag-ui/client HttpAgent in the React Stream-of-Mind panel). ``build_demo_thinking`` here is the
offline snapshot for GET /api/brain/stream/status.

Usage:
    .venv/bin/python run_stream_of_mind.py
"""
from __future__ import annotations

import json
import warnings

warnings.filterwarnings("ignore")

from cognition import Thinker
from cognition.stream_of_mind import StreamOfMind


class _DemoBrain:
    """Deterministic recall + a concept graph + a writable long-term store (ingest_text),
    so the working→long-term consolidation is visible offline (no embedding download)."""

    FACTS = {
        "gradient descent": "Gradient descent minimizes a loss function by repeatedly stepping "
                            "opposite the gradient; the learning rate sets the step size.",
        "the loss surface": "The loss surface is walked downhill by optimization toward lower loss.",
        "backpropagation": "Backpropagation computes the gradient of the loss for each weight.",
        "the learning rate": "The learning rate scales each gradient step in optimization.",
    }

    class _Graph:
        CONCEPTS = ["gradient", "optimization", "loss", "learning_rate", "backprop"]
        EDGES = [("gradient", "optimization"), ("optimization", "loss"), ("loss", "backprop")]

        def snapshot(self, types=None):
            return {"nodes": [{"id": f"concept:{c}", "type": "concept", "label": c}
                              for c in self.CONCEPTS],
                    "edges": [{"source": f"concept:{a}", "target": f"concept:{b}",
                               "rel": "co_occurs"} for a, b in self.EDGES]}

    def __init__(self):
        self.graph = self._Graph()
        self.long_term: list[dict] = []      # thoughts consolidated from working memory

    def recall(self, query, k=4):
        q = {w for w in query.lower().split() if len(w) > 3}
        out = []
        for title, text in self.FACTS.items():
            if q & (set(text.lower().split()) | set(title.lower().split())):
                out.append({"title": title, "snippet": text, "score": 1.0 / (1 + len(out))})
        return out[:k]

    def ingest_text(self, title, text):
        self.long_term.append({"title": title, "text": text})
        return "doc:" + title


def _abstainer():
    import numpy as np
    from cognition import CalibratedAbstainer
    rng = np.random.default_rng(20260629)
    n = 400
    conf = rng.uniform(0, 1, n)
    correct = (rng.uniform(0, 1, n) < (0.12 + 0.82 * conf)).astype(int)
    return CalibratedAbstainer(confidence_level=0.8, min_calib=30).calibrate(conf, correct)


def _build() -> tuple:
    brain = _DemoBrain()
    thinker = Thinker.from_brain(brain, abstainer=_abstainer(), recall_k=4)
    # deterministic logical clock so ids/timestamps are reproducible run-to-run
    import itertools
    ticks = itertools.count(1)
    som = StreamOfMind(thinker, brain=brain, clock=lambda: next(ticks) * 1000)
    return brain, som


def build_demo_thinking() -> dict:
    """Offline deterministic P4.6 snapshot for GET /api/brain/stream/status."""
    brain, som = _build()
    grounded = som.think("How does gradient descent reduce the loss during optimization?")
    unknown = som.think("What were the exact tick prices of every stock in 1973?")
    return {
        "phase": "P4.6",
        "title": "Stream-of-Mind + observability",
        "pipeline": "working memory (ephemeral, TTL-fade) → Global Workspace competition → "
                    "long-term memory (salient winners consolidated to the KnowledgeBrain)",
        "transport": "AG-UI protocol (POST /api/agui) → @ag-ui/client HttpAgent → React panel",
        "grounded": {
            "q": grounded["query"], "answer": grounded["answer"],
            "thoughts": grounded["thoughts"], "n_thoughts": grounded["n_thoughts"],
            "n_consolidated": grounded["n_consolidated"],
            "consolidated": [t["text"] for t in grounded["consolidated"]],
        },
        "unknown": {
            "q": unknown["query"], "answer": unknown["answer"],
            "abstained": unknown["abstained"], "n_thoughts": unknown["n_thoughts"],
            "n_consolidated": unknown["n_consolidated"],
        },
        "long_term_memory_grew_to": len(brain.long_term),
        "workspace": som.workspace.status(),
        "observability": som.status()["observability"],
        "recent": som.recent_thoughts()[-12:],
    }


_DEMO_CACHE = None


def demo_snapshot() -> dict:
    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        _DEMO_CACHE = build_demo_thinking()
    return _DEMO_CACHE


# Module-level live engine for the AG-UI endpoint (built once; offline demo brain).
_LIVE = None


def live_stream(query: str, *, strategy: str = "react"):
    """Yield NDJSON-ready thought events for one think cycle (used by /api/agui translation)."""
    global _LIVE
    if _LIVE is None:
        _, _LIVE = _build()
    yield from _LIVE.stream(query or "How does the brain decide when to ask for help?",
                            strategy=strategy)


def main() -> None:
    snap = build_demo_thinking()
    g, u = snap["grounded"], snap["unknown"]
    print("=" * 78)
    print("P4.6 — Stream-of-Mind + observability (OFFLINE deterministic demo)")
    print("=" * 78)
    print(f"\npipeline: {snap['pipeline']}")
    print(f"transport: {snap['transport']}\n")
    print("[1] GROUNDED — the brain's live stream of mind (★ = consolidated to long-term memory)")
    print(f"  Q: {g['q']}")
    for t in g["thoughts"]:
        star = "★LTM" if t["consolidated"] else "    "
        print(f"    {star} [{t['kind']:9}] salience={t['salience']:.2f}  {t['text'][:62]}")
    print(f"  → {g['n_thoughts']} thoughts, {g['n_consolidated']} consolidated to long-term memory")

    print("\n[2] UNKNOWN — low surprise/confidence → fades, nothing consolidates")
    print(f"  Q: {u['q']}")
    print(f"  abstained={u['abstained']}  thoughts={u['n_thoughts']}  "
          f"consolidated={u['n_consolidated']}")

    print(f"\n[3] Long-term memory grew to {snap['long_term_memory_grew_to']} consolidated "
          "thought(s) — the visible working→long-term pipeline.")
    print(f"\nGlobal Workspace: {json.dumps(snap['workspace'])}")
    print(f"Observability (Langfuse): {json.dumps(snap['observability'])}")
    print("\nDONE — you can see its state of mind; salient thoughts become knowledge. (P4.6)")


if __name__ == "__main__":
    main()
