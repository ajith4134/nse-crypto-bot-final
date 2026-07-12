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
            shot = self.page.screenshot()
        except Exception:
            return b""
        self._mirror_shot(shot)
        return shot

    def _mirror_shot(self, shot: bytes) -> None:
        """Reuse an eyes screenshot as the owner's screen-mirror frame (throttled inside
        the mirror) — keeps the mirror seconds-fresh during long vision/LLM waits at zero
        extra browser work (2026-07-10). Never raises into the trading path."""
        if not shot:
            return
        try:
            from trading.broker_sense import screen_mirror
            w, h = self._viewport()
            screen_mirror.record_bytes(self.name, shot, url=self.page.url,
                                       viewport={"w": w, "h": h})
        except Exception:
            pass

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
                self._mirror_shot(shot)
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
        self._note({"act": "perceive", "goal": goal,
                    "via": "free" if screen_text else "vision"}, frame=False)
        return p

    def read(self, question: str, *, timeout: float = 40.0) -> str:
        """Answer a question about the screen. FREE FIRST: extract the on-screen TEXT (DOM +
        OCR) and captured JSON, and answer with the far-less-limited TEXT model. Falls back
        to cloud VISION only when the free senses returned nothing."""
        from core import llm
        self._note({"act": "read", "detail": question[:120]}, frame=False)
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
    def locate(self, target: str, *, timeout: float = 30.0,
               free_only: bool = False) -> Optional[tuple[int, int]]:
        """Return the (x, y) pixel center of the control described by `target`, or None.

        FREE FIRST: match the target against DOM element labels + OCR text (deterministic,
        instant, no quota). Only if the free eyes miss does it fall back to the rate-limited
        cloud vision model (0-1000 grid → viewport pixels).

        `free_only=True`: DOM/OCR ONLY — never the LLM grounding/VLM. Use it on the trade-loop
        thread (e.g. dismiss_modals) so a hung provider connection can't WEDGE the whole funnel
        cycle: a 27-min stall on 2026-07-12 was a modal-dismiss locate() falling into a
        vision_chat that blocked on getaddrinfo (DNS), which the request timeout doesn't bound."""
        if self.eyes is not None:
            try:
                xy = self.eyes.locate(target)
                if xy is not None:
                    self.trail.append({"act": "locate", "target": target, "xy": list(xy),
                                       "via": "free-eyes"})
                    return xy
            except Exception:
                pass
        if free_only:
            return None                              # DOM/OCR missed — do NOT call the LLM
        from core import llm
        shot = self._shot()
        if not shot:
            return None
        # GROUNDED EYES (invent-beyond #1): OmniParser icon-detection grounds the click in a
        # REAL detected control — local match first ($0), then ONE Set-of-Marks cloud pick
        # over the numbered boxes. Only if grounding is unavailable/misses does the old
        # raw-coordinate grid guess below run.
        try:
            from trading.brain.vision.grounded_eyes import get_grounded
            ge = get_grounded()
            if ge is not None:
                ocr = None
                try:
                    if self.eyes is not None:
                        ocr = self.eyes.glance(want_ocr=True).ocr
                except Exception:
                    ocr = None
                xy = ge.locate(target, shot, ocr=ocr)
                via = "grounded-local"
                if xy is None:
                    xy = ge.locate_som(target, shot, ocr=ocr, timeout=timeout)
                    via = "grounded-som"
                if xy is not None:
                    self.trail.append({"act": "locate", "target": target, "xy": list(xy),
                                       "via": via})
                    return xy
        except Exception:
            pass
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
    def click(self, target: str, *, guard: bool = True, settle_ms: int = 400,
              free_only: bool = False) -> bool:
        """Move the pointer to `target` and click it — like a human. Returns True on click.
        Guarded: refuses anything that could place an order / move money.
        `free_only=True` locates via DOM/OCR only (no hangable LLM) — trade-loop-thread safe."""
        if guard and _control_forbidden(target):
            self._note({"act": "click", "target": target, "blocked": "order-guard"})
            return False
        xy = self.locate(target, free_only=free_only)
        if xy is None:
            self._note({"act": "click", "target": target, "found": False}, frame=False)
            return False
        x, y = xy
        try:
            self.page.mouse.move(x, y, steps=self.move_steps)   # glide, not teleport
            self.page.wait_for_timeout(80)
            self.page.mouse.click(x, y)
            self.page.wait_for_timeout(settle_ms)
            self._fresh_eyes()                    # the screen changed — drop the glance cache
            self._note({"act": "click", "target": target, "xy": [x, y], "ok": True})
            return True
        except Exception as e:
            self._note({"act": "click", "target": target, "error": str(e)[:80]}, frame=False)
            return False

    def _fresh_eyes(self) -> None:
        """Invalidate the free-eyes glance cache after an action mutates the screen (#5)."""
        try:
            if getattr(self, "eyes", None) is not None:
                self.eyes.invalidate_glance()
        except Exception:
            pass

    def _note(self, row: dict, *, frame: bool = True) -> None:
        """Record one action honestly in BOTH stores: the in-memory trail (this process)
        and the cross-process screen mirror the owner watches (/api/trading/mirror).
        frame=True captures an annotated frame now; False logs the act but lets the
        mirror's idle throttle decide (for high-frequency read-only acts)."""
        self.trail.append(row)
        try:
            from trading.broker_sense import screen_mirror
            detail = str(row.get("target") or row.get("goal") or row.get("text")
                         or row.get("detail") or "")
            screen_mirror.log_action(
                self.name, self.page, str(row.get("act") or "?"), detail,
                xy=row.get("xy"), ok=row.get("ok"),
                extra={k: str(row[k])[:80] for k in ("blocked", "error", "found")
                       if k in row},
                force=frame)
        except Exception:
            pass

    def type_text(self, text: str, *, guard: bool = True, per_char_ms: int = 45) -> bool:
        """Type into the currently-focused field with human cadence (per-char delay)."""
        if guard and _control_forbidden(text):
            self._note({"act": "type", "blocked": "order-guard"})
            return False
        try:
            self.page.keyboard.type(str(text), delay=per_char_ms)
            self._fresh_eyes()
            self._note({"act": "type", "text": text[:40], "ok": True})
            return True
        except Exception as e:
            self._note({"act": "type", "error": str(e)[:80]}, frame=False)
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
            self._fresh_eyes()
            self._note({"act": "press", "detail": key})
            return True
        except Exception:
            return False

    # ── reflex: clear the pop-ups a human clicks past ────────────────────────────
    def dismiss_modals(self, *, max_dialogs: int = 4) -> int:
        """Close acknowledge-and-continue dialogs (SEBI risk notice, cookie banners) AND
        onboarding tour tooltips (the recurring 'Quick Navigation … Next/×' coach-marks that
        block the real controls). Returns how many it dismissed. Never touches order dialogs."""
        cleared = 0
        dead: set[str] = set()      # labels that clicked but changed nothing (this pass)
        for _ in range(max_dialogs):
            done = False
            for label in _DISMISS_LABELS:
                if label in dead or _control_forbidden(label):
                    continue
                # free_only: a modal close button is ALWAYS a DOM element — never invoke the
                # LLM grounding here. It runs on the funnel's trade-loop thread, so a hung
                # provider connection would wedge the WHOLE cycle (27-min stall, 2026-07-12).
                before = self.locate(label, free_only=True)
                if before is None:
                    continue
                if not self.click(label, settle_ms=500, free_only=True):
                    dead.add(label)
                    continue
                # VERIFY the dialog actually went away (2026-07-10): a click "succeeding"
                # only means the mouse fired — a decorative/covered match stays put and
                # used to be re-clicked forever ('Okay, I Understand' @1254,27 loop),
                # which also starved the × fallback below. Same label still at the same
                # spot → not a dismissal; blacklist it for this pass and move on.
                after = self.locate(label, free_only=True)
                if after is not None and abs(after[0] - before[0]) <= 2 \
                        and abs(after[1] - before[1]) <= 2:
                    self._note({"act": "click", "target": label, "ok": False,
                                "detail": f"{label} — no effect, skipping this pass"},
                               frame=False)
                    dead.add(label)
                    continue
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

    # ── fast learned navigation: plan from what the stack already knows ──────────
    def navigate(self, target: str, *, max_steps: int = 6) -> dict:
        """Reach the named app page/section FAST + ACCURATELY (ledger #10 wiring).

        fast_nav ranks HOW from what the stack already learned: replay a recorded hand
        skill (zero per-step vision) → direct goto of the best school-learned URL →
        honest visual explore (which records a new nav skill for next time). A goto only
        counts as arrived when the target's words actually appear in the landed URL/
        title/headings — never trust the jump itself. Every attempt's outcome feeds
        fast_nav_stats.json (2-strikes demotion), so accuracy compounds run over run.
        Read-only: the same order-guard as every other hand action applies."""
        from trading.brain.vision import fast_nav
        tt = fast_nav._tokens(target)
        for step in fast_nav.plan(self.name, target):
            method = str(step.get("method") or "")
            key = str(step.get("key") or step.get("url") or "")
            t0 = time.time()
            ok = False
            try:
                if method == "skill":
                    # ui_skills.json keys are "<app>:<skill>"; _replay_skill re-prefixes
                    bare = key.split(":", 1)[1] if key.startswith(f"{self.name}:") else key
                    ok = self._replay_skill(bare, {})
                elif method == "goto":
                    self.page.goto(key, timeout=20000, wait_until="domcontentloaded")
                    self.page.wait_for_timeout(800)
                    self.dismiss_modals()
                    seen = f"{self.page.url or ''} "
                    try:
                        seen += (self.page.title() or "") + " "
                        seen += " ".join(self.page.locator("h1, h2").all_inner_texts())
                    except Exception:
                        pass
                    ok = bool(tt & fast_nav._tokens(seen))
                elif method == "explore":
                    res = self.explore(
                        f"Navigate to the {target} page/section of this app. Do NOT "
                        "click any Buy/Sell/Trade button.",
                        max_steps=max_steps,
                        skill_key=f"nav-{'-'.join(sorted(tt)) or 'page'}")
                    ok = bool(res.get("done"))
            except Exception:
                ok = False
            fast_nav.record(self.name, target, method, key, ok,
                            (time.time() - t0) * 1000.0)
            self._note({"act": "navigate", "target": target, "ok": ok,
                        "detail": f"{method}:{key[:80]}"}, frame=ok)
            if ok:
                return {"target": target, "method": method, "key": key, "done": True}
        return {"target": target, "done": False}

    # ── autonomous exploration: see → decide → act → repeat (the full loop) ───────
    def explore(self, goal: str, *, max_steps: int = 8, skill_key: str | None = None,
                params: dict | None = None) -> dict:
        """Pursue `goal` on the page like a human exploring: perceive, decide the next single
        action from what's visible, act, and repeat until done or budget spent. Read-only
        exploration by default (order-guarded), so it can roam and learn safely.

        SKILL-CACHE (invent-beyond #2, Voyager-for-UI, 2026-07-07): pass `skill_key` (a
        stable name like 'upstox:add-watchlist-symbol') + `params` ({'SYM': 'RELIANCE'})
        and a previously-successful action trajectory REPLAYS directly — no per-step
        vision-LLM thinking on repeat tasks. A replay that stumbles (a click misses)
        falls back to a fresh explore, whose winning trajectory is re-recorded
        (self-healing). Callers confirm the outcome with skill_feedback()."""
        from core import llm
        params = params or {}
        if skill_key and self._replay_skill(skill_key, params):
            return {"goal": goal, "done": True, "replayed": True, "skill": skill_key}
        history: list[str] = []
        steps_rec: list[dict] = []                 # structured trajectory for the skill cache
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
                if skill_key and steps_rec:
                    self._save_skill(skill_key, steps_rec, params)
                return {"goal": goal, "steps": step, "done": True, "history": history,
                        "final": p.text[:400]}
            if act == "click":
                if self.click(tgt):
                    steps_rec.append({"action": "click", "target": tgt})
            elif act == "type":
                txt = str(obj.get("text") or "")
                if self.click_and_type(tgt, txt):
                    steps_rec.append({"action": "type", "target": tgt, "text": txt})
            elif act == "scroll":
                try:
                    self.page.mouse.wheel(0, 700)
                    steps_rec.append({"action": "scroll"})
                except Exception:
                    pass
            elif act == "read":
                self.remember(f"{goal}:{step}", self.read(tgt or goal))
        return {"goal": goal, "steps": max_steps, "done": False, "history": history}

    # ── the UI skill cache (Voyager pattern: record → replay → self-heal) ─────────
    _SKILLS_FILE = "ui_skills.json"

    @staticmethod
    def _tmpl(s: str, params: dict, reverse: bool = False) -> str:
        """'pin BELUSDT row' ⇄ 'pin {SYM} row' — parameterize/instantiate a step string."""
        out = s or ""
        for name, val in (params or {}).items():
            v = str(val)
            if not v:
                continue
            if reverse:
                out = out.replace("{%s}" % name, v)
            else:
                out = out.replace(v, "{%s}" % name)
        return out

    def _replay_skill(self, key: str, params: dict) -> bool:
        """Execute a cached trajectory. True only if EVERY step lands; any miss drops the
        cache entry (self-heal) so the next call explores fresh."""
        from trading import state
        skills = state.load_json(self._SKILLS_FILE, {})
        ent = skills.get(f"{self.name}:{key}") if isinstance(skills, dict) else None
        if not ent or not ent.get("steps") or ent.get("fails", 0) >= 2:
            return False
        for st in ent["steps"]:
            act = st.get("action")
            tgt = self._tmpl(st.get("target", ""), params, reverse=True)
            ok = True
            if act == "click":
                ok = self.click(tgt)
            elif act == "type":
                ok = self.click_and_type(tgt, self._tmpl(st.get("text", ""), params,
                                                         reverse=True))
            elif act == "scroll":
                try:
                    self.page.mouse.wheel(0, 700)
                except Exception:
                    ok = False
            if not ok:
                self.skill_feedback(key, False)       # stumbled → count the fail honestly
                return False
        self.trail.append({"act": "replay-skill", "skill": key, "ok": True})
        return True

    def _save_skill(self, key: str, steps: list[dict], params: dict) -> None:
        """Record a WINNING trajectory (parameterized) — the hand's learned muscle memory."""
        from trading import state
        skills = state.load_json(self._SKILLS_FILE, {})
        if not isinstance(skills, dict):
            skills = {}
        skills[f"{self.name}:{key}"] = {
            "steps": [{**st,
                       **({"target": self._tmpl(st.get("target", ""), params)}
                          if "target" in st else {}),
                       **({"text": self._tmpl(st.get("text", ""), params)}
                          if "text" in st else {})} for st in steps],
            "wins": (skills.get(f"{self.name}:{key}") or {}).get("wins", 0),
            "fails": 0, "ts": time.time(), "broker": self.name}
        state.save_json(self._SKILLS_FILE, skills)

    def skill_feedback(self, key: str, ok: bool) -> None:
        """Caller-confirmed outcome (the eyes re-read the screen): wins build trust (W7
        track record + rule-of-three), 2 fails evict the trajectory for re-learning."""
        from trading import state
        skills = state.load_json(self._SKILLS_FILE, {})
        k = f"{self.name}:{key}"
        ent = skills.get(k) if isinstance(skills, dict) else None
        if not ent:
            return
        if ok:
            ent["wins"] = ent.get("wins", 0) + 1
            ent["fails"] = 0
        else:
            ent["fails"] = ent.get("fails", 0) + 1
            if ent["fails"] >= 2:
                skills.pop(k, None)                   # evict → next call re-learns fresh
        if k in skills:
            skills[k] = ent
        state.save_json(self._SKILLS_FILE, skills)
        try:
            from trading.brain import track_record
            track_record.bump(f"ui-skill:{k}", kind="ui-skill", win=ok)
        except Exception:
            pass


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
