"""trading/brain/ultra.py — glue singleton for the brain ultra-upgrade (Phases A–E).

One place the dashboard/API reads the whole upgraded stack from (honest wiring):

  • AssociativeMemory (memory/associative.py) — HippoRAG PPR + A-MEM evolution, persisted
    under trading/state so recall survives restarts.
  • FileMemory (memory/file_memory.py) — Claude-style one-fact-per-file notes in
    brain_memory/ at the repo root, indexed into the associative graph on load.
  • MicroTransformerNode + CInferenceKernel (nodes/micro_transformer_node.py) — the cloned
    nanoGPT/llama2.c micro-LLM; status reports availability + last training losses.
  • perception (trading/brain/perception.py) — Docling/Surya document reading.
  • ContinualLearner (trading/brain/continual.py) — Avalanche Replay+EWC.

All lazy: nothing heavy is imported until the first status()/recall() call.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE = Path(__file__).resolve().parent.parent / "state"

_file_memory = None
_last_llm_node = None          # set by callers that train the micro-LLM


def file_memory():
    """Singleton FileMemory over brain_memory/ + persisted associative index."""
    global _file_memory
    if _file_memory is None:
        from memory.associative import AssociativeMemory
        from memory.file_memory import FileMemory

        def _llm(messages):
            try:
                from core import llm
                # hard wall-clock budget: memory writes run inline on trading-loop
                # threads, and an unbounded failover chain is n_providers × 45s
                return llm.chat(messages, timeout=20, total_timeout=45)
            except Exception:
                return None
        _STATE.mkdir(parents=True, exist_ok=True)
        assoc = AssociativeMemory(llm_chat=_llm, path=_STATE / "associative_notes.json")
        _file_memory = FileMemory(_ROOT / "brain_memory", associative=assoc)
    return _file_memory


def remember(name: str, description: str, body: str, type: str = "lesson") -> dict:
    return file_memory().write(name, description, body, type=type)


def recall(query: str, k: int = 5) -> list[dict]:
    return file_memory().recall(query, k=k)


def set_llm_node(node) -> None:
    global _last_llm_node
    _last_llm_node = node


def status() -> dict:
    fm = file_memory()
    out = {"file_memory": fm.status(), "associative": fm.assoc.status()}
    try:
        from nodes.micro_transformer_node import CInferenceKernel
        kern = CInferenceKernel()
        out["micro_llm"] = {
            "nanogpt_node": "nodes.micro_transformer_node.MicroTransformerNode "
                            "(vendor/nanogpt @3adf61e)",
            "trained": _last_llm_node is not None,
            "last_losses": getattr(_last_llm_node, "losses", [])[-5:],
            "c_kernel_built": kern.available(),
        }
    except Exception as e:
        out["micro_llm"] = {"error": str(e)[:120]}
    try:
        from trading.brain import perception
        out["perception"] = perception.status()
    except Exception as e:
        out["perception"] = {"error": str(e)[:120]}
    try:
        import avalanche
        out["continual"] = {"engine": f"avalanche-lib {avalanche.__version__} (Replay+EWC)",
                            "worldmodel_online": "MarketWorldModel.update_online "
                                                 "(dreamer-continual-replay)"}
    except Exception as e:
        out["continual"] = {"error": str(e)[:120]}
    try:
        from trading.brain.researcher import AutonomousResearcher
        out["researcher"] = AutonomousResearcher().status() | {
            "deep_engine": "gpt-researcher (installed; enabled with OPENAI_API_KEY or "
                           "GPT_RESEARCHER=1) + Reflexion critique"}
    except Exception as e:
        out["researcher"] = {"error": str(e)[:120]}
    return out
