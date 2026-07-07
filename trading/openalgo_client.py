"""trading/openalgo_client.py — thin, honest wrapper over the OpenAlgo REST SDK.

OpenAlgo is a self-hosted middleware server (Flask+React) that unifies 33 Indian
brokers behind one REST API. It must already be running at OPENALGO_HOST
(default http://127.0.0.1:5000) before any call here succeeds — this wrapper does
NOT start it. See trading-execution-blueprint.md §8.1.

Design:
  • Single source of truth for SDK method/param names — if OpenAlgo changes a
    signature, fix it here only.
  • Lazy import: the module imports fine even when `openalgo` isn't installed yet,
    so the rest of the package (config, instruments parsing, tests) stays usable.
  • Honest connectivity: `ping()` actually round-trips to the server (funds call)
    and returns a typed result — never a fabricated "connected".
  • Live-trade guard: order methods refuse to dispatch a LIVE order unless
    trading_config.is_live AND `allow_live=True` is explicitly passed.

Usage:
    from trading.openalgo_client import OpenAlgoClient
    cli = OpenAlgoClient()
    health = cli.ping()              # -> ConnState(connected=..., detail=...)
    cli.place_order(symbol="RELIANCE", action="BUY", exchange="NSE", quantity=1)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading.config import TradingConfig, trading_config


@dataclass(frozen=True)
class ConnState:
    """Result of a real connectivity probe — no optimistic guessing."""
    connected: bool
    host: str
    detail: str
    broker: str | None = None


class OpenAlgoError(RuntimeError):
    """Raised for OpenAlgo API / transport failures with a clear message."""


class OpenAlgoClient:
    """Wraps the `openalgo` python SDK. One instance per process is enough."""

    # OpenAlgo "strategy" tag attached to every order (shown in its order book).
    DEFAULT_STRATEGY = "MLNetworkBrain"

    def __init__(self, config: TradingConfig | None = None, strategy: str | None = None):
        self.config = config or trading_config
        self.strategy = strategy or self.DEFAULT_STRATEGY
        self._sdk: Any | None = None  # lazily constructed openalgo.api instance
        self._lot_cache: dict[tuple[str, str], int] = {}  # (symbol, exchange) -> lotsize

    # ── SDK lifecycle ─────────────────────────────────────────────────────────
    def _client(self) -> Any:
        """Build (once) and return the underlying openalgo.api client."""
        if self._sdk is not None:
            return self._sdk
        try:
            from openalgo import api  # type: ignore
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise OpenAlgoError(
                "The 'openalgo' SDK is not installed. Run:\n"
                "    .venv/bin/pip install openalgo\n"
                "and start the OpenAlgo server at "
                f"{self.config.openalgo_host}."
            ) from exc
        key = self.config.require_key()
        self._sdk = api(
            api_key=key,
            host=self.config.openalgo_host,
            ws_url=self.config.openalgo_ws_url,
        )
        return self._sdk

    # ── connectivity ──────────────────────────────────────────────────────────
    def ping(self) -> ConnState:
        """Round-trip to the server (funds endpoint). Honest connected/not state."""
        host = self.config.openalgo_host
        if not self.config.is_configured:
            return ConnState(False, host, "OPENALGO_API_KEY absent in .env")
        try:
            resp = self._client().funds()
        except OpenAlgoError as exc:
            return ConnState(False, host, str(exc))
        except Exception as exc:  # transport / server-down / auth
            return ConnState(False, host, f"{type(exc).__name__}: {exc}")
        status = (resp or {}).get("status") if isinstance(resp, dict) else None
        if status == "success":
            return ConnState(True, host, "funds endpoint OK", broker=(resp or {}).get("broker"))
        return ConnState(False, host, f"unexpected response: {resp!r}")

    # ── analyzer (paper/sandbox) mode ─────────────────────────────────────────
    def analyzer_status(self) -> dict:
        """Return OpenAlgo's analyzer state ({'analyze_mode': bool, ...})."""
        return self._check(self._client().analyzerstatus(), "analyzerstatus")

    def set_analyzer(self, analyze: bool) -> dict:
        """Toggle OpenAlgo analyzer mode: True = simulated (paper), False = live."""
        return self._check(self._client().analyzertoggle(mode=bool(analyze)), "analyzertoggle")

    def sync_mode(self) -> bool:
        """Ensure the server's analyzer matches our TRADING_MODE. Returns analyze_mode.

        paper -> analyzer ON (orders simulated in the sandbox, no live broker hit)
        live  -> analyzer OFF (orders sent to the real broker)
        """
        want_analyze = not self.config.is_live
        try:
            cur = self.analyzer_status().get("data", {})
            if bool(cur.get("analyze_mode")) != want_analyze:
                self.set_analyzer(want_analyze)
        except OpenAlgoError:
            # Older servers may lack the analyzer endpoints; surface via ping instead.
            self.set_analyzer(want_analyze)
        return want_analyze

    # ── orders ────────────────────────────────────────────────────────────────
    def _guard_live(self, allow_live: bool) -> None:
        if self.config.is_live and not allow_live:
            raise OpenAlgoError(
                "Refusing to place a LIVE order: TRADING_MODE=live but allow_live "
                "was not explicitly set. Pass allow_live=True to confirm real money."
            )

    def place_order(
        self,
        *,
        symbol: str,
        action: str,                 # "BUY" | "SELL"
        exchange: str = "NSE",
        quantity: int = 1,
        product: str = "MIS",        # MIS (intraday) | CNC | NRML
        price_type: str = "MARKET",  # MARKET | LIMIT | SL | SL-M
        price: float = 0.0,
        trigger_price: float = 0.0,
        allow_live: bool = False,
    ) -> dict:
        """Place an order via OpenAlgo. In paper mode this hits OpenAlgo's sandbox."""
        self._guard_live(allow_live)
        resp = self._client().placeorder(
            strategy=self.strategy,
            symbol=symbol,
            action=action.upper(),
            exchange=exchange.upper(),
            price_type=price_type.upper(),
            product=product.upper(),
            quantity=str(quantity),
            price=str(price),
            trigger_price=str(trigger_price),
        )
        return self._check(resp, "placeorder")

    def modify_order(
        self,
        *,
        order_id: str,
        symbol: str,
        action: str,
        exchange: str,
        quantity: int,
        price: float,
        product: str = "MIS",
        price_type: str = "LIMIT",
        trigger_price: float = 0.0,
        allow_live: bool = False,
    ) -> dict:
        self._guard_live(allow_live)
        resp = self._client().modifyorder(
            order_id=str(order_id),
            strategy=self.strategy,
            symbol=symbol,
            action=action.upper(),
            exchange=exchange.upper(),
            price_type=price_type.upper(),
            product=product.upper(),
            quantity=str(quantity),
            price=str(price),
            trigger_price=str(trigger_price),
        )
        return self._check(resp, "modifyorder")

    def cancel_order(self, order_id: str) -> dict:
        resp = self._client().cancelorder(order_id=str(order_id), strategy=self.strategy)
        return self._check(resp, "cancelorder")

    def cancel_all(self) -> dict:
        """Kill-switch helper: cancel every open order for our strategy."""
        resp = self._client().cancelallorder(strategy=self.strategy)
        return self._check(resp, "cancelallorder")

    # ── read-only data ────────────────────────────────────────────────────────
    def quote(self, symbol: str, exchange: str = "NSE") -> dict:
        resp = self._client().quotes(symbol=symbol, exchange=exchange.upper())
        return self._check(resp, "quotes")

    def depth(self, symbol: str, exchange: str = "NSE") -> dict:
        """5-level order-book depth (bids/asks price+quantity) for a symbol."""
        resp = self._client().depth(symbol=symbol, exchange=exchange.upper())
        return self._check(resp, "depth")

    def history(self, symbol: str, exchange: str = "NSE", *, interval: str = "5m",
                start_date: str, end_date: str) -> dict:
        """Historical OHLCV candles from the broker (via OpenAlgo). interval e.g. 1m/5m/15m/1h/D;
        dates are 'YYYY-MM-DD'. Returns the raw server dict (data = list of candle rows)."""
        resp = self._client().history(symbol=symbol, exchange=exchange.upper(),
                                      interval=interval, start_date=start_date,
                                      end_date=end_date)
        # history() may return a pandas DataFrame (SDK) or a dict — normalize to a dict
        if hasattr(resp, "to_dict"):
            return {"status": "success", "data": resp.reset_index().to_dict("records")}
        return self._check(resp, "history")

    def symbol_info(self, symbol: str, exchange: str = "NSE") -> dict:
        """Master-contract row for a symbol (lotsize, ticksize, expiry, token, …)."""
        resp = self._client().symbol(symbol=symbol, exchange=exchange.upper())
        return self._check(resp, "symbol")

    def lot_size(self, symbol: str, exchange: str = "NSE") -> int | None:
        """REAL lot size from OpenAlgo's master contract, cached per (symbol, exchange).
        Returns None when the symbol is unknown or the server is unreachable — callers
        must fall back to their own default rather than trade a guessed lot."""
        key = (symbol, exchange.upper())
        if key in self._lot_cache:
            return self._lot_cache[key]
        try:
            d = self.symbol_info(symbol, exchange).get("data") or {}
            lot = int(float(d.get("lotsize") or 0))
        except Exception:
            return None
        if lot > 0:
            self._lot_cache[key] = lot
            return lot
        return None

    def funds(self) -> dict:
        return self._check(self._client().funds(), "funds")

    def positions(self) -> dict:
        return self._check(self._client().positionbook(), "positionbook")

    def orders(self) -> dict:
        return self._check(self._client().orderbook(), "orderbook")

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _check(resp: Any, endpoint: str) -> dict:
        """Validate an OpenAlgo response envelope; raise on API-level failure."""
        if not isinstance(resp, dict):
            raise OpenAlgoError(f"{endpoint}: non-dict response {resp!r}")
        if resp.get("status") == "error":
            raise OpenAlgoError(f"{endpoint} failed: {resp.get('message', resp)}")
        return resp
