"""trading/session.py — NSE T1 orchestrator (single honest entry point).

Wires the T1 foundation pieces into one object that the runner, tests, and the
dashboard status endpoint all share:

    OpenAlgoClient ── connectivity, orders
    InstrumentStore ── symbol search (watchlist add)
    MarketFeed + TickCache ── live per-symbol prices
    Watchlist ── persisted tracked symbols (drives feed subscriptions)
    MasterToggle ── ON starts the feed, OFF stops ALL activity
    squareoff ── exchange auto-flatten deadlines

Order placement goes through `place_order`, which enforces BOTH guards:
master-toggle-ON and (for live) explicit confirmation.
"""
from __future__ import annotations

from trading import squareoff
from trading.config import TradingConfig, trading_config
from trading.instruments import InstrumentStore
from trading.market_toggle import MasterToggle
from trading.openalgo_client import OpenAlgoClient
from trading.tick_cache import MarketFeed, TickCache
from trading.watchlist import Watchlist


class NSESession:
    """The live NSE trading session (T1 foundation)."""

    def __init__(self, config: TradingConfig | None = None, poll_interval: float = 1.0):
        self.config = config or trading_config
        self.client = OpenAlgoClient(config=self.config)
        self.store = InstrumentStore(client=self.client)
        self.cache = TickCache()
        self.feed = MarketFeed(cache=self.cache, client=self.client, poll_interval=poll_interval)
        self.watchlist = Watchlist(feed=self.feed, store=self.store)
        self.toggle = MasterToggle(
            market="NSE",
            on_start=self.feed.start,
            on_stop=self.feed.stop,
        )
        # If the toggle was persisted ON, the feed should already be running.
        if self.toggle.is_on:
            self.feed.start()

    # ── orders (guarded) ──────────────────────────────────────────────────────
    def place_order(self, *, symbol: str, action: str, exchange: str = "NSE",
                    quantity: int = 1, allow_live: bool = False, **kw) -> dict:
        """Place an order only when the market is ON; live requires confirmation."""
        self.toggle.assert_on()
        # Ensure the OpenAlgo server's analyzer matches our mode (paper -> sandbox).
        self.client.sync_mode()
        return self.client.place_order(
            symbol=symbol, action=action, exchange=exchange,
            quantity=quantity, allow_live=allow_live, **kw,
        )

    def cancel_order(self, order_id: str) -> dict:
        self.toggle.assert_on()
        return self.client.cancel_order(order_id)

    # ── status (honest, secrets-safe) ─────────────────────────────────────────
    def status(self) -> dict:
        conn = self.client.ping()
        return {
            "config": self.config.as_status(),
            "connection": {
                "connected": conn.connected,
                "host": conn.host,
                "detail": conn.detail,
                "broker": conn.broker,
            },
            "toggle": {"market": self.toggle.market, "on": self.toggle.is_on},
            "feed": {"running": self.feed.is_running, "mode": self.feed.mode},
            "watchlist": [
                {"symbol": i.symbol, "exchange": i.exchange} for i in self.watchlist.items()
            ],
            "ticks": self.cache.snapshot(),
            "squareoff_due": squareoff.due_exchanges(),
        }

    def shutdown(self) -> None:
        self.feed.stop()
