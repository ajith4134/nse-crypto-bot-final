"""Shared candidate pool of node families + hyperparameter variants.

Central place the growing brain and robustness runs draw from, so the pool
scales in one spot. Each entry is (factory, name); names are unique.

REUSE-FIRST REALIGNMENT: the pool now draws on the OSS-backed nodes
(`nodes.oss_nodes`) — scikit-learn / XGBoost / LightGBM / ReservoirPy /
hmmlearn / nolds — instead of the hand-rolled stdlib miniatures. The original
pure-Python nodes remain importable (`nodes.base_learners`, `nodes.phase2_nodes`,
`nodes.phase2b_nodes`, `nodes.chaos_nodes`) and are exposed as `STDLIB_CANDIDATES`
so the no-deps path still works and the two can be compared head-to-head. If an
OSS import fails for any reason, that entry is skipped and the stdlib pool is
used as the fallback (graceful degradation, same NodeProtocol either way).
"""
from __future__ import annotations

import os

from nodes.base_learners import DecisionStumpNode, KNNNode, LogisticRegressionNode
from nodes.chaos_nodes import ChaosFeatureNode, RecurrenceNode
from nodes.phase2_nodes import GaussianNBNode, MLPNode, ReservoirNode
from nodes.phase2b_nodes import RandomForestNode, RegimeGatedNode

# ---- pure-stdlib pool (zero-dependency fallback, the original miniatures) ---
STDLIB_CANDIDATES = [
    (lambda: LogisticRegressionNode(name="logreg"), "logreg"),
    (lambda: KNNNode(k=5, name="knn5"), "knn5"),
    (lambda: KNNNode(k=10, name="knn10"), "knn10"),
    (lambda: KNNNode(k=20, name="knn20"), "knn20"),
    (lambda: DecisionStumpNode(name="stump"), "stump"),
    (lambda: MLPNode(hidden=10, epochs=140, name="mlp10"), "mlp10"),
    (lambda: MLPNode(hidden=16, epochs=160, name="mlp16"), "mlp16"),
    (lambda: ReservoirNode(size=40, name="reservoir40"), "reservoir40"),
    (lambda: ReservoirNode(size=80, name="reservoir80"), "reservoir80"),
    (lambda: GaussianNBNode(name="gaussnb"), "gaussnb"),
    (lambda: RandomForestNode(n_trees=20, depth=4, name="rf20"), "rf20"),
    (lambda: RandomForestNode(n_trees=30, depth=5, name="rf30"), "rf30"),
    (lambda: RegimeGatedNode(gate_idx=8, name="regime_gated"), "regime_gated"),
    (lambda: RecurrenceNode(k=20, name="recurrence20"), "recurrence20"),
    (lambda: ChaosFeatureNode(name="chaos_feat"), "chaos_feat"),
]


def _oss_candidates():
    """Build the OSS-backed candidate list; returns [] if the stack is absent."""
    try:
        from nodes import oss_nodes as O
    except Exception:
        return []
    return [
        (lambda: O.logreg_node("sk_logreg"), "sk_logreg"),
        (lambda: O.knn_node(5, "sk_knn5"), "sk_knn5"),
        (lambda: O.knn_node(10, "sk_knn10"), "sk_knn10"),
        (lambda: O.knn_node(20, "sk_knn20"), "sk_knn20"),
        (lambda: O.stump_node("sk_stump"), "sk_stump"),
        (lambda: O.tree_node(5, "sk_tree5"), "sk_tree5"),
        (lambda: O.mlp_node(16, "sk_mlp16"), "sk_mlp16"),
        (lambda: O.mlp_node(32, "sk_mlp32"), "sk_mlp32"),
        (lambda: O.gaussnb_node("sk_gaussnb"), "sk_gaussnb"),
        (lambda: O.svm_node("sk_svm"), "sk_svm"),
        (lambda: O.rf_node(100, None, "sk_rf100"), "sk_rf100"),
        (lambda: O.rf_node(200, None, "sk_rf200"), "sk_rf200"),
        (lambda: O.gbdt_node(100, "sk_gbdt"), "sk_gbdt"),
        (lambda: O.xgboost_node(200, 4, "xgboost"), "xgboost"),
        (lambda: O.lightgbm_node(200, 31, "lightgbm"), "lightgbm"),
        (lambda: O.ReservoirPyNode(units=80, name="esn80"), "esn80"),
        (lambda: O.ReservoirPyNode(units=150, name="esn150"), "esn150"),
        (lambda: O.HMMRegimeNode(2, name="hmm_regime2"), "hmm_regime2"),
        (lambda: O.HMMRegimeNode(3, name="hmm_regime3"), "hmm_regime3"),
        # NOTE: NoldsChaosNode is deliberately NOT in the growth pool. Profiling
        # showed it was ~89% of total pool fit time (it computes sampen/Hurst/DFA
        # per row, 1000x/fit) AND those measures are near-meaningless on short
        # tabular feature rows (they need long sequences). It stays importable
        # (nodes.oss_nodes.NoldsChaosNode) for genuine long time-series use; it
        # just doesn't belong in the per-row tabular growth pool. This is the fix
        # for the slow CI gate — a language rewrite would not have helped, the
        # node is algorithmically expensive + low-value here, not CPU-bound code.
    ]


def _micro_llm_candidates():
    """Cloned-LLM node (vendor/nanogpt): the brain's own micro-transformer (Phase C)."""
    try:
        from nodes.micro_transformer_node import MicroTransformerNode
        import torch  # noqa: F401 — nanoGPT path needs torch
    except Exception:
        return []
    return [(lambda: MicroTransformerNode(name="micro_llm", epochs=30), "micro_llm")]


