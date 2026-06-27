"""Phase 4 demo: build the knowledge brain, ingest docs, and recall.

Ingests the project's own markdown docs (+ a few Wikipedia summaries if the
network is up), then runs semantic recall queries. Writes knowledge_state.json
for the dashboard's /knowledge view.

Run:  python3 run_knowledge.py
"""
from __future__ import annotations

import json
import os
import urllib.request

from memory.brain import KnowledgeBrain

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "knowledge_state.json")

DOCS = ["CONVENTIONS.md", "PROJECT_BRIEF.md", "ml-network-master-plan.md",
        "ml-network-research.md", "ml-network-related-topics.md"]
WIKI = ["Reservoir computing", "Mixture of experts", "Order book", "Symbolic regression"]
QUERIES = [
    "how does the regime-aware router pick which node to use?",
    "what is reservoir computing good for?",
    "how do we evaluate a model without data leakage?",
    "rules for the auto-generated index file",
]


def _wiki(title: str) -> str | None:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "_")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ml-brain/0.1"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read()).get("extract")
    except Exception:
        return None


def main() -> dict:
    brain = KnowledgeBrain()
    for d in DOCS:
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            brain.ingest_file(p)
    for w in WIKI:
        ext = _wiki(w)
        if ext:
            brain.ingest_text(f"wiki: {w}", ext)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(brain.dashboard_snapshot(), f, indent=2)

    answers = {q: brain.recall(q, k=3) for q in QUERIES}
    return {"stats": brain.stats(), "answers": answers}


if __name__ == "__main__":
    s = main()
    print("Knowledge brain stats:", json.dumps(s["stats"]))
    for q, hits in s["answers"].items():
        print(f"\nQ: {q}")
        for h in hits:
            print(f"  [{h['score']:.3f}] {h['title']}  (concepts: {', '.join(h['concepts'][:4])})")
            print(f"       {h['snippet'][:130]}…")
