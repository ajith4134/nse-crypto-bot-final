"""run_network.py — CORTEX B7: unified network-state generator → network_state.json.

Supersedes run_active.py/run_columns.py for the dashboard VIZ feed (saved-plan
Step 4, design §3): fits a HierarchicalGateNode (T4 — per-input active
subnetwork over Leiden co-activation communities) on REAL market candles from
the freqtrade store (cortex_signal.build_features, next-bar-up labels,
chronological split; synthetic regime data survives only in TINY test mode),
runs a small ReflexArc (T3 — conditional compute: cheap sklearn
tier → deep hgate tier) to capture the real compute log, and writes
network_state.json (repo root, NOT state.json) with the SigmaNetwork superset
schema: every node tagged with column (core.columns), segment+stage
(core.segments), trust (core.trust ledger, when the file exists) and tier.

Honest wiring: edges come from HierarchicalGateNode.graph_snapshot (real trained
gate weights only), firing from firing_records, compute stats from the actual
ReflexArc.compute_log. Nothing is fabricated.

Run:  .venv/bin/python run_network.py [--json]
Env:  ML_COLUMNS_FULL=1     → full catalog pool (heavy; background only)
      ML_NETWORK_TINY=1     → tiny pool + small dataset (tests / smoke)
      ML_NETWORK_STATE_PATH → override the output path (tests)
"""
from __future__ import annotations

import os

# single-threaded BLAS BEFORE numpy/torch import — fitting the pool many times
# deadlocks under multi-threaded OpenMP/BLAS oversubscription (observed: the
# process hangs at 0% CPU). One thread per fit is the researched fix
# (run_columns.py pattern).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import random
import time
from collections import Counter

import numpy as np

from core.columns import column_for, group_factories, layout_for
from core.segments import get_segment, group_by_segment, segment_for, segment_layout
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy, selective_accuracy
from nodes.active_subnet import HierarchicalGateNode
from nodes.reflex import ReflexArc
from run_columns import _pool

STATE_PATH = os.environ.get(
    "ML_NETWORK_STATE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "network_state.json"))
TINY = os.environ.get("ML_NETWORK_TINY") == "1"
N_FIRING = 48
# fast sklearn nodes = the reflex arc's CHEAP tier (tier-1 votes, zero gate training)
CHEAP = ("sk_logreg", "sk_stump", "sk_knn10", "sk_knn5", "sk_tree5", "sk_gaussnb")
TINY_KEEP = ("sk_logreg", "sk_knn10", "sk_tree5", "sk_stump", "sk_gbdt")


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _split_chrono(X, y, frac=0.7):
    """Ordered train/test cut for REAL market data (CANON-30: no shuffle)."""
    cut = int(len(X) * frac)
    return list(X[:cut]), list(y[:cut]), list(X[cut:]), list(y[cut:])


def _real_dataset(n_rows: int, tf_min: int = 15, horizon_bars: int = 16) -> dict:
    """REAL market dataset (no demos): freqtrade 1m candles on disk → resampled
    to `tf_min`-minute bars (1m next-bar direction is near-pure noise; CANON-06
    horizon arbitration) → trading.cortex_signal.build_features (CANON-24
    warm-up gated, SAME features as the live shadow signal) → BARRIER labels
    (CANON-28, ±vol-scaled barriers within `horizon_bars`): a far more learnable
    target than next-bar-up. UNCLEAR bars are dropped (binary UP/DOWN task) and
    the mandatory class-balance check is recorded. Raises if no real data is on
    disk — never silently falls back to synthetic."""
    import pandas as pd
    from data.downloads import locate_freqtrade_1m
    from trading.cortex_signal import FEATURE_NAMES, build_features
    from trading.labels import barrier_label, class_balance
    files = locate_freqtrade_1m()
    pick = ([f for f in files if "BTC_USDT_USDT-1m-futures" in f]
            or [f for f in files if "BTC_USDT" in f] or files)
    if not pick:
        raise RuntimeError("no real 1m candle data on disk — run the freqtrade "
                           "downloader first (never fake a dataset)")
    path = pick[0]
    raw = pd.read_feather(path)
    # 1m → tf_min OHLCV resample (chronological; need headroom for warm-up + drops)
    raw = raw.set_index(pd.to_datetime(raw["date"]))
    df = raw.resample(f"{tf_min}min").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"}).dropna().tail(n_rows * 2 + 400)
    X, close = build_features(df.reset_index())
    if len(X) < 200:
        raise RuntimeError(f"real dataset too short after warm-up gating: {len(X)} rows")
    # vol-scaled barriers: 1.5× the typical |15m move| within a ~4h horizon
    pip = 1.5 * float(np.median(np.abs(np.diff(close))))
    y3 = barrier_label(close, pipdiff=pip, sl_tp_ratio=1.0,
                       horizon_bars=horizon_bars)
    keep = y3 != 1                                     # drop UNCLEAR → binary task
    X, y = X[keep], (y3[keep] == 2).astype(int)        # UP=1, DOWN=0
    X, y = X[-n_rows:], y[-n_rows:]
    bal = class_balance(y)
    parts = os.path.basename(path).split("-1m")[0].split("_")
    pair = f"{parts[0]}/{parts[1]}" + (f":{parts[2]}" if len(parts) > 2 else "")
    return {"name": f"{pair} {tf_min}m barrier±{pip:.0f} (real candles)",
            "n": len(X),
            "X": [list(map(float, r)) for r in X], "y": [int(v) for v in y],
            "features": len(FEATURE_NAMES), "feature_names": list(FEATURE_NAMES),
            "class_balance": bal, "barrier_pip": round(pip, 2),
            "horizon_bars": horizon_bars, "timeframe": f"{tf_min}m",
            "source": f"freqtrade store: {os.path.basename(path)}"}


def _deep_lane_factories() -> list[tuple]:
    """Video-lane deep experts (B2) appended to the real-mode pool: TCN,
    LSTM and torch-MLP lanes (CPU-sized, small epochs). Sklearn stays the
    reflex arc's cheap tier; these land in tier-2 behind the hgate."""
    from nodes.video_lanes import LSTMLaneNode, TCNProbNode, TorchMLPLaneNode
    return [
        ("tcn_lane", lambda: TCNProbNode(lookback=32, channels=(12, 12), epochs=4)),
        ("lstm_lane", lambda: LSTMLaneNode(backcandles=24, units=48, epochs=4)),
        ("mlp_lane_torch", lambda: TorchMLPLaneNode(epochs=20)),
    ]


def _trust_ledger():
    """Real TrustLedger IF its JSON file exists (never fabricate trust)."""
    from core.trust import TrustLedger
    path = os.environ.get("MLNB_TRUST_PATH") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "brain_memory", "node_trust.json")
    if not os.path.exists(path):
        return None, {}
    ledger = TrustLedger(path=path)
    return ledger, ledger.snapshot()


