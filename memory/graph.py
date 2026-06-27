"""KnowledgeGraph — concept graph backed by NetworkX (reuse-first).

Documents, chunks and extracted concepts are nodes; edges link doc->chunk
(has_chunk), doc->concept (about) and concept<->concept (co_occurs). Documents
that share concepts become connected, forming a navigable web of knowledge the
dashboard renders. Backed by `networkx.MultiDiGraph` (mature OSS graph algos for
free); if NetworkX is unavailable we fall back to a stdlib dict graph so the
no-deps mode still works. Public API is unchanged: add_node / add_edge /
neighbors / snapshot / stats.

Inputs: node ids + types + labels, and (src, dst, rel) edges.
Outputs: neighbor lists, a dashboard snapshot {nodes, edges}, and stats.
"""
from __future__ import annotations

try:
    import networkx as nx  # type: ignore
    _HAVE_NX = True
except Exception:  # pragma: no cover - exercised only in no-deps mode
    _HAVE_NX = False


class _NetworkxGraph:
    """NetworkX MultiDiGraph wearing the project's KnowledgeGraph API."""

    def __init__(self):
        self._g = nx.MultiDiGraph()

    def add_node(self, nid: str, ntype: str, label: str) -> None:
        if self._g.has_node(nid):
            self._g.nodes[nid]["count"] += 1
        else:
            self._g.add_node(nid, type=ntype, label=label, count=1)

    def add_edge(self, src: str, dst: str, rel: str) -> None:
        # key=rel collapses duplicate (src, dst, rel) edges, matching the old
        # de-dup semantics while still allowing distinct relations per pair.
        if not self._g.has_edge(src, dst, key=rel):
            self._g.add_edge(src, dst, key=rel, rel=rel)

    def neighbors(self, nid: str) -> list[str]:
        if not self._g.has_node(nid):
            return []
        out = list(self._g.successors(nid)) + list(self._g.predecessors(nid))
        return list(dict.fromkeys(out))

    def snapshot(self, types=None) -> dict:
        types = types or {"doc", "concept"}
        nodes = [{"id": i, **d} for i, d in self._g.nodes(data=True)
                 if d.get("type") in types]
        keep = {n["id"] for n in nodes}
        edges = [{"source": s, "target": d, "rel": k}
                 for s, d, k in self._g.edges(keys=True) if s in keep and d in keep]
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        by: dict[str, int] = {}
        for _, d in self._g.nodes(data=True):
            by[d.get("type", "?")] = by.get(d.get("type", "?"), 0) + 1
        return {"nodes": self._g.number_of_nodes(),
                "edges": self._g.number_of_edges(), "by_type": by}


class _DictGraph:
    """Pure-stdlib fallback (the original implementation)."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []
        self._seen = set()

    def add_node(self, nid: str, ntype: str, label: str) -> None:
        if nid in self.nodes:
            self.nodes[nid]["count"] += 1
        else:
            self.nodes[nid] = {"type": ntype, "label": label, "count": 1}

    def add_edge(self, src: str, dst: str, rel: str) -> None:
        key = (src, dst, rel)
        if key not in self._seen:
            self._seen.add(key)
            self.edges.append(key)

    def neighbors(self, nid: str) -> list[str]:
        out = [d for (s, d, _) in self.edges if s == nid]
        out += [s for (s, d, _) in self.edges if d == nid]
        return list(dict.fromkeys(out))

    def snapshot(self, types=None) -> dict:
        types = types or {"doc", "concept"}
        nodes = [{"id": i, **n} for i, n in self.nodes.items() if n["type"] in types]
        keep = {n["id"] for n in nodes}
        edges = [{"source": s, "target": d, "rel": r}
                 for (s, d, r) in self.edges if s in keep and d in keep]
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict:
        by: dict[str, int] = {}
        for n in self.nodes.values():
            by[n["type"]] = by.get(n["type"], 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "by_type": by}


def KnowledgeGraph():
    """Factory: NetworkX-backed graph when available, else the stdlib fallback.

    Returned object exposes the unchanged add_node / add_edge / neighbors /
    snapshot / stats API the rest of the code calls.
    """
    return _NetworkxGraph() if _HAVE_NX else _DictGraph()
