"""trading/brain/entryexit.py — regime/pattern-gated entry + learned exit (T8.6).

Combines the T8.6 context (regime + anomaly) with a strategy's signal to decide ENTRY,
and decides EXIT from regime change / anomaly spike / signal reversal / an optional
learned exit model (a T8.5 River OnlineNode predicting "exit now"). This is the lean,
CPU, deterministic entry/exit layer; a full RL exit policy (**FinRL** / trading-rl) is
the heavier upgrade for when RL training infra is in place — same `should_exit` interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading.brain.continual import OnlineNode


@dataclass
class EntryExitPolicy:
    """Regime/anomaly-gated entry + multi-trigger (incl. learned) exit."""
    allowed_regimes: tuple = ("bull", "bear", "neutral")
    max_anomaly: float = 3.0
    exit_model: OnlineNode | None = None       # optional learned exit (T8.5 OnlineNode)
    exit_threshold: float = 0.5

    # ── entry ───────────────────────────────────────────────────────────────────
    def should_enter(self, *, signal: int, regime: str, anomaly_score: float = 0.0) -> dict:
        if signal == 0:
            return {"enter": False, "reason": "no signal"}
        if regime not in self.allowed_regimes:
            return {"enter": False, "reason": f"regime {regime} not allowed"}
        if anomaly_score > self.max_anomaly:
            return {"enter": False, "reason": f"anomaly spike {anomaly_score:.2f}"}
        return {"enter": True, "side": "LONG" if signal > 0 else "SHORT",
                "reason": f"signal {signal} in {regime}"}

    # ── exit ────────────────────────────────────────────────────────────────────
    def should_exit(self, *, position_side: str, signal: int, regime: str,
                    anomaly_score: float = 0.0, exit_features=None) -> dict:
        side = position_side.upper()
        if regime not in self.allowed_regimes:
            return {"exit": True, "reason": f"regime left allowed set ({regime})"}
        if anomaly_score > self.max_anomaly:
            return {"exit": True, "reason": f"anomaly spike {anomaly_score:.2f}"}
        if (side == "LONG" and signal < 0) or (side == "SHORT" and signal > 0):
            return {"exit": True, "reason": "signal reversed"}
        if self.exit_model is not None and exit_features is not None:
            p = self.exit_model.predict_proba([exit_features])[0]
            if p >= self.exit_threshold:
                return {"exit": True, "reason": f"learned exit p={p:.2f}", "exit_proba": p}
        return {"exit": False, "reason": "hold"}

    def train_exit(self, rows: list, labels: list) -> "EntryExitPolicy":
        """Train the optional learned-exit OnlineNode on (context → should-exit) samples."""
        if self.exit_model is None:
            raise ValueError("no exit_model attached")
        self.exit_model.fit(rows, labels)
        return self

    def status(self) -> dict:
        return {"allowed_regimes": list(self.allowed_regimes), "max_anomaly": self.max_anomaly,
                "learned_exit": self.exit_model is not None}
