"""trading/broker_sense/binance_options.py — Binance options IV/skew regime gauge (P4).

Only BTC/ETH/major coins have options, so this is NOT a per-altcoin signal — it's a MARKET-REGIME
read (crypto's "VIX"): implied volatility level + put/call skew = the market's priced fear/greed.
Binance computes the greeks and IV and serves them FREE via the options endpoint (eapi/v1/mark);
we read them (no Black-Scholes on our side) and summarise:

  • ATM IV      — implied vol of the near-the-money (|delta|≈0.5), nearest-expiry options. High = fear.
  • 25Δ skew    — IV(25Δ put) − IV(25Δ call). Positive = downside hedges bid up = risk-off.
  • risk_off    — a compact [-1,1] regime lean: +1 = risk-off (high IV + put skew), -1 = risk-on.

regime() returns BTC + ETH summaries + a combined gauge the brain uses as global context (size
down / bias defensive in risk-off). TTL-cached (~120s). Public data, no keys. Kill: BINANCE_OPTIONS=0.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

_MARK_URL = "https://eapi.binance.com/eapi/v1/mark"
_TTL = float(os.getenv("BINANCE_OPTIONS_TTL", "120") or 120)
_cache: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("BINANCE_OPTIONS", "1").strip().lower() not in ("0", "false", "off")


def _get_json(url: str):
    """GET+parse; isolated for test monkeypatch. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


_DEPTH_URL = "https://eapi.binance.com/eapi/v1/depth"


def option_book(binance_symbol: str) -> tuple[float, float] | None:
    """(best_bid, best_ask) for a Binance option contract from eapi depth. `binance_symbol` is the
    NATIVE format 'AVAX-260714-6.5-P' (not ccxt). None on failure/empty. This is the liquidity
    guard's correct book source — the guard used ccxt.deribit(), which returns an EMPTY book for
    Binance symbols (bid=0), so EVERY Binance option read as hollow_book and never opened (bug fix
    2026-07-13). limit=10 (Binance eapi rejects other small limits with HTTP 400)."""
    d = _get_json(f"{_DEPTH_URL}?symbol={binance_symbol}&limit=10")
    if not isinstance(d, dict):
        return None
    try:
        bids = d.get("bids") or []
        asks = d.get("asks") or []
        bid = float(bids[0][0]) if bids else 0.0
        ask = float(asks[0][0]) if asks else 0.0
        return (bid, ask)
    except (TypeError, ValueError, IndexError):
        return None


def _mark():
    now = time.time()
    with _lock:
        hit = _cache.get("mark")
        if hit and now - hit[0] <= _TTL:
            return hit[1]
    d = _get_json(_MARK_URL)
    if isinstance(d, list) and d:
        with _lock:
            _cache["mark"] = (now, d)
        return d
    with _lock:
        hit = _cache.get("mark")
        return hit[1] if hit else []


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse(sym: str):
    """'BTC-260925-145000-C' → (underlying, expiry_str, strike, 'C'/'P'). None on malformed."""
    parts = str(sym).split("-")
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3].upper()


def iv_summary(underlying: str = "BTC") -> dict:
    """ATM IV + 25Δ skew for `underlying` from the nearest expiry. All values are Binance-computed."""
    out = {"underlying": underlying, "atm_iv": None, "skew_25d": None,
           "n_contracts": 0, "expiry": None, "risk_off": None}
    if not enabled():
        return out
    rows = []
    for m in _mark():
        p = _parse(m.get("symbol", ""))
        if not p or p[0] != underlying:
            continue
        iv = _f(m.get("markIV"))
        delta = _f(m.get("delta"))
        if iv is None or delta is None:
            continue
        rows.append({"expiry": p[1], "type": p[3], "iv": iv, "delta": delta})
    out["n_contracts"] = len(rows)
    if not rows:
        return out
    expiry = min(r["expiry"] for r in rows)              # nearest expiry (YYMMDD sorts chronologically)
    near = [r for r in rows if r["expiry"] == expiry]
    out["expiry"] = expiry
    # ATM = |delta| nearest 0.5 among calls & puts
    atm = sorted(near, key=lambda r: abs(abs(r["delta"]) - 0.5))[:4]
    if atm:
        out["atm_iv"] = round(sum(r["iv"] for r in atm) / len(atm), 4)
    # 25Δ skew: put with delta≈-0.25 vs call with delta≈+0.25
    calls = [r for r in near if r["type"] == "C" and r["delta"] > 0]
    puts = [r for r in near if r["type"] == "P" and r["delta"] < 0]
    if calls and puts:
        c25 = min(calls, key=lambda r: abs(r["delta"] - 0.25))
        p25 = min(puts, key=lambda r: abs(r["delta"] + 0.25))
        out["skew_25d"] = round(p25["iv"] - c25["iv"], 4)
    # compact regime lean: elevated IV (>0.6 ann) and positive put skew → risk-off
    if out["atm_iv"] is not None:
        iv_term = max(-1.0, min(1.0, (out["atm_iv"] - 0.55) / 0.35))     # ~0.55 neutral, 0.90 → +1
        skew_term = 0.0 if out["skew_25d"] is None else max(-1.0, min(1.0, out["skew_25d"] / 0.10))
        out["risk_off"] = round(max(-1.0, min(1.0, 0.6 * iv_term + 0.4 * skew_term)), 4)
    return out


def regime() -> dict:
    """Market-wide options regime: BTC + ETH IV/skew + a combined risk-off gauge in [-1,1]."""
    if not enabled():
        return {"available": False}
    btc = iv_summary("BTC")
    eth = iv_summary("ETH")
    gauges = [x["risk_off"] for x in (btc, eth) if x.get("risk_off") is not None]
    combined = round(sum(gauges) / len(gauges), 4) if gauges else None
    label = None
    if combined is not None:
        label = "risk-off" if combined > 0.33 else "risk-on" if combined < -0.33 else "neutral"
    return {"available": bool(gauges), "btc": btc, "eth": eth,
            "risk_off": combined, "label": label, "ts": time.time()}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
