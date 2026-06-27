"""Walk-forward (chronological) evaluation on real crypto — the HONEST protocol.

Expanding-window per asset: for each fold the brain trains on the earliest
history, selects nodes on a recent val slice, early-stops on a recent guard
slice, and is tested on the STRICTLY FUTURE window. No shuffling, no leakage.
Aggregated across folds × assets. Compare to the (leaky) shuffled number.

Run:  python3 run_realwf.py
"""
from __future__ import annotations

import json
import os

from core.brain import GrowingBrain
from data.dataset import MAJORS, make_dataset
from eval.golden import accuracy
from nodes.pool import CANDIDATES

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "walkforward.json")


def chrono_folds(n, n_folds=5, init=0.5):
    start = int(n * init)
    test_size = max(1, (n - start) // n_folds)
    folds = []
    for f in range(n_folds):
        tr_end = start + f * test_size
        te0, te1 = tr_end, min(tr_end + test_size, n)
        if te0 >= n:
            break
        folds.append((tr_end, te0, te1))
    return folds


def _split_history(Xh, yh, vfrac=0.15, gfrac=0.15):
    n = len(Xh)
    g0 = int(n * (1 - gfrac))
    v0 = int(n * (1 - gfrac - vfrac))
    return Xh[:v0], yh[:v0], Xh[v0:g0], yh[v0:g0], Xh[g0:], yh[g0:]


def eval_coin(coin, target="direction"):
    d = make_dataset(coin, target)               # cached; chronological order preserved
    X, y = d["X"], d["y"]
    rows = []
    for tr_end, te0, te1 in chrono_folds(len(X)):
        Xh, yh = X[:tr_end], y[:tr_end]
        Xte, yte = X[te0:te1], y[te0:te1]
        Xtr, ytr, Xval, yval, Xg, yg = _split_history(Xh, yh)
        if min(len(Xtr), len(Xval), len(Xg), len(Xte)) < 5:
            continue
        b = GrowingBrain([c[0] for c in CANDIDATES], [c[1] for c in CANDIDATES])
        k = min(15, len(Xtr))
        b.grow(Xtr, ytr, Xval, yval, combiner="router", regime_aware=True,
               k=k, Xg=Xg, yg=yg, patience=3)
        base = max(sum(yte) / len(yte), 1 - sum(yte) / len(yte))
        rows.append({"test": round(accuracy(b.predict(Xte), yte), 4),
                     "baseline": round(base, 4), "nodes": len(b.selected),
                     "n_test": len(Xte)})
    return rows


def main(coins=None, target="direction") -> dict:
    coins = coins or MAJORS
    per_coin = {}
    allrows = []
    for c in coins:
        try:
            rows = eval_coin(c, target)
            if rows:
                per_coin[c] = rows
                allrows += rows
        except Exception as e:
            print(f"  [warn] {c} skipped: {e}")
    if not allrows:
        return {"error": "no data"}
    accs = [r["test"] for r in allrows]
    bases = [r["baseline"] for r in allrows]
    n = len(accs)
    mean = sum(accs) / n
    std = (sum((a - mean) ** 2 for a in accs) / n) ** 0.5
    bmean = sum(bases) / n
    summary = {
        "protocol": "walk-forward (expanding window, chronological, no leakage)",
        "target": target, "coins": list(per_coin), "folds_total": n,
        "mean_test": round(mean, 4), "std": round(std, 4),
        "baseline_mean": round(bmean, 4), "edge": round(mean - bmean, 4),
        "per_coin_mean": {c: round(sum(r["test"] for r in rs) / len(rs), 4)
                          for c, rs in per_coin.items()},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "folds": allrows}, f, indent=2)
    return summary


if __name__ == "__main__":
    import sys
    tgt = sys.argv[1] if len(sys.argv) > 1 else "volatility"
    s = main(target=tgt)
    print(f"Walk-forward (chronological, honest) — target = {s['target']}:")
    for c, m in s["per_coin_mean"].items():
        print(f"  {c:12} mean test {m:.3f}")
    print(f"OVERALL: mean test {s['mean_test']:.3f} ± {s['std']:.3f}  "
          f"vs baseline {s['baseline_mean']:.3f}  ->  edge {s['edge']:+.3f}  "
          f"({s['folds_total']} folds across {len(s['coins'])} assets)")
