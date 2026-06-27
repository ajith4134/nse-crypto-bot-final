"""KnowledgeBrain — the Phase-4 brain/memory layer.

Ingests documents (text / .md / .txt / .py / .pdf), chunks them into the
VectorMemory (neural embeddings + cosine recall via embedded ChromaDB), extracts
concepts into the KnowledgeGraph (NetworkX), and answers recall queries via
semantic search + graph context. It GROWS as more is ingested, and tracks how
often each chunk is recalled (a crude salience signal for future consolidation).

Inputs: titles/paths/urls + raw text. Outputs: recall hits, stats, and a
dashboard snapshot ({stats, nodes, edges}). Public API (KnowledgeBrain and its
ingest_text/ingest_file/recall/stats/dashboard_snapshot methods) is unchanged.
"""
from __future__ import annotations

import html
import os
import re
import urllib.request
from collections import Counter
from itertools import combinations

from memory.graph import KnowledgeGraph
from memory.store import VectorMemory, tokenize


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "doc"


def _chunk(text: str, words: int = 70) -> list[str]:
    toks = text.split()
    return [" ".join(toks[i:i + words]) for i in range(0, len(toks), words)] or [text]


def _read_pdf(path: str) -> str:
    """Extract text from a PDF (reuse-first: pypdf, pure-Python, CPU-only)."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(re.sub(r"\s+", " ", raw)).strip()


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
        concepts = self.mem.top_terms(Counter(tokenize(text)), n=6)
        for term in concepts:
            cnode = "concept:" + term
            self.graph.add_node(cnode, "concept", term)
            self.graph.add_edge(doc_id, cnode, "about")
        # Concept co-occurrence: concepts sharing a document get linked, so the
        # graph forms a navigable web (not just a star of doc->concept spokes).
        for a, b in combinations(sorted(concepts), 2):
            self.graph.add_edge("concept:" + a, "concept:" + b, "co_occurs")
        return doc_id

    def ingest_file(self, path: str) -> str:
        if path.lower().endswith(".pdf"):
            text = _read_pdf(path)
        else:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        return self.ingest_text(os.path.basename(path), text)

    def ingest_url(self, url: str) -> str:
        """Lightweight live-web ingestion stand-in (urllib + HTML->text).

        Kept dependency-free and CPU-only on purpose: the reuse-first next drop-in
        for rich crawling is Crawl4AI, but it needs a headless browser (Playwright)
        that is heavy and fragile in headless/CI environments, so it is skipped
        here. This stub fetches a page and strips tags so URLs are still ingestible.
        """
        req = urllib.request.Request(url, headers={"User-Agent": "ml-brain/0.1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", "ignore")
        title = url.split("//")[-1][:60]
        return self.ingest_text(f"url: {title}", _html_to_text(raw))

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
