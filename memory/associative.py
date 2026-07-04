"""memory/associative.py — associative "connect-the-dots" memory (brain ultra-upgrade, Phase A).

Stitches TWO real projects (vendored; see vendor/README.md) over our KnowledgeGraph:

  1. HippoRAG (vendor/hipporag, OSU-NLP @ef2f14c) — hippocampal-index retrieval: facts become
     entity nodes + relation edges in a knowledge graph; a query seeds Personalized PageRank
     at its entities, and activation SPREADS to associated old memories — multi-hop recall of
     a past topic when a related one is being read. We reuse the exact retrieve→seed→PPR→rank
     flow (HippoRAG.py: add_fact_edges / retrieve / run_ppr) but run PPR through OUR
     memory/graph.py `personalized_ranks` (NetworkX prpack-equivalent; stdlib fallback works).
  2. A-MEM (vendor/a_mem, agiresearch @ceffb86) — Zettelkasten agentic notes: every memory is
     analyzed into keywords/context/tags (analyze_content prompt), auto-LINKS to its nearest
     neighbours, and new knowledge triggers EVOLUTION of older linked notes (evolution prompt:
     strengthen / update_neighbor). Prompts are taken from memory_system.py verbatim in spirit;
     the LLM is our core.llm 12-provider failover instead of A-MEM's LLMController.

Offline-safe + deterministic (project pattern, same as semantic.py / hybrid_memory.py):
LLM reachable → real extraction/evolution; otherwise a functional heuristic path (keyword
entities, similarity linking) so every capability works and is testable with no network.
Notes persist to a JSON file when `path` is given. No secrets logged.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

from memory.graph import KnowledgeGraph

_STOP = frozenset(
    "the a an and or but if then else for while of to in on at by with from as is are was "
    "were be been being it its this that these those i you he she we they them his her our "
    "your their not no yes do does did done can could should would will shall may might must "
    "have has had having there here when where which who whom what why how all any both each "
    "few more most other some such only own same so than too very just also into over under "
    "again once during before after above below up down out off about against between".split())

# A-MEM analyze_content prompt (vendor/a_mem/agentic_memory/memory_system.py), condensed.
_ANALYZE_PROMPT = (
    "Generate a structured analysis of the content: identify salient keywords (nouns/verbs/"
    "key concepts, most important first), one context sentence (topic, key points, purpose), "
    "and broad categorical tags. Reply ONLY JSON: "
    '{"keywords": ["..."], "context": "...", "tags": ["..."]}')

# HippoRAG OpenIE triple extraction, condensed to a single JSON call.
_TRIPLES_PROMPT = (
    "Extract factual (subject, relation, object) triples from the text. Keep entities short "
    'noun phrases. Reply ONLY JSON: {"triples": [["subject","relation","object"], ...]}')

# A-MEM evolution prompt (memory_system.py _evolution_system_prompt), condensed.
_EVOLVE_PROMPT = (
    "You are a memory-evolution agent. Given a NEW memory note (context, content, keywords) "
    "and its nearest-neighbour notes, decide whether to evolve the memory network. Reply ONLY "
    'JSON: {"should_evolve": true|false, "actions": ["strengthen"|"update_neighbor"], '
    '"suggested_connections": [neighbor indices, 0-based], "tags_to_update": ["..."], '
    '"new_tags_neighborhood": [["..."], ...]}')


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9_\-]{2,}", str(text).lower()) if w not in _STOP]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _parse_json(reply: str | None) -> dict | None:
    if not reply:
        return None
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except Exception:
        return None


@dataclass
class Note:
    """A-MEM MemoryNote, adapted: one unit of memory with semantic metadata + links."""
    content: str
    title: str = ""
    id: str = ""
    keywords: list = field(default_factory=list)
    context: str = "General"
    tags: list = field(default_factory=list)
    links: list = field(default_factory=list)          # ids of associated notes
    retrieval_count: int = 0
    evolution_history: list = field(default_factory=list)
    created: float = 0.0

    def __post_init__(self):
        self.id = self.id or uuid.uuid4().hex[:12]


class AssociativeMemory:
    """HippoRAG associative recall + A-MEM note linking/evolution over KnowledgeGraph.

    add(text)  → analyze (A-MEM) + triples (HippoRAG) → graph + note store → evolve neighbours
    recall(q)  → query entities seed Personalized PageRank → activation spreads to old notes
    """

    def __init__(self, llm_chat=None, path: str | Path | None = None,
                 link_threshold: float = 0.18, evolve_k: int = 4):
        self.graph = KnowledgeGraph()
        self.notes: dict[str, Note] = {}
        self.llm_chat = llm_chat            # callable(messages)->str | None (core.llm injected)
        self.link_threshold = link_threshold
        self.evolve_k = evolve_k
        self.path = Path(path) if path else None
        self._llm_used = False
        if self.path and self.path.exists():
            self._load()

    # ── LLM plumbing (injected; offline → heuristic path) ────────────────────────
    def _chat(self, system: str, user: str) -> str | None:
        if self.llm_chat is None:
            return None
        try:
            reply = self.llm_chat([{"role": "system", "content": system},
                                   {"role": "user", "content": user[:2000]}])
            self._llm_used = reply is not None
            return reply
        except Exception:
            return None

    # ── A-MEM analyze_content: keywords / context / tags ─────────────────────────
    def _analyze(self, text: str) -> dict:
        data = _parse_json(self._chat(_ANALYZE_PROMPT, text))
        if data and data.get("keywords"):
            return {"keywords": [str(k).lower() for k in data.get("keywords", [])][:12],
                    "context": str(data.get("context", "General"))[:200],
                    "tags": [str(t).lower() for t in data.get("tags", [])][:8]}
        freq: dict[str, int] = {}
        for w in _words(text):
            freq[w] = freq.get(w, 0) + 1
        kws = [w for w, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))][:10]
        return {"keywords": kws, "context": " ".join(str(text).split()[:18]), "tags": kws[:3]}

    # ── HippoRAG OpenIE: (subject, relation, object) triples ─────────────────────
    def _triples(self, text: str, keywords: list[str]) -> list[tuple[str, str, str]]:
        data = _parse_json(self._chat(_TRIPLES_PROMPT, text))
        out = []
        for t in (data or {}).get("triples", []):
            if isinstance(t, (list, tuple)) and len(t) == 3:
                out.append(tuple(str(x).lower().strip()[:60] for x in t))
        if out:
            return out[:20]
        # heuristic fallback: co-occurring keywords become co_occurs relations (HippoRAG's
        # synonymy/co-occurrence edges approximation; keeps the graph connected offline)
        return [(keywords[i], "co_occurs", keywords[i + 1])
                for i in range(min(len(keywords), 6) - 1)]

    # ── write path: note + graph + A-MEM evolution ───────────────────────────────
    def add(self, text: str, title: str = "", now: float = 0.0, meta: dict | None = None) -> dict:
        info = self._analyze(text)
        note = Note(content=str(text), title=title or (info["context"][:60]),
                    keywords=info["keywords"], context=info["context"],
                    tags=info["tags"], created=now)
        nid = f"note:{note.id}"
        self.graph.add_node(nid, "note", note.title[:80])
        triples = self._triples(text, note.keywords)
        for s, r, o in triples:
            for ent in (s, o):
                self.graph.add_node(f"ent:{ent}", "entity", ent)
                self.graph.add_edge(nid, f"ent:{ent}", "about")
            self.graph.add_edge(f"ent:{s}", f"ent:{o}", r)
        for kw in note.keywords:                       # entity index for query seeding
            self.graph.add_node(f"ent:{kw}", "entity", kw)
            self.graph.add_edge(nid, f"ent:{kw}", "about")
        evolved = self._evolve(note)
        self.notes[note.id] = note
        self._save()
        return {"id": note.id, "title": note.title, "keywords": note.keywords,
                "links": note.links, "evolved": evolved, "triples": len(triples),
                "llm": self._llm_used}

    def _neighbours(self, note: Note, k: int) -> list[tuple[float, Note]]:
        base = set(note.keywords) | set(_words(note.content))
        scored = []
        for other in self.notes.values():
            if other.id == note.id:
                continue
            sim = _jaccard(base, set(other.keywords) | set(_words(other.content)))
            if sim > 0:
                scored.append((sim, other))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]

    def _evolve(self, note: Note) -> dict:
        """A-MEM memory evolution: link the new note + let it UPDATE older neighbours."""
        nbrs = self._neighbours(note, self.evolve_k)
        if not nbrs:
            return {"should_evolve": False, "linked": 0, "updated": 0}
        desc = "\n".join(f"[{i}] context={n.context} tags={n.tags} content={n.content[:120]}"
                         for i, (_, n) in enumerate(nbrs))
        data = _parse_json(self._chat(
            _EVOLVE_PROMPT, f"NEW context={note.context}\ncontent={note.content[:400]}\n"
            f"keywords={note.keywords}\nNEIGHBOURS:\n{desc}"))
        linked = updated = 0
        if data and data.get("should_evolve"):
            idxs = [i for i in data.get("suggested_connections", [])
                    if isinstance(i, int) and 0 <= i < len(nbrs)]
            new_tags = data.get("new_tags_neighborhood", [])
            for j, i in enumerate(idxs):
                _, other = nbrs[i]
                self._link(note, other)
                linked += 1
                if "update_neighbor" in data.get("actions", []) and j < len(new_tags):
                    other.tags = [str(t).lower() for t in new_tags[j]][:8] or other.tags
                    other.evolution_history.append({"by": note.id, "tags": other.tags})
                    updated += 1
            if data.get("tags_to_update"):
                note.tags = [str(t).lower() for t in data["tags_to_update"]][:8]
        else:                                          # offline heuristic: similarity linking
            for sim, other in nbrs:
                if sim >= self.link_threshold:
                    self._link(note, other)
                    other.evolution_history.append({"by": note.id, "sim": round(sim, 3)})
                    linked += 1
        return {"should_evolve": linked > 0, "linked": linked, "updated": updated}

    def _link(self, a: Note, b: Note) -> None:
        if b.id not in a.links:
            a.links.append(b.id)
        if a.id not in b.links:
            b.links.append(a.id)
        self.graph.add_edge(f"note:{a.id}", f"note:{b.id}", "associated")

    # ── read path: HippoRAG retrieve — seed entities → PPR → ranked old notes ────
    def recall(self, query: str, k: int = 4) -> list[dict]:
        qinfo = self._analyze(query)
        qterms = list(dict.fromkeys(qinfo["keywords"] + _words(query)))
        seeds: dict[str, float] = {}
        for t in qterms:                               # exact + fuzzy entity match seeding
            seeds[f"ent:{t}"] = seeds.get(f"ent:{t}", 0.0) + 1.0
        ranks = self.graph.personalized_ranks(seeds)
        scored: list[tuple[float, Note]] = []
        for note in self.notes.values():
            ppr = ranks.get(f"note:{note.id}", 0.0)
            kw = _jaccard(set(qterms), set(note.keywords) | set(_words(note.content)))
            score = ppr * 10.0 + kw                    # PPR dominates; keyword breaks ties
            if score > 0:
                scored.append((score, note))
        scored.sort(key=lambda x: -x[0])
        hits = []
        for score, note in scored[:k]:
            note.retrieval_count += 1
            hits.append({"id": note.id, "title": note.title,
                         "snippet": note.content[:200], "score": round(score, 5),
                         "links": note.links, "tags": note.tags,
                         "via": "associative(hipporag-ppr+amem)"})
        self._save()
        return hits

    # ── persistence (durable across processes) ───────────────────────────────────
    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"notes": [asdict(n) for n in self.notes.values()]}, indent=0))

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except Exception:
            return
        for nd in data.get("notes", []):
            note = Note(**nd)
            self.notes[note.id] = note
            self.graph.add_node(f"note:{note.id}", "note", note.title[:80])
            for kw in note.keywords:
                self.graph.add_node(f"ent:{kw}", "entity", kw)
                self.graph.add_edge(f"note:{note.id}", f"ent:{kw}", "about")
        for note in self.notes.values():               # restore associations
            for lid in note.links:
                if lid in self.notes:
                    self.graph.add_edge(f"note:{note.id}", f"note:{lid}", "associated")

    def status(self) -> dict:
        g = self.graph.stats()
        return {"notes": len(self.notes), "graph": g,
                "links": sum(len(n.links) for n in self.notes.values()) // 2,
                "llm": self._llm_used, "persisted": bool(self.path),
                "donors": ["hipporag(vendored @ef2f14c, PPR recall)",
                           "a-mem(vendored @ceffb86, note evolution)"]}
