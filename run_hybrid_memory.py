"""run_hybrid_memory.py — Phase P4.2 Hybrid human memory OFFLINE demo.

Drives `memory.hybrid_memory.HybridMemory` end to end, fully OFFLINE and deterministic
(NO network, NO API keys, NO embedding model). HybridMemory fuses FOUR real, reused
projects — our code is glue:

  1. Stanford Generative-Agents memory stream — VENDORED (vendor/generative_agents_memory,
     Apache-2.0): observations with LLM-rated importance, retrieve by recency+importance+
     relevance, and REFLECT (synthesize higher-level insights). The retrieval engine.
  2. Letta (pip, real) — tiered core-memory blocks (persona/human), embedded/offline.
  3. mem0 (pip, real) — optional semantic store, gated on an LLM key (off here).
  4. HumanMemory (ours) — the one piece no library does: Ebbinghaus decay + auto_dream
     FORGETTING/consolidation.

A real KnowledgeBrain downloads an embedding model on first use (= network) and the LLM
keys hit the cloud, so this demo composes HybridMemory over a tiny **stub brain** and a
**stub LLM chat** (deterministic importance/synthesis), and **injects** the epoch clock
(`now`) + datetimes (`created` / `curr_time`) so decay, retrieval and dream are fully
reproducible. The injected stub LLM also exercises the REAL GA importance_fn/synthesize_fn
paths (offline they would otherwise fall back to the vendored heuristics).

What it demonstrates:
  1. add() — store titled memories; GA rates importance/poignancy (LLM-driven, shown).
  2. recall() — fused hits from BOTH the GA stream ('generative-agents') and the
     decay-aware channel ('vector').
  3. reflect() — real GA reflection producing DEDUPED higher-level insights.
  4. dream() — Ebbinghaus forgetting/consolidation (forgets trivia, keeps important).
  5. status() — components: vendored GA + real Letta + mem0-gated + Ebbinghaus.

`build_demo_hybrid_memory()` returns a JSON-able snapshot {add, recall, reflect, dream,
status} for the dashboard. Offline + deterministic.

Usage:
    .venv/bin/python run_hybrid_memory.py
"""
from __future__ import annotations

import datetime
import json
import sys
import warnings

warnings.filterwarnings("ignore")  # keep the demo output clean

from memory.hybrid_memory import HybridMemory

DAY = 86400.0
NOW0 = 1_700_000_000.0  # fixed epoch anchor → deterministic decay/dream
DT0 = datetime.datetime(2023, 11, 14, 22, 13, 20)  # fixed datetime anchor for GA nodes

# Deterministic offline memories (trading/research themed). Texts are kept token-disjoint
# so the stub brain's keyword recall targets the intended memory per query.
_MEMORIES = [
    ("Stop loss discipline",
     "Cutting losses quickly preserved capital during the volatile crash; strict risk "
     "management saved the trading account from ruin.",),
    ("Position sizing rule",
     "Never allocate more than two percent of portfolio equity to any single speculative "
     "trade; disciplined sizing controls drawdown.",),
    ("Fed rate decision",
     "The central bank hiked interest rates sharply; equities sold off across every sector "
     "during the macro shock.",),
    ("Bitcoin halving cycle",
     "Historically the halving precedes a multi month crypto bull run as new supply "
     "issuance drops by half.",),
    ("Office coffee machine",
     "The breakroom espresso maker broke down again this morning; a minor annoyance.",),
    ("Lobby parking slot",
     "Parked in bay forty seven beside the elevator today; an utterly trivial detail.",),
]

# Deterministic LLM importance ratings (1-10) keyed by a distinctive token in each text.
_RATINGS = {
    "risk": 9, "sizing": 8, "interest": 8, "halving": 7, "espresso": 2, "parking": 2,
    "bay": 2,
}


class _StubMem:
    """Mimics KnowledgeBrain.mem: a `chunks` dict {id: {title, text}}."""

    def __init__(self) -> None:
        self.chunks: dict[str, dict] = {}


class _StubBrain:
    """Offline stand-in for KnowledgeBrain — deterministic keyword recall, no model/network.

    Exposes the surface HybridMemory + HumanMemory need: `.mem.chunks`, `ingest_text()`
    and `recall(query, k)` returning {id, title, score, snippet} hits."""

    def __init__(self) -> None:
        self.mem = _StubMem()

    def ingest_text(self, title: str, text: str) -> str:
        self.mem.chunks[title] = {"title": title, "text": text}
        return title  # doc_id

    @staticmethod
    def _toks(s: str) -> set[str]:
        return {t.strip(".,;").lower() for t in s.split() if t.strip(".,;")}

    def recall(self, query: str, k: int = 4) -> list[dict]:
        q = self._toks(query)
        scored = []
        for cid, ch in self.mem.chunks.items():
            overlap = len(q & self._toks(ch["title"] + " " + ch["text"]))
            if overlap:
                scored.append((overlap, cid, ch))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{"id": cid, "title": ch["title"], "score": float(ov),
                 "snippet": ch["text"][:120].replace("\n", " ")}
                for ov, cid, ch in scored[:k]]


class _StubLLM:
    """Deterministic offline stand-in for core.llm chat — exercises the REAL GA
    importance_fn + synthesize_fn paths without any network call."""

    def __call__(self, messages) -> str:
        sysmsg = (messages[0].get("content", "") if messages else "").lower()
        user = messages[-1].get("content", "") if messages else ""
        if "importance" in sysmsg or "poignancy" in sysmsg:
            low = user.lower()
            for token, score in _RATINGS.items():
                if token in low:
                    return str(score)
            return "5"
        if "insight" in sysmsg or "synthesize" in sysmsg:
            # Fixed insights → identical across GA focal points, so HybridMemory.reflect
            # must DEDUP them down to a unique set.
            return ("Risk management and disciplined position sizing protect trading capital\n"
                    "Macro rate decisions drive cross asset volatility\n"
                    "Risk management and disciplined position sizing protect trading capital")
        return ""


