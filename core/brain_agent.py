"""core/brain_agent.py — LangGraph brain agent: "talk to the brain" (Phase P4.1).

A real **LangGraph** StateGraph agent that answers questions by FIRST recalling from the
brain's human-like associative memory (KnowledgeBrain.recall) and THEN responding with an
LLM grounded in that recalled context (retrieval-augmented). This upgrades the plain chat
into a stateful agent graph that can grow more tools (web research P4.3, etc.).

Reuse-first: graph = langgraph; memory = memory.brain.KnowledgeBrain; LLM = core.llm
(multi-provider, gated). Offline-safe: with no LLM configured (core.llm.NoLLMConfigured)
it degrades to an honest memory-grounded template answer, so it always works and is
fully unit-testable with injected stubs (no network).
"""
from __future__ import annotations

from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph


class BrainState(TypedDict):
    query: str
    history: list
    recalled: list
    reply: str
    llm_used: bool


_SYSTEM = ("You are the ML Network Brain — a CPU-first network of prediction-model nodes "
           "with a learning brain. Answer concisely and honestly, grounded in the recalled "
           "memory below. If the memory doesn't cover it, say so.")


def _default_llm():
    """Lazy core.llm.chat (multi-provider, gated). Returns a callable or None."""
    try:
        from core import llm
        return llm
    except Exception:  # pragma: no cover
        return None


class BrainAgent:
    """LangGraph agent: recall memory → respond (LLM-grounded, offline-safe)."""

    def __init__(self, brain=None, *, llm_chat: Callable | None = None, recall_k: int = 4,
                 thinker=None):
        self.brain = brain                       # KnowledgeBrain or None (no memory)
        self.recall_k = recall_k
        self._llm = _default_llm()
        # injected chat(messages)->str overrides core.llm (for tests / custom providers)
        self._llm_chat = llm_chat
        # P4.5 deliberate-reasoning layer (cognition.Thinker), lazily attachable; the agent
        # works without it (P4.1 recall→respond) and gains think() when one is wired in.
        self._thinker = thinker
        self.app = self._build()

    # ── graph ───────────────────────────────────────────────────────────────────
    def _build(self):
        g = StateGraph(BrainState)
        g.add_node("recall", self._recall_node)
        g.add_node("respond", self._respond_node)
        g.add_edge(START, "recall")
        g.add_edge("recall", "respond")
        g.add_edge("respond", END)
        return g.compile()

    def _recall_node(self, state: BrainState) -> dict:
        if self.brain is None:
            return {"recalled": []}
        try:
            return {"recalled": self.brain.recall(state["query"], k=self.recall_k)}
        except Exception:
            return {"recalled": []}

    def _context(self, recalled: list) -> str:
        if not recalled:
            return "(no relevant memory found)"
        lines = []
        for r in recalled:
            title = r.get("title") or ""
            snip = (r.get("snippet") or r.get("text") or "")[:200]
            lines.append(f"- {title}: {snip}".strip())
        return "\n".join(lines)

    def _respond_node(self, state: BrainState) -> dict:
        ctx = self._context(state["recalled"])
        messages = [{"role": "system", "content": f"{_SYSTEM}\n\nRecalled memory:\n{ctx}"}]
        messages += list(state.get("history") or [])
        messages.append({"role": "user", "content": state["query"]})

        # 1) injected chat
        if self._llm_chat is not None:
            try:
                return {"reply": str(self._llm_chat(messages)), "llm_used": True}
            except Exception:
                pass
        # 2) core.llm (gated multi-provider)
        if self._llm is not None:
            try:
                return {"reply": str(self._llm.chat(messages)), "llm_used": True}
            except Exception:
                pass  # NoLLMConfigured or transport error → fall through to template
        # 3) offline template grounded in memory (honest, always works)
        if state["recalled"]:
            return {"reply": f"(no LLM configured) From memory:\n{ctx}", "llm_used": False}
        return {"reply": "(no LLM configured and no relevant memory found)", "llm_used": False}

    # ── public ──────────────────────────────────────────────────────────────────
    def ask(self, message: str, *, history: list | None = None) -> dict:
        out = self.app.invoke({"query": message, "history": history or [],
                               "recalled": [], "reply": "", "llm_used": False})
        return {
            "reply": out["reply"], "llm_used": out["llm_used"],
            "used_memory": bool(out["recalled"]),
            "recalled": [{"title": r.get("title"), "via": r.get("via"),
                          "score": round(float(r.get("score", 0.0)), 4)}
                         for r in out["recalled"]],
        }

    # ── P4.5: deliberate "thinking" path ─────────────────────────────────────────
    def attach_thinker(self, thinker) -> "BrainAgent":
        """Wire in a cognition.Thinker so the agent can think() (reason→calibrate→audit)."""
        self._thinker = thinker
        return self

    def think(self, message: str, *, strategy: str = "react") -> dict:
        """Deliberate answer: ReAct/ToT reasoning + conformal abstention + constitution audit
        + active-inference surprise/curiosity. Falls back to ask() if no Thinker is attached."""
        if self._thinker is None:
            out = self.ask(message)
            out["thinking"] = False
            return out
        result = self._thinker.think(message, strategy=strategy)
        result["thinking"] = True
        return result

    def status(self) -> dict:
        model = None
        if self._llm is not None:
            try:
                am = self._llm.active_model()
                model = am[0] if am else None
            except Exception:
                model = None
        st = {"engine": "langgraph", "has_memory": self.brain is not None,
              "llm": model, "recall_k": self.recall_k, "thinking": self._thinker is not None}
        if self._thinker is not None:
            try:
                st["cognition"] = self._thinker.status()
            except Exception:
                pass
        return st
