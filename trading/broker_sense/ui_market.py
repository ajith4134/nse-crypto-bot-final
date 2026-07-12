"""trading/broker_sense/ui_market.py — UI-ONLY market data for EVERYTHING beyond candles.

THE MOTTO (owner-approved 2026-07-12): "Data = web navigation only" — every market data
element the brain needs must come from NAVIGATING the Binance/Upstox account web apps,
not from calling data APIs. ui_data.py is the candles door; THIS module is the door for
every other kind the interception layer already classifies while the eyes browse:

  orderbook · funding/mark_price/index_price · open_interest · long_short · taker_volume
  ticker (→ movers) · liquidation · option_chain · recent_trades

  feed_capture()  — called by interception for every classified REST body / WS frame.
                    Parses the app's OWN payloads (Binance fapi/bapi + WS event shapes,
                    Upstox wrapped rows) into normalized records keyed by (kind, SYMBOL).
  book()/funding()/open_interest()/long_short()/taker()/ticker()/movers()/
  recent_liquidations()/option_chain() — the read paths. Per-kind freshness gates;
                    a stale/missing read returns None HONESTLY (callers record the miss
                    and may fall back to API only when UI-only mode is off).
  coverage()      — the owner's instrument: which kinds/symbols the eyes are feeding.

RAM-first (motto tenet 6) with a merge-written cross-process snapshot (ui_market.json)
so the dashboard/other processes see the funnel's captures. No fabrication: parse
failures are dropped, never guessed.
"""
from __future__ import annotations

import os
import re
import time

from trading import state

_STORE: dict[tuple[str, str], dict] = {}      # (kind, SYMBOL) -> {data, ts, url, broker}
_LIQS: dict[str, list] = {}                   # SYMBOL -> bounded [{ts, side, qty, price}]
_HITS = {"fed": 0, "served": 0, "missed": 0}
_LIQ_MAX = 200
_SNAP_FILE = "ui_market.json"
_SNAP_EVERY_S = 60.0
_SNAP_KEYS_MAX = 4000
_HYDRATE_EVERY_S = 60.0
_last_snap = 0.0
_last_hydrate = 0.0

# Per-kind freshness (s): how old a capture may be and still be served. Matches each
# feed's real cadence in the app (book/ticker stream sub-second; positioning is 5m data).
_FRESH_S = {
    "orderbook": 45.0, "ticker": 60.0, "mark_price": 90.0, "index_price": 90.0,
    "funding": 120.0, "open_interest": 1200.0, "long_short": 1200.0,
    "taker_volume": 1200.0, "option_chain": 1800.0, "recent_trades": 120.0,
    "basis": 1200.0, "movers": 300.0,
}


def _fresh_for(kind: str) -> float:
    try:
        return float(os.environ.get(f"UI_MARKET_FRESH_{kind.upper()}", "") or
                     _FRESH_S.get(kind, 300.0))
    except ValueError:
        return _FRESH_S.get(kind, 300.0)


def _norm_symbol(raw: str) -> str:
    """BTC/USDT:USDT, btcusdt, NSE_EQ|INE… → canonical uppercase token (ui_data parity)."""
    s = re.sub(r"[/:]", "", (raw or "").upper())
    if s.endswith("USDTUSDT"):
        s = s[:-4]
    return re.sub(r"[^A-Z0-9|_-]", "", s)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _unwrap(body):
    """Peel the app's envelopes: combined-WS {"stream","data"}, Indian-broker {"data": …},
    bapi {"code","data"} — down to the payload rows/event."""
    seen = 0
    while isinstance(body, dict) and seen < 3:
        inner = body.get("data")
        if inner is None or not isinstance(inner, (dict, list)):
            break
        body = inner
        seen += 1
    return body


def _url_symbol(url: str) -> str | None:
    m = re.search(r"[?&](?:symbol|instrument_key|pair)=([A-Za-z0-9|_:%-]{2,40})", url or "")
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1))
    return None


def _event_symbol(d: dict) -> str | None:
    for k in ("s", "symbol", "S", "instrument_key", "instrumentKey", "tradingsymbol"):
        v = d.get(k)
        if isinstance(v, str) and 2 <= len(v) <= 40:
            return v
    return None


