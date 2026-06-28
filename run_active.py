"""run_active.py — P3.8: PER-INPUT ACTIVE SUBNETWORK + sigma.js dashboard state.

Builds a SPARSE (top-k) differentiable gate over a pool of frozen experts so the active
subnetwork is chosen PER INPUT (not statically pruned): only the top-k experts fire on any
given input, so a node useless on average but expert on a few inputs is kept and fired
exactly when needed. Detects co-activation COMMUNITIES (NetworkX modularity over "which
experts fire together") and emits an enriched state.json that the sigma.js dashboard renders
as community-clustered nodes with a live, animated per-input FIRING PATH.

Honest-wiring: edge weights = real mean gate weights; communities, usage and firing samples
are all actual computed values. Run:  python run_active.py   (then `make dash`).
"""
from __future__ import annotations

import json
import os
import random
import time

import numpy as np

from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes import pool
from nodes.gated_node import GatedMoENode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
WANT = ["sk_logreg", "sk_knn5", "sk_knn10", "sk_knn20", "sk_stump", "sk_tree5",
        "sk_mlp16", "sk_gaussnb", "sk_svm", "sk_rf100", "sk_gbdt", "xgboost",
        "lightgbm", "hmm_regime2"]
TOP_K = 4
N_FIRING = 48


def _experts():
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in WANT]
    if len(chosen) < 6:
        chosen = list(zip(facs, nms))[:12]
    return [f for f, _ in chosen], [n for _, n in chosen]


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _communities(coact: np.ndarray) -> list[int]:
    """Greedy-modularity communities over the co-activation graph (NetworkX, reused)."""
    E = coact.shape[0]
    try:
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(range(E))
        for i in range(E):
            for j in range(i + 1, E):
                if coact[i, j] > 0.05:
                    g.add_edge(i, j, weight=float(coact[i, j]))
        comms = nx.community.greedy_modularity_communities(g, weight="weight")
        cid = {}
        for c, members in enumerate(comms):
            for k in members:
                cid[k] = c
        return [cid.get(i, 0) for i in range(E)]
    except Exception:
        return [0] * E


def main() -> dict:
    factories, _ = _experts()
    ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
    Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])

    gate = GatedMoENode(factories, top_k=TOP_K, epochs=250).fit(Xtr, ytr)
    names = gate.expert_names
    E = len(names)
    w, active = gate.active_subnetwork(Xte)               # (n,E) weights, (n,E) bool mask
    acc = round(accuracy(gate.predict(Xte), yte), 4)
    usage = active.mean(0)                                 # per-expert fire frequency
    meanw = w.mean(0)
    coact = (active.astype(float).T @ active.astype(float)) / len(Xte)   # (E,E) both-active
    comm = _communities(coact)

    pred = gate.predict(Xte)
    samples = np.linspace(0, len(Xte) - 1, min(N_FIRING, len(Xte))).astype(int)
    firing = [{"i": int(k),
               "active": [int(i) for i in range(E) if active[k, i]],
               "weights": [round(float(w[k, i]), 3) for i in range(E) if active[k, i]],
               "correct": bool(pred[k] == yte[k])} for k in samples]

    nodes = [{"name": nm, "kind": "base", "community": int(comm[i]),
              "usage": round(float(usage[i]), 3), "mean_weight": round(float(meanw[i]), 4),
              "metrics": {"metric": "fire_rate", "value": round(float(usage[i]), 3)}}
             for i, nm in enumerate(names)]
    nodes.append({"name": "gated_moe", "kind": "gate", "community": -1, "usage": 1.0,
                  "mean_weight": 1.0, "metrics": {"metric": "accuracy", "value": acc}})
    edges = [{"source": nm, "target": "gated_moe", "weight": round(float(meanw[i]), 4)}
             for i, nm in enumerate(names)]

    up = sum(yte) / len(yte)
    state = {
        "project": f"ML Network Brain — Active Subnetwork (P3.8: per-input top-{TOP_K} MoE)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "per-input sparse routing · co-activation communities · live firing path",
        "dataset": {"name": ds["name"], "n": ds["n"], "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": round(max(up, 1 - up), 4)},
        "headline_accuracy": acc, "gate_accuracy": acc,
        "active_subnet": {"top_k": TOP_K, "n_experts": E,
                          "mean_active": round(float(active.sum(1).mean()), 2),
                          "n_communities": len(set(comm))},
        "nodes": nodes, "edges": edges,
        "communities": {nm: int(comm[i]) for i, nm in enumerate(names)},
        "firing": firing,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = main()
    a = s["active_subnet"]
    print(f"Active subnetwork → {STATE_PATH}")
    print(f"  {a['n_experts']} experts · top-{a['top_k']} per input (mean active {a['mean_active']}) "
          f"· {a['n_communities']} communities · gate acc {s['gate_accuracy']:.3f}")
    print(f"  firing samples: {len(s['firing'])}  edges: {len(s['edges'])}")
