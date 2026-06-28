"""run_full_network.py — THE FULL trainable network over the ENTIRE node catalog.

Runs the P3.5–3.9 trainable stack over the whole rich node pool (run_multi.domain_pool —
the ~320-node catalog across heads) for EACH output head. Structure search (P3.9) learns
per-node architecture gates and PRUNES the hundreds of candidate nodes down to a per-head
ACTIVE SUBNETWORK; a sparse top-k gate over the survivors predicts. This is the capstone
that turns the validated mechanism into the actual 320-node neural network.

Writes state.json: the direction head's learned active subnetwork in the sigma firing-path
format (per-input top-k) + all-head accuracy/pruning KPIs. CPU-heavy → run in background.

Run:  python run_full_network.py    (then `make dash`)
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

from data.benchmarks import make_benchmark_dataset
from eval.golden import baseline_for, score_head
from run_active import _communities
from run_multi import SYNTH_HEADS, domain_pool
from nodes.structure_search import StructureSearchNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
TOP_K = 5
N_FIRING = 48


def _firing_state(ss: StructureSearchNode, Xte, yte, head_reports) -> dict:
    """Build the sigma active-subnetwork state from a fitted structure-search node
    (the DIRECTION head): kept experts + committed sparse gate's per-input firing."""
    gate = ss._final                                   # committed GatedMoENode over kept experts
    names = gate.expert_names
    E = len(names)
    w, active = gate.active_subnetwork(Xte)
    usage = active.mean(0)
    meanw = w.mean(0)
    coact = (active.astype(float).T @ active.astype(float)) / len(Xte)
    comm = _communities(coact)
    pred = gate.predict(Xte)
    samples = np.linspace(0, len(Xte) - 1, min(N_FIRING, len(Xte))).astype(int)
    firing = [{"i": int(k),
               "active": [int(i) for i in range(E) if active[k, i]],
               "weights": [round(float(w[k, i]), 3) for i in range(E) if active[k, i]],
               "correct": bool(pred[k] == yte[k])} for k in samples]
    # KEPT experts (the learned active subnetwork) — wired to the gate, full colour, firing
    nodes = [{"name": nm, "kind": "base", "community": int(comm[i]), "kept": True,
              "usage": round(float(usage[i]), 3), "mean_weight": round(float(meanw[i]), 4),
              "metrics": {"metric": "fire_rate", "value": round(float(usage[i]), 3)}}
             for i, nm in enumerate(names)]
    edges = [{"source": nm, "target": "gated_moe", "weight": round(float(meanw[i]), 4)}
             for i, nm in enumerate(names)]
    # PRUNED candidates — shown as a dim backdrop (the rest of the catalog the search rejected)
    arch = ss.architecture()
    imp = arch["importance"]
    for nm in arch["pruned"]:
        nodes.append({"name": nm, "kind": "base", "community": -2, "kept": False,
                      "usage": 0.0, "mean_weight": round(float(imp.get(nm, 0.0)), 4),
                      "metrics": {"metric": "importance", "value": round(float(imp.get(nm, 0.0)), 4)}})
    nodes.append({"name": "gated_moe", "kind": "gate", "community": -1, "kept": True, "usage": 1.0,
                  "mean_weight": 1.0, "metrics": {"metric": "accuracy",
                                                  "value": head_reports[0]["value"]}})
    return {"nodes": nodes, "edges": edges,
            "communities": {nm: int(comm[i]) for i, nm in enumerate(names)},
            "firing": firing,
            "active_subnet": {"top_k": TOP_K, "n_experts": E,
                              "mean_active": round(float(active.sum(1).mean()), 2),
                              "n_communities": len(set(comm))}}


def main() -> dict:
    items = domain_pool()                               # (name, factory) over the rich catalog
    factories = [f for _, f in items]
    n_candidates = len(factories)
    ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.03)
    X = ds["X"]
    cut = int(len(X) * 0.7)
    Xtr, Xte = X[:cut], X[cut:]

    head_reports = []
    dir_ss = dir_yte = None
    for h in SYNTH_HEADS:
        ytr = ds["targets"][h.name][:cut]
        yte = ds["targets"][h.name][cut:]
        ss = StructureSearchNode(factories, folds=3, epochs=200, top_k=TOP_K,
                                 min_keep=8, max_keep=18, keep_frac=0.35,
                                 task=h.task, head=h.name,
                                 name=f"search_{h.name}").fit(Xtr, ytr)
        out = ss.predict_output(Xte)
        sc = score_head(h, out, yte)
        bl = baseline_for(h, ytr, yte)
        arch = ss.architecture()
        head_reports.append({"name": h.name, "task": h.task, "metric": sc["metric"],
                             "value": round(sc["value"], 4), "baseline": round(bl["value"], 4),
                             "beats_baseline": bool(sc["value"] > bl["value"]),
                             "n_total": arch["n_total"], "n_kept": arch["n_kept"],
                             "kept": arch["kept"]})
        if h.name == "direction":
            dir_ss, dir_yte = ss, yte

    sig = _firing_state(dir_ss, Xte, dir_yte, [r for r in head_reports if r["name"] == "direction"])
    state = {
        "project": f"ML Network Brain — FULL Trainable Network ({n_candidates}-node catalog → learned active subnetwork)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "structure search over the full catalog · per-head pruning · per-input firing",
        "dataset": {"name": ds["name"], "n": len(X), "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": head_reports[0]["baseline"]},
        "headline_accuracy": head_reports[0]["value"],
        "gate_accuracy": head_reports[0]["value"],
        "n_candidates": n_candidates,
        "heads_full": head_reports,
        **sig,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = main()
    print(f"FULL trainable network → {STATE_PATH}")
    print(f"candidate nodes per head: {s['n_candidates']}")
    print(f"{'head':12} {'task':11} {'value':>7} {'base':>6}  beats?  pruned")
    for h in s["heads_full"]:
        print(f"{h['name']:12} {h['task']:11} {h['value']:7.3f} {h['baseline']:6.3f}"
              f"  {'YES' if h['beats_baseline'] else 'no':4}  {h['n_total']}→{h['n_kept']}")
    print(f"direction active subnetwork: {s['active_subnet']}")