# ── per-kind parsers: app payload → normalized record ────────────────────────
def _parse_orderbook(d, url, *, stream: str | None = None):
    """Binance REST depth {bids,asks}, WS partial-book {b,a}, bookTicker {b,B,a,A};
    Indian-broker {bids:[{price,quantity}],asks:[…]}. → {bid, ask, bids, asks}.

    DIFF frames are NOT books (live-probe 2026-07-12: a diff's first level said BTC
    bid=1000): futures diff and partial-book events share the same shape, so the stream
    name is the only reliable discriminator — plain @depth = diff (skip), @depthN =
    top-N snapshot (trust). No stream info + update-ids present → assume diff, skip."""
    if not isinstance(d, dict):
        return None
    is_event = d.get("e") == "depthUpdate" or ("u" in d and ("U" in d or "pu" in d))
    if is_event:
        low = (stream or "").lower()
        if "@depth" in low:
            if not re.search(r"@depth\d", low):
                return None                       # plain @depth → diff stream
        elif "levels" not in d:
            return None                           # eventless origin unknown → don't trust
    sym = _event_symbol(d) or _url_symbol(url)
    bids, asks = d.get("bids") or d.get("b"), d.get("asks") or d.get("a")
    if isinstance(bids, str) or isinstance(asks, str):        # bookTicker: b/a are prices
        bid, ask = _f(d.get("b")), _f(d.get("a"))
        if bid is None and ask is None:
            return None
        return sym, {"bid": bid, "ask": ask, "bid_qty": _f(d.get("B")),
                     "ask_qty": _f(d.get("A")), "bids": None, "asks": None}

    def _lvl(row):
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            return [_f(row[0]), _f(row[1])]
        if isinstance(row, dict):
            return [_f(row.get("price") or row.get("p")),
                    _f(row.get("quantity") or row.get("qty") or row.get("q"))]
        return None
    b = [x for x in map(_lvl, bids or []) if x and x[0]][:20]
    a = [x for x in map(_lvl, asks or []) if x and x[0]][:20]
    if not b and not a:
        return None
    return sym, {"bid": b[0][0] if b else None, "ask": a[0][0] if a else None,
                 "bid_qty": b[0][1] if b else None, "ask_qty": a[0][1] if a else None,
                 "bids": b, "asks": a}


def _parse_mark(d, url):
    """markPriceUpdate WS event / premiumIndex REST row → funding + mark + index."""
    if not isinstance(d, dict):
        return None
    sym = _event_symbol(d) or _url_symbol(url)
    mark = _f(d.get("p") or d.get("markPrice") or d.get("mark_price"))
    rate = _f(d.get("r") or d.get("lastFundingRate") or d.get("fundingRate")
              or d.get("funding_rate"))
    if mark is None and rate is None:
        return None
    nft = d.get("T") or d.get("nextFundingTime") or d.get("next_funding_ts")
    return sym, {"mark": mark, "index": _f(d.get("i") or d.get("indexPrice")),
                 "funding_rate": rate,
                 "next_funding_ts": int(nft) if isinstance(nft, (int, float)) and nft else None}


def _parse_ticker(d, url):
    """24hrTicker WS event / REST 24hr row / broker quote row / Binance bulk get-product-dynamic
    row ({s,c,h,l,o,v,qv}) → last + %chg + vol. When no explicit %change field is present (the
    bulk market row), derive it from open→close so the 1000+-symbol bulk screen carries direction."""
    if not isinstance(d, dict):
        return None
    sym = _event_symbol(d) or _url_symbol(url)
    last = _f(d.get("c") or d.get("lastPrice") or d.get("last") or d.get("ltp")
              or d.get("last_price") or d.get("close"))
    if last is None:
        return None
    pct = _f(d.get("P") or d.get("priceChangePercent") or d.get("change_percent")
             or d.get("netChange"))
    if pct is None:                                   # bulk market row: derive from open→close
        op = _f(d.get("o") or d.get("openPrice") or d.get("open"))
        if op:
            pct = round((last - op) / op * 100.0, 4)
    return sym, {"last": last, "pct_change": pct,
                 "high": _f(d.get("h") or d.get("highPrice") or d.get("high")),
                 "low": _f(d.get("l") or d.get("lowPrice") or d.get("low")),
                 "open": _f(d.get("o") or d.get("openPrice") or d.get("open")),
                 "quote_volume": _f(d.get("qv") or d.get("q") or d.get("quoteVolume")),
                 "trades": _f(d.get("n") or d.get("count"))}


def _parse_open_interest(d, url):
    if not isinstance(d, dict):
        return None
    sym = _event_symbol(d) or _url_symbol(url)
    oi = _f(d.get("sumOpenInterestValue") or d.get("openInterest")
            or d.get("sumOpenInterest") or d.get("oi"))
    if oi is None:
        return None
    return sym, {"open_interest": oi, "oi_ts": d.get("timestamp") or d.get("time")}


