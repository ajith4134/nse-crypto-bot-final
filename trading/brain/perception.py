"""trading/brain/perception.py — read ANY document/image into structured text (Phase D).

The coding-agent "read data in the image" capability, powered by real OSS:

  • Docling (IBM, pip `docling`) — converts PDF / Office / HTML / images into structured
    Markdown with layout, tables and reading order. The primary engine.
  • Surya-family OCR (via docling's OCR options / rapidocr fallback) — scanned pages and
    screenshots become text. CPU-only; models auto-download on first use and are cached.
  • OmniParser (vendored, trading/brain/gui) stays the LIVE-UI screenshot parser for the
    computer-use agent; this module is for documents/reports/charts — complementary.

`read_any(source)` accepts a path or bytes and returns {"text", "tables", "engine", "ok"}.
Enabled-when-installed pattern (same as semantic.py): with docling present the full document
stack is used; otherwise a functional plain-reader (txt/csv/json/md) still works, so the
capability is honest and offline-testable. Output feeds memory ingestion (associative +
file memory) so what the brain READS becomes what the brain REMEMBERS.
"""
from __future__ import annotations

import json
from pathlib import Path

_PLAIN_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".py", ".yaml", ".yml", ".html"}


def _docling_convert(path: Path) -> dict | None:
    """Real Docling pipeline (lazy import; heavy model load only on first call)."""
    try:
        from docling.document_converter import DocumentConverter
    except Exception:
        return None
    try:
        conv = DocumentConverter()
        result = conv.convert(str(path))
        doc = result.document
        tables = []
        try:
            for t in getattr(doc, "tables", []) or []:
                tables.append(t.export_to_dataframe().to_dict("records"))
        except Exception:
            pass
        return {"text": doc.export_to_markdown(), "tables": tables, "engine": "docling"}
    except Exception:
        return None


def _plain_read(path: Path) -> dict | None:
    if path.suffix.lower() not in _PLAIN_SUFFIXES:
        return None
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return None
    tables = []
    if path.suffix.lower() == ".csv":
        rows = [ln.split(",") for ln in text.splitlines() if ln.strip()]
        if len(rows) > 1:
            hdr = rows[0]
            tables = [dict(zip(hdr, r)) for r in rows[1:50]]
    elif path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, list):
                tables = data[:50]
        except Exception:
            pass
    return {"text": text[:200_000], "tables": tables, "engine": "plain"}


def read_any(source: str | Path | bytes, *, suffix: str = ".pdf",
             memory=None, title: str = "") -> dict:
    """Read any document/image → structured text (+ optional memory ingestion).

    source: file path, or raw bytes (suffix tells the decoder what it is).
    memory: optional object with .add(text, title=...) — e.g. AssociativeMemory /
            HybridMemory — so reading IS remembering.
    """
    if isinstance(source, bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(source)
            path = Path(f.name)
    else:
        path = Path(source)
    if not path.exists():
        return {"ok": False, "error": "not found", "text": "", "tables": [], "engine": None}

    out = _plain_read(path) if path.suffix.lower() in _PLAIN_SUFFIXES else None
    if out is None:
        out = _docling_convert(path) or _plain_read(path)
    if out is None:
        return {"ok": False, "error": "no engine could read this format",
                "text": "", "tables": [], "engine": None}
    out["ok"] = bool(out["text"].strip())
    out["source"] = str(path)
    if memory is not None and out["ok"]:
        try:
            memory.add(out["text"][:4000], title=title or path.name)
            out["remembered"] = True
        except Exception:
            out["remembered"] = False
    return out


def status() -> dict:
    try:
        import docling  # noqa: F401
        have_docling = True
    except Exception:
        have_docling = False
    try:
        import surya  # noqa: F401
        have_surya = True
    except Exception:
        have_surya = False
    return {"docling": have_docling, "surya_ocr": have_surya,
            "plain_formats": sorted(_PLAIN_SUFFIXES),
            "role": "documents/reports (OmniParser handles live UI screenshots)"}
