"""Node interface contracts for the prediction-graph network.

Defines the typed I/O schema, the NodeProtocol every node must satisfy, and a
BaseNode with shared behaviour (label = threshold on probability). A node that
does not implement fit/predict_proba cannot be used as a node, so the graph
stays wired correctly.

Inputs:  feature rows  -> Matrix (list[list[float]])
Outputs: class-1 probabilities -> Vector (list[float]); labels -> Labels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

Matrix = list[list[float]]
Vector = list[float]
Labels = list[int]


@dataclass(frozen=True)
class IOSchema:
    """Declares what a node consumes and produces."""
    input_dim: int
    input_desc: str
    output_desc: str


@runtime_checkable
class NodeProtocol(Protocol):
    """Structural contract. isinstance(x, NodeProtocol) is True only if x has
    name, kind, schema and the three methods — enforced at registration."""
    name: str
    kind: str
    schema: IOSchema

    def fit(self, X: Matrix, y: Labels) -> "NodeProtocol": ...
    def predict_proba(self, X: Matrix) -> Vector: ...
    def predict(self, X: Matrix) -> Labels: ...


@dataclass
class NodeInfo:
    """Serializable description of a node for INDEX.md and the dashboard."""
    name: str
    kind: str
    summary: str
    schema: IOSchema
    trained: bool = False
    metrics: dict = field(default_factory=dict)
    upstream: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "summary": self.summary,
            "input_dim": self.schema.input_dim, "input_desc": self.schema.input_desc,
            "output_desc": self.schema.output_desc, "trained": self.trained,
            "metrics": self.metrics, "upstream": self.upstream,
        }


class BaseNode:
    """Shared base: subclasses implement fit() and predict_proba()."""
    name: str = "base"
    kind: str = "base"
    summary: str = ""
    schema: IOSchema = IOSchema(0, "features", "p(class=1)")

    def fit(self, X: Matrix, y: Labels) -> "BaseNode":
        raise NotImplementedError

    def predict_proba(self, X: Matrix) -> Vector:
        raise NotImplementedError

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


NodeFactory = Callable[[], BaseNode]
