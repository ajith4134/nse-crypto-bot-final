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
import math
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

    def recall(self, query: str, k: int = 4, associative: bool = True) -> list[dict]:
        """Hybrid human-like recall: vector similarity + ASSOCIATIVE spreading-activation
        (Personalized PageRank over the knowledge graph), fused by Reciprocal Rank Fusion,
        then reinforced by how often each memory has been recalled before (salience).

        Backward-compatible: returns the same {title, score, snippet, concepts} dicts (plus a
        `via` field = 'vector' | 'associative'). Degrades to vector-only if the graph/PPR is
        unavailable, so the no-deps path still works.
        """
        cand = max(k * 4, 12)
        hits = self.mem.search(query, cand)            # broaden the candidate pool
        if not hits:
            return []

        def rrf(rank: int) -> float:                    # reciprocal rank fusion (k0=60)
            return 1.0 / (60 + rank)

        fused: dict[str, float] = {}
        via: dict[str, str] = {}
        for r, (cid, _s) in enumerate(hits):            # 1) vector channel
            fused[cid] = fused.get(cid, 0.0) + rrf(r)
            via[cid] = "vector"

        if associative:                                 # 2) associative channel (PPR)
            seeds = {cid: max(s, 1e-3) for cid, s in hits}
            pr = self.graph.personalized_ranks(seeds)
            pr_chunks = sorted(((cid, sc) for cid, sc in pr.items() if cid in self.mem.chunks),
                               key=lambda kv: -kv[1])
            for r, (cid, _sc) in enumerate(pr_chunks[:cand]):
                fused[cid] = fused.get(cid, 0.0) + rrf(r)
                via.setdefault(cid, "associative")

        for cid in fused:                               # 3) salience: recalled-before = stronger
            fused[cid] *= 1.0 + 0.15 * math.log1p(self.access.get(cid, 0))

        ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        results = []
        for cid, score in ranked:
            ch = self.mem.chunks.get(cid)
            if ch is None:
                continue
            self.access[cid] += 1                       # reinforce on recall
            doc_id = cid.split("#")[0]
            concepts = [n.split(":", 1)[1] for n in self.graph.neighbors(doc_id)
                        if n.startswith("concept:")]
            results.append({"title": ch["title"], "score": round(score, 4),
                            "snippet": ch["text"][:220].replace("\n", " "),
                            "concepts": concepts[:6], "via": via.get(cid, "vector")})
        return results

    def stats(self) -> dict:
        return {"docs": len(self.docs), "chunks": len(self.mem.chunks),
                "vocab": len(self.mem.df), **self.graph.stats(),
                "recalls": sum(self.access.values())}

    def dashboard_snapshot(self) -> dict:
        snap = self.graph.snapshot(types={"doc", "concept"})
        return {"stats": self.stats(), **snap}
