"""trading/brain/vision/ocular_cortex.py — the Ocular Cortex: ultra-advanced eyes + memory.

Modeled on how human vision becomes knowledge, in three stages:

  ICONIC   — one glance at a broker screen is captured as a PerceptualFrame that FUSES every
             modality at once: screenshot pixels + DOM controls (+ coordinates) + OCR numbers
             + the app's own internal JSON (network interception) + an API reference quote.
             (A human's retina doesn't read "the DOM" or "the pixels" — it takes the whole
             scene; so does a frame.)

  WORKING  — the last few frames per (broker, page) live in a short ring buffer, so the brain
             can ground the present against the immediate past ("the depth ladder moved since
             the last bar"), exactly like visual working memory.

  EPISODIC — repeated exposure CONSOLIDATES a layout into long-term memory: where each control
             sits (the golden path), which data kinds the page exposes, and how reliable that
             knowledge is. Recall lets the brain go straight to what it needs like someone
             who's used the app a hundred times; a layout that no longer matches raises a
             NOVELTY flag → the computer-use loop re-explores it.

Everything runs free and on CPU: the "understanding" of a screenshot is delegated to
core.llm.vision_chat (free multimodal tiers); structure/coordinate memory is plain Python.
Read-only: the cortex observes, it never acts (actions live in the guarded computer-use loop).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from trading import state

_LAYOUT_FILE = "ocular_layouts.json"
_LINK_FILE = "ocular_frame_links.json"
_FRAME_DIR = "ocular_frames"                 # screenshots kept ONLY for decision-linked frames
_WORKING_MAX = 8                             # frames per (broker, page) in working memory
_JACCARD_KNOWN = 0.60                        # label-set overlap ≥ this ⇒ "same layout"
_HABIT_N = 5                                 # consolidations before a layout is a habit


def _norm_label(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()[:48]


def _label_set(controls) -> set[str]:
    return {_norm_label(c.get("label", "")) for c in (controls or []) if c.get("label")}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _fingerprint(controls) -> str:
    """Structural fingerprint of a screen: hash of its sorted control labels. Stable when
    only values change, different when the LAYOUT changes — the novelty signal."""
    labels = sorted(_label_set(controls))
    return hashlib.sha1("|".join(labels).encode("utf-8", "ignore")).hexdigest()[:16]


@dataclass
class PerceptualFrame:
    """One fused glance at a broker screen — the iconic capture."""
    broker: str
    page_kind: str                           # 'screener' | 'segment' | 'symbol' | 'orderbook' | …
    url: str = ""
    ts: float = field(default_factory=time.time)
    screenshot: bytes | None = None          # PNG bytes (kept only if linked to a decision)
    dom_controls: list = field(default_factory=list)   # [{label, tag, x, y, w, h}]
    ocr_text: str = ""
    ocr_numbers: dict = field(default_factory=dict)
    network: dict = field(default_factory=dict)        # {kind: latest JSON body}
    api_ref: dict = field(default_factory=dict)        # reference quote/top-of-book
    vision_read: str = ""                    # free-VLM understanding (lazy, optional)
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = _fingerprint(self.dom_controls)

    @property
    def frame_id(self) -> str:
        raw = f"{self.broker}|{self.page_kind}|{self.ts:.3f}|{self.fingerprint}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def modalities(self) -> list[str]:
        """Which senses actually fired this frame (honest — only non-empty ones)."""
        m = []
        if self.screenshot:
            m.append("pixels")
        if self.dom_controls:
            m.append("dom")
        if self.ocr_text or self.ocr_numbers:
            m.append("ocr")
        if self.network:
            m.append("network")
        if self.api_ref:
            m.append("api")
        return m

    def data_values(self) -> dict:
        """Flatten the observed numeric data (OCR numbers + api ref) for learning columns."""
        out = dict(self.ocr_numbers)
        for k, v in (self.api_ref or {}).items():
            if isinstance(v, (int, float)):
                out.setdefault(k, v)
        return out

    def to_public(self) -> dict:
        return {"frame_id": self.frame_id, "broker": self.broker, "page_kind": self.page_kind,
                "url": self.url, "ts": self.ts, "fingerprint": self.fingerprint,
                "modalities": self.modalities(), "n_controls": len(self.dom_controls),
                "network_kinds": sorted(self.network), "vision_read": self.vision_read[:600]}


class LayoutMemory:
    """Persistent episodic memory of broker-app layouts (the golden paths).

    key = "broker/page_kind"; each remembers the label-sets seen, per-label coordinates, the
    data kinds exposed, consolidation state, and reliability (n_seen, last_seen)."""

    def __init__(self):
        self._data: dict = state.load_json(_LAYOUT_FILE, {})

    @staticmethod
    def _key(broker: str, page_kind: str) -> str:
        return f"{broker}/{page_kind}"

    def observe(self, frame: PerceptualFrame) -> dict:
        """Fold a frame into memory. Returns {novel, known, consolidation, jaccard}."""
        key = self._key(frame.broker, frame.page_kind)
        mem = self._data.setdefault(key, {"layouts": [], "coords": {}, "kinds": [],
                                          "n_seen": 0, "first_seen": frame.ts,
                                          "last_seen": frame.ts})
        labels = _label_set(frame.dom_controls)
        # match against known layouts by label-set overlap
        best_i, best_j = -1, 0.0
        for i, lay in enumerate(mem["layouts"]):
            j = _jaccard(labels, set(lay["labels"]))
            if j > best_j:
                best_i, best_j = i, j
        known = best_j >= _JACCARD_KNOWN
        if known:
            lay = mem["layouts"][best_i]
            lay["n_seen"] += 1
            lay["labels"] = sorted(set(lay["labels"]) | labels)   # accrete new controls
            lay["last_seen"] = frame.ts
            lay["fingerprint"] = frame.fingerprint
        else:
            mem["layouts"].append({"labels": sorted(labels), "fingerprint": frame.fingerprint,
                                   "n_seen": 1, "first_seen": frame.ts, "last_seen": frame.ts})
        # golden-path coordinates: last-known position per control label
        for c in frame.dom_controls:
            lab = _norm_label(c.get("label", ""))
            if lab and c.get("x") is not None:
                mem["coords"][lab] = {"x": c.get("x"), "y": c.get("y"),
                                      "w": c.get("w"), "h": c.get("h"),
                                      "tag": c.get("tag", ""), "ts": frame.ts}
        # data kinds this page exposes (from network interception)
        if frame.network:
            mem["kinds"] = sorted(set(mem["kinds"]) | set(frame.network))
        mem["n_seen"] += 1
        mem["last_seen"] = frame.ts
        max_n = max((lay["n_seen"] for lay in mem["layouts"]), default=1)
        consolidation = ("consolidated" if max_n >= _HABIT_N
                         else "working" if max_n >= 2 else "iconic")
        return {"novel": not known, "known": known, "consolidation": consolidation,
                "jaccard": round(best_j, 3)}

    def recall(self, broker: str, page_kind: str) -> dict | None:
        """What the brain already knows about this page: golden-path coords, data kinds,
        reliability, consolidation. None if never seen (→ explore it)."""
        mem = self._data.get(self._key(broker, page_kind))
        if not mem:
            return None
        max_n = max((lay["n_seen"] for lay in mem["layouts"]), default=1)
        return {"coords": mem["coords"], "kinds": mem["kinds"], "n_seen": mem["n_seen"],
                "layouts_known": len(mem["layouts"]), "last_seen": mem["last_seen"],
                "consolidation": ("consolidated" if max_n >= _HABIT_N
                                  else "working" if max_n >= 2 else "iconic")}

    def is_novel(self, frame: PerceptualFrame) -> bool:
        """READ-ONLY novelty check — does NOT record the frame (unlike observe). True when the
        frame's layout matches nothing we've consolidated for this page."""
        mem = self._data.get(self._key(frame.broker, frame.page_kind))
        if not mem or not mem["layouts"]:
            return True
        labels = _label_set(frame.dom_controls)
        best = max((_jaccard(labels, set(lay["labels"])) for lay in mem["layouts"]), default=0.0)
        return best < _JACCARD_KNOWN

    def locate(self, broker: str, page_kind: str, label_like: str) -> dict | None:
        """Golden-path lookup: last-known coordinates of a control by (fuzzy) label."""
        mem = self._data.get(self._key(broker, page_kind))
        if not mem:
            return None
        want = _norm_label(label_like)
        if want in mem["coords"]:
            return mem["coords"][want]
        for lab, xy in mem["coords"].items():          # substring fallback
            if want and want in lab:
                return xy
        return None

    def save(self) -> None:
        state.save_json(_LAYOUT_FILE, self._data)

    def status(self) -> dict:
        return {k: {"n_seen": m["n_seen"], "layouts": len(m["layouts"]),
                    "kinds": m["kinds"], "controls_known": len(m["coords"])}
                for k, m in self._data.items()}


class OcularCortex:
    """Facade over frame capture + working memory + episodic LayoutMemory + free vision."""

    def __init__(self, *, recorder=None, layout: LayoutMemory | None = None):
        self._recorder = recorder                      # lazy: interception.get_recorder()
        self.layout = layout or LayoutMemory()
        self._working: dict[str, list[PerceptualFrame]] = {}   # key → recent frames
        self._links: dict = state.load_json(_LINK_FILE, {})    # episode_id → frame record
        self.stats = {"frames": 0, "novel": 0, "vision_reads": 0}

    def recorder(self):
        if self._recorder is None:
            from trading.broker_sense.interception import get_recorder
            self._recorder = get_recorder()
        return self._recorder

    # ── capture ──────────────────────────────────────────────────────────────────
    def perceive(self, broker: str, page_kind: str, *, page=None, url: str = "",
                 dom_controls=None, ocr_text: str = "", ocr_numbers=None,
                 screenshot: bytes | None = None, api_ref=None,
                 capture_screenshot: bool = True) -> PerceptualFrame:
        """Build a fused PerceptualFrame. If a live Playwright `page` is given, DOM controls +
        screenshot are extracted from it; the app's captured JSON is pulled from the network
        recorder. Explicit modality args override/augment (used by tests + non-browser paths).
        Stores the frame in working memory and consolidates it into LayoutMemory."""
        controls = list(dom_controls or [])
        shot = screenshot
        if page is not None:
            pc, ps = _extract_from_page(page, want_shot=capture_screenshot)
            if pc:
                controls = controls or pc
            if ps and shot is None:
                shot = ps
        network = {}
        try:
            network = self._read_network(broker)
        except Exception:
            network = {}
        frame = PerceptualFrame(broker=broker, page_kind=page_kind, url=url,
                                screenshot=shot, dom_controls=controls, ocr_text=ocr_text,
                                ocr_numbers=dict(ocr_numbers or {}), network=network,
                                api_ref=dict(api_ref or {}))
        verdict = self.layout.observe(frame)
        self.layout.save()
        key = f"{broker}/{page_kind}"
        buf = self._working.setdefault(key, [])
        buf.append(frame)
        del buf[:-_WORKING_MAX]
        self.stats["frames"] += 1
        if verdict["novel"]:
            self.stats["novel"] += 1
        frame_meta = verdict
        self._last_verdict = frame_meta
        return frame

    def _read_network(self, broker: str) -> dict:
        """Freshest captured JSON per kind for this broker (free — the app already fetched it)."""
        rec = self.recorder()
        out = {}
        for kind, _needles in _known_kinds():
            body = rec.latest(broker, kind)
            if body is not None:
                out[kind] = body
        return out

    def last_verdict(self) -> dict:
        return getattr(self, "_last_verdict", {})

    # ── recall (the habit path) ──────────────────────────────────────────────────
    def recall(self, broker: str, page_kind: str) -> dict | None:
        return self.layout.recall(broker, page_kind)

    def locate(self, broker: str, page_kind: str, label_like: str) -> dict | None:
        return self.layout.locate(broker, page_kind, label_like)

    def is_novel(self, frame: PerceptualFrame) -> bool:
        """True if this frame's layout doesn't match what we've consolidated (→ re-explore).
        READ-ONLY: it does not record the frame (perceive() already did the recording)."""
        return self.layout.is_novel(frame)

    def working(self, broker: str, page_kind: str) -> list[PerceptualFrame]:
        return list(self._working.get(f"{broker}/{page_kind}", []))

    def ground(self, broker: str, page_kind: str) -> dict:
        """Cross-frame grounding vs the immediately-previous frame (visual working memory):
        which controls appeared/disappeared. Empty if there's no prior frame."""
        buf = self._working.get(f"{broker}/{page_kind}", [])
        if len(buf) < 2:
            return {}
        prev, cur = _label_set(buf[-2].dom_controls), _label_set(buf[-1].dom_controls)
        return {"appeared": sorted(cur - prev), "disappeared": sorted(prev - cur),
                "stable": len(cur & prev)}

    # ── free-VLM understanding (lazy, only when asked) ───────────────────────────
    def describe(self, frame: PerceptualFrame, prompt: str | None = None,
                 *, total_timeout: float = 40.0) -> str:
        """Delegate genuine 'what am I looking at' to the FREE vision providers. Caches the
        reading on the frame. Degrades to '' (honest) if no screenshot or no vision key."""
        if not frame.screenshot:
            return ""
        from core import llm
        if not llm.vision_available():
            return ""
        p = prompt or (
            f"You are the eyes of an automated trader looking at a {frame.broker} "
            f"{frame.page_kind} screen. Describe precisely what data and controls are visible "
            f"(prices, order book, candles, filters, buttons) and where. Be concise and factual.")
        try:
            txt = llm.vision_chat(p, frame.screenshot, total_timeout=total_timeout)
            frame.vision_read = txt or ""
            self.stats["vision_reads"] += 1
            return frame.vision_read
        except Exception:
            return ""

    # ── visual-outcome linkage (re-see what drove a trade) ───────────────────────
    def link_to_decision(self, frame: PerceptualFrame, episode_id: str) -> str:
        """Persist a compact record of the frame that drove a decision (+ its screenshot),
        keyed by the decision-memory episode, so reflection can later re-see the chart."""
        rec = frame.to_public()
        rec["data_values"] = frame.data_values()
        if frame.screenshot:
            try:
                d = state._path(_FRAME_DIR)
                d.mkdir(parents=True, exist_ok=True)
                path = d / f"{frame.frame_id}.png"
                path.write_bytes(frame.screenshot)
                rec["screenshot_path"] = str(path)
            except Exception:
                pass
        self._links[episode_id] = rec
        # keep the link map bounded (newest 500 decisions)
        if len(self._links) > 500:
            for old in sorted(self._links, key=lambda k: self._links[k].get("ts", 0))[:-500]:
                self._links.pop(old, None)
        state.save_json(_LINK_FILE, self._links)
        return rec.get("screenshot_path", "")

    def recall_decision_frame(self, episode_id: str) -> dict | None:
        return self._links.get(episode_id)

    def status(self) -> dict:
        return {"stats": dict(self.stats), "layouts": self.layout.status(),
                "linked_decisions": len(self._links),
                "vision_online": _vision_online()}


