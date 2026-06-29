"""cognition/reasoning.py — deliberate reasoning: ReAct + Tree-of-Thoughts (Phase P4.5).

Reuse-first: a real **LangGraph** ``StateGraph`` that reasons *deliberately* over the brain's
own memory instead of answering in one shot. Two complementary strategies, both offline-safe:

  * **ReAct** (Reason + Act): a think → act(recall) → observe loop. Each step the agent writes
    a short *thought*, issues a recall *action* against ``KnowledgeBrain.recall`` (its only
    tool — it acts on its OWN memory), observes the hits, and decides whether it has enough to
    answer or must keep digging. The full thought/action/observation trace is returned.

  * **Tree-of-Thoughts** (ToT): branch the query into several candidate sub-questions / angles,
    recall for each branch, score branches by retrieved evidence, and keep the best — deliberate
    search instead of a single greedy chain.

The LLM is optional and injected (``propose_fn``/``score_fn``): with a stub or no LLM the graph
uses deterministic heuristics (query decomposition by salient terms, evidence-count scoring), so
it is fully unit-testable with NO network and NO API key — exactly like P4.1–P4.4.
"""
from __future__ import annotations

import re
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "what", "how", "why", "do",
         "does", "in", "on", "for", "with", "about", "tell", "me", "explain", "can", "i"}


def _terms(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", q.lower()) if w not in _STOP]


class ReActState(TypedDict):
    query: str
    steps: list          # [{thought, action, observation, n_hits}]
    recalled: list       # best evidence gathered so far
    answer: str
    done: bool


class ReasoningGraph:
    """ReAct loop + Tree-of-Thoughts search over the brain's memory (LangGraph)."""

    def __init__(self, brain=None, *, recall_k: int = 4, max_steps: int = 3,
                 propose_fn: Callable | None = None, score_fn: Callable | None = None):
        self.brain = brain
        self.recall_k = recall_k
        self.max_steps = max_steps
        self.propose_fn = propose_fn      # (query)->list[str] sub-questions (LLM optional)
        self.score_fn = score_fn          # (query, hits)->float branch score (LLM optional)
        self.app = self._build()

    # ── ReAct graph ───────────────────────────────────────────────────────────────
    def _build(self):
        g = StateGraph(ReActState)
        g.add_node("reason", self._reason_step)
        g.add_edge(START, "reason")
        g.add_conditional_edges("reason", self._route, {"continue": "reason", "stop": END})
        return g.compile()

    def _recall(self, query: str) -> list[dict]:
        if self.brain is None:
            return []
        try:
            return self.brain.recall(query, k=self.recall_k)
        except Exception:
            return []

    def _reason_step(self, state: ReActState) -> dict:
        steps = list(state["steps"])
        # step 0 is the broad recall on the whole query; only FOCUSED digs (steps[1:])
        # count as "explored", so ReAct keeps drilling into fresh concepts each turn.
        seen_terms = {t for s in steps[1:] for t in _terms(s["action"])}
        # pick the next angle: the original query first, then unexplored salient terms
        if not steps:
            action = state["query"]
            thought = "Recall what I know directly about the question."
        else:
            fresh = [t for t in _terms(state["query"]) if t not in seen_terms]
            if fresh:
                action = " ".join(fresh[:3])
                thought = f"Direct recall was thin; dig into related concept(s): {action}."
            else:
                action = state["query"]
                thought = "No new angle to explore; finalise from gathered evidence."
        hits = self._recall(action)
        merged = self._merge(state["recalled"], hits)
        steps.append({"thought": thought, "action": action,
                      "observation": [h.get("title") for h in hits], "n_hits": len(hits)})
        enough = len(merged) >= self.recall_k or len(steps) >= self.max_steps
        return {"steps": steps, "recalled": merged, "done": enough,
                "answer": self._compose(state["query"], merged) if enough else ""}

    def _route(self, state: ReActState) -> str:
        return "stop" if state["done"] else "continue"

    @staticmethod
    def _merge(a: list[dict], b: list[dict]) -> list[dict]:
        out, seen = list(a), {(h.get("title"), h.get("snippet")) for h in a}
        for h in b:
            key = (h.get("title"), h.get("snippet"))
            if key not in seen:
                seen.add(key)
                out.append(h)
        return out

    @staticmethod
    def _compose(query: str, recalled: list[dict]) -> str:
        if not recalled:
            return "(reasoned over memory but found no supporting evidence)"
        lines = [f"- {h.get('title')}: {(h.get('snippet') or '')[:160]}" for h in recalled[:4]]
        return "Reasoned answer grounded in recalled evidence:\n" + "\n".join(lines)

    # ── public: ReAct ──────────────────────────────────────────────────────────────
    def react(self, query: str) -> dict:
        out = self.app.invoke({"query": query, "steps": [], "recalled": [],
                               "answer": "", "done": False})
        return {"answer": out["answer"], "steps": out["steps"],
                "recalled": out["recalled"], "n_steps": len(out["steps"]),
                "strategy": "react"}

    # ── public: Tree-of-Thoughts ────────────────────────────────────────────────────
    def _branches(self, query: str) -> list[str]:
        if self.propose_fn is not None:
            try:
                bs = [str(b).strip() for b in self.propose_fn(query) if str(b).strip()]
                if bs:
                    return bs[:4]
            except Exception:
                pass
        # deterministic decomposition: the query + one focused sub-question per salient term
        ts = _terms(query)
        branches = [query] + [f"{query} ({t})" for t in ts[:3]]
        return branches or [query]

    def _score(self, query: str, hits: list[dict]) -> float:
        if self.score_fn is not None:
            try:
                return float(self.score_fn(query, hits))
            except Exception:
                pass
        # evidence-based heuristic: total retrieval score + a small breadth bonus
        return sum(float(h.get("score", 0.0)) for h in hits) + 0.01 * len(hits)

    def tree_of_thoughts(self, query: str) -> dict:
        """Branch the query into angles, recall per branch, keep the best-supported one."""
        thoughts = []
        for b in self._branches(query):
            hits = self._recall(b)
            thoughts.append({"thought": b, "score": round(self._score(b, hits), 4),
                             "evidence": [h.get("title") for h in hits], "hits": hits})
        thoughts.sort(key=lambda t: -t["score"])
        best = thoughts[0] if thoughts else {"thought": query, "hits": [], "score": 0.0}
        return {"answer": self._compose(query, best["hits"]),
                "best_thought": best["thought"], "branches": [
                    {"thought": t["thought"], "score": t["score"], "evidence": t["evidence"]}
                    for t in thoughts], "recalled": best["hits"], "strategy": "tree-of-thoughts"}

    def reason(self, query: str, *, strategy: str = "react") -> dict:
        return self.tree_of_thoughts(query) if strategy == "tree-of-thoughts" else self.react(query)

    def status(self) -> dict:
        return {"engine": "langgraph", "has_memory": self.brain is not None,
                "max_steps": self.max_steps, "recall_k": self.recall_k,
                "strategies": ["react", "tree-of-thoughts"]}
