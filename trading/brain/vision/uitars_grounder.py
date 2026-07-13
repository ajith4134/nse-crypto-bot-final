"""trading/brain/vision/uitars_grounder.py — UI-TARS end-to-end GUI grounder (adopt-plan item 1).

Alternative to the OmniParser->OCR->Set-of-Marks chain in grounded_eyes: ByteDance UI-TARS is a
single vision model TRAINED on GUI grounding — given a screenshot + a target description it emits
the click coordinate directly (elements are a first-class concept, not image regions). Matches
Claude Computer-Use / OpenAI Operator on grounding benchmarks (repo: github.com/bytedance/UI-TARS,
Apache-2.0). Behind a KILL-SWITCH so OmniParser stays the CPU-cheap default:

    GROUNDER=uitars      → human_ui.locate() tries THIS first, falls back to OmniParser/SoM.
    UITARS_MODEL=ui-tars → the Ollama model tag serving UI-TARS locally (same runtime as our
                           permanent qwen2.5-vl eyes; a 7B GGUF runs on this box like qwen2.5-vl).

Honest degrade: if the model isn't pulled / the endpoint is down / the output can't be parsed,
locate() returns None and the caller falls through to the existing grounding chain UNCHANGED —
never a hallucinated coordinate, never a broken click. Works for BOTH the Binance and Upstox web
apps (it grounds pixels, market-agnostic). No new heavy dep: reuses the local Ollama runtime.
"""
from __future__ import annotations

import base64
import io
import os
import re
import threading
import time
from typing import Optional

_STATS = {"asks": 0, "hits": 0, "parse_fail": 0, "errors": 0, "last_ms": 0}
_AVAIL: Optional[bool] = None            # cached model-availability probe
_LOCK = threading.Lock()


def enabled() -> bool:
    """UI-TARS is the active grounder only when GROUNDER=uitars (OmniParser is the default)."""
    return os.environ.get("GROUNDER", "omniparser").strip().lower() == "uitars"


def _model() -> str:
    return os.environ.get("UITARS_MODEL", "ui-tars")


def _ollama_base() -> str:
    """Native Ollama endpoint (supports base64 images in /api/chat). Derives from the same
    config the local-vision floor uses; strips a trailing /v1 (OpenAI-compat) if present."""
    base = (os.environ.get("OLLAMA_HOST")
            or os.environ.get("LOCAL_LLM_BASE_URL")
            or "http://localhost:11434")
    base = base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    if not base.startswith("http"):
        base = "http://" + base
    return base


def available() -> bool:
    """True when the UI-TARS model is actually pulled into the local runtime (cached probe).
    Cheap /api/tags check — never downloads. Lets status()/callers be honest about the lane."""
    global _AVAIL
    if _AVAIL is not None:
        return _AVAIL
    with _LOCK:
        if _AVAIL is not None:
            return _AVAIL
        try:
            import requests
            r = requests.get(f"{_ollama_base()}/api/tags", timeout=3)
            tags = [m.get("name", "") for m in (r.json().get("models") or [])]
            want = _model()
            _AVAIL = any(want == t or t.startswith(want + ":") or want in t for t in tags)
        except Exception:
            _AVAIL = False
    return _AVAIL


# UI-TARS grounding prompt: the model's own GROUNDING template asks for a single point in a
# normalized 0-1000 coordinate space, which we then scale to viewport pixels.
_PROMPT = (
    "You are a GUI grounding model. Output the click point for the described UI element as "
    "coordinates in a 0-1000 normalized space (0,0 = top-left, 1000,1000 = bottom-right). "
    "Reply with ONLY `(x,y)` and nothing else, or `(-1,-1)` if the element is not visible.\n"
    "Element: {target}")

_COORD_RE = re.compile(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?")


def _png_dims(png: bytes) -> tuple[int, int]:
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        return im.size                    # (w, h)


def locate(target: str, png: bytes, *, timeout: float = 30.0) -> Optional[tuple[int, int]]:
    """Ground `target` to a pixel (x, y) via UI-TARS. None on any failure (caller falls back)."""
    if not png or not available():
        return None
    try:
        w, h = _png_dims(png)
    except Exception:
        return None
    _STATS["asks"] += 1
    t0 = time.monotonic()
    try:
        import requests
        payload = {
            "model": _model(),
            "messages": [{"role": "user", "content": _PROMPT.format(target=target),
                          "images": [base64.b64encode(png).decode()]}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 24},
        }
        r = requests.post(f"{_ollama_base()}/api/chat", json=payload, timeout=timeout)
        raw = (r.json().get("message") or {}).get("content", "")
    except Exception:
        _STATS["errors"] += 1
        return None
    finally:
        _STATS["last_ms"] = int((time.monotonic() - t0) * 1000)
    m = _COORD_RE.search(str(raw))
    if not m:
        _STATS["parse_fail"] += 1
        return None
    try:
        nx, ny = float(m.group(1)), float(m.group(2))
    except ValueError:
        _STATS["parse_fail"] += 1
        return None
    if nx < 0 or ny < 0:
        return None                       # model says "not visible" — honest miss
    # UI-TARS may emit normalized 0-1000 OR already-pixel coords; disambiguate by range.
    if nx <= 1000 and ny <= 1000 and (nx > w or ny > h or max(w, h) > 1000):
        x = int(round(nx / 1000.0 * w))
        y = int(round(ny / 1000.0 * h))
    else:
        x, y = int(round(nx)), int(round(ny))
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))
    _STATS["hits"] += 1
    return (x, y)


def status() -> dict:
    return {"active_grounder": "uitars" if enabled() else "omniparser",
            "model": _model(), "model_pulled": available(), "stats": dict(_STATS)}
