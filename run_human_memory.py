"""run_human_memory.py — Phase P4.2 (Human-like memory) OFFLINE demo.

Drives `memory.human_memory.HumanMemory` end to end, fully OFFLINE and deterministic
(NO network, NO API keys, NO embedding model). HumanMemory wraps a KnowledgeBrain with
human dynamics; a real KnowledgeBrain downloads an embedding model on first use (=
network), so this demo composes HumanMemory over a tiny **stub brain** and **injects**
the epoch clock (`now`) so the Ebbinghaus decay and the dream pass are fully reproducible.

What it demonstrates:

  1. recall() — decay-aware recall: each hit carries a `strength` (retention) and `tier`.

  2. Ebbinghaus decay curve — strength of a REINFORCED memory (recalled several times)
     vs a comparable NEVER-recalled one at increasing `now` offsets. Stability grows with
     recall count + importance, so the reinforced memory decays measurably slower.

  3. dream(60 days) — a consolidation/sleep pass: it FORGETS only never-recalled,
     low-importance, decayed trivia, while important and rehearsed memories CONSOLIDATE
     (are protected / promoted) and survive.

  4. status() — tier counts (core / recall / archival).

`build_demo_human_memory()` returns a JSON-able snapshot {recall, decay_curve, dream,
status} for the dashboard. Offline + deterministic.

Usage:
    .venv/bin/python run_human_memory.py
"""
from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")  # keep the demo output clean

from memory.human_memory import HumanMemory

DAY = 86400.0
NOW0 = 1_700_000_000.0  # fixed epoch anchor → fully deterministic decay/dream

# Deterministic offline memories. Texts are kept token-disjoint so the stub brain's
# keyword recall targets exactly one memory per query (reproducible reinforcement).
_MEMORIES = [
    ("Daughter first steps",
     "Watched my daughter take her first wobbly steps across the living room. "
     "An unforgettable milestone.",
     0.95),                                   # deeply important → protected even if unused
    ("Wedding anniversary date",
     "Our wedding anniversary falls in autumn; we celebrate every single year.",
     0.90),                                   # important → protected
    ("Project launch deadline",
     "The product ships at quarter end; engineering must freeze the release candidate.",
     0.50),                                   # ordinary, but REHEARSED below → consolidates
    ("Grocery list Tuesday",
     "Buy milk eggs spinach yoghurt; ran out midweek.",
     0.50),                                   # never-recalled control for the decay curve
    ("Random radio jingle",
     "A catchy insurance advert tune stuck briefly after the morning commute.",
     0.30),                                   # never-recalled trivia → forgotten by dream
    ("License plate glimpse",
     "Glanced at a passing car number plate at the junction; gone instantly.",
     0.20),                                   # never-recalled trivia → forgotten by dream
]

_REINFORCED = "Project launch deadline"
_CONTROL = "Grocery list Tuesday"


class _StubMem:
    """Mimics KnowledgeBrain.mem: just a `chunks` dict {id: {title, text}}."""

    def __init__(self) -> None:
        self.chunks: dict[str, dict] = {}


class _StubBrain:
    """Offline stand-in for KnowledgeBrain — deterministic keyword recall, no model/network.

    Exposes the surface HumanMemory needs: `.mem.chunks` and `.recall(query, k)` returning
    {title, score, snippet} hits (the same shape KnowledgeBrain.recall returns)."""

    def __init__(self, memories: list[tuple[str, str, float]]) -> None:
        self.mem = _StubMem()
        for title, text, _imp in memories:
            self.mem.chunks[title] = {"title": title, "text": text}

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
        return [{"title": ch["title"], "score": float(ov),
                 "snippet": ch["text"][:120].replace("\n", " ")}
                for ov, cid, ch in scored[:k]]


def _build() -> HumanMemory:
    """Fresh HumanMemory over a stub brain, with injected importance, at epoch NOW0."""
    brain = _StubBrain(_MEMORIES)
    hm = HumanMemory(brain, now=NOW0)
    for title, _text, imp in _MEMORIES:
        hm.remember(title, now=NOW0, importance=imp)
    return hm


