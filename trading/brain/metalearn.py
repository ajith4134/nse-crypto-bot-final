"""trading/brain/metalearn.py — MAML-style meta-init for sample-efficiency (T8.5).

Trades accrue slowly per symbol, so a brand-new symbol/regime shouldn't start from
scratch. We keep a GLOBAL pooled online model trained across all symbols ("tasks") and
**warm-start** a new per-symbol model by cloning the global learned state — the
meta-learning idea (learn an initialization that adapts from few samples), realised on
CPU with River. `adapt()` quantifies the benefit: few-shot accuracy of a WARM-started
model vs a COLD one on a new task.

Lightweight + deterministic (River is RNG-free). Not full second-order MAML — it's the
practical "good initialization across tasks" variant that fits an online CPU brain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading.brain.continual import OnlineNode, clone_model, _new_model


@dataclass
class MetaLearner:
    features: list
    _global: OnlineNode = field(default=None, init=False)
    _tasks: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._global = OnlineNode(self.features, name="meta_global")

    def observe(self, row, y, *, task: str = "global") -> None:
        """Feed a sample into the global pool (and the task's own model if it exists)."""
        self._global.learn_one(row, y)
        if task in self._tasks:
            self._tasks[task].learn_one(row, y)

    def new_task_model(self, task: str, *, warm: bool = True) -> OnlineNode:
        """Create a per-task model — warm-started from the global state (or cold)."""
        node = OnlineNode(self.features, name=f"task_{task}")
        if warm and self._global.n_seen > 0:
            node.model = clone_model(self._global.model)
            node.n_seen = self._global.n_seen          # inherit "experience"
        self._tasks[task] = node
        return node

    def adapt(self, task_samples: list, *, shots: int = 20) -> dict:
        """Few-shot benefit on a NEW task: warm vs cold accuracy over the first `shots`.

        Prequential: predict-then-learn over the first `shots` samples for each variant.
        """
        warm = OnlineNode(self.features, name="warm")
        if self._global.n_seen > 0:
            warm.model = clone_model(self._global.model)
            warm.n_seen = self._global.n_seen
        cold = OnlineNode(self.features, name="cold")

        def _run(node) -> float:
            c = 0
            k = 0
            for row, y in task_samples[:shots]:
                yb = bool(y)
                if node.n_seen > 0:
                    c += int((node.predict_proba([row])[0] >= 0.5) == yb)
                    k += 1
                node.learn_one(row, yb)
            return c / k if k else 0.0

        warm_acc = _run(warm)
        cold_acc = _run(cold)
        return {"shots": shots, "warm_accuracy": round(warm_acc, 4),
                "cold_accuracy": round(cold_acc, 4),
                "few_shot_gain": round(warm_acc - cold_acc, 4),
                "global_seen": self._global.n_seen}

    def status(self) -> dict:
        return {"features": len(self.features), "global_seen": self._global.n_seen,
                "tasks": list(self._tasks)}
