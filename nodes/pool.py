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
        (lambda: O.NoldsChaosNode("nolds_chaos"), "nolds_chaos"),
    ]


_OSS = _oss_candidates()
USING_OSS = bool(_OSS)

# OSS pool is primary; falls back to the stdlib miniatures if the stack is absent.
CANDIDATES = _OSS if USING_OSS else STDLIB_CANDIDATES


def factories():
    return [c[0] for c in CANDIDATES]


def names():
    return [c[1] for c in CANDIDATES]
