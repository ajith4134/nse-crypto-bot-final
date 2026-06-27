"""VectorMemory — pure-stdlib semantic store (TF-IDF + cosine).

No dependencies: tokenizes text, stores per-chunk term counts, and ranks by
cosine similarity of TF-IDF vectors. Good enough for real recall now; swappable
for neural embeddings + a vector DB later (reuse-first / ask-to-install).
"""
from __future__ import annotations

import math
import re
from collections import Counter

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "it", "this", "that", "be", "at", "from", "we", "you",
    "can", "if", "so", "not", "but", "its", "into", "each", "per", "via", "use",
    "used", "using", "they", "their", "than", "then", "which", "when", "what",
    "how", "all", "any", "may", "more", "most", "one", "two", "do", "does",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z][a-z0-9]{2,}", text.lower()) if t not in _STOP]


class VectorMemory:
    def __init__(self):
        self.chunks: dict[str, dict] = {}     # cid -> {text, counts, title}
        self.df: dict[str, int] = {}          # term -> #chunks containing it

    def add(self, cid: str, text: str, title: str = "") -> None:
        counts = Counter(tokenize(text))
        self.chunks[cid] = {"text": text, "counts": counts, "title": title}
        for t in counts:
            self.df[t] = self.df.get(t, 0) + 1

    def _idf(self, t: str) -> float:
        n = len(self.chunks)
        return math.log((1 + n) / (1 + self.df.get(t, 0))) + 1.0

    def _tfidf(self, counts: Counter) -> dict[str, float]:
        tot = sum(counts.values()) or 1
        v = {t: (c / tot) * self._idf(t) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
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

    def top_terms(self, counts: Counter, n: int = 6) -> list[str]:
        scored = sorted(((c * self._idf(t), t) for t, c in counts.items()), reverse=True)
        return [t for _, t in scored[:n]]
