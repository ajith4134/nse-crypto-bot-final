"""trading/crypto/funding.py — perpetual funding-rate monitor (T2 §5).

Aggregates live funding rates across exchanges so the dashboard can show the
funding basis (and later, cross-exchange funding arbitrage). Network access is
delegated to an injected client resolver, so this is unit-testable with a fake.

A positive funding rate => longs pay shorts (perp trading above spot).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from trading.crypto.config import CryptoConfig, crypto_config
from trading.crypto.exchange_client import ExchangeClient


@dataclass(frozen=True)
class Funding:
    exchange: str
    symbol: str
    rate: float                 # current funding rate (fraction, e.g. 0.0001 = 0.01%)
    next_time: int | None       # ms epoch of next funding, if provided
    mark_price: float | None = None

    @property
    def rate_pct(self) -> float:
        return self.rate * 100.0

    @property
    def annualized_pct(self) -> float:
        # Most perps fund every 8h => 3x/day => 1095x/year.
        return self.rate * 3 * 365 * 100.0


class FundingMonitor:
    """Fetches funding rates for (exchange, symbol) pairs."""

    def __init__(self, config: CryptoConfig | None = None,
                 client_factory: Callable[[str], ExchangeClient] | None = None):
        self.config = config or crypto_config
        self._factory = client_factory or (lambda ex: ExchangeClient(ex, "swap", self.config))
        self._clients: dict[str, ExchangeClient] = {}

    def _client(self, exchange: str) -> ExchangeClient:
        if exchange not in self._clients:
            self._clients[exchange] = self._factory(exchange)
        return self._clients[exchange]

    def fetch(self, symbol: str, exchange: str) -> Funding | None:
        try:
            r = self._client(exchange).funding_rate(symbol)
        except Exception:
            return None
        rate = r.get("fundingRate")
        if rate is None:
            return None
        return Funding(
            exchange=exchange, symbol=symbol, rate=float(rate),
            next_time=r.get("fundingTimestamp") or r.get("nextFundingTime"),
            mark_price=r.get("markPrice"),
        )

    def scan(self, symbol: str, exchanges: list[str] | None = None) -> list[Funding]:
        """Funding for one symbol across exchanges (for basis comparison)."""
        out = []
        for ex in (exchanges or list(self.config.exchanges)):
            f = self.fetch(symbol, ex)
            if f is not None:
                out.append(f)
        return out

    @staticmethod
    def best_spread(rates: list[Funding]) -> dict | None:
        """Largest funding spread across exchanges (arb signal). None if <2."""
        if len(rates) < 2:
            return None
        hi = max(rates, key=lambda f: f.rate)
        lo = min(rates, key=lambda f: f.rate)
        return {
            "symbol": hi.symbol,
            "long_funding_exchange": lo.exchange,   # pay less / receive on the low side
            "short_funding_exchange": hi.exchange,
            "spread": hi.rate - lo.rate,
            "spread_pct": (hi.rate - lo.rate) * 100.0,
        }
