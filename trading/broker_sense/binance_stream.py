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
# DEPTH mirror (2026-07-12): per-symbol 20-level partial book for the top-N movers, pushed at 500ms,
# so psychology (OBI/microprice/walls) reads depth from RAM instead of a ~300ms REST fetch_order_book
# per symbol × the shortlist (the funnel EXECUTE hotspot). Bounded: N streams in one connection,
# symbol set refreshed by reconnect. All-market full depth is a firehose, so we scope to the movers.
_DEPTH_HOST = "wss://fstream.binance.com/stream?streams="
_DEPTH_N = int(os.getenv("BINANCE_DEPTH_N", "120") or 120)      # streams per connection (cap)
_DEPTH_REFRESH_S = float(os.getenv("BINANCE_DEPTH_REFRESH_S", "300") or 300)   # re-pick movers


def depth_enabled() -> bool:
    return enabled() and os.getenv("BINANCE_STREAM_DEPTH", "1").strip().lower() not in ("0", "false", "off")


def enabled() -> bool:
    return os.getenv("BINANCE_STREAM", "1").strip().lower() not in ("0", "false", "off")


class BinanceUniverseMirror:
    """Live in-RAM snapshot of Binance USDⓈ-M futures, updated by the all-market push streams."""

    def __init__(self):
        self._mark: dict[str, dict] = {}        # symbol -> {mark, funding_rate, next_funding_ts, ts}
        self._ticker: dict[str, dict] = {}       # symbol -> {last, pct_change, high, low, quote_volume, count, ts}
        self._book: dict[str, dict] = {}         # symbol -> {bids:[[p,q]], asks:[[p,q]], ts} (20-lvl depth)
        self._liqs: deque = deque(maxlen=_MAX_LIQS)   # recent liquidation events (all symbols)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._depth_thread: threading.Thread | None = None
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
        try:
            stream = msg.get("stream", "")
            data = msg.get("data")
            now = time.time()
            self._last_msg_ts = now
            if stream.startswith("!markPrice") and isinstance(data, list):
                with self._lock:
                    for d in data:
                        s = d.get("s")
                        if not s:
                            continue
                        self._mark[s] = {
                            "mark": _f(d.get("p")),
                            "funding_rate": _f(d.get("r")),
                            "next_funding_ts": _i(d.get("T")),
                            "ts": now,
                        }
            elif stream.startswith("!ticker") and isinstance(data, list):
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
                o = (data or {}).get("o") if isinstance(data, dict) else None
                if isinstance(o, dict) and o.get("s"):
                    with self._lock:
                        self._liqs.append({
                            "symbol": o.get("s"), "side": o.get("S"),
                            "qty": _f(o.get("q")), "price": _f(o.get("p")),
                            "ts": _i(o.get("T")) / 1000.0 if o.get("T") else now,
                        })
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
            pass

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

    def start(self) -> "BinanceUniverseMirror":
        if not enabled() or self._running:
            return self
        self._running = True
        self._started_ts = time.time()
        self._backfill_rest()                    # immediate data so the first read isn't empty
        self._thread = threading.Thread(target=self._run, daemon=True, name="binance-mirror")
        self._thread.start()
        if depth_enabled():                      # separate connection: 20-level depth for movers
            self._depth_thread = threading.Thread(target=self._run_depth, daemon=True,
                                                  name="binance-mirror-depth")
            self._depth_thread.start()
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
