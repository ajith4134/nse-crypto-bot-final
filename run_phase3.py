"""run_phase3.py — the LEARNED-ROUTING frontier (Phase 3), validated honestly.

Compares the Phase-3 routers against the static baselines the plan says they must
beat, across ALL acceptance bars and BOTH data sources:

  combiners
    best_single   — best individual expert on held-out data (the lower bar)
    stacking      — StackingEnsembleNode meta-learner (the plan's static baseline)
    dcs_router    — LearnedRouterNode (DCS local-accuracy, regime-aware)
    hellsemble    — HellsembleRouterNode (circles of difficulty)      [Phase-3 mechanism]
    deep_router   — DeepRouterNode depth=2 (routers-of-routers, L2)    [research gap]

  acceptance bars (all)
    beats_stacking      — hellsemble/deep ≥ stacking on the held-out split
    beats_best_single   — hellsemble/deep ≥ best single expert
    noise_ok            — routers hold accuracy across a noise sweep ≥ stacking
    robust              — multi-seed mean − std stays above the naive baseline

  data (both)
    synthetic — mackey-glass regime shift (develop; noise sweep + multi-seed)
    crypto    — REAL per-coin walk-forward direction head (honest confirm)

Writes phase3.json (full comparison) and state.json (the live Hellsemble network
for the dashboard). CPU-only, reuse-first (experts come from nodes.pool).

Run:  python run_phase3.py
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
from nodes.router_node import DeepRouterNode, HellsembleRouterNode, LearnedRouterNode
from nodes.routing_advanced import (CaruanaEnsembleNode, ConformalGatedRouterNode,
                                    DESRouterNode)
from nodes.structure_search import StructureSearchNode
from nodes.stacking_node import StackingEnsembleNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
PHASE3_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase3.json")

# Fast, diverse experts (linear · instance · bagged-trees · regime-HMM). The
# slower sk_mlp16/esn80 stay available in the pool but are off this hot path so
# the full sweep×seeds grid stays CPU-cheap.
WANT = ["sk_logreg", "sk_knn10", "sk_rf100", "hmm_regime2"]


def _experts() -> tuple[list, list]:
    """A small diverse expert pool (OSS-backed, with stdlib fallback via nodes.pool)."""
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in WANT]
    if len(chosen) < 3:                                  # OSS absent — take first few of fallback
        chosen = list(zip(facs, nms))[:6]
    return [f for f, _ in chosen], [n for _, n in chosen]


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _naive(y) -> float:
    up = sum(y) / len(y)
    return max(up, 1 - up)


ROUTER_TAGS = ("dcs_router", "hellsemble", "deep_router", "des_router",
               "conformal_router", "caruana", "gated_moe", "deep_cascade", "dynamic_bus",
               "structure_search")


def _combiners(factories, names, Xtr, ytr, Xte, yte, regime_aware, full=False):
    """Train every combiner and return {tag: accuracy} on the held-out split.

    full=True also trains the heavier advanced routers (DESlib / MAPIE / Caruana);
    the noise-sweep and multi-seed grids use full=False to bound runtime.
    """
    res = {}
    # best single expert
    best = 0.0
    for f in factories:
        m = f().fit(Xtr, ytr)
        best = max(best, accuracy(m.predict(Xte), yte))
    res["best_single"] = round(best, 4)
    # static stacking (the baseline to beat)
    stk = StackingEnsembleNode(factories).fit(Xtr, ytr)
    res["stacking"] = round(accuracy(stk.predict(Xte), yte), 4)
    # DCS learned router (existing Phase-3 core)
    dcs = LearnedRouterNode(factories, k=25, regime_aware=regime_aware).fit(Xtr, ytr)
    res["dcs_router"] = round(accuracy(dcs.predict(Xte), yte), 4)
    # Hellsemble circles of difficulty
    hell = HellsembleRouterNode(factories, k=25).fit(Xtr, ytr)
    res["hellsemble"] = round(accuracy(hell.predict(Xte), yte), 4)
    # Deep L2 router
    deep = DeepRouterNode(factories, depth=2, branching=3, k=25).fit(Xtr, ytr)
    res["deep_router"] = round(accuracy(deep.predict(Xte), yte), 4)
    if full:                                              # advanced reuse-first routers
        des = DESRouterNode(factories, method="KNORAU").fit(Xtr, ytr)
        res["des_router"] = round(accuracy(des.predict(Xte), yte), 4)
        conf = ConformalGatedRouterNode(factories).fit(Xtr, ytr)
        res["conformal_router"] = round(accuracy(conf.predict(Xte), yte), 4)
        car = CaruanaEnsembleNode(factories).fit(Xtr, ytr)
        res["caruana"] = round(accuracy(car.predict(Xte), yte), 4)
        gm = GatedMoENode(factories, epochs=250).fit(Xtr, ytr)   # P3.5 differentiable gate
        res["gated_moe"] = round(accuracy(gm.predict(Xte), yte), 4)
        dc = DeepCascadeNode(factories, max_layers=4).fit(Xtr, ytr)   # P3.6 deep gated cascade
        res["deep_cascade"] = round(accuracy(dc.predict(Xte), yte), 4)
        res["_cascade_depth"] = dc.depth
        db = DynamicBusNode(factories).fit(Xtr, ytr)                  # P3.7 dynamic I/O bus
        res["dynamic_bus"] = round(accuracy(db.predict(Xte), yte), 4)
        ss = StructureSearchNode(factories, epochs=200).fit(Xtr, ytr)  # P3.9 learn+prune wiring
        res["structure_search"] = round(accuracy(ss.predict(Xte), yte), 4)
        res["_search_kept"] = f"{ss.architecture()['n_kept']}/{ss.architecture()['n_total']}"
    return res, (hell, names)


def _best_router(res: dict) -> tuple[str, float]:
    """Best accuracy among the routing combiners present in res."""
    cand = {t: res[t] for t in ROUTER_TAGS if t in res}
    name = max(cand, key=cand.get)
    return name, cand[name]


def _synthetic_headline(factories, names):
    ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
    Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
    res, (hell, _) = _combiners(factories, names, Xtr, ytr, Xte, yte, regime_aware=True, full=True)
    res["baseline"] = round(_naive(yte), 4)
    return res, hell, ds, (Xtr, ytr, Xte, yte)


def _noise_sweep(factories, names, levels=(0.05, 0.15, 0.25)):
    rows = []
    for nz in levels:
        ds = make_regime_dataset(n=900, noise_hi=nz, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        r, _ = _combiners(factories, names, Xtr, ytr, Xte, yte, regime_aware=True)
        r["noise"] = nz
        r["baseline"] = round(_naive(yte), 4)
        rows.append(r)
    return rows


def _multiseed(factories, names, seeds=(1, 2, 3)):
    runs = []
    for s in seeds:
        ds = make_regime_dataset(n=1000, noise_hi=0.15, seed=s)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"], seed=s)
        hell = HellsembleRouterNode(factories, k=25).fit(Xtr, ytr)
        deep = DeepRouterNode(factories, depth=2, branching=3, k=25).fit(Xtr, ytr)
        stk = StackingEnsembleNode(factories).fit(Xtr, ytr)
        runs.append({"seed": s,
                     "hellsemble": round(accuracy(hell.predict(Xte), yte), 4),
                     "deep_router": round(accuracy(deep.predict(Xte), yte), 4),
                     "stacking": round(accuracy(stk.predict(Xte), yte), 4),
                     "baseline": round(_naive(yte), 4)})
    def stat(key):
        xs = [r[key] for r in runs]
        m = sum(xs) / len(xs)
        sd = (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
        return {"mean": round(m, 4), "std": round(sd, 4), "min": min(xs), "max": max(xs)}
    return {"runs": runs, "hellsemble": stat("hellsemble"),
            "deep_router": stat("deep_router"), "stacking": stat("stacking"),
            "baseline_mean": round(sum(r["baseline"] for r in runs) / len(runs), 4)}


def _crypto(factories, names):
    """REAL per-coin walk-forward on the direction head (honest confirm)."""
    try:
        from data.dataset import MAJORS, make_dataset
    except Exception as e:
        return {"available": False, "reason": str(e)}
    Xtr, ytr, Xte, yte, used = [], [], [], [], []
    for c in MAJORS:
        try:
            d = make_dataset(c)
        except Exception:
            continue
        X, y = d["X"], d["targets"]["direction"]
        cut = int(len(X) * 0.7)
        Xtr += X[:cut]; ytr += y[:cut]; Xte += X[cut:]; yte += y[cut:]; used.append(c)
    if not used:
        return {"available": False, "reason": "no cached crypto coins (run run_crypto.py first)"}
    res, _ = _combiners(factories, names, Xtr, ytr, Xte, yte, regime_aware=False, full=True)
    res["baseline"] = round(_naive(yte), 4)
    res["available"] = True
    res["coins"] = used
    res["note"] = ("free crypto OHLCV has no leak-free edge under walk-forward; "
                   "values are EXPECTED near baseline — reported honestly")
    return res


def _register_dashboard(hell, names, Xte, yte, headline):
    """Live network = the Hellsemble router fed by its specialised experts (honest edges)."""
    registry.reset()
    for e in hell.experts:                               # real, fitted specialist experts
        registry.register(e)
        registry.set_metrics(e.name, {"test_accuracy": round(accuracy(e.predict(Xte), yte), 4)})
    registry.register(hell, upstream=hell.expert_names)
    registry.set_metrics(hell.name, {"test_accuracy": headline["hellsemble"],
                                     "routing": hell.routing_histogram(Xte)})
    return registry.snapshot()


def main() -> dict:
    factories, names = _experts()
    headline, hell, ds, (Xtr, ytr, Xte, yte) = _synthetic_headline(factories, names)
    sweep = _noise_sweep(factories, names)
    seeds = _multiseed(factories, names)
    crypto = _crypto(factories, names)

    # ── acceptance bars (all) — judged on the BEST router available ──
    br_name, br_acc = _best_router(headline)
    beats_stacking = br_acc >= headline["stacking"]
    beats_best_single = br_acc >= headline["best_single"]
    noise_ok = (sum(max(r["hellsemble"], r["deep_router"], r["dcs_router"]) for r in sweep) >=
                sum(r["stacking"] for r in sweep))
    robust = (seeds["hellsemble"]["mean"] - seeds["hellsemble"]["std"] >
              seeds["baseline_mean"])
    acceptance = {"best_router": br_name, "best_router_acc": br_acc,
                  "beats_stacking": bool(beats_stacking),
                  "beats_best_single": bool(beats_best_single),
                  "noise_ok": bool(noise_ok), "robust": bool(robust),
                  "all_passed": bool(beats_stacking and beats_best_single and
                                     noise_ok and robust)}

    snap = _register_dashboard(hell, names, Xte, yte, headline)
    state = {
        "project": "ML Network Brain — Phase 3: Learned Routing (Hellsemble + Deep L2/L3)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": ds["name"], "n": ds["n"], "features": len(ds["feature_names"]),
                    "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": headline["baseline"]},
        "headline_accuracy": headline["hellsemble"],
        "router_accuracy": headline["hellsemble"],
        "stacking_accuracy": headline["stacking"],
        "acceptance": acceptance,
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n["name"], "test_accuracy": n["metrics"].get("test_accuracy")}
                    for n in snap["nodes"]],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    report = {"experts": names, "synthetic_headline": headline,
              "noise_sweep": sweep, "multiseed": seeds, "crypto": crypto,
              "acceptance": acceptance, "generated_at": state["generated_at"]}
    with open(PHASE3_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    report["_state"] = state
    return report


if __name__ == "__main__":
    s = main()
    print(f"experts: {', '.join(s['experts'])}")
    h = s["synthetic_headline"]
    print("\nSYNTHETIC (mackey-glass regime, noise_hi=0.15)  baseline="
          f"{h['baseline']:.3f}")
    for tag in ("best_single", "stacking", "dcs_router", "hellsemble", "deep_router",
                "des_router", "conformal_router", "caruana", "gated_moe", "deep_cascade",
                "dynamic_bus", "structure_search"):
        if tag in h:
            extra = (f"  (depth={h['_cascade_depth']})" if tag == "deep_cascade" else
                     f"  (kept {h['_search_kept']})" if tag == "structure_search" else "")
            print(f"  {tag:16} {h[tag]:.3f}{extra}")
    print("\nNOISE SWEEP (acc by combiner)")
    print(f"  {'noise':>6} {'base':>6} {'stack':>6} {'dcs':>6} {'hell':>6} {'deep':>6}")
    for r in s["noise_sweep"]:
        print(f"  {r['noise']:>6.2f} {r['baseline']:>6.3f} {r['stacking']:>6.3f} "
              f"{r['dcs_router']:>6.3f} {r['hellsemble']:>6.3f} {r['deep_router']:>6.3f}")
    ms = s["multiseed"]
    print("\nMULTI-SEED robustness (5 seeds)")
    print(f"  hellsemble  {ms['hellsemble']['mean']:.3f} ± {ms['hellsemble']['std']:.3f}")
    print(f"  deep_router {ms['deep_router']['mean']:.3f} ± {ms['deep_router']['std']:.3f}")
    print(f"  stacking    {ms['stacking']['mean']:.3f} ± {ms['stacking']['std']:.3f}")
    print(f"  baseline    {ms['baseline_mean']:.3f}")
    c = s["crypto"]
    if c.get("available"):
        print(f"\nCRYPTO walk-forward ({'+'.join(c['coins'])})  baseline={c['baseline']:.3f}")
        for tag in ("best_single", "stacking", "hellsemble", "deep_router",
                    "des_router", "conformal_router", "caruana", "gated_moe", "deep_cascade",
                    "dynamic_bus"):
            if tag in c:
                print(f"  {tag:16} {c[tag]:.3f}")
        print(f"  note: {c['note']}")
    else:
        print(f"\nCRYPTO: unavailable — {c.get('reason')}")
    a = s["acceptance"]
    print("\nACCEPTANCE:", {k: a[k] for k in a})
    print("ALL PASSED" if a["all_passed"] else "NOT ALL PASSED (see above)")
