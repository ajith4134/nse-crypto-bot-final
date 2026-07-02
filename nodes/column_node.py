"""ColumnNode — OPTION A: the intra-column differentiable gate.

A COLUMN (see core.columns) is a family of same-type nodes that do the SAME job in
DIFFERENT ways (e.g. the "trees" column: stump / random-forest / GBDT). A ColumnNode
ensembles ITS members with a learned, input-conditioned gate so the network trusts the
locally-best member per input — and exposes the learned weights for the dashboard.

Reuse-first: this is a THIN wrapper over the already-tested differentiable gate
(nodes.gated_node.GatedMoENode, P3.5) — frozen experts, backprop on the wiring only,
Switch-style load-balance, optional top-k sparse routing (CPU-first: fire k members/input).
ColumnNode adds only column IDENTITY (key/title/color/members) and dashboard metadata, so
A composes the existing primitive rather than reinventing a gate.

Open-to-future-nodes: a ColumnNode is built from whatever members land in its column
(core.columns.group_factories); adding a new node just grows a column's member list — no
signature change. Members whose output width doesn't fit the head are dropped by the gate.
"""
from __future__ import annotations

import numpy as np

from core.columns import get_column
from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.gated_node import GatedMoENode


class ColumnNode(BaseNode):
    kind = "column"

    def __init__(self, column_key: str, member_factories: list[NodeFactory],
                 top_k: int = 0, epochs: int = 200, lr: float = 0.05,
                 balance_coef: float = 0.01, noisy: bool = True, folds: int = 5,
                 seed: int = 7, task: str = "binary", head: str = "y",
                 name: str | None = None):
        col = get_column(column_key)
        self.column_key = column_key
        self.title = col.title
        self.color = col.color
        self.name = name or f"col_{column_key}@{head}"
        self.summary = f"Column '{col.title}': {col.desc}"
        self.task = task
        self.head = head
        self.top_k = top_k
        # the intra-column gate (frozen members = experts; only the gate learns)
        self._gate = GatedMoENode(
            member_factories, epochs=epochs, lr=lr, top_k=top_k, noisy=noisy,
            balance_coef=balance_coef, folds=folds, seed=seed, task=task, head=head,
            name=f"{self.name}__gate")
        self.schema = IOSchema(0, "features", f"{task} output [column:{column_key}]")

    # ── training / inference (delegate to the tested gate) ──
    def fit(self, X: Matrix, y: Labels) -> "ColumnNode":
        self._gate.fit(X, y)
        self.member_names = list(self._gate.expert_names)   # members that survived width-filter
        self._K = self._gate._K
        d = len(X[0])
        self.schema = IOSchema(d, f"{d} numeric features",
                               f"{self.task} output [column:{self.column_key}]")
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return self._gate.predict_output(X)

    def predict_proba(self, X: Matrix) -> Vector:
        return self._gate.predict_proba(X)

    def predict(self, X: Matrix) -> Labels:
        return self._gate.predict(X)

    # ── dashboard / introspection (honest wiring: real learned values) ──
    def gate_weights(self, X: Matrix) -> dict:
        """Mean learned weight per member — the trained intra-column wiring."""
        return self._gate.gate_weights(X)

    def active_subnetwork(self, X: Matrix):
        """Per-input (weights, active-mask) — which members fire on each input (top-k)."""
        return self._gate.active_subnetwork(X)

    @property
    def members(self) -> list[str]:
        return getattr(self, "member_names", [])
