"""Market-segment taxonomy — the CORTEX overlay that tags every neuron with a
market segment AND a pipeline stage (CORTEX build step B1; stitch-map row 5).

This is the sibling of :mod:`core.columns` (deliberately the SAME pattern):
columns group nodes by COMPUTE family ("how the node works"), segments group
them by MARKET/PIPELINE role ("what part of the trading problem it serves").
Both overlays are attributes on every neuron (design §1 T4) and both feed the
dashboard's honest layout — a node's segment is derived from its real
name/kind metadata, never hand-assigned per node.

Stages order the segments along the trading pipeline
(data → features → detection → forecasting → decision → execution), which is
the CORTEX signal path in §1: sensory features feed detection/forecasting
tissues whose outputs drive decisions executed on a market venue.

A segment is chosen by the FIRST matching rule (order matters: specific →
generic) over node NAME substrings + `kind` — the metadata every NodeProtocol
node already carries — with a `general` catch-all so ANY future node lands in
a segment with no code change (same open-to-future guarantee as columns.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# the ordered pipeline stages (data flows left → right through the cortex)
STAGES: tuple[str, ...] = ("data", "features", "detection", "forecasting",
                           "decision", "execution")


@dataclass(frozen=True)
class Segment:
    """One market/pipeline segment of the network.

    key        : stable identifier (used in network_state.json / dashboard).
    title      : human label for the dashboard header.
    desc       : what market/pipeline role this segment serves.
    color      : dashboard accent (Dark-Pro palette); purely cosmetic.
    name_subs  : node-name substrings that route a node into this segment.
    kinds      : node `kind` values that route a node into this segment.
    stage      : pipeline stage, one of STAGES (data → … → execution).
    """
    key: str
    title: str
    desc: str
    color: str
    name_subs: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    stage: str = "data"

    def matches(self, name: str, kind: str) -> bool:
        n, k = name.lower(), (kind or "").lower()
        return any(s in n for s in self.name_subs) or k in self.kinds


# ── the ordered segment stack (specific rules first, catch-all last) ─────────
# name_subs use the REAL node vocabulary (nodes/pool.py + run_multi.domain_pool
# + trading/* node names) so the live catalog lands in meaningful segments.
SEGMENTS: list[Segment] = [
    Segment("options", "Options",
            "Options-market nodes — implied vol, greeks, chains, straddles (NSE CE/PE + crypto options).",
            "#f6c445",
            name_subs=("option", "greeks", "straddle", "strangle", "chain_", "iv_surface"),
            stage="execution"),
    Segment("crypto", "Crypto",
            "Crypto-venue nodes — Freqtrade/ccxt exchanges, coins, order-book psychology feeds.",
            "#00b3a4",
            name_subs=("crypto", "freqtrade", "binance", "bybit", "okx", "kucoin",
                       "btc", "eth", "coin", "ccxt", "funding"),
            stage="execution"),
    Segment("nse_equity", "NSE Equity",
            "Indian-market nodes — OpenAlgo/Zerodha venues, NIFTY/BANKNIFTY, bhavcopy history.",
            "#ff9f43",
            name_subs=("nse", "openalgo", "nifty", "banknifty", "bhavcopy", "zerodha",
                       "equity", "indian", "mcx"),
            stage="execution"),
    Segment("forex", "Forex",
            "Currency-market nodes — FX pairs (dukascopy EURUSD daily/1m lanes, PNP doctrine).",
            "#4f9dff",
            name_subs=("forex", "fx_", "eurusd", "dukascopy", "currency", "usdinr"),
            stage="data"),
    Segment("risk_regime", "Risk / Regime",
            "Latent-state & risk nodes — regime HMMs, changepoints, volatility, drawdown/risk stats.",
            "#ff6b9d",
            name_subs=("hmm", "regime", "markov", "bocpd", "changepoint", "kalman",
                       "garch", "vol", "risk", "empyrical", "survival", "copula",
                       "meanrev", "ou_", "adf", "drawdown", "vix", "sizer", "kelly"),
            stage="detection"),
    Segment("meta_routing", "Meta / Routing",
            "Combiner & routing tissue — gates, routers, conformal, stacking, RL policies, buses.",
            "#a0a0a0",
            name_subs=("router", "gate", "conformal", "stacking", "ensemble", "meta",
                       "caruana", "des_", "hellsemble", "rl_policy", "policy",
                       "cascade", "column"),
            kinds=("meta", "router", "gate", "cascade", "bus"),
            stage="decision"),
    Segment("forecasting", "Forecasting",
            "Predictor nodes — sequence NNs, boosters, classic ML, foundation forecasters.",
            "#c678dd",
            name_subs=("forecast", "nbeats", "nhits", "tsmixer", "tcn", "gru", "lstm",
                       "prophet", "nvar", "deeptime", "chronos", "tabpfn", "esn",
                       "xgb", "lightgbm", "catboost", "ngboost", "gbdt",
                       "sk_", "mlp", "knn", "logreg", "tree", "stump", "svm",
                       "naive", "gaussnb", "_rf", "rf100", "rf200", "forest",
                       "micro_llm", "river", "hoeffding", "arima"),
            kinds=("dl",),
            stage="forecasting"),
    Segment("features", "Features",
            "Feature/signal extractors — TA libraries, spectral/entropy/shape transforms, denoisers.",
            "#e0c46c",
            name_subs=("catch22", "tsfel", "tsfresh", "talib", "pandas_ta", "stockstats",
                       "feature", "wavelet", "emd", "vmd", "ewt", "ssa", "ssqueeze",
                       "hilbert", "spectral", "lombscargle", "fracdiff", "alpha",
                       "librosa", "entropyhub", "antropy", "entropy", "signature",
                       "rocket", "sax", "shapelet", "denoise", "savgol", "decomp",
                       "ica", "dict_learn", "robust_pca", "fractal", "candle",
                       "pattern", "indicator"),
            kinds=("feature",),
            stage="features"),
    # catch-all — GUARANTEES every node lands somewhere (open to future nodes).
    Segment("general", "General",
            "Unsegmented nodes — any new node lands here until a segment rule is added.",
            "#6b7280",
            stage="data"),
]

SEGMENT_KEYS: tuple[str, ...] = tuple(s.key for s in SEGMENTS)
_BY_KEY: dict[str, Segment] = {s.key: s for s in SEGMENTS}


def segment_for(name: str, kind: str = "") -> str:
    """Return the segment key for a node, by first-match; 'general' if none match."""
    for seg in SEGMENTS:
        if seg.key == "general":
            continue
        if seg.matches(name, kind):
            return seg.key
    return "general"


def get_segment(key: str) -> Segment:
    return _BY_KEY[key]


def group_by_segment(factories: list, names: list[str], kinds: list[str] | None = None
                     ) -> dict[str, list[tuple]]:
    """Group (factory, name) pairs by segment key (mirror of columns.group_factories).

    kinds is optional; when absent, matching uses the name only (kinds default to "").
    Returns an ordered dict keyed by the SEGMENTS order, containing only NON-EMPTY
    segments.
    """
    kinds = kinds or [""] * len(names)
    buckets: dict[str, list[tuple]] = {s.key: [] for s in SEGMENTS}
    for f, nm, kd in zip(factories, names, kinds):
        buckets[segment_for(nm, kd)].append((f, nm))
    return {s.key: buckets[s.key] for s in SEGMENTS if buckets[s.key]}


@dataclass
class SegmentLayout:
    """Serializable segment description for the dashboard (network_state.json)."""
    key: str
    title: str
    desc: str
    color: str
    stage: str
    members: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"key": self.key, "title": self.title, "desc": self.desc,
                "color": self.color, "stage": self.stage,
                "members": self.members, "size": len(self.members)}


def segment_layout(grouped: dict[str, list[tuple]]) -> list[dict]:
    """Build the ordered dashboard segment layout from a grouped pool."""
    out = []
    for key, pairs in grouped.items():
        seg = _BY_KEY[key]
        out.append(SegmentLayout(seg.key, seg.title, seg.desc, seg.color, seg.stage,
                                 [nm for _, nm in pairs]).to_json())
    return out
