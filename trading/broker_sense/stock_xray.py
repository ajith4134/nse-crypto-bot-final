"""trading/broker_sense/stock_xray.py — the Upstox Stock X-Ray: one FUSED per-stock snapshot.

When the brain presses "trade" on a stock, capture EVERYTHING about it in one object, fused
from two sources so nothing is missed:

  • STRUCTURED (OpenAlgo API — exact, free, deterministic): multi-timeframe candles, the full
    indicator suite per TF, 20-level market depth + order-book imbalance, open interest, the
    live quote (day range/change/volume), estimated circuit bands, and computed demand/supply
    zones (swing-cluster support/resistance).
  • VISUAL (the FREE eyes on the Upstox Pro app — for anything API-only): the exact upper/lower
    circuit, the TBT (tick-by-tick) chart, Upstox's own summary widgets / demand-zone overlay.
    Optional (needs a headed session) — the structured half stands alone when it's off.

Everything reuses existing infra: OpenAlgoClient (quote/depth/history), indicator_fusion
(indicators_from_ohlcv), and free_eyes (DOM+OCR, no paid vision). Persisted per symbol so the
dashboard panel and the trade journal can show the snapshot that drove each entry.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from trading import state

_TFS = ("1m", "5m", "15m", "1h", "1d")
_XRAY_FILE = "stock_xray.json"          # symbol -> latest snapshot (capped)
_MAX_STORE = 60


# ── OpenAlgo helpers ─────────────────────────────────────────────────────────
def _oa():
    from trading.openalgo_client import OpenAlgoClient
    return OpenAlgoClient()


def _is_option(symbol: str, segment: str) -> bool:
    # a CE/PE suffix is an option ONLY when preceded by a digit (the strike) — else equity names
    # like RELIAN-CE / INFY-PE are misread as options (classic bug). See memory options screener.
    s = (symbol or "").upper()
    if (segment or "").lower() == "options":
        return True
    return len(s) > 2 and s[-2:] in ("CE", "PE") and s[-3].isdigit()


def _opt_exchange(symbol: str, exchange: str, segment: str) -> str:
    """BSE index options live on BFO; other NSE F&O on NFO; equity on NSE."""
    s = (symbol or "").upper()
    if _is_option(symbol, segment) or s.endswith("FUT"):
        return "BFO" if s.startswith(("SENSEX", "BANKEX")) else "NFO"
    return exchange or "NSE"


# ── computed analytics (deterministic, from candles) ─────────────────────────
def demand_supply_zones(candles: list, *, lookback: int = 120, k: int = 3) -> dict:
    """Support (demand) + resistance (supply) levels from swing highs/lows over the candles.
    A swing high/low is a local extremum with `k` lower/higher bars each side; nearby swings
    are clustered (within 0.4%) into zones, ranked by touch count. Deterministic, no I/O."""
    rows = candles[-lookback:] if candles else []
    highs = [_f(r, "high") for r in rows]
    lows = [_f(r, "low") for r in rows]
    closes = [_f(r, "close") for r in rows]
    if len([c for c in closes if c]) < 2 * k + 5:
        return {"demand": [], "supply": [], "available": False}
    sup_lvls, dem_lvls = [], []
    for i in range(k, len(rows) - k):
        if highs[i] and all(highs[i] >= highs[i - j] and highs[i] >= highs[i + j] for j in range(1, k + 1)):
            sup_lvls.append(highs[i])
        if lows[i] and all(lows[i] <= lows[i - j] and lows[i] <= lows[i + j] for j in range(1, k + 1)):
            dem_lvls.append(lows[i])
    price = closes[-1] or 0.0
    return {"available": True, "price": price,
            "supply": _cluster(sup_lvls, price, above=True),
            "demand": _cluster(dem_lvls, price, above=False)}


def _cluster(levels: list, price: float, *, above: bool, tol: float = 0.004) -> list[dict]:
    """Cluster nearby levels into zones {level, touches, dist_pct}, nearest-to-price first."""
    zones: list[dict] = []
    for lv in sorted(levels):
        for z in zones:
            if abs(lv - z["_sum"] / z["touches"]) / (lv or 1) <= tol:
                z["_sum"] += lv
                z["touches"] += 1
                break
        else:
            zones.append({"_sum": lv, "touches": 1})
    out = []
    for z in zones:
        lvl = round(z["_sum"] / z["touches"], 2)
        if price and ((above and lvl >= price) or (not above and lvl <= price)):
            out.append({"level": lvl, "touches": z["touches"],
                        "dist_pct": round((lvl - price) / price * 100.0, 2)})
    out.sort(key=lambda d: abs(d["dist_pct"]))
    return out[:5]


def circuit_bands(quote: dict) -> dict:
    """Estimated NSE price band around prev_close. NSE assigns 2/5/10/20% bands per security;
    OpenAlgo doesn't expose the exact one, so we report the common 10% estimate AND flag it as
    an estimate — the EXACT band is filled from the Upstox visual capture when available."""
    prev = _f(quote, "prev_close") or _f(quote, "close") or _f(quote, "ltp")
    if not prev:
        return {"available": False}
    band = 0.10
    return {"available": True, "estimate": True, "band_pct": band * 100,
            "upper_circuit": round(prev * (1 + band), 2),
            "lower_circuit": round(prev * (1 - band), 2), "reference": prev,
            "note": "10% estimate; exact band from Upstox visual when captured"}


def depth_imbalance(depth: dict) -> dict:
    """Order-book pressure from the depth ladder + total buy/sell quantities."""
    d = depth.get("data", depth) if isinstance(depth, dict) else {}
    tbq, tsq = _f(d, "totalbuyqty"), _f(d, "totalsellqty")
    asks, bids = d.get("asks") or [], d.get("bids") or []
    bid_qty = sum(_f(b, "quantity") for b in bids[:5])
    ask_qty = sum(_f(a, "quantity") for a in asks[:5])
    imb = None
    tot = (tbq or 0) + (tsq or 0)
    if tot:
        imb = round(((tbq or 0) - (tsq or 0)) / tot, 4)      # +1 all buyers .. -1 all sellers
    return {"total_buy_qty": tbq, "total_sell_qty": tsq, "top5_bid_qty": bid_qty,
            "top5_ask_qty": ask_qty, "imbalance": imb,
            "best_bid": _f(bids[0], "price") if bids else None,
            "best_ask": _f(asks[0], "price") if asks else None,
            "levels": {"bids": bids[:20], "asks": asks[:20]}}


# ── the capture ──────────────────────────────────────────────────────────────
def capture(symbol: str, exchange: str = "NSE", segment: str = "intraday", *,
            with_visual: bool = False, sessions=None) -> dict:
    """Build the fused X-Ray snapshot for one symbol. Best-effort — every source degrades to a
    honest empty section (never fabricated) so a partial capture is still useful."""
    oa = _oa()
    exch = _opt_exchange(symbol, exchange, segment)
    snap: dict = {"symbol": symbol, "exchange": exch, "segment": segment,
                  "ts": time.time(), "sources": []}

    # quote + depth (one round each). RAM-FIRST (owner 2026-07-14): the LIVE quote + 5-level book
    # come off the Zerodha Kite in-RAM mirror (paid feed, pushed → no API call), shaped like
    # OpenAlgo's depth response so the analytics below are unchanged. Fall back to the OpenAlgo
    # depth REST only when NSE is not in UI-only/RAM mode or the mirror is cold. (Deep historical
    # candles further down legitimately aren't in the live mirror, so they stay on OpenAlgo.)
    q = None
    src = None
    try:
        from trading.broker_sense import kite_stream as _ks
        kt, kb = _ks.ticker(symbol), _ks.book(symbol)
        if kt and kt.get("last"):
            q = {"data": {
                "ltp": kt.get("last"), "open": kt.get("open"), "high": kt.get("high"),
                "low": kt.get("low"), "prev_close": kt.get("close"),
                "volume": kt.get("volume"), "oi": kt.get("oi"),
                "bids": [{"price": p, "quantity": qq} for p, qq in (kb or {}).get("bids", [])],
                "asks": [{"price": p, "quantity": qq} for p, qq in (kb or {}).get("asks", [])],
            }}
            src = "kite:mirror"
    except Exception:
        q = None
    if q is None:
        _ui_only = False
        try:
            from trading.broker_sense import ui_data
            _ui_only = ui_data.ui_only_for("nse")
        except Exception:
            _ui_only = False
        if not _ui_only:
            try:
                q = oa.depth(symbol, exchange=exch)
                src = "openalgo:depth"
            except Exception as e:
                snap["quote_error"] = str(e)[:120]
    if q is not None:
        try:
            qd = q.get("data", q) if isinstance(q, dict) else {}
            snap["quote"] = {k: qd.get(k) for k in
                             ("ltp", "open", "high", "low", "prev_close", "volume", "oi", "ltq")}
            if qd:
                ltp, prev = _f(qd, "ltp"), _f(qd, "prev_close")
                snap["quote"]["change_pct"] = round((ltp - prev) / prev * 100, 2) if (ltp and prev) else None
            snap["depth"] = depth_imbalance(q)
            snap["circuit"] = circuit_bands(qd)
            snap["open_interest"] = _f(qd, "oi")
            snap["sources"].append(src or "openalgo:depth")
        except Exception as e:
            snap["quote_error"] = str(e)[:120]

    # multi-timeframe candles + indicators. OpenAlgo needs a date window + 'D' for daily; each
    # TF gets a lookback wide enough for the indicator suite (≥200 bars where it matters).
    import datetime as _dt
    from trading.broker_sense.indicator_fusion import indicators_from_ohlcv
    _today = _dt.date.today()
    _TF_MAP = {"1m": ("1m", 3), "5m": ("5m", 8), "15m": ("15m", 20),
               "1h": ("1h", 90), "1d": ("D", 400)}
    multi_tf: dict = {}
    all_candles: dict = {}
    for tf in _TFS:
        iv, days = _TF_MAP.get(tf, (tf, 30))
        try:
            h = oa.history(symbol, exchange=exch, interval=iv,
                           start_date=str(_today - _dt.timedelta(days=days)),
                           end_date=str(_today))
            rows = h.get("data", h) if isinstance(h, dict) else h
            rows = rows if isinstance(rows, list) else []
            all_candles[tf] = rows[-220:]
            # indicators_from_ohlcv expects LIST rows [ts,o,h,l,c,v]; OpenAlgo returns dicts
            listed = _to_list_candles(rows)
            slim = [c for c in (_slim_candle(r) for r in rows[-120:]) if c]   # JSON-safe candles
            multi_tf[tf] = {"n": len(rows),
                            "indicators": indicators_from_ohlcv(listed) if listed else {"available": False},
                            "last": slim[-1] if slim else None,
                            "candles": slim}                  # for the panel's mini-charts
        except Exception as e:
            multi_tf[tf] = {"n": 0, "indicators": {"available": False}, "error": str(e)[:80]}
    snap["timeframes"] = multi_tf
    if any(v.get("n") for v in multi_tf.values()):
        snap["sources"].append("openalgo:history")

    # demand/supply zones from the richest available TF (prefer 1h, else daily/15m)
    base = all_candles.get("1h") or all_candles.get("1d") or all_candles.get("15m") or []
    snap["zones"] = demand_supply_zones(base)

    # options: greeks + OI (from the quote if the venue provides them)
    if _is_option(symbol, segment):
        snap["option"] = {"oi": snap.get("open_interest"),
                          "greeks": {k: _f(snap.get("quote", {}), k)
                                     for k in ("delta", "gamma", "theta", "vega", "iv")}}

    # UI-market door (THE MOTTO 2026-07-12): whatever the eyes captured from the app's
    # own streams for this symbol — book/funding/OI/positioning — rides the X-Ray too,
    # with provenance. Best-effort: an empty door adds nothing.
    try:
        from trading.broker_sense import ui_market
        kinds = ui_market.fresh_kinds(symbol)
        if kinds:
            snap["ui_market"] = {"fresh_kinds": kinds,
                                 "book": ui_market.book(symbol),
                                 "funding": ui_market.funding(symbol),
                                 "open_interest": ui_market.open_interest(symbol),
                                 "long_short": ui_market.long_short(symbol),
                                 "taker": ui_market.taker(symbol)}
            snap["sources"].append("ui:capture")
    except Exception:
        pass

    # derived summary (always available from the structured data)
    snap["summary"] = _summary(snap)

    # VISUAL half (free eyes on Upstox) — optional, exact circuit / TBT / summary widgets
    if with_visual:
        snap["visual"] = _visual_capture(symbol, sessions)
        if snap["visual"].get("available"):
            snap["sources"].append("upstox:free-eyes")

    _persist(symbol, snap)
    return snap


def _summary(snap: dict) -> dict:
    q = snap.get("quote") or {}
    ltp, hi, lo = _f(q, "ltp"), _f(q, "high"), _f(q, "low")
    rng_pos = None
    if ltp and hi and lo and hi > lo:
        rng_pos = round((ltp - lo) / (hi - lo) * 100, 1)     # where in the day's range (0 low..100 high)
    tf1h = (snap.get("timeframes", {}).get("1h") or {}).get("indicators", {})
    return {"change_pct": q.get("change_pct"), "day_range_position_pct": rng_pos,
            "trend_1h": tf1h.get("regime") or tf1h.get("trend"),
            "rsi_1h": tf1h.get("rsi"), "depth_imbalance": (snap.get("depth") or {}).get("imbalance"),
            "nearest_supply": (snap.get("zones", {}).get("supply") or [{}])[0].get("level"),
            "nearest_demand": (snap.get("zones", {}).get("demand") or [{}])[0].get("level")}


def _visual_capture(symbol: str, sessions) -> dict:
    """Read the Upstox stock page with the FREE eyes (DOM+OCR, no paid vision): the exact
    circuit limits, whether a TBT chart is present, and the app's own summary text."""
    try:
        if sessions is None:
            from trading.broker_sense.sessions import get_sessions
            sessions = get_sessions()
        from trading.broker_sense.free_eyes import FreeEyes
        pg = sessions.page("upstox", f"https://pro.upstox.com/stocks/{symbol}", timeout_ms=40000)
        if pg is None:
            return {"available": False, "reason": "no upstox session (need BROKER_SENSE_HEADED=1 + login)"}
        pg.wait_for_timeout(8000)
        eyes = FreeEyes(pg, broker="upstox")
        text = eyes.text()
        import re
        circ = re.findall(r"(?:upper|lower)\s*circuit[^0-9]*([0-9][0-9,.]+)", text, re.I)
        out = {"available": bool(text), "screen_text_excerpt": text[:1500],
               "circuit_seen": circ[:2], "tbt_present": "tbt" in text.lower() or "tick by tick" in text.lower()}
        try:
            pg.close()
        except Exception:
            pass
        return out
    except Exception as e:
        return {"available": False, "reason": str(e)[:120]}


