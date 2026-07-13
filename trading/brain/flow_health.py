"""trading/brain/flow_health.py — proves the ONE cognitive loop actually flows (R1).

GOAL.md Pillar 2: every existing feature is a lobe on one loop —
perceive → recall → reason → decide → act → observe → reflect → learn → evolve →
teach-self → back to perceive. This monitor verifies each stage CARRIES REAL DATA by
checking the freshness of the concrete state files that stage writes (honest wiring:
we report file ages measured from disk, never assumptions). An edge is healthy when
both endpoint stages are healthy — that is the "continuous flow" the owner asked for.

Stage → evidence mapping is explicit and auditable below. Thresholds are per-stage
(perception must be minutes-fresh; acting/evolving are naturally sparser). Output
feeds /api/trading/brain/flow and the unified Brain page's connection diagram.
"""
from __future__ import annotations

import time
from pathlib import Path

from memory.neurons import DEFAULT_ROOT as NEURON_ROOT
from trading import state

# stage → (evidence files relative to trading/state unless absolute, freshness budget secs)
STAGES: list[dict] = [
    {"key": "perceive", "label": "Perceive (eyes: UI market, news, candles)",
     "files": ["ui_market.json", "ui_candles.json", "news_memory.json"],
     "budget": 30 * 60},
    {"key": "recall", "label": "Recall (associative + episodic memory)",
     "files": ["associative_notes.json", "decision_episodes.json"],
     "budget": 12 * 3600},
    {"key": "reason", "label": "Reason (fusion, cortex, UQ)",
     "files": ["cortex_shadow.json", "crypto_entry_meta.json", "uq_abstentions.json"],
     "budget": 2 * 3600},
    {"key": "decide", "label": "Decide (funnel, previews, sandbox)",
     "files": ["broker_sense_nse_trades.json", "sandbox_trades.json",
               "micro_policy.json"],
     "budget": 6 * 3600},
    {"key": "act", "label": "Act (orders via APIs; journal entries)",
     "files": ["journal.json"],
     "budget": 48 * 3600},
    {"key": "observe", "label": "Observe (outcomes, x-ray, truth ledger)",
     "files": ["stock_xray.json", "direction_truth_seen.json"],
     "budget": 24 * 3600},
    {"key": "reflect", "label": "Reflect (episodes, mind events)",
     "files": ["decision_episodes.json", "mind_events.json"],
     "budget": 12 * 3600},
    {"key": "learn", "label": "Learn (neuron web, auto-learn log)",
     "files": [str(NEURON_ROOT / "neurons.db"), "learning_log.json"],
     "budget": 24 * 3600},
    {"key": "evolve", "label": "Evolve (self-evolve, instruction lineage)",
     "files": ["self_evolve.json", "instruction_traces.json"],
     "budget": 7 * 24 * 3600},
    {"key": "teach_self", "label": "Teach-self (school exams, curriculum)",
     "files": ["school.json", "self_evaluation.json"],
     "budget": 7 * 24 * 3600},
]


def _age(path: Path, now: float) -> float | None:
    try:
        return max(0.0, now - path.stat().st_mtime)
    except OSError:
        return None


def flow_status(*, now: float | None = None) -> dict:
    """Freshness of every stage + health of every loop edge. Disk truth only."""
    ts = time.time() if now is None else float(now)
    stages = []
    for spec in STAGES:
        evidence = []
        for f in spec["files"]:
            p = Path(f) if str(f).startswith("/") else state.STATE_DIR / f
            a = _age(p, ts)
            evidence.append({"file": p.name, "age_secs": None if a is None else round(a),
                             "exists": a is not None})
        ages = [e["age_secs"] for e in evidence if e["age_secs"] is not None]
        freshest = min(ages) if ages else None
        stages.append({
            "key": spec["key"], "label": spec["label"], "budget_secs": spec["budget"],
            "freshest_secs": freshest,
            "ok": freshest is not None and freshest <= spec["budget"],
            "evidence": evidence,
        })
    edges = []
    for a, b in zip(stages, stages[1:] + stages[:1]):     # …teach_self → perceive
        edges.append({"src": a["key"], "dst": b["key"],
                      "ok": bool(a["ok"] and b["ok"])})
    healthy = sum(1 for s in stages if s["ok"])
    return {"ts": ts, "stages": stages, "edges": edges,
            "healthy_stages": healthy, "total_stages": len(stages),
            "flowing": healthy == len(stages),
            "note": "ages measured from state-file mtimes on disk — no assumptions"}
