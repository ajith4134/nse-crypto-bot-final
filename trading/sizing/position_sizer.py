"""Per-trade position sizer -- turns an edge/stop/prob into qty & notional.

The live execution loop calls :class:`PositionSizer.size(...)` once per
candidate trade and receives a dict describing how much capital to deploy.

Methods (selectable via ``method=`` or auto-picked):

* ``atr_risk``   -- risk ``max_risk_pct`` of capital; qty = risk / per-unit-risk
                    where per-unit-risk = ATR (or ``|entry - stop|``). Robust
                    default: bounds the worst-case loss regardless of edge.
* ``kelly``      -- ``keeks`` (Fractional/Drawdown) Kelly from
                    ``{win_rate, payoff}`` -> fraction-of-capital -> notional.
* ``vol_target`` -- size so the position's volatility ~= a target volatility:
                    qty = capital * target_vol / (price * volatility).
* ``ai_meta``    -- AFML Ch.10 bet sizing from a calibrated ``prob`` (signed by
                    side) -> fraction -> notional. The "AI feature".
* ``auto``       -- picks the best method for whichever inputs are present,
                    applies fractional-Kelly shrink, a max-drawdown-aware
                    reduction, and the ``max_position_pct`` hard cap.

Everything is deterministic and offline. ``keeks`` is reused when present;
if it is missing every path degrades to an equivalent numpy/scipy formula so
the module never crashes (mirrors ``portfolio_risk.py``).

SIGN CONVENTION
---------------
``side='LONG'`` -> positive qty/fraction; ``side='SHORT'`` -> negative qty and
negative ``fraction`` (the capital magnitudes ``notional`` / ``capital_used``
/ ``risk_amount`` are always reported as positive >= 0).
"""
from __future__ import annotations

import math
from typing import Optional

from scipy.stats import norm

# ---- reuse-first: keeks per-trade Kelly classes ------------------------- #
try:  # keeks 0.3.0 (MIT) -- KellyCriterion etc. return a *fraction* of capital
    from keeks.binary_strategies.kelly import (
        DrawdownAdjustedKelly,
        FractionalKellyCriterion,
        KellyCriterion,
    )
    _HAS_KEEKS = True
except Exception:  # pragma: no cover - degrade to numpy formula
    KellyCriterion = FractionalKellyCriterion = DrawdownAdjustedKelly = None  # type: ignore
    _HAS_KEEKS = False


_VALID_METHODS = {"atr_risk", "kelly", "vol_target", "ai_meta", "auto"}


def _side_sign(side: str) -> int:
    """+1 for LONG / BUY, -1 for SHORT / SELL."""
    s = (side or "LONG").strip().upper()
    if s in ("SHORT", "SELL", "S", "-1"):
        return -1
    return +1


# --------------------------------------------------------------------------- #
# AFML Ch.10 -- bet sizing from predicted probabilities (the "AI feature")
# --------------------------------------------------------------------------- #
def afml_bet_size(prob: float, side: str = "LONG", num_classes: int = 2) -> float:
    """Signed bet size in ``[-1, 1]`` from a calibrated win-probability.

    Lopez de Prado, *Advances in Financial Machine Learning*, Ch.10 -- "bet
    sizing from predicted probabilities". For a probability ``p`` that the
    predicted side wins, with ``num_classes`` outcomes, the test statistic is::

        z = (p - 1/num_classes) / sqrt(p * (1 - p))

    mapped to a size via the standard-normal CDF::

        m = 2 * norm.cdf(z) - 1      # in (-1, 1), == 0 at p = 1/num_classes

    The result is multiplied by the side sign so a SHORT returns a negative
    bet. At ``p = 0.5`` (binary) the size is ~0; as ``p -> 1`` it -> +-1.

    We implement this directly because mlfinlab/mlfinpy do not install here
    (numba build fails); this is the ~10-line equivalent of
    ``bet_sizing.bet_size_probability``.
    """
    sign = _side_sign(side)
    p = float(prob)
    # Numerical guards: clip away from the degenerate 0/1 where variance -> 0.
    eps = 1e-12
    p = min(max(p, eps), 1.0 - eps)
    threshold = 1.0 / float(num_classes)
    denom = math.sqrt(p * (1.0 - p))
    if denom <= 0.0:  # pragma: no cover - guarded by eps clip above
        z = 0.0
    else:
        z = (p - threshold) / denom
    m = 2.0 * norm.cdf(z) - 1.0
    m = max(-1.0, min(1.0, m))
    return sign * m


