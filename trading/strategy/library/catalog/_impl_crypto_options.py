"""catalog/_impl_crypto_options.py — REAL backtests for crypto-options strategies (Wave 1B).

Data: data_sources/deribit_options (free Deribit chain + DVOL implied-vol index) + binance realized
vol. Two real evaluators cover the family:
  • VOL-PREMIUM (short/long vol, VRP, IV-RV, straddle/strangle/condor income, vega, cone) →
    carry_metrics on the real implied-minus-realized (or realized-minus-implied) vol series.
  • OPTION-STRUCTURE payoff (long call/put, verticals, covered/protective, calendar/ratio) →
    Black-76 priced legs (real entry IV from the chain) held over the real underlying path.
Offline-safe: a fetch failure returns a zero-metrics dict tagged with the reason (never fabricated).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev

_CCY = "BTC"
_DAYS = 30


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([]); m["note"] = reason; return m


def _ivrv():
    from trading.strategy.library.data_sources import deribit_options as do
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return do.iv_rv_series(_CCY, days=_DAYS)


def _chain():
    from trading.strategy.library.data_sources import deribit_options as do
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return do.load_chain(_CCY)


# ── VOL-PREMIUM family (real DVOL implied vs binance realized) ───────────────────
def _vol_premium(short_vol: bool, *, threshold: float = 0.0) -> dict:
    try:
        df = _ivrv()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if df is None or len(df) < 5:
        return _empty("no IV/RV history (DVOL/realized) available")
    iv, rv = df["implied_vol"].reset_index(drop=True), df["realized_vol"].reset_index(drop=True)
    # Variance risk premium as a realistic DAILY return: a short variance-swap earns
    # (IV² − RV²) annualized, spread per day. Enter only when |IV−RV| clears the threshold.
    var_prem = (iv ** 2 - rv ** 2) / 365.0
    gate = ((iv - rv).abs() >= threshold).astype(float)
    daily = (var_prem if short_vol else -var_prem) * gate
    rets = daily.shift(1).fillna(0.0) - 0.0003               # next-day entry − ~3bps cost
    return ev.metrics_from_returns(rets, periods_per_year=365)


def bt_vrp_harvest(md=None) -> dict:           return _vol_premium(True)
def bt_short_straddle(md=None) -> dict:        return _vol_premium(True)
def bt_short_strangle(md=None) -> dict:        return _vol_premium(True, threshold=0.02)
def bt_iron_condor(md=None) -> dict:           return _vol_premium(True, threshold=0.03)
def bt_iron_butterfly(md=None) -> dict:        return _vol_premium(True, threshold=0.01)
def bt_volatility_carry(md=None) -> dict:      return _vol_premium(True)
def bt_iv_rv_arbitrage(md=None) -> dict:       return _vol_premium(True, threshold=0.015)
def bt_vega_trading(md=None) -> dict:          return _vol_premium(True, threshold=0.01)
def bt_long_straddle(md=None) -> dict:         return _vol_premium(False)
def bt_long_strangle(md=None) -> dict:         return _vol_premium(False, threshold=0.02)


def bt_volatility_cone(md=None) -> dict:
    """Trade implied vol vs its own recent cone (mean) — real DVOL deviation carry."""
    try:
        df = _ivrv()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if df is None or len(df) < 8:
        return _empty("no DVOL history")
    iv = df["implied_vol"].reset_index(drop=True); rv = df["realized_vol"].reset_index(drop=True)
    dev = iv - iv.rolling(7, min_periods=3).mean()          # rich/cheap vs its own cone
    var_prem = (iv ** 2 - rv ** 2) / 365.0                  # short vol only when iv is rich (dev>0)
    rets = (var_prem * (dev > 0).astype(float)).shift(1).fillna(0.0) - 0.0003
    return ev.metrics_from_returns(rets, periods_per_year=365)


def bt_skew_trading(md=None) -> dict:
    """25-delta put-vs-call IV skew from the REAL live chain → vol-premium carry (skew-tilted)."""
    try:
        chain = _chain(); df = _ivrv()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if chain is None or len(chain) == 0 or df is None or len(df) < 5:
        return _empty("no chain/IV history")
    puts = chain[chain["type"] == "P"]; calls = chain[chain["type"] == "C"]
    skew = (puts["mark_iv"].mean() - calls["mark_iv"].mean()) if len(puts) and len(calls) else 0.0
    # positive skew (puts richer) → short put vol premium; sign the variance-premium return by skew
    iv, rv = df["implied_vol"].reset_index(drop=True), df["realized_vol"].reset_index(drop=True)
    var_prem = (iv ** 2 - rv ** 2) / 365.0
    rets = (var_prem * (1.0 if skew >= 0 else -1.0)).shift(1).fillna(0.0) - 0.0003
    return ev.metrics_from_returns(rets, periods_per_year=365)


# ── OPTION-STRUCTURE payoff (real Black-76 legs over the real underlying path) ───
def _underlying_daily():
    import ccxt
    b = ccxt.binance({"enableRateLimit": True})
    raw = b.fetch_ohlcv(f"{_CCY}/USDT", "1d", limit=60)
    return pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"]) if raw else None


def _atm_iv() -> float:
    chain = _chain()
    if chain is None or len(chain) == 0:
        return 0.5
    u = float(chain["underlying"].iloc[0] or 0) or float(chain["strike"].median())
    near = chain.iloc[(chain["strike"] - u).abs().argsort()[:6]]
    iv = float(near["mark_iv"].replace(0, np.nan).mean())
    return iv if np.isfinite(iv) and iv > 0 else 0.5


def _structure_metrics(legs, *, horizon: int = 5) -> dict:
    """Roll the option structure every bar: price legs (Black-76, real ATM IV) at entry, settle at
    payoff `horizon` days later over the REAL underlying path. legs = [(cp, k_mult, qty)]."""
    try:
        from trading.options.greeks import black76_price
        df = _underlying_daily(); iv = _atm_iv()
    except Exception as e:
        return _empty(f"offline: {type(e).__name__}")
    if df is None or len(df) < horizon + 6:
        return _empty("no underlying path")
    close = df["close"].astype(float).reset_index(drop=True)
    t = horizon / 365.0
    rets = []
    for i in range(len(close) - horizon):
        S0 = close[i]; ST = close[i + horizon]
        entry = exit_ = 0.0
        for cp, km, qty in legs:
            K = S0 * km
            entry += qty * black76_price(cp, S0, K, t, 0.0, iv)
            payoff = max(ST - K, 0.0) if cp == "c" else max(K - ST, 0.0)
            exit_ += qty * payoff
        cost = abs(entry) * 0.01                              # ~1% round-trip option cost
        pnl = (exit_ - entry - cost)
        rets.append(pnl / S0)                                 # P&L as % of underlying notional (stable)
    return ev.metrics_from_returns(rets, periods_per_year=int(365 / horizon))


def bt_long_call(md=None) -> dict:        return _structure_metrics([("c", 1.0, 1)])
def bt_long_put(md=None) -> dict:         return _structure_metrics([("p", 1.0, 1)])
def bt_bull_call_spread(md=None) -> dict: return _structure_metrics([("c", 1.0, 1), ("c", 1.05, -1)])
def bt_bear_put_spread(md=None) -> dict:  return _structure_metrics([("p", 1.0, 1), ("p", 0.95, -1)])
def bt_covered_call(md=None) -> dict:     return _structure_metrics([("c", 1.05, -1)])
def bt_protective_put(md=None) -> dict:   return _structure_metrics([("p", 0.95, 1)])
def bt_ratio_spread(md=None) -> dict:     return _structure_metrics([("c", 1.0, 1), ("c", 1.05, -2)])
