"""trading/brain/vision/computer_use.py — the FREE computer-use loop (cloned, read-only).

This is the open-source computer-use pattern (Anthropic's demo loop: observe screen → decide
ONE action → execute → observe again → repeat) rebuilt to run for FREE: the "brain" behind
the eyes is core.llm.vision_chat (free multimodal tiers), NOT the paid Claude Computer Use
API. Grounding is DOM-first (we act on real, labelled controls the page exposes) with the
screenshot given to the VLM for understanding — more reliable AND free than blind pixel
coordinates.

Two backends:
  free      (default) — vision_chat picks the next action from the visible controls. No GPU,
                        no per-call charge. This is the production path.
  anthropic (opt-in)  — the paid Claude Computer Use API; DISABLED unless COMPUTER_USE_PAID=1
                        and an ANTHROPIC_API_KEY is present. Never used by default.

Hard safety: a read-only guard (same forbidden-control family as sessions.py) makes it
IMPOSSIBLE for the loop to click buy / sell / order / place / confirm / leverage / deposit /
withdraw. The brain explores and reads; execution is done ONLY by the API exec adapter
elsewhere. Every step is bounded (max_steps + per-decision timeout) so a cycle can't wedge.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

from trading.brain.vision.ocular_cortex import get_cortex

# Order-placing / money-moving controls the loop must NEVER click or type into. Broad on
# purpose (fail SAFE): it also catches bare "Submit" / "Proceed" / "Pay" confirm buttons that
# a broker order dialog uses, and the raw "Long"/"Short" position-entry buttons on futures.
FORBIDDEN = re.compile(
    r"\b(buy|sell|order|place|trade|confirm|submit|proceed|leverage|margin|"
    r"withdraw|transfer|deposit|pay|long|short)\b", re.I)
# …but these are DATA VIEWS (order book, long/short RATIO, depth, open interest): safe to open
# and read even though the label contains an otherwise-forbidden word. Reads are never blocked
# at all (looking changes no state) — only clicks/types are guarded, via _control_forbidden.
SAFE_VIEW = re.compile(
    r"\b(order\s*book|orderbook|long[\s/]*short(\s*ratio)?|market\s*depth|depth\s*chart|"
    r"open\s*interest|order\s*history)\b", re.I)


def _control_forbidden(text: str) -> bool:
    """True if clicking/typing this control could place an order or move money. A data-view
    label (order book / long-short ratio / depth) is explicitly allowed so the brain can reach
    exactly the screens it is meant to read."""
    if not text:
        return False
    if SAFE_VIEW.search(text):
        return False
    return bool(FORBIDDEN.search(text))

_ACTION_GRAMMAR = (
    'Reply with EXACTLY ONE JSON object, no prose. Allowed actions:\n'
    '  {"action":"click","target":"<exact visible control label>","thought":"why"}\n'
    '  {"action":"type","target":"<field label>","value":"<text>","thought":"why"}\n'
    '  {"action":"scroll","target":"down|up","thought":"why"}\n'
    '  {"action":"read","target":"<what data you are reading now>","thought":"note"}\n'
    '  {"action":"done","thought":"<summary of what you accomplished/found>"}\n'
    'FORBIDDEN: never click or type anything that places or confirms an order '
    '(buy, sell, order, confirm, leverage, deposit). You only look and navigate.'
)


class GuardViolation(RuntimeError):
    """Raised when the loop is asked to perform a forbidden (order-placing) action."""


@dataclass
class Action:
    kind: str                # click | type | scroll | navigate | read | done | noop
    target: str = ""
    value: str = ""
    thought: str = ""

    def describe(self) -> str:
        return f"{self.kind}({self.target!r}{'='+self.value if self.value else ''})"


def _parse_action(text: str) -> Action:
    """Extract the first JSON action object from a model reply; robust to surrounding prose."""
    if not text:
        return Action("noop", thought="empty reply")
    m = re.search(r"\{.*?\}", text, re.S)
    if not m:
        return Action("done", thought=text.strip()[:200])
    try:
        d = json.loads(m.group(0))
    except Exception:
        return Action("done", thought=text.strip()[:200])
    kind = str(d.get("action", "noop")).lower().strip()
    return Action(kind=kind, target=str(d.get("target", "")),
                  value=str(d.get("value", "")), thought=str(d.get("thought", ""))[:300])


def _is_forbidden(action: Action) -> bool:
    # reading / scrolling / done / noop never change state → always safe (a read of the
    # "long/short ratio" or "order book" is exactly what we want and must not be blocked)
    if action.kind in ("read", "done", "scroll", "noop"):
        return False
    # only clicks/types can place an order → guard both the target label and any typed value
    return _control_forbidden(action.target) or _control_forbidden(action.value)


class ComputerUseAgent:
    """Observe → decide (free VLM) → guarded-execute → repeat, over a live broker page."""

    def __init__(self, *, cortex=None, backend: str = "free", max_steps: int = 12,
                 allow_actions: bool = True, per_decision_timeout: float = 30.0):
        self.cortex = cortex or get_cortex()
        self.backend = backend
        self.max_steps = max_steps
        self.allow_actions = allow_actions       # False → dry plan only (never touches page)
        self.per_decision_timeout = per_decision_timeout
        self.blocked = 0                          # forbidden actions refused (safety telemetry)

    # ── the vision brain (free by default) ───────────────────────────────────────
    def _decide(self, goal: str, screenshot, controls: list[str]) -> Action:
        prompt = (f"You are the eyes and hands of an automated trader. GOAL: {goal}\n"
                  f"Visible controls you may click/type into: {controls[:60]}\n"
                  f"{_ACTION_GRAMMAR}")
        try:
            txt = self._vision(prompt, screenshot)
        except Exception as e:
            return Action("done", thought=f"vision unavailable: {str(e)[:120]}")
        return _parse_action(txt)

    def _vision(self, prompt: str, screenshot) -> str:
        if self.backend == "anthropic":
            return self._anthropic_vision(prompt, screenshot)
        from core import llm
        if not llm.vision_available():
            raise RuntimeError("no free vision provider configured")
        imgs = [screenshot] if screenshot else []
        if not imgs:                              # no pixels → text-only reasoning still works
            return llm.chat([{"role": "user", "content": prompt}],
                            total_timeout=self.per_decision_timeout, max_tokens=250)
        return llm.vision_chat(prompt, imgs, total_timeout=self.per_decision_timeout,
                               max_tokens=250)

    def _anthropic_vision(self, prompt: str, screenshot) -> str:
        """Paid Claude Computer Use — OFF unless explicitly opted in (owner wants free)."""
        if os.environ.get("COMPUTER_USE_PAID") != "1" or not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("paid computer-use disabled (set COMPUTER_USE_PAID=1 to enable)")
        import base64

        import anthropic
        client = anthropic.Anthropic()
        content = [{"type": "text", "text": prompt}]
        if screenshot:
            b64 = base64.b64encode(screenshot).decode() if isinstance(screenshot, bytes) else screenshot
            content.append({"type": "image", "source": {"type": "base64",
                            "media_type": "image/png", "data": b64}})
        r = client.messages.create(model="claude-opus-4-8", max_tokens=250,
                                   messages=[{"role": "user", "content": content}])
        return "".join(getattr(b, "text", "") for b in r.content)

    # ── guarded execution on the live page ───────────────────────────────────────
    def _guard(self, action: Action) -> None:
        if _is_forbidden(action):
            self.blocked += 1
            raise GuardViolation(f"refused order-placing action: {action.describe()}")

    def _execute(self, page, action: Action, broker: str) -> dict:
        """Perform one guarded action on the Playwright page. Never places orders."""
        self._guard(action)
        if not self.allow_actions:
            return {"ok": True, "planned": True, "action": action.describe()}
        try:
            if action.kind == "click":
                el = _find_control(page, action.target)
                if el is None:
                    return {"ok": False, "reason": "control not found", "action": action.describe()}
                el.click()
                page.wait_for_timeout(1200)
                return {"ok": True, "action": action.describe()}
            if action.kind == "type":
                el = _find_control(page, action.target, inputs=True)
                if el is None:
                    return {"ok": False, "reason": "field not found", "action": action.describe()}
                el.fill(action.value)
                return {"ok": True, "action": action.describe()}
            if action.kind == "scroll":
                dy = 700 if action.target.lower() != "up" else -700
                page.mouse.wheel(0, dy)
                page.wait_for_timeout(600)
                return {"ok": True, "action": action.describe()}
        except GuardViolation:
            raise
        except Exception as e:
            return {"ok": False, "reason": str(e)[:140], "action": action.describe()}
        return {"ok": True, "action": action.describe()}      # read/done/noop are no-ops here

    # ── the loop ─────────────────────────────────────────────────────────────────
    def run(self, page, broker: str, page_kind: str, goal: str, *, url: str = "") -> dict:
        """Drive the page toward `goal` in ≤ max_steps guarded actions. Returns the trajectory,
        the final PerceptualFrame's public view, and any refused (forbidden) actions."""
        trajectory: list[dict] = []
        summary = ""
        last_frame = None
        for step in range(self.max_steps):
            frame = self.cortex.perceive(broker, page_kind, page=page, url=url)
            last_frame = frame
            controls = [c.get("label", "") for c in frame.dom_controls if c.get("label")]
            action = self._decide(goal, frame.screenshot, controls)
            entry = {"step": step, "thought": action.thought, "action": action.describe()}
            if action.kind == "done":
                summary = action.thought
                trajectory.append(entry)
                break
            try:
                res = self._execute(page, action, broker)
            except GuardViolation as gv:
                entry["blocked"] = str(gv)
                trajectory.append(entry)
                continue                          # refuse + keep going (never places the order)
            entry["result"] = res
            trajectory.append(entry)
        return {"broker": broker, "page_kind": page_kind, "goal": goal, "summary": summary,
                "steps": len(trajectory), "blocked": self.blocked, "trajectory": trajectory,
                "frame": last_frame.to_public() if last_frame else None}

    def explore(self, page, broker: str, page_kind: str) -> dict:
        """Novelty-driven: learn a page's layout + where its data lives (for the golden path)."""
        goal = (f"Explore this {broker} {page_kind} screen. Identify every segment tab, every "
                f"filter/sort control (volume, movement), the order book, the candle chart and "
                f"its timeframes, and where the key numbers are. Do not place any order.")
        return self.run(page, broker, page_kind, goal)


def _find_control(page, target: str, *, inputs: bool = False):
    """Locate a clickable/input element on the page by (fuzzy) visible label. Best-effort;
    None if not found. Never selects an order control (double-guard at the DOM layer)."""
    want = " ".join((target or "").split()).lower()
    if not want or _control_forbidden(want):
        return None
    sel = ("input, textarea, [contenteditable=true]" if inputs
           else "button, a, [role=button], [role=tab], input")
    try:
        els = page.query_selector_all(sel)
    except Exception:
        return None
    best = None
    for el in els[:300]:
        try:
            label = (el.inner_text() or el.get_attribute("aria-label")
                     or el.get_attribute("placeholder") or el.get_attribute("name") or "")
            label = " ".join(label.split()).lower()
        except Exception:
            continue
        if not label or _control_forbidden(label):
            continue
        if label == want:
            return el
        if best is None and want in label:
            best = el
    return best


_AGENT: ComputerUseAgent | None = None


def get_agent() -> ComputerUseAgent:
    global _AGENT
    if _AGENT is None:
        _AGENT = ComputerUseAgent()
    return _AGENT
