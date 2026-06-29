"""cognition — Phase P4.5: "Thinking + knowing-what-it-knows".

The brain's reasoning + governance layer, stitched from real, tested OSS:

  - active_inference.ActiveInferenceModel  — pymdp (NumPy Active Inference): beliefs
        updated per ingest; principled surprise (Bayesian) + curiosity (expected info gain).
  - reasoning.ReasoningGraph               — LangGraph ReAct (think→act→observe over the
        brain's own memory) + Tree-of-Thoughts (branch→score→select). Offline-safe.
  - neuro_symbolic.SymbolicReasoner        — pyDatalog traceable logic over the knowledge
        graph (transitive concept reasoning with a full inference trace); scallop adapter
        if scallopy is ever present. CausalAnalyzer — DoWhy effect+refutation, causal-learn
        discovery.
  - calibration.CalibratedAbstainer        — MAPIE / crepes conformal + netcal calibration →
        an abstention threshold that escalates to the human ("asks for help").
  - guardrails.Constitution                — NeMo-Guardrails runtime rails (offline-safe
        programmatic fallback) — a self-audit constitution over the brain's outputs.
  - thinker.Thinker                        — the orchestrator that ties them together and is
        wired into core.brain_agent.BrainAgent (thinking=True path).

CPU-first, reuse-first, offline-safe (deterministic with injected stubs — no network, no
API keys required), per the project conventions and the ml-network-brain-ultra-blueprint.md.
"""

from cognition.active_inference import ActiveInferenceModel
from cognition.affect import Mood
from cognition.calibration import CalibratedAbstainer
from cognition.embodiment import Embodiment
from cognition.guardrails import Constitution
from cognition.identity import Identity
from cognition.neuro_symbolic import CausalAnalyzer, SymbolicReasoner
from cognition.reasoning import ReasoningGraph
from cognition.society import InternalDebate
from cognition.thinker import Thinker

__all__ = [
    "ActiveInferenceModel",
    "ReasoningGraph",
    "SymbolicReasoner",
    "CausalAnalyzer",
    "CalibratedAbstainer",
    "Constitution",
    "Thinker",
    # P4.8 — multimodal + identity + society + affect
    "Mood",
    "Identity",
    "InternalDebate",
    "Embodiment",
]
