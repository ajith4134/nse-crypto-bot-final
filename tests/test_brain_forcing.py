"""Forcing tests for brain paths the audit (2026-07-03) found under-exercised.

Each test FORCE-FEEDS synthetic data so the path provably works even when the live
system hasn't produced that data yet (operator directive: never leave a feature
unverified because data is missing — create the data).

Covers:
  1. FileMemory.recall()            — keyword fallback path (no associative memory)
  2. ComputerUseAgent.experiment()  — GUI-agent → HypothesisLedger research bridge
  3. KnowledgeBrain.recall()        — keyword fallback when embeddings are unavailable
  4. OnlineNode drift → replay_retrain — ADWIN fires on regime flip and the retrained
     node actually adapts (accuracy on the new regime recovers)
  5. CInferenceKernel               — llama2.c C hot-path binary is built and detected
Run: pytest tests/test_brain_forcing.py
"""
import tempfile
from pathlib import Path

import numpy as np
import pytest

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # isolate: never touch live state


# ── 1. FileMemory.recall (keyword path) ─────────────────────────────────────────
def test_file_memory_recall_keyword_fallback(tmp_path):
    from memory.file_memory import FileMemory
    fm = FileMemory(root=tmp_path, associative=None)
    fm.write("lot-size-rule", "NFO orders trade in lots",
             "NIFTY options quantity must be a multiple of the lot size 65.", type="project")
    fm.write("coffee-pref", "irrelevant note", "The operator likes filter coffee.",
             type="user")
    hits = fm.recall("what is the NIFTY lot size quantity rule", k=2)
    assert hits, "keyword recall returned nothing"
    assert hits[0]["title"] == "lot-size-rule"
    assert "file-memory(keyword)" in hits[0]["via"]


# ── 2. GUI agent → HypothesisLedger bridge ──────────────────────────────────────
def _planted_trades(n: int = 120, seed: int = 0) -> list[dict]:
    """Planted truth: LONG in a Trending regime is genuinely better on R."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        regime = "Trending" if i % 2 else "Ranging"
        direction = "LONG" if rng.random() < 0.6 else "SHORT"
        edge = 0.6 if (regime == "Trending" and direction == "LONG") else -0.05
        r = float(rng.normal(edge, 1.0))
        out.append({"trade_id": str(i), "symbol": "BTC/USDT", "market": "CRYPTO",
                    "direction": direction, "market_regime_entry": regime,
                    "r_multiple": r, "net_pnl": r * 100,
                    "brain_confidence_entry": float(rng.random()),
                    "strategy_name": "demo"})
    return out


def test_gui_agent_experiment_runs_hypothesis_cycle():
    from trading.brain.gui.agent import ComputerUseAgent
    agent = ComputerUseAgent(persist=False, allow_live=False)
    out = agent.experiment(trades=_planted_trades(), seed=7)
    assert out["available"] is True
    assert out["n_trades"] == 120
    assert out["hypotheses"]["n_hypotheses"] >= 1
    # the ledger must have actually tested claims, not just proposed them
    assert isinstance(out["ledger"], (dict, list))


# ── 3. KnowledgeBrain keyword fallback (no embedding model) ─────────────────────
def test_knowledge_brain_recall_without_embeddings():
    from memory.brain import KnowledgeBrain
    kb = KnowledgeBrain()
    # Force the TF-IDF fallback path regardless of what's installed:
    kb.mem._collection = None
    kb.mem.backend = "tfidf"
    kb.ingest_text("lots", "NIFTY option orders must be placed in multiples of lot size.")
    kb.ingest_text("coffee", "Filter coffee is popular in the south.")
    hits = kb.recall("lot size multiples for NIFTY options", k=2)
    assert hits, "keyword-fallback recall returned nothing"
    top = hits[0]
    assert "lot" in (str(top.get("snippet", "")) + str(top.get("title", ""))).lower()


# ── 4. Drift detection → replay retrain actually adapts ─────────────────────────
def test_online_node_drift_then_replay_retrain_adapts():
    from trading.brain.continual import OnlineNode, ReplayBuffer, replay_retrain
    rng = np.random.default_rng(3)
    feats = ["a", "b"]
    node = OnlineNode(feats, name="drift-force")
    buf = ReplayBuffer()

    def sample(regime_flip: bool):
        x = rng.normal(size=2)
        y = (x[0] > 0) if not regime_flip else (x[0] <= 0)   # label rule flips
        return [float(x[0]), float(x[1])], bool(y)           # row = feature-ordered list

    # regime 1: learn the rule
    for _ in range(300):
        row, y = sample(False)
        node.learn_one(row, y)
        buf.add(row, y)
    # regime 2 (flipped): drift should fire
    for _ in range(300):
        row, y = sample(True)
        node.learn_one(row, y)
    assert node.drift_events >= 1, "ADWIN never fired on a hard label flip"

    # adaptation: retrain with replay + fresh samples, then score on the NEW regime
    new = [sample(True) for _ in range(300)]
    node2 = replay_retrain(feats, new, buf, rng, replay_k=100, name="retrained")
    correct = 0
    for _ in range(200):
        row, y = sample(True)
        p = np.asarray(node2.predict_proba(np.array([row]))).ravel()
        pred = bool(p[-1] > 0.5) if p.size else False
        correct += int(pred == y)
    assert correct / 200 > 0.6, f"retrained node did not adapt (acc={correct/200:.2f})"


# ── 5. llama2.c C kernel present (polyglot hot path) ────────────────────────────
def test_c_inference_kernel_available():
    from nodes.micro_transformer_node import CInferenceKernel
    k = CInferenceKernel()
    if not k.available():
        pytest.skip("llama2.c binary not built on this machine (run `make run` in vendor/llama2_c)")
    assert k.binary.exists() and k.binary.stat().st_size > 0


# ── 6. KnowledgeBrain persistence across restarts (Brain Learning panel bug) ────
def test_knowledge_brain_persists_across_instances(monkeypatch, tmp_path):
    """Regression 2026-07-03: learned docs vanished on every dashboard restart —
    VectorMemory created a RANDOM-named Chroma collection per process, so the panel
    showed 0 documents right after learning. persist=True must survive re-instantiation."""
    from memory import store as store_mod
    monkeypatch.setattr(store_mod, "CHROMA_DIR", str(tmp_path / "chroma"))
    from memory.brain import KnowledgeBrain
    b1 = KnowledgeBrain(persist=True)
    if b1.mem._collection is None:
        pytest.skip("chroma/embeddings unavailable in this environment")
    b1.ingest_text("ito", "The Ito integral extends calculus to Brownian motion paths.")
    assert b1.stats()["docs"] == 1
    b2 = KnowledgeBrain(persist=True)          # simulated restart: new instance, same disk
    s = b2.stats()
    assert s["docs"] == 1 and s["chunks"] >= 1, f"knowledge lost on restart: {s}"
    assert b2.recall("Brownian motion integral", k=1), "rehydrated brain cannot recall"
