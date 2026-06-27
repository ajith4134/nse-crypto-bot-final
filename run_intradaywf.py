"""Walk-forward (chronological) on Binance INTRADAY klines — more samples/structure.

Same honest expanding-window protocol as run_realwf, but on intraday data and
across symbols. Default target = volatility.

Run:  python3 run_intradaywf.py [target] [interval]
"""
from __future__ import annotations

import json
import os
import sys

import run_realwf as wf                      # reuse chrono_folds + _split_history
from core.brain import GrowingBrain
from data.binance import fetch_klines, make_kline_dataset
from eval.golden import accuracy
from nodes.pool import CANDIDATES

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intraday_wf.json")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]


def eval_symbol(symbol, interval, target):
    d = make_kline_dataset(symbol, interval, target)
    X, y = d["X"], d["y"]
    rows = []
    for tr_end, te0, te1 in wf.chrono_folds(len(X), n_folds=6):
        Xh, yh = X[:tr_end], y[:tr_end]
        Xte, yte = X[te0:te1], y[te0:te1]
        Xtr, ytr, Xval, yval, Xg, yg = wf._split_history(Xh, yh)
        if min(len(Xtr), len(Xval), len(Xg), len(Xte)) < 5:
            continue
        b = GrowingBrain([c[0] for c in CANDIDATES], [c[1] for c in CANDIDATES])
        b.grow(Xtr, ytr, Xval, yval, combiner="router", regime_aware=True,
               k=min(15, len(Xtr)), Xg=Xg, yg=yg, patience=3)
        base = max(sum(yte) / len(yte), 1 - sum(yte) / len(yte))
        rows.append({"test": round(accuracy(b.predict(Xte), yte), 4),
                     "baseline": round(base, 4), "nodes": len(b.selected)})
    return rows


def main(target="volatility", interval="1h", total=2500) -> dict:
    per, allrows = {}, []
    for s in SYMBOLS:
        try:
            fetch_klines(s, interval, total)          # refresh cache
            rows = eval_symbol(s, interval, target)
            if rows:
                per[s] = rows
                allrows += rows
        except Exception as e:
            print(f"  [warn] {s} skipped: {e}")
    if not allrows:
        return {"error": "no data"}
    accs = [r["test"] for r in allrows]
    n = len(accs)
    mean = sum(accs) / n
    std = (sum((a - mean) ** 2 for a in accs) / n) ** 0.5
    bmean = sum(r["baseline"] for r in allrows) / n
    summary = {"protocol": "intraday walk-forward (chronological, no leakage)",
               "target": target, "interval": interval, "symbols": list(per),
               "folds_total": n, "mean_test": round(mean, 4), "std": round(std, 4),
               "baseline_mean": round(bmean, 4), "edge": round(mean - bmean, 4),
               "per_symbol_mean": {s: round(sum(r["test"] for r in rs) / len(rs), 4)
                                   for s, rs in per.items()}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "folds": allrows}, f, indent=2)
    return summary


if __name__ == "__main__":
    tgt = sys.argv[1] if len(sys.argv) > 1 else "volatility"
    itv = sys.argv[2] if len(sys.argv) > 2 else "1h"
    s = main(target=tgt, interval=itv)
    print(f"Intraday walk-forward — target={s['target']} interval={s['interval']}:")
    for sym, m in s["per_symbol_mean"].items():
        print(f"  {sym:9} mean test {m:.3f}")
    print(f"OVERALL: mean test {s['mean_test']:.3f} ± {s['std']:.3f}  "
          f"vs baseline {s['baseline_mean']:.3f}  ->  edge {s['edge']:+.3f}  "
          f"({s['folds_total']} folds across {len(s['symbols'])} symbols)")
