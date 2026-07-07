"""trading/brain/vision/human_ui.py — the brain's human-like eyes→brain→hand→memory loop.

Cutting-edge, non-fragile web interaction: the brain operates a web app the way a PERSON
does — it LOOKS at the rendered pixels (eyes), UNDERSTANDS what's there (brain), MOVES the
pointer to the right spot and clicks/types (hand), and REMEMBERS what it read (memory).

Why pixel/vision-based, not CSS/DOM selectors: modern broker SPAs (Upstox Pro) render into
shadow DOM / canvas and detect automation — raw selectors find NOTHING and break on every
UI refactor. A human doesn't read the DOM; they read the screen. So does this: perception is
`core.llm.vision_chat` (FREE multimodal, no GPU/paid), localization returns pixel coordinates,
and action is real mouse-move + click at those coordinates. That survives DOM changes because
it targets what's VISIBLE, exactly like a person.

Requires a REAL (headed) browser on a display — see SessionManager(headless=False) + Xvfb
(BROKER_SENSE_HEADED=1). Safety: every click/type is order-guarded (reuses computer_use's
FORBIDDEN matcher) so the eyes-and-hands loop can LOOK at anything but can NEVER place an
order / move money. Perception (looking) is never guarded — looking changes no state.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from trading.brain.vision.computer_use import _control_forbidden

# common "just acknowledge and continue" dialog labels a human clicks past without thinking
_DISMISS_LABELS = ("Okay, I Understand", "I Understand", "Okay", "Got it", "Accept",
                   "Continue", "Dismiss", "Close", "No thanks", "Maybe later", "Skip")


@dataclass
class Perception:
    """One eyes→brain read of the current screen."""
    text: str                                  # the brain's understanding of the page
    shot: bytes = b""                          # the raw screenshot the read was made from
    data: dict = field(default_factory=dict)   # any structured data extracted
    ts: float = 0.0


class HumanUI:
    """Drive a Playwright `page` like a human: see → understand → move+click/type → remember."""

    def __init__(self, page, *, name: str = "web", memory=None, move_steps: int = 18):
        self.page = page
        self.name = name
        self._mem = memory                     # OcularPerception / LayoutMemory (optional)
        self.move_steps = move_steps           # >1 = human-like glide, not a teleport
        self.trail: list[dict] = []            # honest action log (for the dashboard)
        # FREE 24/7 eyes (network + DOM + local OCR) — the workhorse; cloud vision is the
        # rate-limited last resort. See trading/brain/vision/free_eyes.py.
        try:
            from trading.brain.vision.free_eyes import FreeEyes
            self.eyes = FreeEyes(page, broker=name)
        except Exception:
            self.eyes = None

    # ── EYES: capture the rendered screen ────────────────────────────────────────
    def _shot(self) -> bytes:
        try:
            return self.page.screenshot()
        except Exception:
            return b""

    def _viewport(self) -> tuple[int, int]:
        vp = self.page.viewport_size or {"width": 1600, "height": 1000}
        return int(vp["width"]), int(vp["height"])

    # ── BRAIN: understand the screen (free vision) ───────────────────────────────
    def perceive(self, goal: str = "", *, timeout: float = 40.0) -> Perception:
        """Look at the page and describe what's on it (optionally focused on `goal`)."""
        from core import llm
        screen_text, shot = "", b""
        if self.eyes is not None:
            try:
                g = self.eyes.glance()
                screen_text, shot = g.text(), g.shot
            except Exception:
                screen_text = ""
        # FREE: understand from the extracted text (DOM+OCR) via the text model
        if screen_text.strip():
            try:
                txt = llm.chat([{"role": "user", "content":
                    "Visible text extracted from a broker web app screen (DOM + OCR):\n---\n"
                    f"{screen_text[:4000]}\n---\nDescribe concisely what this screen shows"
                    + (f", focused on: {goal}" if goal else "") + "."}],
                    max_tokens=400, temperature=0.2)
            except Exception:
                txt = screen_text[:800]                     # raw text is still a real read
        else:
            shot = shot or self._shot()
            try:
                txt = llm.vision_chat("Describe this broker web app screen concisely.",
                                      shot, total_timeout=timeout) if shot else "(no screen)"
            except Exception as e:
                txt = f"(perception unavailable: {str(e)[:80]})"
        p = Perception(text=txt, shot=shot, ts=time.time())
        self.trail.append({"act": "perceive", "goal": goal, "via": "free" if screen_text else "vision"})
        return p

    def read(self, question: str, *, timeout: float = 40.0) -> str:
        """Answer a question about the screen. FREE FIRST: extract the on-screen TEXT (DOM +
        OCR) and captured JSON, and answer with the far-less-limited TEXT model. Falls back
        to cloud VISION only when the free senses returned nothing."""
        from core import llm
        screen_text = ""
        if self.eyes is not None:
            try:
                screen_text = self.eyes.text()
            except Exception:
                screen_text = ""
        if screen_text.strip():
            try:
                return llm.chat([{"role": "user", "content":
                    "This is the visible text extracted from a broker web app screen "
                    f"(DOM + OCR):\n---\n{screen_text[:4000]}\n---\n"
                    f"Answer precisely, using only this text: {question}"}],
                    max_tokens=400, temperature=0.1)
            except Exception:
                pass
        shot = self._shot()                                # last resort: rate-limited vision
        if not shot:
            return screen_text[:600]
        try:
            return llm.vision_chat(
                f"Look at this broker web app screen and answer precisely: {question}\n"
                "Answer with only the requested facts.", shot, total_timeout=timeout)
        except Exception:
            return screen_text[:600]

    def read_json(self, instruction: str, *, timeout: float = 40.0) -> Any:
        """Extract STRUCTURED data from the screen (e.g. the watchlist symbols as a list)."""
        raw = self.read(instruction + " Reply with ONLY valid JSON, no prose.", timeout=timeout)
        return _extract_json(raw)

    # ── BRAIN→HAND: locate an element by description, in pixels ───────────────────
    def locate(self, target: str, *, timeout: float = 30.0) -> Optional[tuple[int, int]]:
        """Return the (x, y) pixel center of the control described by `target`, or None.

        FREE FIRST: match the target against DOM element labels + OCR text (deterministic,
        instant, no quota). Only if the free eyes miss does it fall back to the rate-limited
        cloud vision model (0-1000 grid → viewport pixels)."""
        if self.eyes is not None:
            try:
                xy = self.eyes.locate(target)
                if xy is not None:
                    self.trail.append({"act": "locate", "target": target, "xy": list(xy),
                                       "via": "free-eyes"})
                    return xy
            except Exception:
                pass
        from core import llm
        shot = self._shot()
        if not shot:
            return None
        prompt = (
            f"Find this control on the screen: \"{target}\".\n"
            "Return ONLY JSON: {\"found\": true/false, \"x\": <0-1000>, \"y\": <0-1000>} where x,y "
            "are the CENTER of the control on a 0-1000 grid (0,0 = top-left, 1000,1000 = "
            "bottom-right). If it is not visible, return {\"found\": false}.")
        try:
            raw = llm.vision_chat(prompt, shot, total_timeout=timeout, max_tokens=120)
        except Exception:
            return None
        obj = _extract_json(raw) or {}
        if not isinstance(obj, dict) or not obj.get("found"):
            return None
        try:
            gx, gy = float(obj["x"]), float(obj["y"])
        except (KeyError, TypeError, ValueError):
            return None
        w, h = self._viewport()
        x = max(0, min(w - 1, round(gx / 1000.0 * w)))
        y = max(0, min(h - 1, round(gy / 1000.0 * h)))
        return (x, y)

    # ── HAND: human-like pointer + keyboard (order-guarded) ──────────────────────
    def click(self, target: str, *, guard: bool = True, settle_ms: int = 400) -> bool:
        """Move the pointer to `target` and click it — like a human. Returns True on click.
        Guarded: refuses anything that could place an order / move money."""
        if guard and _control_forbidden(target):
            self.trail.append({"act": "click", "target": target, "blocked": "order-guard"})
            return False
        xy = self.locate(target)
        if xy is None:
            self.trail.append({"act": "click", "target": target, "found": False})
            return False
        x, y = xy
        try:
            self.page.mouse.move(x, y, steps=self.move_steps)   # glide, not teleport
            self.page.wait_for_timeout(80)
            self.page.mouse.click(x, y)
            self.page.wait_for_timeout(settle_ms)
            self.trail.append({"act": "click", "target": target, "xy": [x, y], "ok": True})
            return True
        except Exception as e:
            self.trail.append({"act": "click", "target": target, "error": str(e)[:80]})
            return False

    def type_text(self, text: str, *, guard: bool = True, per_char_ms: int = 45) -> bool:
        """Type into the currently-focused field with human cadence (per-char delay)."""
        if guard and _control_forbidden(text):
            self.trail.append({"act": "type", "blocked": "order-guard"})
            return False
        try:
            self.page.keyboard.type(str(text), delay=per_char_ms)
            self.trail.append({"act": "type", "text": text[:40], "ok": True})
            return True
        except Exception as e:
            self.trail.append({"act": "type", "error": str(e)[:80]})
            return False

    def click_and_type(self, target: str, text: str, *, clear: bool = True) -> bool:
        """Click a field then type into it (e.g. a search box) — the common human sequence."""
        if not self.click(target):
            return False
        if clear:
            try:
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Delete")
            except Exception:
                pass
        return self.type_text(text)

    def press(self, key: str) -> bool:
        try:
            self.page.keyboard.press(key)
            return True
        except Exception:
            return False

    # ── reflex: clear the pop-ups a human clicks past ────────────────────────────
    def dismiss_modals(self, *, max_dialogs: int = 4) -> int:
        """Close acknowledge-and-continue dialogs (SEBI risk notice, cookie banners) AND
        onboarding tour tooltips (the recurring 'Quick Navigation … Next/×' coach-marks that
        block the real controls). Returns how many it dismissed. Never touches order dialogs."""
        cleared = 0
        for _ in range(max_dialogs):
            done = False
            for label in _DISMISS_LABELS:
                if _control_forbidden(label):
                    continue
                if self.click(label, settle_ms=500):
                    cleared += 1
                    done = True
                    break
            if not done:                               # try the tour's close (×) icon by sight
                if self.click("the small × (close) icon on the onboarding tooltip / coach-mark "
                              "popup, if any is visible", settle_ms=400):
                    cleared += 1
                    done = True
            if not done:
                break
        return cleared

    # ── MEMORY: keep what was read ───────────────────────────────────────────────
    def remember(self, key: str, data: Any) -> None:
        """Persist an observation (episodic memory + a durable JSON note)."""
        rec = {"key": key, "data": data, "ts": time.time(), "site": self.name}
        try:
            if self._mem is not None and hasattr(self._mem, "note"):
                self._mem.note(key, data)
        except Exception:
            pass
        try:
            from trading import state
            log = state.load_json("human_ui_memory.json", [])
            if isinstance(log, list):
                state.save_json("human_ui_memory.json", (log + [rec])[-500:])
        except Exception:
            pass

    # ── autonomous exploration: see → decide → act → repeat (the full loop) ───────
    def explore(self, goal: str, *, max_steps: int = 8) -> dict:
        """Pursue `goal` on the page like a human exploring: perceive, decide the next single
        action from what's visible, act, and repeat until done or budget spent. Read-only
        exploration by default (order-guarded), so it can roam and learn safely."""
        from core import llm
        history: list[str] = []
        self.dismiss_modals()
        for step in range(max_steps):
            p = self.perceive(goal)
            decide = (
                f"GOAL: {goal}\n"
                f"WHAT YOU SEE: {p.text[:1200]}\n"
                f"ACTIONS SO FAR: {history[-5:]}\n"
                "Choose the SINGLE next action toward the goal. Reply ONLY JSON: "
                "{\"action\":\"click|type|read|scroll|done\", \"target\":\"<visible control "
                "or field, for click/type>\", \"text\":\"<for type>\", \"why\":\"<short>\"}.")
            try:                                        # FREE text-model decision (perception
                obj = _extract_json(llm.chat([{"role": "user", "content": decide}],  # already
                    max_tokens=200, temperature=0.2)) or {}                          # embeds
            except Exception as e:                                                    # what-you-see
                return {"goal": goal, "steps": step, "stopped": f"decide error: {str(e)[:80]}",
                        "history": history}
            act = str(obj.get("action") or "done").lower()
            tgt = str(obj.get("target") or "")
            history.append(f"{act}:{tgt or obj.get('text','')}")
            if act == "done":
                return {"goal": goal, "steps": step, "done": True, "history": history,
                        "final": p.text[:400]}
            if act == "click":
                self.click(tgt)
            elif act == "type":
                self.click_and_type(tgt, str(obj.get("text") or ""))
            elif act == "scroll":
                try:
                    self.page.mouse.wheel(0, 700)
                except Exception:
                    pass
            elif act == "read":
                self.remember(f"{goal}:{step}", self.read(tgt or goal))
        return {"goal": goal, "steps": max_steps, "done": False, "history": history}


# ── JSON tolerant extractor (models wrap JSON in prose/fences) ────────────────
def _extract_json(raw: str) -> Any:
    if not raw:
        return None
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)          # first {...} or [...]
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
    return None
