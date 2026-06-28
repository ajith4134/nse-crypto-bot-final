"""trading/brain/skills.py — growing skill library (T8.8, Voyager pattern).

A persistent, ever-growing library of VALIDATED trading "skills" (parameterised
strategies / rules) the brain can retrieve and reuse — the Voyager idea applied to
trading. A skill is ADMITTED only if it clears a quality gate (its back-tested metric
must beat a threshold AND, for an existing same-named skill, improve on it), so the
library only grows with things that actually worked. Retrieval ranks by market + metric.

Persisted as JSON (reuses trading.state) so the library survives restarts and compounds
across sessions — accuracy/coverage rise the more the brain trades. Pure Python, CPU.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading import state


@dataclass
class Skill:
    id: str
    name: str
    kind: str                          # strategy | rule | playbook
    market: str
    payload: dict                      # e.g. Strategy.to_dict() or a rule spec
    metric: float = 0.0                # quality score (e.g. OOS fitness / expectancy)
    metrics: dict = field(default_factory=dict)
    source: str = ""
    generation: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "market": self.market,
                "payload": self.payload, "metric": self.metric, "metrics": self.metrics,
                "source": self.source, "generation": self.generation}

    @classmethod
    def from_dict(cls, d: dict) -> "Skill":
        return cls(**{k: d.get(k) for k in ("id", "name", "kind", "market", "payload",
                                            "metric", "metrics", "source", "generation")})


class SkillLibrary:
    """Quality-gated, growing, persisted library of reusable trading skills."""

    def __init__(self, *, state_file: str = "skill_library.json", min_metric: float = 0.0,
                 persist: bool = True):
        self.state_file = state_file
        self.min_metric = min_metric
        self.persist = persist
        self._skills: dict[str, Skill] = {}
        if persist:
            self._load()

    def _load(self) -> None:
        rows = state.load_json(self.state_file, [])
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and r.get("name"):
                    self._skills[r["name"]] = Skill.from_dict(r)

    def _save(self) -> None:
        if self.persist:
            state.save_json(self.state_file, [s.to_dict() for s in self._skills.values()])

    # ── admission (the gate) ────────────────────────────────────────────────────
    def admit(self, skill: Skill) -> dict:
        """Admit a skill only if it clears the metric gate AND beats any same-named skill."""
        if skill.metric < self.min_metric:
            return {"admitted": False, "reason": f"metric {skill.metric:.4f} < gate {self.min_metric}"}
        existing = self._skills.get(skill.name)
        if existing is not None and skill.metric <= existing.metric:
            return {"admitted": False, "reason": f"does not beat existing ({existing.metric:.4f})"}
        self._skills[skill.name] = skill
        self._save()
        return {"admitted": True, "improved": existing is not None}

    def admit_strategy(self, strategy, metric: float, *, metrics: dict | None = None,
                       source: str = "evolution") -> dict:
        """Convenience: admit an evolved Strategy (T8.1/T8.3) as a skill."""
        d = strategy.to_dict() if hasattr(strategy, "to_dict") else dict(strategy)
        skill = Skill(id=d.get("id", ""), name=d.get("id") or f"skill_{len(self._skills)}",
                      kind="strategy", market=d.get("market", ""), payload=d, metric=metric,
                      metrics=metrics or {}, source=source,
                      generation=d.get("provenance", {}).get("generation", 0))
        return self.admit(skill)

    # ── retrieval ───────────────────────────────────────────────────────────────
    def retrieve(self, *, market: str | None = None, k: int = 5) -> list[Skill]:
        skills = [s for s in self._skills.values()
                  if market is None or s.market.upper() == market.upper()]
        return sorted(skills, key=lambda s: s.metric, reverse=True)[:k]

    def best(self, market: str | None = None) -> Skill | None:
        top = self.retrieve(market=market, k=1)
        return top[0] if top else None

    def __len__(self) -> int:
        return len(self._skills)

    def status(self) -> dict:
        by_market = {}
        for s in self._skills.values():
            by_market[s.market] = by_market.get(s.market, 0) + 1
        return {"n_skills": len(self._skills), "min_metric": self.min_metric,
                "by_market": by_market,
                "top": [{"name": s.name, "market": s.market, "metric": round(s.metric, 4)}
                        for s in self.retrieve(k=5)]}
