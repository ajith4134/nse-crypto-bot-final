"""trading/crypto/session.py — Crypto T2 orchestrator (one honest entry point).

Wires the T2 pieces together, reusing T1's MasterToggle (market="CRYPTO"):

    ExchangeClient(s)  ── ccxt public data + (guarded) live orders
    CryptoFeed + TickCache ── live per-symbol prices (toggle-gated)
    CryptoWatchlist    ── persisted tracked symbols (drives feed)
    PaperEngine        ── paper fills against the REAL order book
    FundingMonitor     ── funding rates across exchanges
    MasterToggle       ── ON starts the feed, OFF stops ALL activity

paper_order() fills against a freshly-fetched live order book; it is the default
path. Live orders go through the exchange client and are refused unless live mode
+ keys + explicit allow_live.
"""
from __future__ import annotations

from trading.crypto.config import CryptoConfig, crypto_config
from trading.crypto.exchange_client import ExchangeClient
from trading.crypto.feed import CryptoFeed
from trading.crypto.funding import FundingMonitor
from trading.crypto.paper_engine import PaperEngine
from trading.crypto.watchlist import CryptoWatchlist
from trading.market_toggle import MasterToggle
from trading.tick_cache import TickCache


class CryptoSession:
    def __init__(self, config: CryptoConfig | None = None, market_type: str = "swap",
                 poll_interval: float = 2.0, starting_balance: float = 100_000.0):
        self.config = config or crypto_config
        self.market_type = market_type
        self.cache = TickCache()
        self.feed = CryptoFeed(cache=self.cache, config=self.config,
                               market_type=market_type, poll_interval=poll_interval)
        self.watchlist = CryptoWatchlist(feed=self.feed)
        self.paper = PaperEngine(starting_balance=starting_balance, quote=self.config.quote)
        self.funding = FundingMonitor(config=self.config)
        self.toggle = MasterToggle(market="CRYPTO",
                                   on_start=self.feed.start, on_stop=self.feed.stop)
        self._clients: dict[str, ExchangeClient] = {}
        if self.toggle.is_on:
            self.feed.start()

    def client(self, exchange: str | None = None) -> ExchangeClient:
        ex = (exchange or self.config.default_exchange).lower()
        if ex not in self._clients:
            self._clients[ex] = ExchangeClient(ex, self.market_type, self.config)
        return self._clients[ex]

    # ── orders ────────────────────────────────────────────────────────────────
    def paper_order(self, *, symbol: str, side: str, amount: float,
                    exchange: str | None = None, leverage: float = 1.0,
                    margin_mode: str = "isolated") -> dict:
        """Simulate a market order against the live order book (toggle must be ON)."""
        self.toggle.assert_on()
        ex = (exchange or self.config.default_exchange).lower()
        book = self.client(ex).order_book(symbol)
        return self.paper.market_order(
            symbol=symbol, exchange=ex, side=side, amount=amount, order_book=book,
            leverage=leverage, margin_mode=margin_mode,
        )

    def paper_close(self, symbol: str, exchange: str | None = None) -> dict:
        self.toggle.assert_on()
        ex = (exchange or self.config.default_exchange).lower()
        book = self.client(ex).order_book(symbol)
        return self.paper.close(symbol, ex, book)

    # ── status (honest, secrets-safe) ─────────────────────────────────────────
    def _mark_prices(self) -> dict:
        marks = {}
        for key, t in self.cache.snapshot().items():
            marks[key] = t["ltp"]
            marks[t["symbol"]] = t["ltp"]
        return marks

    def status(self) -> dict:
        marks = self._mark_prices()
        return {
            "config": self.config.as_status(),
            "market_type": self.market_type,
            "toggle": {"market": self.toggle.market, "on": self.toggle.is_on},
            "feed": {"running": self.feed.is_running},
            "watchlist": [
                {"symbol": i.symbol, "exchange": i.exchange, "market_type": i.market_type}
                for i in self.watchlist.items()
            ],
            "ticks": self.cache.snapshot(),
            "paper": self.paper.summary(marks),
        }

    def shutdown(self) -> None:
        self.feed.stop()
