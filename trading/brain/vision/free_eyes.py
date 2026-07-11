"""trading/brain/vision/free_eyes.py — the brain's FREE, 24/7, never-rate-limited eyes.

Cloud vision (core.llm.vision_chat) is rate-limited on the free tiers, so it can't be the
workhorse. This module makes the brain SEE without it, by turning the "look at pixels"
problem into a "read structured data + text" problem — a perception LADDER, cheapest and
most-exact first, all local, no paid API, no quota:

  1. NETWORK sense — the broker SPA fetches everything (prices, watchlist, positions,
     candles, depth, greeks) as JSON; NetworkRecorder already captures it. Reading the
     app's OWN data feed is exact + instant + free. (trading/broker_sense/interception.py)
  2. DOM sense — enumerate interactive elements with TEXT + bounding boxes; gives free
     click-coordinates AND all visible labels, no vision. (reuses ocular_cortex._extract_from_page)
  3. OCR sense — RapidOCR/PaddleOCR (already installed) on the screenshot → words + boxes,
     for pixel-only content (charts/canvas) not in the DOM/network.

LOCALIZE (eyes→hand): match a target described in words against DOM labels → OCR text →
return the element's pixel centre. Exact text targets ('Pin new symbols') resolve with NO
LLM at all — deterministic + instant. READ (eyes→brain): DOM text + network JSON, answered
by the far-less-limited TEXT model (core.llm.chat) or plain regex — vision only as a last
resort. This is why the eyes work 24/7.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ── OCR engine (local, installed: RapidOCR primary, PaddleOCR fallback) ───────
_OCR = None
_OCR_KIND = None


_OCR_POOL = None


def _ocr_pool():
    """Shared OCR worker pool (#5): many pages' OCR overlaps on the cores instead of
    queueing behind one another. Sized modestly — OCR engines hold their own threads."""
    global _OCR_POOL
    if _OCR_POOL is None:
        from concurrent.futures import ThreadPoolExecutor
        _OCR_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="free-eyes-ocr")
    return _OCR_POOL


def _ocr_safe(shot) -> list:
    """Run OCR with a HARD wall-clock cap. The bare .result() here had NO timeout, so a wedged
    OCR engine blocked the caller (the funnel's browser hand → whole trade loop) forever
    (2026-07-11 mirror-freeze). On timeout/failure we degrade to DOM-only controls — never wedge."""
    import os as _os
    try:
        t = float(_os.getenv("FREE_EYES_OCR_TIMEOUT", "12") or 12)
    except ValueError:
        t = 12.0
    try:
        return _ocr_pool().submit(_ocr_read, shot).result(timeout=t)
    except Exception:                             # TimeoutError | OCR error → honest empty read
        return []


def _ocr_engine():
    """Lazily build a local OCR engine. RapidOCR (ONNX, fast) → PaddleOCR fallback → None."""
    global _OCR, _OCR_KIND
    if _OCR is not None or _OCR_KIND == "none":
        return _OCR
    try:
        from rapidocr import RapidOCR
        _OCR, _OCR_KIND = RapidOCR(), "rapidocr"
        return _OCR
    except Exception:
        pass
    try:
        from paddleocr import PaddleOCR
        _OCR, _OCR_KIND = PaddleOCR(use_angle_cls=False, lang="en", show_log=False), "paddleocr"
        return _OCR
    except Exception:
        _OCR_KIND = "none"
        return None


def _ocr_read(png_bytes: bytes) -> list[dict]:
    """OCR a PNG → [{text, cx, cy, box:[x,y,w,h]}] (pixel centres). [] if OCR unavailable."""
    eng = _ocr_engine()
    if eng is None or not png_bytes:
        return []
    try:
        import io
        import numpy as np
        from PIL import Image
        img = np.array(Image.open(io.BytesIO(png_bytes)).convert("RGB"))
    except Exception:
        return []
    out: list[dict] = []
    try:
        if _OCR_KIND == "rapidocr":
            res = eng(img)
            # rapidocr 3.x returns an object (.boxes/.txts) or a (list, elapse) tuple
            boxes = getattr(res, "boxes", None)
            txts = getattr(res, "txts", None)
            if boxes is not None and txts is not None:
                pairs = zip(boxes, txts)
            else:
                data = res[0] if isinstance(res, (list, tuple)) and res and isinstance(res[0], list) else res
                pairs = [(r[0], r[1]) for r in (data or []) if isinstance(r, (list, tuple)) and len(r) >= 2]
            for box, txt in pairs:
                out.append(_ocr_row(box, txt))
        elif _OCR_KIND == "paddleocr":
            res = eng.ocr(img, cls=False)
            for line in (res[0] if res and isinstance(res, list) else []):
                box, (txt, _score) = line[0], line[1]
                out.append(_ocr_row(box, txt))
    except Exception:
        return [r for r in out if r]
    return [r for r in out if r]


def _ocr_row(box, txt) -> Optional[dict]:
    try:
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        return {"text": str(txt), "cx": int(x + w / 2), "cy": int(y + h / 2),
                "box": [int(x), int(y), int(w), int(h)]}
    except Exception:
        return None


# ── fuzzy target→label matcher (deterministic, no LLM) ───────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


_STOP = {"the", "a", "an", "to", "of", "on", "for", "and", "or", "button", "icon",
         "click", "next", "in", "at", "is", "it", "that", "this", "with", "new"}


def _tok_hit(tok: str, pool: set) -> bool:
    """A token matches a pool token if equal, or (len≥3) a substring either way — so
    'symbol' matches 'symbols', 'watchlist' matches 'watchlists', etc."""
    return any(tok == p or (len(tok) >= 3 and (tok in p or p in tok)) for p in pool)


def _score_match(target: str, label: str) -> float:
    """How well a described `target` names a control `label` (0..1). Weighted toward LABEL
    coverage — a short label fully named inside a verbose target ('the + button to Pin new
    symbols') scores high — with substring/plural tolerance and stop-word removal."""
    t = {w for w in _norm(target).split() if w not in _STOP}
    l = {w for w in _norm(label).split() if w not in _STOP}
    if not t or not l:
        return 0.0
    label_cov = sum(1 for p in l if _tok_hit(p, t)) / len(l)     # of the label's words, how many the target names
    target_cov = sum(1 for p in t if _tok_hit(p, l)) / len(t)
    return round(label_cov * 0.8 + target_cov * 0.2, 4)


@dataclass
class Glance:
    """One free multi-sense read of the screen."""
    controls: list[dict] = field(default_factory=list)     # DOM elements + boxes
    ocr: list[dict] = field(default_factory=list)          # OCR words + boxes
    net: dict = field(default_factory=dict)                # captured JSON by kind
    shot: bytes = b""
    ts: float = 0.0

    def text(self) -> str:
        """All visible text the free senses picked up (DOM labels + OCR lines)."""
        seen, lines = set(), []
        for c in self.controls:
            lb = (c.get("label") or "").strip()
            if lb and lb.lower() not in seen:
                seen.add(lb.lower())
                lines.append(lb)
        for o in self.ocr:
            tx = (o.get("text") or "").strip()
            if tx and tx.lower() not in seen:
                seen.add(tx.lower())
                lines.append(tx)
        return "\n".join(lines)


class FreeEyes:
    """Free perception over a live Playwright page: network + DOM + OCR (no paid vision)."""

    def __init__(self, page, *, broker: str = "upstox", recorder=None):
        self.page = page
        self.broker = broker
        self._recorder = recorder
        self._attach_recorder()

    def _attach_recorder(self) -> None:
        if self._recorder is None:
            try:
                from trading.broker_sense.interception import get_recorder
                self._recorder = get_recorder()
            except Exception:
                self._recorder = None
        try:
            if self._recorder is not None:
                self._recorder.attach(self.page, self.broker)   # start capturing the JSON feed
        except Exception:
            pass

    # ── the free glance ──────────────────────────────────────────────────────
    # Perception cost model (invent-beyond #5, 2026-07-07): a glance = DOM walk +
    # screenshot (Playwright, page-thread-bound) + OCR (pure CPU). Action chains
    # (dismiss_modals → locate → click → confirm) used to re-glance EVERY step and
    # always paid OCR — a 16-symbol watchlist pass cost ~40 min. Now: a short-TTL
    # glance cache lets one perception serve the whole chain, OCR is LAZY (only when
    # the DOM misses), and OCR runs on a shared pool so many pages' OCR overlaps on
    # the 12 cores instead of queueing.
    _GLANCE_TTL_S = 1.2

    def glance(self, *, want_ocr: bool = True, fresh: bool = False) -> Glance:
        cached = getattr(self, "_glance_cache", None)
        if not fresh and cached is not None and time.time() - cached.ts < self._GLANCE_TTL_S:
            if cached.ocr or not want_ocr:
                return cached
            if cached.shot:                       # OCR-upgrade the cached shot: no re-walk
                cached.ocr.extend(_ocr_safe(cached.shot))
                return cached
        from trading.brain.vision.ocular_cortex import _extract_from_page
        controls, shot = _extract_from_page(self.page, want_shot=True)
        ocr = []
        if want_ocr and shot:
            ocr = _ocr_safe(shot)                 # overlaps across pages; HARD-bounded (never wedges)
        net = {}
        try:
            if self._recorder is not None:
                snap = self._recorder.snapshot() if hasattr(self._recorder, "snapshot") else {}
                if isinstance(snap, dict):
                    net = {k: v for k, v in snap.items()}
        except Exception:
            net = {}
        g = Glance(controls=controls, ocr=ocr, net=net, shot=shot or b"", ts=time.time())
        self._glance_cache = g
        return g

    def invalidate_glance(self) -> None:
        """The hand calls this after any action that changes the screen (click/type/nav)."""
        self._glance_cache = None

    # ── LOCALIZE: target text → pixel centre (deterministic, no LLM) ──────────
    def locate(self, target: str, *, min_score: float = 0.45) -> Optional[tuple[int, int]]:
        # LAZY OCR: the DOM answers most locates exactly — pay for OCR only on a miss.
        g = self.glance(want_ocr=False)
        best, best_s = None, min_score
        for c in g.controls:                                 # DOM first (most exact)
            if c.get("x") is None or c.get("covered"):
                # covered = an overlay/modal is on top at the control's center — clicking
                # its coords would hit the overlay, not it (2026-07-10 phantom-click fix)
                continue
            s = _score_match(target, c.get("label", ""))
            if s > best_s:
                best_s, best = s, (int(c["x"] + (c.get("w") or 0) / 2),
                                   int(c["y"] + (c.get("h") or 0) / 2))
        if best is not None:
            return best
        g = self.glance(want_ocr=True)                       # miss → the OCR lens
        for o in g.ocr:                                      # OCR text fallback
            s = _score_match(target, o.get("text", ""))
            if s > best_s:
                best_s, best = s, (o["cx"], o["cy"])
        return best

    # ── READ: structured data / text from the free senses (no vision) ─────────
    def network(self, kind: str) -> Any:
        try:
            if self._recorder is not None:
                row = self._recorder.latest(self.broker, kind)
                return (row or {}).get("body") if isinstance(row, dict) else row
        except Exception:
            pass
        return None

    def text(self) -> str:
        """All visible on-screen text (free) — hand this to the text brain to parse."""
        return self.glance().text()

    def find_text(self, needle: str) -> bool:
        return _norm(needle) in _norm(self.text())
