"""trading/tick_cache.py — per-symbol real-time price cache (T1 §5).

Maintains the latest tick per subscribed symbol in a thread-safe cache, fed by:
  1. OpenAlgo WebSocket LTP feed (preferred — push, low latency), or
  2. REST quote polling (fallback) when the WS feed is unavailable.

Honest-wiring + toggle compliance: the feed only runs while started. The NSE
master toggle (market_toggle.py) calls stop() on OFF, guaranteeing ZERO polling
and zero network activity when the market switch is off (T1 §7).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from trading.openalgo_client import OpenAlgoClient, OpenAlgoError


@dataclass
class Tick:
    symbol: str
    exchange: str
    ltp: float = 0.0
    ts: float = 0.0          # epoch seconds when received
    raw: dict = field(default_factory=dict)

    def is_stale(self, max_age: float = 10.0) -> bool:
        """True if no tick, or the last tick is older than max_age seconds."""
        return (time.time() - self.ts) > max_age if self.ts else True


class TickCache:
    """Thread-safe latest-tick store. Read by the dashboard / strategy layer."""

    def __init__(self):
        self._lock = threading.RLock()
        self._ticks: dict[str, Tick] = {}

    @staticmethod
    def _key(symbol: str, exchange: str) -> str:
        return f"{exchange.upper()}:{symbol.upper()}"

    def update(self, symbol: str, exchange: str, ltp: float, raw: dict | None = None) -> None:
        k = self._key(symbol, exchange)
        with self._lock:
            self._ticks[k] = Tick(symbol, exchange, float(ltp), time.time(), raw or {})

    def get(self, symbol: str, exchange: str = "NSE") -> Tick | None:
        with self._lock:
            return self._ticks.get(self._key(symbol, exchange))

    def snapshot(self) -> dict[str, dict]:
        """Honest snapshot for the dashboard: only symbols we actually received."""
        with self._lock:
            return {
                k: {"symbol": t.symbol, "exchange": t.exchange, "ltp": t.ltp, "ts": t.ts}
                for k, t in self._ticks.items()
            }

    def clear(self) -> None:
        with self._lock:
            self._ticks.clear()


class MarketFeed:
    """Drives a TickCache from OpenAlgo. WS-first, REST-poll fallback.

    Lifecycle: subscribe(...) registers interest; start() begins the feed in a
    background thread; stop() halts ALL activity (toggle-OFF contract).
    """

    def __init__(
        self,
        cache: TickCache | None = None,
        client: OpenAlgoClient | None = None,
        poll_interval: float = 1.0,
    ):
        self.cache = cache or TickCache()
        self.client = client or OpenAlgoClient()
        self.poll_interval = poll_interval
        self._subs: dict[str, tuple[str, str]] = {}  # key -> (symbol, exchange)
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._ws = None            # underlying openalgo ws handle, if used
        self._mode: str = "idle"   # "ws" | "poll" | "idle"

    # ── subscription management ───────────────────────────────────────────────
    def subscribe(self, symbol: str, exchange: str = "NSE") -> None:
        key = f"{exchange.upper()}:{symbol.upper()}"
        with self._lock:
            self._subs[key] = (symbol, exchange.upper())
        if self._running and self._mode == "ws":
            self._ws_subscribe([(symbol, exchange.upper())])

    def unsubscribe(self, symbol: str, exchange: str = "NSE") -> None:
        key = f"{exchange.upper()}:{symbol.upper()}"
        with self._lock:
            self._subs.pop(key, None)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        return self._mode

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if not self._try_start_ws():
            self._mode = "poll"
            self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="nse-poll")
            self._thread.start()

    def stop(self) -> None:
        """Halt the feed completely — the toggle-OFF = zero-activity contract."""
        self._running = False
        self._mode = "idle"
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                ws.disconnect()
            except Exception:
                pass
        t = self._thread
        self._thread = None
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=self.poll_interval + 1.0)

    # ── WebSocket path ────────────────────────────────────────────────────────
    def _try_start_ws(self) -> bool:
        """Attempt the OpenAlgo WS LTP feed. Returns True on success."""
        try:
            sdk = self.client._client()
        except OpenAlgoError:
            return False
        if not all(hasattr(sdk, m) for m in ("connect", "subscribe_ltp")):
            return False
        try:
            sdk.connect()
        except Exception:
            return False
        self._ws = sdk
        self._mode = "ws"
        with self._lock:
            current = list(self._subs.values())
        if current:
            self._ws_subscribe(current)
        return True

    def _ws_subscribe(self, pairs: list[tuple[str, str]]) -> None:
        if self._ws is None:
            return
        instruments = [{"exchange": ex, "symbol": sym} for sym, ex in pairs]
        try:
            self._ws.subscribe_ltp(instruments, on_data_received=self._on_ws_data)
        except Exception:
            # WS broke mid-flight — fall back to polling.
            self._mode = "poll"
            if not (self._thread and self._thread.is_alive()):
                self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="nse-poll")
                self._thread.start()

    def _on_ws_data(self, data) -> None:
        """OpenAlgo WS callback. Payload shape varies; extract LTP defensively."""
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if not isinstance(row, dict):
                continue
            sym = row.get("symbol") or row.get("tradingsymbol")
            ex = (row.get("exchange") or "NSE").upper()
            ltp = row.get("ltp") or row.get("last_price") or row.get("lp")
            if sym and ltp is not None:
                try:
                    self.cache.update(sym, ex, float(ltp), row)
                except (TypeError, ValueError):
                    continue

    # ── REST polling path ─────────────────────────────────────────────────────
    def _poll_loop(self) -> None:
        while self._running:
            with self._lock:
                pairs = list(self._subs.values())
            for sym, ex in pairs:
                if not self._running:
                    break
                try:
                    resp = self.client.quote(sym, ex)
                    data = resp.get("data", resp)
                    ltp = data.get("ltp") or data.get("last_price") or data.get("lp")
                    if ltp is not None:
                        self.cache.update(sym, ex, float(ltp), data if isinstance(data, dict) else {})
                except Exception:
                    # One bad symbol shouldn't kill the loop; skip this tick.
                    continue
            # Sleep in small slices so stop() is responsive.
            slept = 0.0
            while self._running and slept < self.poll_interval:
                time.sleep(0.1)
                slept += 0.1
