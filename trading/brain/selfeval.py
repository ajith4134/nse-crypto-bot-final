"""trading/brain/selfeval.py — auto-quiz + Reflexion self-critique (T8.5).

The "proves it gets smarter" layer.

AutoQuiz — **prequential (test-then-train) evaluation**: for each new sample the model
FIRST predicts (held-out — it hasn't seen the label), we score it, THEN it learns. The
accuracy-vs-trade-count curve and its slope are the honest proof that the brain's
predictions improve with experience (rising slope on a learnable stream).

Reflexion — after each closed trade, generate a short natural-language self-critique
keyed to the outcome vs the prediction ("predicted UP, got DOWN into high VIX — avoid")
and store it in the T8.4 semantic memory, so lessons accrue. Rule-based + CPU by default;
uses SemanticMemory (which itself upgrades to an LLM when configured).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from trading.brain.continual import OnlineNode


@dataclass
class QuizResult:
    n: int
    final_accuracy: float
    slope: float                       # accuracy-vs-count trend (per sample)
    rising: bool
    curve: list                        # [(count, rolling_accuracy), ...]

    def as_dict(self) -> dict:
        return {"n": self.n, "final_accuracy": self.final_accuracy, "slope": self.slope,
                "rising": self.rising, "curve": self.curve}


class AutoQuiz:
    """Prequential self-test that proves predictive accuracy rises with experience."""

    def __init__(self, features: list[str], *, sample_every: int = 25, warmup: int = 10):
        self.features = list(features)
        self.sample_every = sample_every
        self.warmup = warmup

    def run(self, samples: list, *, node: OnlineNode | None = None) -> QuizResult:
        """`samples` = ordered list of (row, y). Test-then-train each; track accuracy."""
        node = node or OnlineNode(self.features, name="autoquiz")
        correct = 0
        seen = 0
        curve = []
        for row, y in samples:
            yb = bool(y)
            if seen >= self.warmup:                       # held-out prediction BEFORE learning
                p = node.predict_proba([row])[0]
                correct += int((p >= 0.5) == yb)
                scored = seen - self.warmup + 1
                if scored % self.sample_every == 0:
                    curve.append((seen + 1, round(correct / scored, 4)))
            node.learn_one(row, yb)
            seen += 1
        scored_total = max(1, seen - self.warmup)
        final_acc = correct / scored_total
        if len(curve) >= 2:
            xs = np.array([c[0] for c in curve], dtype=float)
            ys = np.array([c[1] for c in curve], dtype=float)
            slope = float(np.polyfit(xs, ys, 1)[0])
        else:
            slope = 0.0
        return QuizResult(n=seen, final_accuracy=round(final_acc, 4), slope=round(slope, 8),
                          rising=slope > 0, curve=curve)


# ── Reflexion self-critique ──────────────────────────────────────────────────────
_LABELS = {1: "UP", 0: "DOWN", True: "UP", False: "DOWN"}


def reflect(trade, predicted_label, actual_label) -> str:
    """Build a short self-critique note from a trade's prediction vs outcome (CPU)."""
    d = trade.to_dict() if hasattr(trade, "to_dict") else dict(trade)
    pred = _LABELS.get(predicted_label, str(predicted_label))
    act = _LABELS.get(actual_label, str(actual_label))
    sym = d.get("symbol", "?")
    net = d.get("net_pnl")
    ctx = []
    if d.get("india_vix_entry"):
        ctx.append(f"VIX {float(d['india_vix_entry']):.0f}")
    if d.get("market_regime_entry"):
        ctx.append(str(d["market_regime_entry"]))
    if d.get("entry_hour") is not None:
        ctx.append(f"{int(d['entry_hour'])}:00")
    ctxs = (" (" + ", ".join(ctx) + ")") if ctx else ""
    if pred == act:
        return f"{sym}: correct {pred} call{ctxs}; net {net}. Reinforce this setup."
    return (f"{sym}: predicted {pred} but got {act}{ctxs}; net {net}. "
            f"Review entry — this setup misled the model.")


def reflect_and_store(trade, predicted_label, actual_label, semantic_memory) -> dict:
    """Generate the reflection and persist it to the (T8.4) semantic memory."""
    note = reflect(trade, predicted_label, actual_label)
    res = semantic_memory.add_trade_lesson(trade, note) if hasattr(
        semantic_memory, "add_trade_lesson") else semantic_memory.add(note)
    return {"note": note, "stored": res}
