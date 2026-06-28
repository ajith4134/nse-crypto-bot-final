"""trading/options/greeks.py — Black-76 option Greeks (T4 §2).

Black-76 prices options on a FORWARD/FUTURES price F (not spot) — the correct model
for index/stock-futures and MCX commodity options on Indian exchanges. The analytic
formulas below are exact and need only the stdlib + (for IV) scipy's root finder.
An optional fast-vollib backend (`py_vollib_vectorized`) can be selected for a
vectorized accelerated path; results agree to numerical precision.

Conventions (trader-facing units):
  • delta : per 1.00 move in F            (call ∈ [0,1], put ∈ [-1,0])
  • gamma : per 1.00 move in F
  • vega  : per 1 VOL POINT (1% = 0.01 change in sigma)  → analytic_vega / 100
  • theta : per CALENDAR DAY                              → analytic_theta / 365
  • rho   : per 1% change in r                            → analytic_rho / 100

`flag` is "c"/"call" or "p"/"put". t is time-to-expiry in YEARS, r the risk-free
rate (annual, e.g. 0.065), sigma the annualised volatility (e.g. 0.18 = 18%).
"""
from __future__ import annotations

import math

SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _is_call(flag: str) -> bool:
    f = flag.lower()
    if f in ("c", "call"):
        return True
    if f in ("p", "put"):
        return False
    raise ValueError(f"flag must be c/call or p/put, got {flag!r}")


def _d1_d2(F: float, K: float, t: float, sigma: float) -> tuple[float, float]:
    if F <= 0 or K <= 0:
        raise ValueError("F and K must be > 0")
    vol = sigma * math.sqrt(t)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * t) / vol
    return d1, d1 - vol


def black76_price(flag: str, F: float, K: float, t: float, r: float, sigma: float) -> float:
    """Black-76 option price. Handles the t→0 / sigma→0 intrinsic limit cleanly."""
    call = _is_call(flag)
    df = math.exp(-r * t)
    if t <= 0 or sigma <= 0:
        intrinsic = max(0.0, F - K) if call else max(0.0, K - F)
        return df * intrinsic
    d1, d2 = _d1_d2(F, K, t, sigma)
    if call:
        return df * (F * _norm_cdf(d1) - K * _norm_cdf(d2))
    return df * (K * _norm_cdf(-d2) - F * _norm_cdf(-d1))


def _analytic_greeks(flag: str, F: float, K: float, t: float, r: float, sigma: float) -> dict:
    call = _is_call(flag)
    df = math.exp(-r * t)
    price = black76_price(flag, F, K, t, r, sigma)
    if t <= 0 or sigma <= 0:
        # Degenerate: delta is a step, the rest vanish.
        if call:
            delta = df if F > K else (df * 0.5 if F == K else 0.0)
        else:
            delta = -df if F < K else (-df * 0.5 if F == K else 0.0)
        return {"price": price, "delta": delta, "gamma": 0.0,
                "vega": 0.0, "theta": 0.0, "rho": -t * price / 100.0}

    d1, d2 = _d1_d2(F, K, t, sigma)
    nd1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(t)

    gamma = df * nd1 / (F * sigma * sqrt_t)
    vega = F * df * nd1 * sqrt_t                       # per 1.00 vol
    # theta_calendar = r*price - df*F*n(d1)*sigma/(2√t)   (same n-term for call/put)
    theta_year = r * price - df * F * nd1 * sigma / (2.0 * sqrt_t)
    if call:
        delta = df * _norm_cdf(d1)
    else:
        delta = -df * _norm_cdf(-d1)
    rho_year = -t * price                              # F independent of r in Black-76

    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega / 100.0,        # per 1 vol point (1%)
        "theta": theta_year / 365.0,  # per calendar day
        "rho": rho_year / 100.0,      # per 1% rate move
    }


def _vollib_greeks(flag: str, F: float, K: float, t: float, r: float, sigma: float) -> dict | None:
    """Optional accelerated backend. Returns None if fast-vollib isn't installed."""
    try:
        from py_vollib_vectorized import vectorized_black  # type: ignore
        from py_vollib_vectorized.greeks import (  # type: ignore
            delta as v_delta, gamma as v_gamma, rho as v_rho, theta as v_theta, vega as v_vega,
        )
    except Exception:
        return None
    f = "c" if _is_call(flag) else "p"
    kw = dict(flag=f, F=F, K=K, t=t, r=r, sigma=sigma, model="black", return_as="array")
    return {
        "price": float(vectorized_black(f, F, K, t, r, sigma, return_as="array")[0]),
        "delta": float(v_delta(**kw)[0]),
        "gamma": float(v_gamma(**kw)[0]),
        "vega": float(v_vega(**kw)[0]),
        "theta": float(v_theta(**kw)[0]),
        "rho": float(v_rho(**kw)[0]),
    }


def get_all_greeks(flag: str, F: float, K: float, t: float, r: float, sigma: float,
                   *, backend: str = "analytic") -> dict:
    """Price + delta/gamma/vega/theta/rho as a dict.

    backend: "analytic" (default, always available), "vollib" (require fast-vollib),
    or "auto" (use fast-vollib if importable, else analytic).
    """
    b = backend.lower()
    if b in ("vollib", "auto"):
        out = _vollib_greeks(flag, F, K, t, r, sigma)
        if out is not None:
            out["backend"] = "vollib"
            return out
        if b == "vollib":
            raise RuntimeError(
                "backend='vollib' requested but py_vollib_vectorized is not installed. "
                "Run: .venv/bin/pip install py_vollib_vectorized  (or use backend='analytic')."
            )
    out = _analytic_greeks(flag, F, K, t, r, sigma)
    out["backend"] = "analytic"
    return out


def implied_vol(price: float, flag: str, F: float, K: float, t: float, r: float,
                *, lo: float = 1e-6, hi: float = 5.0, tol: float = 1e-8) -> float | None:
    """Solve Black-76 implied volatility from a market price (Brent's method).

    Returns None when the price is outside the no-arbitrage band (below intrinsic or
    above the forward bound) so a vol simply does not exist.
    """
    call = _is_call(flag)
    df = math.exp(-r * t)
    intrinsic = df * (max(0.0, F - K) if call else max(0.0, K - F))
    upper = df * (F if call else K)
    if price <= intrinsic + 1e-12 or price >= upper - 1e-12 or t <= 0:
        # At/над bounds → 0 / undefined; only solve strictly inside.
        if abs(price - intrinsic) <= 1e-12:
            return 0.0
        return None

    f = lambda s: black76_price(flag, F, K, t, r, s) - price
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:               # not bracketed within [lo, hi]
        return None
    try:
        from scipy.optimize import brentq
        return float(brentq(f, lo, hi, xtol=tol, maxiter=200))
    except Exception:
        # Stdlib bisection fallback (no scipy).
        a, b = lo, hi
        for _ in range(200):
            mid = 0.5 * (a + b)
            fm = f(mid)
            if abs(fm) < tol:
                return mid
            if flo * fm <= 0:
                b, fhi = mid, fm
            else:
                a, flo = mid, fm
        return 0.5 * (a + b)
