"""run_multi.py — the MULTI-OUTPUT network: an output layer of several heads.

Realises the plan's output layer (not one binary label). On the SAME input
features it trains an independent sub-network per OutputHead, covering all three
task types at once. Two data sources:

  synthetic (default)  — Mackey-Glass etc.: heads = direction(binary),
                         regime(multiclass-3), magnitude(regression).
  crypto               — REAL cached crypto (BTC/ETH/BNB/SOL): heads =
                         direction(binary), volatility(binary), magnitude(regression).
                         PER-COIN walk-forward (each coin split past->future, then
                         pooled) — the only honest split for multi-asset series.

Each head gets its own base-node pool (classifiers auto-handle multiclass;
regressors for the regression head) + a per-head meta combiner (soft-vote /
mean) that REALLY consumes the base nodes' predictions. Honest per-task metric
vs per-task baseline. Writes state.json with a real `heads` list + nodes/edges
tagged by head, so the dashboard renders multiple outputs.

NOTE (honesty): free crypto OHLCV has NO leak-free edge under walk-forward
(documented finding); the crypto heads are EXPECTED to sit at/below baseline.
That is reported truthfully — the value here is the multi-output mechanism on
real data, not a fabricated edge.

Run:  python run_multi.py [mackey_glass | logistic_map | crypto]
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np

np.seterr(all="ignore")

from core import registry
from core.heads import TASK_REGRESSION, OutputHead
from data.benchmarks import make_benchmark_dataset
from eval.golden import baseline_for, score_head
from nodes import oss_nodes as O

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
N = 1500

SYNTH_HEADS = [
    OutputHead("direction", "binary", 2, "next-step direction (up/down)"),
    OutputHead("regime", "multiclass", 3, "next-step regime (down/flat/up)"),
    OutputHead("magnitude", "regression", 1, "next-step return (regression)"),
]
CRYPTO_HEADS = [
    OutputHead("direction", "binary", 2, "next-day direction (up/down)"),
    OutputHead("volatility", "binary", 2, "big move next day? (high/low)"),
    OutputHead("magnitude", "regression", 1, "next-day return (regression)"),
]


def cls_pool():
    """Classifier base nodes — the same factories serve binary AND multiclass."""
    return [
        ("sk_logreg", O.logreg_node),
        ("sk_knn10", lambda: O.knn_node(10)),
        ("sk_rf100", lambda: O.rf_node(100, None, "sk_rf100")),
        ("xgboost", O.xgboost_node),
        ("lightgbm", O.lightgbm_node),
        ("sk_mlp16", lambda: O.mlp_node(16)),
    ]


def reg_pool():
    """Regressor base nodes for the regression head."""
    return [
        ("sk_ridge", O.ridge_reg_node),
        ("sk_rf_reg", lambda: O.rf_reg_node(100)),
        ("sk_gbdt_reg", O.gbdt_reg_node),
        ("xgboost_reg", O.xgb_reg_node),
    ]


def domain_pool():
    """Curated FAST best-of-breed across all node families (PhD physics/math/quant/
    signal-processing/control) — every node is task-aware so it serves any head.
    Deliberately EXCLUDES the slow ones (STUMPY ~26s, EVT ~20s, GaussianProcess
    ~12s) which stay importable standalone but off the hot path."""
    from nodes import advanced_nodes as A
    from nodes import dl_nodes as DL
    from nodes import github_feature_nodes as GF
    from nodes import github_predict_nodes as GP
    from nodes import github_t2_feature as G2F
    from nodes import github_t2_predict as G2P
    from nodes import online_nodes as ON
    from nodes import dynamics_nodes as D
    from nodes import frontier_nodes as F
    from nodes import ml_nodes as M
    from nodes import probabilistic_nodes as P
    from nodes import quant_nodes as Q
    from nodes import signal_nodes as S
    from nodes import spectral_nodes as SP
    from nodes import structure_nodes as ST
    return [
        # physics / chaos / nonlinear dynamics
        ("sindy", D.sindy_node), ("rqa", D.rqa_node), ("permentropy", D.permentropy_node),
        ("antropy", D.antropy_node), ("dmd", D.dmd_node), ("transfer_entropy", D.transfer_entropy_node),
        ("multifractal", ST.multifractal_node),
        # signal-in-noise / pattern detection
        ("wavelet", S.wavelet_energy_node), ("emd", S.emd_energy_node), ("ssa", S.ssa_node),
        ("kalman", S.kalman_level_node), ("rmt", S.rmt_signal_node), ("pyod", S.pyod_anomaly_node),
        ("nist", S.nist_randomness_node),
        ("spectral", SP.spectral_node), ("lombscargle", SP.lombscargle_node), ("hilbert", SP.hilbert_node),
        # math / topology / graph / causal / control
        ("catch22", M.catch22_node), ("tda", M.tda_node), ("causal", M.causal_select_node),
        ("control", M.control_sysid_node), ("visibility_graph", ST.visibility_graph_node),
        ("optimal_transport", ST.optimal_transport_node), ("functional_data", SP.functional_data_node),
        ("regime", SP.regime_node),
        # quant / finance
        ("ewma_vol", Q.ewma_vol_node), ("garch_vol", Q.garch_vol_node),
        ("statsforecast", Q.statsforecast_node), ("adf", Q.adf_stationarity_node),
        ("survival", P.survival_hazard_node),
        # probabilistic / symbolic / fuzzy
        ("conformal", P.conformal_node), ("prophet", P.prophet_node),
        ("gplearn", P.gplearn_symbolic_node), ("fuzzy", P.fuzzy_ts_node),
        # frontier: quantum / RL / options
        ("quantum", F.quantum_kernel_node), ("rl_policy", F.rl_policy_node),
        ("option_iv", F.option_iv_node),
        # newly-researched families
        ("hawkes", A.hawkes_node), ("nvar", A.nvar_node), ("signature", A.signature_node),
        ("edm", A.edm_node), ("som", A.som_node), ("elm", A.elm_node),
        ("copula", A.copula_node), ("rocket", A.rocket_node), ("nystroem", A.nystroem_node),
        # deep learning (CPU) — TCN/N-BEATS/TSMixer/GRU/AE fast; N-HiTS heavier
        ("tcn", DL.tcn_node), ("nbeats", DL.nbeats_node), ("tsmixer", DL.tsmixer_node),
        ("gru", DL.gru_node), ("ae_anomaly", DL.ae_anomaly_node), ("nhits", DL.nhits_node),
        # GitHub-projects-as-nodes (Tier 1) — predictors + feature extractors
        ("catboost", GP.catboost_node), ("ngboost", GP.ngboost_node),
        ("skforecast", GP.skforecast_node),
        ("talib", GF.talib_node), ("librosa", GF.librosa_node),
        ("entropyhub", GF.entropyhub_node), ("tsfel", GF.tsfel_node),
        ("fracdiff", GF.fracdiff_node),
        # GitHub Tier 2 — predictors/dynamics (fast subset; flaml/autots standalone)
        ("mlforecast", G2P.mlforecast_node), ("functime", G2P.functime_node),
        ("deeptime", G2P.deeptime_node), ("pomegranate_hmm", G2P.pomegranate_hmm_node),
        ("pgmpy", G2P.pgmpy_bayesnet_node), ("econml", G2P.econml_node),
        ("pykalman", G2P.pykalman_node), ("simdkalman", G2P.simdkalman_node),
        # GitHub Tier 2 — features/anomaly (node2vec standalone — slow)
        ("ssqueeze", G2F.ssqueeze_node), ("scikit_dim", G2F.scikit_dim_node),
        ("feature_engine", G2F.feature_engine_node), ("stockstats", G2F.stockstats_node),
        ("pandas_ta", G2F.pandas_ta_classic_node), ("ta", G2F.ta_node),
        ("adtk", G2F.adtk_anomaly_node),
        # online / incremental learning (River) — the growing-brain fit
        ("river_linear", ON.river_logreg_node), ("river_hoeffding", ON.river_hoeffding_node),
        ("river_arf", ON.river_arf_node),
    ]


class _MetaView:
    """Minimal NodeProtocol-satisfying view of a per-head meta/output node.

    The combiner is a real soft-vote (classification) / mean (regression) over
    the base nodes' predictions, so upstream=base_names is a TRUE dependency.
    """

    def __init__(self, name, head: OutputHead, proba):
        from core.node_protocol import IOSchema
        self.name = name
        self.kind = "meta"
        self.summary = ("soft-vote over base-node class probabilities"
                        if head.is_classification else "mean over base-node predictions")
        self.task = head.task
        self.head = head.name
        self.schema = IOSchema(0, "base-node predictions", f"{head.task} output")
        self._proba = proba

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        return [float(r[-1]) for r in self._proba]

    def predict(self, X):
        return [int(np.argmax(r)) for r in self._proba]


def _combine(outputs, task="binary"):
    """Soft-vote (classification, mean of class-probs) or robust MEDIAN (regression)
    over base predict_output. Median makes the regression meta robust to a single
    exploding regressor on noisy real data (e.g. an outlier return)."""
    arr = [np.asarray(o, dtype=float) for o in outputs]
    return np.median(arr, axis=0) if task == "regression" else np.mean(arr, axis=0)


# --------------------------------------------------------------------------- #
#  Data loaders — each returns (name, feat, Xtr, Xte, head_targets, heads, n)
#  where head_targets[head.name] = (ytr, yte).
# --------------------------------------------------------------------------- #
def _load_synthetic(benchmark: str, n: int):
    ds = make_benchmark_dataset(benchmark, n=n, noise=0.05)
    X, feat = ds["X"], ds["feature_names"]
    cut = int(len(X) * 0.7)
    Xtr, Xte = X[:cut], X[cut:]
    ht = {h.name: (ds["targets"][h.name][:cut], ds["targets"][h.name][cut:])
          for h in SYNTH_HEADS}
    return (f"{benchmark} (synthetic, known process)", feat, Xtr, Xte, ht,
            SYNTH_HEADS, len(X))


def _load_crypto(train_frac: float = 0.7):
    """Per-coin walk-forward: split each coin's history past->future, then pool
    the train halves and the test halves (no cross-coin leakage)."""
    from data.dataset import MAJORS, make_dataset
    Xtr, Xte, feat, used = [], [], None, []
    acc = {h.name: [[], []] for h in CRYPTO_HEADS}
    for c in MAJORS:
        try:
            d = make_dataset(c)
        except Exception as e:                      # missing cache / parse error
            print(f"  [skip {c}: {e}]")
            continue
        feat = d["feature_names"]
        Xc = d["X"]
        cut = int(len(Xc) * train_frac)
        Xtr += Xc[:cut]; Xte += Xc[cut:]; used.append(c)
        for h in CRYPTO_HEADS:
            yv = d["targets"][h.name]
            acc[h.name][0] += yv[:cut]
            acc[h.name][1] += yv[cut:]
    if not used:
        raise SystemExit("no cached crypto coins found — run `python run_crypto.py` "
                         "or data.dataset.ensure() to fetch first.")
    ht = {k: (v[0], v[1]) for k, v in acc.items()}
    return (f"REAL crypto walk-forward ({'+'.join(used)})", feat, Xtr, Xte, ht,
            CRYPTO_HEADS, len(Xtr) + len(Xte))


def _split_dataset(ds: dict, cap: int = 2500, train_frac: float = 0.7):
    """Chronological train/test split of a dataset dict {X, targets, feature_names,
    name} into the (name, feat, Xtr, Xte, head_targets, heads, n) tuple the runner
    expects. Capped to the most recent `cap` rows for tractability."""
    X, feat, tg = ds["X"], ds["feature_names"], ds["targets"]
    if len(X) > cap:
        X = X[-cap:]
        tg = {k: v[-cap:] for k, v in tg.items()}
    cut = int(len(X) * train_frac)
    Xtr, Xte = X[:cut], X[cut:]
    ht = {h.name: (tg[h.name][:cut], tg[h.name][cut:]) for h in SYNTH_HEADS}
    return ds["name"], feat, Xtr, Xte, ht, SYNTH_HEADS, len(X)


def _load_external(source: str):
    from data.external import make_external_dataset
    return _split_dataset(make_external_dataset(source))


def main(arg: str = "mackey_glass", n: int = N, pool: str = "core") -> dict:
    from data.external import EXTERNAL_SOURCES
    if arg == "crypto":
        name, feat, Xtr, Xte, head_targets, heads, n = _load_crypto()
        source = "crypto"
    elif arg in EXTERNAL_SOURCES:
        name, feat, Xtr, Xte, head_targets, heads, n = _load_external(arg)
        source = arg
    elif arg == "mtf":
        from data.binance import make_mtf_dataset
        name, feat, Xtr, Xte, head_targets, heads, n = _split_dataset(make_mtf_dataset())
        source = "mtf"
    elif arg == "orderbook":
        from data.orderbook import make_orderbook_dataset
        name, feat, Xtr, Xte, head_targets, heads, n = _split_dataset(make_orderbook_dataset())
        source = "orderbook"
    elif arg == "mtf_indian":
        from data.external import make_mtf_indian
        name, feat, Xtr, Xte, head_targets, heads, n = _split_dataset(make_mtf_indian())
        source = "mtf_indian"
    else:
        name, feat, Xtr, Xte, head_targets, heads, n = _load_synthetic(arg, n)
        source = "synthetic"
    stack = ("ALL node families — physics · chaos · signal-in-noise · quant · math · control · ML"
             if pool == "rich" else
             "scikit-learn · XGBoost · LightGBM (multi-head: binary · multiclass · regression)")

    registry.reset()
    head_reports = []
    for h in heads:
        ytr, yte = head_targets[h.name]
        items = domain_pool() if pool == "rich" else (
            reg_pool() if h.task == TASK_REGRESSION else cls_pool())
        base_names, base_outs = [], []
        for base_name, factory in items:
            try:                                          # one bad node can't kill the run
                nd = factory()
                nd.head, nd.task = h.name, h.task
                nd.name = f"{base_name}@{h.name}"
                nd.fit(Xtr, ytr)
                out = nd.predict_output(Xte)
                if not out or len(out[0]) != h.n_outputs:   # ragged/degenerate -> skip
                    print(f"  [skip {base_name}@{h.name}: output width "
                          f"{len(out[0]) if out else 0} != {h.n_outputs}]")
                    continue
                sc = score_head(h, out, yte)
                registry.register(nd)
                registry.set_metrics(nd.name, {"metric": sc["metric"], "value": round(sc["value"], 4)})
                base_names.append(nd.name)
                base_outs.append(out)
            except Exception as e:
                print(f"  [skip {base_name}@{h.name}: {type(e).__name__}: {e}]")

        if not base_outs:
            print(f"  [head {h.name}: no usable base nodes — skipped]")
            continue
        meta_out = _combine(base_outs, h.task)
        meta_sc = score_head(h, meta_out.tolist(), yte)
        meta = _MetaView(f"meta@{h.name}", h, meta_out)
        registry.register(meta, upstream=base_names)
        registry.set_metrics(meta.name, {"metric": meta_sc["metric"], "value": round(meta_sc["value"], 4)})
        out_node = _MetaView(f"ŷ:{h.name}", h, meta_out)
        out_node.kind = "output"
        registry.register(out_node, upstream=[meta.name])

        base = baseline_for(h, ytr, yte)
        head_reports.append({
            "name": h.name, "task": h.task, "metric": meta_sc["metric"],
            "value": round(meta_sc["value"], 4), "baseline": round(base["value"], 4),
            "beats_baseline": bool(meta_sc["value"] > base["value"]), "n_base_nodes": len(base_names),
        })

    snap = registry.snapshot()
    state = {
        "project": f"ML Network Brain — MULTI-OUTPUT ({source})",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": stack,
        "dataset": {"name": name, "n": n, "features": len(feat), "feature_names": feat,
                    "train": len(Xtr), "test": len(Xte), "source": source, "pool": pool},
        "heads": head_reports, "multi_output": True,
        "nodes": snap["nodes"], "edges": snap["edges"],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    rest = [a for a in sys.argv[1:] if a != "rich"]
    arg = rest[0] if rest else "mackey_glass"
    pool = "rich" if "rich" in sys.argv[1:] else "core"
    s = main(arg, pool=pool)
    print(f"MULTI-OUTPUT network on: {s['dataset']['name']}  ({len(s['heads'])} heads, "
          f"train={s['dataset']['train']} test={s['dataset']['test']})")
    print(f"{'head':12} {'task':11} {'metric':9} {'value':>7} {'baseline':>9}  beats?")
    for h in s["heads"]:
        print(f"{h['name']:12} {h['task']:11} {h['metric']:9} {h['value']:7.3f} {h['baseline']:9.3f}"
              f"  {'YES' if h['beats_baseline'] else 'no'}  ({h['n_base_nodes']} nodes)")
    print(f"total nodes: {len(s['nodes'])}  edges: {len(s['edges'])}")
