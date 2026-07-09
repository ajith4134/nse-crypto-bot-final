"""trading/brain/vision/grounded_eyes.py — LOCAL grounded eyes (invent-beyond #1).

OmniParser's icon-detection model (vendored project: vendor/omniparser; weights:
microsoft/OmniParser-v2.0 icon_detect, YOLO) runs LOCALLY on CPU and grounds every
click/read in real detected UI elements — buttons, icons, toggles, stars — the exact
controls the DOM+OCR free eyes miss (canvas/shadow-DOM SPAs render them with no text).

Cost model (why this beats the old chain):
  free eyes (DOM+OCR)      → exact text targets, instant, $0        (unchanged, first)
  grounded eyes (THIS)     → icon/control targets, ~1s CPU, $0      (new middle layer)
  Set-of-Marks ambiguity   → ONE cloud pick of a NUMBERED box, $≈0  (new; replaces …)
  raw 0-1000 grid guess    → cloud VLM guesses coordinates          (… this, last resort)
The SoM path is qualitatively safer than the grid guess: the model only CHOOSES among
elements the local detector actually found, so the click lands on a real control's
center — it can pick the wrong element, but never a hallucinated point.

No Florence-2 captioning here (GPU upgrade slot, per gui/perception): icons are labeled
deterministically from the OCR text inside/beside them; unlabeled icons stay reachable
through the SoM path. Kill-switch: GROUNDED_EYES=0. Honest degrade: missing weights or
ultralytics → get_grounded() returns None and every caller falls through unchanged.
"""
from __future__ import annotations

import io
import os
import threading
import time
from typing import Any, Optional

_BOX_CONF = 0.05          # OmniParser's own BOX_TRESHOLD default
_IOU = 0.4
_MAX_ELEMENTS = 80        # SoM legibility cap (numbered boxes on one image)
_LABEL_PAD_PX = 26        # OCR text this close below/right of an icon names it

_LOCK = threading.Lock()
_GROUNDED: Any = "unset"  # tri-state: "unset" | None (unavailable) | GroundedEyes


def _weights_path() -> Optional[str]:
    """The OmniParser-v2 icon_detect weights, from the local HF cache only — never a
    surprise download on a trading path (fetch explicitly: hf_hub_download(
    'microsoft/OmniParser-v2.0', 'icon_detect/model.pt'))."""
    try:
        from huggingface_hub import hf_hub_download
        return hf_hub_download("microsoft/OmniParser-v2.0", "icon_detect/model.pt",
                               local_files_only=True)
    except Exception:
        return None


