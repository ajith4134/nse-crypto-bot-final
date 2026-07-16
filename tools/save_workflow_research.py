#!/usr/bin/env python3
"""tools/save_workflow_research.py — rescue completed workflow-agent results to durable files.

Owner 2026-07-16 ("I am reaching the limit — keep saving the completed agents' research to files as
soon as it's done"): a long deep-research workflow's findings must survive the session that launched
it. The harness already persists every agent transcript under the session's subagents/workflows/<run>/
directory, but as raw JSONL that nobody will ever read. This walks those transcripts and writes each
completed agent's FINAL RETURN VALUE out as markdown/JSON under research/, so the research is usable
even if the launching session dies mid-run.

Idempotent + incremental: re-run it any time; it simply re-dumps whatever has completed so far.

    python3 tools/save_workflow_research.py                     # auto-discovers recent runs
    python3 tools/save_workflow_research.py --run wf_1b9d76ec-ac6 --out research/gate-rebuild
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

HOME = os.path.expanduser("~")
PROJ = Path(HOME) / ".claude/projects/-home-karan18190164"


def _iter_json(path: Path):
    """Yield each JSON object in a .jsonl, skipping unparseable/partial trailing lines."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue          # a half-written final line while the run is live
    except OSError:
        return


def _text_of(obj) -> str:
    """Best-effort: pull human-readable text out of a transcript/journal record."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        for k in ("result", "output", "text", "content", "value", "final"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, (dict, list)):
                return json.dumps(v, indent=2)
        return json.dumps(obj, indent=2)
    return str(obj)


def _last_assistant_text(path: Path) -> str:
    """The agent's final assistant message = its return value (workflow subagents are told so)."""
    out = ""
    for rec in _iter_json(path):
        msg = rec.get("message") if isinstance(rec, dict) else None
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            out = content
        elif isinstance(content, list):
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            if any(p.strip() for p in parts):
                out = "\n".join(p for p in parts if p.strip())
    return out


def save_run(run_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = {"run": run_dir.name, "journal_entries": 0, "agents_saved": 0, "out": str(out_dir)}

    # 1) the journal records each agent()'s actual return value — the authoritative result
    journal = run_dir / "journal.jsonl"
    entries = list(_iter_json(journal))
    if entries:
        rep["journal_entries"] = len(entries)
        (out_dir / f"{run_dir.name}-journal.json").write_text(json.dumps(entries, indent=2))
        lines = [f"# Workflow research journal — {run_dir.name}", ""]
        for i, e in enumerate(entries, 1):
            label = e.get("label") or e.get("phase") or e.get("agent") or f"entry-{i}"
            lines += [f"## {i}. {label}", "", "```", _text_of(e.get("result", e))[:20000], "```", ""]
        (out_dir / f"{run_dir.name}-journal.md").write_text("\n".join(lines))

    # 2) every completed agent transcript → its final text (survives a killed orchestrator)
    saved = []
    for tp in sorted(run_dir.glob("agent-*.jsonl")):
        txt = _last_assistant_text(tp)
        if not txt.strip():
            continue                     # still running / produced nothing yet
        name = re.sub(r"[^a-z0-9-]", "", tp.stem.lower())
        (out_dir / f"{run_dir.name}-{name}.md").write_text(
            f"# Agent {tp.stem} — {run_dir.name}\n\n{txt}\n")
        saved.append(name)
    rep["agents_saved"] = len(saved)
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", help="run id (wf_...); default = all found")
    ap.add_argument("--out", default="research/workflow-research")
    args = ap.parse_args()

    roots = list(PROJ.glob("*/subagents/workflows/wf_*"))
    if args.run:
        roots = [r for r in roots if r.name in set(args.run)]
    if not roots:
        print("no workflow runs found")
        return
    for r in sorted(roots):
        out = Path(HOME) / args.out / r.name
        rep = save_run(r, out)
        print(f"{rep['run']}: journal={rep['journal_entries']} agents_saved={rep['agents_saved']} -> {rep['out']}")


if __name__ == "__main__":
    main()
