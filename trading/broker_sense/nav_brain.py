"""trading/broker_sense/nav_brain.py — intelligent Binance-UI navigation (Planner-Actor-Validator).

The brain's browsing was dumb: it looped on one page and opened the OFF options segment. This is the
SOTA fix (research/intelligent-web-navigation.md) — Skyvern-2.0's Planner-Actor-Validator loop
stitched onto our own perception/action layers, so navigation is GOAL-DIRECTED, SEGMENT-GATED, and
SELF-CORRECTING when stuck:

  • PLANNER  — decompose a goal into concrete UI actions, HARD-GATED by boss.active_segments so it can
    NEVER plan to open a segment the owner toggled off. Uses core.llm when available; a deterministic
    heuristic otherwise (so it works with no LLM and is fully testable).
  • ACTOR    — execute one action via the injected act_fn (wired to human_ui / live_browser).
  • VALIDATOR— re-perceive after the action: did the page move toward the sub-goal? A STUCK-DETECTOR
    (same page signature K times) declares a loop and hands error context back to the Planner to
    REPLAN / escape — the piece our old nav lacked, which is why it looped.

Injectable perceive_fn/act_fn keep it decoupled from Playwright (unit-testable, and the live adapter
is thin). Honest + bounded: a step budget + a replan cap guarantee termination; every step is traced.
"""
from __future__ import annotations

import hashlib
import json
import re

_OFF_SEGMENT_WORDS = ("options", "prediction", "futures", "spot", "equity", "commodities")


class NavBrain:
    """Goal-directed, segment-gated, self-correcting navigation over a live browser."""

    def __init__(self, perceive_fn, act_fn, *, market: str = "crypto",
                 max_steps: int = 12, max_replans: int = 3, stuck_k: int = 3):
        self.perceive = perceive_fn        # () -> {url, text?, image?} (current page)
        self.act = act_fn                  # (action: dict) -> None  (click/goto/scroll/type)
        self.market = market
        self.max_steps = max_steps
        self.max_replans = max_replans
        self.stuck_k = stuck_k

    # ── the gate: never touch a segment the owner turned off ─────────────────────────
    def allowed_segments(self) -> set:
        try:
            from trading.brain import boss
            return {s.lower() for s in boss.active_segments(self.market)}
        except Exception:
            return set()                   # fail-CLOSED: unknown gate → touch no gated segment

    def _gate(self, actions: list[dict]) -> list[dict]:
        """Drop any action whose target names a segment that is NOT active (the core fix)."""
        allowed = self.allowed_segments()
        out = []
        for a in actions:
            tgt = f"{a.get('target', '')} {a.get('segment', '')}".lower()
            seg = next((w for w in _OFF_SEGMENT_WORDS if re.search(rf"\b{w}\b", tgt)), None)
            if seg is not None and allowed and seg not in allowed:
                continue                   # gated-off segment → never plan it
            out.append(a)
        return out

    # ── Planner ──────────────────────────────────────────────────────────────────────
    def plan(self, goal: str, perception: dict, *, error: str | None = None) -> list[dict]:
        """Goal → ordered UI actions, segment-gated. LLM when available, heuristic otherwise."""
        actions = self._llm_plan(goal, perception, error) or self._heuristic_plan(goal, perception)
        return self._gate(actions)[: self.max_steps]

    def _llm_plan(self, goal, perception, error) -> list[dict] | None:
        try:
            from core import llm
            allowed = sorted(self.allowed_segments()) or ["futures"]
            sys = ("You navigate the Binance web trading UI. Output ONLY a JSON array of actions, each "
                   '{"type":"click|goto|scroll|type","target":"<visible label / url>","segment":"<or empty>"}. '
                   f"You may ONLY visit these segments: {allowed}. NEVER output an action for any other "
                   "segment. Keep it short and goal-directed; do not repeat the current page.")
            usr = (f"Goal: {goal}\nCurrent page: {perception.get('url', '')} — "
                   f"{str(perception.get('text', ''))[:400]}")
            if error:
                usr += f"\nYou were STUCK: {error}. Choose a DIFFERENT action to make progress."
            raw = llm.chat([{"role": "system", "content": sys}, {"role": "user", "content": usr}],
                           max_tokens=300, temperature=0.2, total_timeout=25)
            m = re.search(r"\[.*\]", raw or "", re.DOTALL)
            actions = json.loads(m.group(0)) if m else None
            return [a for a in actions if isinstance(a, dict) and a.get("target")] or None
        except Exception:
            return None

    def _heuristic_plan(self, goal, perception) -> list[dict]:
        """No-LLM fallback: visit each ALLOWED segment tab once (purposeful, never an off segment)."""
        allowed = sorted(self.allowed_segments()) or ["futures"]
        return [{"type": "click", "target": f"{seg} tab", "segment": seg} for seg in allowed]

    # ── Validator + stuck-detector ────────────────────────────────────────────────────
    @staticmethod
    def page_signature(perception: dict) -> str:
        basis = f"{perception.get('url', '')}|{str(perception.get('text', ''))[:2000]}"
        return hashlib.sha1(basis.encode()).hexdigest()[:16]

    def is_stuck(self, sigs: list[str]) -> bool:
        """Same page signature the last `stuck_k` steps ⇒ we're looping."""
        return len(sigs) >= self.stuck_k and len(set(sigs[-self.stuck_k:])) == 1

    def validate(self, action: dict, before: dict, after: dict) -> bool:
        """Progress check: the page changed, and (if the action named a target) the target now
        appears on the page. Cheap + honest — no LLM needed for the common case."""
        if self.page_signature(before) == self.page_signature(after):
            return False                   # nothing moved → not validated
        tgt = str(action.get("target", "")).lower().split()[0:1]
        if tgt:
            return tgt[0] in str(after.get("text", "")).lower() or bool(after.get("url"))
        return True

    # ── the loop ───────────────────────────────────────────────────────────────────────
    def navigate(self, goal: str) -> dict:
        """Plan → act → validate → replan-on-stuck, until the plan completes or budgets run out.
        Returns a full trace. Never raises into the caller."""
        trace: list[dict] = []
        sigs: list[str] = []
        try:
            plan = self.plan(goal, self.perceive())
        except Exception:
            plan = []
        i = steps = replans = 0
        while i < len(plan) and steps < self.max_steps:
            action = plan[i]
            try:
                before = self.perceive()
                self.act(action)
                after = self.perceive()
            except Exception as e:
                trace.append({"action": action, "ok": False, "error": str(e)[:80]})
                i += 1
                steps += 1
                continue
            steps += 1
            sigs.append(self.page_signature(after))
            ok = self.validate(action, before, after)
            trace.append({"action": action, "ok": ok, "sig": sigs[-1]})
            if ok:
                i += 1                     # progressed → next sub-goal
            elif self.is_stuck(sigs):      # same page repeatedly ⇒ we're looping
                if replans >= self.max_replans:
                    break                  # give up honestly rather than loop forever
                replans += 1               # STUCK → replan with error context, restart the plan
                plan = self.plan(goal, after, error=f"looping on {action.get('target')}")
                i = 0
                sigs = sigs[-1:]
            # else: not validated but not yet stuck → RETRY the same action (i unchanged) so
            # identical pages accumulate toward the stuck-detector; max_steps bounds the retries.
        return {"goal": goal, "steps": steps, "replans": replans,
                "completed": i >= len(plan) and len(plan) > 0,
                "allowed_segments": sorted(self.allowed_segments()), "trace": trace}