def _foundation_candidates():
    """Tier-1 foundation / SOTA model nodes (nodes/foundation_nodes.py, groups A–E).
    Returns [] if the OSS stack (torch + chronos/neuralforecast/gpytorch/PyG/tigramite)
    is absent — each node self-guards its own heavy import too."""
    try:
        from nodes import foundation_nodes as F
        import torch  # noqa: F401
    except Exception:
        return []
    cands = [
        (lambda: F.ChronosNode(name="chronos"), "chronos"),
        (lambda: F.TimesFMNode(name="timesfm"), "timesfm"),
        (lambda: F.TinyTimeMixerNode(name="tinytimemixer"), "tinytimemixer"),
        (lambda: F.MoiraiNode(name="moirai"), "moirai"),
        (lambda: F.LagLlamaNode(name="lag_llama"), "lag_llama"),
        (lambda: F.PatchTSTNode(name="patchtst"), "patchtst"),
        (lambda: F.ITransformerNode(name="itransformer"), "itransformer"),
        (lambda: F.TFTNode(name="tft"), "tft"),
        (lambda: F.GPyTorchGPNode(name="gpytorch_gp"), "gpytorch_gp"),
        (lambda: F.GluonTSDeepARNode(name="gluonts_deepar"), "gluonts_deepar"),
        (lambda: F.CrossAssetGNNNode(name="graphsage_xasset"), "graphsage_xasset"),
        (lambda: F.TigramiteCausalNode(name="tigramite_pcmci"), "tigramite_pcmci"),
    ]
    try:                                                    # Tier-2 nodes (nodes/tier2_nodes.py)
        from nodes import tier2_nodes as T2
        cands += [
            (lambda: T2.KANNode(name="kan"), "kan"),
            (lambda: T2.XLSTMNode(name="xlstm"), "xlstm"),
            (lambda: T2.LiquidLTCNode(name="liquid_ltc"), "liquid_ltc"),
            (lambda: T2.NeuralCDENode(name="neural_cde"), "neural_cde"),
            (lambda: T2.QuantLibGreeksNode(name="quantlib_greeks"), "quantlib_greeks"),
            (lambda: T2.MarkovRegimeNode(name="markov_regime"), "markov_regime"),
        ]
    except Exception:
        pass
    try:                                                    # cloud-LLM forecaster (nodes/llm_forecast_node.py)
        from nodes.llm_forecast_node import LLMForecastNode
        cands.append((lambda: LLMForecastNode(name="llm_forecast"), "llm_forecast"))
    except Exception:
        pass
    try:                                                    # Tier-2b remainder (nodes/tier2b_nodes.py)
        from nodes import tier2b_nodes as T2B
        cands += [
            (lambda: T2B.TiDENode(name="tide"), "tide"),
            (lambda: T2B.TimesNetNode(name="timesnet"), "timesnet"),
            (lambda: T2B.TimeMixerNode(name="timemixer"), "timemixer"),
            (lambda: T2B.MambaNode(name="mamba"), "mamba"),
            (lambda: T2B.NormFlowNode(name="normflow"), "normflow"),
            (lambda: T2B.BayesianTorchNode(name="bayesian_nn"), "bayesian_nn"),
            (lambda: T2B.LiNGAMNode(name="lingam"), "lingam"),
        ]
    except Exception:
        pass
    try:                                                    # Tier-3 nodes (nodes/tier3_nodes.py)
        from nodes import tier3_nodes as T3
        cands += [
            (lambda: T3.SB3RLExecNode(name="sb3_ppo_exec"), "sb3_ppo_exec"),
            (lambda: T3.Alpha360Node(name="alpha360"), "alpha360"),
            (lambda: T3.PyGODAnomalyNode(name="pygod_anomaly"), "pygod_anomaly"),
            (lambda: T3.TemporalGraphNode(name="temporal_graph"), "temporal_graph"),
        ]
    except Exception:
        pass
    return cands


def foundation_panel_candidates(panel):
    """Group-F portfolio-optimizer nodes — need a panel dict (returns/close/target),
    so they're built on demand by the panel-aware caller, not the per-row pool."""
    try:
        from nodes import foundation_nodes as F
    except Exception:
        return []
    return [
        (lambda: F.RiskfolioWeightNode(panel), "riskfolio_w"),
        (lambda: F.PyPortfolioOptWeightNode(panel), "pypfopt_w"),
    ]


FOUNDATION_CANDIDATES = _foundation_candidates()


def foundation_factories():
    return [c[0] for c in FOUNDATION_CANDIDATES]


def foundation_names():
    return [c[1] for c in FOUNDATION_CANDIDATES]


_OSS = _oss_candidates()
USING_OSS = bool(_OSS)
if _OSS:
    _OSS.extend(_micro_llm_candidates())
    # Foundation/neural-forecaster nodes are EXPENSIVE to fit (real neural training
    # per candidate) and would slow greedy forward-selection just like NoldsChaosNode.
    # They stay fully importable + available via foundation_factories(); they only join
    # the default growth pool when explicitly opted in. (See percoin/decision-memory
    # gated-on-purpose precedents.)
    if os.environ.get("MLNB_FOUNDATION_NODES") == "1":
        _OSS.extend(FOUNDATION_CANDIDATES)

# OSS pool is primary; falls back to the stdlib miniatures if the stack is absent.
CANDIDATES = _OSS if USING_OSS else STDLIB_CANDIDATES


def factories():
    return [c[0] for c in CANDIDATES]


def names():
    return [c[1] for c in CANDIDATES]
