"""trading/brain/gui/skills.py — the LEARN layer: a growing library of GUI macros.

Adapted from vendor/voyager (SkillManager) but stripped of its langchain/OpenAI/Chroma deps:
a GUI skill is a named, reusable sequence of dashboard ACTIONS (a macro) plus a natural-language
description and its empirical success stats. The agent retrieves the best matching skill for a
goal (embedding-free keyword similarity — CPU, no dep), executes it, and updates its win-rate;
skills that keep working rise, skills that fail fall. This is how the agent "practices and gets
better": every validated macro is added to the library and compounds across sessions
(persisted via trading.state).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

STATE_FILE = "gui_skills.json"


def _tokens(text: str) -> set[str]:
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split()
            if len(w) > 2}


@dataclass
class GuiSkill:
    """A reusable dashboard macro: ordered action-steps + description + success stats."""
    name: str
    description: str
    target: str = "own_dashboard"
    steps: list = field(default_factory=list)     # [{"action","market",...}] for ActionExecutor
    tags: list = field(default_factory=list)
    n_used: int = 0
    n_success: int = 0

    @property
    def success_rate(self) -> float:
        return (self.n_success / self.n_used) if self.n_used else 0.0

    def record(self, ok: bool) -> None:
        self.n_used += 1
        if ok:
            self.n_success += 1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = round(self.success_rate, 4)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GuiSkill":
        keep = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**keep)


class GuiSkillLibrary:
    """Voyager-pattern growing skill library, file-based and CPU-only."""

    def __init__(self, *, persist: bool = True):
        self.persist = persist
        self.skills: dict[str, GuiSkill] = {}
        self._load()
        if not self.skills:
            self._seed()

    # ---- persistence ------------------------------------------------------
    def _load(self) -> None:
        if not self.persist:
            return
        from trading import state
        blob = state.load_json(STATE_FILE, {})
        for d in blob.get("skills", []):
            s = GuiSkill.from_dict(d)
            self.skills[s.name] = s

    def _save(self) -> None:
        if not self.persist:
            return
        from trading import state
        state.save_json(STATE_FILE, {"skills": [s.to_dict() for s in self.skills.values()]})

    # ---- seed with the obvious starter macros (so the agent is useful day 1) ----
    def _seed(self) -> None:
        seeds = [
            GuiSkill("start_crypto", "start the crypto market (enable + drive the Freqtrade bot)",
                     steps=[{"action": "start", "market": "CRYPTO"}],
                     tags=["start", "crypto", "run", "go", "enable"]),
            GuiSkill("stop_crypto", "stop the crypto market (disable + stop the Freqtrade bot)",
                     steps=[{"action": "stop", "market": "CRYPTO"}],
                     tags=["stop", "crypto", "disable", "halt"]),
            GuiSkill("pause_crypto", "graceful de-risk: only position-reducing orders",
                     steps=[{"action": "pause", "market": "CRYPTO"}],
                     tags=["pause", "reduce", "derisk", "crypto"]),
            GuiSkill("panic_all", "kill-switch: halt every market at once",
                     steps=[{"action": "panic", "market": "ALL"}],
                     tags=["panic", "halt", "kill", "emergency", "stop"]),
            GuiSkill("flatten_positions", "close every open position now",
                     steps=[{"action": "close_all", "market": "CRYPTO"}],
                     tags=["close", "flatten", "exit", "flat"]),
            GuiSkill("set_crypto_balance_1000", "reset crypto paper wallet to 1000",
                     steps=[{"action": "set_balance", "market": "CRYPTO", "amount": 1000.0}],
                     tags=["balance", "wallet", "paper", "reset", "fund"]),
            GuiSkill("widen_trailing_stop", "loosen the trailing stop to hold trades longer",
                     steps=[{"action": "set_strategy", "market": "CRYPTO",
                             "trail_mode": "percent", "trail_pct": 0.08}],
                     tags=["trailing", "stop", "hold", "strategy", "wide"]),
        ]
        for s in seeds:
            self.skills[s.name] = s
        self._save()

    # ---- library ops ------------------------------------------------------
    def add(self, skill: GuiSkill) -> GuiSkill:
        self.skills[skill.name] = skill
        self._save()
        return skill

    def get(self, name: str) -> GuiSkill | None:
        return self.skills.get(name)

    def record_use(self, name: str, ok: bool) -> None:
        s = self.skills.get(name)
        if s:
            s.record(ok)
            self._save()

    def retrieve(self, goal: str, k: int = 3) -> list[GuiSkill]:
        """Best skills for a goal: keyword overlap (name+desc+tags), tie-broken by success."""
        want = _tokens(goal)
        scored = []
        for s in self.skills.values():
            have = _tokens(s.name + " " + s.description + " " + " ".join(s.tags))
            overlap = len(want & have)
            if overlap:
                scored.append((overlap, s.success_rate, s))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [s for _, _, s in scored[:k]]

    def top(self, k: int = 12) -> list[dict]:
        ranked = sorted(self.skills.values(),
                        key=lambda s: (s.n_used > 0, s.success_rate, s.n_used), reverse=True)
        return [s.to_dict() for s in ranked[:k]]

    def to_json(self) -> dict:
        used = [s for s in self.skills.values() if s.n_used]
        return {"n_skills": len(self.skills), "n_practiced": len(used),
                "skills": self.top()}
