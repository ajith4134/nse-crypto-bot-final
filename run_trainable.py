"""run_trainable.py — render the P3.5–3.7 TRAINABLE NETWORK on the dashboard.

Builds the differentiable gate (P3.5), the deep gated cascade (P3.6) and the dynamic
I/O bus (P3.7) on the synthetic regime benchmark and registers the REAL trainable
network into state.json: shared expert nodes → three trainable combiners, each carrying
its own LEARNED wiring (gate weights / attention) on hover. Honest-wiring: every edge is
a true consumes-relationship; the weights shown are the actual trained values.

Run:  python run_trainable.py     (then `make dash` to view)
"""
from __future__ import annotations

import json
import os
import random
import time

from core import registry
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes import pool
from nodes.cascade_node import DeepCascadeNode
from nodes.dynamic_bus import DynamicBusNode
from nodes.gated_node import GatedMoENode
from nodes.stacking_node import StackingEnsembleNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
WANT = ["sk_logreg", "sk_knn10", "sk_rf100", "hmm_regime2"]


def _experts():
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in WANT]
    if len(chosen) < 3:
        chosen = list(zip(facs, nms))[:6]
    return [f for f, _ in chosen]


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def main() -> dict:
    factories = _experts()
    ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
    Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
    acc = lambda node: round(accuracy(node.predict(Xte), yte), 4)

    registry.reset()
    expert_names = []
    for f in factories:                                   # shared frozen experts ("neurons")
        nd = f().fit(Xtr, ytr)
        registry.register(nd)
        registry.set_metrics(nd.name, {"metric": "accuracy", "value": acc(nd)})
        expert_names.append(nd.name)

    # ── the three trainable combiners, each wired to the shared experts ──
    gate = GatedMoENode(factories, epochs=250).fit(Xtr, ytr)
    casc = DeepCascadeNode(factories, max_layers=4).fit(Xtr, ytr)
    bus = DynamicBusNode(factories).fit(Xtr, ytr)
    stk = StackingEnsembleNode(factories).fit(Xtr, ytr)   # honest static reference

    registry.register(gate, upstream=expert_names)
    registry.set_metrics(gate.name, {"metric": "accuracy", "value": acc(gate),
                                     "learned_gate": gate.gate_weights(Xte)})
    registry.register(casc, upstream=expert_names)
    registry.set_metrics(casc.name, {"metric": "accuracy", "value": acc(casc),
                                     "depth": casc.depth, "final_gate": casc.gate_weights(Xte)})
    registry.register(bus, upstream=expert_names)
    registry.set_metrics(bus.name, {"metric": "accuracy", "value": acc(bus),
                                    "source_attention": bus.source_attention(Xte)})

    snap = registry.snapshot()
    up = sum(yte) / len(yte)
    state = {
        "project": "ML Network Brain — Trainable Network (P3.5–3.7: gate · cascade · bus)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "differentiable gate · deep cascade · dynamic I/O bus · backprop on the wiring",
        "dataset": {"name": ds["name"], "feature_names": ds["feature_names"], "n": ds["n"],
                    "train": len(Xtr), "test": len(Xte), "naive_baseline": round(max(up, 1 - up), 4)},
        "headline_accuracy": max(acc(gate), acc(casc), acc(bus)),
        "stacking_accuracy": acc(stk),
        "gate_accuracy": acc(gate),
        "cascade_accuracy": acc(casc), "cascade_depth": casc.depth,
        "bus_accuracy": acc(bus),
        "nodes": snap["nodes"], "edges": snap["edges"],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = main()
    print(f"Trainable network → {STATE_PATH}")
    print(f"  experts: {len(s['nodes']) - 3}  combiners: gate/cascade/bus  edges: {len(s['edges'])}")
    print(f"  gate {s['gate_accuracy']:.3f} · cascade {s['cascade_accuracy']:.3f} "
          f"(depth {s['cascade_depth']}) · bus {s['bus_accuracy']:.3f} · stacking {s['stacking_accuracy']:.3f}")
