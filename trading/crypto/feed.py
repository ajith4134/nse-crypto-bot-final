"""trading/crypto/feed.py — crypto market feed (T2).

Polls ccxt tickers into a REUSED TickCache (from trading.tick_cache). Mirrors the
T1 MarketFeed lifecycle: subscribe interest, start() to poll in a background
thread, stop() to halt ALL activity (the crypto master-toggle OFF contract).

Public ticker data needs no API keys. ccxt REST polling keeps it simple and
dependency-light; a ccxt.pro WebSocket upgrade can drop in behind this interface.
"""
from __future__ import annotations

import threading
import time

from trading.crypto.config import CryptoConfig, crypto_config
from trading.crypto.exchange_client import ExchangeClient
from trading.tick_cache import TickCache


class CryptoFeed:
    """Polls subscribed (exchange, symbol) tickers into a TickCache."""

    def __init__(self, cache: TickCache | None = None, config: CryptoConfig | None = None,
                 market_type: str = "swap", poll_interval: float = 2.0):
        self.cache = cache or TickCache()
        self.config = config or crypto_config
        self.market_type = market_type
        self.poll_interval = poll_interval
        self._clients: dict[str, ExchangeClient] = {}
        self._subs: dict[str, tuple[str, str]] = {}   # key -> (symbol, exchange)
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None

    def _client(self, exchange: str) -> ExchangeClient:
        if exchange not in self._clients:
            self._clients[exchange] = ExchangeClient(exchange, self.market_type, self.config)
        return self._clients[exchange]

    # ── subscriptions ─────────────────────────────────────────────────────────
    def subscribe(self, symbol: str, exchange: str | None = None) -> None:
        exchange = (exchange or self.config.default_exchange).lower()
        key = f"{exchange.upper()}:{symbol.upper()}"
        with self._lock:
            self._subs[key] = (symbol, exchange)

    def unsubscribe(self, symbol: str, exchange: str | None = None) -> None:
        exchange = (exchange or self.config.default_exchange).lower()
        key = f"{exchange.upper()}:{symbol.upper()}"
        with self._lock:
            self._subs.pop(key, None)

    @property
    def is_running(self) -> bool:
        return self._running

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="crypto-poll")
        self._thread.start()

    def stop(self) -> None:
        """Halt the feed completely — toggle-OFF = zero-activity contract."""
        self._running = False
        t = self._thread
        self._thread = None
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=self.poll_interval + 1.0)

    def _poll_loop(self) -> None:
        while self._running:
            with self._lock:
                pairs = list(self._subs.values())
            for symbol, exchange in pairs:
                if not self._running:
                    break
                try:
                    tk = self._client(exchange).ticker(symbol)
                    last = tk.get("last") or tk.get("close")
                    if last is not None:
                        self.cache.update(symbol, exchange, float(last), tk)
                except Exception:
                    continue   # one bad symbol must not kill the loop
            slept = 0.0
            while self._running and slept < self.poll_interval:
                time.sleep(0.1)
                slept += 0.1
