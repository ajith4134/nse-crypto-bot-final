"""memory/hybrid_memory.py — hybrid human memory (Phase P4.2), wired to REAL projects.

Per the locked reuse policy: the heavy logic comes from real, tested projects; our code is
glue. This fuses four real components, powered by the project's LLM cloud keys (core.llm):

  1. Generative-Agents memory stream — VENDORED Stanford code (vendor/generative_agents_memory,
     Apache-2.0): store observations with LLM-rated importance, retrieve by recency+importance+
     relevance, and REFLECT (synthesize higher-level insights). This is the retrieval engine.
  2. Letta (pip, real) — tiered core-memory blocks (ChatMemory persona/human + a knowledge
     block), used embedded/offline (no server). The "tiers" representation.
  3. mem0 (pip, real) — optional external semantic store, gated on an LLM key.
  4. KnowledgeBrain (ours) — PPR+RRF associative graph; HumanMemory (ours) supplies the one
     thing no library does: Ebbinghaus decay + auto_dream FORGETTING/consolidation.
  5. AssociativeMemory (memory/associative.py) — HippoRAG PPR "connect-the-dots" recall +
     A-MEM note linking/evolution (both vendored), the multi-hop associative channel.

LLM keys power GA's importance_fn + synthesize_fn (via core.llm). Offline-safe + deterministic:
LLM injected (stub in tests) → falls back to the vendored heuristic importance/synthesis; mem0
off by default; times injected. No network at import.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from memory.associative import AssociativeMemory
from memory.human_memory import HumanMemory
from vendor.generative_agents_memory import (
    MemoryStream,
    default_importance_fn,
    default_synthesize_fn,
)


def _default_llm():
    try:
        from core import llm
        return llm
    except Exception:  # pragma: no cover
        return None


@dataclass
class HybridMemory:
    brain: object                                   # KnowledgeBrain (ingest_text + recall)
    human: HumanMemory | None = None
    llm_chat: object = None                          # callable(messages)->str (overrides core.llm)
    use_mem0: bool = False
    use_reranker: bool = False
    assoc_path: str | None = None                    # persist associative notes when set
    reflections: list = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.human = self.human or HumanMemory(self.brain, use_reranker=self.use_reranker)
        self._llm = _default_llm()
        # GA memory stream (real vendored code), importance + synthesis powered by our LLM keys
        self.stream = MemoryStream(importance_fn=self._llm_importance,
                                   synthesize_fn=self._llm_synthesize)
        self.letta = self._init_letta()
        self._mem0 = self._init_mem0() if self.use_mem0 else None
        # associative channel (HippoRAG PPR + A-MEM evolution), same injected LLM
        self.assoc = AssociativeMemory(llm_chat=self._chat, path=self.assoc_path)

    # ── real Letta tiered core-memory (embedded, offline) ────────────────────────
    def _init_letta(self):
        try:
            from letta.schemas.memory import ChatMemory
            return ChatMemory(human="Operator: CPU-first, trades NSE + crypto.",
                              persona="ML Network Brain — a learning network of model nodes.")
        except Exception:  # pragma: no cover
            return None

    def _init_mem0(self):
        try:  # pragma: no cover - gated on creds
            import os
            from mem0 import Memory
            if not os.environ.get("OPENAI_API_KEY"):
                return None
            cfg = {"llm": {"provider": "openai", "config": {
                "model": os.environ.get("MEM0_LLM_MODEL", "gpt-4o-mini")}}}
            base = os.environ.get("OPENAI_BASE_URL")
            if base:
                cfg["llm"]["config"]["openai_base_url"] = base
            return Memory.from_config(cfg)
        except Exception:
            return None

    def _chat(self, messages) -> str | None:
        if self.llm_chat is not None:
            try:
                return str(self.llm_chat(messages))
            except Exception:
                return None
        if self._llm is not None:
            try:
                return str(self._llm.chat(messages))
            except Exception:
                return None
        return None

    # ── LLM-powered fns handed to the real GA stream (offline → vendored default) ─
    def _llm_importance(self, text: str) -> int:
        reply = self._chat([
            {"role": "system", "content": "Rate the importance/poignancy of this memory for a "
             "trading/research agent on a 1-10 scale. Reply ONLY the integer."},
            {"role": "user", "content": str(text)[:500]}])
        if reply:
            m = re.search(r"\d+", reply)
            if m:
                return max(1, min(10, int(m.group())))
        return default_importance_fn(text)             # vendored heuristic (offline)

    def _llm_synthesize(self, statements) -> list:
        joined = "\n".join(f"- {s}" for s in statements)
        reply = self._chat([
            {"role": "system", "content": "From these memories synthesize up to 3 higher-level "
             "INSIGHTS, one per line, terse."},
            {"role": "user", "content": joined}])
        if reply:
            out = [ln.strip("-* ").strip() for ln in reply.splitlines() if ln.strip()]
            if out:
                return out[:3]
        return default_synthesize_fn(statements)       # vendored default (offline)

    # ── write ───────────────────────────────────────────────────────────────────
    def add(self, title: str, text: str, *, created=None, now: float = 0.0) -> dict:
        node = self.stream.add_observation(text, created=created)   # GA: rates importance
        importance = float(getattr(node, "poignancy", 5)) / 10.0
        doc_id = self.brain.ingest_text(title, text)
        self.human.remember(title, now=now, importance=importance)
        mem0_ok = False
        if self._mem0 is not None:
            try:  # pragma: no cover
                self._mem0.add(text, user_id="brain", metadata={"title": title})
                mem0_ok = True
            except Exception:
                mem0_ok = False
        assoc = self.assoc.add(text, title=title, now=now)   # HippoRAG graph + A-MEM evolve
        return {"doc_id": doc_id, "title": title, "importance": round(importance, 3),
                "poignancy": getattr(node, "poignancy", None), "mem0": mem0_ok,
                "assoc": {"id": assoc["id"], "links": assoc["links"],
                          "evolved": assoc["evolved"]["should_evolve"]}}

    # ── recall: GA stream (recency+importance+relevance) + decay-aware fuse ───────
    def recall(self, query: str, k: int = 4, *, now: float = 0.0, curr_time=None) -> list[dict]:
        out: list[dict] = []
        try:
            retrieved = self.stream.retrieve([query], n_count=k * 3, curr_time=curr_time)
            for node in (retrieved.get(query, []) if isinstance(retrieved, dict) else retrieved):
                out.append({"title": "(ga)", "snippet": getattr(node, "description", ""),
                            "via": "generative-agents",
                            "importance": getattr(node, "poignancy", None)})
        except Exception:
            pass
        for h in self.human.recall(query, k=k, now=now):     # decay-aware associative channel
            out.append(h)
        out.extend(self.assoc.recall(query, k=k))            # HippoRAG PPR multi-hop channel
        return out[:max(k, len(out))]

    # ── reflection (real GA reflection, LLM-synthesized) ─────────────────────────
    def reflect(self, *, curr_time=None, now: float = 0.0) -> dict:
        try:
            insights_nodes = self.stream.run_reflect(curr_time=curr_time)
        except Exception as exc:
            return {"reflected": False, "reason": f"reflect error: {str(exc)[:60]}"}
        seen, insights = set(), []
        for n in (insights_nodes or []):                    # GA reflects per focal point → dedup
            d = getattr(n, "description", str(n))
            if d not in seen:
                seen.add(d)
                insights.append(d)
        for ins in insights:                                # persist insights as salient memories
            self.add(f"insight: {ins[:40]}", ins, now=now)
            self.human.remember(f"insight: {ins[:40]}", now=now, importance=0.85)
        self.reflections.append({"now": now, "insights": insights})
        return {"reflected": bool(insights), "insights": insights}

    def dream(self, now: float) -> dict:
        return self.human.dream(now)                          # Ebbinghaus forget/consolidate

    def status(self, now: float = 0.0) -> dict:
        return {"human": self.human.status(now),
                "ga_stream": {"n": len(getattr(self.stream, "seq_event", [])) +
                              len(getattr(self.stream, "seq_thought", [])),
                              "source": "vendored Stanford generative_agents (Apache-2.0)"},
                "letta": self.letta is not None, "mem0": self._mem0 is not None,
                "llm": self._llm.active_model()[0] if (self._llm and self._llm.active_model())
                else None, "reflections": len(self.reflections),
                "associative": self.assoc.status(),
                "components": ["generative-agents(vendored real)", "letta(real,tiered)",
                               "mem0(real,gated)", "human_memory(ebbinghaus decay/dream)",
                               "associative(hipporag-ppr + a-mem evolution)"]}
