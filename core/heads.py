"""Output heads — the multi-output contract for the prediction-graph network.

The plan calls for a network with an OUTPUT LAYER of several heads (not one
binary label): the same input can be mapped to many targets, each node can carry
its own golden target, and tasks may be classification OR regression. An
`OutputHead` is the single abstraction that expresses all of these:

  * multi-head targets  -> several heads of different tasks (direction, vol, magnitude)
  * multi-horizon       -> several binary heads at different shifts (dir_1h/4h/1d)
  * multiclass          -> one head with task="multiclass", n_classes=K
  * per-node own target -> a node bound to one head (node.head == head.name)

A node declares the head it serves (`node.head`) and its task (`node.task`);
the eval plane scores each head with the metric appropriate to its task, against
an honest per-task baseline (majority for classification, mean for regression).
"""
from __future__ import annotations

from dataclasses import dataclass

# task kinds -----------------------------------------------------------------
TASK_BINARY = "binary"
TASK_MULTICLASS = "multiclass"
TASK_REGRESSION = "regression"
TASKS = (TASK_BINARY, TASK_MULTICLASS, TASK_REGRESSION)


@dataclass(frozen=True)
class OutputHead:
    """One output of the network's output layer.

    name      : stable identifier (e.g. "direction", "magnitude", "regime").
    task      : one of TASKS.
    n_classes : number of classes for classification (2 for binary); 1 for regression.
    desc      : human-readable description for the dashboard.
    """
    name: str
    task: str = TASK_BINARY
    n_classes: int = 2
    desc: str = ""

    def __post_init__(self):
        if self.task not in TASKS:
            raise ValueError(f"unknown task {self.task!r}; expected one of {TASKS}")

    @property
    def n_outputs(self) -> int:
        """Width of one prediction row: 1 for regression, n_classes otherwise."""
        return 1 if self.task == TASK_REGRESSION else self.n_classes

    @property
    def is_classification(self) -> bool:
        return self.task in (TASK_BINARY, TASK_MULTICLASS)

    def to_json(self) -> dict:
        return {"name": self.name, "task": self.task,
                "n_classes": self.n_classes, "desc": self.desc}


# A few canonical heads the runners use (data layer already builds these targets;
# see data/features.py: y_dir / y_ret / y_vol_high).
HEAD_DIRECTION = OutputHead("direction", TASK_BINARY, 2, "next-step direction (up/down)")
HEAD_VOLATILITY = OutputHead("volatility", TASK_BINARY, 2, "big move next step? (high/low)")
HEAD_MAGNITUDE = OutputHead("magnitude", TASK_REGRESSION, 1, "next-step return (regression)")
HEAD_REGIME = OutputHead("regime", TASK_MULTICLASS, 3, "regime class (down/flat/up)")
