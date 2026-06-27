"""Run the grown + routed + guarded brain on REAL multi-asset crypto data.

Fetches BTC/ETH/BNB/SOL (CoinGecko, keyless), builds next-day direction features
per asset, concatenates them (many co-existing regimes), then grows the network
with the guard and reports honest test accuracy vs the naive baseline.

Run:  python3 run_real.py
"""
from __future__ import annotations

import json
import os
import time

import run_brain as rb
from core import registry
from core.brain import GrowingBrain
from data.dataset import MAJORS, make_combined
from eval.golden import accuracy
from nodes.pool import CANDIDATES

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def main(days: int = 365) -> dict:
    registry.reset()
    ds = make_combined(MAJORS, target="direction", days=days)
    Xtr, ytr, Xval, yval, Xg, yg, Xte, yte = rb._split4_shuffled(ds["X"], ds["y"], seed=7)

    brain = GrowingBrain([c[0] for c in CANDIDATES], [c[1] for c in CANDIDATES])
    history = brain.grow(Xtr, ytr, Xval, yval, combiner="router", regime_aware=True,
                         k=25, Xg=Xg, yg=yg, patience=3)
    sel = brain.selected_names()
    base = max(sum(yte) / len(yte), 1 - sum(yte) / len(yte))
    test = accuracy(brain.predict(Xte), yte)

    for i in brain.selected:
        node = brain.trained[i]
        registry.register(node)
        registry.set_metrics(node.name, {"test_accuracy": round(accuracy(node.predict(Xte), yte), 4),
                                         "selected_by_brain": True})

    class _RouterView:
        name, kind = "regime_router", "router"
        summary = "Brain-grown routed combiner on REAL crypto"
        schema = brain.trained[brain.selected[0]].schema
        def fit(self, X, y): return self
        def predict_proba(self, X): return brain.predict_proba(X)
        def predict(self, X): return brain.predict(X)
    registry.register(_RouterView(), upstream=sel)
    registry.set_metrics("regime_router", {"test_accuracy": round(test, 4)})

    snap = registry.snapshot()
    state = {
        "project": "ML Network Brain — REAL crypto (BTC/ETH/BNB/SOL)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": "multi-asset daily next-day direction (CoinGecko)",
                    "n": ds["n"], "features": len(ds["feature_names"]),
                    "coins": ds["coins"], "train": len(Xtr), "val": len(Xval),
                    "guard": len(Xg), "test": len(Xte),
                    "naive_baseline": round(base, 4)},
        "headline_accuracy": round(test, 4),
        "router_accuracy": round(test, 4),
        "selected_nodes": sel,
        "growth_history": history,
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n["name"], "test_accuracy": n["metrics"].get("test_accuracy")}
                    for n in snap["nodes"]],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state, base, test


if __name__ == "__main__":
    s, base, test = main()
    print(f"REAL crypto: {s['dataset']['coins']}  n={s['dataset']['n']} "
          f"(train {s['dataset']['train']} / test {s['dataset']['test']})")
    print(f"Naive baseline: {base:.3f}")
    print("Growth (val drives selection, guard stops):")
    for h in s["growth_history"]:
        mark = "KEPT  " if h.get("kept") else "rolled"
        print(f"  +{h['added']:14} val {h['val_accuracy']:.3f}  guard {h.get('guard_accuracy')}  [{mark}]")
    print(f"Grown+routed brain TEST accuracy: {test:.3f}  (kept {len(s['selected_nodes'])} nodes)")
    print("selected:", s["selected_nodes"])
