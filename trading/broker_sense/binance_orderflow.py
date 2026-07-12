"""trading/broker_sense/binance_orderflow.py — Binance-computed order-flow & positioning features.

Phase-1 order-flow layer of the compute-offload roadmap (research/video/binance-app-improve/plan.md).
Everything here is COMPUTED BY BINANCE and merely read by us — the brain spends no CPU deriving it:

  • funding rate + next-funding countdown          ← in-RAM mirror (push, free)
  • liquidation pressure (recent notional by side) ← in-RAM mirror (push, free)
  • global long/short ACCOUNT ratio (retail crowd) ← /futures/data (REST, 5m cadence)
  • top-trader long/short ACCOUNT + POSITION ratio ← /futures/data (smart-money)
  • taker BUY/SELL volume ratio (aggressor flow)    ← /futures/data
  • open interest + OI %change (conviction)         ← /futures/data

Bounded + cheap: called ONLY for the shortlist the mirror's movers() already narrowed, and every
REST feed is TTL-cached (default 120s — Binance's own cadence is 5m, so this is generous). Reads
that miss/stale return None and are flagged, never faked (honest-wiring). No API keys — public data.

    from trading.broker_sense import binance_orderflow as of
    of.features("BTCUSDT")     # {funding_rate, crowd_long_pct, smart_long_pct, taker_buy_ratio, ...}
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request

from trading.broker_sense.binance_stream import get_mirror

_FAPI = "https://fapi.binance.com"
_TTL = float(os.getenv("BINANCE_ORDERFLOW_TTL", "120") or 120)
_LIQ_WINDOW_S = 300.0            # liquidation pressure looks back this many seconds
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("BINANCE_ORDERFLOW", "1").strip().lower() not in ("0", "false", "off")


def _norm(symbol: str) -> str:
    """Normalize any caller's symbol to Binance USDⓈ-M perp form: BTC/USDT, BTC/USDT:USDT → BTCUSDT."""
    return (symbol or "").upper().replace("/", "").split(":")[0]


