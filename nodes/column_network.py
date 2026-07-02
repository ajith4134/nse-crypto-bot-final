"""ColumnNetwork — OPTIONS B, C, D + dynamic brain-driven I/O.

Builds on core.columns (grouping) and nodes.column_node.ColumnNode (option A) to
assemble the full connected network the user asked for:

  A  intra-column gate      : ColumnNode (each column ensembles its own members)   [column_node.py]
  B  cross-column router     : a second differentiable gate over the COLUMN outputs — learns
                               which columns matter per input (sparse top-k → CPU-first).
  C  growing / pruning DGMG  : grow depth as a cascade OVER columns (reuse DeepCascadeNode's
                               plateau rule) and PRUNE near-zero-weight columns (lottery-ticket).
  D  brain-as-gate           : the brain's context (regime / imagination / hypothesis signals)
                               is appended to the CROSS-GATE INPUT ONLY (not the experts), so the
                               brain drives routing without polluting the frozen members.

Dynamic brain-driven I/O (the user's follow-up idea — evaluated as worth building):
  * OUTPUTS  — ColumnNetwork holds one cross-column router PER HEAD. The brain passes a
    HeadRequest (subset of trained head keys); the network computes ONLY those heads. Fewer
    heads requested ⇒ less compute (lazy). Selecting UNTRAINED head types is out of scope.
  * INPUTS   — variable input sets ride the already-tested presence mask of nodes.dynamic_bus;
    the cross-gate is count-agnostic over columns (a dropped column just isn't computed).

Reuse-first: the gate math is the shared nodes.gated_node primitives (gate_train / gate_weights /
gate_combine, Switch load-balance); depth growth is nodes.cascade_node.DeepCascadeNode; OOF
leakage discipline is nodes.stacking_node. This module is ORGANISING glue, not new algorithms.
"""
from __future__ import annotations

import numpy as np

from core.columns import group_factories, layout_for
from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.cascade_node import DeepCascadeNode
from nodes.column_node import ColumnNode
from nodes.gated_node import (gate_combine, gate_train, gate_weights, kfold_indices,
                              standardize_fit)


