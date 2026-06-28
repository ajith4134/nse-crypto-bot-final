"""trading/strategy/registry.py — promote evolved strategies to NodeProtocol nodes (T8.3).

A guardrail-passing Strategy is wrapped as a StrategyNode that satisfies the project's
NodeProtocol (name/kind/schema + fit/predict_proba/predict), so the ML Network Brain can
route/ensemble it exactly like any other node. The node consumes a TRADING feature matrix
(rows of the FEATURE_NAMES values, in `features` order) and emits p(long): long→~0.9,
short→~0.1, flat→0.5. `fit` is a no-op (the genome is already "trained" by evolution).

StrategyRegistry holds the promoted nodes with their OOS metrics + guardrail status for
the dashboard. This is the honest bridge from the evolution engine into the brain.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.node_protocol import BaseNode, IOSchema, NodeProtocol
from trading.strategy.genome import Strategy, compile_signal, get_pset


class StrategyNode(BaseNode):
    """Wraps an evolved Strategy as a NodeProtocol node over a trading feature matrix."""

    kind = "strategy"

    def __init__(self, strategy: Strategy, features: list[str], *, metrics: dict | None = None):
        self.strategy = strategy
        self.features = list(features)
        self.name = strategy.id or "strategy"
        self.summary = f"evolved {strategy.market} GP strategy (gen {strategy.provenance.get('generation', 0)})"
        self.schema = IOSchema(len(self.features), "trading features (z-scored)", "p(long)")
        self.metrics = metrics or {}
        self._trained = True

    def fit(self, X, y=None) -> "StrategyNode":          # genome already evolved; no-op
        return self

    def _frame(self, X) -> pd.DataFrame:
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        cols = self.features[: arr.shape[1]]
        return pd.DataFrame(arr[:, : len(cols)], columns=cols)

    def predict_proba(self, X):
        df = self._frame(X)
        pset = get_pset(self.features)
        # z-score over the provided batch (approx; live would use a rolling window)
        z = {}
        for f in self.features:
            col = df[f] if f in df.columns else pd.Series(0.0, index=df.index)
            sd = col.std()
            z[f] = (col - col.mean()) / sd if sd and sd > 0 else col * 0.0
        zdf = pd.DataFrame(z, index=df.index)
        long_sig = compile_signal(self.strategy.long_tree(), pset, zdf, self.features)
        if self.strategy.allow_short and self.strategy.short_src:
            short_sig = compile_signal(self.strategy.short_tree(), pset, zdf, self.features)
        else:
            short_sig = pd.Series(False, index=df.index)
        out = []
        for lo, sh in zip(long_sig, short_sig):
            out.append(0.9 if (lo and not sh) else (0.1 if (sh and not lo) else 0.5))
        return out


def promote(strategy: Strategy, features: list[str], *, metrics: dict | None = None) -> StrategyNode:
    """Wrap a Strategy as a StrategyNode (verified to satisfy NodeProtocol)."""
    node = StrategyNode(strategy, features, metrics=metrics)
    assert isinstance(node, NodeProtocol), "StrategyNode must satisfy NodeProtocol"
    return node


@dataclass
class StrategyRegistry:
    """Holds promoted strategy nodes + their provenance/metrics for the brain + dashboard."""
    nodes: list = field(default_factory=list)

    def add(self, node: StrategyNode) -> StrategyNode:
        self.nodes.append(node)
        return node

    def names(self) -> list[str]:
        return [n.name for n in self.nodes]

    def status(self) -> dict:
        return {
            "n_promoted": len(self.nodes),
            "nodes": [{"name": n.name, "kind": n.kind, "market": n.strategy.market,
                       "generation": n.strategy.provenance.get("generation", 0),
                       "metrics": n.metrics} for n in self.nodes],
        }
