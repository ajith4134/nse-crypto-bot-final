"""cognition/society.py — society of mind: internal debate → vote (Phase P4.8).

The brain holds an INTERNAL DEBATE — specialist roles argue a question from different angles,
then a judge tallies a verdict. The blueprint names CrewAI/MetaGPT for this, but both hard-pin
``pydantic<2.13`` + ``chromadb~=1.1`` and would force-downgrade and BREAK the working
nemoguardrails/litellm/letta stack (verified). Per the dep-weight rule (capability first; a dep
that breaks the stack isn't viable) and the "ship the equivalent capability" rule, this is the
faithful equivalent: the same "specialist roles debate, then vote" pattern driven by the
project's already-gated multi-provider ``core.llm`` — zero new deps, no conflict.

Offline-safe: with no LLM key the debate degrades to a deterministic, evidence-based vote (each
role scores the question from cheap heuristics), so it always returns a verdict and is fully
testable with NO network. An injected ``chat`` callable overrides ``core.llm`` for tests.
"""
from __future__ import annotations

import re

# specialist roles: each gets a system stance; the judge aggregates their votes.
ROLES = {
    "bull": "You are the BULL. Argue FOR the proposition with the strongest honest case. "
            "End with a line 'VOTE: yes' or 'VOTE: no'.",
    "bear": "You are the BEAR/skeptic. Argue AGAINST the proposition, surfacing the biggest "
            "risks. End with a line 'VOTE: yes' or 'VOTE: no'.",
    "risk": "You are the RISK officer. Weigh downside vs upside soberly. "
            "End with a line 'VOTE: yes' or 'VOTE: no'.",
}

_POS = ("up", "gain", "profit", "beat", "strong", "win", "bull", "support", "confirm", "good",
        "growth", "yes", "buy", "opportunity")
_NEG = ("down", "loss", "risk", "weak", "crash", "bear", "reject", "drawdown", "bad", "fear",
        "no", "sell", "danger", "overbought")


def _default_chat():
    try:
        from core import llm
        return llm.chat
    except Exception:
        return None


def _vote_from_text(text: str) -> int:
    m = re.search(r"VOTE:\s*(yes|no)", text or "", re.I)
    if m:
        return 1 if m.group(1).lower() == "yes" else -1
    t = (text or "").lower()
    return 1 if sum(w in t for w in _POS) >= sum(w in t for w in _NEG) else -1


def _heuristic_vote(role: str, question: str, ctx: str) -> tuple[str, int]:
    """Deterministic per-role vote when no LLM is available (evidence-based, reproducible)."""
    t = f"{question} {ctx}".lower()
    pos = sum(w in t for w in _POS)
    neg = sum(w in t for w in _NEG)
    bias = {"bull": 1, "bear": -1, "risk": 0}[role]      # each role's prior lean
    score = pos - neg + bias
    vote = 1 if score > 0 else -1 if score < 0 else (1 if role == "bull" else -1)
    arg = (f"[{role}] evidence: +{pos}/-{neg} (lean {bias:+d}) → "
           f"VOTE: {'yes' if vote > 0 else 'no'}")
    return arg, vote


class InternalDebate:
    """Specialist roles debate a question, a judge tallies the verdict (core.llm; offline-safe)."""

    def __init__(self, *, chat=None, roles: dict | None = None):
        self.roles = roles or ROLES
        self._chat = chat if chat is not None else _default_chat()

    def debate(self, question: str, *, context: str = "") -> dict:
        arguments, votes = {}, {}
        mode = "stub"
        for role, stance in self.roles.items():
            reply = None
            if self._chat is not None:
                try:
                    reply = self._chat([{"role": "system", "content": stance},
                                        {"role": "user",
                                         "content": f"Proposition: {question}\n\n{context}".strip()}])
                except Exception:
                    reply = None
            if reply:
                mode = "llm"
                arguments[role] = str(reply)
                votes[role] = _vote_from_text(str(reply))
            else:
                arg, v = _heuristic_vote(role, question, context)
                arguments[role] = arg
                votes[role] = v
        tally = sum(votes.values())
        verdict = "yes" if tally > 0 else "no" if tally < 0 else "tie"
        return {
            "question": question,
            "verdict": verdict,
            "tally": tally,
            "votes": votes,
            "consensus": abs(tally) == len(self.roles),
            "arguments": {r: a[:280] for r, a in arguments.items()},
            "mode": mode,
        }

    def status(self) -> dict:
        return {"roles": list(self.roles), "engine": "core.llm" if self._chat else "stub",
                "has_llm": self._chat is not None}
