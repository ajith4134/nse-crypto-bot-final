"""cognition/thinker.py — the P4.5 orchestrator: "thinks, stays calibrated, asks for help".

``Thinker`` chains the five P4.5 layers into one deliberate cognitive cycle over the brain's
own memory — this is what ``BrainAgent(thinking=True)`` runs instead of a one-shot reply:

    reason (ReAct/ToT over memory)
      → score confidence from the gathered evidence
      → calibrate + decide (conformal): ANSWER, or ABSTAIN and escalate to the human
      → audit against the constitution (secrets-safe / grounded / honest / non-harmful)
      → reflect: active-inference surprise + curiosity on the query's topic
      → optionally enrich with symbolic (traceable) related concepts

Every piece is a real reused engine (LangGraph, pymdp, pyDatalog, DoWhy/causal-learn, MAPIE,
netcal, NeMo-Guardrails). Offline-safe and deterministic with injected stubs — no network, no
API key — so it unit-tests exactly like P4.1–P4.4. ``from_brain`` wires it straight onto a
``KnowledgeBrain`` (topics = its top concepts).
"""
from __future__ import annotations

from cognition.active_inference import ActiveInferenceModel
from cognition.calibration import CalibratedAbstainer
from cognition.guardrails import Constitution
from cognition.neuro_symbolic import SymbolicReasoner
from cognition.reasoning import ReasoningGraph, _terms


class Thinker:
    def __init__(self, brain=None, *, reasoner: ReasoningGraph | None = None,
                 active_inference: ActiveInferenceModel | None = None,
                 symbolic: SymbolicReasoner | None = None,
                 abstainer: CalibratedAbstainer | None = None,
                 constitution: Constitution | None = None,
                 recall_k: int = 4):
        self.brain = brain
        self.reasoner = reasoner or ReasoningGraph(brain, recall_k=recall_k)
        self.active_inference = active_inference
        self.symbolic = symbolic
        self.abstainer = abstainer or CalibratedAbstainer()
        self.constitution = constitution or Constitution()
        self.recall_k = recall_k

    # ── construction from a brain ───────────────────────────────────────────────────
    @classmethod
    def from_brain(cls, brain, *, topics: list[str] | None = None, recall_k: int = 4,
                   abstainer: CalibratedAbstainer | None = None) -> "Thinker":
        topics = topics or cls._top_concepts(brain)
        ai = ActiveInferenceModel(topics) if len(topics) >= 2 else None
        sym = SymbolicReasoner.from_brain(brain)
        return cls(brain, active_inference=ai, symbolic=sym, abstainer=abstainer,
                   recall_k=recall_k)

    @staticmethod
    def _top_concepts(brain, n: int = 6) -> list[str]:
        try:
            snap = brain.graph.snapshot()
            concepts = [nd.get("label") or nd.get("id", "").split(":")[-1]
                        for nd in snap.get("nodes", []) if nd.get("type") == "concept"]
            return [c for c in concepts if c][:n]
        except Exception:
            return []

    # ── confidence from evidence ────────────────────────────────────────────────────
    @staticmethod
    def _confidence(recalled: list[dict], k: int) -> float:
        """Bounded [0,1] confidence: evidence breadth × score concentration."""
        if not recalled:
            return 0.0
        scores = [max(float(h.get("score", 0.0)), 0.0) for h in recalled]
        total = sum(scores) or 1.0
        concentration = max(scores) / total          # 1.0 = one dominant hit; →0 = diffuse
        breadth = min(1.0, len(recalled) / max(k, 1))
        # a confident answer has BOTH a clear top match and corroborating breadth
        return round(min(1.0, 0.5 * concentration + 0.5 * breadth), 4)

    # ── the cognitive cycle ─────────────────────────────────────────────────────────
    def think(self, query: str, *, strategy: str = "react", enrich_symbolic: bool = True) -> dict:
        # 1) deliberate reasoning over memory
        reasoning = self.reasoner.reason(query, strategy=strategy)
        recalled = reasoning.get("recalled", [])

        # 2) confidence → 3) calibrated decision (answer vs abstain+escalate)
        confidence = self._confidence(recalled, self.recall_k)
        decision = self.abstainer.decide(confidence)
        abstained = decision["abstain"]

        # 4) compose the user-facing answer honestly
        if abstained:
            answer = ("I'm not confident enough to answer this reliably "
                      f"(confidence {decision['calibrated_confidence']}). Escalating to you "
                      "— could you confirm or add context?")
        else:
            answer = reasoning.get("answer", "")

        # 5) constitution audit (secrets / grounded / honest / harmful)
        audit = self.constitution.audit(answer, grounded_in=recalled, abstained=abstained)
        final_answer = audit["safe_text"]
        if not audit["ok"]:
            # secrets already redacted in safe_text; for other hard violations, fail safe
            if any("non-harmful" in v or "honest-uncertainty" in v for v in audit["violations"]):
                final_answer = "[withheld by the brain's constitution] " + \
                    ("Escalating to a human." if abstained else "Cannot answer that safely.")

        # 6) reflect: active-inference surprise + curiosity on this query's topic
        reflection = self._reflect(query)

        # 7) symbolic enrichment: traceable related concepts
        symbolic = self._symbolic(query) if (enrich_symbolic and self.symbolic) else None

        return {
            "query": query,
            "answer": final_answer,
            "abstained": abstained,
            "escalate_to_human": decision["escalate_to_human"],
            "confidence": confidence,
            "calibrated_confidence": decision["calibrated_confidence"],
            "calibration": {"engine": decision["engine"], "reason": decision["reason"],
                            "prediction_set": decision["prediction_set"]},
            "reasoning": {"strategy": reasoning.get("strategy"),
                          "steps": reasoning.get("steps") or reasoning.get("branches"),
                          "evidence": [h.get("title") for h in recalled]},
            "surprise": reflection.get("surprise"),
            "curiosity": reflection.get("most_curious"),
            "reflection": reflection,
            "symbolic": symbolic,
            "constitution": {"ok": audit["ok"], "violations": audit["violations"],
                             "engine": audit["engine"]},
        }

    def _reflect(self, query: str) -> dict:
        if self.active_inference is None:
            return {}
        ql = query.lower()
        for t in self.active_inference.topics:
            if t.lower() in ql:
                return self.active_inference.observe(t)
        # no known topic in the query → just report what it's most curious about
        return {"surprise": None, "most_curious": self.active_inference.most_curious_topic()}

    def _symbolic(self, query: str) -> dict | None:
        ts = _terms(query)
        for t in ts:
            t2 = t.replace("-", "_")
            res = self.symbolic.related(t2)
            if res.get("related"):
                return {"concept": res["start"], "related": res["related"][:6],
                        "trace": {k: v for k, v in list(res["trace"].items())[:3]},
                        "engine": res["engine"]}
        return None

    def status(self) -> dict:
        return {
            "reasoner": self.reasoner.status(),
            "active_inference": self.active_inference.status() if self.active_inference else None,
            "symbolic": self.symbolic.status() if self.symbolic else None,
            "calibration": self.abstainer.status(),
            "constitution": self.constitution.status(),
        }
