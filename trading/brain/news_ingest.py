"""trading/brain/news_ingest.py — scheduled FREE-news ingestion into the brain (2026-07-10).

Zero-cost knowledge gathering (owner rule zero-cost-first): public RSS feeds only, no
paid API, no key. Each ingest cycle (piggybacked on the learn loop, min 15-min gap):

    fetch feeds (trading/brain/news.fetch_rss — feedparser)
      → dedupe vs news_seen.json (url/title hash, capped)
      → VADER/FinBERT sentiment (trading/brain/sentiment.SentimentScorer)
      → symbol-entity linking against the LIVE tradable universe (journal symbols +
        index aliases), so items carry the symbols they talk about
      → newest items → news_memory.json (capped store the decision path and the
        NewsResearcher can read WITHOUT refetching), mind-event on strong items.

Feeds are env-overridable (NEWS_FEEDS="url1,url2"). All defaults are public, free RSS.
"""
from __future__ import annotations

import hashlib
import os
import re
import time

_SEEN_FILE = "news_seen.json"
_STORE_FILE = "news_memory.json"
_STORE_CAP = 500
_SEEN_CAP = 4000
_MIN_GAP_SEC = 900.0                      # at most one real fetch per 15 min

# public, free, no-key feeds — crypto + India markets (env-overridable)
DEFAULT_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.livemint.com/rss/markets",
]

# words that LOOK like symbols but aren't (avoid linking "IT stocks" → ITC etc.)
_STOP = {"THE", "AND", "FOR", "NSE", "BSE", "SEBI", "RBI", "IPO", "GDP", "USD", "INR",
         "ETF", "CEO", "CFO", "AI", "IT", "US", "UK", "EU", "Q1", "Q2", "Q3", "Q4",
         # tradable names that are also everyday English (false-link on first live run)
         "POWER", "GOLD", "SILVER", "IDEA", "TRUST", "PRIME", "FOCUS", "MOTHERSON"}
_ALIASES = {
    "BITCOIN": "BTC/USDT", "BTC": "BTC/USDT", "ETHEREUM": "ETH/USDT", "ETH": "ETH/USDT",
    "SOLANA": "SOL/USDT", "NIFTY": "NIFTY", "SENSEX": "SENSEX", "BANKNIFTY": "BANKNIFTY",
}


def _feeds() -> list[str]:
    env = os.getenv("NEWS_FEEDS", "").strip()
    return [u.strip() for u in env.split(",") if u.strip()] if env else list(DEFAULT_FEEDS)


def _universe() -> set[str]:
    """LIVE tradable names to link against: journal symbols, bare of venue suffixes."""
    from trading import state
    syms: set[str] = set()
    for r in (state.load_json("journal.json", []) or [])[-1500:]:
        if isinstance(r, dict) and r.get("symbol"):
            base = str(r["symbol"]).split("/")[0].split(":")[0]
            if 2 < len(base) <= 12 and base.upper() not in _STOP:
                syms.add(base.upper())
    return syms


def _link_symbols(text: str, universe: set[str]) -> list[str]:
    """Symbols mentioned in `text`. Aliases match case-insensitively (unambiguous words);
    universe tickers ≤4 chars must appear ALL-CAPS in the ORIGINAL text — short coin
    tickers are English words ("ROSE", "CAP") and matched 'rose'/'cap' as verbs on the
    first live run (2026-07-10). Longer tickers (RELIANCE, HDFCBANK) match any case."""
    raw_toks = set(re.findall(r"[A-Za-z]{2,15}", text))
    upper_toks = {t.upper() for t in raw_toks}
    caps_toks = {t for t in raw_toks if t.isupper()}          # written as a TICKER
    out = {_ALIASES[t] for t in upper_toks if t in _ALIASES}
    for sym in universe - _STOP:
        if len(sym) >= 5 and sym in upper_toks:
            out.add(sym)
        elif sym in caps_toks:
            out.add(sym)
    return sorted(out)[:6]


def _hash(item) -> str:
    return hashlib.sha1((item.url or item.title).encode()).hexdigest()[:16]


def ingest_once(fetcher=None, force: bool = False) -> dict:
    """One ingest cycle. `fetcher(url, limit)` injectable for tests (no network)."""
    from trading import state
    from trading.brain import news as _news
    from trading.brain.sentiment import SentimentScorer
    store = state.load_json(_STORE_FILE, {}) or {}
    last = float(store.get("last_fetch_ts") or 0)
    if not force and time.time() - last < _MIN_GAP_SEC:
        return {"skipped": True, "reason": f"fetched {time.time() - last:.0f}s ago"}
    fetch = fetcher or _news.fetch_rss
    seen = state.load_json(_SEEN_FILE, []) or []
    seen_set = set(seen)
    scorer = SentimentScorer()
    universe = _universe()
    items, errors = [], []
    for url in _feeds():
        try:
            items.extend(fetch(url, limit=20) or [])
        except Exception as e:                    # one dead feed never kills the cycle
            errors.append(f"{url}: {type(e).__name__}")
    fresh = []
    for it in items:
        h = _hash(it)
        if h in seen_set:
            continue
        seen_set.add(h)
        seen.append(h)
        try:
            compound = float(scorer.score(it.text).get("compound") or 0.0)
        except Exception:
            compound = 0.0
        fresh.append({"title": it.title[:200], "source": it.source or "",
                      "url": it.url, "ts": it.ts or time.time(),
                      "compound": round(compound, 4),
                      "symbols": _link_symbols(it.text, universe)})
    rows = (store.get("items") or []) + fresh
    store = {"items": rows[-_STORE_CAP:], "last_fetch_ts": time.time(),
             "n_feeds": len(_feeds()), "errors": errors}
    state.save_json(_STORE_FILE, store)
    state.save_json(_SEEN_FILE, seen[-_SEEN_CAP:])
    # strong stories reach the stream of mind (the brain "notices" the news)
    try:
        from trading.brain import mind_events
        for f in fresh:
            if abs(f["compound"]) >= 0.6 and f["symbols"]:
                mind_events.emit("news", f"{'📈' if f['compound'] > 0 else '📉'} "
                                 f"{','.join(f['symbols'])}: {f['title'][:120]}")
    except Exception:
        pass
    return {"fetched": len(items), "new": len(fresh), "errors": errors,
            "store_size": len(store["items"])}


def items_for(symbol: str, limit: int = 10) -> list[dict]:
    """Newest stored items linked to `symbol` (entry-time lookups, no refetch)."""
    from trading import state
    base = str(symbol).split("/")[0].split(":")[0].upper()
    rows = (state.load_json(_STORE_FILE, {}) or {}).get("items") or []
    hits = [r for r in rows if any(base in s.upper() for s in (r.get("symbols") or []))]
    return hits[-limit:]


def status() -> dict:
    from trading import state
    store = state.load_json(_STORE_FILE, {}) or {}
    rows = store.get("items") or []
    by_sym: dict[str, int] = {}
    for r in rows:
        for s in r.get("symbols") or []:
            by_sym[s] = by_sym.get(s, 0) + 1
    return {"live": True, "demo": False, "n_items": len(rows),
            "last_fetch_ts": store.get("last_fetch_ts"),
            "feeds": _feeds(), "errors": store.get("errors") or [],
            "top_symbols": sorted(by_sym.items(), key=lambda kv: -kv[1])[:12],
            "latest": rows[-8:]}
