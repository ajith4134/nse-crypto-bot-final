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

from core import llm

_BRAIN = None
SYSTEM = (
    "You are the ML Network Brain — the meta-controller of a CPU-first network of hundreds of "
    "prediction-model nodes with a learning memory. Answer concisely, technically, and HONESTLY; "
    "if you don't know or the memory doesn't say, say so. Prefer the provided MEMORY context when "
    "it is relevant."
)


def _brain():
    global _BRAIN
    if _BRAIN is None:
        from memory.brain import KnowledgeBrain
        b = KnowledgeBrain()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for path in sorted(glob.glob(os.path.join(root, "*.md")))[:14]:   # the project's own docs
            try:
                b.ingest_file(path)
            except Exception:
                pass
        _BRAIN = b
    return _BRAIN


def chat(message: str, history: list[dict] | None = None) -> dict:
    message = (message or "").strip()
    if not message:
        return {"reply": "", "sources": [], "thoughts": [], "error": "empty message"}

    thoughts = ["recalling memory…"]
    sources, context = [], ""
    try:
        hits = _brain().recall(message, k=4)
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
    try:
        hits = _brain().recall(message, k=4)
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
