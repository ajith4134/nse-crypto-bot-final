"""KnowledgeBrain — the Phase-4 brain/memory layer.

Ingests documents (text / .md / .txt / .py), chunks them into the VectorMemory,
extracts concepts into the KnowledgeGraph, and answers recall queries via
semantic search + graph context. It GROWS as more is ingested, and tracks how
often each chunk is recalled (a crude salience signal for future consolidation).
"""
from __future__ import annotations

import os
import re
from collections import Counter

from memory.graph import KnowledgeGraph
from memory.store import VectorMemory, tokenize


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "doc"


def _chunk(text: str, words: int = 70) -> list[str]:
    toks = text.split()
    return [" ".join(toks[i:i + words]) for i in range(0, len(toks), words)] or [text]


class KnowledgeBrain:
    def __init__(self):
        self.mem = VectorMemory()
        self.graph = KnowledgeGraph()
        self.access = Counter()
        self.docs: list[str] = []

    def ingest_text(self, title: str, text: str) -> str:
        doc_id = "doc:" + _slug(title)
        self.graph.add_node(doc_id, "doc", title)
        self.docs.append(doc_id)
        for i, ch in enumerate(_chunk(text)):
            cid = f"{doc_id}#c{i}"
            self.mem.add(cid, ch, title)
            self.graph.add_node(cid, "chunk", f"{title} [{i}]")
            self.graph.add_edge(doc_id, cid, "has_chunk")
        for term in self.mem.top_terms(Counter(tokenize(text)), n=6):
            cnode = "concept:" + term
            self.graph.add_node(cnode, "concept", term)
            self.graph.add_edge(doc_id, cnode, "about")
        return doc_id

    def ingest_file(self, path: str) -> str:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return self.ingest_text(os.path.basename(path), text)

    def recall(self, query: str, k: int = 4) -> list[dict]:
        hits = self.mem.search(query, k)
        results = []
        for cid, score in hits:
            self.access[cid] += 1
            ch = self.mem.chunks[cid]
            doc_id = cid.split("#")[0]
            concepts = [n.split(":", 1)[1] for n in self.graph.neighbors(doc_id)
                        if n.startswith("concept:")]
            snippet = ch["text"][:220].replace("\n", " ")
            results.append({"title": ch["title"], "score": score,
                            "snippet": snippet, "concepts": concepts[:6]})
        return results

    def stats(self) -> dict:
        return {"docs": len(self.docs), "chunks": len(self.mem.chunks),
                "vocab": len(self.mem.df), **self.graph.stats(),
                "recalls": sum(self.access.values())}

    def dashboard_snapshot(self) -> dict:
        snap = self.graph.snapshot(types={"doc", "concept"})
        return {"stats": self.stats(), **snap}
