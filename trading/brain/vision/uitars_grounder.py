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
    """AGGRESSIVE mode: UI-TARS grounds FIRST when GROUNDER=uitars. Off by default (it's ~tens of
    seconds on CPU); prefer last_resort() for the sane wiring."""
    return os.environ.get("GROUNDER", "omniparser").strip().lower() == "uitars"


def last_resort() -> bool:
    """LAST-RESORT mode (recommended): UI-TARS runs ONLY after DOM/OCR + OmniParser(local+SoM) +
    the cloud grid-guess have ALL missed — a rare total miss, off the trade-loop hot path. Its
    ~tens-of-seconds CPU cost is paid only on those rare misses, buying accuracy without stalling
    normal navigation. Enabled by UITARS_LAST_RESORT=1 (or implied by the aggressive GROUNDER=uitars)."""
    if os.environ.get("UITARS_LAST_RESORT", "0") in ("1", "true", "TRUE", "yes", "on"):
        return True
    return enabled()


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


def _max_px() -> int:
    """Longest-side cap for the image SENT to the model. A VLM's cost is dominated by the
    number of vision tokens (∝ pixels), so downscaling a 1600px screenshot to ~1024 cuts the
    token count 2-4× → the single biggest latency lever on CPU. Coordinates are normalized
    0-1000 (resolution-independent), so we still map them back to the ORIGINAL pixels — the
    downscale speeds inference WITHOUT breaking the click location. UITARS_MAX_PX overrides."""
    try:
        return int(os.environ.get("UITARS_MAX_PX", "1024"))
    except ValueError:
        return 1024


def _prep_image(png: bytes) -> tuple[bytes, int, int]:
    """(downscaled_png_for_model, orig_w, orig_h). Downscale only when it helps; keep the
    ORIGINAL dims for coordinate rescaling."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        w, h = im.size
        cap = _max_px()
        longest = max(w, h)
        if longest <= cap:
            return png, w, h
        scale = cap / float(longest)
        small = im.convert("RGB").resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = io.BytesIO()
        small.save(buf, format="JPEG", quality=85)     # JPEG: fewer bytes than PNG to transfer
        return buf.getvalue(), w, h


def locate(target: str, png: bytes, *, timeout: float = 30.0) -> Optional[tuple[int, int]]:
    """Ground `target` to a pixel (x, y) via UI-TARS. None on any failure (caller falls back)."""
    if not png or not available():
        return None
    try:
        small, w, h = _prep_image(png)               # downscale for speed; keep orig dims
    except Exception:
        return None
    _STATS["asks"] += 1
    t0 = time.monotonic()
    try:
        import requests
        payload = {
            "model": _model(),
            "messages": [{"role": "user", "content": _PROMPT.format(target=target),
                          "images": [base64.b64encode(small).decode()]}],
            "stream": False,
            # keep_alive holds the model in RAM between clicks so we pay the 2-6 GB load ONCE,
            # not per locate() — turns a cold minutes-long call into a warm seconds-long one.
            "keep_alive": os.environ.get("UITARS_KEEP_ALIVE", "10m"),
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
    mode = "uitars-first" if enabled() else ("uitars-last-resort" if last_resort() else "off")
    return {"mode": mode, "default_grounder": "omniparser",
            "model": _model(), "model_pulled": available(),
            "max_px": _max_px(), "stats": dict(_STATS)}
