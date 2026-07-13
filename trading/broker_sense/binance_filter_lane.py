"""trading/broker_sense/binance_filter_lane.py — the Binance-filter TOP-N breadth lane.

Owner idea (2026-07-12, APPROVED): instead of deep-evaluating one symbol at a time, read the
Binance segment market page's OWN filters/sort columns (24h %, volume, funding, OI, long/short,
taker) — all already captured via the UI by `ui_market` — SORT the whole market by a filter
combination, and open the TOP-N (adaptive 20→50→100). This restores API-era trade breadth the
motto-pure way: hundreds of pre-ranked candidates from data the eyes already hold, instead of the
~37-symbols/cycle the per-symbol funnel screen manages (the 40-vs-10 collapse).

Scope of THIS module (Stage 1): the RANKER — pure, testable scoring of the UI-captured universe by
named filter presets, returning ranked top-N candidates. It does NOT decide direction and does NOT
place orders (that's the executor + `learned_direction`, wired by the caller). It runs as a NEW
PARALLEL candidate lane (kill-switchable via BINANCE_FILTER_LANE), never replacing the funnel.

Stage 2 (learned combo-selector): score each preset's realized forward edge from truth_ledger per
regime and rotate toward the winner (reuse autoresearch.py + PresetStore). Stage 3: per-pick side
from learned_direction + indicator_fusion. Both are documented seams, not yet in this file.

Levers: BINANCE_FILTER_LANE (0 disables), BINANCE_FILTER_PRESET (default 'momentum'),
BINANCE_FILTER_TOPN (base N, default 20), BINANCE_FILTER_MIN_FRESH (skip stale rows).
"""
from __future__ import annotations

import os
import re

from trading.broker_sense import ui_market as _um

_FLAT = re.compile(r"^([A-Z0-9]+?)(USDT|USDC|BUSD|FDUSD)$")


def to_pair(flat: str, segment: str = "futures") -> str:
    """Flat exchange symbol from the UI capture ('DODOXUSDT') → the engine-tradeable pair form
    ('DODOX/USDT:USDT' for futures, 'DODOX/USDT' for spot) that CryptoEngineClient.tradeable_form
    expects. The eyes surface flat tickers; the engine trades slashed pairs — without this bridge
    every pick is silently dropped as non-tradeable. Already-slashed input is returned unchanged."""
    s = str(flat or "").upper().strip()
    if "/" in s:
        return s
    m = _FLAT.match(s)
    base = m.group(1) if m else s
    return f"{base}/USDT" if segment == "spot" else f"{base}/USDT:USDT"


