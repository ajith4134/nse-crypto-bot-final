"""trading/strategy/self_evolve.py — the lifelong self-evolving strategy loop.

The chat's last "self-evolving agent" gap (research/brain-stitch-gap-map.md, gap #3).
The genetic engine itself already exists (`evolve.py` = DEAP NSGA-II + guardrails) and is
intentionally **gated OFF** (`trading.strategy.control`). What was missing is the
*lifelong controller* that makes the system actually GROW from experience, Voyager-style:

  run_generation -> evolve() a population (gated; force only for the offline demo)
                 -> admit guardrail-PASSED survivors into the SkillLibrary (the growing,
                    persisted skill store) — this is the missing wiring
                 -> record lineage/history (compounds across sessions)
  reevaluate     -> re-score admitted strategy-skills on FRESH data and RETIRE the ones
                    that no longer hold up (skills decay — the loop self-prunes)
  seed (optional)-> bias admission with the HypothesisLedger's confirmed edges, so the
                    brain's research feeds its evolution (cross-capability stitch)

Nothing here weakens the gate: with evolution disabled `run_generation` returns a clean
`{"gated": True}` instead of raising, so the dashboard can show what WOULD happen. The
SkillLibrary + history persist via `trading.state`, so the library compounds over time.

Inputs:  OHLCV frames; optional HypothesisLedger; optional SkillLibrary.
Outputs: generation/admission records (dicts) + a growing persisted SkillLibrary.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.node_protocol import BaseNode, IOSchema
from trading.brain.skills import SkillLibrary
from trading.strategy.control import evolution_enabled
from trading.strategy.evolve import evolve
from trading.strategy.fitness import fitness
from trading.strategy.genome import Strategy

RETIRE_BELOW = 0.0          # re-evaluated score ≤ this → skill retired from the library


class SelfEvolvingLoop:
    """Lifelong controller: evolve → admit winners → re-evaluate/retire → compound."""

    HISTORY_FILE = "self_evolve.json"

    def __init__(self, *, library: SkillLibrary | None = None, persist: bool = True,
                 min_metric: float = 0.0, hypotheses=None):
        self.persist = persist
        self.library = library or SkillLibrary(min_metric=min_metric, persist=persist)
        self.hypotheses = hypotheses               # optional HypothesisLedger seed
        self.history: list[dict] = []
        self._load()

    # ---- persistence ------------------------------------------------------
    def _load(self):
        if not self.persist:
            return
        from trading import state
        self.history = state.load_json(self.HISTORY_FILE, []) or []

    def _save(self):
        if not self.persist:
            return
        from trading import state
        state.save_json(self.HISTORY_FILE, self.history[-100:])

    # ---- one evolution generation-batch -> admit winners ------------------
    def run_generation(self, ohlcv: pd.DataFrame, *, market: str = "CRYPTO",
                       generations: int = 4, pop_size: int = 16, seed: int = 0,
                       n_folds: int = 4, force: bool = False) -> dict:
        """Evolve a population and admit guardrail-passing survivors into the library.

        Honors the gate: if evolution is disabled and `force` is False, returns a
        `{"gated": True, "ran": False}` summary instead of running (no raise).
        """
        if not evolution_enabled() and not force:
            return {"ran": False, "gated": True,
                    "reason": "strategy evolution gated OFF (trading.strategy.control); "
                              "library-first phase. force=True or set_evolution_enabled(True) to run.",
                    "library": self.library.status(), "history": self.history[-10:]}

        result = evolve(ohlcv, market=market, generations=generations, pop_size=pop_size,
                        seed=seed, n_folds=n_folds, force=force)

        admitted = []
        for node in result.promoted:
            strat = getattr(node, "strategy", node)        # StrategyNode wraps a Strategy
            metric, metrics = self._node_metric(node, strat)
            metrics = self._seed_with_hypotheses(metrics, market)
            res = self.library.admit_strategy(strat, metric, metrics=metrics,
                                               source="self_evolve")
            if res.get("admitted"):
                admitted.append({"name": getattr(strat, "id", "?"),
                                 "metric": round(metric, 4),
                                 "improved": res.get("improved", False)})

        rec = {"market": market, "generations": generations,
               "evaluated": result.n_evaluated, "promoted": len(result.promoted),
               "admitted": len(admitted),
               "best_score": result.history[-1]["best_score"] if result.history else None,
               "pbo": (result.pbo or {}).get("pbo"),
               "gen_history": result.history}
        self.history.append(rec)
        self._save()
        return {"ran": True, "gated": False, **rec, "admitted_skills": admitted,
                "library": self.library.status()}

    # ---- re-evaluate admitted strategy-skills on fresh data, retire failures
    def reevaluate(self, ohlcv: pd.DataFrame, *, market: str | None = None,
                   retire_below: float = RETIRE_BELOW, n_folds: int = 4) -> dict:
        """Re-score strategy skills on FRESH data; retire those that no longer hold up."""
        retired, kept = [], []
        feats = None
        for skill in list(self.library.retrieve(market=market, k=10_000)):
            if skill.kind != "strategy":
                continue
            try:
                strat = Strategy.from_dict(skill.payload)
                if feats is None:
                    from trading.strategy.features import compute_features
                    feats = compute_features(ohlcv)
                f = fitness(strat, ohlcv, features=feats, n_folds=n_folds)
                if f.score <= retire_below:
                    self.library._skills.pop(skill.name, None)
                    retired.append({"name": skill.name, "fresh_score": round(f.score, 4)})
                    try:                          # cause-of-death ledger (real retirement)
                        from trading.brain import graveyard as _gy
                        _gy.record_death(skill.name, kind="skill", stage="reeval_retire",
                                         metric=round(f.score, 4), market=market or "",
                                         detail=f"fresh score {f.score:.4f} <= {retire_below}")
                    except Exception:
                        pass
                else:
                    kept.append({"name": skill.name, "fresh_score": round(f.score, 4)})
            except Exception as e:
                kept.append({"name": skill.name, "error": str(e)[:80]})
        if retired:
            self.library._save()
        return {"retired": retired, "kept": kept, "library": self.library.status()}

    # ---- helpers ----------------------------------------------------------
    def _node_metric(self, node, strat) -> tuple[float, dict]:
        """Scalar quality + metrics dict for admission (prefer the evolved fitness score)."""
        fit = getattr(strat, "_fit", None)
        metrics = dict(getattr(node, "metrics", {}) or {})
        if fit is not None:
            metrics.setdefault("score", round(float(fit.score), 6))
            return float(fit.score), metrics
        return float(metrics.get("oos_sharpe_mean", 0.0)), metrics

    def _seed_with_hypotheses(self, metrics: dict, market: str) -> dict:
        """Annotate admission with the brain's confirmed-hypothesis bias (advisory)."""
        if self.hypotheses is None:
            return metrics
        try:
            sup = self.hypotheses.support({"market": market})
            metrics = {**metrics, "hypothesis_bias": sup.get("bias", 0.0)}
        except Exception:
            pass
        return metrics

    # ---- views ------------------------------------------------------------
    def status(self) -> dict:
        last = self.history[-1] if self.history else {}
        return {"enabled": evolution_enabled(), "n_batches": len(self.history),
                "total_admitted": sum(h.get("admitted", 0) for h in self.history),
                "last_batch": last, "library": self.library.status()}

    def to_json(self) -> dict:
        return {**self.status(),
                "history": [{k: h[k] for k in ("market", "generations", "evaluated",
                                               "promoted", "admitted", "best_score", "pbo")
                             if k in h} for h in self.history[-15:]]}


# ============================================================================ #
#  SelfEvolveNode — NodeProtocol face                                           #
# ============================================================================ #
class SelfEvolveNode(BaseNode):
    """NodeProtocol face: predict_proba = P(a profitable evolved strategy is available),
    derived from the best skill metric in the library (squashed to [0,1])."""
    name = "self_evolving_loop"
    kind = "evolution"
    summary = "Lifelong loop: evolve strategies → admit guardrail-passed winners into the growing skill library"
    schema = IOSchema(1, "market context", "p(profitable evolved strategy available)")
    task = "binary"
    head = "y"

    def __init__(self, loop: SelfEvolvingLoop | None = None):
        self.loop = loop or SelfEvolvingLoop(persist=False)

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        best = self.loop.library.best()
        p = float(1.0 / (1.0 + np.exp(-(best.metric if best else 0.0))))
        n = len(X) if hasattr(X, "__len__") else 1
        return [p] * n


def register_self_evolve(loop: SelfEvolvingLoop | None = None) -> SelfEvolveNode:
    """Self-register on the live node registry (dashboard-sync). Idempotent."""
    from core import registry
    node = SelfEvolveNode(loop=loop)
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