def _parse_long_short(d, url):
    if not isinstance(d, dict):
        return None
    sym = _event_symbol(d) or _url_symbol(url)
    ratio = _f(d.get("longShortRatio") or d.get("long_short_ratio"))
    lacc = _f(d.get("longAccount") or d.get("long_account"))
    if ratio is None and lacc is None:
        return None
    # topLongShort* URLs are the smart-money variant — keep them distinct from crowd,
    # AND keep account-ratio distinct from position-ratio (they diverge; conflating
    # them would let the account ratio masquerade as position conviction)
    low = (url or "").lower()
    smart = bool(re.search(r"top(?:long|lts)", low))
    variant = "position" if "position" in low else "account"
    return sym, {"ratio": ratio, "long_pct": lacc, "smart": smart, "variant": variant}


def _parse_taker(d, url):
    if not isinstance(d, dict):
        return None
    sym = _event_symbol(d) or _url_symbol(url)
    r = _f(d.get("buySellRatio") or d.get("buy_sell_ratio"))
    if r is None:
        return None
    return sym, {"buy_sell_ratio": r, "buy_vol": _f(d.get("buyVol")),
                 "sell_vol": _f(d.get("sellVol"))}


def _parse_liquidation(d, url):
    """forceOrder event {o:{s,S,q,p,ap,T}} or a bare order dict. Carries the EVENT time
    when present — a captured liquidation-HISTORY array must not be stamped 'now' (the
    orderflow 300s pressure window would count hours-old flushes as current)."""
    if not isinstance(d, dict):
        return None
    o = d.get("o") if isinstance(d.get("o"), dict) else d
    sym = _event_symbol(o) or _url_symbol(url)
    price, qty = _f(o.get("ap") or o.get("p") or o.get("price")), _f(o.get("q") or o.get("qty"))
    side = o.get("S") or o.get("side")
    if not sym or price is None or qty is None or side not in ("BUY", "SELL"):
        return None
    ev = _f(o.get("T") or o.get("time") or o.get("timestamp") or d.get("E"))
    ev_s = ev / 1000.0 if ev and ev > 10**12 else ev
    return sym, {"side": side, "qty": qty, "price": price, "event_ts": ev_s}


_PARSERS = {
    "orderbook": _parse_orderbook, "mark_price": _parse_mark, "funding": _parse_mark,
    "index_price": _parse_mark, "ticker": _parse_ticker,
    "open_interest": _parse_open_interest, "long_short": _parse_long_short,
    "taker_volume": _parse_taker, "liquidation": _parse_liquidation,
}
# kinds stored raw (no per-field normalization yet — served as captured, still useful)
_RAW_KINDS = {"option_chain", "recent_trades", "movers", "basis", "screener"}


_STREAM_SYM_RE = re.compile(r'^([a-z0-9]{2,24})@')


def _stream_hint(body) -> str | None:
    """Combined-WS frames carry the symbol ONLY in the wrapper's stream name
    ({"stream":"btcusdt@depth20@100ms","data":{…}} — partial-depth data has no 's')."""
    if isinstance(body, dict) and isinstance(body.get("stream"), str):
        m = _STREAM_SYM_RE.match(body["stream"])
        if m:
            return m.group(1).upper()
    return None


def feed_capture(broker: str, kind: str, url: str, body) -> int:
    """Interception hook for every classified non-candle payload. Parses + indexes;
    returns how many (kind, symbol) records were stored. Cheap + never raises."""
    try:
        hint = _stream_hint(body)
        stream_name = body.get("stream") if isinstance(body, dict) else None
        d = _unwrap(body)
        stored = 0
        parser = _PARSERS.get(kind)
        if parser is not None:
            rows = d if isinstance(d, list) else [d]
            # arrays push MANY symbols at once (!markPrice@arr, !ticker@arr,
            # openInterestHist…) — the app IS the RAM mirror; index every element.
            # Per-symbol history rows (positioning) come oldest→newest: iterate in
            # order so the LAST (newest) row wins the upsert.
            for row in rows[-400:]:
                got = (parser(row, url, stream=stream_name) if kind == "orderbook"
                       else parser(row, url))
                if not got:
                    continue
                sym, rec = got
                _learn_alias(row)
                sym = _norm_symbol(sym or hint or "")
                if not sym:
                    continue
                if kind == "liquidation":
                    ev = rec.pop("event_ts", None)
                    lst = _LIQS.setdefault(sym, [])
                    lst.append({"ts": ev or time.time(), **rec})
                    del lst[:-_LIQ_MAX]
                    stored += 1
                    continue
                # funding/mark/index all land in ONE mark_price record per symbol —
                # merge so a funding-only row never wipes a fresh mark (and vice versa)
                k = "mark_price" if kind in ("funding", "index_price") else kind
                if k == "long_short" and rec.pop("smart", False):
                    # account vs position ratios stay distinct kinds — they diverge
                    k = ("long_short_smart" if rec.get("variant") == "position"
                         else "long_short_smart_acct")
                rec.pop("variant", None)
                cur = _STORE.get((k, sym))
                if cur and k == "mark_price":
                    merged = dict(cur["data"])
                    merged.update({kk: vv for kk, vv in rec.items() if vv is not None})
                    rec = merged
                _STORE[(k, sym)] = {"data": rec, "ts": time.time(),
                                    "url": (url or "")[:160], "broker": broker}
                stored += 1
        elif kind in _RAW_KINDS:
            sym = _norm_symbol(_url_symbol(url) or
                               (_event_symbol(d) if isinstance(d, dict) else "") or "*")
            _STORE[(kind, sym or "*")] = {"data": d, "ts": time.time(),
                                          "url": (url or "")[:160], "broker": broker}
            stored = 1
        if stored:
            _HITS["fed"] += stored
            _maybe_snapshot()
        return stored
    except Exception:
        return 0


