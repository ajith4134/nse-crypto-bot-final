"""trading/options/chain.py — OptionsChain container (T4 §3 live chain table).

Ties one chain snapshot (a list of OptionQuotes for a single expiry) to every T4
analytic: per-row Greeks + IV, Max Pain, PCR, GEX, OI heatmap, and multi-leg payoff.
Market data is INJECTED (quotes built from the broker/ccxt feed by the caller), so
this object is fully offline-testable and the live feed only has to produce quotes.

Black-76 forward `F` is the futures/forward price of the underlying; `r` the rate;
`t` the time-to-expiry in years. IV per row is taken from the quote if present,
else solved from its last price. `status()` returns one honest JSON-able snapshot
for the dashboard — computed values only, nothing decorative.
"""
from __future__ import annotations

from dataclasses import dataclass

from trading.options.gex import gamma_exposure
from trading.options.greeks import get_all_greeks, implied_vol
from trading.options.max_pain import max_pain
from trading.options.oi import oi_heatmap
from trading.options.payoff import PayoffLeg, payoff_summary
from trading.options.pcr import put_call_ratio


def _is_call(opt_type: str) -> bool:
    t = opt_type.lower()
    if t in ("c", "ce", "call"):
        return True
    if t in ("p", "pe", "put"):
        return False
    raise ValueError(f"opt_type must be CE/PE/call/put, got {opt_type!r}")


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    opt_type: str                 # CE/PE/call/put
    expiry: str = ""
    oi: float = 0.0
    volume: float = 0.0
    ltp: float = 0.0              # last traded premium
    iv: float | None = None      # if absent, solved from ltp

    @property
    def is_call(self) -> bool:
        return _is_call(self.opt_type)

    @property
    def flag(self) -> str:
        return "c" if self.is_call else "p"


@dataclass(frozen=True)
class OptionLeg:
    """A position the trader holds in the chain (for payoff building)."""
    strike: float
    opt_type: str
    position: str                 # long | short
    qty: float = 1.0


class OptionsChain:
    """One-expiry options chain + every T4 analytic on top of it."""

    def __init__(self, quotes: list[OptionQuote], *, forward: float, t: float,
                 r: float = 0.065, spot: float | None = None, lot_size: int = 1):
        if forward <= 0:
            raise ValueError("forward must be > 0")
        self.quotes = list(quotes)
        self.F = forward
        self.t = t
        self.r = r
        self.spot = spot if spot is not None else forward
        self.lot_size = lot_size
        self._calls = {q.strike: q for q in self.quotes if q.is_call}
        self._puts = {q.strike: q for q in self.quotes if not q.is_call}

    # ── per-strike maps ─────────────────────────────────────────────────────────
    def call_oi(self) -> dict[float, float]:
        return {k: q.oi for k, q in self._calls.items()}

    def put_oi(self) -> dict[float, float]:
        return {k: q.oi for k, q in self._puts.items()}

    def call_volume(self) -> dict[float, float]:
        return {k: q.volume for k, q in self._calls.items()}

    def put_volume(self) -> dict[float, float]:
        return {k: q.volume for k, q in self._puts.items()}

    # ── IV + Greeks ─────────────────────────────────────────────────────────────
    def iv_of(self, quote: OptionQuote) -> float | None:
        if quote.iv is not None:
            return quote.iv
        if quote.ltp <= 0:
            return None
        return implied_vol(quote.ltp, quote.flag, self.F, quote.strike, self.t, self.r)

    def greeks_of(self, quote: OptionQuote, *, backend: str = "analytic") -> dict | None:
        sigma = self.iv_of(quote)
        if sigma is None or sigma <= 0:
            return None
        g = get_all_greeks(quote.flag, self.F, quote.strike, self.t, self.r, sigma,
                           backend=backend)
        g.update(strike=quote.strike, opt_type=quote.opt_type, iv=sigma)
        return g

    def atm_strike(self) -> float | None:
        strikes = sorted(set(self._calls) | set(self._puts))
        return min(strikes, key=lambda k: abs(k - self.F)) if strikes else None

    def atm_iv(self) -> float | None:
        k = self.atm_strike()
        if k is None:
            return None
        for q in (self._calls.get(k), self._puts.get(k)):
            if q is not None:
                iv = self.iv_of(q)
                if iv:
                    return iv
        return None

    # ── analytics ───────────────────────────────────────────────────────────────
    def max_pain(self) -> dict:
        return max_pain(self.call_oi(), self.put_oi())

    def pcr(self) -> dict:
        return put_call_ratio(self.call_oi(), self.put_oi(),
                              call_volume=self.call_volume(), put_volume=self.put_volume())

    def oi_heatmap(self, *, top_n: int = 3) -> dict:
        return oi_heatmap(self.call_oi(), self.put_oi(), top_n=top_n)

    def gex(self) -> dict:
        """GEX needs per-strike gamma; gamma is strike-symmetric so compute once/strike."""
        rows = []
        co, po = self.call_oi(), self.put_oi()
        for k in sorted(set(self._calls) | set(self._puts)):
            ref = self._calls.get(k) or self._puts.get(k)
            g = self.greeks_of(ref) if ref else None
            rows.append({"strike": k, "gamma": (g or {}).get("gamma", 0.0),
                         "call_oi": co.get(k, 0.0), "put_oi": po.get(k, 0.0)})
        return gamma_exposure(rows, spot=self.spot, contract_size=self.lot_size)

    def payoff(self, legs: list[OptionLeg], **kw) -> dict:
        payoff_legs = []
        for leg in legs:
            q = (self._calls if _is_call(leg.opt_type) else self._puts).get(leg.strike)
            premium = q.ltp if q is not None else 0.0
            payoff_legs.append(PayoffLeg(
                kind="call" if _is_call(leg.opt_type) else "put",
                position=leg.position, strike=leg.strike, premium=premium,
                qty=leg.qty, lot_size=self.lot_size,
            ))
        return payoff_summary(payoff_legs, **kw)

    # ── honest status for the dashboard ─────────────────────────────────────────
    def status(self) -> dict:
        return {
            "forward": self.F, "spot": self.spot, "t_years": self.t, "r": self.r,
            "n_strikes": len(set(self._calls) | set(self._puts)),
            "atm_strike": self.atm_strike(), "atm_iv": self.atm_iv(),
            "max_pain": self.max_pain()["max_pain_strike"],
            "pcr_oi": self.pcr()["pcr_oi"],
            "gex": {k: self.gex()[k] for k in ("total_gex", "regime", "zero_gamma",
                                               "call_wall", "put_wall")},
            "oi_walls": {"call": self.oi_heatmap()["call_walls"],
                         "put": self.oi_heatmap()["put_walls"]},
        }
