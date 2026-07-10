"""tests/test_news_ingest.py — free-RSS → symbol-linked brain news memory (2026-07-10)."""
from __future__ import annotations

import json

from trading.brain.news import NewsItem


def _fetcher(url, limit=20):
    return [
        NewsItem(title="Bitcoin surges past resistance as ETF inflows jump",
                 summary="BTC rallies", source="test", ts=1.0, url="http://x/1"),
        NewsItem(title="RELIANCE announces record quarterly results",
                 summary="strong earnings", source="test", ts=2.0, url="http://x/2"),
        NewsItem(title="Weather pleasant across the plains",
                 summary="", source="test", ts=3.0, url="http://x/3"),
    ]


def _seed_journal(tmp_path):
    rows = [{"symbol": "RELIANCE", "net_pnl": 1}, {"symbol": "BTC/USDT:USDT", "net_pnl": -1}]
    (tmp_path / "journal.json").write_text(json.dumps(rows))


def test_ingest_links_symbols_and_dedupes(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed_journal(tmp_path)
    from trading.brain import news_ingest
    out = news_ingest.ingest_once(fetcher=_fetcher, force=True)
    assert out["new"] == 3 and not out["errors"]
    store = tstate.load_json("news_memory.json", {})
    by_title = {r["title"]: r for r in store["items"]}
    assert "BTC/USDT" in by_title["Bitcoin surges past resistance as ETF inflows jump"]["symbols"]
    assert "RELIANCE" in by_title["RELIANCE announces record quarterly results"]["symbols"]
    assert by_title["Weather pleasant across the plains"]["symbols"] == []
    # second run: everything already seen
    out2 = news_ingest.ingest_once(fetcher=_fetcher, force=True)
    assert out2["new"] == 0


def test_items_for_symbol_lookup(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed_journal(tmp_path)
    from trading.brain import news_ingest
    news_ingest.ingest_once(fetcher=_fetcher, force=True)
    hits = news_ingest.items_for("BTC/USDT:USDT")
    assert len(hits) == 1 and "Bitcoin" in hits[0]["title"]


def test_min_gap_rate_limit(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed_journal(tmp_path)
    from trading.brain import news_ingest
    news_ingest.ingest_once(fetcher=_fetcher, force=True)
    out = news_ingest.ingest_once(fetcher=_fetcher)          # inside the 15-min gap
    assert out.get("skipped") is True


def test_dead_feed_never_kills_cycle(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed_journal(tmp_path)
    from trading.brain import news_ingest

    def bad(url, limit=20):
        raise ConnectionError("feed down")
    out = news_ingest.ingest_once(fetcher=bad, force=True)
    assert out["new"] == 0 and out["errors"]
