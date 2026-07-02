"""core/chat_brain.py — P4.1: chat with the brain (RAG-grounded, cloud-LLM).

Wires the dashboard chat to the project's KnowledgeBrain: a user message is grounded in
recalled memory (the brain has ingested the project's own docs), then answered by a cloud
LLM via core.llm. Returns {reply, sources, thoughts, error}:
  • sources  — the real memory passages used (honest-wiring; recall works even with no LLM).
  • thoughts — a short ephemeral trace of the brain's state (seed of the Stream-of-Mind panel).
  • error    — a graceful message (e.g. no LLM key configured) instead of a crash.

The KnowledgeBrain is built lazily on first call and cached; doc ingestion failures degrade
to an LLM-only chat (sources empty), never an error.
"""
from __future__ import annotations

import glob
import os
import threading

from core import llm

_BRAIN = None
_BRAIN_BUILDING = False
_BRAIN_LOCK = threading.Lock()
SYSTEM = (
    "You are the ML Network Brain — the meta-controller of a CPU-first network of hundreds of "
    "prediction-model nodes with a learning memory, and an autonomous trading + research agent. "
    "You can converse two-way with the operator and report your OWN progress. Answer concisely, "
    "technically, and HONESTLY; if you don't know or the state doesn't say, say so. Use the "
    "BRAIN STATE and MEMORY context when relevant; when asked about your knowledge, learning, or "
    "strategies, quote the real numbers from BRAIN STATE."
)


def _brain_state() -> str:
    """A compact, REAL snapshot of the brain's own progress (foundry, hypotheses, knowledge)
    so the chat can honestly report on itself. Best-effort; empty string on failure."""
    bits = []
    try:
        from trading.strategy.foundry import StrategyFoundry
        fj = StrategyFoundry(persist=True).to_json()
        tracked = [r for r in fj.get("leaderboard", []) if r.get("best_score") is not None]
        top = tracked[0] if tracked else None
        bits.append(f"Strategy Foundry: {fj.get('n_specs')} strategies across "
                    f"{len(fj.get('by_segment', {}))} segments, {len(tracked)} tracked by real "
                    f"performance" + (f"; best = {top['name']} ({top['segment']}, score "
                    f"{top['best_score']})" if top else ""))
    except Exception:
        pass
    try:
        from trading.brain.hypothesis import HypothesisLedger
        c = HypothesisLedger(persist=True).counts()
        bits.append(f"Hypothesis ledger: {c.get('confirmed', 0)} confirmed / "
                    f"{c.get('refuted', 0)} refuted / {c.get('open', 0)} open.")
    except Exception:
        pass
    try:
        import os as _os
        from trading import state as _st
        rf = _st._path("research_findings.json")
        if rf.exists():
            import json as _j
            n = len(_j.load(open(rf)).get("briefs", []))
            bits.append(f"Latest research cycle: {n} symbols researched online.")
    except Exception:
        pass
    return " ".join(bits)


def _build_brain():
    """Heavy: SentenceTransformer embedding init + ingest 14 project .md. Runs in a bg thread."""
    global _BRAIN
    from memory.brain import KnowledgeBrain
    b = KnowledgeBrain()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in sorted(glob.glob(os.path.join(root, "*.md")))[:14]:       # the project's own docs
        try:
            b.ingest_file(path)
        except Exception:
            pass
    _BRAIN = b


def _brain():
    """NON-BLOCKING (2026-07-02 fix): building the KnowledgeBrain (embedding-model init +
    doc ingestion) synchronously in the request thread hung /api/chat past the socket
    timeout. Now it warms in ONE background thread; until ready this returns None and chat
    answers LLM-only (no doc grounding), then auto-upgrades to grounded answers once warm."""
    global _BRAIN_BUILDING
    if _BRAIN is not None:
        return _BRAIN
    with _BRAIN_LOCK:
        if not _BRAIN_BUILDING:
            _BRAIN_BUILDING = True
            threading.Thread(target=_build_brain, daemon=True, name="chat-brain-warm").start()
    return None