class PositionSizer:
    """Capital sizing engine. One instance per strategy/account; stateless per
    call except for an optional rolling-drawdown awareness fed via
    :meth:`update_drawdown`.
    """

    def __init__(
        self,
        *,
        method: str = "kelly_atr",
        max_risk_pct: float = 1.0,
        kelly_fraction: float = 0.5,
        max_position_pct: float = 25.0,
        max_drawdown_pct: float = 20.0,
    ) -> None:
        # ``kelly_atr`` is an alias for the smart auto blend (the live default).
        if method in ("kelly_atr", "blend", "default"):
            method = "auto"
        if method not in _VALID_METHODS:
            raise ValueError(
                f"unknown method {method!r}; choose from "
                f"{sorted(_VALID_METHODS | {'kelly_atr'})}"
            )
        self.method = method
        self.max_risk_pct = float(max_risk_pct)
        self.kelly_fraction = float(kelly_fraction)
        self.max_position_pct = float(max_position_pct)
        self.max_drawdown_pct = float(max_drawdown_pct)
        # rolling drawdown (positive fraction, e.g. 0.12 == 12% below peak)
        self._current_drawdown = 0.0
        self._calls = 0

    # ----------------------------------------------------------- bookkeeping
    def update_drawdown(self, drawdown_pct: float) -> None:
        """Inform the sizer of the current rolling drawdown (%, >= 0).

        Used by the ``auto`` blend to linearly de-risk as drawdown approaches
        ``max_drawdown_pct`` (size hits 0 at the limit).
        """
        self._current_drawdown = max(0.0, float(drawdown_pct))

    def _drawdown_factor(self) -> float:
        """Linear de-risk multiplier in ``[0, 1]`` from the rolling drawdown."""
        if self.max_drawdown_pct <= 0:
            return 1.0
        frac = self._current_drawdown / self.max_drawdown_pct
        return max(0.0, min(1.0, 1.0 - frac))

    # --------------------------------------------------------------- helpers
    def _cap_fraction(self, fraction: float) -> float:
        """Clip an *absolute* fraction to the per-position hard cap."""
        cap = self.max_position_pct / 100.0
        return max(0.0, min(cap, fraction))

    @staticmethod
    def _payoff_to_keeks(win_rate: float, payoff: float):
        """Map ``(win_rate, payoff)`` to keeks (payoff, loss) where loss=1."""
        return float(payoff), 1.0

    # ------------------------------------------------------------ core sizing
    def _kelly_fraction(self, win_rate: float, payoff: float) -> float:
        """Raw (unsigned) Kelly fraction, shrunk by ``self.kelly_fraction``.

        Reuses ``keeks.FractionalKellyCriterion`` when available; otherwise
        the closed-form ``f* = p - q/b`` (Kelly for win/loss bets).
        """
        p = float(win_rate)
        b = float(payoff)
        if _HAS_KEEKS:
            try:
                strat = FractionalKellyCriterion(
                    payoff=b, loss=1.0, transaction_cost=0.0,
                    fraction=self.kelly_fraction,
                )
                f = strat.evaluate(p, 1.0)  # returns a fraction; bankroll ignored
                return max(0.0, float(f))
            except Exception:  # pragma: no cover - degrade to formula
                pass
        f_star = p - (1.0 - p) / b if b > 0 else 0.0
        return max(0.0, f_star * self.kelly_fraction)

    # ----------------------------------------------------------------- size()
    def size(
        self,
        *,
        capital: float,
        entry_price: float,
        stop_price: Optional[float] = None,
        atr: Optional[float] = None,
        win_rate: Optional[float] = None,
        payoff: Optional[float] = None,
        prob: Optional[float] = None,
        side: str = "LONG",
        volatility: Optional[float] = None,
        market: str = "CRYPTO",
    ) -> dict:
        """Return a sizing decision dict.

        Keys: ``qty`` (signed; +long/-short), ``notional`` (>=0),
        ``capital_used`` (>=0), ``risk_amount`` (>=0, est. loss if stop hit),
        ``method`` (resolved), ``fraction`` (signed fraction-of-capital), and
        ``reason`` (human-readable).
        """
        self._calls += 1
        capital = float(capital)
        entry_price = float(entry_price)
        sign = _side_sign(side)

        if capital <= 0 or entry_price <= 0:
            return self._empty(
                "non-positive capital/price", side,
                method=self.method if self.method != "auto" else "auto",
            )

        method = self._resolve_method(
            stop_price=stop_price, atr=atr, win_rate=win_rate,
            payoff=payoff, prob=prob, volatility=volatility,
        )

        # --- per-unit stop distance (used by atr_risk & risk_amount) ---
        per_unit_risk = self._per_unit_risk(entry_price, stop_price, atr)

        if method == "atr_risk":
            fraction_abs, reason = self._size_atr(capital, per_unit_risk, entry_price)
        elif method == "kelly":
            fraction_abs, reason = self._size_kelly(win_rate, payoff)
        elif method == "vol_target":
            fraction_abs, reason = self._size_vol_target(volatility)
        elif method == "ai_meta":
            fraction_abs, reason = self._size_ai_meta(prob, side)
        else:  # auto blend
            fraction_abs, reason = self._size_auto(
                capital, entry_price, per_unit_risk, win_rate, payoff,
                prob, side, volatility,
            )

        # ---- universal overlays: drawdown de-risk + hard cap ----
        dd_factor = self._drawdown_factor()
        if dd_factor < 1.0:
            fraction_abs *= dd_factor
            reason += f"; dd_factor={dd_factor:.2f}"
        capped = self._cap_fraction(fraction_abs)
        if capped < fraction_abs - 1e-12:
            reason += f"; capped@{self.max_position_pct:g}%"
        fraction_abs = capped

        notional = fraction_abs * capital
        qty_abs = notional / entry_price if entry_price > 0 else 0.0
        # risk_amount = estimated loss if the stop is hit (qty * stop distance);
        # if no stop is known, fall back to the deployed notional as worst case.
        if per_unit_risk is not None and per_unit_risk > 0:
            risk_amount = qty_abs * per_unit_risk
        else:
            risk_amount = notional

        return {
            "qty": sign * qty_abs,
            "notional": notional,
            "capital_used": notional,
            "risk_amount": risk_amount,
            "method": method,
            "fraction": sign * fraction_abs,
            "side": "SHORT" if sign < 0 else "LONG",
            "market": str(market).upper(),
            "reason": reason,
        }

    # --------------------------------------------------- method resolution
    def _resolve_method(
        self, *, stop_price, atr, win_rate, payoff, prob, volatility
    ) -> str:
        if self.method != "auto":
            return self.method
        # auto stays "auto" -- the blend itself inspects inputs.
        return "auto"

    @staticmethod
    def _per_unit_risk(entry_price, stop_price, atr) -> Optional[float]:
        """Per-share stop distance: ATR if given, else |entry - stop|."""
        if atr is not None and float(atr) > 0:
            return float(atr)
        if stop_price is not None:
            d = abs(float(entry_price) - float(stop_price))
            if d > 0:
                return d
        return None

    # ------------------------------------------------------- per-method math
    def _size_atr(self, capital, per_unit_risk, entry_price):
        risk_amount = (self.max_risk_pct / 100.0) * capital
        if per_unit_risk is None or per_unit_risk <= 0:
            return 0.0, "atr_risk: no ATR/stop -> 0 (cannot bound risk)"
        qty = risk_amount / per_unit_risk
        fraction = (qty * entry_price) / capital if capital > 0 else 0.0
        return fraction, (
            f"atr_risk: risk {self.max_risk_pct:g}% (={risk_amount:.2f}) "
            f"/ per-unit {per_unit_risk:.4f}"
        )

    def _size_kelly(self, win_rate, payoff):
        if win_rate is None or payoff is None:
            return 0.0, "kelly: missing win_rate/payoff -> 0"
        f = self._kelly_fraction(win_rate, payoff)
        return f, (
            f"kelly: f*x{self.kelly_fraction:g} on p={float(win_rate):.2f}, "
            f"b={float(payoff):.2f} -> {f:.4f}"
        )

    def _size_vol_target(self, volatility, target_vol: float = 0.15):
        if volatility is None or float(volatility) <= 0:
            return 0.0, "vol_target: missing/invalid volatility -> 0"
        # fraction-of-capital such that position vol ~= target_vol.
        fraction = target_vol / float(volatility)
        return fraction, (
            f"vol_target: {target_vol:g}/{float(volatility):.4f} -> {fraction:.4f}"
        )

    def _size_ai_meta(self, prob, side):
        if prob is None:
            return 0.0, "ai_meta: missing prob -> 0"
        m = afml_bet_size(float(prob), side=side)  # signed in [-1, 1]
        # The cap maps |m|=1 to the max_position_pct exposure (AFML size is a
        # fraction of the *max* bet, scaled here to our per-position cap).
        cap = self.max_position_pct / 100.0
        fraction_abs = abs(m) * cap
        return fraction_abs, (
            f"ai_meta(AFML Ch.10): prob={float(prob):.3f} -> m={m:+.3f} "
            f"x cap {self.max_position_pct:g}%"
        )

    def _size_auto(
        self, capital, entry_price, per_unit_risk, win_rate, payoff,
        prob, side, volatility,
    ):
        """Pick the richest method available, blending edge with a stop cap.

        Priority: if we have an edge (prob or win/payoff) AND a stop, take the
        *smaller* of the edge-fraction and the atr-risk-fraction (never risk
        more than max_risk_pct to the stop). Else use whatever single signal
        is present, falling back to atr_risk, then a tiny fixed fraction.
        """
        edge_fraction = None
        edge_reason = ""
        if prob is not None:
            edge_fraction, edge_reason = self._size_ai_meta(prob, side)
        elif win_rate is not None and payoff is not None:
            edge_fraction, edge_reason = self._size_kelly(win_rate, payoff)
        elif volatility is not None and float(volatility) > 0:
            edge_fraction, edge_reason = self._size_vol_target(volatility)

        atr_fraction, atr_reason = self._size_atr(
            capital, per_unit_risk, entry_price
        )
        has_stop = per_unit_risk is not None and per_unit_risk > 0

        if edge_fraction is not None and has_stop:
            chosen = min(edge_fraction, atr_fraction)
            return chosen, (
                f"auto: min(edge={edge_fraction:.4f}, "
                f"atr={atr_fraction:.4f}) [{edge_reason}]"
            )
        if edge_fraction is not None:
            return edge_fraction, f"auto: edge-only [{edge_reason}]"
        if has_stop:
            return atr_fraction, f"auto: atr-only [{atr_reason}]"
        # nothing actionable -> minimal fixed fraction (1/10th of the cap)
        fb = self.max_position_pct / 100.0 * 0.1
        return fb, "auto: no edge/stop -> minimal fixed fraction"

    # ----------------------------------------------------------------- utils
    def _empty(self, reason: str, side: str, method: str) -> dict:
        sign = _side_sign(side)
        return {
            "qty": 0.0, "notional": 0.0, "capital_used": 0.0,
            "risk_amount": 0.0, "method": method, "fraction": 0.0,
            "side": "SHORT" if sign < 0 else "LONG", "market": "",
            "reason": reason,
        }

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        return {
            "sizer": "PositionSizer",
            "method": self.method,
            "max_risk_pct": self.max_risk_pct,
            "kelly_fraction": self.kelly_fraction,
            "max_position_pct": self.max_position_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "current_drawdown_pct": self._current_drawdown,
            "keeks": _HAS_KEEKS,
            "ai_feature": "AFML Ch.10 bet sizing from predicted probabilities",
            "calls": self._calls,
            "deterministic": True,
            "offline": True,
        }


