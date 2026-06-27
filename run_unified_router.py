"""(2) Fold regime-routing into the main learned_router.

Compares the plain DCS router vs the regime-aware router (same code, regime
score folded into the neighbour space) on the calm→noisy regime dataset, and
writes the regime-aware router as the live network for the dashboard.
"""
from __future__ import annotations

import json
import os
import random
import time

from core import registry
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes.base_learners import KNNNode, LogisticRegressionNode
from nodes.chaos_nodes import RecurrenceNode
from nodes.phase2_nodes import ReservoirNode
from nodes.phase2b_nodes import RegimeGatedNode
from nodes.router_node import LearnedRouterNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
POOL = [
    lambda: ReservoirNode(size=30, name="reservoir"),
    lambda: RecurrenceNode(k=20, name="recurrence"),
    lambda: LogisticRegressionNode(name="logreg"),
    lambda: KNNNode(k=15, name="knn"),
    lambda: RegimeGatedNode(gate_idx=8, name="regime_gated"),
]
POOL_NAMES = ["reservoir", "recurrence", "logreg", "knn", "regime_gated"]


def _split(X, y, reg, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return (p(X, idx[:cut]), p(y, idx[:cut]),
            p(X, idx[cut:]), p(y, idx[cut:]), p(reg, idx[cut:]))


def _by_regime(pred, y, reg):
    f = lambda r: accuracy([p for p, _, rr in zip(pred, y, reg) if rr == r],
                           [t for _, t, rr in zip(pred, y, reg) if rr == r])
    return round(f(0), 4), round(f(1), 4)


def main() -> dict:
    registry.reset()
    ds = make_regime_dataset(n=1300, noise_hi=0.15)
    Xtr, ytr, Xte, yte, regte = _split(ds["X"], ds["y"], ds["regime"])

    plain = LearnedRouterNode(POOL, k=25, regime_aware=False).fit(Xtr, ytr)
    aware = LearnedRouterNode(POOL, k=25, regime_aware=True, name="regime_router").fit(Xtr, ytr)

    res = {}
    for tag, r in (("plain_router", plain), ("regime_router", aware)):
        p = r.predict(Xte)
        res[tag] = {"overall": round(accuracy(p, yte), 4),
                    "per_regime": _by_regime(p, yte, regte),
                    "routing": r.routing_histogram(Xte)}

    # live network = regime-aware router fed by the pool
    for f in POOL:
        node = f().fit(Xtr, ytr)
        registry.register(node)
        registry.set_metrics(node.name, {"test_accuracy": round(accuracy(node.predict(Xte), yte), 4)})
    registry.register(aware, upstream=POOL_NAMES)
    registry.set_metrics("regime_router", {"test_accuracy": res["regime_router"]["overall"],
                                           "routing": res["regime_router"]["routing"]})
    snap = registry.snapshot()
    up = sum(yte) / len(yte)
    state = {
        "project": "ML Network Brain — Regime-Aware Router (2)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": "mackey_glass regime shift (calm→noisy)", "n": ds["n"],
                    "features": len(ds["feature_names"]), "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": round(max(up, 1 - up), 4)},
        "headline_accuracy": res["regime_router"]["overall"],
        "router_accuracy": res["regime_router"]["overall"],
        "stacking_accuracy": res["plain_router"]["overall"],
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n["name"], "test_accuracy": n["metrics"].get("test_accuracy")}
                    for n in snap["nodes"]],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    state["_res"] = res
    return state


if __name__ == "__main__":
    s = main()
    print(f"Dataset: {s['dataset']['name']}  test={s['dataset']['test']} "
          f"baseline={s['dataset']['naive_baseline']:.3f}")
    print(f"{'router':>15} | overall | calm  | noisy")
    print("-" * 46)
    for tag in ("plain_router", "regime_router"):
        r = s["_res"][tag]
        print(f"{tag:>15} |  {r['overall']:.3f}  | {r['per_regime'][0]:.3f} | {r['per_regime'][1]:.3f}")
    print("regime_router routing:", s["_res"]["regime_router"]["routing"])