# ── persistence + status ─────────────────────────────────────────────────────
def _persist(symbol: str, snap: dict) -> None:
    try:
        store = state.load_json(_XRAY_FILE, {})
        if not isinstance(store, dict):
            store = {}
        store[symbol.upper()] = snap
        if len(store) > _MAX_STORE:                          # keep the most-recent N symbols
            for k in sorted(store, key=lambda s: store[s].get("ts", 0))[:len(store) - _MAX_STORE]:
                store.pop(k, None)
        state.save_json(_XRAY_FILE, store)
    except Exception:
        pass


def get_xray(symbol: str) -> Optional[dict]:
    try:
        return state.load_json(_XRAY_FILE, {}).get((symbol or "").upper())
    except Exception:
        return None


def latest(limit: int = 20) -> list[dict]:
    try:
        store = state.load_json(_XRAY_FILE, {})
        rows = sorted(store.values(), key=lambda s: s.get("ts", 0), reverse=True)
        return rows[:limit]
    except Exception:
        return []


def capture_on_open(symbol: str, exchange: str = "NSE", segment: str = "intraday") -> None:
    """Fire-and-forget X-Ray capture when a trade opens (structured half; visual off by default
    to stay light + avoid the Upstox profile lock). Never raises into the trade path."""
    try:
        capture(symbol, exchange, segment, with_visual=False)
    except Exception:
        pass


def _to_list_candles(rows: list) -> list:
    """OpenAlgo dict candles → [ts, open, high, low, close, volume] lists (what the indicator
    suite's _ohlc expects). Skips malformed rows."""
    out = []
    for r in rows:
        if not isinstance(r, dict):
            if isinstance(r, (list, tuple)) and len(r) >= 5:
                out.append(list(r))
            continue
        try:
            out.append([r.get("timestamp"), float(r["open"]), float(r["high"]),
                        float(r["low"]), float(r["close"]), float(r.get("volume") or 0)])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _slim_candle(r: Any) -> Optional[dict]:
    """JSON-safe compact candle {t,o,h,l,c,v} (pandas Timestamp → epoch seconds)."""
    if not isinstance(r, dict):
        return None
    ts = r.get("timestamp")
    try:
        t = int(ts.timestamp()) if hasattr(ts, "timestamp") else (int(ts) if ts is not None else None)
    except Exception:
        t = str(ts)
    try:
        return {"t": t, "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                "c": float(r["close"]), "v": float(r.get("volume") or 0)}
    except (KeyError, TypeError, ValueError):
        return None


def _f(d: Any, key: str) -> Optional[float]:
    try:
        v = (d or {}).get(key) if isinstance(d, dict) else None
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None
