"""trading/crypto/exchange_client.py — thin ccxt wrapper (T2).

One wrapper per (exchange, market_type). Public market data (ticker, order book,
funding rate, markets) needs NO API keys. Live order placement / leverage / margin
changes require keys AND are refused unless the config is in live mode with an
explicit allow_live confirmation.

Single source of truth for ccxt call shapes — if ccxt changes, fix it here only.
Lazy import so the package imports without ccxt installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading.crypto.config import CryptoConfig, crypto_config

# OpenAlgo-style market type -> ccxt defaultType
_DEFAULT_TYPE = {"spot": "spot", "swap": "swap", "future": "future", "option": "option"}


class ExchangeError(RuntimeError):
    """ccxt / transport failure with a clear message."""


@dataclass(frozen=True)
class Reachable:
    ok: bool
    exchange: str
    detail: str


class ExchangeClient:
    """Wraps one ccxt exchange for one market type."""

    def __init__(self, exchange: str | None = None, market_type: str = "swap",
                 config: CryptoConfig | None = None):
        self.config = config or crypto_config
        self.exchange = (exchange or self.config.default_exchange).lower()
        if market_type not in _DEFAULT_TYPE:
            raise ValueError(f"market_type must be one of {tuple(_DEFAULT_TYPE)}")
        self.market_type = market_type
        self._ex: Any | None = None

    # ── ccxt lifecycle ────────────────────────────────────────────────────────
    def _client(self) -> Any:
        if self._ex is not None:
            return self._ex
        try:
            import ccxt  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ExchangeError("ccxt not installed. Run: .venv/bin/pip install ccxt") from exc
        if not hasattr(ccxt, self.exchange):
            raise ExchangeError(f"unknown ccxt exchange '{self.exchange}'")
        opts = {
            "enableRateLimit": True,
            "timeout": 15000,
            "options": {"defaultType": _DEFAULT_TYPE[self.market_type]},
        }
        opts.update(self.config.keys_for(self.exchange).as_ccxt())  # keys only if present
        self._ex = getattr(ccxt, self.exchange)(opts)
        return self._ex

    def _norm(self, symbol: str) -> str:
        """Normalize to ccxt's unified linear-perp symbol for swap markets.

        ccxt linear perps are 'BASE/QUOTE:QUOTE' (e.g. BTC/USDT:USDT). For a swap
        session, a bare 'BTC/USDT' would resolve to spot; append the settle leg.
        """
        if self.market_type == "swap" and ":" not in symbol and "/" in symbol:
            return f"{symbol}:{self.config.quote}"
        return symbol

    # ── public market data (no keys) ──────────────────────────────────────────
    def reachable(self) -> Reachable:
        """Honest reachability probe (fetch BTC ticker). Never fabricates."""
        try:
            self.ticker(f"BTC/{self.config.quote}")
            return Reachable(True, self.exchange, "ticker OK")
        except Exception as exc:
            return Reachable(False, self.exchange, f"{type(exc).__name__}: {str(exc)[:120]}")

    def load_markets(self, reload: bool = False) -> dict:
        try:
            return self._client().load_markets(reload)
        except Exception as exc:
            raise ExchangeError(f"load_markets failed: {exc}") from exc

    def ticker(self, symbol: str) -> dict:
        try:
            return self._client().fetch_ticker(self._norm(symbol))
        except Exception as exc:
            raise ExchangeError(f"fetch_ticker({symbol}) failed: {exc}") from exc

    def order_book(self, symbol: str, limit: int = 50) -> dict:
        try:
            return self._client().fetch_order_book(self._norm(symbol), limit)
        except Exception as exc:
            raise ExchangeError(f"fetch_order_book({symbol}) failed: {exc}") from exc

    def funding_rate(self, symbol: str) -> dict:
        try:
            return self._client().fetch_funding_rate(self._norm(symbol))
        except Exception as exc:
            raise ExchangeError(f"fetch_funding_rate({symbol}) failed: {exc}") from exc

    def search_markets(self, query: str, limit: int = 25) -> list[dict]:
        """Filter loaded markets by symbol/base substring (no extra network)."""
        q = (query or "").upper()
        out = []
        for sym, m in self.load_markets().items():
            if q in sym.upper() or q in str(m.get("base", "")).upper():
                out.append({"symbol": sym, "base": m.get("base"), "quote": m.get("quote"),
                            "type": m.get("type"), "active": m.get("active")})
                if len(out) >= limit:
                    break
        return out

    # ── live trading (keys + explicit confirmation required) ──────────────────
    def _guard_live(self, allow_live: bool) -> None:
        if not self.config.is_live:
            raise ExchangeError("TRADING_MODE is not 'live' — use the paper engine instead.")
        if not allow_live:
            raise ExchangeError("Refusing live order without allow_live=True (real money).")
        if not self.config.has_keys(self.exchange):
            raise ExchangeError(f"No API keys for {self.exchange}; cannot trade live.")

    def set_leverage(self, leverage: int, symbol: str, allow_live: bool = False) -> dict:
        self._guard_live(allow_live)
        return self._client().set_leverage(leverage, symbol)

    def set_margin_mode(self, margin_mode: str, symbol: str, allow_live: bool = False) -> dict:
        self._guard_live(allow_live)  # "isolated" | "cross"
        return self._client().set_margin_mode(margin_mode, symbol)

    def create_order(self, *, symbol: str, side: str, amount: float, order_type: str = "market",
                     price: float | None = None, allow_live: bool = False, **params) -> dict:
        self._guard_live(allow_live)
        return self._client().create_order(symbol, order_type, side, amount, price, params)
