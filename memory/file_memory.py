"""memory/file_memory.py — durable one-fact-per-file memory, Claude-Code style (Phase B).

Mirrors exactly how Claude Code persists project memory across long sessions (the pattern
this repo already uses at .claude/projects/.../memory/): each memory is ONE markdown file
holding ONE fact, with YAML frontmatter (name / description / type), plus a MEMORY.md index
with a one-line pointer per note that is cheap to load at startup. Body text may link other
notes with [[name]] — links that don't resolve yet simply mark future notes, not errors.

This is glue (from-scratch allowed per stitch map: no OSS project implements the exact
Claude file-memory discipline). The heavy recall lives in memory/associative.py: every note
written here is ingested into AssociativeMemory so old facts resurface associatively when a
related topic is being read. Types follow Claude's: user / feedback / project / reference —
plus 'lesson' for trade lessons.

No LLM required to write or load; deterministic; safe to run in tests via a tmp dir.
"""
from __future__ import annotations

import re
from pathlib import Path

_TYPES = ("user", "feedback", "project", "reference", "lesson")


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:60] or "note"


class FileMemory:
    """Claude-style file memory: write(fact) → note file + index line; recall via associative."""

    def __init__(self, root: str | Path, associative=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "MEMORY.md"
        self.assoc = associative                     # AssociativeMemory | None
        if self.assoc is not None:
            # backfill ONLY notes the store hasn't seen, via the heuristic (no-LLM) path:
            # Note.id is a random uuid, so a naive re-add duplicates the store every boot,
            # and each LLM-analyzed add is 3 chat calls — 161 notes wedged the funnel main
            # thread for ~1h walking rate-limited provider chains (2026-07-10)
            known = {n.title for n in self.assoc.notes.values()}
            for note in self.load_all():             # old facts become recallable
                if note["name"] not in known:
                    self.assoc.add(note["body"], title=note["name"], use_llm=False)

    # ── write: one fact per file + index pointer (the Claude discipline) ─────────
    def write(self, name: str, description: str, body: str,
              type: str = "project", now: float = 0.0) -> dict:
        if type not in _TYPES:
            type = "project"
        name = _slug(name)
        path = self.root / f"{name}.md"
        existing = path.exists()                     # update-not-duplicate rule
        path.write_text(
            f"---\nname: {name}\ndescription: {description.strip()}\n"
            f"metadata:\n  type: {type}\n---\n\n{body.strip()}\n")
        self._index_add(name, description)
        if self.assoc is not None:
            self.assoc.add(body, title=name, now=now)
        return {"name": name, "path": str(path), "updated": existing}

    def _index_add(self, name: str, description: str) -> None:
        line = f"- [{name}]({name}.md) — {description.strip()}"
        lines = self.index.read_text().splitlines() if self.index.exists() else []
        lines = [ln for ln in lines if f"({name}.md)" not in ln]   # replace, don't duplicate
        lines.append(line)
        self.index.write_text("\n".join(lines) + "\n")

    # ── read ──────────────────────────────────────────────────────────────────────
    def load_all(self) -> list[dict]:
        notes = []
        for path in sorted(self.root.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            note = self._parse(path)
            if note:
                notes.append(note)
        return notes

    def get(self, name: str) -> dict | None:
        path = self.root / f"{_slug(name)}.md"
        return self._parse(path) if path.exists() else None

    def _parse(self, path: Path) -> dict | None:
        try:
            text = path.read_text()
        except Exception:
            return None
        m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
        front, body = (m.group(1), m.group(2)) if m else ("", text)

        def _field(key):
            fm = re.search(rf"^\s*{key}:\s*(.+)$", front, re.M)
            return fm.group(1).strip() if fm else ""
        links = re.findall(r"\[\[([a-z0-9\-]+)\]\]", body)
        return {"name": _field("name") or path.stem, "description": _field("description"),
                "type": _field("type") or "project", "body": body.strip(),
                "links": links, "file": path.name}

    def recall(self, query: str, k: int = 4) -> list[dict]:
        """Associative recall over the file notes (falls back to keyword scan)."""
        if self.assoc is not None:
            return self.assoc.recall(query, k=k)
        q = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
        scored = []
        for note in self.load_all():
            words = set(re.findall(r"[a-z0-9]{3,}", (note["body"] + note["description"]).lower()))
            s = len(q & words)
            if s:
                scored.append((s, note))
        scored.sort(key=lambda x: -x[0])
        return [{"title": n["name"], "snippet": n["body"][:200], "score": s,
                 "via": "file-memory(keyword)"} for s, n in scored[:k]]

    def status(self) -> dict:
        notes = self.load_all()
        by: dict[str, int] = {}
        for n in notes:
            by[n["type"]] = by.get(n["type"], 0) + 1
        return {"notes": len(notes), "by_type": by, "root": str(self.root),
                "index": self.index.exists(), "associative": self.assoc is not None}
