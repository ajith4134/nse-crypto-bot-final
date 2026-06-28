"""trading/brain/experience.py — episodic experience bank + CBR recall (T8.4).

Indexes every closed trade as a "case": a deterministic numeric vector of the PRE-TRADE
setup (market/direction/time + market-context + options + risk fields), stored with its
OUTCOME (net P&L, R-multiple, win). Before a new decision, `recall()` retrieves the k
most analogous historical setups and aggregates their outcomes — weighted by relevance
(vector distance) × recency × importance (|net P&L|) — into a decision bias:
expected win-rate, expected P&L, a directional bias in [-1,1], and a confidence in [0,1].
Accuracy improves mechanically as the case base grows; it is fully auditable (you can
show the precedent trades).

Reuse-first: vector store + ANN search = **LanceDB** (embedded, CPU, persisted to disk);
falls back to an in-memory numpy exact-kNN if LanceDB is unavailable so it always works.
The setup vector excludes outcome fields (no leakage): outcomes are the labels recalled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

try:
    import lancedb
    _HAVE_LANCEDB = True
except Exception:  # pragma: no cover
    _HAVE_LANCEDB = False


def _num(v) -> float:
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# Pre-trade setup fields → scaled vector component. (field, scale-fn) — outcome fields excluded.
VEC_SPEC: list[tuple] = [
    ("market", lambda t: 1.0 if str(t.get("market", "")).upper() in
     ("CRYPTO", "BINANCE", "BYBIT") or str(t.get("instrument_type", "")).upper()
     in ("PERP", "SPOT", "QUARTERLY") else 0.0),
    ("direction", lambda t: 1.0 if str(t.get("direction", "")).upper() == "LONG"
     else (-1.0 if str(t.get("direction", "")).upper() == "SHORT" else 0.0)),
    ("entry_hour", lambda t: _num(t.get("entry_hour")) / 24.0),
    ("india_vix", lambda t: (_num(t.get("india_vix_entry")) - 15.0) / 10.0),
    ("regime_conf", lambda t: (_num(t.get("regime_confidence")) - 50.0) / 50.0),
    ("rel_volume", lambda t: _num(t.get("relative_volume")) - 1.0),
    ("oi_change", lambda t: _num(t.get("oi_change_pct")) / 100.0),
    ("fear_greed", lambda t: (_num(t.get("fear_greed_index")) - 50.0) / 50.0),
    ("funding", lambda t: _num(t.get("funding_rate_entry")) * 100.0),
    ("ls_ratio", lambda t: _num(t.get("long_short_ratio_entry")) - 1.0),
    ("iv", lambda t: (_num(t.get("iv_entry")) - 0.2) / 0.2),
    ("iv_rank", lambda t: (_num(t.get("iv_rank_entry")) - 50.0) / 50.0),
    ("delta", lambda t: _num(t.get("delta_entry"))),
    ("leverage", lambda t: (_num(t.get("leverage")) - 1.0) / 10.0),
    ("risk_reward", lambda t: (_num(t.get("risk_reward")) - 2.0) / 2.0),
]
VEC_FIELDS: list[str] = [name for name, _ in VEC_SPEC]
VEC_DIM = len(VEC_SPEC)


def _as_dict(trade) -> dict:
    if hasattr(trade, "to_dict"):
        return trade.to_dict()
    return dict(trade)


def trade_vector(trade) -> list[float]:
    """Deterministic scaled setup vector for a trade (ClosedTrade or dict)."""
    d = _as_dict(trade)
    return [round(float(fn(d)), 6) for _, fn in VEC_SPEC]


def _outcome(trade) -> dict:
    d = _as_dict(trade)
    net = _num(d.get("net_pnl"))
    return {
        "trade_id": str(d.get("trade_id", "")), "symbol": str(d.get("symbol", "")),
        "market": str(d.get("market", "")), "net_pnl": net,
        "r_multiple": _num(d.get("r_multiple")), "win": 1 if net > 0 else 0,
        "entry_datetime": str(d.get("entry_datetime", "")),
        "strategy_name": str(d.get("strategy_name", "")),
    }


@dataclass
class Recall:
    n: int
    expected_win_rate: float          # 0..100
    expected_pnl: float               # weighted mean net P&L of neighbours
    bias: float                       # [-1,1] weighted directional edge (sign of expected pnl)
    confidence: float                 # 0..1 (grows with agreement + sample size)
    neighbours: list                  # the retrieved cases (auditable precedent)

    def as_dict(self) -> dict:
        return {"n": self.n, "expected_win_rate": self.expected_win_rate,
                "expected_pnl": self.expected_pnl, "bias": self.bias,
                "confidence": self.confidence,
                "neighbours": [{k: v for k, v in c.items() if k != "vector"}
                               for c in self.neighbours]}


class ExperienceBank:
    """Episodic case base over closed trades, with CBR recall to bias new decisions."""

    def __init__(self, uri: str | None = None, *, table: str = "experience",
                 use_lancedb: bool | None = None):
        self.table_name = table
        self._mem: list[dict] = []                 # always-present mirror (fallback + stats)
        self._use_lancedb = (_HAVE_LANCEDB if use_lancedb is None else
                             (use_lancedb and _HAVE_LANCEDB))
        self._db = None
        self._tbl = None
        if self._use_lancedb and uri:
            self._db = lancedb.connect(uri)

    # ── ingest ──────────────────────────────────────────────────────────────────
    def add_trade(self, trade) -> "ExperienceBank":
        row = {"vector": trade_vector(trade), **_outcome(trade)}
        self._mem.append(row)
        if self._use_lancedb and self._db is not None:
            if self._tbl is None:
                self._tbl = self._db.create_table(self.table_name, data=[row], mode="overwrite")
            else:
                self._tbl.add([row])
        return self

    def add_many(self, trades) -> "ExperienceBank":
        for t in trades:
            self.add_trade(t)
        return self

    def from_journal(self, journal) -> "ExperienceBank":
        return self.add_many(journal.trades)

    def size(self) -> int:
        return len(self._mem)

    # ── retrieve ────────────────────────────────────────────────────────────────
    def _query_vector(self, query) -> np.ndarray:
        if isinstance(query, (list, tuple, np.ndarray)) and not hasattr(query, "to_dict"):
            v = np.asarray(query, dtype=float)
        else:
            v = np.asarray(trade_vector(query), dtype=float)
        if v.shape[0] != VEC_DIM:
            raise ValueError(f"query vector dim {v.shape[0]} != {VEC_DIM}")
        return v

    def retrieve(self, query, k: int = 10) -> list[dict]:
        """Return the k nearest cases (each annotated with `_distance`)."""
        if not self._mem:
            return []
        qv = self._query_vector(query)
        if self._use_lancedb and self._tbl is not None:
            res = self._tbl.search(qv.tolist()).limit(k).to_list()
            return res
        # numpy exact-kNN fallback
        mat = np.array([r["vector"] for r in self._mem], dtype=float)
        d = np.linalg.norm(mat - qv, axis=1)
        idx = np.argsort(d)[:k]
        out = []
        for i in idx:
            row = dict(self._mem[i])
            row["_distance"] = float(d[i])
            out.append(row)
        return out

    # ── CBR recall → decision bias ──────────────────────────────────────────────
    def recall(self, query, k: int = 10, *, now_ts: float | None = None) -> Recall:
        """Aggregate the k nearest cases' outcomes into a decision bias."""
        cases = self.retrieve(query, k)
        if not cases:
            return Recall(0, 0.0, 0.0, 0.0, 0.0, [])
        pnls = np.array([c["net_pnl"] for c in cases], dtype=float)
        wins = np.array([c["win"] for c in cases], dtype=float)
        dist = np.array([c.get("_distance", 0.0) for c in cases], dtype=float)
        relevance = 1.0 / (1.0 + dist)
        importance = 1.0 + np.abs(pnls) / (np.abs(pnls).max() + 1e-9)
        w = relevance * importance
        w = w / (w.sum() + 1e-12)
        expected_pnl = float((w * pnls).sum())
        expected_win = float((w * wins).sum() * 100.0)
        # agreement = how one-sided the neighbours' outcomes are
        agreement = abs(float((w * np.sign(pnls)).sum()))
        confidence = float(agreement * (len(cases) / (len(cases) + 5.0)))
        scale = (np.abs(pnls).mean() + 1e-9)
        bias = float(np.clip(expected_pnl / scale, -1.0, 1.0))
        return Recall(n=len(cases), expected_win_rate=round(expected_win, 2),
                      expected_pnl=round(expected_pnl, 4), bias=round(bias, 4),
                      confidence=round(confidence, 4), neighbours=cases)

    def status(self) -> dict:
        markets = {}
        for r in self._mem:
            markets[r["market"]] = markets.get(r["market"], 0) + 1
        wins = sum(r["win"] for r in self._mem)
        return {
            "n_cases": len(self._mem), "vector_dim": VEC_DIM,
            "store": "lancedb" if (self._use_lancedb and self._tbl is not None) else "memory",
            "by_market": markets,
            "base_win_rate": round(wins / len(self._mem) * 100.0, 2) if self._mem else 0.0,
        }
