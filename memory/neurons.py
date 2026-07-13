"""memory/neurons.py — the ONE common language: instruction-shaped Neurons (Brain Ultra Upgrade, Pillar 1).

Owner requirements R15/R16/R24 (research/brain-ultra-upgrade/OWNER_MESSAGE_VERBATIM.md):
ALL brain data — strategies, research, books, news, findings, inventions, knowledge,
memory, episodes, exams, lessons — becomes the SAME atomic unit (a Neuron) connected in
one graph (the "web of neurons"). The common language is INSTRUCTION-SHAPED: every
neuron, whatever its kind, carries a mandatory `action` facet — how to USE this
knowledge — so the web is simultaneously a knowledge graph and an executable
instruction library.

Design (A-MEM atomicity + Claude file-memory discipline + HippoRAG-ready graph):
- one markdown file per neuron under brain_memory/neurons/ (human-auditable),
- mirrored into SQLite with FTS5 (machine-fast search; tokenized fallback when the
  build lacks FTS5), links in a first-class table,
- RAM cache of every neuron (motto: RAM for speed),
- auto-linking on add via token-jaccard against recent neighbours (deterministic,
  no-LLM path — the LLM enrichment lives in memory/associative.py which callers may
  also feed; see memory/neuron_web.py converters).

Instructions evolve: `derive()` creates a child neuron with `parents` lineage +
`mutated-from` links (GEPA-style genetic tree, R26 operators live in
trading/brain/instructions.py). Usage/exam evidence lands via `record_use` /
`record_exam` and drives `confidence`. `growth()` answers R28 (accumulation must be
measurable). No fake data anywhere: everything reported comes from the store itself.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "brain_memory" / "neurons"

KINDS = ("fact", "concept", "instruction", "skill", "strategy", "finding",
         "invention", "episode", "source", "news", "book-chapter", "exam", "lesson")
LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6")
RELS = ("supports", "contradicts", "uses", "derived-from", "mutated-from",
        "crossover-of", "taught-by", "tested-by", "related")

_WORD = re.compile(r"[a-z0-9]{3,}")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(str(text).lower()))


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _nid() -> str:
    return "n-" + uuid.uuid4().hex[:12]


@dataclass
class Neuron:
    """One atomic unit of brain knowledge, always instruction-shaped (R24)."""
    id: str
    kind: str
    title: str
    body: str
    action: str                     # mandatory: how to USE this knowledge
    level: str = "L1"
    links: list = field(default_factory=list)       # [{"to": id, "rel": rel}]
    origin: str = ""                # provenance: url|book|trade|experiment|lesson|store
    ref: str = ""                   # provenance pointer (url, file, trade id…)
    confidence: float = 0.5
    stats: dict = field(default_factory=lambda: {
        "times_used": 0, "wins": 0, "losses": 0, "pnl": 0.0, "last_used": 0.0})
    exam: dict = field(default_factory=lambda: {"last_score": None, "last_tested": 0.0})
    version: int = 1
    parents: list = field(default_factory=list)
    created: float = 0.0
    updated: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "title": self.title, "body": self.body,
            "action": self.action, "level": self.level, "links": list(self.links),
            "origin": self.origin, "ref": self.ref, "confidence": self.confidence,
            "stats": dict(self.stats), "exam": dict(self.exam), "version": self.version,
            "parents": list(self.parents), "created": self.created, "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Neuron":
        known = {f for f in cls.__dataclass_fields__}          # tolerate future fields
        return cls(**{k: v for k, v in d.items() if k in known})


class NeuronStore:
    """File + SQLite(FTS5) + RAM store of the whole web of neurons."""

    def __init__(self, root: str | Path | None = None, *, auto_link_k: int = 4,
                 auto_link_min: float = 0.18):
        self.root = Path(root) if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self.auto_link_k = auto_link_k
        self.auto_link_min = auto_link_min
        self._lock = threading.RLock()
        self._cache: dict[str, Neuron] = {}
        self._word_cache: dict[str, set[str]] = {}
        self._db = sqlite3.connect(str(self.root / "neurons.db"),
                                   check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._fts = self._init_schema()
        self._rehydrate()

    # ── schema / load ─────────────────────────────────────────────────────────
    def _init_schema(self) -> bool:
        c = self._db
        c.execute("""CREATE TABLE IF NOT EXISTS neurons(
            id TEXT PRIMARY KEY, kind TEXT, title TEXT, level TEXT,
            confidence REAL, created REAL, updated REAL, json TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS links(
            src TEXT, dst TEXT, rel TEXT, created REAL,
            UNIQUE(src, dst, rel))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_links_src ON links(src)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_links_dst ON links(dst)")
        try:
            c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS neurons_fts
                USING fts5(id UNINDEXED, title, body, action)""")
            c.commit()
            return True
        except sqlite3.OperationalError:            # sqlite built without FTS5
            c.commit()
            return False

    def _rehydrate(self) -> None:
        with self._lock:
            for (js,) in self._db.execute("SELECT json FROM neurons"):
                try:
                    n = Neuron.from_dict(json.loads(js))
                    self._cache[n.id] = n
                    self._word_cache[n.id] = _words(f"{n.title} {n.body} {n.action}")
                except Exception:
                    continue                        # one bad row never kills the store

    # ── write path ────────────────────────────────────────────────────────────
    def add(self, kind: str, title: str, body: str, action: str, *,
            level: str = "L1", origin: str = "", ref: str = "",
            confidence: float = 0.5, links: list | None = None,
            parents: list | None = None, version: int = 1,
            nid: str | None = None, now: float | None = None,
            auto_link: bool = True) -> Neuron:
        """Create (or overwrite by explicit nid) one neuron. `action` is MANDATORY (R24)."""
        if kind not in KINDS:
            raise ValueError(f"unknown neuron kind {kind!r}; must be one of {KINDS}")
        action = str(action or "").strip()
        if not action:
            raise ValueError("neuron rejected: empty `action` facet — every neuron "
                             "must say how to USE it (owner requirement R24)")
        title = str(title or "").strip()[:300]
        body = str(body or "").strip()
        if not title or not body:
            raise ValueError("neuron rejected: title and body are required")
        if level not in LEVELS:
            level = "L1"
        ts = time.time() if now is None else float(now)
        n = Neuron(id=nid or _nid(), kind=kind, title=title, body=body, action=action,
                   level=level, origin=str(origin), ref=str(ref),
                   confidence=max(0.0, min(1.0, float(confidence))),
                   parents=list(parents or []), version=int(version),
                   created=ts, updated=ts)
        with self._lock:
            old = self._cache.get(n.id)
            if old is not None:
                # update-in-place (deterministic-id upsert): accumulated EVIDENCE is
                # never wiped by a content refresh — stats/exam/links/created survive
                # (R28: recorded exam scores and usage history must not be erased)
                n.stats = old.stats
                n.exam = old.exam
                n.links = old.links
                n.created = old.created
                n.confidence = old.confidence if (old.stats.get("wins", 0)
                                                  + old.stats.get("losses", 0)) else n.confidence
            self._persist(n)
            for lk in (links or []):
                if isinstance(lk, dict) and lk.get("to"):
                    self.link(n.id, lk["to"], lk.get("rel", "related"), now=ts)
            for pid in n.parents:
                self.link(n.id, pid, "mutated-from", now=ts)
            if auto_link:
                self._auto_link(n, now=ts)
        return n

    def _persist(self, n: Neuron) -> None:
        self._cache[n.id] = n
        self._word_cache[n.id] = _words(f"{n.title} {n.body} {n.action}")
        self._db.execute(
            "INSERT OR REPLACE INTO neurons(id,kind,title,level,confidence,created,updated,json)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (n.id, n.kind, n.title, n.level, n.confidence, n.created, n.updated,
             json.dumps(n.to_dict())))
        if self._fts:
            self._db.execute("DELETE FROM neurons_fts WHERE id=?", (n.id,))
            self._db.execute("INSERT INTO neurons_fts(id,title,body,action) VALUES(?,?,?,?)",
                             (n.id, n.title, n.body, n.action))
        self._db.commit()
        self._write_file(n)

    def _write_file(self, n: Neuron) -> None:
        """Human-auditable markdown twin (atomic tmp+rename)."""
        links = "; ".join(f"{l['to']}|{l['rel']}" for l in n.links)
        text = (f"---\nid: {n.id}\nkind: {n.kind}\ntitle: {n.title}\nlevel: {n.level}\n"
                f"origin: {n.origin}\nref: {n.ref}\nconfidence: {n.confidence:.3f}\n"
                f"version: {n.version}\nparents: {','.join(n.parents)}\n"
                f"links: {links}\ncreated: {n.created:.0f}\nupdated: {n.updated:.0f}\n---\n\n"
                f"{n.body}\n\n## How to use (action facet)\n\n{n.action}\n")
        path = self.root / f"{n.id}.md"
        tmp = path.with_suffix(".md.tmp")
        try:
            tmp.write_text(text)
            os.replace(tmp, path)
        except OSError:
            pass                                    # DB row is the source of truth

    # ── links / web ───────────────────────────────────────────────────────────
    def link(self, src: str, dst: str, rel: str = "related", *,
             now: float | None = None) -> bool:
        """Returns True only when a NEW edge was created (duplicates return False)."""
        if rel not in RELS:
            rel = "related"
        if src == dst:
            return False
        ts = time.time() if now is None else float(now)
        with self._lock:                              # membership check under the lock
            if src not in self._cache or dst not in self._cache:
                return False
            n = self._cache[src]
            if any(l["to"] == dst and l["rel"] == rel for l in n.links):
                return False                          # duplicate — honest count for weave
            self._db.execute(
                "INSERT OR IGNORE INTO links(src,dst,rel,created) VALUES(?,?,?,?)",
                (src, dst, rel, ts))
            n.links.append({"to": dst, "rel": rel})
            n.updated = ts
            self._persist(n)
        return True

    def _auto_link(self, n: Neuron, *, now: float) -> None:
        """Deterministic A-MEM-style neighbour linking (no LLM, no network).

        Score = max(full-text jaccard, title-token jaccard): titles are dense with
        the entity ("RSI", "Binance") so two notes about the same thing connect even
        when their bodies barely overlap.
        """
        me = self._word_cache.get(n.id, set())
        me_t = _words(n.title)
        scored = []
        for oid, words in self._word_cache.items():
            if oid == n.id:
                continue
            other = self._cache.get(oid)
            s = max(_jaccard(me, words),
                    _jaccard(me_t, _words(other.title)) if other else 0.0)
            if s >= self.auto_link_min:
                scored.append((s, oid))
        scored.sort(reverse=True)
        for _, oid in scored[: self.auto_link_k]:
            self.link(n.id, oid, "related", now=now)

    def neighbors(self, nid: str, *, limit: int = 20) -> list[dict]:
        with self._lock:                              # cursor + cache read serialized
            rows = self._db.execute(
                "SELECT src,dst,rel FROM links WHERE src=? OR dst=? LIMIT ?",
                (nid, nid, int(limit))).fetchall()
            out = []
            for src, dst, rel in rows:
                other = dst if src == nid else src
                n = self._cache.get(other)
                if n:
                    out.append({"id": other, "title": n.title, "kind": n.kind,
                                "rel": rel})
        return out

    def all_neurons(self) -> list[Neuron]:
        """Thread-safe snapshot of the cache for iteration by readers."""
        with self._lock:
            return list(self._cache.values())

    # ── read / search ─────────────────────────────────────────────────────────
    def get(self, nid: str) -> Neuron | None:
        return self._cache.get(nid)

    def search(self, query: str, k: int = 8, *, kind: str | None = None) -> list[dict]:
        """FTS5 (bm25) search with tokenized fallback; returns dicts w/ score."""
        query = str(query or "").strip()
        if not query:
            return []
        hits: list[tuple[float, str]] = []
        with self._lock:
            if self._fts:
                try:
                    q = " OR ".join(_WORD.findall(query.lower())) or query
                    hits = [(-float(rank), nid) for nid, rank in self._db.execute(
                            "SELECT id, bm25(neurons_fts) FROM neurons_fts "
                            "WHERE neurons_fts MATCH ? ORDER BY bm25(neurons_fts) LIMIT ?",
                            (q, int(k) * 3)).fetchall()]
                except sqlite3.OperationalError:
                    hits = []
            if not hits:                            # fallback: jaccard scan in RAM
                qw = _words(query)
                hits = [(s, oid) for oid, w in self._word_cache.items()
                        if (s := _jaccard(qw, w)) > 0]
                hits.sort(reverse=True)
        out = []
        for score, nid in hits:
            n = self._cache.get(nid)
            if not n or (kind and n.kind != kind):
                continue
            d = n.to_dict()
            d["score"] = round(float(score), 4)
            out.append(d)
            if len(out) >= k:
                break
        return out

    # ── evidence: usage + exams drive confidence (R4/R22) ─────────────────────
    def record_use(self, nid: str, *, win: bool | None = None, pnl: float = 0.0,
                   domain: str = "", now: float | None = None,
                   count_use: bool = True) -> Neuron | None:
        """count_use=False records OUTCOME evidence only (the grade-at-close path) —
        the use event was already counted when the neuron was consulted."""
        n = self._cache.get(nid)
        if not n:
            return None
        ts = time.time() if now is None else float(now)
        with self._lock:
            if count_use:
                n.stats["times_used"] = int(n.stats.get("times_used", 0)) + 1
            n.stats["last_used"] = ts
            n.stats["pnl"] = float(n.stats.get("pnl", 0.0)) + float(pnl)
            if win is True:
                n.stats["wins"] = int(n.stats.get("wins", 0)) + 1
            elif win is False:
                n.stats["losses"] = int(n.stats.get("losses", 0)) + 1
            w, l = n.stats.get("wins", 0), n.stats.get("losses", 0)
            if w + l:                                # Laplace-smoothed win-rate belief
                n.confidence = round((w + 1) / (w + l + 2), 4)
            if domain:
                by = n.stats.setdefault("by_domain", {})
                d = by.get(domain)
                if not isinstance(d, dict):           # migrate old int format in place
                    d = {"uses": int(d or 0), "wins": 0, "losses": 0}
                if count_use:
                    d["uses"] += 1
                if win is True:
                    d["wins"] += 1
                elif win is False:
                    d["losses"] += 1
                by[domain] = d                        # per-domain outcomes (R22 honest)
            n.updated = ts
            self._persist(n)
        return n

    def record_exam(self, nid: str, score: float, *, now: float | None = None) -> Neuron | None:
        n = self._cache.get(nid)
        if not n:
            return None
        ts = time.time() if now is None else float(now)
        with self._lock:
            n.exam["last_score"] = round(float(score), 4)
            n.exam["last_tested"] = ts
            n.updated = ts
            self._persist(n)
        return n

    # ── evolution lineage (R26 operators call this; see trading/brain/instructions) ──
    def derive(self, parent_ids: list[str], *, title: str, body: str, action: str,
               kind: str | None = None, rel: str = "mutated-from",
               now: float | None = None) -> Neuron:
        parents = [p for p in parent_ids if p in self._cache]
        if not parents:
            raise ValueError("derive() needs at least one existing parent neuron")
        base = self._cache[parents[0]]
        child = self.add(kind or base.kind, title, body, action, level=base.level,
                         origin="evolution", ref=",".join(parents),
                         confidence=base.confidence, parents=parents,
                         version=max(self._cache[p].version for p in parents) + 1,
                         now=now, auto_link=False)
        for p in parents[1:] if rel == "crossover-of" else []:
            self.link(child.id, p, "crossover-of", now=now)
        return child

    def lineage(self, nid: str, *, depth: int = 6) -> list[dict]:
        out, seen, frontier = [], set(), [nid]
        for _ in range(depth):
            nxt = []
            for cur in frontier:
                n = self._cache.get(cur)
                if not n or cur in seen:
                    continue
                seen.add(cur)
                out.append({"id": n.id, "title": n.title, "version": n.version,
                            "confidence": n.confidence, "parents": list(n.parents)})
                nxt.extend(n.parents)
            frontier = nxt
        return out

    # ── observability: honest numbers only (R28, dashboard) ──────────────────
    def growth(self, *, buckets: int = 30, bucket_secs: float = 86400.0,
               now: float | None = None) -> list[dict]:
        """Accumulation time-series: neurons + links created per bucket (R28)."""
        ts = time.time() if now is None else float(now)
        start = ts - buckets * bucket_secs
        series = [{"t": start + i * bucket_secs, "neurons": 0, "links": 0}
                  for i in range(buckets)]
        with self._lock:
            n_rows = self._db.execute(
                "SELECT created FROM neurons WHERE created>=?", (start,)).fetchall()
            l_rows = self._db.execute(
                "SELECT created FROM links WHERE created>=?", (start,)).fetchall()
        for (created,) in n_rows:
            i = min(buckets - 1, max(0, int((created - start) // bucket_secs)))
            series[i]["neurons"] += 1
        for (created,) in l_rows:
            i = min(buckets - 1, max(0, int((created - start) // bucket_secs)))
            series[i]["links"] += 1
        return series

    def snapshot_graph(self, *, limit: int = 400) -> dict:
        """Nodes+edges for the dashboard neuron-web viz (most-connected first)."""
        with self._lock:
            link_rows = self._db.execute("SELECT src,dst,rel FROM links").fetchall()
            neurons = list(self._cache.values())
            total = len(self._cache)
        deg: dict[str, int] = {}
        for src, dst, _ in link_rows:
            deg[src] = deg.get(src, 0) + 1
            deg[dst] = deg.get(dst, 0) + 1
        ranked = sorted(neurons,
                        key=lambda n: (deg.get(n.id, 0), n.updated), reverse=True)[:limit]
        keep = {n.id for n in ranked}
        nodes = [{"id": n.id, "label": n.title[:60], "kind": n.kind, "level": n.level,
                  "confidence": n.confidence, "degree": deg.get(n.id, 0)} for n in ranked]
        edges = [{"src": s, "dst": d, "rel": r} for s, d, r in link_rows
                 if s in keep and d in keep]
        return {"nodes": nodes, "edges": edges,
                "total_neurons": total, "total_links": len(link_rows)}

    def status(self) -> dict:
        by_kind: dict[str, int] = {}
        by_level: dict[str, int] = {}
        with_action = 0
        with self._lock:
            neurons = list(self._cache.values())
            n_links = self._db.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        for n in neurons:
            by_kind[n.kind] = by_kind.get(n.kind, 0) + 1
            by_level[n.level] = by_level.get(n.level, 0) + 1
            if n.action.strip():
                with_action += 1
        total = len(neurons)
        return {"neurons": total, "by_kind": by_kind, "by_level": by_level,
                "links": n_links,
                "action_coverage": round(with_action / total, 4) if total else 1.0,
                "fts5": self._fts, "root": str(self.root)}


_STORE: NeuronStore | None = None
_STORE_LOCK = threading.Lock()


def get_store(root: str | Path | None = None) -> NeuronStore:
    """Process-wide singleton (same discipline as trading.brain.get_brain)."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None or (root and Path(root) != _STORE.root):
            _STORE = NeuronStore(root)
        return _STORE
