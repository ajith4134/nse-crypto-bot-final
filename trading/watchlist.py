"""trading/watchlist.py — persisted NSE watchlist (T1 §6).

A search-add-remove watchlist whose state survives restarts (state/watchlist.json).
Empty watchlist is allowed — per the blueprint, an empty list later means "bot
self-selects", but in T1 it simply means nothing is tracked.

Each entry is an instrument (symbol+exchange). Adding to the watchlist optionally
subscribes the live tick feed so prices stream in; removing unsubscribes — keeping
the feed honest (we only stream what's actually watched).
"""
from __future__ import annotations

from dataclasses import dataclass

from trading import state
from trading.instruments import InstrumentStore, Instrument
from trading.tick_cache import MarketFeed

_WATCHLIST_FILE = "watchlist.json"


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    exchange: str

    @property
    def key(self) -> str:
        return f"{self.exchange.upper()}:{self.symbol.upper()}"


class Watchlist:
    """Ordered, de-duplicated watchlist with JSON persistence."""

    def __init__(self, feed: MarketFeed | None = None, store: InstrumentStore | None = None):
        self.feed = feed
        self.store = store
        raw = state.load_json(_WATCHLIST_FILE, [])
        self._items: list[WatchItem] = [
            WatchItem(r["symbol"], r["exchange"]) for r in raw
            if isinstance(r, dict) and r.get("symbol") and r.get("exchange")
        ]
        # Re-subscribe persisted symbols to the feed (if a feed is attached).
        if self.feed is not None:
            for it in self._items:
                self.feed.subscribe(it.symbol, it.exchange)

    # ── queries ───────────────────────────────────────────────────────────────
    def items(self) -> list[WatchItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, WatchItem):
            return any(i.key == item.key for i in self._items)
        return False

    def search(self, query: str, exchange: str = "NSE") -> list[Instrument]:
        """Search instruments to add (delegates to the OpenAlgo-backed store)."""
        if self.store is None:
            raise RuntimeError("Watchlist has no InstrumentStore; cannot search.")
        return self.store.search(query, exchange)

    # ── mutations ─────────────────────────────────────────────────────────────
    def add(self, symbol: str, exchange: str = "NSE") -> bool:
        """Add a symbol. Returns False if already present. Subscribes the feed."""
        item = WatchItem(symbol.upper(), exchange.upper())
        if item in self:
            return False
        self._items.append(item)
        self._persist()
        if self.feed is not None:
            self.feed.subscribe(item.symbol, item.exchange)
        return True

    def remove(self, symbol: str, exchange: str = "NSE") -> bool:
        """Remove a symbol. Returns False if absent. Unsubscribes the feed."""
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
        state.save_json(
            _WATCHLIST_FILE,
            [{"symbol": i.symbol, "exchange": i.exchange} for i in self._items],
        )
