"""trading/advintel/arbitrage.py — Phase-T8 cross-exchange arbitrage scanner +
funding-rate farming detector.

Two honest, fee-aware scanners:

1. Spot price arbitrage — buy the cheapest ask, sell the richest bid across
   exchanges. Net of round-trip taker fees + slippage; only flagged
   ``actionable`` when the spread clears the cost floor.

2. Funding-rate farming — go LONG on the exchange that *pays* you funding and
   SHORT on the one where you *pay*, capturing the funding spread delta-neutral.
   Net funding must beat the (small, periodic) fee drag to be ``profitable``.

OFFLINE-TESTABLE + GATED: all market data flows through INJECTED source
callables. Tests pass stubs (no network). Live ccxt public REST is used only
when no source is injected AND the scanner is driven live.

  price_source(exchange, symbol)   -> {"bid": float, "ask": float}
  funding_source(exchange, symbol) -> funding rate (fraction; +0.0001 = +0.01%)

Aligned with trading/crypto/funding.py: funding rate is a fraction where a
POSITIVE rate means longs pay shorts; annualization assumes 8h funding
(3x/day, 1095x/year).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# Funding periodicity: most perps settle every 8h => 3/day => 1095/year.
FUNDING_PERIODS_PER_YEAR = 3 * 365


@dataclass(frozen=True)
class CostModel:
    """Configurable fee/slippage assumption (fractions, per side)."""
    taker_fee: float = 0.0005        # 0.05% per side (taker)
    slippage: float = 0.0            # extra per-side cushion

    @property
    def per_side(self) -> float:
        return self.taker_fee + self.slippage

    @property
    def round_trip(self) -> float:
        """Buy on one venue + sell on the other = two taker legs."""
        return 2.0 * self.per_side

    def as_dict(self) -> dict:
        return {
            "taker_fee": self.taker_fee,
            "slippage": self.slippage,
            "per_side": self.per_side,
            "round_trip": self.round_trip,
        }


@dataclass
class ArbitrageScanner:
    """Cross-exchange spot arb + funding-farm detector.

    Inject ``price_source`` / ``funding_source`` for offline/testable use; leave
    them ``None`` to fall back to live ccxt public calls (network).
    """
    price_source: Callable[[str, str], dict] | None = None
    funding_source: Callable[[str, str], float] | None = None
    costs: CostModel = field(default_factory=CostModel)

    # cache live ccxt clients (only built if no source injected)
    _clients: dict[str, object] = field(default_factory=dict, init=False, repr=False)
    _scans: int = field(default=0, init=False, repr=False)

    # ------------------------------------------------------------------ data
    def _client(self, exchange: str):
        if exchange not in self._clients:
            import ccxt  # imported lazily so import never needs network/ccxt at module load
            self._clients[exchange] = getattr(ccxt, exchange)({"enableRateLimit": True})
        return self._clients[exchange]

    def _price(self, exchange: str, symbol: str) -> dict | None:
        try:
            if self.price_source is not None:
                q = self.price_source(exchange, symbol)
            else:
                t = self._client(exchange).fetch_ticker(symbol)
                q = {"bid": t.get("bid"), "ask": t.get("ask")}
        except Exception:
            return None
        if q is None:
            return None
        bid, ask = q.get("bid"), q.get("ask")
        if bid is None or ask is None:
            return None
        return {"bid": float(bid), "ask": float(ask)}

    def _funding(self, exchange: str, symbol: str) -> float | None:
        try:
            if self.funding_source is not None:
                r = self.funding_source(exchange, symbol)
            else:
                r = self._client(exchange).fetch_funding_rate(symbol).get("fundingRate")
        except Exception:
            return None
        return None if r is None else float(r)

    # ------------------------------------------------------------------ spot
    def scan_spot(self, symbol: str,
                  exchanges: tuple[str, ...] = ("binance", "bybit")) -> dict | None:
        """Cross-exchange spot spread: buy cheapest ask, sell richest bid."""
        self._scans += 1
        quotes = {}
        for ex in exchanges:
            p = self._price(ex, symbol)
            if p is not None:
                quotes[ex] = p
        if len(quotes) < 2:
            return None

        # sell where bid is highest, buy where ask is lowest
        best_bid_exch = max(quotes, key=lambda e: quotes[e]["bid"])
        best_ask_exch = min(quotes, key=lambda e: quotes[e]["ask"])
        best_bid = quotes[best_bid_exch]["bid"]
        best_ask = quotes[best_ask_exch]["ask"]

        spread_abs = best_bid - best_ask
        mid = (best_bid + best_ask) / 2.0
        spread_pct = (spread_abs / mid * 100.0) if mid else 0.0
        cost_pct = self.costs.round_trip * 100.0
        net_pct = spread_pct - cost_pct

        return {
            "symbol": symbol,
            "best_bid_exch": best_bid_exch,   # SELL here
            "best_ask_exch": best_ask_exch,   # BUY here
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_abs": spread_abs,
            "spread_pct": spread_pct,
            "cost_pct": cost_pct,
            "net_pct": net_pct,
            "direction": f"buy@{best_ask_exch} -> sell@{best_bid_exch}",
            "actionable": spread_abs > 0 and net_pct > 0,
        }

    def scan_universe(self, symbols, exchanges: tuple[str, ...] = ("binance", "bybit")) -> list[dict]:
        """Rank arb opportunities across symbols by spread_pct (desc)."""
        out = []
        for sym in symbols:
            r = self.scan_spot(sym, exchanges=exchanges)
            if r is not None:
                out.append(r)
        out.sort(key=lambda r: r["spread_pct"], reverse=True)
        return out

    # --------------------------------------------------------------- funding
    def funding_farm(self, symbol: str,
                     exchanges: tuple[str, ...] = ("binance", "bybit")) -> dict | None:
        """Delta-neutral funding farm: long where you're PAID, short where you PAY.

        A positive funding rate means longs pay shorts. So to receive funding we
        SHORT the high-rate venue and LONG the low-rate venue; the captured rate
        per period is (high - low).

        Honest cost model: funding income RECURS every period while the position
        is held, but the entry/exit (round-trip) fee is paid ONCE. So we do not
        net the fee against a single period — we net it against the annualized
        carry, and report ``breakeven_periods`` (how long the farm must be held
        to recover the one-time fee).
        """
        self._scans += 1
        rates = {}
        for ex in exchanges:
            f = self._funding(ex, symbol)
            if f is not None:
                rates[ex] = f
        if len(rates) < 2:
            return None

        short_exch = max(rates, key=lambda e: rates[e])   # high rate: shorts get paid
        long_exch = min(rates, key=lambda e: rates[e])    # low/neg rate: longs get paid
        net_funding_rate = rates[short_exch] - rates[long_exch]  # per period, >= 0

        entry_cost = self.costs.round_trip                # one-time round-trip fee
        annualized_pct = net_funding_rate * FUNDING_PERIODS_PER_YEAR * 100.0
        # subtract the one-time entry cost once from a year of carry
        annualized_net_pct = annualized_pct - entry_cost * 100.0
        breakeven_periods = (entry_cost / net_funding_rate) if net_funding_rate > 0 else None

        return {
            "symbol": symbol,
            "long_exch": long_exch,
            "short_exch": short_exch,
            "long_rate": rates[long_exch],
            "short_rate": rates[short_exch],
            "net_funding_rate": net_funding_rate,
            "entry_cost": entry_cost,
            "breakeven_periods": breakeven_periods,
            "annualized_pct": annualized_pct,
            "annualized_net_pct": annualized_net_pct,
            # positive net carry AND the one-time fee is recovered within a year
            "profitable": net_funding_rate > 0 and annualized_net_pct > 0,
        }

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        return {
            "scanner": "ArbitrageScanner",
            "live_mode": self.price_source is None or self.funding_source is None,
            "price_source": "injected" if self.price_source else "live(ccxt)",
            "funding_source": "injected" if self.funding_source else "live(ccxt)",
            "costs": self.costs.as_dict(),
            "funding_periods_per_year": FUNDING_PERIODS_PER_YEAR,
            "scans_run": self._scans,
        }