# ── cached public REST (Binance computes; we read) ───────────────────────────
def _get_json(url: str):
    """GET + parse JSON. Isolated so tests monkeypatch this, never the network. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mlnb/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _cached(key: str, url: str):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] <= _TTL:
            return hit[1]
    val = _get_json(url)
    if val is not None:
        with _cache_lock:
            _cache[key] = (now, val)
        return val
    with _cache_lock:                       # serve the last good value on a failed refresh (honest: it's cached)
        hit = _cache.get(key)
        return hit[1] if hit else None


def _data(path: str, symbol: str, *, period: str = "5m", limit: int = 1):
    q = urllib.parse.urlencode({"symbol": symbol.upper(), "period": period, "limit": limit})
    return _cached(f"{path}:{symbol}:{period}:{limit}", f"{_FAPI}/futures/data/{path}?{q}")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── the feature pack ─────────────────────────────────────────────────────────
def _ui_only() -> bool:
    """THE MOTTO (2026-07-12): UI-only mode turns off EVERY API path in this module —
    the app's captured order-flow kinds (ui_market) are the sole source; missing kinds
    are honest Nones, never a silent /futures/data poll or public-WS read."""
    try:
        from trading.broker_sense import ui_data
        return ui_data.enabled()
    except Exception:
        return False


def _fund_fields(out: dict, src: dict) -> None:
    """funding_rate/mark/next_funding_in_s from a funding record (one derivation for
    the capture and mirror branches — they must never compute different numbers)."""
    out["funding_rate"] = src.get("funding_rate")
    out["mark"] = src.get("mark")
    nf = src.get("next_funding_ts")
    out["next_funding_in_s"] = (round(max(0.0, nf / 1000.0 - time.time()), 1)
                                if nf else None)


def _liq_pressure(symbol: str, *, ui_only: bool = False) -> dict:
    """Recent liquidation notional by side — the app's captured forceOrder stream first
    (ui_market), the public push mirror only when UI-only mode is off."""
    now = time.time()
    liqs = []
    try:
        from trading.broker_sense import ui_market
        liqs = [x for x in ui_market.recent_liquidations(symbol, 200)
                if now - (x.get("ts") or 0) <= _LIQ_WINDOW_S]
    except Exception:
        pass
    if not liqs and not ui_only:
        liqs = [x for x in get_mirror().recent_liquidations(symbol, 200)
                if now - (x.get("ts") or 0) <= _LIQ_WINDOW_S]
    # Binance forceOrder side is the side of the LIQUIDATION order: SELL = a long got liquidated.
    long_liq = sum((x.get("qty") or 0) * (x.get("price") or 0) for x in liqs if x.get("side") == "SELL")
    short_liq = sum((x.get("qty") or 0) * (x.get("price") or 0) for x in liqs if x.get("side") == "BUY")
    tot = long_liq + short_liq
    return {
        "liq_long_notional": round(long_liq, 2), "liq_short_notional": round(short_liq, 2),
        "liq_count": len(liqs),
        # >0 → longs being flushed (down-pressure); <0 → shorts squeezed (up-pressure)
        "liq_skew": round((long_liq - short_liq) / tot, 4) if tot > 0 else None,
    }


def features(symbol: str, *, cheap: bool = False) -> dict:
    """Binance-computed order-flow/positioning features for one shortlisted symbol.

    Every value is read (mirror or cached REST), never locally derived. Missing/stale → None,
    with `source` provenance. Mirror reads are RAM; REST is TTL-cached to Binance's cadence.
    `cheap=True` (WIDE-universe pass): mirror-only (funding + liquidations) — SKIPS the per-symbol
    /futures/data REST (long-short/taker/OI) so a 600-symbol pass stays fast and never trips
    Binance's 1000/5min data-endpoint rate limit."""
    sym = _norm(symbol)
    out: dict = {"symbol": sym, "source": "binance", "ts": time.time()}
    if not enabled():
        out["enabled"] = False
        return out

    ui_only = _ui_only()                      # one read — features() runs per symbol
    # 0) THE MOTTO: the app's OWN captured feeds serve every kind they can, first.
    # Values are set only when the capture actually CARRIES them — a partial capture
    # must not plant a None that blocks the (still allowed) REST/mirror backfill.
    try:
        from trading.broker_sense import ui_market
    except Exception:
        ui_market = None
    if ui_market is not None:
        mk = ui_market.funding(sym)
        if mk and mk.get("funding_rate") is not None:
            _fund_fields(out, mk)
            out["funding_stale"] = False
            out["source"] = "ui:capture"
        ls = ui_market.long_short(sym)
        if ls and ls.get("ratio") is not None:
            out["crowd_long_short"] = ls["ratio"]
        if ls and ls.get("long_pct") is not None:
            out["crowd_long_pct"] = ls["long_pct"]
        lss = ui_market.long_short(sym, smart=True)
        if lss and lss.get("ratio") is not None:
            out["smart_pos_long_short"] = lss["ratio"]
        if lss and lss.get("long_pct") is not None:
            out["smart_long_pct"] = lss["long_pct"]
        tkc = ui_market.taker(sym)
        if tkc and tkc.get("buy_sell_ratio") is not None:
            out["taker_buy_sell_ratio"] = tkc["buy_sell_ratio"]
        oic = ui_market.open_interest(sym)
        if oic and oic.get("open_interest") is not None:
            out["open_interest_usd"] = oic["open_interest"]

    # 1) funding + countdown (public mirror, push) — failsafe only, off in UI-only mode
    if out.get("funding_rate") is None and not ui_only:
        mk = get_mirror().funding(sym)
        if mk:
            _fund_fields(out, mk)
        out["funding_stale"] = get_mirror().is_stale(sym)
    out.setdefault("funding_stale", out.get("funding_rate") is None)

    # 2) liquidation pressure (captures first; mirror gated inside)
    out.update(_liq_pressure(sym, ui_only=ui_only))

    if cheap or ui_only:      # mirror/UI-only: never the per-symbol /futures/data REST
        return out

    # 3) crowd positioning — global account long/short (retail; contrarian at extremes)
    if out.get("crowd_long_pct") is None:
        g = _data("globalLongShortAccountRatio", sym)
        if isinstance(g, list) and g:
            out["crowd_long_short"] = _f(g[-1].get("longShortRatio"))
            out["crowd_long_pct"] = _f(g[-1].get("longAccount"))

    # 4) smart-money — top-trader account + position long/short
    if out.get("smart_acct_long_short") is None:
        ta = _data("topLongShortAccountRatio", sym)
        if isinstance(ta, list) and ta:
            out["smart_acct_long_short"] = _f(ta[-1].get("longShortRatio"))
    if out.get("smart_long_pct") is None:
        tp = _data("topLongShortPositionRatio", sym)
        if isinstance(tp, list) and tp:
            out["smart_pos_long_short"] = _f(tp[-1].get("longShortRatio"))
            out["smart_long_pct"] = _f(tp[-1].get("longAccount"))

    # 5) aggressor flow — taker buy/sell volume
    if out.get("taker_buy_sell_ratio") is None:
        tk = _data("takerlongshortRatio", sym)
        if isinstance(tk, list) and tk:
            out["taker_buy_sell_ratio"] = _f(tk[-1].get("buySellRatio"))

    # 6) open interest + %change (conviction) — need 2 points for the delta
    if out.get("open_interest_usd") is None:
        oi = _data("openInterestHist", sym, limit=2)
        if isinstance(oi, list) and oi:
            cur = _f(oi[-1].get("sumOpenInterestValue"))
            out["open_interest_usd"] = cur
            if len(oi) >= 2:
                prev = _f(oi[-2].get("sumOpenInterestValue"))
                if cur is not None and prev:
                    out["oi_change_pct"] = round((cur - prev) / prev * 100.0, 3)
    return out


def signal(symbol: str, *, cheap: bool = False) -> dict:
    """A compact, brain-friendly read of the order-flow pack: a directional tilt in [-1,1] plus
    the raw features. Tilt is a transparent blend — the brain's ML decides how to weight it.
    `cheap=True` = mirror-only (no per-symbol REST) for the wide-universe pass.

    Convention: +1 = flow/positioning leans LONG-favourable, -1 = SHORT-favourable."""
    f = features(symbol, cheap=cheap)
    votes: list[float] = []
    # aggressor flow: taker buy/sell ratio > 1 → buyers lifting → long tilt
    if f.get("taker_buy_sell_ratio") is not None:
        r = f["taker_buy_sell_ratio"]
        votes.append(max(-1.0, min(1.0, (r - 1.0) * 2.0)))
    # retail crowd is contrarian: crowd very long → short tilt
    if f.get("crowd_long_pct") is not None:
        votes.append(max(-1.0, min(1.0, (0.5 - f["crowd_long_pct"]) * 4.0)))
    # smart money is follow: top traders long → long tilt
    if f.get("smart_long_pct") is not None:
        votes.append(max(-1.0, min(1.0, (f["smart_long_pct"] - 0.5) * 4.0)))
    # liquidation skew: longs flushed (skew>0) → short-term down pressure → short tilt
    if f.get("liq_skew") is not None:
        votes.append(-f["liq_skew"])
    tilt = round(sum(votes) / len(votes), 4) if votes else None
    return {"symbol": f["symbol"], "tilt": tilt, "n_signals": len(votes), "features": f}


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
