"""Phase-T8: Portfolio risk & optimization (Riskfolio-Lib + PyPortfolioOpt).

REUSE-FIRST: prefers `riskfolio` (rp.Portfolio / rp.HCPortfolio) and
`pypfopt` (HRPOpt) for the heavy lifting. Every library call is wrapped in
try/except that DEGRADES to a deterministic numpy fallback, so this module
never crashes even if a lib call fails -- but the real library result is
always preferred when available.

CPU-only, deterministic, fully offline: every function operates on a pandas
DataFrame of per-asset RETURNS (columns = symbols, rows = periods). No
network access of any kind.

SIGN CONVENTION
---------------
Returns are simple period returns (e.g. 0.01 == +1%). Losses are NEGATIVE.
`var()` / `cvar()` therefore return NEGATIVE numbers for a normal loss tail
(e.g. -0.023 means "5% of periods lose 2.3% or more"). `max_drawdown()`
returns a NEGATIVE fraction (e.g. -0.18 == -18% peak-to-trough).
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd

# Optional heavy deps -- import lazily-tolerant so the module loads even if a
# library is broken/missing; calls fall back to numpy.
try:  # riskfolio-lib
    import riskfolio as rp  # type: ignore
    _HAS_RP = True
except Exception:  # pragma: no cover
    rp = None  # type: ignore
    _HAS_RP = False

try:  # PyPortfolioOpt
    from pypfopt import HRPOpt  # type: ignore
    _HAS_PYPFOPT = True
except Exception:  # pragma: no cover
    HRPOpt = None  # type: ignore
    _HAS_PYPFOPT = False


# --------------------------------------------------------------------------- #
# Input hygiene helpers
# --------------------------------------------------------------------------- #
def _as_returns_df(returns) -> pd.DataFrame:
    """Coerce input to a clean float DataFrame (drop all-NaN, fill NaN -> 0)."""
    if isinstance(returns, pd.Series):
        df = returns.to_frame()
    elif isinstance(returns, pd.DataFrame):
        df = returns.copy()
    else:
        df = pd.DataFrame(returns)
    df = df.apply(pd.to_numeric, errors="coerce")
    # Drop columns that are entirely NaN, then fill remaining NaN with 0.0.
    df = df.dropna(axis=1, how="all")
    df = df.fillna(0.0)
    return df.astype(float)


def _portfolio_series(returns: pd.DataFrame,
                      weights: Optional[Sequence[float]] = None) -> pd.Series:
    """Collapse a returns frame to a single portfolio return series."""
    if returns.shape[1] == 1:
        return returns.iloc[:, 0]
    if weights is None:
        n = returns.shape[1]
        w = np.full(n, 1.0 / n)
    else:
        w = np.asarray(weights, dtype=float)
        s = w.sum()
        if s == 0 or not np.isfinite(s):
            w = np.full(returns.shape[1], 1.0 / returns.shape[1])
        else:
            w = w / s
    return pd.Series(returns.values @ w, index=returns.index)


def _is_degenerate(df: pd.DataFrame) -> bool:
    return df is None or df.empty or df.shape[0] < 2 or df.shape[1] < 1


# --------------------------------------------------------------------------- #
# Tail risk: VaR / CVaR (historical)
# --------------------------------------------------------------------------- #
def var(returns,
        alpha: float = 0.05,
        weights: Optional[Sequence[float]] = None,
        per_asset: bool = False):
    """Historical Value-at-Risk at confidence ``1-alpha``.

    Returns a NEGATIVE number for a loss tail (loss sign convention).

    * ``per_asset=False`` (default): collapse to a portfolio series (equal-
      weight unless ``weights`` given) and return a single float.
    * ``per_asset=True``: return a dict {symbol: VaR}.
    """
    df = _as_returns_df(returns)
    if _is_degenerate(df):
        return None

    def _v(arr: np.ndarray) -> float:
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return 0.0
        return float(np.quantile(arr, alpha))

    if per_asset:
        return {c: _v(df[c].to_numpy()) for c in df.columns}
    return _v(_portfolio_series(df, weights).to_numpy())


def cvar(returns,
         alpha: float = 0.05,
         weights: Optional[Sequence[float]] = None,
         per_asset: bool = False):
    """Historical CVaR / Expected Shortfall at confidence ``1-alpha``.

    Mean of the worst ``alpha`` fraction of outcomes. NEGATIVE for losses.
    """
    df = _as_returns_df(returns)
    if _is_degenerate(df):
        return None

    def _cv(arr: np.ndarray) -> float:
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return 0.0
        thr = np.quantile(arr, alpha)
        tail = arr[arr <= thr]
        if tail.size == 0:
            return float(thr)
        return float(tail.mean())

    if per_asset:
        return {c: _cv(df[c].to_numpy()) for c in df.columns}
    return _cv(_portfolio_series(df, weights).to_numpy())


# --------------------------------------------------------------------------- #
# Kelly fraction
# --------------------------------------------------------------------------- #
def kelly_fraction(returns, cap: float = 1.0, half: bool = True) -> dict:
    """Per-asset Kelly fraction f* = mean / variance (Gaussian approx).

    Returns a dict::

        {symbol: {"kelly": f*, "half_kelly": f*/2, "capped": clip(f*, -cap, cap)}}

    ``half_kelly`` is the common risk-reduced sizing; ``capped`` clips the
    raw Kelly into ``[-cap, cap]``. ``half`` controls whether ``capped`` is
    applied to half- or full-Kelly.
    """
    df = _as_returns_df(returns)
    out: dict = {}
    if _is_degenerate(df):
        return out
    for c in df.columns:
        arr = df[c].to_numpy()
        arr = arr[np.isfinite(arr)]
        if arr.size < 2:
            out[c] = {"kelly": 0.0, "half_kelly": 0.0, "capped": 0.0}
            continue
        mu = float(arr.mean())
        var_ = float(arr.var(ddof=1))
        if var_ <= 0 or not math.isfinite(var_):
            f = 0.0
        else:
            f = mu / var_
        if not math.isfinite(f):
            f = 0.0
        hk = f / 2.0
        base = hk if half else f
        capped = float(np.clip(base, -abs(cap), abs(cap)))
        out[c] = {"kelly": f, "half_kelly": hk, "capped": capped}
    return out


# --------------------------------------------------------------------------- #
# Hierarchical Risk Parity weights
# --------------------------------------------------------------------------- #
def hrp_weights(returns) -> dict:
    """Hierarchical Risk Parity weights -> {symbol: weight} summing to 1.

    Prefers riskfolio ``rp.HCPortfolio(...).optimization(model='HRP')``;
    falls back to pypfopt ``HRPOpt``; finally to inverse-variance weights.
    """
    df = _as_returns_df(returns)
    if _is_degenerate(df):
        return {}
    if df.shape[1] == 1:
        return {df.columns[0]: 1.0}

    # 1) riskfolio HCPortfolio
    if _HAS_RP:
        try:
            port = rp.HCPortfolio(returns=df)
            w = port.optimization(
                model="HRP",
                codependence="pearson",
                rm="MV",
                rf=0.0,
                linkage="single",
                max_k=10,
                leaf_order=True,
            )
            if w is not None and not w.empty:
                ser = w.iloc[:, 0]
                return {str(k): float(v) for k, v in ser.items()}
        except Exception:
            pass

    # 2) pypfopt HRPOpt
    if _HAS_PYPFOPT:
        try:
            hrp = HRPOpt(returns=df)
            w = hrp.optimize()
            if w:
                return {str(k): float(v) for k, v in w.items()}
        except Exception:
            pass

    # 3) numpy fallback: inverse-variance weights
    variances = df.var(ddof=1).replace(0.0, np.nan)
    inv = 1.0 / variances
    inv = inv.fillna(0.0)
    total = inv.sum()
    if total <= 0:
        n = df.shape[1]
        return {str(c): 1.0 / n for c in df.columns}
    w = inv / total
    return {str(k): float(v) for k, v in w.items()}


# --------------------------------------------------------------------------- #
# Max drawdown
# --------------------------------------------------------------------------- #
def max_drawdown(equity_or_returns) -> Optional[float]:
    """Maximum peak-to-trough drawdown as a NEGATIVE fraction.

    Accepts either an equity/price curve or a return series. Heuristic: if
    every value is small (|x| < ~1.5) it's treated as returns and compounded
    into an equity curve; otherwise treated as an equity curve directly.
    """
    if isinstance(equity_or_returns, pd.DataFrame):
        if equity_or_returns.shape[1] == 1:
            arr = equity_or_returns.iloc[:, 0].to_numpy(dtype=float)
        else:
            # treat as multi-asset returns -> equal-weight portfolio returns
            arr = _portfolio_series(_as_returns_df(equity_or_returns)).to_numpy()
    else:
        arr = np.asarray(equity_or_returns, dtype=float).ravel()

    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return 0.0

    looks_like_returns = np.nanmax(np.abs(arr)) < 1.5
    equity = np.cumprod(1.0 + arr) if looks_like_returns else arr

    if np.any(equity <= 0):
        # can't form a clean ratio drawdown -> use absolute peak-to-trough
        peak = np.maximum.accumulate(equity)
        dd = equity - peak
        return float(dd.min())

    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(dd.min())


# --------------------------------------------------------------------------- #
# Portfolio heat
# --------------------------------------------------------------------------- #
def portfolio_heat(positions: Iterable[Mapping],
                   total_capital: Optional[float] = None) -> dict:
    """Percent of capital at risk across open positions.

    ``positions``: iterable of dicts with at least ``capital_at_risk`` (and
    typically ``symbol``). ``total_capital`` may be passed explicitly; if any
    position carries a ``total_capital``/``capital`` field that is used when
    the arg is omitted.

    Returns::

        {"heat": fraction, "heat_pct": percent, "at_risk": sum,
         "total_capital": cap, "per_position": {symbol: fraction}}
    """
    positions = list(positions or [])
    cap = total_capital
    per_pos = []
    at_risk = 0.0
    for p in positions:
        car = float(p.get("capital_at_risk", 0.0) or 0.0)
        at_risk += car
        per_pos.append((str(p.get("symbol", f"pos{len(per_pos)}")), car))
        if cap is None:
            c = p.get("total_capital", p.get("capital"))
            if c is not None:
                cap = float(c)

    if not cap or cap <= 0 or not math.isfinite(cap):
        return {
            "heat": 0.0, "heat_pct": 0.0, "at_risk": at_risk,
            "total_capital": cap or 0.0, "per_position": {},
        }

    return {
        "heat": at_risk / cap,
        "heat_pct": 100.0 * at_risk / cap,
        "at_risk": at_risk,
        "total_capital": cap,
        "per_position": {sym: (car / cap) for sym, car in per_pos},
    }


# --------------------------------------------------------------------------- #
# Mean-risk optimization
# --------------------------------------------------------------------------- #
def optimize(returns, objective: str = "MinRisk") -> dict:
    """Mean-risk optimal weights via riskfolio ``rp.Portfolio``.

    ``objective``:
        * ``'MinRisk'`` -> minimum-variance (rm='MV', obj='MinRisk')
        * ``'Sharpe'``  -> max risk-adjusted return (rm='MV', obj='Sharpe')
        * ``'CVaR'``    -> minimum-CVaR (rm='CVaR', obj='MinRisk')

    Returns {symbol: weight} summing to 1. Falls back to inverse-variance
    (MinRisk/CVaR) or mean/vol-tilted (Sharpe) weights if riskfolio fails.
    """
    df = _as_returns_df(returns)
    if _is_degenerate(df):
        return {}
    if df.shape[1] == 1:
        return {str(df.columns[0]): 1.0}

    obj = str(objective)
    rm = "CVaR" if obj.upper() == "CVAR" else "MV"
    rp_obj = "Sharpe" if obj.lower() == "sharpe" else "MinRisk"

    if _HAS_RP:
        try:
            port = rp.Portfolio(returns=df)
            port.assets_stats(method_mu="hist", method_cov="hist")
            w = port.optimization(
                model="Classic", rm=rm, obj=rp_obj, rf=0.0, l=0.0, hist=True,
            )
            if w is not None and not w.empty:
                ser = w.iloc[:, 0]
                total = float(ser.sum())
                if total > 0 and math.isfinite(total):
                    return {str(k): float(v) / total for k, v in ser.items()}
        except Exception:
            pass

    # numpy fallback
    if rp_obj == "Sharpe":
        mu = df.mean()
        vol = df.std(ddof=1).replace(0.0, np.nan)
        score = (mu / vol).clip(lower=0.0).fillna(0.0)
        if score.sum() <= 0:
            n = df.shape[1]
            return {str(c): 1.0 / n for c in df.columns}
        w = score / score.sum()
        return {str(k): float(v) for k, v in w.items()}

    # MinRisk / CVaR fallback: inverse-variance
    return hrp_weights(df)


# --------------------------------------------------------------------------- #
# Class API
# --------------------------------------------------------------------------- #
class PortfolioRisk:
    """Convenience wrapper over a returns DataFrame for the dashboard.

    Example
    -------
    >>> pr = PortfolioRisk(returns_df)
    >>> pr.report()          # JSON-able dict
    """

    def __init__(self,
                 returns,
                 weights: Optional[Sequence[float]] = None,
                 alpha: float = 0.05):
        self.returns = _as_returns_df(returns)
        self.weights = weights
        self.alpha = float(alpha)

    # tail risk -----------------------------------------------------------
    def var(self, per_asset: bool = False):
        return var(self.returns, self.alpha, self.weights, per_asset)

    def cvar(self, per_asset: bool = False):
        return cvar(self.returns, self.alpha, self.weights, per_asset)

    # sizing / structure --------------------------------------------------
    def kelly(self, cap: float = 1.0, half: bool = True):
        return kelly_fraction(self.returns, cap=cap, half=half)

    def hrp(self):
        return hrp_weights(self.returns)

    def optimize(self, objective: str = "MinRisk"):
        return optimize(self.returns, objective)

    def max_drawdown(self):
        if _is_degenerate(self.returns):
            return 0.0
        return max_drawdown(_portfolio_series(self.returns, self.weights))

    # scalar metrics ------------------------------------------------------
    def sharpe(self, periods_per_year: int = 252) -> Optional[float]:
        """Annualized Sharpe of the (equal-weight unless weighted) portfolio."""
        if _is_degenerate(self.returns):
            return None
        s = _portfolio_series(self.returns, self.weights).to_numpy()
        s = s[np.isfinite(s)]
        if s.size < 2:
            return None
        sd = s.std(ddof=1)
        if sd <= 0 or not math.isfinite(sd):
            return 0.0
        return float(s.mean() / sd * math.sqrt(periods_per_year))

    # dashboard payload ---------------------------------------------------
    def report(self) -> dict:
        """JSON-able summary dict for the dashboard."""
        def _safe(fn, default=None):
            try:
                return fn()
            except Exception:
                return default

        return {
            "n_assets": int(self.returns.shape[1]),
            "n_periods": int(self.returns.shape[0]),
            "alpha": self.alpha,
            "var": _safe(lambda: self.var()),
            "cvar": _safe(lambda: self.cvar()),
            "max_drawdown": _safe(lambda: self.max_drawdown(), 0.0),
            "hrp_weights": _safe(lambda: self.hrp(), {}),
            "kelly": _safe(lambda: self.kelly(), {}),
            "sharpe": _safe(lambda: self.sharpe()),
        }


__all__ = [
    "PortfolioRisk",
    "var",
    "cvar",
    "kelly_fraction",
    "hrp_weights",
    "max_drawdown",
    "portfolio_heat",
    "optimize",
]
