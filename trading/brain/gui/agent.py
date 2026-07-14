"""trading/brain/gui/agent.py — the computer-use agent loop + its NodeProtocol face.

ComputerUseAgent ties the four layers into the loop the chat asks for:

    observe(target)  → SEE the dashboard (perception.py)
    decide(goal)     → recall lessons (reflection.py) + retrieve a skill (skills.py) + read the
                       live state for safety, and PLAN an action sequence
    act(plan)        → press the buttons (actions.py), guarded + paper-first
    reflect()        → distil a verbal lesson from the attempt (reflection.py)
    learn()          → update the skill's success stats / promote a new validated macro
    practice(n)      → run the loop repeatedly so skills compound — "study, practice, become
                       more intelligent"
    experiment()     → form a testable claim about what it sees and run it through the brain's
                       HypothesisLedger (trading/brain/hypothesis.py), so GUI observations feed
                       the same AI-Scientist research loop the rest of the brain uses.

ComputerUseNode exposes the agent's learned action-success credence on the NodeProtocol so the
capability shows up in the registry + node graph (dashboard-sync). Offline-safe and secrets-free.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema
from trading.brain.gui.actions import ActionExecutor
from trading.brain.gui.perception import DashboardPerception, capabilities as _perc_caps
from trading.brain.gui.reflection import GuiReflector
from trading.brain.gui.skills import GuiSkill, GuiSkillLibrary
from trading.brain.gui.targets import TargetRegistry


class ComputerUseAgent:
    """Sees dashboards, presses their buttons, experiments, reflects and learns."""

    def __init__(self, *, persist: bool = True, allow_live: bool = False,
                 default_dry_run: bool = True):
        self.targets = TargetRegistry(persist=persist)
        self.perception = DashboardPerception()
        self.actions = ActionExecutor(allow_live=allow_live, default_dry_run=default_dry_run)
        self.skills = GuiSkillLibrary(persist=persist)
        self.reflector = GuiReflector(persist=persist)
        self._last_perception: dict | None = None

    # ---- SEE --------------------------------------------------------------
    def observe(self, target_name: str = "own_dashboard", *, deep: bool = False) -> dict:
        target = self.targets.get(target_name)
        if target is None:
            return {"error": f"unknown target {target_name!r}",
                    "known": [t.name for t in self.targets.all()]}
        p = self.perception.see(target, deep=deep).to_dict()
        self._last_perception = p
        return p

    # ---- safety read: is it safe to push new trading activity? ------------
    def _safety(self, perception: dict, market: str = "CRYPTO") -> dict:
        """Read the live online state to avoid pressing 'start' into a HALTED kill-switch."""
        online = (perception or {}).get("panels", {}).get("online", {})
        markets = online.get("markets", {}) if isinstance(online, dict) else {}
        ms = markets.get(market) or markets.get(market.upper()) or {}
        ts = str(ms.get("trading_state", "")).upper()
        return {"halted": ts == "HALTED", "trading_state": ts,
                "mode": ms.get("mode", "PAPER"), "enabled": ms.get("enabled")}

    # ---- DECIDE -----------------------------------------------------------
    def decide(self, goal: str, target_name: str = "own_dashboard",
               market: str = "CRYPTO") -> dict:
        """Plan an action sequence for `goal`: recall lessons, retrieve a skill, safety-check."""
        perception = self._last_perception or self.observe(target_name)
        lessons = [l.to_dict() for l in self.reflector.recall(goal)]
        candidates = self.skills.retrieve(goal, k=3)
        chosen = candidates[0] if candidates else None
        safety = self._safety(perception, market)
        plan = {"goal": goal, "target": target_name, "market": market,
                "chosen_skill": chosen.name if chosen else None,
                "alternatives": [c.name for c in candidates[1:]],
                "steps": list(chosen.steps) if chosen else [],
                "lessons_recalled": lessons, "safety": safety, "abort": False, "reason": ""}
        if chosen is None:
            plan["abort"] = True
            plan["reason"] = f"no skill matches goal {goal!r} — observe more or add a skill"
            return plan
        # safety gate: don't push NEW trading activity into a kill-switched market
        opens_activity = any(s.get("action") in ("start",) for s in chosen.steps)
        if opens_activity and safety["halted"]:
            plan["abort"] = True
            plan["reason"] = ("market is HALTED (kill-switch) — refusing to start new activity; "
                              "clear the halt first")
        return plan

    # ---- ACT + REFLECT + LEARN (one full step) ---------------------------
    def step(self, goal: str, target_name: str = "own_dashboard", market: str = "CRYPTO",
             *, dry_run: bool | None = None, use_http: bool = False) -> dict:
        """One full perceive→decide→act→reflect→learn cycle. Returns the trace."""
        # deep=True: an ACTION cycle must SEE the React-rendered controls before pressing them
        # (the cheap stdlib parse finds none on our SPA); the Playwright cost is fine off the poll.
        perception = self.observe(target_name, deep=True)
        plan = self.decide(goal, target_name, market)
        trajectory: list[dict] = []
        if plan["abort"]:
            lesson = self.reflector.reflect(goal, [{"action": "decide", "ok": False,
                                                    "reason": plan["reason"]}], ok=False)
            return {"goal": goal, "plan": plan, "trajectory": [], "ok": False,
                    "lesson": lesson.to_dict(), "perception": perception}
        target = self.targets.get(target_name)
        ok_all = True
        for st in plan["steps"]:
            act = st.get("action")
            kw = {k: v for k, v in st.items() if k not in ("action", "market")}
            mkt = st.get("market", market)
            if use_http and target is not None:
                res = self.actions.http_control(target, act, mkt, dry_run=dry_run, **kw)
            else:
                res = self.actions.control(act, mkt, dry_run=dry_run, **kw)
            d = res.to_dict()
            trajectory.append(d)
            ok_all = ok_all and res.ok
        # LEARN: update the chosen skill's success stats + reflect
        if plan["chosen_skill"]:
            self.skills.record_use(plan["chosen_skill"], ok_all)
        lesson = self.reflector.reflect(goal, trajectory, ok=ok_all)
        return {"goal": goal, "plan": plan, "trajectory": trajectory, "ok": ok_all,
                "lesson": lesson.to_dict(),
                "perception": {"reachable": perception.get("reachable"),
                               "n_controls": perception.get("n_controls"),
                               "charts": perception.get("charts")}}

    # ---- PRACTICE (compound skills over many cycles) ---------------------
    def practice(self, goals: list[str] | None = None, rounds: int = 1,
                 target_name: str = "own_dashboard") -> dict:
        """Run the loop over a goal set repeatedly (paper/dry by default) so skills compound."""
        goals = goals or ["start crypto", "pause crypto", "widen trailing stop",
                          "flatten positions", "stop crypto"]
        runs = []
        for _ in range(max(1, rounds)):
            for g in goals:
                r = self.step(g, target_name, dry_run=True)   # practice is always dry
                runs.append({"goal": g, "ok": r["ok"],
                             "skill": r["plan"].get("chosen_skill")})
        practiced = [s for s in self.skills.skills.values() if s.n_used]
        return {"rounds": rounds, "goals": goals, "n_runs": len(runs),
                "n_skills_practiced": len(practiced),
                "skill_success": {s.name: round(s.success_rate, 3) for s in practiced},
                "runs": runs[-len(goals):]}

    # ---- EXPERIMENT (feed observations into the brain's research loop) ----
    def experiment(self, trades: list[dict] | None = None, seed: int = 0) -> dict:
        """Form testable claims from what the agent can see and run them through the brain's
        HypothesisLedger (AI-Scientist loop). If no journal is provided, reads the closed-trade
        journal; honestly reports when there is not yet enough evidence."""
        try:
            from trading.brain.hypothesis import HypothesisLedger
        except Exception as e:
            return {"available": False, "error": f"{type(e).__name__}: {e}"}
        if trades is None:
            try:
                from trading.journal.journal import TradeJournal
                jr = TradeJournal(state_file="journal.json", persist=True)
                trades = [t.to_dict() for t in jr.trades]
            except Exception:
                trades = []
        led = HypothesisLedger(persist=False)
        summary = led.run_cycle(trades or [], seed=seed)
        return {"available": True, "n_trades": len(trades or []),
                "hypotheses": summary, "ledger": led.to_json(),
                "note": "GUI agent fed what it observed into the HypothesisLedger research loop"}

    # ---- status (dashboard-sync, honest) ---------------------------------
    def to_json(self) -> dict:
        return {
            "targets": self.targets.to_json(),
            "perception_capabilities": _perc_caps(),     # cheap: no network read on status poll
            "action_capabilities": self.actions.capabilities(),
            "skills": self.skills.to_json(),
            "reflections": self.reflector.to_json(),
            "last_perception": self._last_perception,
        }


# ============================================================================ #
#  ComputerUseNode — NodeProtocol face                                          #
# ============================================================================ #
class ComputerUseNode(BaseNode):
    """NodeProtocol face: predict_proba = the agent's learned action-success credence.

    fit(X, y) records a base success rate from labels; predict_proba blends it with the mean
    success-rate of practiced GUI skills, so the node reflects how reliable the agent's learned
    macros are. Keeps the computer-use capability visible in the registry/dashboard.
    """
    name = "computer_use_agent"
    kind = "agent"
    summary = ("computer-use / GUI agent: sees dashboards (own + Freqtrade/FreqUI), presses "
               "buttons, experiments, reflects (Reflexion) and grows a skill library (Voyager)")
    schema = IOSchema(1, "GUI action context", "p(action succeeds | learned skills)")
    task = "binary"
    head = "y"

    def __init__(self, agent: ComputerUseAgent | None = None):
        self.agent = agent or ComputerUseAgent(persist=False)
        self._base = 0.5

    def fit(self, X, y):
        ya = np.asarray(y, dtype=float)
        if len(ya):
            self._base = float((ya > 0).mean())
        return self

    def predict_proba(self, X):
        used = [s for s in self.agent.skills.skills.values() if s.n_used]
        sr = float(np.mean([s.success_rate for s in used])) if used else 0.5
        p = max(0.0, min(1.0, 0.5 * self._base + 0.5 * sr))
        n = len(X) if hasattr(X, "__len__") else 1
        return [p] * n


def register_computer_use_agent(agent: ComputerUseAgent | None = None) -> ComputerUseNode:
    """Self-register on the live node registry (dashboard-sync). Idempotent."""
    from core import registry
    node = ComputerUseNode(agent=agent)
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