# instrument_key ↔ trading-symbol aliases (Upstox keys stores by NSE_EQ|ISIN while the
# funnel asks by RELIANCE — learned from any app payload carrying BOTH spellings)
_ALIASES: dict[str, str] = {}


def _learn_alias(row) -> None:
    if not isinstance(row, dict):
        return
    ik = row.get("instrument_key") or row.get("instrumentKey")
    ts_ = (row.get("tradingsymbol") or row.get("trading_symbol")
           or row.get("scripname") or row.get("symbol"))
    if isinstance(ik, str) and isinstance(ts_, str) and "|" in ik and "|" not in ts_:
        a, b = _norm_symbol(ik), _norm_symbol(ts_)
        if a and b and a != b:
            _ALIASES[a] = b
            _ALIASES[b] = a


# ── read paths (honest: fresh capture or None) ───────────────────────────────
def _candidates(symbol: str) -> list[str]:
    s = (symbol or "").upper()
    out = [_norm_symbol(s)]
    base = s.split("/")[0].split(":")[0]
    if base and base != s:
        out.append(_norm_symbol(base + "USDT"))
        out.append(_norm_symbol(base))
    for c in list(out):                        # learned instrument-key aliases
        alias = _ALIASES.get(c)
        if alias:
            out.append(alias)
    return list(dict.fromkeys(c for c in out if c))


def _get(kind: str, symbol: str) -> dict | None:
    _hydrate_from_snapshot()
    fresh = _fresh_for(kind)
    for cand in _candidates(symbol):
        row = _STORE.get((kind, cand))
        if row and time.time() - row["ts"] <= fresh:
            _HITS["served"] += 1
            return {**row["data"], "ts": row["ts"], "source": "ui:capture",
                    "broker": row.get("broker")}
    _HITS["missed"] += 1
    return None


def book(symbol: str) -> dict | None:
    """Top-of-book + levels from the app's own depth stream. None when not fresh."""
    return _get("orderbook", symbol)


def funding(symbol: str) -> dict | None:
    """{mark, index, funding_rate, next_funding_ts} from the app's markPrice feed."""
    return _get("mark_price", symbol)


def ticker(symbol: str) -> dict | None:
    return _get("ticker", symbol)


def open_interest(symbol: str) -> dict | None:
    return _get("open_interest", symbol)


def long_short(symbol: str, *, smart: bool = False) -> dict | None:
    return _get("long_short_smart" if smart else "long_short", symbol)


def taker(symbol: str) -> dict | None:
    return _get("taker_volume", symbol)


def option_chain(symbol: str) -> dict | None:
    return _get("option_chain", symbol)


def recent_liquidations(symbol: str, n: int = 50) -> list:
    _hydrate_from_snapshot()
    return list(_LIQS.get(_norm_symbol(symbol), []))[-n:]


def movers(n: int = 20) -> list[dict]:
    """Top movers computed from the app's OWN ticker stream captures (|%chg| ranked).
    Empty list when the eyes haven't fed tickers fresh enough — honest, never faked."""
    _hydrate_from_snapshot()
    now, fresh = time.time(), _fresh_for("ticker")
    rows = [{"symbol": sym, **r["data"]}
            for (kind, sym), r in _STORE.items()
            if kind == "ticker" and now - r["ts"] <= fresh
            and r["data"].get("pct_change") is not None]
    rows.sort(key=lambda r: -abs(r["pct_change"]))
    return rows[:n]


