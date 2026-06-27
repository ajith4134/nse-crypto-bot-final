"""(ii) Demonstrate the noise-regime router beating either single expert.

Builds a regime dataset (calm then noisy), splits so both regimes appear in
train and test, and compares reservoir-only, recurrence-only, and the
NoiseRegimeRouter — including per-regime accuracy. Writes state.json for the
dashboard.
"""
from __future__ import annotations

import json
import os
import random
import time

from core import registry
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes.base_learners import LogisticRegressionNode
from nodes.chaos_nodes import RecurrenceNode
from nodes.noise_router import NoiseRegimeRouter
from nodes.phase2_nodes import ReservoirNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

CALM = lambda: ReservoirNode(size=30, name="reservoir")
CHAOTIC = lambda: RecurrenceNode(k=20, name="recurrence")
EXPERTS = [CALM, CHAOTIC, lambda: LogisticRegressionNode(name="logreg")]


def _split(X, y, reg, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    tr, te = idx[:cut], idx[cut:]
    pick = lambda S, I: [S[i] for i in I]
    return (pick(X, tr), pick(y, tr), pick(X, te), pick(y, te), pick(reg, te))


def _by_regime(pred, y, reg):
    calm = [(p, t) for p, t, r in zip(pred, y, reg) if r == 0]
    chao = [(p, t) for p, t, r in zip(pred, y, reg) if r == 1]
    ca = accuracy([p for p, _ in calm], [t for _, t in calm]) if calm else None
    ha = accuracy([p for p, _ in chao], [t for _, t in chao]) if chao else None
    return ca, ha


def main() -> dict:
    registry.reset()
    ds = make_regime_dataset(n=1300, noise_hi=0.15)
    Xtr, ytr, Xte, yte, regte = _split(ds["X"], ds["y"], ds["regime"])

    res = CALM().fit(Xtr, ytr)
    rec = CHAOTIC().fit(Xtr, ytr)
    router = NoiseRegimeRouter(EXPERTS, name="noise_router").fit(Xtr, ytr)

    preds = {"reservoir": res.predict(Xte), "recurrence": rec.predict(Xte),
             "noise_router": router.predict(Xte)}
    overall = {k: round(accuracy(p, yte), 4) for k, p in preds.items()}
    per_regime = {k: _by_regime(p, yte, regte) for k, p in preds.items()}

    for node, up in [(res, []), (rec, [])]:
        registry.register(node)
        registry.set_metrics(node.name, {"test_accuracy": overall[node.name]})
    registry.register(router, upstream=["reservoir", "recurrence"])
    registry.set_metrics("noise_router", {"test_accuracy": overall["noise_router"],
                                          "assignment": router.assignment(),
                                          "routed": router.routed})
    snap = registry.snapshot()
    state = {
        "project": "ML Network Brain — Noise-Regime Router (ii)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": "mackey_glass regime shift (calm → noisy)",
                    "n": ds["n"], "features": len(ds["feature_names"]),
                    "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": round(max(sum(yte) / len(yte),
                                                1 - sum(yte) / len(yte)), 4)},
        "headline_accuracy": overall["noise_router"],
        "router_accuracy": overall["noise_router"],
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": k, "test_accuracy": v} for k, v in overall.items()],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    state["_per_regime"] = per_regime
    return state


if __name__ == "__main__":
    s = main()
    print(f"Dataset: {s['dataset']['name']}  test={s['dataset']['test']} "
          f"baseline={s['dataset']['naive_baseline']:.3f}")
    print(f"{'model':>13} | overall | calm  | noisy")
    print("-" * 44)
    for k in ("reservoir", "recurrence", "noise_router"):
        ca, ha = s["_per_regime"][k]
        o = next(h["test_accuracy"] for h in s["history"] if h["name"] == k)
        print(f"{k:>13} |  {o:.3f}  | {ca:.3f} | {ha:.3f}")
    nr = [n for n in s["nodes"] if n["name"] == "noise_router"][0]["metrics"]
    print(f"learned assignment: {nr['assignment']}")
    print(f"routing counts: {nr['routed']}")
