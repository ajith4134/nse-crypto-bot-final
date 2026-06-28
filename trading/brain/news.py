"""trading/brain/news.py — autonomous news research + sentiment nodes (T8.7).

The brain reads the world: fetch news/articles, score their tone (T8.7 sentiment), and
turn per-symbol news sentiment into a NodeProtocol feature the brain can ensemble + a
summary for Telegram (T7) / Stream-of-Mind.

Reuse-first / offline-first:
  • fetching — `feedparser` RSS (real) behind an INJECTED fetcher, so tests run on a stub
    list with no network; `autonomous_research()` is a gated GPT-Researcher hook (LLM)
    that degrades to a sentiment digest when not configured.
  • scoring — SentimentScorer (vendored VADER default, FinBERT optional).
  • NewsSentimentNode — maps a [-1,1] news compound to p(bullish), a real NodeProtocol node.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from core.node_protocol import BaseNode, IOSchema
from trading.brain.sentiment import SentimentScorer


@dataclass
class NewsItem:
    title: str
    summary: str = ""
    source: str = ""
    ts: float = 0.0
    url: str = ""
    symbols: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title}. {self.summary}".strip()


def fetch_rss(url: str, *, limit: int = 20) -> list[NewsItem]:
    """Fetch headlines from an RSS/Atom feed via feedparser (real network)."""
    try:
        import feedparser
    except Exception:  # pragma: no cover
        return []
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:limit]:
        out.append(NewsItem(title=getattr(e, "title", ""), summary=getattr(e, "summary", ""),
                            source=getattr(feed.feed, "title", url), url=getattr(e, "link", "")))
    return out


class NewsResearcher:
    """Fetch → score → aggregate per-symbol news sentiment; optional autonomous web research."""

    def __init__(self, scorer: SentimentScorer | None = None, fetcher=None):
        self.scorer = scorer or SentimentScorer()
        self.fetcher = fetcher                      # callable() -> list[NewsItem]; injected for tests

    def _items_for(self, symbol: str, items: list[NewsItem]) -> list[NewsItem]:
        # Word-boundary match (so 'ETH' doesn't match 'method'/'whether') OR an explicit
        # symbols tag. No whole-feed fallback: a symbol with no news → no articles → neutral,
        # rather than mis-attributing market-wide sentiment to it.
        s = symbol.lower()
        pat = re.compile(r"\b" + re.escape(s) + r"\b")
        return [it for it in items if pat.search(it.text.lower())
                or any(s == str(x).lower() for x in it.symbols)]

    def research(self, symbol: str, *, items: list[NewsItem] | None = None,
                 top: int = 5) -> dict:
        """Aggregate sentiment for `symbol` over `items` (or the injected fetcher's feed)."""
        if items is None:
            items = self.fetcher() if self.fetcher else []
        relevant = self._items_for(symbol, items)
        scored = [(it, self.scorer.score(it.text)) for it in relevant]
        comps = [sc["compound"] for _, sc in scored]
        avg = round(sum(comps) / len(comps), 4) if comps else 0.0
        pos = sum(1 for c in comps if c > 0.05)
        neg = sum(1 for c in comps if c < -0.05)
        headlines = sorted(scored, key=lambda x: abs(x[1]["compound"]), reverse=True)[:top]
        return {
            "symbol": symbol, "n_articles": len(relevant), "avg_compound": avg,
            "label": SentimentScorer._label(avg), "bullish": pos, "bearish": neg,
            "backend": self.scorer.active_backend,
            "top_headlines": [{"title": it.title, "compound": sc["compound"],
                               "source": it.source} for it, sc in headlines],
        }

    def autonomous_research(self, query: str) -> dict:
        """Gated GPT-Researcher hook: deep web research when configured, else a note."""
        if str(os.environ.get("GPT_RESEARCHER_ENABLED", "")).lower() in ("1", "true", "yes"):
            try:  # pragma: no cover - network/LLM
                from gpt_researcher import GPTResearcher  # type: ignore
                import asyncio
                gr = GPTResearcher(query=query, report_type="research_report")
                asyncio.get_event_loop().run_until_complete(gr.conduct_research())
                report = asyncio.get_event_loop().run_until_complete(gr.write_report())
                return {"available": True, "query": query, "report": report}
            except Exception as exc:
                return {"available": False, "query": query, "error": str(exc)[:120]}
        return {"available": False, "query": query,
                "note": "set GPT_RESEARCHER_ENABLED=1 + install gpt-researcher + an LLM key "
                        "to enable autonomous web research"}


class NewsSentimentNode(BaseNode):
    """NodeProtocol node: maps a [-1,1] news-sentiment compound → p(bullish)."""

    kind = "news_sentiment"

    def __init__(self, name: str = "news_sentiment"):
        self.name = name
        self.summary = "per-symbol news sentiment → p(bullish)"
        self.schema = IOSchema(1, "news compound sentiment [-1,1]", "p(bullish)")

    def fit(self, X, y=None) -> "NewsSentimentNode":
        return self

    def predict_proba(self, X):
        out = []
        for row in X:
            c = float(row[0]) if len(row) else 0.0
            out.append(min(1.0, max(0.0, (c + 1.0) / 2.0)))    # [-1,1] → [0,1]
        return out