class ColumnNetworkNode(BaseNode):
    """Single-head connected column network: columns (A) + cross-column router (B),
    with optional growth/prune (C) and brain-context gate input (D)."""
    kind = "column_network"

    def __init__(self, factories: list[NodeFactory], names: list[str],
                 kinds: list[str] | None = None, task: str = "binary", head: str = "y",
                 cross_top_k: int = 0, intra_top_k: int = 0, epochs: int = 200,
                 lr: float = 0.05, balance_coef: float = 0.01, noisy: bool = True,
                 folds: int = 3, intra_folds: int = 3, grow: bool = False,
                 max_layers: int = 3, prune_eps: float = 0.01, brain_ctx_dim: int = 0,
                 seed: int = 7, name: str | None = None):
        self.task = task
        self.head = head
        self.name = name or f"colnet@{head}"
        self.summary = f"Connected column network over {head} (cross-column gate; grow={grow})."
        self.cross_top_k = cross_top_k
        self.intra_top_k = intra_top_k
        self.epochs = epochs
        self.lr = lr
        self.balance_coef = balance_coef
        self.noisy = noisy
        self.folds = folds
        self.intra_folds = intra_folds
        self.grow = grow
        self.max_layers = max_layers
        self.prune_eps = prune_eps
        self.brain_ctx_dim = brain_ctx_dim          # D: width of appended brain context
        self.seed = seed
        # group the pool into columns (open-to-future: unknown nodes → 'other')
        self._grouped = group_factories(factories, names, kinds)
        self.column_keys = list(self._grouped)
        self.schema = IOSchema(0, "features", f"{task} output [colnet]")

    # ── column factory: each column is a ColumnNode (option A) ──
    def _column_factory(self, key: str, members: list[NodeFactory], folds: int) -> NodeFactory:
        return lambda: ColumnNode(
            key, members, top_k=self.intra_top_k, epochs=self.epochs, lr=self.lr,
            balance_coef=self.balance_coef, noisy=self.noisy, folds=folds,
            seed=self.seed, task=self.task, head=self.head)

    def _column_factories(self, folds: int) -> list[NodeFactory]:
        return [self._column_factory(k, [f for f, _ in pairs], folds)
                for k, pairs in self._grouped.items()]

    def _col_outputs(self, columns, X_list) -> np.ndarray:
        """(n, C, K) — one predict_output block per column."""
        return np.stack([np.asarray(c.predict_output(X_list), dtype=float) for c in columns],
                        axis=1)

    def _gate_input(self, X: np.ndarray, brain_ctx: np.ndarray | None) -> np.ndarray:
        """Cross-gate input = raw features (+ brain context, option D)."""
        if self.brain_ctx_dim and brain_ctx is not None:
            return np.concatenate([X, np.asarray(brain_ctx, dtype=float)], axis=1)
        return X

    def fit(self, X: Matrix, y: Labels, brain_ctx: Matrix | None = None) -> "ColumnNetworkNode":
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n, d = Xa.shape
        self._K = (int(ya.max()) + 1) if self._cls else 1

        # ── GROW (option C): delegate depth growth to the tested cascade OVER columns ──
        if self.grow:
            self._combiner = DeepCascadeNode(
                self._column_factories(self.intra_folds), max_layers=self.max_layers,
                folds=self.folds, top_k=self.cross_top_k, gate_epochs=self.epochs, lr=self.lr,
                balance_coef=self.balance_coef, noisy=self.noisy, seed=self.seed,
                task=self.task, head=self.head, name=f"{self.name}__cascade").fit(X, y)
            self.columns = self._combiner.layers[-1]            # last-layer columns (for dashboard)
            self.column_names = [c.name for c in self.columns]
            self.depth = self._combiner.depth
            self.schema = IOSchema(d, f"{d} numeric features",
                                   f"{self.task} output [colnet grow L{self.depth}]")
            return self

        # ── B/D: keep only columns with ≥1 member that fits this head (width K) ──
        m = max(2, int(n * 0.8))
        viable = {}
        for key, pairs in self._grouped.items():
            try:
                col = self._column_factory(key, [f for f, _ in pairs], self.intra_folds)()
                col.fit(Xa[:m].tolist(), ya[:m].tolist())
                if len(col.predict_output(Xa[m:m + 3].tolist())[0]) == self._K:
                    viable[key] = pairs
            except Exception:
                pass                                    # column has no member for this head → drop
        if not viable:
            raise ValueError(f"no column fits head '{self.head}' (width {self._K})")
        self._grouped = viable
        self.column_keys = list(viable)

        # ── single cross-column gate over columns, leakage-safe OOF meta ──
        cbrain = np.asarray(brain_ctx, dtype=float) if brain_ctx is not None else None
        C = len(self.column_keys)
        meta = np.zeros((n, C, self._K), dtype=float)
        for val_idx in kfold_indices(n, self.folds):
            tr = [i for i in range(n) if i not in set(val_idx)]
            cols = [f().fit(Xa[tr].tolist(), ya[tr].tolist())
                    for f in self._column_factories(self.intra_folds)]
            meta[val_idx] = self._col_outputs(cols, Xa[val_idx].tolist())

        gin = self._gate_input(Xa, cbrain)
        self._mean, self._std = standardize_fit(gin)
        Xz = (gin - self._mean) / self._std
        self._gate, self._noise = gate_train(
            Xz, meta, ya, self._cls, self.epochs, self.lr, self.balance_coef,
            self.noisy, self.cross_top_k, self.seed)

        # refit columns on ALL data for inference
        self.columns = [f().fit(X, y) for f in self._column_factories(self.intra_folds)]
        self.column_names = list(self.column_keys)
        self.depth = 1
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [colnet]")
        return self

    # ── inference ──
    def _cross_weights(self, X: Matrix, brain_ctx: Matrix | None) -> np.ndarray:
        cbrain = np.asarray(brain_ctx, dtype=float) if brain_ctx is not None else None
        gin = self._gate_input(np.asarray(X, dtype=float), cbrain)
        Xz = (gin - self._mean) / self._std
        return gate_weights(self._gate, self._noise, Xz, self.cross_top_k, len(self.columns))

    def predict_output(self, X: Matrix, brain_ctx: Matrix | None = None) -> list[list[float]]:
        if self.grow:
            return self._combiner.predict_output(X)
        w = self._cross_weights(X, brain_ctx)
        meta = self._col_outputs(self.columns, X)
        return gate_combine(w, meta, self._cls).tolist()

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [int(np.argmax(r)) for r in rows]

    # ── dashboard / introspection (honest wiring) ──
    def column_weights(self, X: Matrix, brain_ctx: Matrix | None = None) -> dict:
        """Mean learned CROSS-column weight per column — the trained inter-column wiring."""
        if self.grow:
            gw = self._combiner.gate_weights(X)
            return {n: gw.get(n, 0.0) for n in self.column_names}
        w = self._cross_weights(X, brain_ctx).mean(axis=0)
        return {k: round(float(v), 4) for k, v in zip(self.column_keys, w)}

    def pruned_columns(self, X: Matrix, brain_ctx: Matrix | None = None) -> list[str]:
        """Columns whose learned weight ≈ 0 — lottery-ticket prune candidates (option C)."""
        return [k for k, v in self.column_weights(X, brain_ctx).items() if v < self.prune_eps]

    def column_intra_weights(self, X: Matrix) -> dict:
        """Per-column, the intra-column member weights (option A wiring) — nested for the dashboard."""
        out = {}
        for c in self.columns:
            try:
                out[getattr(c, "column_key", c.name)] = c.gate_weights(X)
            except Exception:
                pass
        return out

    def layout(self) -> list[dict]:
        """Ordered column layout (key/title/desc/color/members) for the dashboard."""
        return layout_for(self._grouped)