class GroundedEyes:
    """Local OmniParser grounding: screenshot → detected UI elements → pixel centers."""

    def __init__(self, model):
        self._model = model
        self.stats = {"grounds": 0, "elements": 0, "local_hits": 0, "som_hits": 0,
                      "som_asks": 0, "last_ms": 0}

    # ── DETECT: YOLO icon/control boxes (local, CPU) ─────────────────────────────
    def _detect(self, png: bytes) -> list[dict]:
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("RGB")
        t0 = time.monotonic()
        # imgsz bounds CPU cost (full-res on a 1600px viewport took ~10× longer for no
        # accuracy win on UI controls); boxes come back in ORIGINAL-image pixels.
        try:
            imgsz = int(os.environ.get("GROUNDED_EYES_IMGSZ", "640"))
        except ValueError:
            imgsz = 640
        res = self._model.predict(img, conf=_BOX_CONF, iou=_IOU, imgsz=imgsz,
                                  verbose=False)[0]
        self.stats["last_ms"] = int((time.monotonic() - t0) * 1000)
        out = []
        for b in (res.boxes or []):
            x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
            out.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "cx": int((x1 + x2) / 2), "cy": int((y1 + y2) / 2),
                        "conf": round(float(b.conf[0]), 3), "kind": "icon", "label": ""})
        out.sort(key=lambda e: -e["conf"])
        return out[:_MAX_ELEMENTS]

    # ── GROUND: name each detected control from the OCR words in/near it ────────
    def ground(self, png: bytes, ocr: Optional[list[dict]] = None) -> list[dict]:
        """Detected elements with deterministic text labels (OCR inside the box, else the
        nearest word just below/right — how humans read icon captions)."""
        els = self._detect(png)
        for e in els:
            inside, near = [], []
            for o in (ocr or []):
                cx, cy = o.get("cx"), o.get("cy")
                if cx is None or cy is None or not (o.get("text") or "").strip():
                    continue
                if e["x1"] <= cx <= e["x2"] and e["y1"] <= cy <= e["y2"]:
                    inside.append((cy, cx, o["text"].strip()))
                elif (e["x1"] - _LABEL_PAD_PX <= cx <= e["x2"] + _LABEL_PAD_PX
                      and e["y1"] <= cy <= e["y2"] + _LABEL_PAD_PX):
                    near.append((cy, cx, o["text"].strip()))
            words = [t for _, _, t in sorted(inside)] or [t for _, _, t in sorted(near)[:2]]
            e["label"] = " ".join(words)[:60]
        self.stats["grounds"] += 1
        self.stats["elements"] += len(els)
        return els

    # ── LOCATE: deterministic label match (local, $0) ────────────────────────────
    def locate(self, target: str, png: bytes, *, ocr: Optional[list[dict]] = None,
               min_score: float = 0.45) -> Optional[tuple[int, int]]:
        from trading.brain.vision.free_eyes import _score_match
        best, best_s = None, min_score
        for e in self.ground(png, ocr):
            if not e["label"]:
                continue
            s = _score_match(target, e["label"])
            if s > best_s:
                best_s, best = s, (e["cx"], e["cy"])
        if best is not None:
            self.stats["local_hits"] += 1
        return best

    # ── AMBIGUITY: ONE Set-of-Marks cloud pick over the LOCALLY-grounded boxes ──
    def locate_som(self, target: str, png: bytes, *, ocr: Optional[list[dict]] = None,
                   timeout: float = 30.0) -> Optional[tuple[int, int]]:
        """Number every detected element on the screenshot, ask the vision model which
        NUMBER matches `target`, click that element's center. The model chooses among
        real controls only — it can never return a hallucinated coordinate."""
        els = self.ground(png, ocr)
        if not els:
            return None
        marked = self._som_image(png, els)
        if not marked:
            return None
        from core import llm
        self.stats["som_asks"] += 1
        try:
            raw = llm.vision_chat(
                f"The screenshot has numbered red boxes on interactive elements. Which "
                f"number is: \"{target}\"? Reply with ONLY the number, or -1 if absent.",
                marked, total_timeout=timeout, max_tokens=12)
            idx = int("".join(ch for ch in str(raw) if ch in "-0123456789") or "-1")
        except Exception:
            return None
        if 0 <= idx < len(els):
            self.stats["som_hits"] += 1
            return (els[idx]["cx"], els[idx]["cy"])
        return None

    @staticmethod
    def _som_image(png: bytes, els: list[dict]) -> bytes:
        try:
            from PIL import Image, ImageDraw
            img = Image.open(io.BytesIO(png)).convert("RGB")
            dr = ImageDraw.Draw(img)
            for i, e in enumerate(els):
                dr.rectangle([e["x1"], e["y1"], e["x2"], e["y2"]],
                             outline=(255, 60, 60), width=2)
                dr.text((e["x1"] + 2, max(0, e["y1"] - 12)), str(i), fill=(255, 60, 60))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return b""


def get_grounded() -> Optional[GroundedEyes]:
    """Process-wide singleton. None (honestly unavailable) when GROUNDED_EYES=0, the
    weights aren't in the HF cache yet, or ultralytics is missing — callers fall through
    to their existing cloud path unchanged."""
    global _GROUNDED
    if os.environ.get("GROUNDED_EYES", "1") not in ("1", "true", "TRUE", "yes"):
        return None
    if _GROUNDED != "unset":
        return _GROUNDED
    with _LOCK:
        if _GROUNDED != "unset":
            return _GROUNDED
        try:
            path = _weights_path()
            if not path:
                _GROUNDED = None
                return None
            from ultralytics import YOLO
            _GROUNDED = GroundedEyes(YOLO(path))
        except Exception:
            _GROUNDED = None
    return _GROUNDED


def status() -> dict:
    """Honest wiring status for the dashboard (never triggers a model load)."""
    g = _GROUNDED if _GROUNDED != "unset" else None
    return {"enabled": os.environ.get("GROUNDED_EYES", "1") in ("1", "true", "TRUE", "yes"),
            "loaded": isinstance(g, GroundedEyes),
            "weights_cached": bool(_weights_path()),
            **({"stats": g.stats} if isinstance(g, GroundedEyes) else {})}