def _vision_online() -> bool:
    try:
        from core import llm
        return llm.vision_available()
    except Exception:
        return False


def _known_kinds():
    """Data kinds the interception layer can classify (shared vocabulary)."""
    from trading.broker_sense.interception import _KIND_RULES
    return _KIND_RULES


# 2026-07-10 rewrite: the old per-element loop cost ~3 protocol round-trips × 200
# elements (~600 RPCs) per glance — a real page-lag source with glances every cycle —
# and it collected INVISIBLE/occluded elements, so locate() clicked phantom controls
# forever (the 'Okay, I Understand' @1254,27 loop: a permanently-present but covered
# header notice outranked the real popup). ONE in-page evaluate now returns only
# on-screen, visible controls, each hit-tested at its center (`covered`=an overlay is
# on top) so the hand never aims at something it cannot actually press.
_EXTRACT_CONTROLS_JS = """
() => {
  const out = [];
  const els = document.querySelectorAll("button, a, input, [role=button], [role=tab]");
  const vw = window.innerWidth, vh = window.innerHeight;
  for (let i = 0; i < els.length && out.length < 200; i++) {
    const el = els[i];
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;                                   // collapsed
    if (r.bottom < 0 || r.right < 0 || r.top > vh || r.left > vw) continue; // off-screen
    const st = window.getComputedStyle(el);
    if (st.visibility === "hidden" || st.display === "none" || +st.opacity === 0) continue;
    let label = (el.innerText || el.getAttribute("aria-label") ||
                 el.getAttribute("placeholder") || el.getAttribute("name") || "").trim();
    label = label.replace(/\\s+/g, " ").slice(0, 48);
    if (!label) continue;
    const cx = Math.max(0, Math.min(vw - 1, r.left + r.width / 2));
    const cy = Math.max(0, Math.min(vh - 1, r.top + r.height / 2));
    const top = document.elementFromPoint(cx, cy);
    const covered = !(top && (el === top || el.contains(top) || top.contains(el)));
    out.push({label, tag: el.tagName.toLowerCase(), x: r.left, y: r.top,
              w: r.width, h: r.height, covered});
  }
  return out;
}
"""


def _extract_from_page(page, *, want_shot: bool = True):
    """Pull VISIBLE DOM controls (+ coordinates + occlusion flag) and a screenshot from a
    live Playwright page in one protocol round-trip. Best-effort; returns ([], None) on
    any failure so capture never breaks a cycle."""
    try:
        controls = page.evaluate(_EXTRACT_CONTROLS_JS) or []
    except Exception:
        controls = []
    shot = None
    if want_shot:
        try:
            shot = page.screenshot(type="png")
        except Exception:
            shot = None
    return controls, shot


_CORTEX: OcularCortex | None = None


def get_cortex() -> OcularCortex:
    global _CORTEX
    if _CORTEX is None:
        _CORTEX = OcularCortex()
    return _CORTEX
