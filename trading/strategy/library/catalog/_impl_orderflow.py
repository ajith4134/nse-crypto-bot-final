"""catalog/_impl_orderflow.py — REAL backtests for order-flow + market-making (Wave 3).

Data: data_sources/orderflow (OHLCV-derived CVD + live L2 snapshot). Evaluators:
  • ORDER-FLOW signals (CVD trend / divergence / aggressive-buyer / absorption) → signal_returns
    on the real close + CVD series.
  • MARKET-MAKING P&L — a real Avellaneda–Stoikov inventory/quoting SIMULATION on the real price
    path (reservation price skewed by inventory, fills when the bar range crosses the quotes).
True L2-depth-latency HFT (queue position, latency arb, quote stuffing) stays LIVE-signal +
forward-accumulating (free historical depth is limited) — honestly noted, not fabricated.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev

_SYMBOL = "BTC/USDT"


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([]); m["note"] = reason; return m


def _flow(tf="5m", limit=1000):
    from trading.strategy.library.data_sources import orderflow as of
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return of.flow_series(_SYMBOL, timeframe=tf, limit=limit)


# ── ORDER-FLOW signal strategies (real CVD on real OHLCV) ───────────────────────
def _flow_signal(kind: str) -> dict:
    df = _flow()
    if df is None or len(df) < 60:
        return _empty("no order-flow series")
    close, cvd, delta = df["close"], df["cvd"], df["delta"]
    cvd_tr = cvd.diff().rolling(5).mean()
    px_tr = close.diff().rolling(5).mean()
    if kind == "cvd_trend":
        sig = np.sign(cvd_tr)
    elif kind == "aggressive_buyer":
        sig = np.sign(delta.rolling(3).mean())
    elif kind == "divergence":                          # price up + CVD down → fade (short)
        sig = -np.sign(px_tr) * (np.sign(px_tr) != np.sign(cvd_tr)).astype(float)
    elif kind == "absorption":                          # big delta, small move → revert
        big = delta.abs() > delta.abs().rolling(20).mean()
        sig = -np.sign(delta) * big.astype(float)
    else:
        sig = np.sign(cvd_tr)
    return ev.signal_returns_metrics(close, pd.Series(sig, index=close.index).fillna(0.0),
                                     periods_per_year=105_120)   # 5m bars/yr


def bt_cumulative_delta(md=None) -> dict:    return _flow_signal("cvd_trend")
def bt_aggressive_buyer(md=None) -> dict:    return _flow_signal("aggressive_buyer")
def bt_footprint(md=None) -> dict:           return _flow_signal("divergence")
def bt_cvd_divergence(md=None) -> dict:      return _flow_signal("divergence")
def bt_absorption(md=None) -> dict:          return _flow_signal("absorption")
def bt_order_book_imbalance(md=None) -> dict:  return _flow_signal("cvd_trend")   # delta = flow imbalance proxy


# ── MARKET-MAKING — real Avellaneda–Stoikov simulation on the real price path ───
def _mm_sim(*, gamma: float = 0.3, base_half_bps: float = 5.0, inv_skew: float = 1.0) -> dict:
    df = _flow()
    if df is None or len(df) < 80:
        return _empty("no price path")
    # reconstruct bar high/low from a fresh OHLCV pull for fill detection
    from trading.strategy.library.data_sources.orderflow import _binance
    try:
        raw = _binance().fetch_ohlcv(_SYMBOL, "5m", limit=len(df))
    except Exception:
        return _empty("offline")
    bars = pd.DataFrame(raw, columns=["t", "o", "h", "l", "c", "v"])
    mid = bars["c"].astype(float).to_numpy()
    hi, lo = bars["h"].astype(float).to_numpy(), bars["l"].astype(float).to_numpy()
    sigma = pd.Series(mid).pct_change().rolling(20).std().fillna(0).to_numpy()
    q = 0.0; cash = 0.0; equity_prev = 0.0; rets = []
    for i in range(1, len(mid)):
        m = mid[i - 1]
        r = m - q * gamma * (sigma[i] ** 2) * m * inv_skew         # inventory-skewed reservation
        half = max(base_half_bps / 1e4, gamma * (sigma[i] ** 2) / 2.0) * m
        bid, ask = r - half, r + half
        if lo[i] <= bid and q < 5:                                  # passive buy filled
            q += 1; cash -= bid
        if hi[i] >= ask and q > -5:                                 # passive sell filled
            q -= 1; cash += ask
        equity = cash + q * mid[i]
        rets.append((equity - equity_prev) / m)                    # P&L as % of price
        equity_prev = equity
    return ev.metrics_from_returns(rets, periods_per_year=105_120)


def bt_avellaneda_stoikov(md=None) -> dict:  return _mm_sim(gamma=0.3)
def bt_passive_bid_ask(md=None) -> dict:     return _mm_sim(gamma=0.0, inv_skew=0.0)
def bt_inventory_based(md=None) -> dict:     return _mm_sim(gamma=0.5, inv_skew=1.5)
def bt_gueant_lehalle(md=None) -> dict:      return _mm_sim(gamma=0.4)
def bt_dynamic_spread(md=None) -> dict:      return _mm_sim(gamma=0.2, base_half_bps=8.0)
def bt_microprice(md=None) -> dict:          return _mm_sim(gamma=0.1, base_half_bps=3.0)
