"""trading/broker_sense/kite_stream.py — Zerodha (Kite) NSE in-RAM mirror, FED VIA OPENALGO's WS.

Owner mandate (2026-07-14): NSE trade SELECTION must read ALL its market data — multi-TF candles,
LTP/ticker, order depth, volume, OI — from an ALWAYS-ON in-RAM store, the SAME WAY crypto does
(binance_stream.py), instead of a per-cycle REST call. The data is the owner's PAID Zerodha feed;
the "combine Kite Connect with OpenAlgo" decision (owner 2026-07-14) is realised by NOT running a
second Zerodha login: **OpenAlgo already fronts Zerodha** — it runs the KiteTicker connection
internally, manages the broker's DAILY access_token server-side, maps symbols→tokens, and
re-publishes normalized ticks on its unified market-data WebSocket (:8765) keyed by our OpenAlgo
API key. So we drop `kiteconnect` entirely and subscribe to OpenAlgo's WS via the installed
`openalgo` SDK FeedAPI, folding each `msg["data"]` tick into RAM. The funnel then reads the whole
universe from RAM in microseconds — no network at decision time, ~0 idle CPU (push, not poll).

DATA ONLY. Order PLACEMENT is unchanged (still the OpenAlgo/broker order API, exec_adapter.py).

ONE subscription per symbol, in DEPTH mode (3): that puts KiteTicker in FULL mode, whose tick
carries ltp+ohlc+volume+oi+vwap+5-level book together. The SDK's own callbacks are NOT used — they
rebuild a trimmed dict per mode and drop volume/OHLC from depth frames — so _raw_feed_class()
overrides _process_message to read the server's envelope untouched (see its docstring).

Config (no Kite token ever — OpenAlgo owns the daily broker login): OPENALGO_API_KEY (already set)
+ OPENALGO_HOST (default http://127.0.0.1:5000; WS port 8765). Kill switch KITE_STREAM=0; feed mode
KITE_STREAM_MODE=ltp|quote downgrades the subscription (debug only; default depth). Degrades
to nothing (callers keep their OpenAlgo REST fallback) when the openalgo SDK/key is missing or
OpenAlgo isn't logged into the broker for the day — every read returns None/[] rather than raising.

Read API (all pure RAM reads, mirror of binance_stream):
    m = get_kite_mirror(); m.subscribe_symbols([...]); m.start()
    m.ticker("RELIANCE"); m.book("RELIANCE"); m.candles("RELIANCE", 300, 100)
    m.nse_rows(); m.price_at("RELIANCE", epoch); m.status()
    # module-level: ohlcv(sym, "5m", 220) / ticker(sym) / book(sym) / nse_rows()
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque

from trading import state


def _raw_feed_class(base):
    """The openalgo SDK's FeedAPI, subclassed so _process_message hands us the RAW envelope.

    WHY (live-verified 2026-07-16, NSE open): the SDK does not pass the server's tick through — it
    rebuilds a NEW dict per subscription type before invoking the callback. feed.py's mode-3 branch
    keeps only {ltp, timestamp, depth} and DROPS volume/OHLC/OI; its mode-2 branch drops the book.
    We need both, and no combination of subscribe_quote+subscribe_depth can deliver them: OpenAlgo's
    zerodha adapter keys subscriptions by "exchange:symbol" (no mode), so the second call REPLACES
    the first, and the proxy tags each client with a single mode. The server already puts everything
    in the mode-3 "full" frame — only the client trimmed it. Overriding this one method keeps the
    SDK's connect/auth/reconnect/subscription-replay machinery intact.
    """
    class _RawFeed(base):
        _sink = None                      # set to a callable(msg) before connect()

        def _process_message(self, message_str):
            try:
                msg = json.loads(message_str)
            except Exception:
                return super()._process_message(message_str)
            if isinstance(msg, dict) and msg.get("type") == "market_data":
                if self._sink is not None:
                    self._sink(msg)       # untrimmed: ltp+ohlc+volume+oi+vwap+depth
                return
            return super()._process_message(message_str)   # auth/subscribe acks, reconnect state

    return _RawFeed

# Live multi-TF OHLC candles rolled from the OpenAlgo ltp stream (the feed pushes the DAY's ohlc in
# a tick, not intraday bars — so we aggregate them ourselves, exactly like the crypto mirror rolls
# candles off markPrice). Volume per bar = delta of the tick's cumulative day volume.
# 1h/1d included (2026-07-16): the funnel's LOOK asks for 1m/5m/15m/1h/4h/1d, so a mirror that rolled
# only 1m/5m/15m left the slow TFs permanently "unavailable" — funnel._vote then judged direction on
# fast TFs alone. 1h+1d are ~free to seed (95 rows/0.07s, 80 rows/0.36s) and roll from the same ticks.
# (4h is deliberately absent: Zerodha's history API has no 4h interval, so it could never be seeded.)
_CANDLE_TFS = tuple(int(x) for x in
                    (os.getenv("KITE_CANDLE_TFS", "60,300,900,3600,86400")).split(",") if x)
_CANDLE_MAXLEN = int(os.getenv("KITE_CANDLE_MAXLEN", "240") or 240)   # bars kept per (sym, tf)
_HIST_EVERY_S = 15.0            # sample per-symbol price history at most this often
_HIST_MAXLEN = 320             # ~80 min of ltp history per symbol (price_at horizon resolution)
_STALE_AFTER_S = 20.0          # a push field older than this is flagged stale (NSE ticks ~sub-second)
_STATUS_FILE = "kite_stream.json"

# STARTUP BACKFILL (2026-07-16): seed candles from OpenAlgo's history API on start so the funnel can
# decide immediately instead of waiting 15/75/225 min for the stream to roll 15 bars per TF. One-shot
# only — the decision path never touches REST. KITE_BACKFILL=0 disables (stream-only).
_BACKFILL_ON = os.getenv("KITE_BACKFILL", "1").strip().lower() not in ("0", "false", "off")
_BACKFILL_SLEEP_S = float(os.getenv("KITE_BACKFILL_SLEEP_S", "0.12") or 0.12)   # ~8/s < OpenAlgo's 10/s
_TF_TO_OA = {60: "1m", 300: "5m", 900: "15m", 1800: "30m", 3600: "1h", 86400: "D"}
# Lookback PER TIMEFRAME, sized to fill _CANDLE_MAXLEN (240) bars — never more. A flat 6-day window
# pulled 1726 1m-rows per symbol (2.04s each → ~7min of the backfill) only to discard all but 240,
# while leaving 1d with 5 bars — below ohlcv()'s 15-bar floor, so 1d stayed unavailable anyway.
# Each window covers 240 bars of TRADING time plus slack for weekends/holidays.
_BACKFILL_DAYS_BY_TF = {60: 2, 300: 5, 900: 10, 1800: 20, 3600: 30, 86400: 365}
_BACKFILL_DAYS = int(os.getenv("KITE_BACKFILL_DAYS", "0") or 0)   # >0 forces one window for every TF


def enabled() -> bool:
    return os.getenv("KITE_STREAM", "1").strip().lower() not in ("0", "false", "off")


def _openalgo_cfg() -> tuple[str, str] | None:
    """(api_key, host) for OpenAlgo, or None when the key is unset (mirror stays a no-op).
    OpenAlgo — not us — holds the Zerodha broker credentials + daily token; we only need our
    own OpenAlgo API key to consume its unified feed."""
    key = (os.getenv("OPENALGO_API_KEY") or "").strip()
    if not key:
        return None
    host = (os.getenv("OPENALGO_HOST") or "http://127.0.0.1:5000").strip()
    return (key, host)


def _flat(symbol: str) -> str:
    """Normalize a symbol to the OpenAlgo tradingsymbol key: strip an NSE:/NFO: exchange prefix and
    any :… suffix, uppercase. 'NSE:RELIANCE' / 'RELIANCE' -> 'RELIANCE'."""
    s = str(symbol or "").upper().strip()
    if ":" in s:
        s = s.split(":")[-1]
    return s


class KiteZerodhaMirror:
    """Live in-RAM snapshot of the NSE F&O universe, fed by OpenAlgo's unified market-data WS
    (which itself streams the owner's Zerodha KiteTicker session)."""

    def __init__(self):
        self._ltp: dict[str, dict] = {}          # sym -> {last, pct_change, high, low, open, close, volume, oi, ts}
        self._candles: dict[str, dict] = {}      # sym -> {tf_s -> deque[[bar_ts,o,h,l,c,v,vol_base]]}
        self._book: dict[str, dict] = {}         # sym -> {bids:[[p,q]], asks:[[p,q]], ts}
        self._hist: dict[str, deque] = {}        # sym -> deque[(ts, ltp)]
        self._hist_last: dict[str, float] = {}
        self._want: set[str] = set()             # tradingsymbols we intend to stream (NSE)
        self._subscribed: set[str] = set()       # symbols already subscribed on the feed
        self._lock = threading.RLock()
        self._client = None                      # the openalgo.api FeedAPI client
        self._running = False
        self._connected = False
        self._last_msg_ts = 0.0
        self._last_snap = 0.0
        self._started_ts = 0.0
        self._backfilled = False                 # True once the one-shot history seed has run

    # ── universe selection ───────────────────────────────────────────────────
    def subscribe_symbols(self, symbols) -> None:
        """Set/extend the NSE tradingsymbols to stream. If already connected, subscribes the new
        ones live. Idempotent; never raises."""
        try:
            syms = {_flat(s) for s in (symbols or []) if s}
            if not syms:
                return
            with self._lock:
                self._want |= syms
            if self._connected and self._client is not None:
                self._subscribe_wanted()
        except Exception:
            pass

    def _subscribe_wanted(self) -> None:
        """Subscribe any wanted-but-unsubscribed symbols in DEPTH mode (3) — the FULL superset.

        Mode 3 makes OpenAlgo put Zerodha's KiteTicker in FULL mode, whose tick carries
        ltp+ohlc+volume+oi+vwap+5-level book TOGETHER; _RawFeed reads it untrimmed. Do NOT also
        subscribe_quote for the same symbol: the adapter keys subscriptions by "exchange:symbol", so
        a second mode silently REPLACES the first — the earlier "both" default did exactly that and
        froze volume at its subscribe-time snapshot (candle volume stuck at 0.0, live-caught
        2026-07-16). KITE_STREAM_MODE=ltp|quote forces a lesser mode for debugging only. Bounded by
        Zerodha's 3000/connection cap. Never raises."""
        try:
            with self._lock:
                pending = [s for s in self._want if s not in self._subscribed][:3000]
            if not pending or self._client is None:
                return
            instruments = [{"symbol": s, "exchange": "NSE"} for s in pending]
            mode = (os.getenv("KITE_STREAM_MODE", "depth") or "depth").lower()
            fn = {"ltp": self._client.subscribe_ltp,
                  "quote": self._client.subscribe_quote}.get(mode, self._client.subscribe_depth)
            fn(instruments)      # frames arrive via _RawFeed._process_message → _on_tick
            with self._lock:
                self._subscribed |= set(pending)
        except Exception as e:
            print(f"[nse-mirror] subscribe failed: {e!r}", flush=True)

    # ── tick handling (PURE — unit-testable without a socket) ────────────────
    def _on_tick(self, msg) -> None:
        """OpenAlgo feed callback. Envelope = {"type":"market_data","symbol","exchange","mode",
        "data":{...}}; control frames (auth/subscribe acks) carry a different `type` and are
        ignored. Never raises."""
        try:
            if not isinstance(msg, dict):
                return
            if msg.get("type") not in ("market_data", None):
                return                                    # auth/subscribe/heartbeat ack — not a tick
            data = msg.get("data")
            sym = msg.get("symbol")
            if sym and isinstance(data, dict):
                self._apply_one(_flat(sym), data)
        except Exception:
            pass

    def _apply_one(self, sym: str, data: dict) -> None:
        """Fold one OpenAlgo tick `data` dict into the in-RAM snapshot (merging with the last known
        record so a partial-mode frame never wipes a field). Called from the feed thread. Never raises."""
        now = time.time()
        self._last_msg_ts = now
        with self._lock:
            prev = self._ltp.get(sym, {})
            ltp = _f(data.get("ltp"))
            if ltp is None:
                ltp = prev.get("last")
            close = _f(data.get("close"))
            if close is None:
                close = prev.get("close")
            cum_vol = _f(data.get("volume"))
            if cum_vol is None:
                cum_vol = prev.get("volume") or 0.0
            oi = _f(data.get("oi"))
            if oi is None:
                oi = _f(data.get("open_interest"))
            if oi is None:
                oi = prev.get("oi")
            pct = (round((ltp - close) / close * 100.0, 4) if (ltp and close) else
                   _f(data.get("price_change_percent")) or prev.get("pct_change"))
            rec = {
                "last": ltp, "pct_change": pct,
                "high": _f(data.get("high")) if data.get("high") is not None else prev.get("high"),
                "low": _f(data.get("low")) if data.get("low") is not None else prev.get("low"),
                "open": _f(data.get("open")) if data.get("open") is not None else prev.get("open"),
                "close": close, "volume": cum_vol, "oi": oi, "ts": now,
                # Zerodha FULL-frame extras (free with mode 3): day VWAP + the exchange's total
                # resting buy/sell quantity — a real order-book imbalance input for psychology.
                "vwap": _f(data.get("average_price")) if data.get("average_price") is not None
                        else prev.get("vwap"),
                "buy_qty": _f(data.get("total_buy_quantity")) if data.get("total_buy_quantity") is not None
                           else prev.get("buy_qty"),
                "sell_qty": _f(data.get("total_sell_quantity")) if data.get("total_sell_quantity") is not None
                            else prev.get("sell_qty"),
            }
            self._ltp[sym] = rec
            if ltp is not None:
                if now - self._hist_last.get(sym, 0.0) >= _HIST_EVERY_S:
                    h = self._hist.get(sym)
                    if h is None:
                        h = self._hist[sym] = deque(maxlen=_HIST_MAXLEN)
                    h.append((now, ltp))
                    self._hist_last[sym] = now
                self._roll_candles(sym, ltp, cum_vol or 0.0, now)
            depth = data.get("depth")
            if isinstance(depth, dict):
                bids = [[_f(q.get("price")), _f(q.get("quantity"))]
                        for q in (depth.get("buy") or []) if _f(q.get("price"))]
                asks = [[_f(q.get("price")), _f(q.get("quantity"))]
                        for q in (depth.get("sell") or []) if _f(q.get("price"))]
                if bids or asks:
                    self._book[sym] = {"bids": bids, "asks": asks, "ts": now}
        if now - self._last_snap >= 10.0:
            self._last_snap = now
            self.write_snapshot()

    def _roll_candles(self, s: str, price: float, cum_vol: float, now: float) -> None:
        """Fold one live tick into every timeframe's current OHLC bar (bar = [ts,o,h,l,c,v,vol_base],
        v = cumulative-volume delta within the bar). Called under _lock; O(len(_CANDLE_TFS)). Never raises."""
        cs = self._candles.get(s)
        if cs is None:
            cs = self._candles[s] = {tf: deque(maxlen=_CANDLE_MAXLEN) for tf in _CANDLE_TFS}
        for tf in _CANDLE_TFS:
            dq = cs[tf]
            bar_ts = int(now // tf) * tf
            if dq and dq[-1][0] == bar_ts:            # same bucket → update H/L/C/V
                bar = dq[-1]
                if price > bar[2]:
                    bar[2] = price
                if price < bar[3]:
                    bar[3] = price
                bar[4] = price
                bar[5] = max(0.0, cum_vol - bar[6]) if cum_vol else bar[5]
            else:                                     # new bucket → open a bar
                dq.append([bar_ts, price, price, price, price, 0.0, cum_vol])

    # ── OpenAlgo feed wiring ─────────────────────────────────────────────────
    def start(self) -> "KiteZerodhaMirror":
        """Begin streaming from OpenAlgo's WS (idempotent). No-op when disabled, already running,
        the openalgo SDK is missing, or OPENALGO_API_KEY is unset — in every such case the read API
        just returns empty and callers keep their OpenAlgo REST fallback."""
        if not enabled() or self._running:
            return self
        cfg = _openalgo_cfg()
        if not cfg:
            print("[nse-mirror] no OPENALGO_API_KEY — mirror idle (OpenAlgo REST fallback)", flush=True)
            return self
        try:
            from openalgo import api as _OAApi
        except Exception:
            print("[nse-mirror] openalgo SDK missing — mirror idle (OpenAlgo REST fallback)", flush=True)
            return self
        api_key, host = cfg
        self._running = True
        self._started_ts = time.time()
        try:
            client = _raw_feed_class(_OAApi)(api_key=api_key, host=host)  # ws_port 8765, auto_reconnect
            client._sink = self._on_tick                   # set BEFORE connect so no frame is missed
            ok = client.connect()                          # opens WS + authenticates with our OpenAlgo key
            self._client = client
            self._connected = bool(ok)
            self._subscribe_wanted()
            print(f"[nse-mirror] OpenAlgo WS connect={ok} · {len(self._subscribed)}/{len(self._want)} "
                  f"symbols subscribed (Zerodha via OpenAlgo, no kiteconnect)", flush=True)
            # Seed history OFF-THREAD: ~600 rate-limited REST calls must never block the caller
            # (run_funnel_loop starts the mirror inline before its first cycle), and the stream
            # keeps folding live ticks into the same store while this runs.
            if _BACKFILL_ON and not self._backfilled:
                threading.Thread(target=self._backfill_history, name="nse-mirror-backfill",
                                 daemon=True).start()
        except Exception as e:
            self._running = False
            self._connected = False
            print(f"[nse-mirror] start failed: {e!r} — OpenAlgo REST fallback", flush=True)
        return self

    def _backfill_history(self) -> int:
        """One-shot REST seed of the candle store from OpenAlgo's history API (the NSE analog of
        binance_stream._backfill_rest), so reads WORK before the stream has rolled enough bars.

        Without this the mirror starts empty and must roll every bar from live ticks, and ohlcv()
        only serves a timeframe once it holds >=15 bars — 15min for 1m, 75min for 5m, 225min for
        15m (past NSE close on a mid-session restart). funnel._vote needs >=2 AGREEING timeframes,
        so NSE voted neutral on every symbol and opened nothing (live-diagnosed 2026-07-16:
        look.read=40, cands=[], non_neutral=0). This is a STARTUP seed, not a per-cycle read — the
        decision path stays pure RAM.

        Best-effort and never raises: any symbol/timeframe that fails just stays stream-only.
        Returns the number of (symbol, tf) series seeded. Rate-limited: OpenAlgo answers 429 above
        ~10 req/s. Only seeds bars STRICTLY OLDER than the live bar so ticks are never clobbered.
        """
        import datetime

        cfg = _openalgo_cfg()
        if not cfg or not _BACKFILL_ON:
            return 0
        try:
            from trading.openalgo_client import OpenAlgoClient
            oa = OpenAlgoClient()
        except Exception as e:
            print(f"[nse-mirror] backfill skipped (no OpenAlgo client): {e!r}", flush=True)
            return 0
        with self._lock:
            symbols = sorted(self._want)
        today = datetime.date.today()
        end = today.isoformat()
        # per-TF window: enough to fill _CANDLE_MAXLEN, never the whole history (see the map)
        starts = {tf: (today - datetime.timedelta(
            days=_BACKFILL_DAYS or _BACKFILL_DAYS_BY_TF.get(tf, 6))).isoformat()
            for tf in _CANDLE_TFS}
        seeded = 0
        for sym in symbols:
            if not self._running:
                return seeded
            for tf in _CANDLE_TFS:
                iv = _TF_TO_OA.get(tf)
                if not iv:
                    continue
                try:
                    resp = oa.history(sym, exchange="NSE", interval=iv,
                                      start_date=starts[tf], end_date=end)
                    rows = (resp or {}).get("data") or []
                    bars = []
                    for r in rows[-_CANDLE_MAXLEN:]:
                        ts = _epoch(r.get("timestamp"))
                        c = _f(r.get("close"))
                        if ts is None or c is None:
                            continue
                        # [ts,o,h,l,c,v,vol_base]; vol_base=0 → the live roll treats this bar's
                        # volume as final rather than differencing it against a day-cumulative.
                        bars.append([int(ts // tf) * tf, _f(r.get("open")) or c,
                                     _f(r.get("high")) or c, _f(r.get("low")) or c, c,
                                     _f(r.get("volume")) or 0.0, 0.0])
                    if not bars:
                        continue
                    with self._lock:
                        cs = self._candles.setdefault(
                            sym, {t: deque(maxlen=_CANDLE_MAXLEN) for t in _CANDLE_TFS})
                        dq = cs[tf]
                        live_ts = dq[-1][0] if dq else None
                        keep = [b for b in bars if live_ts is None or b[0] < live_ts]
                        if keep:
                            merged = keep + ([dq[-1]] if live_ts is not None else [])
                            cs[tf] = deque(merged[-_CANDLE_MAXLEN:], maxlen=_CANDLE_MAXLEN)
                            seeded += 1
                except Exception:
                    pass
                time.sleep(_BACKFILL_SLEEP_S)      # stay under OpenAlgo's ~10/s ceiling
        self._backfilled = True
        print(f"[nse-mirror] backfill seeded {seeded} series "
              f"({len(symbols)} symbols × {len(_CANDLE_TFS)} TFs) from OpenAlgo history", flush=True)
        self.write_snapshot()
        return seeded

    def stop(self) -> None:
        self._running = False
        try:
            if self._client is not None:
                self._client.disconnect()
        except Exception:
            pass

    # ── read API (RAM; the brain never blocks on network here) ───────────────
    def ticker(self, symbol: str) -> dict | None:
        with self._lock:
            v = self._ltp.get(_flat(symbol))
            return dict(v) if v else None

    def book(self, symbol: str, *, max_age_s: float = 5.0) -> dict | None:
        with self._lock:
            v = self._book.get(_flat(symbol))
            if v and (time.time() - v["ts"]) <= max_age_s:
                return {"bids": [list(x) for x in v["bids"]],
                        "asks": [list(x) for x in v["asks"]], "ts": v["ts"]}
        return None

    def price_at(self, symbol: str, epoch: float, *, tol_s: float = 240.0) -> float | None:
        s = _flat(symbol)
        with self._lock:
            h = self._hist.get(s)
            if not h:
                v = self._ltp.get(s)
                return v.get("last") if v and abs(v.get("ts", 0) - epoch) <= tol_s else None
            best, bestd = None, tol_s
            for ts, px in h:
                d = abs(ts - epoch)
                if d <= bestd:
                    best, bestd = px, d
            return best

    def candle_timeframes(self) -> tuple:
        return _CANDLE_TFS

    def candles(self, symbol: str, tf: int = 300, n: int = 100) -> list[list]:
        """In-RAM OHLCV bars [[bar_ts,o,h,l,c,v], …] newest last, rolled live from the tick stream.
        `tf` seconds (must be one of candle_timeframes()). [] when unavailable."""
        try:
            tf = int(tf)
            with self._lock:
                cs = self._candles.get(_flat(symbol))
                if not cs or tf not in cs:
                    return []
                return [[b[0], b[1], b[2], b[3], b[4], b[5]] for b in list(cs[tf])[-int(n):]]
        except Exception:
            return []

    def nse_rows(self, *, min_volume: float = 0.0) -> list[dict]:
        """The subscribed NSE universe in the screener's shape, from RAM (replaces a per-cycle
        OpenAlgo quotes() call). Each row: {symbol, ltp, pct_change, prev_close, volume, high, low}.
        Empty when the mirror is cold → caller falls back to OpenAlgo."""
        out: list[dict] = []
        with self._lock:
            snap = dict(self._ltp)
        for s, v in snap.items():
            vol = v.get("volume") or 0.0
            if vol < min_volume:
                continue
            out.append({"symbol": s, "ltp": v.get("last"), "pct_change": v.get("pct_change"),
                        "prev_close": v.get("close"), "volume": vol,
                        "high": v.get("high"), "low": v.get("low")})
        return out

    def is_stale(self, symbol: str) -> bool:
        v = self.ticker(symbol)
        return (not v) or (time.time() - (v.get("ts") or 0.0) > _STALE_AFTER_S)

    def status(self) -> dict:
        with self._lock:
            n_ltp, n_book = len(self._ltp), len(self._book)
            n_want, n_sub = len(self._want), len(self._subscribed)
            n_cdl = len(self._candles)     # the backfill thread mutates this concurrently
        age = time.time() - self._last_msg_ts if self._last_msg_ts else None
        return {
            "enabled": enabled(), "running": self._running, "connected": self._connected,
            "have_creds": _openalgo_cfg() is not None, "feed": "openalgo-ws",
            "symbols_ticker": n_ltp, "symbols_book": n_book,
            "symbols_wanted": n_want, "symbols_subscribed": n_sub,
            "candle_tfs": list(_CANDLE_TFS), "backfilled": self._backfilled,
            "symbols_candles": n_cdl,
            "last_msg_age_s": round(age, 1) if age is not None else None,
            "stale": age is None or age > _STALE_AFTER_S,
            "uptime_s": round(time.time() - self._started_ts, 1) if self._started_ts else 0.0,
        }

    def snapshot_dict(self) -> dict:
        rows = self.nse_rows()
        by_vol = sorted(rows, key=lambda r: -(r.get("volume") or 0.0))[:15]
        by_gain = sorted(rows, key=lambda r: -(r.get("pct_change") or 0.0))[:10]
        return {"status": self.status(), "top_volume": by_vol, "top_gainers": by_gain,
                "ts": time.time()}

    def write_snapshot(self) -> None:
        try:
            state.update_json(_STATUS_FILE, self.snapshot_dict())
        except Exception:
            pass


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _epoch(v) -> float | None:
    """Epoch seconds from an OpenAlgo history timestamp — pandas Timestamp (tz-aware), datetime,
    ISO string, or a raw epoch (s/ms). Returns None when it can't be read. Never raises."""
    if v is None:
        return None
    ts = getattr(v, "timestamp", None)          # pandas Timestamp / datetime
    if callable(ts):
        try:
            return float(ts())
        except Exception:
            return None
    n = _f(v)
    if n is not None:
        return n / 1000.0 if n > 1e11 else n    # ms → s
    try:
        import datetime
        return datetime.datetime.fromisoformat(str(v)).timestamp()
    except Exception:
        return None


_MIRROR: KiteZerodhaMirror | None = None
_MIRROR_LOCK = threading.Lock()


def get_kite_mirror() -> KiteZerodhaMirror:
    """Process-wide singleton. Call .subscribe_symbols(...) then .start() (both idempotent)."""
    global _MIRROR
    with _MIRROR_LOCK:
        if _MIRROR is None:
            _MIRROR = KiteZerodhaMirror()
    return _MIRROR


# timeframe string → seconds (the mirror only serves those in candle_timeframes()).
_TF_SECONDS: dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400,
}


def ohlcv(symbol: str, timeframe: str = "5m", limit: int = 220) -> list | None:
    """RAM-first NSE candles straight off the mirror, in ccxt OHLCV shape ([ms,o,h,l,c,v]).
    Returns None — so the caller falls back to OpenAlgo — when the mirror lacks the timeframe (only
    candle_timeframes() are rolled, default 1m/5m/15m), lacks the symbol, or hasn't warmed enough
    bars (<15). KITE_STREAM=0 or missing key → None. Never raises."""
    if not enabled():
        return None
    secs = _TF_SECONDS.get(str(timeframe))
    if secs is None:
        return None
    try:
        m = get_kite_mirror()
        if secs not in m.candle_timeframes():
            return None
        bars = m.candles(symbol, secs, int(limit))
        if not bars or len(bars) < 15:
            return None
        return [[int(b[0]) * 1000, float(b[1]), float(b[2]), float(b[3]), float(b[4]),
                 float(b[5] or 0.0)] for b in bars]
    except Exception:
        return None


def ticker(symbol: str) -> dict | None:
    if not enabled():
        return None
    try:
        return get_kite_mirror().ticker(symbol)
    except Exception:
        return None


def book(symbol: str, *, max_age_s: float = 5.0) -> dict | None:
    if not enabled():
        return None
    try:
        return get_kite_mirror().book(symbol, max_age_s=max_age_s)
    except Exception:
        return None


def nse_rows(*, min_volume: float = 0.0) -> list[dict]:
    if not enabled():
        return []
    try:
        return get_kite_mirror().nse_rows(min_volume=min_volume)
    except Exception:
        return []


def status() -> dict:
    try:
        return get_kite_mirror().status()
    except Exception:
        return {"enabled": enabled(), "running": False, "connected": False}
