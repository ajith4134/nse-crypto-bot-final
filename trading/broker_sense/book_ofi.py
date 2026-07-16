"""trading/broker_sense/book_ofi.py — TRUE L2-book OFI/GOFI per-bar history (COVERAGE-AUDIT gap B).

The direction research ranked true book ORDER FLOW IMBALANCE (OFI, Cont–Kukanov–Stoikov) and its
depth-normalized multi-level form (GOFI) as the #1/#2 price drivers — and until 2026-07-16 this
project never computed them: only OHLCV proxies (`buy_press`/`cvd`/`tick_ofi`) and Binance's 5m
positioning aggregates (orderflow_store) existed. This module computes the real thing from the web
app's OWN depth stream (THE MOTTO: market data = web navigation, zero extra API): ui_market feeds
every parsed partial-book snapshot to `on_book()`; we accumulate event-level OFI increments per
book level and flush ONE row per bar per symbol to an append-only JSONL under
`trading/state/orderflow/`.

    on_book(sym, rec, ts)   — event hook (called from ui_market ingest). O(levels) arithmetic,
                              lock-guarded, NEVER raises into the stream pump.
    series(symbol, bar_s)   — the stored history as a DataFrame resampled to bar_s (300s default,
                              matching the equation's 5m bars).
    status()                — honest accumulation report for dashboards/audits.

Per stored bar (bar_s = BOOK_OFI_BAR_S, default 60s):
    ts          bar-start epoch seconds
    n           book snapshots folded into the bar (0 events → no row, never faked)
    ofi         L1 CKS order-flow imbalance, base-qty units, summed over the bar
    ofi_n       ofi normalized by the bar's mean L1 depth (stationarized, cross-symbol comparable)
    gofi        multi-level generalized OFI: per-level bar-sums, each normalized by that level's
                mean depth, exp-weighted (w_l = exp(-l/λ), λ=3) and summed — unitless
    obi         time-mean L1 order-book imbalance (qb-qa)/(qb+qa) ∈ [-1,1]
    microdev_bp time-mean microprice deviation from mid, in basis points (sign = pressure side)
    spread_bp   time-mean relative spread in basis points
    depth_q     time-mean total visible depth (sum of top-level qtys both sides, base units)
    dobi        time-mean multi-level depth imbalance (Σbid−Σask)/(Σbid+Σask) over the top N
                levels ∈ [-1,1] — the book-STATE research's headline predictor (2026-07-16:
                pre-event top-20 depth/imbalance beats order FLOW 3-4× at 1m/5m horizons);
                only depth snapshots contribute (bookTicker frames carry no levels)
    d1s         time-mean L1 share of total visible depth (book concentration/shape), same basis

Honest by construction: accumulates FORWARD only (no depth history exists to backfill); a symbol
whose stream goes quiet gets its last bar closed on the next sweep, and gaps > _RESET_S between
snapshots reset the diff state instead of fabricating one giant increment. Sequence: bookTicker
frames (L1 only, no levels) contribute to L1/obi/spread metrics; @depthN snapshots contribute all
levels. Bounded: per-symbol JSONL rotated to the newest _KEEP_LINES rows.

Levers: BOOK_OFI=0 disables; BOOK_OFI_BAR_S (60); BOOK_OFI_LEVELS (10); BOOK_OFI_LAMBDA (3.0).
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path

from trading import state

_DIR = "orderflow"                       # under state.STATE_DIR
_KEEP_LINES = 120_000                    # ~83 days of 1m bars; rotate keep newest half
_RESET_S = 120.0                         # snapshot gap beyond this resets the diff state
_lock = threading.Lock()
_acc: dict[str, dict] = {}               # SYMBOL -> accumulator
_last_sweep = [0.0]


def enabled() -> bool:
    return os.environ.get("BOOK_OFI", "1").strip().lower() not in ("0", "false", "off")


def _bar_s() -> int:
    try:
        return max(10, int(float(os.environ.get("BOOK_OFI_BAR_S", "60") or 60)))
    except ValueError:
        return 60


def _levels() -> int:
    try:
        return max(1, min(20, int(os.environ.get("BOOK_OFI_LEVELS", "10") or 10)))
    except ValueError:
        return 10


def _dir() -> Path:
    return Path(state.STATE_DIR) / _DIR


def _path(sym: str) -> Path:
    safe = "".join(c for c in sym.upper() if c.isalnum() or c in "._-")[:40]
    return _dir() / f"{safe}.jsonl"


# ── the OFI arithmetic (Cont–Kukanov–Stoikov, per level) ─────────────────────
def _level_ofi(pb, qb, pb0, qb0, pa, qa, pa0, qa0) -> float:
    """One level's OFI increment between consecutive snapshots. CKS:
    e = 1{pb>=pb0}·qb − 1{pb<=pb0}·qb0 − 1{pa<=pa0}·qa + 1{pa>=pa0}·qa0."""
    e = 0.0
    if pb is not None and pb0 is not None:
        if pb >= pb0:
            e += qb or 0.0
        if pb <= pb0:
            e -= qb0 or 0.0
    if pa is not None and pa0 is not None:
        if pa <= pa0:
            e -= qa or 0.0
        if pa >= pa0:
            e += qa0 or 0.0
    return e


def _new_acc(bar: int) -> dict:
    L = _levels()
    return {"bar": bar, "n": 0, "ofi_l": [0.0] * L, "depth_l": [0.0] * L,
            "obi_sum": 0.0, "micro_sum": 0.0, "spread_sum": 0.0, "depth_q_sum": 0.0,
            "l1_depth_sum": 0.0, "dobi_sum": 0.0, "d1s_sum": 0.0, "n_lv": 0,
            "last_mid": None, "prev": None, "prev_ts": 0.0}


def _fold_event(a: dict, rec: dict, ts: float) -> None:
    """Fold one book snapshot into the accumulator (diff vs prev + time-mean stats)."""
    bid, ask = rec.get("bid"), rec.get("ask")
    bq, aq = rec.get("bid_qty") or 0.0, rec.get("ask_qty") or 0.0
    bids, asks = rec.get("bids"), rec.get("asks")
    L = len(a["ofi_l"])
    prev = a["prev"]
    if prev is not None and ts - a["prev_ts"] <= _RESET_S:
        pb0, pa0 = prev.get("bid"), prev.get("ask")
        # L1 (works for both bookTicker and depth snapshots)
        a["ofi_l"][0] += _level_ofi(bid, bq, pb0, prev.get("bid_qty") or 0.0,
                                    ask, aq, pa0, prev.get("ask_qty") or 0.0)
        # deeper levels — only when BOTH snapshots carry levels
        b1, a1 = bids or [], asks or []
        b0, a0 = prev.get("bids") or [], prev.get("asks") or []
        for lv in range(1, min(L, len(b1), len(b0), len(a1), len(a0))):
            a["ofi_l"][lv] += _level_ofi(b1[lv][0], b1[lv][1], b0[lv][0], b0[lv][1],
                                         a1[lv][0], a1[lv][1], a0[lv][0], a0[lv][1])
    # time-mean stats from THIS snapshot
    if bid and ask and bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
        a["last_mid"] = mid                      # bar-close mid → self-contained return labels
        if bq + aq > 0:
            a["obi_sum"] += (bq - aq) / (bq + aq)
            micro = (bid * aq + ask * bq) / (bq + aq)     # microprice (imbalance-weighted)
            a["micro_sum"] += (micro - mid) / mid * 1e4
        a["spread_sum"] += (ask - bid) / mid * 1e4
        a["l1_depth_sum"] += (bq + aq) / 2.0
    for lv in range(min(L, len(bids or []), len(asks or []))):
        a["depth_l"][lv] += ((bids[lv][1] or 0.0) + (asks[lv][1] or 0.0)) / 2.0
    sb = sum((r[1] or 0.0) for r in (bids or [])[:L])
    sa = sum((r[1] or 0.0) for r in (asks or [])[:L])
    a["depth_q_sum"] += sb + sa
    # book-STATE shape (only depth snapshots carry levels; bookTicker frames must not dilute)
    if bids and asks and sb + sa > 0:
        a["dobi_sum"] += (sb - sa) / (sb + sa)
        a["d1s_sum"] += ((bids[0][1] or 0.0) + (asks[0][1] or 0.0)) / (sb + sa)
        a["n_lv"] += 1
    a["n"] += 1
    a["prev"] = rec
    a["prev_ts"] = ts


def _finalize(sym: str, a: dict) -> dict | None:
    """Close a bar → the persisted row. None when the bar saw no events."""
    n = a["n"]
    if n <= 0:
        return None
    try:
        lam = float(os.environ.get("BOOK_OFI_LAMBDA", "3.0") or 3.0)
    except ValueError:
        lam = 3.0
    ofi = a["ofi_l"][0]
    l1_depth = a["l1_depth_sum"] / n
    gofi = 0.0
    for lv, e in enumerate(a["ofi_l"]):
        d = a["depth_l"][lv] / n
        if d > 0:
            gofi += math.exp(-lv / lam) * (e / d)
    return {"ts": a["bar"] * _bar_s(), "n": n,
            "ofi": round(ofi, 6),
            "ofi_n": round(ofi / l1_depth, 6) if l1_depth > 0 else None,
            "gofi": round(gofi, 6),
            "obi": round(a["obi_sum"] / n, 6),
            "microdev_bp": round(a["micro_sum"] / n, 4),
            "spread_bp": round(a["spread_sum"] / n, 4),
            "depth_q": round(a["depth_q_sum"] / n, 4),
            "dobi": round(a["dobi_sum"] / a["n_lv"], 6) if a["n_lv"] else None,
            "d1s": round(a["d1s_sum"] / a["n_lv"], 6) if a["n_lv"] else None,
            # bar-close mid (2026-07-16): forward-return labels straight from the series —
            # IC studies no longer depend on a candle join (ui_candles covers ~45 favorites
            # and goes stale; this store covers all 236 streamed symbols)
            "mid": round(a["last_mid"], 10) if a["last_mid"] else None}


def _append(sym: str, row: dict) -> None:
    p = _path(sym)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, separators=(",", ":")) + "\n"
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode())                    # small single write → atomic append
    finally:
        os.close(fd)
    try:                                               # occasional rotation, cheap size check
        if p.stat().st_size > _KEEP_LINES * 140:
            keep = p.read_text(encoding="utf-8").splitlines()[-_KEEP_LINES // 2:]
            tmp = p.with_suffix(".tmp")
            tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
            os.replace(tmp, p)
    except OSError:
        pass


def on_book(symbol: str, rec: dict, ts: float | None = None) -> None:
    """Event hook: one parsed book snapshot from the app's own stream (ui_market ingest).
    Never raises — this sits inside the funnel's stream pump."""
    try:
        if not enabled() or not symbol or not isinstance(rec, dict):
            return
        now = float(ts if ts is not None else time.time())
        bar = int(now // _bar_s())
        sym = symbol.upper()
        with _lock:
            a = _acc.get(sym)
            if a is None:
                a = _acc[sym] = _new_acc(bar)
            elif a["bar"] != bar:                      # bar rolled → persist the closed bar
                row = _finalize(sym, a)
                prev, prev_ts = a["prev"], a["prev_ts"]
                a2 = _new_acc(bar)
                a2["prev"], a2["prev_ts"] = prev, prev_ts   # diff state carries across bars
                _acc[sym] = a2
                a = a2
                if row:
                    _append(sym, row)
            _fold_event(a, rec, now)
            # sweep: close bars for symbols whose stream went quiet (>=2 bars behind)
            if now - _last_sweep[0] >= 30.0:
                _last_sweep[0] = now
                for s, sa in list(_acc.items()):
                    if s != sym and sa["bar"] < bar - 1:
                        row = _finalize(s, sa)
                        if row:
                            _append(s, row)
                        del _acc[s]
    except Exception:
        pass


def _candidates(symbol: str) -> list[str]:
    s = (symbol or "").upper()
    flat = s.replace("/", "").split(":")[0]
    base = s.split("/")[0].split(":")[0]
    return list(dict.fromkeys(x for x in (flat, base + "USDT", base) if x))


def series(symbol: str, bar_s: int = 300):
    """Stored history for `symbol` as a DataFrame resampled to bar_s bars (ts = bar start,
    ofi/gofi summed, means time-weighted by event count). None when no history exists."""
    try:
        import pandas as pd
        p = None
        for cand in _candidates(symbol):
            q = _path(cand)
            if q.exists():
                p = q
                break
        if p is None:
            return None
        rows = []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["bucket"] = (df["ts"] // bar_s) * bar_s
        df["w"] = df["n"].clip(lower=1)
        g = df.groupby("bucket")
        agg = pd.DataFrame({"of_ofi": g["ofi"].sum(),
                            "of_gofi_book": g["gofi"].sum(),
                            "of_book_n": g["n"].sum()})
        for src, dst in (("ofi_n", "of_ofi_n"), ("obi", "of_obi"),
                         ("microdev_bp", "of_microdev_bp"), ("spread_bp", "of_spread_bp"),
                         ("dobi", "of_dobi"), ("d1s", "of_d1share")):
            if src not in df.columns:            # history predating the field → honest NaN
                agg[dst] = float("nan")
                continue
            m = df[src].notna()                  # rows lacking the field never count as zero
            df["_wx"] = df[src].where(m, 0.0) * df["w"] * m
            df["_wm"] = df["w"] * m
            den = df.groupby("bucket")["_wm"].sum()
            agg[dst] = df.groupby("bucket")["_wx"].sum() / den.where(den > 0)
        # bar-close mid: LAST valid mid in the bucket (a label helper, deliberately NOT in
        # BOOK_FIELDS so it never leaks into the feature bus as a pseudo-feature)
        if "mid" in df.columns:
            agg["of_mid"] = df.dropna(subset=["mid"]).groupby("bucket")["mid"].last()
        else:
            agg["of_mid"] = float("nan")
        return agg.reset_index().rename(columns={"bucket": "ts"})
    except Exception:
        return None


BOOK_FIELDS = ("of_ofi", "of_ofi_n", "of_gofi_book", "of_obi",
               "of_microdev_bp", "of_spread_bp", "of_book_n",
               "of_dobi", "of_d1share")


def status() -> dict:
    """Honest accumulation report: symbols on disk, rows, newest bar age."""
    out = {"enabled": enabled(), "bar_s": _bar_s(), "symbols": 0, "rows": 0,
           "newest_age_s": None, "live_accumulators": len(_acc)}
    try:
        files = sorted(_dir().glob("*.jsonl"))
        out["symbols"] = len(files)
        newest = 0.0
        for p in files:
            try:
                out["rows"] += max(0, sum(1 for _ in open(p, encoding="utf-8")))
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
        if newest:
            out["newest_age_s"] = round(time.time() - newest, 1)
    except OSError:
        pass
    return out