# --------------------------------------------------------------------------- #
#  Multi-head container — the brain-driven DYNAMIC OUTPUT layer
# --------------------------------------------------------------------------- #
class ColumnNetwork:
    """Holds one ColumnNetworkNode per head; serves the brain's dynamic HeadRequest.

    The brain asks for a SUBSET of trained heads (and optionally passes brain context for
    the cross-gate). Only the requested heads are computed → the output width/shape changes
    per call and unrequested heads cost nothing (lazy compute).
    """

    def __init__(self, heads: dict[str, dict]):
        """heads: {head_key: kwargs-for-ColumnNetworkNode (must include task; factories/names
        supplied at fit)}. Kept minimal; see build_from_pool for the common case."""
        self._spec = heads
        self.nets: dict[str, ColumnNetworkNode] = {}

    def fit(self, X: Matrix, targets: dict[str, Labels],
            brain_ctx: Matrix | None = None) -> "ColumnNetwork":
        for hkey, node in self.nets.items():
            node.fit(X, targets[hkey], brain_ctx=brain_ctx)
        return self

    def add_net(self, head_key: str, node: ColumnNetworkNode) -> None:
        self.nets[head_key] = node

    def trained_heads(self) -> list[str]:
        return list(self.nets)

    def predict(self, X: Matrix, request: list[str] | None = None,
                brain_ctx: Matrix | None = None) -> dict[str, list[list[float]]]:
        """Compute ONLY the requested heads (default: all trained). Returns {head: rows}."""
        want = request or self.trained_heads()
        missing = [h for h in want if h not in self.nets]
        if missing:
            raise KeyError(f"untrained head(s) requested: {missing}; trained: {self.trained_heads()}")
        return {h: self.nets[h].predict_output(X, brain_ctx=brain_ctx) for h in want}
