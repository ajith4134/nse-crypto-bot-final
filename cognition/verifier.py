"""cognition/verifier.py — verifier-guided reasoning (Pillar 18, ThinkPRM-style).

One bad step in a reasoning chain silently poisons the conclusion. A *process-reward
model* (PRM) scores each reasoning STEP 0/1 with a short critique, so a plan can be
rejected for a flawed step even when its final answer looks plausible. We drive this
through the project's already-gated ``core.llm`` failover (no GPU, no new dep); with no
LLM key it degrades to a deterministic, evidence-based heuristic so it is always testable.

Two public entry points:
  • StepVerifier.score(steps) → per-step {score, critique} + an aggregate 0..1 process reward.
  • best_of_n(candidates, verify) → re-rank N candidate plans by verified process reward and
    return the winner (self-consistency / best-of-N over a verifier, not majority vote alone).

Reuse-first: prompt-based PRM over core.llm; numpy-free. The PRM + best-of-N wiring is the glue.
"""
from __future__ import annotations

import re


_VERIFY_SYS = (
    "You are a strict step verifier for trading reasoning. For the single reasoning STEP "
    "below, decide if it is logically valid, factually consistent with the context, and free "
    "of unsupported leaps. Reply EXACTLY one line: 'SCORE: 1 — <=12 word reason' if the step "
    "is sound, or 'SCORE: 0 — <=12 word reason' if it is flawed.")

# cheap lexical cues for the offline heuristic verifier
_WEAK = ("obviously", "definitely", "guaranteed", "always", "never", "must", "clearly",
         "everyone knows", "can't lose", "100%", "sure thing", "moon")
_HEDGE = ("because", "since", "given", "data", "evidence", "backtest", "sharpe", "p_up",
          "regime", "atr", "volatility", "confirmed")


def _default_chat():
    try:
        from core import llm
        return llm.chat
    except Exception:
        return None


def _heuristic_step_score(step: str) -> tuple[int, str]:
    """Deterministic 0/1 for one step: reward evidence-grounding, punish unsupported certainty."""
    s = step.lower()
    weak = sum(w in s for w in _WEAK)
    hedge = sum(h in s for h in _HEDGE)
    if weak > hedge:
        return 0, f"unsupported certainty ({weak} strong claims, {hedge} grounded)"
    if hedge == 0 and len(s.split()) > 4:
        return 0, "no evidence cited"
    return 1, f"grounded ({hedge} evidence cues)"


def _parse_score(text: str) -> tuple[int, str]:
    m = re.search(r"SCORE:\s*([01])\s*[—:-]*\s*(.*)", str(text), re.I)
    if m:
        return int(m.group(1)), m.group(2).strip()[:80]
    # fall back to yes/no lexical read
    t = str(text).lower()
    return (1 if ("valid" in t or "sound" in t or "yes" in t) else 0), str(text).strip()[:80]


class StepVerifier:
    """Process-reward model: scores each reasoning step 0/1 with a critique (core.llm; offline-safe)."""

    def __init__(self, *, chat=None):
        self._chat = chat if chat is not None else _default_chat()

    def score(self, steps, *, context: str = "") -> dict:
        steps = [s for s in (steps or []) if str(s).strip()]
        results = []
        for i, step in enumerate(steps):
            if self._chat is not None:
                try:
                    reply = self._chat(
                        [{"role": "system", "content": _VERIFY_SYS},
                         {"role": "user", "content": f"Context: {context}\n\nSTEP {i+1}: {step}"}],
                        max_tokens=60, temperature=0.0)
                    sc, crit = _parse_score(reply)
                    mode = "llm"
                except Exception:
                    sc, crit = _heuristic_step_score(step)
                    mode = "heuristic"
            else:
                sc, crit = _heuristic_step_score(step)
                mode = "heuristic"
            results.append({"step": str(step)[:200], "score": sc, "critique": crit})
        n = len(results)
        reward = float(sum(r["score"] for r in results) / n) if n else 0.0
        weakest = min(results, key=lambda r: r["score"]) if results else None
        return {"steps": results, "process_reward": round(reward, 4), "n_steps": n,
                "all_valid": all(r["score"] == 1 for r in results) if results else False,
                "weakest_step": weakest, "mode": mode}


def best_of_n(candidates, verify, *, key="process_reward") -> dict:
    """Re-rank candidate plans by a verifier's process reward; return the winner + ranking.

    `candidates` is a list of {"plan": str, "steps": [...]} dicts; `verify` is a StepVerifier.
    """
    scored = []
    for i, c in enumerate(candidates):
        rep = verify.score(c.get("steps", []), context=c.get("context", ""))
        scored.append({"idx": i, "plan": c.get("plan", ""), "verdict": rep,
                       "score": rep[key]})
    scored.sort(key=lambda r: r["score"], reverse=True)
    return {"winner": scored[0] if scored else None, "ranking": scored,
            "n_candidates": len(scored)}