# --------------------------------------------------------------------------- #
# Dashboard demo
# --------------------------------------------------------------------------- #
def build_demo_sizing() -> dict:
    """Deterministic worked example for the dashboard (no I/O)."""
    capital = 100_000.0
    sizer = PositionSizer(
        method="auto", max_risk_pct=1.0, kelly_fraction=0.5, max_position_pct=25.0
    )
    examples = {
        "atr_long": sizer.size(
            capital=capital, entry_price=100.0, atr=2.5, side="LONG",
            market="NSE", win_rate=0.55, payoff=1.8,
        ),
        "ai_meta_short": PositionSizer(method="ai_meta", max_position_pct=25.0).size(
            capital=capital, entry_price=50_000.0, prob=0.78, side="SHORT",
            market="CRYPTO",
        ),
        "kelly_long": PositionSizer(method="kelly", kelly_fraction=0.5).size(
            capital=capital, entry_price=2500.0, win_rate=0.6, payoff=2.0,
            side="LONG", market="NSE",
        ),
        "vol_target_long": PositionSizer(method="vol_target").size(
            capital=capital, entry_price=300.0, volatility=0.30, side="LONG",
        ),
    }
    return {"status": sizer.status(), "examples": examples}


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(build_demo_sizing(), indent=2, default=float))
