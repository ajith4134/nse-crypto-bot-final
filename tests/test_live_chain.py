"""tests/test_live_chain.py — real-broker option chain → T4 analytics (2026-07-10)."""
from __future__ import annotations

import datetime as dt

import pytest

from trading.options.live_chain import to_chain


def _raw(expiry_days=7, spot=24000.0, atm=24000.0):
    strikes = [atm - 200, atm, atm + 200]
    chain = []
    for k in strikes:
        chain.append({"strike": k,
                      "ce": {"ltp": max(5.0, spot - k + 120), "oi": 1000, "volume": 500,
                             "lotsize": 65},
                      "pe": {"ltp": max(5.0, k - spot + 120), "oi": 1200, "volume": 400,
                             "lotsize": 65}})
    return {"ts": 0, "underlying": "NIFTY", "expiry": "14JUL26",
            "expiry_iso": (dt.date.today() + dt.timedelta(days=expiry_days)).isoformat(),
            "spot": spot, "atm_strike": atm, "chain": chain}


def test_to_chain_builds_real_analytics():
    ch = to_chain(_raw())
    assert ch.lot_size == 65 and len(ch.quotes) == 6
    snap = ch.status()
    assert snap["n_strikes"] and snap["max_pain"] is not None
    # parity forward from ATM legs (C == P at ATM here → forward ≈ ATM strike)
    assert abs(ch.F - 24000.0) < 1.0


def test_expiry_day_still_has_time_value():
    ch = to_chain(_raw(expiry_days=0))
    assert ch.t > 0                          # half a day, never zero/negative


def test_empty_chain_raises_not_fakes():
    raw = _raw()
    raw["chain"] = []
    with pytest.raises(ValueError):
        to_chain(raw)
