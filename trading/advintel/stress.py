"""trading/advintel/stress.py — Phase-T8: portfolio stress testing & scenario analysis.

Given a portfolio of OPEN positions (NSE equity, crypto perps, commodities, …),
estimate the mark-to-market P&L impact under adverse market scenarios — both a
library of historical/synthetic crises and ad-hoc "what if X drops Y%" shocks.

Honest-wiring: this is a *first-order* shock model (delta-1, beta-adjusted).
We apply an asset-class price shock to each position's notional, respecting
direction (a SHORT profits when the market falls). A volatility multiplier is
carried through for the dashboard but does not change linear P&L (it would matter
for an options book — left as a documented hook, not a fake number).

Pure CPU, deterministic, offline. numpy/pandas only; no network, no new deps.

Public API
----------
    Position(symbol, asset_class, direction, quantity, entry_price, beta=1.0, mark_price=None)
    SCENARIOS                         # dict: name -> Scenario
    list_scenarios()                  # -> list[str]
    stress_test(positions, scenario, *, beta=None)      # -> dict
    scenario_analysis(positions, scenarios=None)        # -> dict
    what_if(positions, asset_class_shocks)              # -> dict
    StressTester(...).report(positions)                # -> JSON-able dict
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Iterable, Mapping, Optional, Sequence, Union

import numpy as np  # noqa: F401  (kept for deterministic numeric ops / future vectorisation)

# --------------------------------------------------------------------------- #
# Asset classes & directions
# --------------------------------------------------------------------------- #

_KNOWN_ASSET_CLASSES = ("equity", "crypto", "commodity")
_DEFAULT_ASSET_CLASS = "equity"


def _norm_asset_class(ac: Optional[str]) -> str:
    """Normalise an asset-class string; unknown -> equity (documented default)."""
    if not ac:
        return _DEFAULT_ASSET_CLASS
    a = str(ac).strip().lower()
    aliases = {
        "stock": "equity", "stocks": "equity", "eq": "equity", "nse": "equity",
        "index": "equity", "futures": "equity", "fno": "equity", "option": "equity",
        "crypto": "crypto", "coin": "crypto", "perp": "crypto", "spot": "crypto",
        "btc": "crypto", "eth": "crypto", "future_crypto": "crypto",
        "commodity": "commodity", "comm": "commodity", "mcx": "commodity",
        "gold": "commodity", "metal": "commodity", "energy": "commodity",
    }
    if a in _KNOWN_ASSET_CLASSES:
        return a
    return aliases.get(a, _DEFAULT_ASSET_CLASS)


def _dir_sign(direction: Optional[str]) -> int:
    """LONG -> +1, SHORT -> -1. Unknown defaults to LONG."""
    d = str(direction or "LONG").strip().upper()
    return -1 if d in ("SHORT", "SELL", "S", "-1") else +1


# --------------------------------------------------------------------------- #
# Position
# --------------------------------------------------------------------------- #

@dataclass
class Position:
    """One open position. ``mark_price`` defaults to ``entry_price`` if not given."""
    symbol: str
    asset_class: str = _DEFAULT_ASSET_CLASS
    direction: str = "LONG"          # LONG | SHORT
    quantity: float = 0.0
    entry_price: float = 0.0
    beta: float = 1.0                # sensitivity vs its asset-class shock (1.0 = market)
    mark_price: Optional[float] = None

    @property
    def price(self) -> float:
        return float(self.mark_price if self.mark_price is not None else self.entry_price)

    @property
    def signed_qty(self) -> float:
        return _dir_sign(self.direction) * abs(float(self.quantity))

    @property
    def notional(self) -> float:
        """Absolute exposure = |qty| * price (always positive)."""
        return abs(float(self.quantity)) * self.price

    @classmethod
    def coerce(cls, p: Union["Position", Mapping]) -> "Position":
        """Accept either a Position or a plain dict."""
        if isinstance(p, Position):
            return p
        if isinstance(p, Mapping):
            return cls(
                symbol=str(p.get("symbol", "")),
                asset_class=_norm_asset_class(p.get("asset_class")),
                direction=str(p.get("direction", "LONG")),
                quantity=float(p.get("quantity", p.get("qty", 0)) or 0),
                entry_price=float(p.get("entry_price", p.get("avg_price", 0)) or 0),
                beta=float(p.get("beta", 1.0) or 1.0),
                mark_price=(None if p.get("mark_price") in (None, "")
                            else float(p["mark_price"])),
            )
        raise TypeError(f"cannot coerce {type(p)!r} into a Position")


def _coerce_all(positions: Optional[Iterable]) -> list[Position]:
    if not positions:
        return []
    return [Position.coerce(p) for p in positions]


# --------------------------------------------------------------------------- #
# Scenario library
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Scenario:
    """A market scenario = per-asset-class price shocks + a vol multiplier.

    ``shocks`` values are fractional returns, e.g. -0.35 == "down 35%".
    ``vol_mult`` is informational (carried to the report); 3.0 == "vol +200%".
    """
    name: str
    description: str
    shocks: Mapping[str, float]      # asset_class -> fractional return
    vol_mult: float = 1.0

    def shock_for(self, asset_class: str) -> float:
        ac = _norm_asset_class(asset_class)
        if ac in self.shocks:
            return float(self.shocks[ac])
        # fall back to equity shock, then to 0
        return float(self.shocks.get("equity", 0.0))


SCENARIOS: dict[str, Scenario] = {
    "covid_2020": Scenario(
        "covid_2020", "COVID-19 crash (Feb–Mar 2020)",
        {"equity": -0.35, "crypto": -0.50, "commodity": -0.30}, vol_mult=3.0,
    ),
    "gfc_2008": Scenario(
        "gfc_2008", "Global Financial Crisis (2008)",
        {"equity": -0.50, "crypto": -0.60, "commodity": -0.45}, vol_mult=3.5,
    ),
    "taper_2013": Scenario(
        "taper_2013", "Taper tantrum (2013)",
        {"equity": -0.08, "crypto": -0.20, "commodity": -0.10}, vol_mult=1.5,
    ),
    "flash_crash": Scenario(
        "flash_crash", "Intraday flash crash (May 2010 style)",
        {"equity": -0.10, "crypto": -0.15, "commodity": -0.08}, vol_mult=4.0,
    ),
    "crypto_winter": Scenario(
        "crypto_winter", "Crypto winter (2022-style draw-down)",
        {"equity": -0.15, "crypto": -0.70, "commodity": -0.05}, vol_mult=2.5,
    ),
    "rate_shock_2022": Scenario(
        "rate_shock_2022", "Aggressive rate-hike repricing (2022)",
        {"equity": -0.20, "crypto": -0.55, "commodity": +0.10}, vol_mult=2.0,
    ),
}


def list_scenarios() -> list[str]:
    """Names of all built-in scenarios."""
    return list(SCENARIOS.keys())


def custom_scenario(name: str, shocks: Mapping[str, float], *,
                    description: str = "", vol_mult: float = 1.0) -> Scenario:
    """Build a parametric ad-hoc scenario, e.g. custom_scenario('nifty_-5', {'equity': -0.05})."""
    norm = {_norm_asset_class(k): float(v) for k, v in (shocks or {}).items()}
    return Scenario(name or "custom", description or f"custom {norm}", norm, float(vol_mult))


def _resolve_scenario(scenario: Union[str, Scenario, Mapping]) -> Scenario:
    if isinstance(scenario, Scenario):
        return scenario
    if isinstance(scenario, str):
        if scenario not in SCENARIOS:
            raise KeyError(f"unknown scenario {scenario!r}; known: {list_scenarios()}")
        return SCENARIOS[scenario]
    if isinstance(scenario, Mapping):
        # treat as a raw shocks dict
        return custom_scenario("custom", scenario)
    raise TypeError(f"cannot resolve scenario from {type(scenario)!r}")


# --------------------------------------------------------------------------- #
# Core P&L impact
# --------------------------------------------------------------------------- #

def _position_impact(p: Position, shock: float, *,
                     beta_override: Optional[float] = None) -> dict:
    """First-order P&L of one position under a fractional ``shock``.

    pnl = signed_qty * price * shock * beta
    A SHORT (signed_qty < 0) profits when shock < 0, exactly as desired.
    """
    beta = float(beta_override) if beta_override is not None else float(p.beta or 1.0)
    eff_shock = shock * beta
    pnl = p.signed_qty * p.price * eff_shock
    return {
        "symbol": p.symbol,
        "asset_class": _norm_asset_class(p.asset_class),
        "direction": "SHORT" if p.signed_qty < 0 else "LONG",
        "quantity": abs(float(p.quantity)),
        "price": round(p.price, 8),
        "notional": round(p.notional, 4),
        "beta": round(beta, 4),
        "shock": round(shock, 6),
        "effective_shock": round(eff_shock, 6),
        "pnl_impact": round(float(pnl), 4),
    }


def _capital(positions: Sequence[Position]) -> float:
    """Gross notional used as the capital base for pct figures."""
    return float(sum(p.notional for p in positions))


def stress_test(positions: Optional[Iterable], scenario, *,
                beta: Optional[Mapping[str, float]] = None) -> dict:
    """Per-position and total P&L impact under ``scenario``.

    ``scenario`` may be a name (str), a Scenario, or a raw shocks dict.
    ``beta`` (optional) maps symbol -> beta to override each position's own beta.
    """
    pos = _coerce_all(positions)
    sc = _resolve_scenario(scenario)
    beta = beta or {}

    rows = []
    for p in pos:
        shock = sc.shock_for(p.asset_class)
        b_over = beta.get(p.symbol) if p.symbol in beta else None
        rows.append(_position_impact(p, shock, beta_override=b_over))

    total = float(sum(r["pnl_impact"] for r in rows))
    cap = _capital(pos)
    worst = min(rows, key=lambda r: r["pnl_impact"]) if rows else None

    return {
        "scenario": sc.name,
        "description": sc.description,
        "vol_mult": sc.vol_mult,
        "shocks": dict(sc.shocks),
        "positions": rows,
        "total_pnl_impact": round(total, 4),
        "capital_base": round(cap, 4),
        "pct_of_capital": round(100.0 * total / cap, 4) if cap else 0.0,
        "worst_position": worst,
        "n_positions": len(rows),
    }


def scenario_analysis(positions: Optional[Iterable],
                      scenarios: Optional[Sequence] = None) -> dict:
    """Run a set of scenarios and summarise each. Defaults to the full library."""
    pos = _coerce_all(positions)
    names = scenarios if scenarios else list_scenarios()

    out: dict[str, dict] = {}
    for name in names:
        res = stress_test(pos, name)
        out[res["scenario"]] = {
            "total_pnl_impact": res["total_pnl_impact"],
            "pct_of_capital": res["pct_of_capital"],
            "vol_mult": res["vol_mult"],
            "worst_position": (res["worst_position"]["symbol"]
                               if res["worst_position"] else None),
            "worst_position_pnl": (res["worst_position"]["pnl_impact"]
                                   if res["worst_position"] else 0.0),
        }
    return out


def what_if(positions: Optional[Iterable],
            asset_class_shocks: Mapping[str, float]) -> dict:
    """Ad-hoc shock, e.g. what_if(pos, {'equity': -0.05}) == 'Nifty drops 5% now'."""
    sc = custom_scenario("what_if", asset_class_shocks or {})
    res = stress_test(positions, sc)
    res["label"] = "what_if"
    return res


# --------------------------------------------------------------------------- #
# StressTester wrapper
# --------------------------------------------------------------------------- #

@dataclass
class StressTester:
    """Stateful wrapper for the dashboard. Holds an optional scenario subset/betas."""
    scenarios: Optional[Sequence[str]] = None
    betas: Mapping[str, float] = field(default_factory=dict)

    def run(self, positions, scenario, *, beta=None):
        return stress_test(positions, scenario, beta=(beta or self.betas))

    def analyze(self, positions):
        return scenario_analysis(positions, self.scenarios)

    def what_if(self, positions, asset_class_shocks):
        return what_if(positions, asset_class_shocks)

    def report(self, positions) -> dict:
        """Full JSON-able stress report for the dashboard."""
        pos = _coerce_all(positions)
        analysis = scenario_analysis(pos, self.scenarios)

        worst_scenario = None
        if analysis:
            worst_scenario = min(analysis.items(),
                                 key=lambda kv: kv[1]["total_pnl_impact"])[0]

        return {
            "n_positions": len(pos),
            "capital_base": round(_capital(pos), 4),
            "scenarios_tested": list(analysis.keys()),
            "analysis": analysis,
            "worst_scenario": worst_scenario,
            "exposure_by_asset_class": _exposure_by_class(pos),
            "generated_offline": True,
        }


def _exposure_by_class(positions: Sequence[Position]) -> dict:
    agg: dict[str, dict] = {}
    for p in positions:
        ac = _norm_asset_class(p.asset_class)
        d = agg.setdefault(ac, {"gross_notional": 0.0, "net_notional": 0.0, "n": 0})
        d["gross_notional"] += p.notional
        d["net_notional"] += p.signed_qty * p.price
        d["n"] += 1
    for d in agg.values():
        d["gross_notional"] = round(d["gross_notional"], 4)
        d["net_notional"] = round(d["net_notional"], 4)
    return agg


__all__ = [
    "Position", "Scenario", "SCENARIOS", "list_scenarios", "custom_scenario",
    "stress_test", "scenario_analysis", "what_if", "StressTester",
]


if __name__ == "__main__":  # pragma: no cover
    demo = [
        Position("RELIANCE", "equity", "LONG", 100, 2900.0, beta=1.1),
        Position("BTCUSDT", "crypto", "SHORT", 2, 60000.0, beta=1.0),
    ]
    print(json.dumps(StressTester().report(demo), indent=2))
