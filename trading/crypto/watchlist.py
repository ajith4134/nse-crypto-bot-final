"""trading/crypto/watchlist.py — persisted crypto watchlist (T2).

Same pattern as the T1 NSE watchlist but with its OWN state file
(crypto_watchlist.json) and an exchange + market-type per item, and it drives a
CryptoFeed instead of the OpenAlgo feed. Reuses trading.state for persistence.
"""
from __future__ import annotations

from dataclasses import dataclass

from trading import state
from trading.crypto.config import crypto_config

_WATCHLIST_FILE = "crypto_watchlist.json"


@dataclass(frozen=True)
class CryptoWatchItem:
    symbol: str
    exchange: str
    market_type: str = "swap"

    @property
    def key(self) -> str:
        return f"{self.exchange.upper()}:{self.symbol.upper()}"


class CryptoWatchlist:
    def __init__(self, feed=None):
        self.feed = feed
        raw = state.load_json(_WATCHLIST_FILE, [])
        self._items: list[CryptoWatchItem] = [
            CryptoWatchItem(r["symbol"], r["exchange"], r.get("market_type", "swap"))
            for r in raw
            if isinstance(r, dict) and r.get("symbol") and r.get("exchange")
        ]
        if self.feed is not None:
            for it in self._items:
                self.feed.subscribe(it.symbol, it.exchange)

    def items(self) -> list[CryptoWatchItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item: object) -> bool:
        return isinstance(item, CryptoWatchItem) and any(i.key == item.key for i in self._items)

    def add(self, symbol: str, exchange: str | None = None, market_type: str = "swap") -> bool:
        exchange = (exchange or crypto_config.default_exchange).upper()
        item = CryptoWatchItem(symbol.upper(), exchange, market_type)
        if item in self:
            return False
        self._items.append(item)
        self._persist()
        if self.feed is not None:
            self.feed.subscribe(item.symbol, item.exchange)
        return True

    def remove(self, symbol: str, exchange: str | None = None) -> bool:
        exchange = (exchange or crypto_config.default_exchange).upper()
        key = f"{exchange.upper()}:{symbol.upper()}"
        before = len(self._items)
        self._items = [i for i in self._items if i.key != key]
        if len(self._items) == before:
            return False
        self._persist()
        if self.feed is not None:
            self.feed.unsubscribe(symbol, exchange)
        return True

    def clear(self) -> None:
        for it in list(self._items):
            if self.feed is not None:
                self.feed.unsubscribe(it.symbol, it.exchange)
        self._items = []
        self._persist()

    def _persist(self) -> None:
        state.save_json(_WATCHLIST_FILE, [
            {"symbol": i.symbol, "exchange": i.exchange, "market_type": i.market_type}
            for i in self._items
        ])
