"""run_brain_agent.py — Phase P4.1 (Talk to the brain) OFFLINE demo.

Drives the LangGraph `BrainAgent` end to end, fully OFFLINE and deterministic (NO
network, NO API keys, NO LLM required). The agent is a real LangGraph StateGraph that
FIRST recalls from the brain's human-like associative memory (KnowledgeBrain.recall)
and THEN responds grounded in that recalled context (retrieval-augmented):

  1. ask() WITH an injected stub LLM — proves the retrieval-augmented path: the reply is
     produced by the (stub) LLM, the recalled memory titles are surfaced, and the system
     prompt the LLM sees carries the recalled context (so the answer is grounded).

  2. ask() OFFLINE with NO LLM — proves the honest memory-grounded fallback: with no LLM
     configured the agent degrades to a template answer built straight from recalled
     memory (never an error, always works).

  3. status() — engine/has_memory/llm/recall_k.

The KnowledgeBrain here is a small REAL in-memory brain (a few ingested project facts),
so recall is genuine semantic+associative recall — not a stub. `build_demo_brain_agent()`
returns a JSON-able snapshot {ask, status} for the dashboard, cached at module level.

Usage:
    .venv/bin/python run_brain_agent.py
"""
from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")  # keep the demo output clean (chroma/embeddings warns)

from core.brain_agent import BrainAgent
from memory.brain import KnowledgeBrain

# Deterministic offline facts the brain "knows" — ingested into a real KnowledgeBrain so
# recall() is genuine semantic + associative recall, not a canned lookup.
_FACTS = [
    ("ML Network Brain",
     "The ML Network Brain is a CPU-first network of hundreds of prediction-model nodes "
     "coordinated by a learning brain agent. It runs offline and routes queries to expert "
     "nodes, then learns from the outcomes."),
    ("KnowledgeBrain memory",
     "The KnowledgeBrain is the Phase-4 associative memory: it ingests documents, embeds "
     "chunks into a vector store, and recalls with human-like spreading activation over a "
     "knowledge graph fused by reciprocal rank fusion and salience."),
    ("LangGraph brain agent",
     "The P4.1 BrainAgent is a LangGraph StateGraph that recalls memory then responds with "
     "an LLM grounded in that recalled context. It degrades to a memory-grounded template "
     "when no LLM is configured, so it always works offline."),
    ("Trading phase",
     "The trading phase adds an NSE and crypto execution stack with a trade journal, "
     "options intelligence, and an evolved-strategy brain pipeline."),
]


def _build_demo_brain() -> KnowledgeBrain:
    """A small REAL in-memory KnowledgeBrain seeded with deterministic project facts."""
    brain = KnowledgeBrain()
    for title, text in _FACTS:
        brain.ingest_text(title, text)
    return brain


def _stub_llm(messages: list[dict]) -> str:
    """Deterministic stand-in for core.llm.chat — proves the injected-LLM path WITHOUT a
    network call. Echoes the user question and confirms it saw the recalled memory in the
    system prompt, so the reply is visibly grounded in retrieval."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    grounded = "Recalled memory:" in system and "(no relevant memory found)" not in system
    tag = "grounded in recalled memory" if grounded else "no memory grounding"
    return f"[stub-llm] Re: {user!r} — answered ({tag})."


def build_demo_brain_agent() -> dict:
    """JSON-able snapshot {ask, status} for the dashboard. Offline + deterministic."""
    brain = _build_demo_brain()
    agent = BrainAgent(brain, llm_chat=_stub_llm)
    return {
        "ask": agent.ask("What is the ML Network Brain and how does it remember things?"),
        "status": agent.status(),
    }


def main() -> int:
    def _hdr(s: str) -> None:
        print("\n" + s + "\n" + "─" * min(len(s), 72))

    print("run_brain_agent.py — P4.1 LangGraph BrainAgent (offline, deterministic)")

    brain = _build_demo_brain()
    q = "What is the ML Network Brain and how does it remember things?"

    # 1) ask() WITH injected stub LLM — retrieval-augmented (grounded) reply.
    _hdr("1. ask() with an injected (stub) LLM — retrieval-augmented, grounded reply")
    agent = BrainAgent(brain, llm_chat=_stub_llm)
    out = agent.ask(q)
    print(f"  Q: {q}")
    print(f"  reply:       {out['reply']}")
    print(f"  llm_used:    {out['llm_used']}   used_memory: {out['used_memory']}")
    print(f"  recalled titles: {[r['title'] for r in out['recalled']]}")
    assert out["llm_used"] and out["used_memory"], "expected LLM-used + memory-grounded"
    assert "grounded in recalled memory" in out["reply"], "reply not grounded in memory"
    print("  ✔ injected-LLM reply is grounded in recalled memory — verified.")

    # 2) ask() OFFLINE with NO LLM — honest memory-grounded template fallback.
    _hdr("2. ask() OFFLINE with no LLM — honest memory-grounded template fallback")
    offline = BrainAgent(brain)        # no injected chat
    offline._llm = None                # force fully offline (ignore any .env provider key)
    out2 = offline.ask(q)
    print(f"  reply:       {out2['reply'][:200]}")
    print(f"  llm_used:    {out2['llm_used']}   used_memory: {out2['used_memory']}")
    assert not out2["llm_used"] and out2["used_memory"], "expected offline + memory-grounded"
    assert "no LLM configured" in out2["reply"], "offline fallback marker missing"
    print("  ✔ offline fallback answers straight from memory (no LLM) — verified.")

    # 3) status().
    _hdr("3. status()")
    print(f"  {json.dumps(agent.status(), default=str)}")

    # 4) JSON-able dashboard snapshot.
    _hdr("4. build_demo_brain_agent() — JSON-able dashboard snapshot")
    print(json.dumps(build_demo_brain_agent(), indent=2, default=str)[:800] + "  ...")

    print("\n✅ P4.1 BrainAgent demo complete (offline, deterministic) — talk to the brain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
