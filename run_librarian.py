"""run_librarian.py — Phase P4.3 (Self-feeding internet) OFFLINE demo.

Drives `memory.librarian.Librarian` end to end, fully OFFLINE and deterministic
(NO network, NO API keys, NO embedding model). The Librarian discovers, fetches,
cleans, de-duplicates, and INGESTS web pages + papers into a KnowledgeBrain — on a
schedule, in live use. A real KnowledgeBrain downloads an embedding model on first
use (= network), so this demo composes the Librarian over a tiny **stub brain**
(captures every ingest_text call) and **INJECTS** stub source callables
(web_search / arxiv_search) + a stub extractor — so nothing ever touches the network.

What it demonstrates:

  1. discover() — pulls candidate items across web + arXiv sources.

  2. feed() — ingests items: WEB items get full-text extraction (via the injected
     extractor), arXiv items use their abstract body. Reports by_source counts.

  3. dedup — a 2nd feed() over the same topics ingests 0 (content+URL hashed seen-set).

  4. status() — seen-set size + found/ingested/dupes counters + source backends.

`build_demo_librarian()` returns a JSON-able snapshot {feed, refeed, status} for the
dashboard. Offline + deterministic.

LIVE MODE (not exercised here — needs network + optional deps): drop the injected
stubs and the Librarian defaults to ddgs (web search), feedparser (RSS), arxiv
(papers), and trafilatura (HTML → clean text). Optional SearXNG / Crawl4AI / Docling
endpoints plug in via the same injected callables. Run it always-on with
`lib.schedule(topics, interval_minutes=60)` — an APScheduler background loop that
re-feeds on an interval. LLM keys (core.llm / OPENAI_*) power summarization.

Usage:
    .venv/bin/python run_librarian.py
"""
from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")  # keep the demo output clean

from memory.librarian import Librarian

_TOPICS = ["continual learning", "associative memory"]

# Deterministic offline "search results". WEB items carry only a short snippet body —
# their full text comes from the injected extractor (mimics trafilatura). arXiv items
# carry their full abstract as the body (no extraction needed).
_WEB_DB = {
    "continual learning": [
        {"title": "Continual learning, explained",
         "url": "https://example.org/continual-learning",
         "body": "short snippet teaser"},
        {"title": "Avoiding catastrophic forgetting",
         "url": "https://example.org/forgetting",
         "body": "short snippet teaser"},
    ],
    "associative memory": [
        {"title": "Modern Hopfield networks",
         "url": "https://example.org/hopfield",
         "body": "short snippet teaser"},
    ],
}

_ARXIV_DB = {
    "continual learning": [
        {"title": "A Continual Learning Survey",
         "url": "http://arxiv.org/abs/1909.08383",
         "body": "Abstract: a comprehensive survey of continual learning methods, "
                 "covering replay, regularization, and parameter-isolation families."},
    ],
    "associative memory": [
        {"title": "Hopfield Networks is All You Need",
         "url": "http://arxiv.org/abs/2008.02217",
         "body": "Abstract: modern continuous Hopfield networks with exponential "
                 "storage capacity and a retrieval rule equivalent to attention."},
    ],
}

# Full clean text the injected extractor returns per URL (mimics trafilatura.extract).
_EXTRACTED = {
    "https://example.org/continual-learning":
        "Continual learning lets a model keep acquiring knowledge across a stream of "
        "tasks without overwriting what it already knows. " * 4,
    "https://example.org/forgetting":
        "Catastrophic forgetting is the abrupt loss of previously learned information "
        "when a network is trained on new data. " * 4,
    "https://example.org/hopfield":
        "Modern Hopfield networks store and retrieve patterns associatively and connect "
        "directly to the attention mechanism of transformers. " * 4,
}


def _stub_web_search(query: str, max_results: int = 5) -> list[dict]:
    """Offline stand-in for ddgs — deterministic, no network."""
    return [dict(r) for r in _WEB_DB.get(query, [])][:max_results]


def _stub_arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    """Offline stand-in for the arxiv client — deterministic, no network."""
    return [dict(r) for r in _ARXIV_DB.get(query, [])][:max_results]


