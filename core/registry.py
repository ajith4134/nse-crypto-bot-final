"""Live node registry — the single source of truth the dashboard reads.

Every node that participates in the network registers here with its metadata,
training status, metrics, and upstream wiring. snapshot() emits the JSON the
dashboard renders, so any newly-registered node automatically appears
(dashboard-sync rule).

Inputs:  node instances + metrics dicts.
Outputs: a JSON-able snapshot of nodes and edges.
"""
from __future__ import annotations

from core.node_protocol import BaseNode, NodeInfo, NodeProtocol

_NODES: dict[str, NodeInfo] = {}


def register(node: BaseNode, summary: str | None = None,
             upstream: list[str] | None = None) -> None:
    """Register a node. Rejects anything that doesn't satisfy NodeProtocol."""
    if not isinstance(node, NodeProtocol):
        raise TypeError(f"{node!r} does not satisfy NodeProtocol")
    _NODES[node.name] = NodeInfo(
        name=node.name, kind=node.kind,
        summary=summary or getattr(node, "summary", ""),
        schema=node.schema, upstream=upstream or [],
        task=getattr(node, "task", "binary"), head=getattr(node, "head", "y"),
    )


def set_metrics(name: str, metrics: dict, trained: bool = True) -> None:
    info = _NODES.get(name)
    if info is None:
        raise KeyError(f"node '{name}' is not registered")
    info.metrics = metrics
    info.trained = trained


def reset() -> None:
    _NODES.clear()


def snapshot() -> dict:
    """Nodes + derived edges (upstream -> node) for the dashboard."""
    edges = [{"source": up, "target": info.name, "head": info.head}
             for info in _NODES.values() for up in info.upstream]
    return {
        "nodes": [info.to_json() for info in _NODES.values()],
        "edges": edges,
    }