def coverage() -> dict:
    """The owner's meter: kinds × symbols the eyes feed, freshness, hit/miss."""
    _hydrate_from_snapshot()
    now = time.time()
    kinds: dict[str, dict] = {}
    for (kind, sym), row in _STORE.items():
        e = kinds.setdefault(kind, {"symbols": 0, "fresh": 0, "oldest_s": 0.0})
        e["symbols"] += 1
        age = now - row["ts"]
        if age <= _fresh_for(kind):
            e["fresh"] += 1
        e["oldest_s"] = round(max(e["oldest_s"], age), 1)
    total = _HITS["served"] + _HITS["missed"]
    return {"kinds": kinds, "keys": len(_STORE), "liq_symbols": len(_LIQS),
            "fed": _HITS["fed"], "served": _HITS["served"], "missed": _HITS["missed"],
            "hit_rate": round(_HITS["served"] / total, 4) if total else None}


def fresh_kinds(symbol: str) -> list[str]:
    """Which kinds have a fresh capture for `symbol` right now (governor/xray helper)."""
    _hydrate_from_snapshot()
    now = time.time()
    out = []
    cands = set(_candidates(symbol))
    for (kind, sym), row in _STORE.items():
        if sym in cands and now - row["ts"] <= _fresh_for(kind):
            out.append(kind)
    return sorted(set(out))


# ── cross-process snapshot (RAM is truth for the feeder; others hydrate) ─────
def _maybe_snapshot() -> None:
    global _last_snap
    if time.time() - _last_snap < _SNAP_EVERY_S or not _STORE:
        return
    _last_snap = time.time()
    rows = {f"{kind}|{sym}": {"ts": r["ts"], "broker": r.get("broker"),
                              "data": r["data"]}
            for (kind, sym), r in _STORE.items()}
    liqs = {sym: lst[-50:] for sym, lst in _LIQS.items()}
    import threading
    # path resolved NOW: the daemon thread may outlive a test's STATE_DIR monkeypatch
    threading.Thread(target=_write_snapshot,
                     args=(rows, liqs, state._path(_SNAP_FILE)),
                     daemon=True, name="ui-market-snapshot").start()


def _write_snapshot(rows: dict, liqs: dict, path=None) -> None:
    """MERGE-write off the hot path (ui_data pattern): a cold restart must not clobber
    the cross-process store; oldest keys dropped past the cap; readers re-gate freshness.
    `path` is resolved by the spawner (STATE_DIR may change under a daemon thread)."""
    import json as _json
    try:
        p = path if path is not None else state._path(_SNAP_FILE)
        try:
            old = _json.loads(p.read_text()) or {}
        except Exception:
            old = {}
        for k, r in (old.get("rows") or {}).items():
            cur = rows.get(k)
            if cur is None or float((r or {}).get("ts") or 0) > float(cur.get("ts") or 0):
                rows[k] = r
        if len(rows) > _SNAP_KEYS_MAX:
            rows = dict(sorted(rows.items(),
                               key=lambda kv: float((kv[1] or {}).get("ts") or 0)
                               )[-_SNAP_KEYS_MAX:])
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(_json.dumps({"saved_ts": time.time(), "rows": rows,
                                    "liquidations": liqs}))
        os.replace(tmp, p)
    except Exception:
        pass


def _hydrate_from_snapshot() -> None:
    """Non-feeder processes (dashboard, executor) read the funnel's snapshot; a live
    feeder never hydrates (its RAM is the truth). Freshness gates still apply on read."""
    global _last_hydrate
    if _HITS["fed"]:
        return
    now = time.time()
    # throttle on TIME alone: gating on `_STORE and …` left the throttle dead exactly
    # when the store is cold/empty — every read then paid a disk JSON load (hundreds
    # per scan cycle in a non-feeder process before the funnel's first snapshot)
    if now - _last_hydrate < _HYDRATE_EVERY_S:
        return
    _last_hydrate = now
    try:
        snap = state.load_json(_SNAP_FILE, {})
        for key, r in (snap.get("rows") or {}).items():
            kind, _, sym = key.partition("|")
            if not kind or not sym or not isinstance(r, dict) or r.get("data") is None:
                continue
            cur = _STORE.get((kind, sym))
            if cur is not None and float(cur.get("ts") or 0) >= float(r.get("ts") or 0):
                continue
            _STORE[(kind, sym)] = {"data": r["data"], "ts": float(r.get("ts") or 0),
                                   "url": "", "broker": r.get("broker")}
        for sym, lst in (snap.get("liquidations") or {}).items():
            if sym not in _LIQS and isinstance(lst, list):
                _LIQS[sym] = lst[-_LIQ_MAX:]
    except Exception:
        pass