def main() -> dict:
    facs, nms = _pool()
    if TINY:
        keep = [(f, n) for f, n in zip(facs, nms) if n in TINY_KEEP]
        if len(keep) >= 3:
            facs, nms = [f for f, _ in keep], [n for _, n in keep]
    n_rows = 420 if TINY else 1300
    epochs = 40 if TINY else 150
    folds = 2 if TINY else 3

    # REAL market data in production (no demos); the synthetic regime set survives
    # ONLY in TINY mode (test smoke of the generator machinery, labeled as such).
    walk_forward = None
    if TINY:
        ds = make_regime_dataset(n=n_rows, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
    else:
        ds = _real_dataset(n_rows)
        Xtr, ytr, Xte, yte = _split_chrono(ds["X"], ds["y"])   # CANON-30
        # deep video lanes join the pool on real data (tier-2 experts)
        for nm, fac in _deep_lane_factories():
            if nm not in nms:
                facs.append(fac)
                nms.append(nm)
        # WALK-FORWARD out-of-sample evaluation (3 sequential folds pooled):
        # a single chronological cut is hostage to one regime window (observed:
        # confident-wrong on a 4-day trend flip). Train on [0,a), test [a,b),
        # rolling — the pooled preds give the honest headline + selective rows.
        X_all, y_all = ds["X"], ds["y"]
        cuts = [int(len(X_all) * f) for f in (0.4, 0.6, 0.8, 1.0)]
        pooled_p, pooled_y, fold_accs = [], [], []
        for a, b in zip(cuts[:-1], cuts[1:]):
            wf = HierarchicalGateNode(facs, epochs=epochs, folds=2).fit(
                X_all[:a], y_all[:a])
            p = [float(v) for v in wf.predict_proba(X_all[a:b])]
            preds = [1 if v >= 0.5 else 0 for v in p]
            fold_accs.append(round(accuracy(preds, y_all[a:b]), 4))
            pooled_p += p
            pooled_y += list(y_all[a:b])
        wf_preds = [1 if v >= 0.5 else 0 for v in pooled_p]
        share = sum(pooled_y) / len(pooled_y)
        walk_forward = {
            "folds": fold_accs,
            "pooled_accuracy": round(accuracy(wf_preds, pooled_y), 4),
            "pooled_n": len(pooled_y),
            "pooled_baseline": round(max(share, 1 - share), 4),
            "selective": selective_accuracy(pooled_p, pooled_y),
        }

    trust_ledger, trust_snap = _trust_ledger()

    # ── T4: hierarchical per-input active subnetwork (Leiden communities) ────
    hgate = HierarchicalGateNode(facs, epochs=epochs, folds=folds,
                                 trust=trust_ledger).fit(Xtr, ytr)
    acc = round(accuracy(hgate.predict(Xte), yte), 4)
    # selective accuracy (the number that matters for an ABSTAINING trader):
    # walk-forward pooled when available (real mode), else the single holdout.
    if walk_forward is not None:
        selective = walk_forward["selective"]
        headline = walk_forward["pooled_accuracy"]      # honest multi-window number
    else:
        try:
            selective = selective_accuracy(hgate.predict_proba(Xte), yte)
        except Exception:
            selective = []                              # proba unavailable → honest empty
        headline = acc
    snap = hgate.graph_snapshot(Xte)
    firing = hgate.firing_records(Xte, yte, n_samples=N_FIRING)

    # ── T3: small reflex arc — cheap sklearn tier → deep hgate tier ─────────
    cheap = [(f, n) for f, n in zip(facs, nms) if n in CHEAP]
    if not cheap:                                   # full-catalog pool safety
        cheap = list(zip(facs, nms))[:3]
    cheap_facs = [f for f, _ in cheap]
    cheap_names = {n for _, n in cheap}
    deep_facs = list(facs)                          # the hgate tier re-gates the pool

    def _hgate_factory():
        return HierarchicalGateNode(deep_facs, epochs=max(30, epochs // 3),
                                    folds=2, name="hgate_deep")

    # bounded slice keeps the arc (kfold inside GatedMoENode × hgate refits) fast
    n_arc = min(len(Xtr), 380 if TINY else 600)
    n_arc_te = min(len(Xte), 90 if TINY else 160)
    arc = ReflexArc([cheap_facs, [_hgate_factory]], epochs=max(30, epochs // 2),
                    folds=2).fit(Xtr[:n_arc], ytr[:n_arc])
    arc.predict(Xte[:n_arc_te])
    log = [e for e in arc.compute_log if e]
    tier_counts = dict(Counter(int(e["tier"]) for e in log))
    escalated = sum(v for t, v in tier_counts.items() if t > 0)
    compute = {
        "tier_counts": {str(k): int(v) for k, v in sorted(tier_counts.items())},
        "escalation_rate": round(escalated / max(1, len(log)), 4),
        "n_inputs": len(log),
        "exit_kinds": dict(Counter(e["exit"] for e in log)),
    }
    tier_of = {n: 1 for n in cheap_names}           # tier-1 = cheap reflex voters
    # everything the hgate routes (incl. community gates + the hgate itself) = tier 2
    default_tier = 2

    # ── enrich nodes with column / segment / stage / trust / tier ───────────
    nodes = []
    for nd in snap["nodes"]:
        name, kind = nd["name"], nd.get("kind", "base")
        seg_key = segment_for(name, kind)
        nodes.append({
            **nd,
            "kept": True,                            # graph_snapshot = real active graph
            "column": column_for(name, kind),
            "segment": seg_key,
            "stage": get_segment(seg_key).stage,
            "trust": trust_snap.get(name),
            "tier": tier_of.get(name, default_tier),
        })
    edges = [{"source": e["source"], "target": e["target"],
              "weight": round(float(np.clip(e.get("weight", 0.0), 0.0, 1.0)), 4)}
             for e in snap["edges"]]

    up = sum(yte) / len(yte)
    naive = (walk_forward["pooled_baseline"] if walk_forward
             else round(max(up, 1 - up), 4))
    state = {
        "project": "ML Network Brain — CORTEX network (T4 hgate · T3 reflex · trust · segments)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "Leiden-community hgate · reflex conditional compute · trust-biased routing",
        "dataset": {"name": ds["name"], "n": ds["n"], "train": len(Xtr), "test": len(Xte),
                    "naive_baseline": naive,
                    "source": ds.get("source", "synthetic (TINY test mode)"),
                    "real": not TINY,
                    **{k: ds[k] for k in ("timeframe", "barrier_pip", "horizon_bars",
                                          "class_balance") if k in ds}},
        "headline_accuracy": headline,
        "gate_accuracy": acc,
        "selective": selective,
        "walk_forward": walk_forward,
        "nodes": nodes,
        "edges": edges,
        "communities": snap["communities"],
        "active_subnet": snap["active_subnet"],
        "firing": firing,
        "compute": compute,
        "columns": layout_for(group_factories(facs, nms)),
        "segments": segment_layout(group_by_segment(facs, nms)),
        "trust": trust_snap,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CORTEX network-state generator (B7)")
    ap.add_argument("--json", action="store_true",
                    help="print the generated state JSON to stdout")
    args = ap.parse_args()
    s = main()
    if args.json:
        print(json.dumps(s))
    else:
        a = s["active_subnet"]
        c = s["compute"]
        print(f"CORTEX network → {STATE_PATH}")
        print(f"  nodes: {len(s['nodes'])}  edges: {len(s['edges'])}  "
              f"communities: {a['n_communities']}  acc: {s['headline_accuracy']:.3f}")
        print(f"  reflex: tiers {c['tier_counts']}  escalation {c['escalation_rate']:.2f}")
        print(f"  columns: {len(s['columns'])}  segments: {len(s['segments'])}  "
              f"trust entries: {len(s['trust'])}")
