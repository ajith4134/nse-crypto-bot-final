"""trading/broker_sense/binance_stream.py — Binance all-market WEBSOCKET mirror (compute-offload).

Owner mandate (2026-07-11): migrate universe-wide work off local CPU onto Binance — the brain's
CPU is reserved for ML. The lag-free way to do that is NOT to poll Binance per decision; it is to
subscribe ONCE to Binance's all-market PUSH streams and keep a live in-RAM snapshot that Binance
updates for us. The brain then reads the whole universe from RAM in microseconds — no network call
at decision time, no local recompute (Binance ships the computed values), ~0 idle CPU (push, not poll).

ONE futures connection (`wss://fstream.binance.com`, combined-stream mode) carries the whole universe:
  • !markPrice@arr  → mark price + FUNDING RATE + next-funding-time for every perp (~1–3s cadence)
  • !ticker@arr     → 24h %change / high / low / quote-volume / trade-count for every symbol
  • !forceOrder@arr → every liquidation, as it happens (reversal/squeeze signal)

Robust (kills option-2's brittleness): auto-reconnect w/ backoff, REST snapshot backfill on connect,
per-field last-update ts + staleness flag (a stale field is REPORTED stale, never served as fresh),
graceful degrade to nothing (callers keep their local fallback) if `websockets` is missing or the
feed is cold. Kill switch: BINANCE_STREAM=0. This module holds NO keys — all feeds are public.

Read API (all pure RAM reads):
    m = get_mirror(); m.start()
    m.movers(30, by="quote_volume")   # Tier-0 universe narrowing → shortlist, on Binance's numbers
    m.funding("BTCUSDT"); m.mark("BTCUSDT"); m.ticker("ETHUSDT")
    m.recent_liquidations("BTCUSDT", 20); m.status()
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque

from trading import state

# Binance restructured futures WS routing to a dedicated /market/ PUBLIC entry point (2025+):
# the old /ws/ and /stream?streams= paths now connect but deliver NO frames. Verified live
# 2026-07-11: /market/stream?streams=... delivers; the others time out. markPrice@arr@1s = 1s cadence.
_WS_URL = ("wss://fstream.binance.com/market/stream?streams="
           "!markPrice@arr@1s/!ticker@arr/!forceOrder@arr")
_STALE_AFTER_S = 15.0            # a push field older than this is flagged stale (streams tick ~1–3s)
_MAX_LIQS = 500
_HIST_EVERY_S = 15.0            # sample the price history at most this often per symbol
_HIST_MAXLEN = 320             # ~80 min of history per symbol (covers every direction horizon)
# In-RAM multi-timeframe OHLC candles (2026-07-13): built live from the same all-market
# markPrice@1s stream — every perp gets multi-TF candles WITHOUT an API/kline call (motto:
# data off the browser/WS surface, RAM for speed). Mark-price OHLC (no volume); the CoinGecko
# bulk door + per-symbol kline WS remain the complements for traded OHLCV / deep history.
_CANDLE_TFS = tuple(int(x) for x in (os.getenv("BINANCE_CANDLE_TFS", "60,300,900")).split(",") if x)
_CANDLE_MAXLEN = int(os.getenv("BINANCE_CANDLE_MAXLEN", "240") or 240)   # bars kept per (sym,tf)
# DEPTH mirror (2026-07-12): per-symbol 20-level partial book for the top-N movers, pushed at 500ms,
# so psychology (OBI/microprice/walls) reads depth from RAM instead of a ~300ms REST fetch_order_book
# per symbol × the shortlist (the funnel EXECUTE hotspot). Bounded: N streams in one connection,
# symbol set refreshed by reconnect. All-market full depth is a firehose, so we scope to the movers.
_DEPTH_HOST = "wss://fstream.binance.com/stream?streams="
_DEPTH_N = int(os.getenv("BINANCE_DEPTH_N", "120") or 120)      # streams per connection (cap)
_DEPTH_REFRESH_S = float(os.getenv("BINANCE_DEPTH_REFRESH_S", "300") or 300)   # re-pick movers

# TAKER flow from the trade PUSH stream (2026-07-16) — NO API. The owner asked for a non-API way to
# get taker/OI/long-short into RAM; taker is the one that has one. `<sym>@aggTrade` carries `m` =
# "was the buyer the maker?", so m=False → the BUYER lifted the ask (taker BUY volume) and m=True →
# the seller hit the bid (taker SELL volume). That is exactly what Binance's own
# /futures/data/takerlongshortRatio reports, derived from the venue's own trade push instead of a
# REST poll. Accumulated into fixed time BUCKETS (O(1) per trade, ~6 dicts/symbol) — never a
# per-trade deque, which would be a firehose at 120 symbols.
#
# ⚠ ENTRY POINT: aggTrade needs the NEW /market/ path — it is NOT deliverable on the legacy
# /stream?streams= host that depth uses. Probed live 2026-07-16:
#     /stream?streams=…@depth20@500ms/…@aggTrade        → depth frames only, ZERO aggTrade
#     /market/stream?streams=…@depth20@500ms/…@aggTrade → aggTrade frames only, ZERO depth
# The two kinds cannot share one socket: depth stays on the legacy host (where it demonstrably
# works) and aggTrade gets its own connection. Piggy-backing aggTrade onto the depth URL looks
# correct and silently yields NOTHING — the same 2025 routing change documented for _WS_URL above.
_AGG_HOST = "wss://fstream.binance.com/market/stream?streams="
_AGG_N = int(os.getenv("BINANCE_AGG_N", "120") or 120)                  # movers streamed for taker
_AGG_REFRESH_S = float(os.getenv("BINANCE_AGG_REFRESH_S", "300") or 300)
_TAKER_BUCKET_S = float(os.getenv("BINANCE_TAKER_BUCKET_S", "60") or 60)
_TAKER_BUCKETS = int(os.getenv("BINANCE_TAKER_BUCKETS", "5") or 5)      # → 5 min rolling window

# OI + LONG/SHORT stats poller (2026-07-16). These have NO WebSocket stream on Binance (verified
# against the official WS market-streams doc: only bookTicker/depth/aggTrade/markPrice/forceOrder/
# kline/ticker exist; open interest and the long-short account ratios live under market-data/rest-api/).
# The only non-API route is the browser, whose measured ceiling is ~6 symbol pages and a 25-44 h
# median age → 0-1.5% coverage. Owner's rule 2026-07-16: "if the other method has more cons than the
# API, then use the API for the rest of the missing data." So: a BACKGROUND poller fills RAM, and the
# DECISION path still reads pure RAM — no network call when the brain decides. Budget: 4 calls ×
# _STATS_N per _STATS_REFRESH_S (=400/5min at the default 100) vs Binance's /futures/data limit
# of 1000 per 5 min per IP.
_STATS_N = int(os.getenv("BINANCE_STATS_N", "100") or 100)
_STATS_REFRESH_S = float(os.getenv("BINANCE_STATS_REFRESH_S", "300") or 300)
_STATS_FRESH_S = float(os.getenv("BINANCE_STATS_FRESH_S", "1800") or 1800)


def depth_enabled() -> bool:
    return enabled() and os.getenv("BINANCE_STREAM_DEPTH", "1").strip().lower() not in ("0", "false", "off")


def stats_enabled() -> bool:
    """The OI/long-short REST poller. Kill switch: BINANCE_STATS=0 → those kinds fall back to the
    browser capture (and to the per-symbol REST already in binance_orderflow)."""
    return enabled() and os.getenv("BINANCE_STATS", "1").strip().lower() not in ("0", "false", "off")


def enabled() -> bool:
    return os.getenv("BINANCE_STREAM", "1").strip().lower() not in ("0", "false", "off")


class BinanceUniverseMirror:
    """Live in-RAM snapshot of Binance USDⓈ-M futures, updated by the all-market push streams."""

    def __init__(self):
        self._mark: dict[str, dict] = {}        # symbol -> {mark, funding_rate, next_funding_ts, ts}
        self._ticker: dict[str, dict] = {}       # symbol -> {last, pct_change, high, low, quote_volume, count, ts}
        # rolling price history (2026-07-13): the all-market stream carries EVERY perp's mark
        # price every 1s → keep a throttled per-symbol time-series so the truth-ledger can look
        # up the price at ANY horizon and resolve 100% of claims (not just BTC/ETH). Bounded.
        self._hist: dict[str, deque] = {}        # symbol -> deque[(ts, mark)]
        self._hist_last: dict[str, float] = {}   # symbol -> last-append ts (throttle)
        self._candles: dict[str, dict] = {}      # symbol -> {tf_s -> deque[[bar_ts,o,h,l,c]]}
        self._book: dict[str, dict] = {}         # symbol -> {bids:[[p,q]], asks:[[p,q]], ts} (20-lvl depth)
        self._liqs: deque = deque(maxlen=_MAX_LIQS)   # recent liquidation events (all symbols)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._taker: dict[str, deque] = {}        # symbol -> deque[{bucket, buy, sell}] (taker flow)
        self._stats: dict[str, dict] = {}         # symbol -> {open_interest_usd, oi_change_pct, …}
        self._stats_thread: threading.Thread | None = None
        self._stats_ts = 0.0
        self._stats_calls = 0
        self._depth_thread: threading.Thread | None = None
        self._agg_thread: threading.Thread | None = None
        self._agg_connected = False
        self._running = False
        self._connected = False
        self._depth_connected = False
        self._depth_watch: list[str] = []        # the top-N symbols we currently stream depth for
        self._depth_last_msg_ts = 0.0
        self._reconnects = 0
        self._last_msg_ts = 0.0
        self._started_ts = 0.0

    # ── frame parsing (PURE — unit-testable without a socket) ────────────────
    def _apply_frame(self, msg: dict) -> None:
        """Apply one combined-stream frame ({"stream","data"}) to the in-RAM snapshot. Never raises."""
        applied = False
        try:
            stream = msg.get("stream", "")
            data = msg.get("data")
            now = time.time()
            self._last_msg_ts = now
            if stream.startswith("!markPrice") and isinstance(data, list):
                applied = True
                with self._lock:
                    for d in data:
                        s = d.get("s")
                        if not s:
                            continue
                        mk = _f(d.get("p"))
                        self._mark[s] = {
                            "mark": mk,
                            "funding_rate": _f(d.get("r")),
                            "next_funding_ts": _i(d.get("T")),
                            "ts": now,
                        }
                        if mk is not None:
                            # throttled price history (every _HIST_EVERY_S) for horizon resolution
                            if now - self._hist_last.get(s, 0.0) >= _HIST_EVERY_S:
                                h = self._hist.get(s)
                                if h is None:
                                    h = self._hist[s] = deque(maxlen=_HIST_MAXLEN)
                                h.append((now, mk))
                                self._hist_last[s] = now
                            # live multi-TF OHLC candles from the SAME stream (no API call)
                            self._roll_candles(s, mk, now)
            elif stream.startswith("!ticker") and isinstance(data, list):
                applied = True
                with self._lock:
                    for d in data:
                        s = d.get("s")
                        if not s:
                            continue
                        self._ticker[s] = {
                            "last": _f(d.get("c")),
                            "pct_change": _f(d.get("P")),
                            "high": _f(d.get("h")),
                            "low": _f(d.get("l")),
                            "quote_volume": _f(d.get("q")),
                            "count": _i(d.get("n")),
                            "ts": now,
                        }
            elif stream.startswith("!forceOrder"):
                applied = True
                o = (data or {}).get("o") if isinstance(data, dict) else None
                if isinstance(o, dict) and o.get("s"):
                    _S = o.get("S")
                    with self._lock:
                        self._liqs.append({
                            "symbol": o.get("s"), "side": _S,
                            # normalized POSITION side liquidated: a Binance forceOrder SELL
                            # force-sells a LONG (long liquidation), BUY force-buys a SHORT
                            # (short liquidation) — the opposite of the order side. Stamping
                            # pos_side here lets signals() count short/long cascades correctly
                            # regardless of the source's convention (2026-07-13 coverage lane).
                            "pos_side": ("long" if _S == "SELL" else
                                         "short" if _S == "BUY" else None),
                            "qty": _f(o.get("q")), "price": _f(o.get("p")),
                            "ts": _i(o.get("T")) / 1000.0 if o.get("T") else now,
                        })
        except Exception:
            pass
        # JSON schema-drift watcher (adopt item 2): only DATA frames (those carrying a
        # "stream") count — subscription acks / pings must not look like a decode failure.
        try:
            if isinstance(msg, dict) and msg.get("stream"):
                from trading.broker_sense import feed_selfheal
                feed_selfheal.note_json("binance", msg, ok=applied)
        except Exception:
            pass

    def _apply_depth_frame(self, msg: dict) -> None:
        """Apply one <sym>@depth20 combined-stream frame → in-RAM 20-level book. Never raises."""
        try:
            stream = msg.get("stream", "")
            data = msg.get("data") or {}
            if "@depth" not in stream:
                return
            s = (data.get("s") or stream.split("@", 1)[0]).upper()
            bids = [[float(p), float(q)] for p, q in (data.get("b") or []) if float(q) > 0]
            asks = [[float(p), float(q)] for p, q in (data.get("a") or []) if float(q) > 0]
            if not bids or not asks:
                return
            now = time.time()
            self._depth_last_msg_ts = now
            with self._lock:
                self._book[s] = {"bids": bids, "asks": asks, "ts": now}
        except Exception:
            return
        # TRUE L2 OFI/GOFI history off the RAM depth stream (motto 2026-07-16: RAM is primary).
        # book_ofi was wired ONLY to the browser capture, which keeps ~6 books fresh at a time
        # (median age 25 h vs its 45 s TTL) — so the research's #1/#2 ranked direction drivers
        # were computed for almost nothing. This connection already pushes 20-level depth for
        # the top-N movers every 500 ms, so the same accumulator now gets ~120 symbols at a
        # real cadence. Outside the lock (fold is O(levels) arithmetic) and never raises, so a
        # book_ofi fault can't kill the mirror thread.
        # The record must match book_ofi's contract exactly ({bid, ask, bid_qty, ask_qty, bids,
        # asks}, same shape ui_market._parse_orderbook emits): without the L1 fields it silently
        # skips the L1 OFI increment AND every time-mean stat (obi/microprice/spread/L1 depth).
        # @depth20 sends bids best-first descending and asks best-first ascending.
        try:
            from trading.broker_sense import book_ofi
            book_ofi.on_book(s, {"bid": bids[0][0], "bid_qty": bids[0][1],
                                 "ask": asks[0][0], "ask_qty": asks[0][1],
                                 "bids": bids, "asks": asks}, now)
        except Exception:
            pass

    def _apply_agg_frame(self, msg: dict) -> None:
        """Apply one <sym>@aggTrade frame → the in-RAM taker-flow buckets. Never raises.

        `m` = "was the buyer the maker?": m=False → buyer was the TAKER (bought at the ask) →
        taker BUY volume; m=True → the seller was the taker → taker SELL volume. Bucketed by
        wall-clock so the read is a cheap sum over ~5 buckets instead of a per-trade scan."""
        try:
            stream = msg.get("stream", "")
            data = msg.get("data") or {}
            if "@aggtrade" not in stream.lower():
                return
            s = (data.get("s") or stream.split("@", 1)[0]).upper()
            qty, price = float(data.get("q") or 0.0), float(data.get("p") or 0.0)
            if qty <= 0 or price <= 0:
                return
            notional = qty * price                      # value-weighted, like Binance's own ratio
            is_taker_buy = not bool(data.get("m"))
            bucket = int(time.time() // _TAKER_BUCKET_S)
            with self._lock:
                dq = self._taker.get(s)
                if dq is None:
                    dq = self._taker[s] = deque(maxlen=_TAKER_BUCKETS)
                if not dq or dq[-1]["bucket"] != bucket:
                    dq.append({"bucket": bucket, "buy": 0.0, "sell": 0.0})
                cur = dq[-1]
                cur["buy" if is_taker_buy else "sell"] += notional
        except Exception:
            pass

    def taker(self, symbol: str) -> dict | None:
        """Taker buy/sell flow over the rolling window, from the venue's own trade push — NO API.
        Returns None (honest miss) when no trades have been seen in-window for `symbol`."""
        s = symbol.upper()
        cutoff = int(time.time() // _TAKER_BUCKET_S) - _TAKER_BUCKETS
        with self._lock:
            dq = self._taker.get(s)
            if not dq:
                return None
            buy = sum(b["buy"] for b in dq if b["bucket"] > cutoff)
            sell = sum(b["sell"] for b in dq if b["bucket"] > cutoff)
        if buy <= 0 and sell <= 0:
            return None
        return {
            "taker_buy_notional": round(buy, 2), "taker_sell_notional": round(sell, 2),
            # Binance's takerlongshortRatio convention: buyVol / sellVol (>1 = buyers lifting).
            # Undefined when the window saw NO taker sells (thin symbol / short window) — report
            # None honestly rather than invent a cap, and let the caller fall back. `imbalance` is
            # always defined, so a one-sided window still carries its signal.
            "buy_sell_ratio": round(buy / sell, 4) if sell > 0 else None,
            "imbalance": round((buy - sell) / (buy + sell), 4),      # [-1,1], +1 = all taker buys
            "window_s": _TAKER_BUCKET_S * _TAKER_BUCKETS, "source": "ram:aggtrade",
        }

    def stats(self, symbol: str) -> dict | None:
        """Open interest + crowd/smart long-short for `symbol` from RAM (filled by the background
        poller — see _run_stats). None when unseen or older than _STATS_FRESH_S: an honest miss,
        never a stale number served as fresh."""
        s = symbol.upper()
        with self._lock:
            row = self._stats.get(s)
        if not row or time.time() - (row.get("ts") or 0) > _STATS_FRESH_S:
            return None
        return dict(row)

    def _run_stats(self) -> None:
        """Background REST poller for the two kinds Binance publishes on NO WebSocket stream:
        open interest and the long/short account ratios. Keeps the DECISION path pure-RAM.

        Deliberate design (owner 2026-07-16): the brain must be fast to decide and open trades, so
        no per-symbol REST at decision time. Scoped to the top-_STATS_N movers and rate-budgeted:
        3 calls/symbol per cycle vs Binance's 1000-per-5-min /futures/data limit."""
        import urllib.request

        def _get(path: str, sym: str, limit: int = 1):
            url = (f"https://fapi.binance.com/futures/data/{path}"
                   f"?symbol={sym}&period=5m&limit={limit}")
            with urllib.request.urlopen(url, timeout=8) as r:
                self._stats_calls += 1
                return json.loads(r.read().decode())

        while self._running:
            try:
                syms = [r["symbol"] for r in self.movers(_STATS_N, by="quote_volume")]
                for sym in syms:
                    if not self._running:
                        break
                    row: dict = {"ts": time.time(), "source": "ram:stats"}
                    try:
                        oi = _get("openInterestHist", sym, limit=2)
                        if isinstance(oi, list) and oi:
                            cur = _f(oi[-1].get("sumOpenInterestValue"))
                            row["open_interest_usd"] = cur
                            if len(oi) >= 2:
                                prev = _f(oi[-2].get("sumOpenInterestValue"))
                                if cur is not None and prev:
                                    row["oi_change_pct"] = round((cur - prev) / prev * 100.0, 3)
                    except Exception:
                        pass
                    try:
                        g = _get("globalLongShortAccountRatio", sym)
                        if isinstance(g, list) and g:
                            row["crowd_long_short"] = _f(g[-1].get("longShortRatio"))
                            row["crowd_long_pct"] = _f(g[-1].get("longAccount"))
                    except Exception:
                        pass
                    try:
                        tp = _get("topLongShortPositionRatio", sym)
                        if isinstance(tp, list) and tp:
                            row["smart_pos_long_short"] = _f(tp[-1].get("longShortRatio"))
                            row["smart_long_pct"] = _f(tp[-1].get("longAccount"))
                    except Exception:
                        pass
                    try:
                        # top-trader ACCOUNT ratio — the 4th field binance_orderflow would other-
                        # wise still REST for at decision time, which would defeat the whole point
                        ta = _get("topLongShortAccountRatio", sym)
                        if isinstance(ta, list) and ta:
                            row["smart_acct_long_short"] = _f(ta[-1].get("longShortRatio"))
                    except Exception:
                        pass
                    if len(row) > 2:                      # more than ts+source → real data
                        with self._lock:
                            self._stats[sym] = row
                    time.sleep(0.15)                      # gentle pacing inside the cycle
                self._stats_ts = time.time()
            except Exception:
                pass
            for _ in range(int(_STATS_REFRESH_S)):        # interruptible sleep
                if not self._running:
                    return
                time.sleep(1.0)

    # ── background stream thread ─────────────────────────────────────────────
    def _run(self) -> None:
        try:
            asyncio.run(self._stream_loop())
        except Exception:
            self._connected = False

    async def _stream_loop(self) -> None:
        try:
            import websockets
        except Exception:
            return                              # no ws lib → callers keep their local fallback
        backoff = 1.0
        while self._running:
            try:
                async with websockets.connect(_WS_URL, ping_interval=20, ping_timeout=20,
                                              open_timeout=15, max_queue=1024) as ws:
                    self._connected = True
                    backoff = 1.0
                    last_snap = 0.0
                    while self._running:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        try:
                            self._apply_frame(json.loads(raw))
                        except Exception:
                            continue
                        if time.time() - last_snap >= 10.0:      # dashboard snapshot every ~10s
                            last_snap = time.time()
                            self.write_snapshot()
            except Exception:
                self._connected = False
                self._reconnects += 1
                await asyncio.sleep(min(backoff, 30.0))
                backoff *= 2                     # exponential backoff on reconnect
        self._connected = False

    def _run_depth(self) -> None:
        try:
            asyncio.run(self._depth_stream_loop())
        except Exception:
            self._depth_connected = False

    async def _depth_stream_loop(self) -> None:
        """Stream 20-level partial book for the top-N movers; reconnect every _DEPTH_REFRESH_S to
        re-pick the set as the universe rotates. One connection, N streams — bounded, no firehose."""
        try:
            import websockets
        except Exception:
            return
        backoff = 1.0
        while self._running:
            # wait until the ticker mirror has enough universe to rank movers
            syms = [r["symbol"] for r in self.movers(_DEPTH_N, by="quote_volume")]
            if not syms:
                await asyncio.sleep(2.0)
                continue
            self._depth_watch = syms
            # depth ONLY — aggTrade is not deliverable on this legacy host (see _AGG_HOST); it
            # runs on its own /market/ connection in _agg_stream_loop.
            url = _DEPTH_HOST + "/".join(f"{s.lower()}@depth20@500ms" for s in syms)
            deadline = time.time() + _DEPTH_REFRESH_S
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20,
                                              open_timeout=15, max_queue=2048) as ws:
                    self._depth_connected = True
                    backoff = 1.0
                    while self._running and time.time() < deadline:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        try:
                            self._apply_depth_frame(json.loads(raw))
                        except Exception:
                            continue
            except Exception:
                self._depth_connected = False
                self._reconnects += 1
                await asyncio.sleep(min(backoff, 30.0))
                backoff *= 2
        self._depth_connected = False

    def _run_agg(self) -> None:
        try:
            asyncio.run(self._agg_stream_loop())
        except Exception:
            self._agg_connected = False

    async def _agg_stream_loop(self) -> None:
        """Stream `@aggTrade` for the top-N movers on the /market/ entry point → in-RAM taker flow.
        Its own connection because the legacy depth host delivers no aggTrade frames (see _AGG_HOST).
        Reconnects every _AGG_REFRESH_S to re-pick movers as the universe rotates."""
        try:
            import websockets
        except Exception:
            return
        backoff = 1.0
        while self._running:
            syms = [r["symbol"] for r in self.movers(_AGG_N, by="quote_volume")]
            if not syms:
                await asyncio.sleep(2.0)
                continue
            url = _AGG_HOST + "/".join(f"{s.lower()}@aggTrade" for s in syms)
            deadline = time.time() + _AGG_REFRESH_S
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20,
                                              open_timeout=15, max_queue=4096) as ws:
                    self._agg_connected = True
                    backoff = 1.0
                    while self._running and time.time() < deadline:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        try:
                            self._apply_agg_frame(json.loads(raw))
                        except Exception:
                            continue
            except Exception:
                self._agg_connected = False
                self._reconnects += 1
                await asyncio.sleep(min(backoff, 30.0))
                backoff *= 2
        self._agg_connected = False

    def start(self) -> "BinanceUniverseMirror":
        if not enabled() or self._running:
            return self
        self._running = True
        self._started_ts = time.time()
        self._backfill_rest()                    # immediate data so the first read isn't empty
        self._thread = threading.Thread(target=self._run, daemon=True, name="binance-mirror")
        self._thread.start()
        if depth_enabled():                      # separate connection: 20-level depth + aggTrade
            self._depth_thread = threading.Thread(target=self._run_depth, daemon=True,
                                                  name="binance-mirror-depth")
            self._depth_thread.start()
        if depth_enabled():                      # taker flow: own /market/ connection (aggTrade)
            self._agg_thread = threading.Thread(target=self._run_agg, daemon=True,
                                                name="binance-mirror-agg")
            self._agg_thread.start()
        if stats_enabled():                      # the only kinds with no WS stream: OI + long/short
            self._stats_thread = threading.Thread(target=self._run_stats, daemon=True,
                                                  name="binance-mirror-stats")
            self._stats_thread.start()
        return self

    def stop(self) -> None:
        self._running = False

    def _backfill_rest(self) -> None:
        """One-shot REST snapshot on (re)start so reads work before the first push arrives. Best-effort."""
        try:
            import urllib.request
            now = time.time()
            with urllib.request.urlopen("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=8) as r:
                rows = json.loads(r.read().decode())
            with self._lock:
                for d in rows:
                    s = d.get("symbol")
                    if not s:
                        continue
                    self._ticker[s] = {
                        "last": _f(d.get("lastPrice")), "pct_change": _f(d.get("priceChangePercent")),
                        "high": _f(d.get("highPrice")), "low": _f(d.get("lowPrice")),
                        "quote_volume": _f(d.get("quoteVolume")), "count": _i(d.get("count")),
                        "ts": now,
                    }
        except Exception:
            pass                                 # cold backfill is fine — the stream fills in shortly

    # ── read API (RAM; the brain never blocks on network here) ───────────────
    def funding(self, symbol: str) -> dict | None:
        with self._lock:
            v = self._mark.get(symbol.upper())
            return dict(v) if v else None

    def mark(self, symbol: str) -> dict | None:
        return self.funding(symbol)

    def price_at(self, symbol: str, epoch: float, *, tol_s: float = 240.0) -> float | None:
        """The mark price closest to `epoch` from the rolling history (within tol_s), for
        100% truth-ledger resolution of ANY perp. None when out of coverage/history."""
        s = symbol.upper()
        with self._lock:
            h = self._hist.get(s)
            if not h:
                v = self._mark.get(s)                 # no history yet → latest, if close enough
                return v.get("mark") if v and abs(v.get("ts", 0) - epoch) <= tol_s else None
            best, bestd = None, tol_s
            for ts, mk in h:
                d = abs(ts - epoch)
                if d <= bestd:
                    best, bestd = mk, d
            return best

    def ticker(self, symbol: str) -> dict | None:
        with self._lock:
            v = self._ticker.get(symbol.upper())
            return dict(v) if v else None

    def book(self, symbol: str, *, max_age_s: float = 5.0) -> dict | None:
        """Fresh 20-level order book {bids, asks, ts} from the depth stream, or None if not
        watched / stale (caller then falls back to REST). Symbol may carry a :USDT settle suffix."""
        s = symbol.split(":")[0].replace("/", "").upper()
        with self._lock:
            v = self._book.get(s)
            if v and (time.time() - v["ts"]) <= max_age_s:
                return {"bids": [list(x) for x in v["bids"]],
                        "asks": [list(x) for x in v["asks"]], "ts": v["ts"]}
        return None

    def movers(self, n: int = 30, *, by: str = "quote_volume", min_quote_volume: float = 0.0) -> list[dict]:
        """Tier-0 universe narrowing on Binance's OWN numbers — the shortlist the brain deep-dives.

        `by`: 'quote_volume' (liquidity) | 'pct_change' (gainers) | 'abs_change' (movers) | 'count'.
        Pure RAM sort over the whole universe Binance pushed us — no local scan of 400 symbols."""
        with self._lock:
            rows = [{"symbol": s, **v} for s, v in self._ticker.items()
                    if (v.get("quote_volume") or 0.0) >= min_quote_volume]
        keyf = {
            "quote_volume": lambda r: r.get("quote_volume") or 0.0,
            "pct_change": lambda r: r.get("pct_change") or 0.0,
            "abs_change": lambda r: abs(r.get("pct_change") or 0.0),
            "count": lambda r: r.get("count") or 0,
        }.get(by, lambda r: r.get("quote_volume") or 0.0)
        rows.sort(key=keyf, reverse=True)
        return rows[: max(0, int(n))]

    def futures_rows(self, *, min_quote_volume: float = 0.0) -> list[dict]:
        """USDⓈ-M perp rows in the screener's shape, from RAM — the Tier-0 universe scan on
        Binance's OWN pushed numbers (replaces a per-cycle ccxt fetch_tickers of ~400 symbols).

        Each row: {symbol (ccxt 'BASE/USDT:USDT'), raw, pct_change, quote_volume, funding_rate}.
        Only USDT-quoted perps (the vast majority); anything mis-converted is harmlessly rejected
        downstream by the executor's tradeability guard. Empty when the mirror is cold → caller
        falls back to ccxt."""
        out: list[dict] = []
        with self._lock:
            tick = dict(self._ticker)
            mark = dict(self._mark)
        for s, t in tick.items():
            if not s.endswith("USDT"):
                continue                          # skip USDC/BUSD perps for now (minor share)
            qv = t.get("quote_volume") or 0.0
            if qv < min_quote_volume:
                continue
            base = s[:-4]
            out.append({
                "symbol": f"{base}/USDT:USDT", "raw": s,
                "pct_change": t.get("pct_change"), "quote_volume": qv,
                "funding_rate": (mark.get(s) or {}).get("funding_rate"),
            })
        return out

    def _roll_candles(self, s: str, price: float, now: float) -> None:
        """Fold one live mark into every timeframe's current OHLC bar. Called under _lock
        from the markPrice loop; O(len(_CANDLE_TFS)) per tick — cheap. Never raises."""
        cs = self._candles.get(s)
        if cs is None:
            cs = self._candles[s] = {tf: deque(maxlen=_CANDLE_MAXLEN) for tf in _CANDLE_TFS}
        for tf in _CANDLE_TFS:
            dq = cs[tf]
            bar_ts = int(now // tf) * tf
            if dq and dq[-1][0] == bar_ts:            # same bucket → update H/L/C
                bar = dq[-1]
                if price > bar[2]:
                    bar[2] = price
                if price < bar[3]:
                    bar[3] = price
                bar[4] = price
            else:                                     # new bucket → open a bar [ts,o,h,l,c]
                dq.append([bar_ts, price, price, price, price])

    def candle_timeframes(self) -> tuple:
        """The timeframes (seconds) currently aggregated in RAM for every symbol."""
        return _CANDLE_TFS

    def candles(self, symbol: str, tf: int = 60, n: int = 100) -> list[list]:
        """In-RAM OHLC bars for ANY perp, aggregated live from the all-market markPrice
        stream — no API/kline request. `tf` seconds (must be one of candle_timeframes()).
        Returns [[bar_ts, open, high, low, close], …] newest last, or [] if unavailable."""
        try:
            tf = int(tf)
            with self._lock:
                cs = self._candles.get(symbol.upper())
                if not cs or tf not in cs:
                    return []
                return [list(b) for b in list(cs[tf])[-int(n):]]
        except Exception:
            return []

    def recent_liquidations(self, symbol: str | None = None, n: int = 50) -> list[dict]:
        with self._lock:
            liqs = list(self._liqs)
        if symbol:
            su = symbol.upper()
            liqs = [x for x in liqs if x.get("symbol") == su]
        return liqs[-int(n):][::-1]              # newest first

    def is_stale(self, symbol: str) -> bool:
        v = self.funding(symbol) or self.ticker(symbol)
        return (not v) or (time.time() - (v.get("ts") or 0.0) > _STALE_AFTER_S)

    def snapshot_dict(self) -> dict:
        """A compact dashboard-ready view of the whole edge (pure RAM). Written to a state file by
        the funnel process so the dashboard route can read it WITHOUT opening a socket (hard rule)."""
        with self._lock:
            marks = [{"symbol": s, "funding_rate": v.get("funding_rate"), "mark": v.get("mark"),
                      "next_funding_ts": v.get("next_funding_ts")}
                     for s, v in self._mark.items() if v.get("funding_rate") is not None]
        funding_hi = sorted(marks, key=lambda m: -(m.get("funding_rate") or 0))[:8]
        funding_lo = sorted(marks, key=lambda m: (m.get("funding_rate") or 0))[:8]
        return {
            "status": self.status(),
            "top_volume": self.movers(15, by="quote_volume"),
            "top_gainers": self.movers(10, by="pct_change"),
            "funding_high": funding_hi, "funding_low": funding_lo,
            "liquidations": self.recent_liquidations(n=25),
            "ts": time.time(),
        }

    def write_snapshot(self) -> None:
        """Dump snapshot_dict (+ catalysts) to the state file. Best-effort; never raises."""
        d = self.snapshot_dict()
        try:
            from trading.broker_sense import binance_catalysts as bc
            if bc.enabled():
                d["new_listings"] = bc.new_listings()[:10]
                d["announcements"] = [{"title": a.get("title"), "symbols": a.get("symbols")}
                                      for a in bc.announcements(n=8)][:8]
        except Exception:
            pass
        try:
            from trading.broker_sense import binance_sectors as _sec
            if _sec.enabled():
                rot = _sec.sector_rotation()
                d["sectors_hot"] = rot[:6]
                d["sectors_cold"] = rot[-4:] if len(rot) > 6 else []
        except Exception:
            pass
        try:
            from trading.broker_sense import binance_options as _opt
            if _opt.enabled():
                d["options_regime"] = _opt.regime()
        except Exception:
            pass
        try:
            from trading.broker_sense import binance_ai_select as _ai
            if _ai.enabled():
                d["ai_select"] = _ai.picks()[:8]
        except Exception:
            pass
        try:
            p = state._path("binance_edge") / "snapshot.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(d, default=str))
            tmp.replace(p)
        except Exception:
            pass

    def status(self) -> dict:
        with self._lock:
            n_mark, n_tick, n_liq, n_book = (len(self._mark), len(self._ticker),
                                             len(self._liqs), len(self._book))
        age = time.time() - self._last_msg_ts if self._last_msg_ts else None
        dage = time.time() - self._depth_last_msg_ts if self._depth_last_msg_ts else None
        return {
            "enabled": enabled(), "running": self._running, "connected": self._connected,
            "reconnects": self._reconnects, "symbols_mark": n_mark, "symbols_ticker": n_tick,
            "liquidations_buffered": n_liq,
            "depth_enabled": depth_enabled(), "depth_connected": self._depth_connected,
            "symbols_book": n_book, "depth_watch": len(self._depth_watch),
            "depth_age_s": round(dage, 1) if dage is not None else None,
            "last_msg_age_s": round(age, 1) if age is not None else None,
            "stale": age is None or age > _STALE_AFTER_S,
            "uptime_s": round(time.time() - self._started_ts, 1) if self._started_ts else 0.0,
        }


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


_MIRROR: BinanceUniverseMirror | None = None
_MIRROR_LOCK = threading.Lock()


def get_mirror() -> BinanceUniverseMirror:
    """Process-wide singleton. Call .start() to begin streaming (idempotent)."""
    global _MIRROR
    with _MIRROR_LOCK:
        if _MIRROR is None:
            _MIRROR = BinanceUniverseMirror()
    return _MIRROR


# timeframe string → seconds (superset; the mirror only serves those in candle_timeframes()).
_TF_SECONDS: dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200, "1d": 86400,
}


def ohlcv(symbol: str, timeframe: str = "5m", limit: int = 220) -> list | None:
    """RAM-first candles for a perp, straight off the all-market WS mirror, in ccxt OHLCV shape
    ([ms, o, h, l, c, v]) — the motto-pure candle source: NO API/kline request, data is aggregated
    live from the `!markPrice@arr` stream already in RAM. This is the consumer-side completion of
    the 2026-07-13 in-RAM multi-TF candle build (the mirror aggregated them; nothing read them yet).

    Mark-price OHLC, volume 0 (the mirror has no volume). Returns None — so the caller falls back to
    its next source — when the mirror lacks the timeframe (only candle_timeframes() are aggregated,
    default 1m/5m/15m), lacks the symbol, or hasn't warmed enough bars (<30). Crypto perps only.
    MIRROR_CANDLES=0 disables. Never raises."""
    if os.environ.get("MIRROR_CANDLES", "1") not in ("1", "true", "TRUE", "yes", "on"):
        return None
    secs = _TF_SECONDS.get(str(timeframe))
    if secs is None:
        return None
    try:
        m = get_mirror()
        if secs not in m.candle_timeframes():
            return None
        flat = str(symbol).split(":")[0].replace("/", "").upper()
        bars = m.candles(flat, secs, int(limit))
        if not bars or len(bars) < 30:
            return None
        return [[int(b[0]) * 1000, float(b[1]), float(b[2]), float(b[3]), float(b[4]), 0.0]
                for b in bars]
    except Exception:
        return None
