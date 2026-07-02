"""gen_index.py — auto-generate INDEX.md from the source tree (AST, stdlib only).

Per CONVENTIONS.md the index is NEVER hand-edited: it is regenerated from the
code so it can't drift. For each .py file it records the module summary, classes,
functions (with args + return annotation), and imports.

Run:  python3 tools/gen_index.py   (or: make index)
"""
from __future__ import annotations

import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "dashboard/static", ".venv", "venv", "node_modules",
             "srv", "openalgo", "catboost_info", ".pytensor",
             # vendored OSS trees are external source we reuse, not project modules to index —
             # excluding them keeps the context-loaded INDEX.md lean (vendor/ is documented in
             # vendor/README.md instead).
             "vendor"}
PKG_DIRS = ("core", "nodes", "eval", "tools", "tests", "dashboard")


def _sig(fn: ast.FunctionDef) -> str:
    args = [a.arg for a in fn.args.args]
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns else ""
    return f"{fn.name}({', '.join(args)}){ret}"


def _summarize(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except (SyntaxError, UnicodeDecodeError, OSError) as e:
        # never let one unparseable file (e.g. a vendored test fixture) crash the whole index
        return {"summary": f"(unparseable: {type(e).__name__})", "classes": [], "funcs": [],
                "imports": []}
    doc = (ast.get_docstring(tree) or "").strip().splitlines()
    classes, funcs, imports = [], [], []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            funcs.append(_sig(node))
        elif isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return {
        "summary": doc[0] if doc else "",
        "classes": classes, "funcs": funcs,
        "imports": sorted({i for i in imports if i}),
    }


def _iter_py() -> list[str]:
    out = []
    for base, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(base, ROOT)
        if any(rel == s or rel.startswith(s + os.sep) or os.path.basename(base) in SKIP_DIRS
               for s in SKIP_DIRS):
            dirs[:] = []
            continue
        for fn in files:
            if fn.endswith(".py"):
                out.append(os.path.join(base, fn))
    return sorted(out)


def build() -> str:
    lines = ["# INDEX.md — AUTO-GENERATED. Do not edit by hand.",
             "", "Regenerate with `make index` (parses the source via AST).", ""]
    for path in _iter_py():
        rel = os.path.relpath(path, ROOT)
        info = _summarize(path)
        lines.append(f"## `{rel}`")
        lines.append(f"_{info['summary']}_" if info["summary"] else "_(no summary)_")
        if info["classes"]:
            lines.append(f"- **classes:** {', '.join(info['classes'])}")
        if info["funcs"]:
            lines.append("- **functions:** " + "; ".join(f"`{s}`" for s in info["funcs"]))
        if info["imports"]:
            lines.append(f"- **imports:** {', '.join(info['imports'])}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    out = os.path.join(ROOT, "INDEX.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {out}")
