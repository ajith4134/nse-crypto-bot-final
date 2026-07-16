"""trading/broker_sense/orderflow_store.py — per-bar REAL order-flow history store (COVERAGE-AUDIT
gap B / A(b)): so the direction equation can train on the actual order-flow the research ranks #1,
not just OHLCV proxies.

`binance_orderflow.features()` gives the live per-symbol order-flow (taker buy/sell, long/short crowd,
OI, funding, liquidations) computed BY Binance; this module SNAPSHOTS it per bar and PERSISTS a growing
time series per symbol, plus a stationarised GOFI-style feature. `series()` / `join_features()` then
splice those real columns onto the OHLCV feature frame (merge-asof by timestamp) so the equation
generators can build order-flow-first equations.

Honest by construction: it ACCUMULATES FORWARD (Binance's /futures/data has no deep per-bar history to
backfill), so the equation's real-order-flow coverage grows as it runs; older bars simply carry NaN
(the generators ignore all-NaN columns). True L2-book OFI needs the depth stream — a further step.
Bounded: last N bars per symbol, active symbols only. Never raises into a caller.
"""
from __future__ import annotations

import time

from trading import state

_FILE = "orderflow_store.json"
_MAX_BARS = 240                     # keep ~ a day of 5m bars per symbol
_BAR_S = 300                        # snapshot granularity (5m bars)

# the order-flow fields we persist per bar (the equation's real order-flow variable set)
_FIELDS = ("of_taker_ratio", "of_crowd_long", "of_smart_long", "of_oi", "of_funding",
           "of_liq_skew", "of_gofi")


def _bar(ts: float | None = None) -> int:
    return int((ts or time.time()) // _BAR_S)


def _extract(feat: dict) -> dict:
    """binance_orderflow.features() → our persisted order-flow record (missing = None, never faked).
    of_gofi: a stationarised order-flow-imbalance proxy — taker buy/sell mapped to [-1,1] and scaled
    by crowd positioning (a cheap stand-in for generalized OFI until the L2 depth stream lands)."""
    def g(*ks):
        for k in ks:
            v = feat.get(k)
            if v is not None:
                return float(v)
        return None
    tr = g("taker_buy_sell_ratio", "taker_buy_ratio")
    crowd = g("crowd_long_pct")
    gofi = None
    if tr is not None:
        # ratio>1 = buyers lifting; log-map to signed, then lean by crowd positioning skew
        import math
        base = math.tanh(math.log(max(tr, 1e-6)))
        skew = ((crowd / 100.0) - 0.5) * 2.0 if crowd is not None else 0.0
        gofi = round(max(-1.0, min(1.0, 0.7 * base + 0.3 * skew)), 4)
    return {
        "of_taker_ratio": tr,
        "of_crowd_long": crowd,
        "of_smart_long": g("smart_long_pct"),
        # binance_orderflow.features() emits `open_interest_usd` — the old alias list ("open_interest",
        # "oi") never matched it, so of_oi could not populate from the fusion path even when the data
        # was there (found 2026-07-16 when the RAM poller filled OI for 100 symbols and this stayed 0%).
        "of_oi": g("open_interest_usd", "open_interest", "oi"),
        "of_funding": g("funding_rate"),
        "of_liq_skew": g("liq_skew", "liquidation_skew"),
        "of_gofi": gofi,
    }


def snapshot(symbol: str, market: str = "crypto", feat: dict | None = None) -> dict | None:
    """Snapshot the live order-flow for `symbol` and append it to the per-bar store (deduped per bar).
    Returns the record, or None when order-flow is unavailable. Never raises.
    `feat` accepts an already-fetched binance_orderflow.features() dict so the fusion hot path
    never pays a second fetch (2026-07-16: the old call sat behind a `not _cheap` gate that the
    default CRYPTO_UNLIMITED_OPENS=1 made unreachable — this store had NEVER written a row)."""
    if market != "crypto":
        return None
    if feat is None:
        try:
            from trading.broker_sense import binance_orderflow as of
            if not of.enabled():
                return None
            feat = of.features(symbol)
        except Exception:
            return None
    if not feat:
        return None
    rec = _extract(feat)
    if all(rec[f] is None for f in _FIELDS):
        return None
    bar = _bar()
    rec["bar"] = bar
    rec["ts"] = bar * _BAR_S
    try:
        store = state.load_json(_FILE, {}) or {}
        rows = store.get(symbol) or []
        if rows and rows[-1].get("bar") == bar:      # same bar → replace (latest read wins)
            rows[-1] = rec
        else:
            rows.append(rec)
        store[symbol] = rows[-_MAX_BARS:]
        state.save_json(_FILE, store)
    except Exception:
        pass
    return rec


def snapshot_all(symbols, market: str = "crypto") -> int:
    """Snapshot a batch of symbols (funnel hook). Returns how many were written."""
    n = 0
    for s in symbols:
        if snapshot(s, market):
            n += 1
    return n


def series(symbol: str):
    """The persisted per-bar order-flow series for `symbol` as a DataFrame (ts + of_* cols), or None."""
    try:
        import pandas as pd
        rows = (state.load_json(_FILE, {}) or {}).get(symbol) or []
        if not rows:
            return None
        return pd.DataFrame(rows)
    except Exception:
        return None


def join_features(feats, symbol: str, *, ts_col: str | None = None):
    """Splice the real order-flow columns onto an OHLCV feature frame by timestamp (merge-asof,
    backward). Rows before the store began carry NaN (all-NaN cols are ignored by the generators).
    `feats` must have a timestamp column (or a DatetimeIndex); returns feats unchanged on any miss."""
    try:
        import pandas as pd
        # find the feature frame's per-row epoch seconds
        if ts_col and ts_col in feats.columns:
            fts = feats[ts_col].astype("int64")
            unit = "ms" if int(fts.iloc[0]) > 1_000_000_000_000 else "s"
            left_ts = pd.to_datetime(fts, unit=unit)
        elif isinstance(feats.index, pd.DatetimeIndex):
            left_ts = feats.index
        else:
            return feats                              # no timestamp to align on → leave as-is
        merged = feats.copy()
        merged["_ts"] = pd.to_datetime(left_ts).values
        orig_index = feats.index
        did = False
        of = series(symbol)
        if of is not None and not of.empty:
            of = of.copy()
            of["_ts"] = pd.to_datetime(of["ts"].astype("int64"), unit="s")
            merged = pd.merge_asof(merged.sort_values("_ts"),
                                   of[["_ts", *_FIELDS]].sort_values("_ts"),
                                   on="_ts", direction="backward")
            did = True
        # TRUE L2-book OFI/GOFI history (book_ofi, 2026-07-16) — the research's #1/#2 ranked
        # drivers, computed from the app's own depth stream and spliced on the same timestamps.
        try:
            from trading.broker_sense import book_ofi
            bk = book_ofi.series(symbol)
            if bk is not None and not bk.empty:
                bk = bk.copy()
                bk["_ts"] = pd.to_datetime(bk["ts"].astype("int64"), unit="s")
                merged = pd.merge_asof(merged.sort_values("_ts"),
                                       bk[["_ts", *book_ofi.BOOK_FIELDS]].sort_values("_ts"),
                                       on="_ts", direction="backward")
                did = True
        except Exception:
            pass
        if not did:
            return feats
        merged = merged.drop(columns=["_ts"])
        merged.index = orig_index
        return merged
    except Exception:
        return feats
