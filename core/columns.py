"""Column taxonomy — the SINGLE SOURCE OF TRUTH that groups the ~320 nodes.

The prediction-graph is organised into COLUMNS. A column is a family of nodes
that answer the SAME function in DIFFERENT ways (e.g. the "trees" column holds
decision-stump / random-forest / gradient-boost nodes — same job, different
method, different outputs). This is both a COMPUTE structure (each column is
ensembled by its own intra-column gate, see nodes.column_node) and the DASHBOARD
layout (columns render left→right; honest-wiring shows the real learned weights).

Design goals it serves (all four the user asked for):
  * clarity/extensibility — one obvious place a node belongs; the dashboard mirrors it.
  * open to future nodes   — a pattern MATCHER assigns nodes by name/kind, and an
    `other` catch-all guarantees ANY newly-added node lands in a column with no
    code change (add a pattern later to promote it out of `other`).
  * CPU-first + quality     — small same-family columns are cheap to gate and keep
    diversity across columns for the cross-column router (nodes.column_network).

A column is chosen by the FIRST matching rule (order matters: specific → generic).
Matching is deliberately over node NAME substrings + `kind`, because that is the
metadata every NodeProtocol node already carries (core.node_protocol).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    """One functional column of the network.

    key        : stable identifier (used in state.json / dashboard / gate names).
    title      : human label for the dashboard header.
    desc       : what function this column performs.
    color      : dashboard accent (Dark-Pro palette); purely cosmetic.
    name_subs  : node-name substrings that route a node into this column.
    kinds      : node `kind` values that route a node into this column.
    """
    key: str
    title: str
    desc: str
    color: str
    name_subs: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()

    def matches(self, name: str, kind: str) -> bool:
        n, k = name.lower(), (kind or "").lower()
        return any(s in n for s in self.name_subs) or k in self.kinds


# ── the ordered column stack (specific families first, catch-all last) ──────
# Order is also the default LEFT→RIGHT dashboard order and the cascade layer order.
# Rules are matched top→down, so more specific / higher-priority families come first
# (e.g. river_* → online BEFORE linear/trees; boosting BEFORE trees). name_subs list the
# actual catalog node-name substrings (run_multi.domain_pool) so the real ~108-node catalog
# lands in meaningful columns, not 'other'.
COLUMNS: list[Column] = [
    Column("boosting", "Gradient Boosting",
           "Gradient-boosted ensembles — XGBoost, LightGBM, CatBoost, NGBoost.",
           "#f6c445",
           name_subs=("xgb", "xgboost", "lightgbm", "lgbm", "catboost", "ngboost", "gbdt",
                      "boost")),
    Column("online", "Online / Streaming",
           "Incremental learners that update per-sample — River adaptive forest/Hoeffding/linear.",
           "#00b3a4",
           name_subs=("river", "hoeffding", "_arf", "online")),
    Column("symbolic", "Symbolic / Equation",
           "Equation & program discovery — genetic programming, sparse dynamics (SINDy).",
           "#b5e853",
           name_subs=("gplearn", "sindy", "symbolic", "genetic")),
    Column("forecasting", "Forecasting / Sequence NN",
           "Time-series forecasters — N-BEATS/N-HiTS/TSMixer/TCN, RNNs, Prophet, statsforecast.",
           "#c678dd",
           name_subs=("deeptime", "nbeats", "nhits", "tsmixer", "tcn", "gru", "lstm", "prophet",
                      "forecast", "functime", "nvar", "skforecast", "statsforecast",
                      "mlforecast")),
    Column("anomaly", "Anomaly / Change",
           "Outlier & change-point detection — PyOD, ADTK, autoencoder anomaly, BOCPD, surrogate.",
           "#ff6b6b",
           name_subs=("pyod", "adtk", "anomaly", "bocpd", "surrogate", "matched_filter",
                      "outlier", "changepoint")),
    Column("spectral", "Spectral / Decomposition",
           "Frequency, wavelet & matrix decompositions — EMD/VMD/EWT/SSQ, Hilbert, ICA, PCA, SSA, DMD.",
           "#5aa9ff",
           name_subs=("wavelet", "ewt", "emd", "vmd", "ssqueeze", "hilbert", "spectral",
                      "lombscargle", "savgol", "decomp", "ssa", "dmd", "ica", "denoise",
                      "robust_pca", "dict_learn", "fracdiff", "fourier", "pca", "librosa")),
    Column("causal", "Causal / Probabilistic",
           "Causal inference & probabilistic structure — EconML, pgmpy, copulas, Hawkes, survival, OT.",
           "#ff9f43",
           name_subs=("causal", "econml", "pgmpy", "copula", "hawkes", "survival",
                      "optimal_transport", "bayes")),
    Column("chaos_structure", "Chaos / Complexity",
           "Nonlinear complexity — entropy, recurrence/RQA, multifractal, TDA, visibility graph, RMT.",
           "#8fbf5f",
           name_subs=("chaos", "lyapunov", "entropy", "antropy", "recurrence", "rqa", "tda",
                      "multifractal", "visibility", "edm", "ncd", "signature", "scikit_dim",
                      "fuzzy", "rmt", "nist", "stoch_resonance", "surrogate_test",
                      "zero_one")),
    Column("ts_features", "TS Features / Shapes",
           "Time-series feature & shape extractors — catch22, tsfel, tslearn shapelet/SAX, ROCKET.",
           "#e0c46c",
           name_subs=("catch22", "tsfel", "tslearn", "shapelet", "sax", "rocket",
                      "feature_engine", "functional_data", "tsfresh", "stumpy")),
    Column("quant", "Quant / Finance",
           "Financial signals & risk — GARCH/vol, options IV, momentum, meta-labeling, TA libraries.",
           "#d29922",
           name_subs=("garch", "vol", "empyrical", "option", "tsmom", "meta_label",
                      "triple_barrier", "bollinger", "alpha", "stockstats", "pandas_ta",
                      "talib", "wq_ts", "vix", "moneyflow", "factor")),
    Column("regime", "Regime / State / Filter",
           "Latent-state, regime & filtering — HMMs, Kalman, changepoint/regime gates, stationarity.",
           "#ff6b9d",
           name_subs=("hmm", "regime", "markov", "pomegranate", "recurring", "state",
                      "kalman", "meanrev", "ou_", "adf", "control", "ewma")),
    Column("reservoir", "Reservoir / Sequence",
           "Echo-state & reservoir computers for temporal/chaotic dynamics.",
           "#ff8f5a",
           name_subs=("reservoir", "esn", "echo", "elm")),
    Column("neural", "Neural / Kernel",
           "Neural & kernel approximators — MLP/DNN, TabPFN, Nyström, self-organising maps.",
           "#9b8cff",
           name_subs=("mlp", "dnn", "deep", "torch", "tabpfn", "nystroem", "som",
                      "autoencoder", "quantum"), kinds=("dl",)),
    Column("neighbors", "Neighbors",
           "Instance-based, local-geometry learners — k-nearest-neighbours variants.",
           "#37c8c3",
           name_subs=("knn", "neighbor", "neighbour")),
    Column("trees", "Trees / Forests",
           "Axis-split learners — decision stumps, decision trees, random forests.",
           "#38c172",
           name_subs=("stump", "tree", "_rf", "rf100", "rf200", "forest", "extratrees")),
    Column("linear", "Linear / Probabilistic",
           "Linear & probabilistic separators — logistic regression, naive Bayes, SVM, ridge.",
           "#4f9dff",
           name_subs=("logreg", "logistic", "gaussnb", "naive", "svm", "ridge", "linear")),
    Column("meta", "Meta / Routers",
           "Combiners that already route/stack other nodes — conformal, DES, Caruana, stacking.",
           "#a0a0a0",
           name_subs=("router", "caruana", "des", "conformal", "hellsemble", "stacking",
                      "ensemble", "rl_policy", "policy"),
           kinds=("meta", "router", "gate", "cascade", "bus")),
    # catch-all — GUARANTEES every node lands somewhere (open to future nodes).
    Column("other", "Other",
           "Uncategorised nodes — any new node lands here until a column rule is added.",
           "#6b7280"),
]

COLUMN_KEYS: tuple[str, ...] = tuple(c.key for c in COLUMNS)
_BY_KEY: dict[str, Column] = {c.key: c for c in COLUMNS}


def column_for(name: str, kind: str = "") -> str:
    """Return the column key for a node, by first-match; 'other' if nothing matches."""
    for col in COLUMNS:
        if col.key == "other":
            continue
        if col.matches(name, kind):
            return col.key
    return "other"


def get_column(key: str) -> Column:
    return _BY_KEY[key]


def group_factories(factories: list, names: list[str], kinds: list[str] | None = None
                    ) -> dict[str, list[tuple]]:
    """Group (factory, name) pairs by column key.

    kinds is optional; when absent, matching uses the name only (kinds default to "").
    Returns an ORDERED dict-like (plain dict preserves insertion order) keyed by the
    COLUMNS order, containing only NON-EMPTY columns.
    """
    kinds = kinds or [""] * len(names)
    buckets: dict[str, list[tuple]] = {c.key: [] for c in COLUMNS}
    for f, nm, kd in zip(factories, names, kinds):
        buckets[column_for(nm, kd)].append((f, nm))
    # preserve COLUMNS order, drop empties
    return {c.key: buckets[c.key] for c in COLUMNS if buckets[c.key]}


@dataclass
class ColumnLayout:
    """Serializable column description for the dashboard (state.json `columns`)."""
    key: str
    title: str
    desc: str
    color: str
    members: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"key": self.key, "title": self.title, "desc": self.desc,
                "color": self.color, "members": self.members, "size": len(self.members)}


def layout_for(grouped: dict[str, list[tuple]]) -> list[dict]:
    """Build the ordered dashboard column layout from a grouped pool."""
    out = []
    for key, pairs in grouped.items():
        col = _BY_KEY[key]
        out.append(ColumnLayout(col.key, col.title, col.desc, col.color,
                                [nm for _, nm in pairs]).to_json())
    return out
