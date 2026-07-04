"""trading/brain/debate_gate.py — adversarial debate + verifier gate for trades (Pillar 18).

Before capital commits to a high-conviction trade, the decision is (a) DEBATED by adversarial
roles (bull / bear / risk — cognition.society) and (b) VERIFIED step-by-step by a process-reward
model (cognition.verifier). The gate returns an auditable decision_snapshot and a size multiplier
driven by the bull/bear flip-rate + verified process reward — never a bare LLM yes/no.

This is the "verified reasoning, not just PnL" gate. It is offline-safe (society + verifier both
degrade to deterministic heuristics with no LLM key) so it always returns a verdict and is testable.

Reuse-first: composes the already-built InternalDebate + StepVerifier; the trade-facing framing,
the confidence math, and the snapshot are the glue. No new deps.
"""
from __future__ import annotations

from cognition.society import InternalDebate
from cognition.verifier import StepVerifier


def _proposition(symbol: str, direction: str, features: dict | None) -> str:
    feats = features or {}
    cue = ", ".join(f"{k}={v}" for k, v in list(feats.items())[:8])
    return (f"Enter a {direction.upper()} position in {symbol} now. "
            f"Signal context: {cue or 'n/a'}.")


def _rationale_steps(symbol: str, direction: str, features: dict | None) -> list[str]:
    """Turn the candidate trade's evidence into discrete reasoning steps the PRM can verify."""
    f = features or {}
    steps = []
    if "p_up" in f:
        steps.append(f"Calibrated p_up={f['p_up']} supports a {direction} bias given the threshold.")
    if "sharpe" in f:
        steps.append(f"The chosen strategy's OOS Sharpe={f['sharpe']} was positive after deflation.")
    if "regime" in f:
        steps.append(f"Current regime is {f['regime']}, where this setup has historical edge.")
    if "psychology" in f:
        steps.append(f"Order-book psychology reads {f['psychology']}, not opposing the entry.")
    if "atr" in f or "volatility" in f:
        steps.append("Volatility is within the band where the trail/stop rules are validated.")
    if not steps:
        steps.append(f"Signal fired for {direction} on {symbol}; evidence context is thin.")
    return steps


class DebateGate:
    """Debate + verifier gate over a candidate trade decision."""

    def __init__(self, *, chat=None, pass_reward: float = 0.5):
        self.debate = InternalDebate(chat=chat)
        self.verifier = StepVerifier(chat=chat)
        self.pass_reward = float(pass_reward)

    def assess(self, symbol: str, direction: str, *, features: dict | None = None) -> dict:
        prop = _proposition(symbol, direction, features)
        ctx = ", ".join(f"{k}={v}" for k, v in (features or {}).items())
        deb = self.debate.debate(prop, context=ctx)
        steps = _rationale_steps(symbol, direction, features)
        ver = self.verifier.score(steps, context=ctx)

        # flip-rate: how split the debate was (0 = unanimous, 1 = maximally split)
        n_roles = max(1, len(deb.get("votes", {})))
        flip = 1.0 - abs(deb.get("tally", 0)) / n_roles
        reward = ver["process_reward"]
        # gate: debate must lean YES AND the reasoning must clear the process-reward floor
        approved = deb.get("verdict") == "yes" and reward >= self.pass_reward
        # size multiplier: high when consensus (low flip) and high verified reward
        size_mult = round(max(0.0, min(1.0, (1.0 - flip) * reward)), 3) if approved else 0.0

        snapshot = {
            "proposition": prop,
            "debate_verdict": deb.get("verdict"),
            "debate_tally": deb.get("tally"),
            "votes": deb.get("votes"),
            "arguments": deb.get("arguments"),
            "flip_rate": round(flip, 3),
            "process_reward": reward,
            "all_steps_valid": ver["all_valid"],
            "weakest_step": ver.get("weakest_step"),
            "verifier_steps": ver["steps"],
            "mode": {"debate": deb.get("mode"), "verifier": ver.get("mode")},
        }
        return {"approved": bool(approved), "size_mult": size_mult, "confidence": size_mult,
                "reason": ("approved: debate=yes, verified reasoning"
                           if approved else
                           f"blocked: verdict={deb.get('verdict')}, reward={reward:.2f}"),
                "decision_snapshot": snapshot}


_GATE: DebateGate | None = None


def get_debate_gate() -> DebateGate:
    global _GATE
    if _GATE is None:
        _GATE = DebateGate()
    return _GATE
