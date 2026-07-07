"""tools/skill_learnings.py — self-improving skills (Hermes-Agent / "self-improving Claude skills").

Research: research/hermes-agent.md. The idea from Nous's Hermes Agent (and the Simon Scrapes video)
is a CLOSED LEARNING LOOP: a skill writes down what it learned from each run so it gets better the
more it's used, instead of starting fresh every time.

This gives every skill in .claude/skills/<name>/ a **LEARNINGS.md** — agent-authored procedural
memory:
  • read(skill)            → the accumulated lessons (injected at the TOP of every skill run by the
                             PostToolUse hook hook_skill_learnings.py, so the agent consults them
                             before executing — the "read learnings first" half of the loop);
  • record(skill, …)       → append a structured lesson (worked / failed / edge / eval score / note)
                             after a run — the "write what you learned" half of the loop.

The lessons are plain markdown (human-readable + shareable, agentskills.io-friendly) and are picked
up by trading/brain/memory_search.py's FTS5 index (source='skill_learning'), so they're searchable
alongside the rest of the brain's memory. CPU-only, stdlib-only, no new dependency.

CLI (used by the hook and callable by the agent):
    python -m tools.skill_learnings read   <skill>
    python -m tools.skill_learnings record <skill> --note "…" [--worked "…"] [--failed "…"] \
           [--edge "…"] [--score 0.8]
    python -m tools.skill_learnings list
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

SKILLS_DIR = Path(os.environ.get("CLAUDE_SKILLS_DIR",
                                 str(Path.home() / ".claude/skills")))
_FILE = "LEARNINGS.md"
_MAX_BYTES = 60_000                    # cap a skill's memory so it never grows unbounded


def _path(skill: str) -> Path:
    skill = "".join(c for c in skill if c.isalnum() or c in "-_").strip() or "unknown"
    return SKILLS_DIR / skill / _FILE


def skill_exists(skill: str) -> bool:
    return (_path(skill).parent).is_dir()


def read(skill: str) -> str:
    """Accumulated lessons for a skill, or '' when none yet. Never raises."""
    p = _path(skill)
    try:
        return p.read_text() if p.exists() else ""
    except OSError:
        return ""


def record(skill: str, *, note: str = "", worked: str = "", failed: str = "",
           edge: str = "", score: float | None = None) -> dict:
    """Append one structured lesson to the skill's LEARNINGS.md. Returns {ok, path, entries}."""
    if not any((note, worked, failed, edge)):
        return {"ok": False, "error": "empty lesson — pass at least one of note/worked/failed/edge"}
    p = _path(skill)
    if not p.parent.is_dir():          # honest: only record for a real skill directory
        return {"ok": False, "error": f"no skill dir for '{skill}' at {p.parent}"}
    ts = time.strftime("%Y-%m-%d %H:%M")
    head = f"## {ts}" + (f" · eval {score:g}" if score is not None else "")
    lines = [head]
    if worked:
        lines.append(f"**Worked:** {worked.strip()}")
    if failed:
        lines.append(f"**Failed:** {failed.strip()}")
    if edge:
        lines.append(f"**Edge case:** {edge.strip()}")
    if note:
        lines.append(f"**Note:** {note.strip()}")
    entry = "\n".join(lines) + "\n\n"
    existing = read(skill)
    if not existing:
        existing = f"# Learnings: {skill}\n\nAgent-authored lessons from past runs (read before executing).\n\n"
    combined = existing + entry
    if len(combined) > _MAX_BYTES:     # keep the header + the most RECENT lessons
        header, _, body = combined.partition("\n\n")
        entries = [e for e in body.split("\n## ") if e.strip()]
        kept, size = [], len(header)
        for e in reversed(entries):    # newest first, until the cap
            chunk = ("## " + e) if not e.startswith("#") else e
            if size + len(chunk) > _MAX_BYTES:
                break
            kept.append(chunk)
            size += len(chunk)
        combined = header + "\n\n" + "".join(reversed(kept))
    try:
        p.write_text(combined)
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "path": str(p), "entries": _count_entries(combined)}


def _count_entries(text: str) -> int:
    return sum(1 for ln in text.splitlines() if ln.startswith("## "))


def all_skills() -> list[str]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def status() -> dict:
    """Per-skill lesson counts — honest view of which skills have learned anything yet."""
    out = {}
    for s in all_skills():
        t = read(s)
        if t:
            out[s] = _count_entries(t)
    return {"skills_with_learnings": len(out), "total_lessons": sum(out.values()), "by_skill": out}


def _main() -> int:
    ap = argparse.ArgumentParser(prog="skill_learnings")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read"); r.add_argument("skill")
    w = sub.add_parser("record"); w.add_argument("skill")
    for f in ("note", "worked", "failed", "edge"):
        w.add_argument(f"--{f}", default="")
    w.add_argument("--score", type=float, default=None)
    sub.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "read":
        print(read(a.skill) or f"(no learnings yet for '{a.skill}')")
    elif a.cmd == "record":
        print(record(a.skill, note=a.note, worked=a.worked, failed=a.failed,
                     edge=a.edge, score=a.score))
    elif a.cmd == "list":
        import json
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
