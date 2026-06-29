"""memory/librarian.py — self-feeding internet: the brain reads on its own (Phase P4.3).

The brain discovers, fetches, cleans, de-duplicates, and INGESTS web pages, papers, and
news into its own KnowledgeBrain memory — continuously, on a schedule. Pipeline:

    discover (web / arXiv / RSS) → fetch+extract (clean text) → dedup → brain.ingest_text

Reuse-first, all gated behind INJECTED callables so it's offline-testable (stubs) and runs
live only when called:
  • web search — ddgs ; RSS — feedparser ; papers — arxiv ; HTML→clean-text — trafilatura.
  • Heavier services (SearXNG, Crawl4AI, Docling) plug in via the same injected callables
    when configured — not required.
Dedup is content+URL hashed (persistable). Scheduling uses APScheduler (live) but a
step-driven `feed()` keeps everything deterministic in tests. No network at import.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field


# ── default (live) source fetchers — lazy imports, try/except → [] ────────────────
def _ddgs_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        from ddgs import DDGS
        return [{"title": r.get("title", ""), "url": r.get("href", ""),
                 "body": r.get("body", "")} for r in DDGS().text(query, max_results=max_results)]
    except Exception:
        return []


def _rss_fetch(url: str, limit: int = 10) -> list[dict]:
    try:
        import feedparser
        f = feedparser.parse(url)
        return [{"title": getattr(e, "title", ""), "url": getattr(e, "link", ""),
                 "body": getattr(e, "summary", "")} for e in f.entries[:limit]]
    except Exception:
        return []


def _arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(query=query, max_results=max_results)
        out = []
        for r in client.results(search):
            out.append({"title": r.title, "url": r.entry_id, "body": r.summary})
        return out
    except Exception:
        return []


def _trafilatura_extract(url: str) -> str:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded) or "" if downloaded else ""
    except Exception:
        return ""


@dataclass
class Librarian:
    """Autonomous knowledge acquirer that feeds the brain from the internet."""

    brain: object                                   # KnowledgeBrain (has ingest_text)
    web_search: object = None                       # (query, max_results) -> [{title,url,body}]
    rss_fetch: object = None                        # (url, limit) -> [...]
    arxiv_search: object = None                     # (query, max_results) -> [...]
    extractor: object = None                        # (url) -> clean text
    persist_path: str | None = None                 # dedup seen-set persistence (json)
    _seen: set = field(default_factory=set, init=False)
    stats: dict = field(default_factory=lambda: {"found": 0, "ingested": 0, "dupes": 0},
                        init=False)

    def __post_init__(self) -> None:
        self.web_search = self.web_search or _ddgs_search
        self.rss_fetch = self.rss_fetch or _rss_fetch
        self.arxiv_search = self.arxiv_search or _arxiv_search
        self.extractor = self.extractor or _trafilatura_extract
        if self.persist_path and os.path.exists(self.persist_path):
            try:
                with open(self.persist_path) as fh:
                    self._seen = set(json.load(fh))
            except Exception:
                self._seen = set()

    @staticmethod
    def _key(url: str, text: str) -> str:
        return hashlib.sha1(f"{url}|{text[:200]}".encode()).hexdigest()

    def _save_seen(self) -> None:
        if self.persist_path:
            try:
                with open(self.persist_path, "w") as fh:
                    json.dump(sorted(self._seen), fh)
            except Exception:
                pass

    # ── discover ────────────────────────────────────────────────────────────────
    def discover(self, topic: str, *, sources=("web", "arxiv"), rss_urls=None,
                 max_per: int = 5) -> list[dict]:
        items: list[dict] = []
        if "web" in sources:
            for r in self.web_search(topic, max_per):
                items.append({**r, "source": "web"})
        if "arxiv" in sources:
            for r in self.arxiv_search(topic, max_per):
                items.append({**r, "source": "arxiv"})
        if "rss" in sources:
            for u in (rss_urls or []):
                for r in self.rss_fetch(u, max_per):
                    items.append({**r, "source": "rss"})
        self.stats["found"] += len(items)
        return items

    # ── ingest one item ─────────────────────────────────────────────────────────
    def ingest_item(self, item: dict) -> dict:
        url = item.get("url", "")
        # web items get full-text extraction; arxiv/rss use the abstract/summary body
        text = item.get("body", "")
        if item.get("source") == "web" and url:
            full = self.extractor(url)
            if full:
                text = full
        title = item.get("title") or url or "untitled"
        if not text.strip():
            return {"ingested": False, "reason": "no content", "title": title}
        key = self._key(url, text)
        if key in self._seen:
            self.stats["dupes"] += 1
            return {"ingested": False, "reason": "duplicate", "title": title}
        self._seen.add(key)
        try:
            doc_id = self.brain.ingest_text(title, text)
        except Exception as exc:
            return {"ingested": False, "reason": f"ingest error: {str(exc)[:60]}", "title": title}
        self.stats["ingested"] += 1
        self._save_seen()
        return {"ingested": True, "doc_id": doc_id, "title": title, "source": item.get("source"),
                "chars": len(text)}

    # ── feed (one pass over topics) ─────────────────────────────────────────────
    def feed(self, topics, *, sources=("web", "arxiv"), rss_urls=None, max_per: int = 5) -> dict:
        if isinstance(topics, str):
            topics = [topics]
        results = []
        for t in topics:
            for item in self.discover(t, sources=sources, rss_urls=rss_urls, max_per=max_per):
                results.append(self.ingest_item(item))
        ingested = [r for r in results if r.get("ingested")]
        return {"topics": list(topics), "found": len(results), "ingested": len(ingested),
                "dupes": sum(1 for r in results if r.get("reason") == "duplicate"),
                "by_source": _count_by(ingested, "source"),
                "items": ingested}

    # ── live scheduling (gated; APScheduler) ────────────────────────────────────
    def schedule(self, topics, *, interval_minutes: int = 60, **feed_kw):  # pragma: no cover
        """Run feed() every interval_minutes on a background scheduler (live use)."""
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler()
        sched.add_job(lambda: self.feed(topics, **feed_kw), "interval",
                      minutes=interval_minutes, id="librarian_feed")
        sched.start()
        return sched

    def status(self) -> dict:
        return {"seen": len(self._seen), **self.stats,
                "sources": {"web": "ddgs", "rss": "feedparser", "arxiv": "arxiv",
                            "extract": "trafilatura"}}


def _count_by(items: list[dict], key: str) -> dict:
    out: dict = {}
    for it in items:
        out[it.get(key, "?")] = out.get(it.get(key, "?"), 0) + 1
    return out
