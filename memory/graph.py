"""KnowledgeGraph — a temporal-ish concept graph (stdlib).

Documents, chunks, and extracted concepts are nodes; edges link doc->chunk and
doc->concept. Documents sharing concepts become connected, forming a navigable
web of knowledge (the 'brain with nodes' idea) that the dashboard renders.
"""
from __future__ import annotations


class KnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}      # id -> {type, label, count}
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
        by = {}
        for n in self.nodes.values():
            by[n["type"]] = by.get(n["type"], 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "by_type": by}