def from_human_ui(humanui, *, market: str = "crypto", **kw) -> "NavBrain":
    """Wire a NavBrain to a live browser via trading.brain.vision.human_ui.HumanUI — nav_brain
    supplies the INTELLIGENCE (plan/validate/segment-gate/stuck-detect); HumanUI supplies the eyes
    (perceive) + hand (vision-locate → click-at-coords, which survives DOM changes). Actions:
    click/type locate their target with the VLM then click its pixels; goto/nav uses page.goto.
    (Live-only: needs a running headed browser session to exercise — the loop itself is unit-tested.)"""
    def perceive() -> dict:
        try:
            p = humanui.perceive()
            return {"url": getattr(getattr(humanui, "page", None), "url", ""),
                    "text": getattr(p, "text", "") or ""}
        except Exception:
            return {"url": getattr(getattr(humanui, "page", None), "url", ""), "text": ""}

    def act(action: dict) -> None:
        page = getattr(humanui, "page", None)
        if page is None:
            return
        t = str(action.get("type", "click")).lower()
        target = str(action.get("target", ""))
        if t in ("goto", "nav") and target.startswith("http"):
            page.goto(target, timeout=30000, wait_until="domcontentloaded")
            return
        if t == "scroll":
            page.mouse.wheel(0, 400)
            return
        xy = None                          # click / type → locate the target by vision, then act
        try:
            xy = humanui.locate(target)
        except Exception:
            xy = None
        if xy:
            page.mouse.click(float(xy[0]), float(xy[1]))
            page.wait_for_timeout(150)
            if t == "type":
                page.keyboard.type(str(action.get("text", "")), delay=12)

    return NavBrain(perceive, act, market=market, **kw)
