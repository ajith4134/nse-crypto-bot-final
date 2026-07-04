"""VectorMemory — semantic chunk store with neural embeddings (reuse-first).

Primary backend: ChromaDB (embedded PersistentClient, NO server) holding real
sentence-embeddings (all-MiniLM-L6-v2 via sentence-transformers) and ranking by
cosine similarity. Inputs: (chunk_id, text, title). Output of `search`: a ranked
list of (chunk_id, cosine_score).

Reuse-first choice: ChromaDB(embedded) + sentence-transformers + NetworkX deliver
human-brain-style vector+graph memory CPU-first with ZERO external services. We
deliberately avoid Mem0 / Graphiti / Neo4j / Qdrant-server here: those need a
running service and/or an LLM key, so they cannot run cleanly headless. If those
OSS imports are unavailable, we fall back to the original pure-stdlib TF-IDF
cosine path so the no-deps mode still works. (Live web ingestion via Crawl4AI is
the next drop-in on the ingestion side — see memory/brain.py.)
"""
from __future__ import annotations

import math
import os
import re
import uuid
from collections import Counter

# Persistent on-disk store for the embedded vector DB (gitignored).
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma_store")
EMBED_MODEL = "all-MiniLM-L6-v2"

# Detect the mature-OSS backend once; fall back to stdlib TF-IDF if unavailable.
try:
    import chromadb  # type: ignore
    _HAVE_CHROMA = True
except Exception:  # pragma: no cover - exercised only in no-deps mode
    _HAVE_CHROMA = False

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "it", "this", "that", "be", "at", "from", "we", "you",
    "can", "if", "so", "not", "but", "its", "into", "each", "per", "via", "use",
    "used", "using", "they", "their", "than", "then", "which", "when", "what",
    "how", "all", "any", "may", "more", "most", "one", "two", "do", "does",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z0-9]{2,}", text.lower()) if t not in _STOP]


def _build_embedding_function():
    """Prefer real neural sentence-embeddings; fall back to Chroma's default.

    Returns (embedding_function, backend_label) or (None, ...) if Chroma itself
    is missing (caller then uses TF-IDF).
    """
    if not _HAVE_CHROMA:
        return None, "tfidf"
    from chromadb.utils import embedding_functions
    try:
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        ef(["warmup"])  # force model load/download now so failures fall back cleanly
        return ef, f"chroma+sentence-transformers/{EMBED_MODEL}"
    except Exception:
        # sentence-transformers unavailable/too heavy: use Chroma's bundled
        # default embedding (ONNX MiniLM) so recall stays neural, not keyword.
        try:
            ef = embedding_functions.DefaultEmbeddingFunction()
            return ef, "chroma+default-onnx-minilm"
        except Exception:
            return None, "tfidf"


class VectorMemory:
    """Add chunks, search them by meaning. Same public API as the TF-IDF original:
    `.chunks`, `.df`, `add(cid, text, title)`, `search(query, k)`, `top_terms(...)`.
    """

    def __init__(self, persist_name: str | None = None):
        self.chunks: dict[str, dict] = {}     # cid -> {text, counts, title}
        self.df: dict[str, int] = {}          # term -> #chunks containing it (vocab/idf)
        self._collection = None
        self.backend = "tfidf"

        ef, label = _build_embedding_function()
        if ef is not None:
            try:
                client = chromadb.PersistentClient(path=CHROMA_DIR)
                if persist_name:
                    # STABLE collection → knowledge survives process restarts. The old
                    # uuid-per-instance name silently abandoned every learned document
                    # on each dashboard restart, so the Brain Learning panel honestly
                    # showed 0 docs/chunks/concepts after learning (2026-07-03 fix).
                    self._collection = client.get_or_create_collection(
                        name=persist_name, embedding_function=ef,
                        metadata={"hnsw:space": "cosine"})
                    self._rehydrate()
                else:
                    # Unique collection per instance keeps tests / runs isolated while
                    # the data still persists on disk under .chroma_store.
                    name = "knowledge_" + uuid.uuid4().hex[:12]
                    self._collection = client.create_collection(
                        name=name, embedding_function=ef,
                        metadata={"hnsw:space": "cosine"})
                self.backend = label
            except Exception:
                self._collection = None
                self.backend = "tfidf"

    def _rehydrate(self) -> None:
        """Rebuild the in-memory chunk/vocab maps from the persisted collection —
        search results are filtered by `cid in self.chunks`, so without this every
        restart made persisted documents unfindable."""
        try:
            got = self._collection.get(include=["documents", "metadatas"])
            for cid, doc, meta in zip(got.get("ids") or [],
                                      got.get("documents") or [],
                                      got.get("metadatas") or []):
                if not doc or cid in self.chunks:
                    continue
                counts = Counter(tokenize(doc))
                self.chunks[cid] = {"text": doc, "counts": counts,
                                    "title": (meta or {}).get("title", "")}
                for t in counts:
                    self.df[t] = self.df.get(t, 0) + 1
        except Exception:
            pass                       # empty/new collection — nothing to rehydrate

    # ---- ingestion -------------------------------------------------------
    def add(self, cid: str, text: str, title: str = "") -> None:
        counts = Counter(tokenize(text))
        self.chunks[cid] = {"text": text, "counts": counts, "title": title}
        for t in counts:
            self.df[t] = self.df.get(t, 0) + 1
        if self._collection is not None:
            self._collection.upsert(ids=[cid], documents=[text],
                                    metadatas=[{"title": title}])

    # ---- retrieval -------------------------------------------------------
    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        if self._collection is not None:
            return self._search_chroma(query, k)
        return self._search_tfidf(query, k)

    def _search_chroma(self, query: str, k: int) -> list[tuple[str, float]]:
        n = min(k, len(self.chunks))
        if n <= 0:
            return []
        res = self._collection.query(query_texts=[query], n_results=n)
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out = []
        for cid, dist in zip(ids, dists):
            if cid in self.chunks:                # cosine distance -> similarity
                out.append((cid, round(1.0 - float(dist), 4)))
        return out

    # ---- stdlib fallback (TF-IDF cosine) --------------------------------
    def _idf(self, t: str) -> float:
        n = len(self.chunks)
        return math.log((1 + n) / (1 + self.df.get(t, 0))) + 1.0

    def _tfidf(self, counts: Counter) -> dict[str, float]:
        tot = sum(counts.values()) or 1
        v = {t: (c / tot) * self._idf(t) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def _search_tfidf(self, query: str, k: int) -> list[tuple[str, float]]:
        qv = self._tfidf(Counter(tokenize(query)))
        if not qv:
            return []
        scored = []
        for cid, ch in self.chunks.items():
            cv = self._tfidf(ch["counts"])
            s = sum(qv.get(t, 0.0) * cv.get(t, 0.0) for t in qv)
            if s > 0:
                scored.append((round(s, 4), cid))
        scored.sort(reverse=True)
        return [(cid, s) for s, cid in scored[:k]]

    # ---- concept extraction (used by the graph layer) -------------------
    def top_terms(self, counts: Counter, n: int = 6) -> list[str]:
        scored = sorted(((c * self._idf(t), t) for t, c in counts.items()), reverse=True)
        return [t for _, t in scored[:n]]
