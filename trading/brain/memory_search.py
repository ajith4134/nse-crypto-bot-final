"""trading/brain/memory_search.py — cross-session FULL-TEXT search over the brain's whole memory.

Hermes-Agent-inspired (research/hermes-agent.md): a self-hosted agent's edge is that it can
RECALL everything it has ever learned. We already have semantic/associative memory (HippoRAG /
A-MEM) and FinMem episodic recall (`decision_memory.recall`, token-overlap over episodes only).
This adds the missing lens: **keyword full-text search, BM25-ranked, across EVERY memory corpus at
once** — associative notes, decision episodes, reflexion lessons, the mind-stream, the learning
log, the agent's own markdown memory files, and per-skill learnings (see `tools/skill_learnings`).

Reuse-first + CPU-first + zero new dep: built on **sqlite FTS5** (the proven full-text engine that
ships inside Python's stdlib `sqlite3`), with BM25 ranking + `snippet()` highlights. The index is a
single file under the state dir; it rebuilds from the source JSON/MD when they change (mtime-gated),
so search is always over the real, current memory — never a stale or fabricated copy.

Honest by construction: every hit is a real stored record (source + ref + timestamp preserved);
an empty corpus yields an empty result, never a made-up one.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from trading import state

_DB_NAME = "memory_index.db"
_MAX_TEXT = 4000                       # cap per-record indexed text (keep the index lean)

# The memory corpora: (source label, state filename, extractor). Each extractor yields
# (ref, ts, title, text) tuples from that file's parsed JSON. Missing files are skipped honestly.
def _rows_associative(d):
    for n in (d.get("notes") or []):
        txt = " ".join(str(n.get(k, "")) for k in ("content", "context"))
        kw = " ".join(n.get("keywords") or []) + " " + " ".join(n.get("tags") or [])
        yield (str(n.get("id", "")), n.get("created"), n.get("title", ""), f"{txt} {kw}")


def _rows_episodes(d):
    for e in (d.get("episodes") or []):
        dec = e.get("decision") or {}
        title = f"{e.get('symbol', '')} {e.get('direction', '')} {e.get('engine', '')}".strip()
        txt = " ".join(str(x) for x in (
            e.get("reflection", ""), dec.get("rationale", "") if isinstance(dec, dict) else dec,
            e.get("attribution", ""), e.get("segment", ""), e.get("market", "")))
        yield (str(e.get("episode_id", "")), e.get("ts") or e.get("opened_at"), title, txt)


def _rows_reflections(d):
    for r in (d.get("lessons") or []):
        yield (str(r.get("task", "")), r.get("ts"),
               r.get("lesson", ""), f"{r.get('lesson', '')} {r.get('detail', '')} {r.get('outcome', '')}")


def _rows_mind(d):
    for ev in (d.get("events") or []):
        yield (str(ev.get("id", "")), ev.get("ts"), ev.get("kind", ""),
               f"{ev.get('text', '')} {ev.get('detail', '')}")


def _rows_learnlog(d):
    for l in (d.get("learned") or []):
        yield (str(l.get("title", "")), l.get("ts"), l.get("title", ""),
               f"{l.get('title', '')} {l.get('kind', '')} {l.get('source', '')}")


_CORPORA = [
    ("associative", "associative_notes.json", _rows_associative),
    ("episode", "decision_episodes.json", _rows_episodes),
    ("reflection", "gui_reflections.json", _rows_reflections),
    ("mind", "mind_events.json", _rows_mind),
    ("learning_log", "learning_log.json", _rows_learnlog),
]

# The agent's own markdown memory (project auto-memory) + per-skill learnings live outside state/.
_MEMORY_MD_DIR = Path(
    os.environ.get("CLAUDE_MEMORY_DIR",
                   str(Path.home() / ".claude/projects/-home-karan18190164/memory")))
_SKILLS_DIR = Path(os.environ.get("CLAUDE_SKILLS_DIR",
                                  str(Path.home() / ".claude/skills")))


def _md_sources():
    """Extra text sources: agent memory *.md and per-skill LEARNINGS.md. (source, ref, mtime, text)."""
    out = []
    if _MEMORY_MD_DIR.is_dir():
        for p in sorted(_MEMORY_MD_DIR.glob("*.md")):
            try:
                out.append(("memory_md", p.stem, p.stat().st_mtime, p.read_text()[:_MAX_TEXT]))
            except OSError:
                continue
    if _SKILLS_DIR.is_dir():
        for p in sorted(_SKILLS_DIR.glob("*/LEARNINGS.md")):
            try:
                out.append(("skill_learning", p.parent.name, p.stat().st_mtime,
                            p.read_text()[:_MAX_TEXT]))
            except OSError:
                continue
    return out


def _corpus_mtime() -> float:
    """Newest mtime across every indexed source — the freshness key for the mtime-gated rebuild."""
    m = 0.0
    for _, fname, _ in _CORPORA:
        p = state._path(fname)
        if p.exists():
            m = max(m, p.stat().st_mtime)
    for _, _, mt, _ in _md_sources():
        m = max(m, mt)
    return m


class MemorySearch:
    """FTS5 full-text index over the whole brain memory. Rebuilds when the corpus changes."""

    def __init__(self):
        self._built_for: float = -1.0

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(state._path(_DB_NAME)))
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS mem USING fts5("
                    "source, ref, ts UNINDEXED, title, text, tokenize='porter unicode61')")
        return con

    def reindex(self, force: bool = False) -> dict:
        """(Re)build the index from the current memory files. mtime-gated: a no-op if nothing
        changed since the last build (unless force). Returns {indexed, sources, took_s}."""
        newest = _corpus_mtime()
        if not force and newest <= self._built_for and state._path(_DB_NAME).exists():
            return {"indexed": self.count(), "sources": self._source_counts(), "reused": True}
        t0 = time.time()
        con = self._connect()
        con.execute("DELETE FROM mem")
        n = 0
        for source, fname, extractor in _CORPORA:
            p = state._path(fname)
            if not p.exists():
                continue
            try:
                d = json.loads(p.read_text() or "{}")
            except (ValueError, OSError):
                continue
            for ref, ts, title, text in extractor(d):
                text = (text or "").strip()
                if not text:
                    continue
                con.execute("INSERT INTO mem(source, ref, ts, title, text) VALUES(?,?,?,?,?)",
                            (source, ref, float(ts) if isinstance(ts, (int, float)) else 0.0,
                             (title or "")[:200], text[:_MAX_TEXT]))
                n += 1
        for source, ref, mt, text in _md_sources():
            if text.strip():
                con.execute("INSERT INTO mem(source, ref, ts, title, text) VALUES(?,?,?,?,?)",
                            (source, ref, mt, ref[:200], text[:_MAX_TEXT]))
                n += 1
        con.commit()
        con.close()
        self._built_for = newest
        return {"indexed": n, "sources": self._source_counts(), "took_s": round(time.time() - t0, 3),
                "reused": False}

    def search(self, query: str, k: int = 10, sources: list[str] | None = None) -> list[dict]:
        """BM25-ranked full-text hits across the memory. Each hit: {source, ref, ts, title,
        snippet, score}. Honest empty list on no match / empty query."""
        query = (query or "").strip()
        if not query:
            return []
        self.reindex()
        con = self._connect()
        # sanitize into an FTS5 OR-query of quoted terms so punctuation can't break the parse
        terms = [t for t in "".join(c if c.isalnum() else " " for c in query).split() if t]
        if not terms:
            con.close()
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        sql = ("SELECT source, ref, ts, title, "
               "snippet(mem, 4, '[', ']', ' … ', 12) AS snip, bm25(mem) AS score "
               "FROM mem WHERE mem MATCH ?")
        params: list = [match]
        if sources:
            sql += " AND source IN (%s)" % ",".join("?" * len(sources))
            params += list(sources)
        # over-fetch so post-dedup we can still return k (some corpora log the same row repeatedly)
        sql += " ORDER BY score LIMIT ?"                      # bm25: lower is better
        params.append(int(k) * 4)
        try:
            rows = con.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            rows = []
        con.close()
        out, seen = [], set()
        for s, r, ts, ti, snip, sc in rows:
            key = (s, r)                                      # collapse duplicate source rows
            if key in seen:
                continue
            seen.add(key)
            out.append({"source": s, "ref": r, "ts": ts, "title": ti,
                        "snippet": snip, "score": round(-sc, 3)})
            if len(out) >= k:
                break
        return out

    def count(self) -> int:
        con = self._connect()
        try:
            n = con.execute("SELECT count(*) FROM mem").fetchone()[0]
        finally:
            con.close()
        return int(n)

    def _source_counts(self) -> dict:
        con = self._connect()
        try:
            rows = con.execute("SELECT source, count(*) FROM mem GROUP BY source").fetchall()
        finally:
            con.close()
        return {s: c for s, c in rows}

    def status(self) -> dict:
        self.reindex()
        return {"total": self.count(), "by_source": self._source_counts(),
                "db": str(state._path(_DB_NAME))}


_SEARCH: MemorySearch | None = None


def get_search() -> MemorySearch:
    global _SEARCH
    if _SEARCH is None:
        _SEARCH = MemorySearch()
    return _SEARCH