def chat(message: str, history: list[dict] | None = None) -> dict:
    message = (message or "").strip()
    if not message:
        return {"reply": "", "sources": [], "thoughts": [], "error": "empty message"}

    thoughts = ["recalling memory…"]
    sources, context = [], ""
    b = _brain()
    if b is None:
        thoughts.append("memory warming up — answering LLM-only")
    else:
        try:
            hits = b.recall(message, k=4)
            thoughts.append(f"recalled {len(hits)} passages")
            sources = [{"title": h["title"], "snippet": h["snippet"]} for h in hits]
            context = "\n\n".join(f"[{h['title']}] {h['snippet']}" for h in hits)
        except Exception as e:
            thoughts.append(f"memory unavailable ({type(e).__name__})")

    sel = llm.active_model()
    if not sel:
        return {"reply": "", "sources": sources, "thoughts": thoughts,
                "error": ("no LLM key configured — add a free key to .env "
                          "(GROQ_API_KEY / CEREBRAS_API_KEY / OPENROUTER_API_KEY / GOOGLE_AISTUDIO_API_KEY)")}
    thoughts.append(f"thinking via {llm.provider_name(sel[0])}…")

    msgs = [{"role": "system", "content": SYSTEM}]
    bstate = _brain_state()
    if bstate:
        msgs.append({"role": "system", "content": "BRAIN STATE (your own real progress):\n" + bstate})
        thoughts.append("checked my own state")
    if context:
        msgs.append({"role": "system", "content": "MEMORY:\n" + context})
    for turn in (history or [])[-6:]:                      # short rolling context
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant"):
            msgs.append({"role": turn["role"], "content": str(turn.get("content", ""))})
    msgs.append({"role": "user", "content": message})

    try:
        reply = llm.chat(msgs)
    except Exception as e:
        return {"reply": "", "sources": sources, "thoughts": thoughts,
                "error": f"LLM error: {type(e).__name__}: {e}"[:200]}
    thoughts.append("done")
    return {"reply": reply, "sources": sources, "thoughts": thoughts, "error": None}


def _build_messages(message: str, context: str, history: list[dict] | None) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM}]
    bstate = _brain_state()
    if bstate:
        msgs.append({"role": "system", "content": "BRAIN STATE (your own real progress):\n" + bstate})
    if context:
        msgs.append({"role": "system", "content": "MEMORY:\n" + context})
    for turn in (history or [])[-6:]:
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant"):
            msgs.append({"role": turn["role"], "content": str(turn.get("content", ""))})
    msgs.append({"role": "user", "content": message})
    return msgs


def chat_stream(message: str, history: list[dict] | None = None):
    """Generator of streaming events for /api/chat/stream:
    {'type':'thought'|'sources'|'token'|'done'|'error', ...}."""
    message = (message or "").strip()
    if not message:
        yield {"type": "error", "error": "empty message"}
        return

    yield {"type": "thought", "text": "recalling memory…"}
    context = ""
    b = _brain()
    if b is None:
        yield {"type": "thought", "text": "memory warming up — answering LLM-only"}
    else:
        try:
            hits = b.recall(message, k=4)
            yield {"type": "thought", "text": f"recalled {len(hits)} passages"}
            srcs = [{"title": h["title"], "snippet": h["snippet"]} for h in hits]
            context = "\n\n".join(f"[{h['title']}] {h['snippet']}" for h in hits)
            if srcs:
                yield {"type": "sources", "sources": srcs}
        except Exception as e:
            yield {"type": "thought", "text": f"memory unavailable ({type(e).__name__})"}

    sel = llm.active_model()
    if not sel:
        yield {"type": "error",
               "error": ("no LLM key configured — add a free key to .env "
                         "(GROQ_API_KEY / CEREBRAS_API_KEY / OPENROUTER_API_KEY / GOOGLE_AISTUDIO_API_KEY)")}
        return
    yield {"type": "thought", "text": f"thinking via {llm.provider_name(sel[0])}…"}

    try:
        for delta in llm.chat_stream(_build_messages(message, context, history)):
            yield {"type": "token", "text": delta}
    except Exception as e:
        yield {"type": "error", "error": f"LLM error: {type(e).__name__}"}
        return
    yield {"type": "thought", "text": "done"}
    yield {"type": "done"}