def _f(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


# ── feature extraction: one UI-captured universe row → normalized filter features ─────
def features(symbol: str, ticker_row: dict | None = None) -> dict:
    """Build the filter feature vector for `symbol` from the eyes' UI captures. Every field is
    best-effort — a missing capture is None (honest), never faked. Cheap per-symbol accessor reads
    (each a dict lookup in ui_market's in-RAM store, no network)."""
    t = ticker_row or _um.ticker(symbol) or {}
    fu = _um.funding(symbol) or {}
    oi = _um.open_interest(symbol) or {}
    ls = _um.long_short(symbol) or {}
    tk = _um.taker(symbol) or {}
    last = _f(t.get("last"))
    pct = _f(t.get("pct_change"))
    vol = _f(t.get("volume") or t.get("qv") or t.get("v"))
    funding = _f(fu.get("funding_rate"))
    oi_val = _f(oi.get("open_interest") or oi.get("oi"))
    ls_ratio = _f(ls.get("ratio") or ls.get("long_short_ratio"))
    taker_buy = _f(tk.get("buy") or tk.get("buy_vol"))
    taker_sell = _f(tk.get("sell") or tk.get("sell_vol"))
    taker_imb = None
    if taker_buy is not None and taker_sell is not None and (taker_buy + taker_sell) > 0:
        taker_imb = (taker_buy - taker_sell) / (taker_buy + taker_sell)
    return {"symbol": symbol, "last": last, "pct_change": pct, "volume": vol,
            "funding_rate": funding, "open_interest": oi_val, "long_short_ratio": ls_ratio,
            "taker_imbalance": taker_imb}


# ── filter PRESETS: named combinations of features → an opportunity score ──────────────
# Each preset weights the (magnitude of) features that define a tradeable dislocation. The score
# ranks WHICH symbols are worth trading now; the SIDE (long/short) is decided downstream by
# learned_direction. Stage 2 replaces the static weights with truth-ledger-learned ones per regime.
_PRESETS = {
    # classic momentum: liquid + moving hard
    "momentum": {"abs_pct": 1.0, "log_vol": 0.6},
    # funding dislocation: crowded funding + liquidity (mean-reversion candidates)
    "funding_extreme": {"abs_funding": 1.0, "log_vol": 0.5, "abs_pct": 0.3},
    # order-flow squeeze: taker imbalance + OI + move
    "squeeze": {"abs_taker": 1.0, "abs_pct": 0.5, "log_vol": 0.4},
    # broad liquidity floor: just the most liquid names (safe default breadth)
    "liquidity": {"log_vol": 1.0},
}


def presets() -> list[str]:
    return list(_PRESETS)


def _components(row: dict) -> dict:
    """Derived, sign-free magnitudes the presets weight (opportunity size, not direction)."""
    import math
    pct = row.get("pct_change")
    vol = row.get("volume")
    fund = row.get("funding_rate")
    taker = row.get("taker_imbalance")
    return {
        "abs_pct": abs(pct) if pct is not None else 0.0,
        "log_vol": math.log10(vol) if (vol is not None and vol > 0) else 0.0,
        "abs_funding": abs(fund) * 100.0 if fund is not None else 0.0,   # rate→~%
        "abs_taker": abs(taker) if taker is not None else 0.0,
    }


def score(row: dict, preset: str = "momentum") -> float:
    """Opportunity score for one universe row under a named preset. Unknown preset → 'liquidity'.
    A row missing every component scores 0 (it will rank last, never crash)."""
    weights = _PRESETS.get(preset) or _PRESETS["liquidity"]
    comp = _components(row)
    return round(sum(w * comp.get(k, 0.0) for k, w in weights.items()), 6)


def rank(rows, preset: str = "momentum", n: int | None = None) -> list[dict]:
    """Rank universe rows by the preset's opportunity score, best first. Rows with no usable
    signal (score 0) are dropped so the lane never opens a trade on an empty read. `n` caps the
    result (None = all)."""
    scored = []
    for r in rows:
        s = score(r, preset)
        if s <= 0.0:
            continue
        scored.append({**r, "filter_score": s, "filter_preset": preset})
    scored.sort(key=lambda r: -r["filter_score"])
    return scored[: n] if n else scored


# ── adaptive N (Stage 1: static base; Stage 2 grows it as the edge proves out) ────────
def adaptive_n() -> int:
    """Top-N to open. Stage 1 returns the owner's base N (BINANCE_FILTER_TOPN, default 20).
    Stage 2 will grow this toward 50/100 only while the lane's realized win-rate holds — the
    'open more only when the edge holds' rule the owner approved."""
    try:
        return max(1, int(os.environ.get("BINANCE_FILTER_TOPN", "20") or 20))
    except ValueError:
        return 20


def enabled() -> bool:
    return os.environ.get("BINANCE_FILTER_LANE", "0") in ("1", "true", "TRUE", "yes", "on")


# ── universe + top picks (integration: pulls from the eyes' captures) ─────────────────
def universe(segment: str = "futures", *, min_rows: int = 1) -> list[dict]:
    """The full UI-captured Binance universe as filter feature rows. Seeded from ui_market.movers()
    (which enumerates every symbol with a fresh ticker capture), each enriched with funding/OI/
    long-short/taker. Empty when the eyes haven't fed tickers fresh — honest, never faked."""
    base = _um.movers(n=10_000) or []
    out = []
    for m in base:
        sym = m.get("symbol")
        if not sym:
            continue
        out.append(features(sym, ticker_row=m))
    return out


def top_picks(segment: str = "futures", preset: str | None = None,
              n: int | None = None) -> list[dict]:
    """The lane's output: the top-N ranked candidates for the executor to open (side decided
    downstream). preset defaults to BINANCE_FILTER_PRESET; n defaults to adaptive_n()."""
    preset = preset or os.environ.get("BINANCE_FILTER_PRESET", "momentum")
    n = n if n is not None else adaptive_n()
    return rank(universe(segment), preset, n)
