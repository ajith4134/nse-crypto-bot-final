"""Trader-psychology engine: crowd sentiment from live order-book depth.

Stitched from vendored OSS (see research/trader-psychology-stitch-map.md):
  • vendor/lob_regime_scanner (CameronScarpati @5658da5) src/features.py — multi-level OFI,
    book imbalance, weighted mid, spread bps, Kyle's lambda, VPIN (flowrisk) — loaded by
    file path because that repo's package __init__ uses absolute `src.` imports.
  • vendor/microprice (sstoikov @4e5f29a) — canonical Stoikov microprice estimator
    (imbalance/spread Markov chain, G* iteration), ported to an online class with a
    weighted-mid fallback while history is short.
  • vendor/crypto_whale_watching (pmaji @304959b) app.py calc_data — whale-wall detection:
    levels within a band of mid whose volume ≥ a fraction of visible side depth.
Depth-slope asymmetry (Næs–Skjeltorp) and the composite score/label are glue.

Venues: NSE via OpenAlgoClient.depth (5 levels, exchange per segment) and crypto via
ExchangeClient.order_book (ccxt, binance→bybit fallback). Consecutive snapshots are kept in
per-symbol rings (also appended to trading/data/depth/*.jsonl to accumulate DeepLOB training
data — see trading/brain/psych_deeplob.py).

Interpretations (research/lob-crowd-psychology-features.md): OBI>0 = crowd buying eagerness →
short-horizon up-drift; microprice−mid sign = imminent drift; OFI ≈ linear driver of ΔP;
widening spread / rising λ / high VPIN = fear, informed-trading toxicity → dampen conviction.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_VENDOR = Path(__file__).resolve().parents[2] / "vendor"
DEPTH_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "depth"

RING_LEN = 720            # ~1h at 5s polling
CACHE_TTL_S = 5.0
WALL_BAND = 0.05          # ±5% of mid (whale-watching default)
WALL_MIN_FRAC = 0.01      # level ≥1% of visible side depth = wall (whale-watching default)
MAX_JSONL_BYTES = 20_000_000  # per-symbol recorder cap

DEFAULT_WEIGHTS = {       # composite direction weights (TradeOutcomeNet learns on top)
    "obi": 0.30,
    "ofi": 0.20,
    "microprice": 0.20,
    "depth_slope": 0.15,
    "walls": 0.15,
}

LABELS = ["capitulation", "fearful", "anxious", "balanced", "optimistic", "greedy", "euphoric"]


def _load_lob_features():
    """Load the donor feature module by path (its package __init__ is not importable)."""
    path = _VENDOR / "lob_regime_scanner" / "src" / "features.py"
    spec = importlib.util.spec_from_file_location("_lob_regime_features", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    LOBF = _load_lob_features()
except Exception:  # pragma: no cover - flowrisk/vendor missing
    LOBF = None
    logger.warning("lob_regime_scanner features unavailable", exc_info=True)


# ── snapshots ────────────────────────────────────────────────────────────────


@dataclass
class BookSnapshot:
    """One order-book depth observation: price/qty ladders, best-first."""
    ts: float
    bids: list[tuple[float, float]]        # [(price, qty)] descending price
    asks: list[tuple[float, float]]        # [(price, qty)] ascending price
    last_price: float | None = None
    last_qty: float | None = None

    @property
    def mid(self) -> float | None:
        if self.bids and self.asks:
            return (self.bids[0][0] + self.asks[0][0]) / 2.0
        return None

    def to_json(self) -> str:
        return json.dumps(
            {"ts": self.ts, "bids": self.bids, "asks": self.asks,
             "last_price": self.last_price, "last_qty": self.last_qty})

    @classmethod
    def from_ccxt(cls, ob: dict) -> "BookSnapshot | None":
        bids = [(float(p), float(q)) for p, q, *_ in (ob.get("bids") or []) if q]
        asks = [(float(p), float(q)) for p, q, *_ in (ob.get("asks") or []) if q]
        if not bids or not asks:
            return None
        ts = (ob.get("timestamp") or 0) / 1000.0 or time.time()
        return cls(ts=ts, bids=bids, asks=asks)

    @classmethod
    def from_openalgo(cls, payload: dict) -> "BookSnapshot | None":
        data = payload.get("data", payload) or {}

        def _levels(rows: Any) -> list[tuple[float, float]]:
            out = []
            for r in rows or []:
                if isinstance(r, dict):
                    p = r.get("price"), r.get("quantity", r.get("qty"))
                else:
                    p = (r[0], r[1]) if len(r) >= 2 else (None, None)
                try:
                    price, qty = float(p[0]), float(p[1])
                except (TypeError, ValueError, IndexError):
                    continue
                if price > 0 and qty > 0:
                    out.append((price, qty))
            return out

        bids = sorted(_levels(data.get("bids")), key=lambda x: -x[0])
        asks = sorted(_levels(data.get("asks")), key=lambda x: x[0])
        if not bids or not asks:
            return None
        ltp = data.get("ltp")
        return cls(ts=time.time(), bids=bids, asks=asks,
                   last_price=float(ltp) if ltp else None,
                   last_qty=float(data.get("ltq") or 0) or None)


def ring_to_frame(ring: "deque[BookSnapshot] | list[BookSnapshot]", levels: int = 5) -> pd.DataFrame:
    """Build the snapshot DataFrame the donor feature functions expect."""
    rows = []
    for s in ring:
        row: dict[str, float] = {"timestamp": s.ts}
        for i in range(1, levels + 1):
            bp, bq = s.bids[i - 1] if len(s.bids) >= i else (np.nan, 0.0)
            ap, aq = s.asks[i - 1] if len(s.asks) >= i else (np.nan, 0.0)
            row[f"bid_price_{i}"], row[f"bid_qty_{i}"] = bp, bq
            row[f"ask_price_{i}"], row[f"ask_qty_{i}"] = ap, aq
        row["mid_price"] = (row["bid_price_1"] + row["ask_price_1"]) / 2.0
        if s.last_price is not None:
            row["last_trade_price"] = s.last_price
        if s.last_qty is not None:
            row["last_trade_qty"] = s.last_qty
        rows.append(row)
    return pd.DataFrame(rows)


# ── Stoikov microprice (ported from vendor/microprice notebook, cells 20–22) ─


class StoikovMicroprice:
    """Online port of Stoikov's microprice estimator.

    fit() reproduces the notebook's prep_data_sym + estimate + G* iteration on a rolling
    snapshot frame; adjustment() looks up G*(imbalance, spread). Falls back to the
    weighted-mid adjustment until enough history accumulates.
    """

    MIN_ROWS = 120

    def __init__(self, n_imb: int = 5, n_spread: int = 2, dt: int = 1, g_iters: int = 6):
        self.n_imb, self.n_spread, self.dt, self.g_iters = n_imb, n_spread, dt, g_iters
        self._gstar: np.ndarray | None = None
        self._ticksize: float | None = None
        self._imb_edges: np.ndarray | None = None

    def fit(self, df: pd.DataFrame) -> bool:
        try:
            T = pd.DataFrame({
                "bid": df["bid_price_1"], "ask": df["ask_price_1"],
                "bs": df["bid_qty_1"], "as": df["ask_qty_1"],
                "time": np.arange(len(df), dtype=float),
            }).dropna()
            if len(T) < self.MIN_ROWS:
                return False
            spread = T["ask"] - T["bid"]
            pos = spread[spread > 0]
            if pos.empty:
                return False
            ticksize = float(pos.min())
            T["spread"] = (np.round(spread / ticksize) * ticksize)
            T["mid"] = (T["bid"] + T["ask"]) / 2
            T = T.loc[(T["spread"] <= self.n_spread * ticksize) & (T["spread"] > 0)].copy()
            T["imb"] = T["bs"] / (T["bs"] + T["as"])
            if len(T) < self.MIN_ROWS or T["imb"].nunique() < self.n_imb:
                return False
            T["imb_bucket"], edges = pd.qcut(
                T["imb"], self.n_imb, labels=False, retbins=True, duplicates="drop")
            n_imb = int(T["imb_bucket"].max()) + 1
            if n_imb < 3:
                return False
            T["spread_bucket"] = np.clip(
                np.round(T["spread"] / ticksize).astype(int) - 1, 0, self.n_spread - 1)
            T["next_mid"] = T["mid"].shift(-self.dt)
            T["next_imb_bucket"] = T["imb_bucket"].shift(-self.dt)
            T["next_spread_bucket"] = T["spread_bucket"].shift(-self.dt)
            T["dM"] = np.round((T["next_mid"] - T["mid"]) / ticksize * 2) * ticksize / 2
            T = T.dropna(subset=["dM", "next_imb_bucket"])
            T = T.loc[(T["dM"].abs() <= ticksize * 1.1)]
            # symmetrize (notebook prep_data_sym)
            T2 = T.copy()
            T2["imb_bucket"] = n_imb - 1 - T2["imb_bucket"]
            T2["next_imb_bucket"] = n_imb - 1 - T2["next_imb_bucket"]
            T2["dM"] = -T2["dM"]
            T = pd.concat([T, T2], ignore_index=True)

            K = np.array([-ticksize, -ticksize / 2, ticksize / 2, ticksize])
            n_state = n_imb * self.n_spread

            def state(row_s, row_i):
                return (row_s * n_imb + row_i).astype(int)

            s_now = state(T["spread_bucket"], T["imb_bucket"])
            s_next = state(T["next_spread_bucket"].fillna(T["spread_bucket"]),
                           T["next_imb_bucket"])
            no_move = T["dM"] == 0
            Q = np.zeros((n_state, n_state))
            np.add.at(Q, (s_now[no_move], s_next[no_move]), 1.0)
            R1 = np.zeros((n_state, 4))
            dm_idx = np.digitize(T.loc[~no_move, "dM"], [-ticksize * 0.75, 0, ticksize * 0.75])
            np.add.at(R1, (s_now[~no_move], dm_idx), 1.0)
            R2 = np.zeros((n_state, n_state))
            np.add.at(R2, (s_now[~no_move], s_next[~no_move]), 1.0)

            def _norm(M_left, M_right):
                joined = np.concatenate([M_left, M_right], axis=1)
                sums = joined.sum(axis=1, keepdims=True)
                sums[sums == 0] = 1.0
                return joined / sums

            T1n = _norm(Q, R1)
            Qn, R1n = T1n[:, :n_state], T1n[:, n_state:]
            T2n = _norm(Q, R2)
            R2n = T2n[:, n_state:]
            inv = np.linalg.inv(np.eye(n_state) - Qn)
            G1 = inv @ R1n @ K
            B = inv @ R2n
            G = G1.copy()
            acc = G1.copy()
            Bp = np.eye(n_state)
            for _ in range(self.g_iters - 1):
                Bp = Bp @ B
                acc = acc + Bp @ G1
            self._gstar, self._ticksize = acc, ticksize
            self._imb_edges = edges
            self._n_imb_eff = n_imb
            return True
        except Exception:
            logger.debug("Stoikov fit failed; using weighted-mid fallback", exc_info=True)
            return False

    def adjustment(self, snap: BookSnapshot) -> float:
        """Microprice − mid. G* lookup when fitted, else weighted-mid adjustment."""
        bp, bq = snap.bids[0]
        ap, aq = snap.asks[0]
        mid = (bp + ap) / 2.0
        imb = bq / (bq + aq) if (bq + aq) > 0 else 0.5
        wmid = ap * imb + bp * (1 - imb)
        if self._gstar is None or self._ticksize is None:
            return wmid - mid
        spread_b = int(np.clip(round((ap - bp) / self._ticksize) - 1, 0, self.n_spread - 1))
        imb_b = int(np.clip(np.digitize(imb, self._imb_edges[1:-1]), 0, self._n_imb_eff - 1))
        return float(self._gstar[spread_b * self._n_imb_eff + imb_b])


# ── whale walls (adapted from vendor/crypto_whale_watching app.py calc_data) ─


def detect_walls(snap: BookSnapshot, band: float = WALL_BAND,
                 min_frac: float = WALL_MIN_FRAC) -> dict:
    """Wall = level within ±band of mid holding ≥ min_frac of that side's visible volume.

    Returns per-side walls and wall_bias ∈ [-1, 1] (bid walls near price = support/greed,
    ask walls = resistance/fear), distance-weighted like the donor's bubble sizing.
    """
    mid = snap.mid
    if not mid:
        return {"bias": 0.0, "bid_walls": [], "ask_walls": []}
    out = {}
    strength = {}
    for side, levels in (("bid", snap.bids), ("ask", snap.asks)):
        vis = [(p, q) for p, q in levels if abs(p - mid) / mid <= band]
        total = sum(q for _, q in vis) or 1.0
        # donor threshold assumes hundreds of levels; on shallow books a wall must also
        # stand out vs the average level (2× share), else every level qualifies
        thresh = max(min_frac, 2.0 / len(vis)) if vis else min_frac
        walls = [{"price": p, "qty": q, "frac": q / total,
                  "dist_pct": abs(p - mid) / mid * 100}
                 for p, q in vis if q / total >= thresh and q > 0]
        walls.sort(key=lambda w: -w["frac"])
        out[f"{side}_walls"] = walls[:5]
        # nearer + bigger walls dominate: Σ frac / (1 + dist/band)
        strength[side] = sum(w["frac"] / (1.0 + (w["dist_pct"] / 100) / band) for w in walls)
    denom = strength["bid"] + strength["ask"]
    out["bias"] = (strength["bid"] - strength["ask"]) / denom if denom else 0.0
    return out


def gap_map(snap: BookSnapshot, depths: tuple = (1, 5, 10, 20)) -> dict:
    """KRF-01/03/04 order-book gap map as a routed feature lane.

    At each fixed depth d ∈ {1,5,10,20} levels the book is summarised by:
      * cum_bid/cum_ask   — cumulative visible size to fill d levels;
      * span_bid/span_ask — price distance (bps from mid) that d levels cover
        (a WIDE span = a liquidity void / gap; the pattern-as-gap premise);
      * gap_bias          — (ask_span - bid_span)/(ask_span + bid_span) ∈ [-1,1]:
        a wider ask gap = thin resistance overhead (upward gap-fill room),
        a wider bid gap = thin support below (downward air-pocket).
    The per-depth vector is the neuron's input; `gap_map_bias` (mean over depths)
    is the scalar routed into the psychology composite. Honest on shallow books:
    depths beyond the visible book reuse the deepest available level."""
    mid = snap.mid
    if not mid:
        return {"gap_map_bias": 0.0, "depths": {}}

    def side(levels: list[tuple[float, float]], d: int) -> tuple[float, float]:
        vis = levels[:d] if levels else []
        if not vis:
            return 0.0, 0.0
        cum = float(sum(q for _, q in vis))
        span = abs(vis[-1][0] - mid) / mid * 10_000        # bps from mid
        return cum, span

    per_depth, biases = {}, []
    for d in depths:
        cb, sb = side(snap.bids, d)
        ca, sa = side(snap.asks, d)
        denom = sb + sa
        bias = (sa - sb) / denom if denom > 0 else 0.0
        per_depth[str(d)] = {"cum_bid": round(cb, 6), "cum_ask": round(ca, 6),
                             "span_bid_bps": round(sb, 4), "span_ask_bps": round(sa, 4),
                             "gap_bias": round(bias, 4)}
        biases.append(bias)
    return {"gap_map_bias": round(float(np.mean(biases)) if biases else 0.0, 4),
            "depths": per_depth}


def depth_slope_bias(snap: BookSnapshot) -> float:
    """Næs–Skjeltorp liquidity-slope asymmetry ∈ [-1, 1].

    Steeper cumulative-depth slope (more volume close to mid) = that side is defended;
    positive = bid side stronger (support), negative = ask side stronger (resistance).
    """
    mid = snap.mid
    if not mid:
        return 0.0

    def slope(levels: list[tuple[float, float]]) -> float:
        if len(levels) < 2:
            return 0.0
        x = np.array([abs(p - mid) / mid for p, _ in levels])
        y = np.cumsum([q for _, q in levels])
        denom = float(np.dot(x, x))
        return float(np.dot(x, y) / denom) if denom > 0 else 0.0

    sb, sa = slope(snap.bids), slope(snap.asks)
    return (sb - sa) / (sb + sa) if (sb + sa) > 0 else 0.0


# ── composite evaluation ─────────────────────────────────────────────────────


def evaluate_ring(ring: "deque[BookSnapshot] | list[BookSnapshot]",
                  micro: StoikovMicroprice | None = None,
                  weights: dict | None = None) -> dict | None:
    """Pure computation: full psychology dict from a snapshot ring (newest last)."""
    ring = list(ring)
    if not ring:
        return None
    snap = ring[-1]
    mid = snap.mid
    if not mid:
        return None
    weights = weights or DEFAULT_WEIGHTS
    levels = min(5, max(len(snap.bids), len(snap.asks)))
    df = ring_to_frame(ring, levels=levels)

    # donor features (lob_regime_scanner)
    obi_top = float(LOBF.compute_book_imbalance(df, depth=levels).iloc[-1]) if LOBF else 0.0
    obi_l1 = float(LOBF.compute_book_imbalance(df, depth=1).iloc[-1]) if LOBF else 0.0
    spread_bps = float(LOBF.compute_spread_bps(df).iloc[-1]) if LOBF else 0.0
    ofi = ofi_z = kyle = vpin = None
    if LOBF and len(df) >= 3:
        window = max(2, min(len(df), 300))
        ofi_df = LOBF.compute_ofi(df, depths=[levels])
        ofi = float(np.nan_to_num(ofi_df[f"ofi_{levels}"].iloc[-1]))
        z = ofi_df[f"ofi_{levels}_zscore"].iloc[-1]
        ofi_z = float(z) if np.isfinite(z) else 0.0
        lam = LOBF.compute_kyles_lambda(df, window=window).iloc[-1]
        kyle = float(lam) if np.isfinite(lam) else None
        if len(df) >= 30:
            try:
                v = LOBF.compute_vpin(df).iloc[-1]
                vpin = float(v) if np.isfinite(v) else None
            except Exception:
                vpin = None

    # microprice drift
    micro = micro or StoikovMicroprice()
    if micro._gstar is None and len(df) >= StoikovMicroprice.MIN_ROWS:
        micro.fit(df)
    micro_adj = micro.adjustment(snap)
    micro_drift_bps = micro_adj / mid * 10_000

    walls = detect_walls(snap)
    slope_bias = depth_slope_bias(snap)
    gaps = gap_map(snap)

    # fear ∈ [0,1]: spread vs its history, plus λ and VPIN levels
    fear_parts = []
    sp = df.get("mid_price")
    spread_series = ((df["ask_price_1"] - df["bid_price_1"]) / sp * 10_000) if sp is not None else None
    if spread_series is not None and len(spread_series) >= 10 and spread_series.std() > 0:
        z = (spread_bps - spread_series.mean()) / spread_series.std()
        fear_parts.append(1 / (1 + math.exp(-z)))          # widening spread = fear
    if vpin is not None:
        fear_parts.append(float(np.clip(vpin, 0.0, 1.0)))  # toxic flow
    if kyle is not None and len(df) >= 10:
        fear_parts.append(0.5 if kyle <= 0 else float(np.clip(kyle * mid, 0.0, 1.0)))
    fear = float(np.clip(np.mean(fear_parts), 0.0, 1.0)) if fear_parts else 0.0

    direction = (
        weights["obi"] * obi_top
        + weights["ofi"] * math.tanh((ofi_z or 0.0) / 2.0)
        + weights["microprice"] * math.tanh(micro_drift_bps / max(spread_bps, 1.0))
        + weights["depth_slope"] * slope_bias
        + weights["walls"] * walls["bias"]
    ) / sum(weights.values())
    score = float(np.clip(direction * (1.0 - 0.5 * fear), -1.0, 1.0))

    # label: direction bucket, overridden toward fear labels when fear dominates
    idx = int(np.clip(round((score + 1) / 2 * (len(LABELS) - 1)), 0, len(LABELS) - 1))
    label = LABELS[idx]
    if fear >= 0.65:
        label = "capitulation" if score < -0.15 else "anxious"

    return {
        "ts": snap.ts,
        "mid": mid,
        "levels": levels,
        "n_snapshots": len(ring),
        "trader_psychology": round(score, 4),
        "psych_label": label,
        "psych_obi": round(obi_top, 4),
        "psych_obi_l1": round(obi_l1, 4),
        "psych_ofi": None if ofi is None else round(ofi, 4),
        "psych_ofi_z": None if ofi_z is None else round(ofi_z, 4),
        "psych_microprice_drift_bps": round(float(micro_drift_bps), 4),
        "psych_spread_bps": round(spread_bps, 4),
        "psych_depth_slope_bias": round(slope_bias, 4),
        "psych_gap_map_bias": gaps["gap_map_bias"],
        "gap_map": gaps["depths"],
        "psych_wall_bias": round(walls["bias"], 4),
        "psych_fear": round(fear, 4),
        "psych_kyle_lambda": None if kyle is None else float(kyle),
        "psych_vpin": None if vpin is None else round(vpin, 4),
        "bid_walls": walls["bid_walls"],
        "ask_walls": walls["ask_walls"],
    }


# ── live engine ──────────────────────────────────────────────────────────────

# crypto segment → ccxt market type (mirrors trading/screener/sources.py)
_CRYPTO_MARKET_TYPE = {"futures": "swap", "spot": "spot", "options": "option",
                       "prediction": "swap"}


class TraderPsychology:
    """Fetches depth per venue, maintains per-symbol snapshot rings, returns psychology dicts.

    evaluate() is safe to call from trading loops: failures return None, results are cached
    for CACHE_TTL_S, snapshots are appended to trading/data/depth/ for DeepLOB training.
    """

    def __init__(self, record: bool = True):
        self._rings: dict[str, deque[BookSnapshot]] = {}
        self._micro: dict[str, StoikovMicroprice] = {}
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        self._record = record
        self._openalgo = None
        self._exchange: dict[str, Any] = {}

    # -- clients ---------------------------------------------------------
    def _nse_client(self):
        if self._openalgo is None:
            from trading.openalgo_client import OpenAlgoClient
            self._openalgo = OpenAlgoClient()
        return self._openalgo

    def _crypto_client(self, market_type: str):
        if market_type not in self._exchange:
            from trading.crypto.exchange_client import ExchangeClient
            self._exchange[market_type] = ExchangeClient(market_type=market_type)
        return self._exchange[market_type]

    # -- snapshot fetch ---------------------------------------------------
    def fetch_snapshot(self, market: str, symbol: str, segment: str | None = None,
                       exchange: str | None = None) -> BookSnapshot | None:
        try:
            if market.upper() == "NSE":
                payload = self._nse_client().depth(symbol, exchange=exchange or "NSE")
                return BookSnapshot.from_openalgo(payload)
            mtype = _CRYPTO_MARKET_TYPE.get((segment or "futures").lower(), "swap")
            ob = self._crypto_client(mtype).order_book(symbol, limit=50)
            return BookSnapshot.from_ccxt(ob)
        except Exception:
            logger.debug("depth fetch failed for %s:%s", market, symbol, exc_info=True)
            return None

    # -- recording (DeepLOB training data) ---------------------------------
    def _record_snapshot(self, key: str, snap: BookSnapshot) -> None:
        try:
            DEPTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
            f = DEPTH_DATA_DIR / (key.replace("/", "_").replace(":", "_") + ".jsonl")
            if f.exists() and f.stat().st_size > MAX_JSONL_BYTES:
                lines = f.read_text().splitlines()[-RING_LEN * 4:]
                f.write_text("\n".join(lines) + "\n")
            with f.open("a") as fh:
                fh.write(snap.to_json() + "\n")
        except Exception:
            logger.debug("depth recording failed", exc_info=True)

    # -- main entry ---------------------------------------------------------
    def evaluate(self, market: str, symbol: str, segment: str | None = None,
                 exchange: str | None = None) -> dict | None:
        key = f"{market}:{segment or '-'}:{symbol}"
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < CACHE_TTL_S:
                return hit[1]
        snap = self.fetch_snapshot(market, symbol, segment=segment, exchange=exchange)
        if snap is None:
            return None
        with self._lock:
            ring = self._rings.setdefault(key, deque(maxlen=RING_LEN))
            ring.append(snap)
            micro = self._micro.setdefault(key, StoikovMicroprice())
            result = evaluate_ring(ring, micro=micro)
            if result is not None:
                result.update({"market": market.upper(), "symbol": symbol,
                               "segment": segment or ""})
                try:  # DeepLOB direction prob (None until a model has been trained)
                    from trading.brain.psych_deeplob import predict_prob_up
                    result["psych_deeplob_prob_up"] = predict_prob_up(ring)
                except Exception:
                    result["psych_deeplob_prob_up"] = None
                self._cache[key] = (now, result)
        if self._record:
            self._record_snapshot(key, snap)
        return result


_ENGINE: TraderPsychology | None = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> TraderPsychology:
    """Process-wide shared engine (rings persist across callers)."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = TraderPsychology()
        return _ENGINE


# journal column names filled from an evaluate() dict (schema.py mirrors these)
PSYCH_TRADE_COLUMNS = [
    "trader_psychology", "psych_label", "psych_obi", "psych_ofi",
    "psych_microprice_drift_bps", "psych_spread_bps", "psych_depth_slope_bias",
    "psych_gap_map_bias", "psych_wall_bias", "psych_fear", "psych_vpin",
    "psych_deeplob_prob_up",
]


def psych_columns(result: dict | None) -> dict:
    """Subset an evaluate() result to the journal columns (None-safe)."""
    if not result:
        return {}
    return {k: result.get(k) for k in PSYCH_TRADE_COLUMNS if result.get(k) is not None or k == "psych_label"}