def _stub_extractor(url: str) -> str:
    """Offline stand-in for trafilatura — deterministic full-text per URL, no network."""
    return _EXTRACTED.get(url, "")


class _StubMem:
    """Mimics KnowledgeBrain.mem: a `chunks` dict {id: {title, text}}."""

    def __init__(self) -> None:
        self.chunks: dict[str, dict] = {}


class _StubBrain:
    """Offline stand-in for KnowledgeBrain — captures every ingest_text, no model/network.

    Exposes the only surface Librarian needs: `ingest_text(title, text) -> doc_id`."""

    def __init__(self) -> None:
        self.mem = _StubMem()
        self._n = 0

    def ingest_text(self, title: str, text: str) -> str:
        self._n += 1
        doc_id = f"doc{self._n}"
        self.mem.chunks[doc_id] = {"title": title, "text": text}
        return doc_id


def build_demo_librarian() -> dict:
    """JSON-able snapshot {feed, refeed, status}. Offline + deterministic.

    Builds a Librarian over a stub brain with INJECTED stub web/arxiv sources + a stub
    extractor, then: feeds across web+arxiv, re-feeds (dedup → 0 ingested), and reports
    status(). No network, no API keys, no embedding model.
    """
    brain = _StubBrain()
    lib = Librarian(
        brain,
        web_search=_stub_web_search,
        arxiv_search=_stub_arxiv_search,
        extractor=_stub_extractor,
        persist_path=None,  # in-memory seen-set → deterministic
    )

    feed = lib.feed(_TOPICS, sources=("web", "arxiv"), max_per=5)
    refeed = lib.feed(_TOPICS, sources=("web", "arxiv"), max_per=5)  # all dupes
    status = lib.status()
    return {"feed": feed, "refeed": refeed, "status": status}


def main() -> int:
    def _hdr(s: str) -> None:
        print("\n" + s + "\n" + "─" * min(len(s), 72))

    print("run_librarian.py — P4.3 Self-feeding internet (offline, deterministic)")
    print("LIVE mode uses ddgs (web) / arxiv (papers) / feedparser (RSS) / trafilatura "
          "(extract), and lib.schedule(topics, interval_minutes=60) for the always-on "
          "APScheduler loop. This demo injects offline stubs — no network.")

    demo = build_demo_librarian()
    feed, refeed, status = demo["feed"], demo["refeed"], demo["status"]

    _hdr("1. feed() — discover web+arxiv → extract (web) → dedup → brain.ingest_text")
    print(f"  topics={feed['topics']}")
    print(f"  found={feed['found']}  ingested={feed['ingested']}  "
          f"dupes={feed['dupes']}  by_source={feed['by_source']}")
    for it in feed["items"]:
        print(f"    + [{it['source']:<5}] {it['title']:<34} "
              f"doc_id={it['doc_id']} chars={it['chars']}")
    assert feed["ingested"] > 0, "first feed should ingest items"
    assert feed["by_source"].get("web", 0) and feed["by_source"].get("arxiv", 0), \
        "should ingest from BOTH web and arxiv"
    # web items get full-text extraction (longer than the short snippet teaser).
    web_items = [it for it in feed["items"] if it["source"] == "web"]
    assert all(it["chars"] > 40 for it in web_items), "web items must be full-text extracted"
    print("  ✔ ingested from both web (full-text extracted) and arxiv (abstracts) — verified.")

    _hdr("2. dedup — a 2nd feed() over the same topics ingests nothing")
    print(f"  refeed: found={refeed['found']}  ingested={refeed['ingested']}  "
          f"dupes={refeed['dupes']}")
    assert refeed["ingested"] == 0, "re-feeding the same topics must ingest 0 (dedup)"
    assert refeed["dupes"] == refeed["found"], "every re-discovered item must be a dupe"
    print("  ✔ re-feed ingested 0 — content+URL dedup works.")

    _hdr("3. status() — seen-set + counters + source backends")
    print(f"  {json.dumps(status, default=str)}")

    _hdr("4. build_demo_librarian() — JSON-able dashboard snapshot")
    print(json.dumps(demo, indent=2, default=str)[:800] + "  ...")

    print("\n✅ P4.3 self-feeding Librarian demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