def _build() -> HybridMemory:
    """Fresh HybridMemory over a stub brain + stub LLM, at epoch NOW0 (offline)."""
    brain = _StubBrain()
    return HybridMemory(brain=brain, llm_chat=_StubLLM(), use_mem0=False)


def build_demo_hybrid_memory() -> dict:
    """JSON-able snapshot {add, recall, reflect, dream, status}. Offline + deterministic."""
    hm = _build()

    # 1) add() several titled memories — GA rates importance/poignancy (via stub LLM).
    added = []
    for i, (title, text) in enumerate(_MEMORIES):
        created = DT0 + datetime.timedelta(minutes=i)
        added.append(hm.add(title, text, created=created, now=NOW0))

    # Rehearse a couple of salient memories so the decay channel ranks them (spacing effect).
    curr = DT0 + datetime.timedelta(hours=1)
    for _ in range(3):
        hm.recall("risk management stop loss capital sizing", k=3, now=NOW0, curr_time=curr)

    # 2) recall() — fused GA ('generative-agents') + decay channel ('vector').
    recall_hits = []
    for h in hm.recall("risk management stop loss capital sizing", k=4, now=NOW0, curr_time=curr):
        recall_hits.append({
            "title": h.get("title"),
            "via": h.get("via", "vector"),               # untagged decay-channel hits = vector
            "snippet": (h.get("snippet") or "")[:80],
            "importance": h.get("importance"),
            "strength": h.get("strength"),
            "tier": h.get("tier"),
        })
    channels = sorted({h["via"] for h in recall_hits})

    # 3) reflect() — real GA reflection, DEDUPED insights.
    reflect_time = DT0 + datetime.timedelta(hours=2)
    reflect = hm.reflect(curr_time=reflect_time, now=NOW0)

    # 4) dream() — Ebbinghaus consolidation 60 days later: forget trivia, keep important.
    before = sorted(hm.human.meta.keys())
    dream = hm.dream(NOW0 + 60 * DAY)
    after = sorted(hm.human.meta.keys())
    dream_report = {
        **dream,
        "forgotten_titles": [t for t in before if t not in after],
    }

    # 5) status() — component roster.
    status = hm.status(NOW0 + 60 * DAY)

    return {"add": added, "recall": recall_hits, "recall_channels": channels,
            "reflect": reflect, "dream": dream_report, "status": status}


def main() -> int:
    def _hdr(s: str) -> None:
        print("\n" + s + "\n" + "-" * min(len(s), 72))

    print("run_hybrid_memory.py — P4.2 Hybrid memory (offline, deterministic)")
    print("Components are REAL reused code: Stanford Generative-Agents memory stream "
          "(VENDORED, Apache-2.0), Letta (pip), mem0 (pip, gated) + our Ebbinghaus decay.")

    demo = build_demo_hybrid_memory()

    _hdr("1. add() — GA rates importance/poignancy (LLM-driven)")
    for a in demo["add"]:
        print(f"  {a['title']:<24} importance={a['importance']}  "
              f"poignancy={a['poignancy']}  mem0={a['mem0']}")
    assert any(a["poignancy"] for a in demo["add"]), "GA must assign poignancy"
    assert len({a["poignancy"] for a in demo["add"]}) > 1, "LLM ratings should vary"
    print("  ✔ importance/poignancy rated by the (stub) LLM via the real GA stream.")

    _hdr("2. recall() — fused GA ('generative-agents') + decay channel ('vector')")
    for h in demo["recall"]:
        print(f"  [{h['via']:<17}] {str(h['title']):<22} "
              f"imp={h['importance']} strength={h['strength']} tier={h['tier']}")
    print(f"  channels present: {demo['recall_channels']}")
    assert "generative-agents" in demo["recall_channels"], "recall must include GA hits"
    assert "vector" in demo["recall_channels"], "recall must include the decay channel"
    print("  ✔ recall fused BOTH the GA stream and the decay-aware channel — verified.")

    _hdr("3. reflect() — real GA reflection, deduped insights")
    r = demo["reflect"]
    print(f"  reflected={r.get('reflected')}")
    for ins in r.get("insights", []):
        print(f"    - {ins}")
    assert r.get("reflected"), "reflection should produce insights"
    assert len(r["insights"]) == len(set(r["insights"])), "insights must be deduped"
    print("  ✔ insights synthesized and deduplicated — verified.")

    _hdr("4. dream() — Ebbinghaus forget trivia, consolidate important")
    d = demo["dream"]
    print(f"  forgotten={d['forgotten']} promoted={d['promoted']} "
          f"consolidated={d['consolidated']} remaining={d['remaining']}")
    print(f"  forgotten_titles: {d['forgotten_titles']}")

    _hdr("5. status() — components (GA vendored + Letta + mem0-gated + Ebbinghaus)")
    print(f"  {json.dumps(demo['status'], default=str)}")
    assert "generative-agents(vendored real)" in demo["status"]["components"]

    _hdr("6. build_demo_hybrid_memory() — JSON-able dashboard snapshot")
    print(json.dumps(demo, indent=2, default=str)[:800] + "  ...")

    print("\n✅ P4.2 hybrid memory demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