def build_demo_human_memory() -> dict:
    """JSON-able snapshot {recall, decay_curve, dream, status}. Offline + deterministic."""
    hm = _build()

    # Rehearse the reinforced memory a few times near NOW0 (spacing effect builds stability).
    for _ in range(3):
        hm.recall("project launch deadline release", k=2, now=NOW0)

    # 1) decay-aware recall (carries strength + tier).
    recall_hits = hm.recall("project launch deadline release", k=3, now=NOW0)

    # 2) Ebbinghaus decay curve: reinforced vs comparable never-recalled control.
    decay_curve = []
    for days in (1, 7, 30, 90):
        t = NOW0 + days * DAY
        decay_curve.append({
            "day": days,
            "reinforced": round(hm.strength(_REINFORCED, t), 4),
            "never_recalled": round(hm.strength(_CONTROL, t), 4),
        })

    # 3) dream consolidation 60 days later: forgets only trivia, keeps important/rehearsed.
    before = sorted(hm.meta.keys())
    dream = hm.dream(NOW0 + 60 * DAY)
    after = sorted(hm.meta.keys())
    dream_report = {
        **dream,
        "forgotten_titles": [t for t in before if t not in after],
        "kept_titles": after,
    }

    # 4) tier counts.
    status = hm.status(NOW0 + 60 * DAY)

    return {"recall": recall_hits, "decay_curve": decay_curve,
            "dream": dream_report, "status": status}


def main() -> int:
    def _hdr(s: str) -> None:
        print("\n" + s + "\n" + "─" * min(len(s), 72))

    print("run_human_memory.py — P4.2 Human-like memory (offline, deterministic)")

    demo = build_demo_human_memory()

    _hdr("1. recall() — decay-aware (strength + Letta tier per hit)")
    for h in demo["recall"]:
        print(f"  {h['title']:<26} strength={h.get('strength')}  "
              f"tier={h.get('tier')}  score={h.get('score')}")

    _hdr("2. Ebbinghaus decay — reinforced vs never-recalled retention")
    print(f"  {'day':>4}  {'reinforced':>11}  {'never_recalled':>14}")
    for row in demo["decay_curve"]:
        flag = "  ← reinforced decays slower" if row["reinforced"] > row["never_recalled"] else ""
        print(f"  {row['day']:>4}  {row['reinforced']:>11}  {row['never_recalled']:>14}{flag}")
    assert all(r["reinforced"] >= r["never_recalled"] for r in demo["decay_curve"]), \
        "reinforced memory should retain at least as much as the never-recalled control"
    assert any(r["reinforced"] > r["never_recalled"] for r in demo["decay_curve"]), \
        "reinforced memory should visibly decay slower than the never-recalled control"
    print("  ✔ reinforced memory decays slower than the never-recalled one — verified.")

    _hdr("3. dream(60 days) — consolidation: forget trivia, keep important/rehearsed")
    d = demo["dream"]
    print(f"  forgotten={d['forgotten']} promoted={d['promoted']} "
          f"consolidated={d['consolidated']} remaining={d['remaining']}")
    print(f"  forgotten_titles: {d['forgotten_titles']}")
    print(f"  kept_titles:      {d['kept_titles']}")
    trivia = {"Random radio jingle", "License plate glimpse"}
    assert trivia.issubset(set(d["forgotten_titles"])), "dream must forget never-recalled trivia"
    assert "Daughter first steps" in d["kept_titles"], "dream must protect important memories"
    assert "Wedding anniversary date" in d["kept_titles"], "dream must protect important memories"
    assert _REINFORCED in d["kept_titles"], "dream must keep rehearsed memories"
    assert not (set(d["forgotten_titles"]) & {"Daughter first steps", "Wedding anniversary date",
                                              _REINFORCED}), "dream must not forget protected memories"
    print("  ✔ dream forgot only never-recalled trivia; kept important + rehearsed — verified.")

    _hdr("4. status() — tier counts (core / recall / archival)")
    print(f"  {json.dumps(demo['status'], default=str)}")

    _hdr("5. build_demo_human_memory() — JSON-able dashboard snapshot")
    print(json.dumps(demo, indent=2, default=str)[:800] + "  ...")

    print("\n✅ P4.2 human-like memory demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
