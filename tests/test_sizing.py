"""Tests for trading/sizing -- per-trade position/capital sizer.

Run: .venv/bin/python -m pytest tests/test_sizing.py -q
"""
from __future__ import annotations

import math

import pytest

from trading.sizing import PositionSizer, afml_bet_size, build_demo_sizing


CAP = 100_000.0


# --------------------------------------------------------------------------- #
# atr_risk: respects max_risk_pct
# --------------------------------------------------------------------------- #
def test_atr_risk_respects_max_risk_pct():
    s = PositionSizer(method="atr_risk", max_risk_pct=1.0, max_position_pct=100.0)
    r = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="LONG")
    # risk_amount must equal 1% of capital (qty * ATR = risk budget).
    assert math.isclose(r["risk_amount"], 0.01 * CAP, rel_tol=1e-9)
    # qty = risk / ATR = 1000 / 2 = 500
    assert math.isclose(r["qty"], 500.0, rel_tol=1e-9)
    assert math.isclose(r["notional"], 500.0 * 100.0, rel_tol=1e-9)
    assert r["method"] == "atr_risk"


def test_atr_risk_uses_stop_distance_when_no_atr():
    s = PositionSizer(method="atr_risk", max_risk_pct=2.0, max_position_pct=100.0)
    r = s.size(capital=CAP, entry_price=100.0, stop_price=95.0, side="LONG")
    # per-unit risk = |100-95| = 5; risk budget = 2% of 100k = 2000; qty = 400
    assert math.isclose(r["risk_amount"], 2000.0, rel_tol=1e-9)
    assert math.isclose(r["qty"], 400.0, rel_tol=1e-9)


def test_atr_risk_scales_with_max_risk_pct():
    a = PositionSizer(method="atr_risk", max_risk_pct=1.0, max_position_pct=100.0)
    b = PositionSizer(method="atr_risk", max_risk_pct=2.0, max_position_pct=100.0)
    ra = a.size(capital=CAP, entry_price=100.0, atr=2.0)
    rb = b.size(capital=CAP, entry_price=100.0, atr=2.0)
    assert math.isclose(rb["qty"], 2 * ra["qty"], rel_tol=1e-9)


def test_atr_risk_zero_when_no_stop_or_atr():
    s = PositionSizer(method="atr_risk")
    r = s.size(capital=CAP, entry_price=100.0)
    assert r["qty"] == 0.0
    assert "cannot bound risk" in r["reason"]


# --------------------------------------------------------------------------- #
# kelly: sane fraction for known win_rate / payoff
# --------------------------------------------------------------------------- #
def test_kelly_fraction_known_values():
    # full Kelly for p=0.6, b=2 is 0.6 - 0.4/2 = 0.4; half-Kelly -> 0.2
    s = PositionSizer(method="kelly", kelly_fraction=0.5, max_position_pct=100.0)
    r = s.size(capital=CAP, entry_price=2500.0, win_rate=0.6, payoff=2.0, side="LONG")
    assert math.isclose(abs(r["fraction"]), 0.2, rel_tol=1e-6)
    assert math.isclose(r["notional"], 0.2 * CAP, rel_tol=1e-6)


def test_kelly_fraction_between_0_and_1():
    s = PositionSizer(method="kelly", kelly_fraction=1.0, max_position_pct=100.0)
    for p, b in [(0.55, 1.5), (0.7, 1.0), (0.51, 3.0)]:
        r = s.size(capital=CAP, entry_price=100.0, win_rate=p, payoff=b)
        assert 0.0 <= r["fraction"] <= 1.0


def test_kelly_no_edge_gives_nonpositive_size():
    # p=0.4, b=1 -> negative edge -> Kelly clipped to 0
    s = PositionSizer(method="kelly", kelly_fraction=0.5, max_position_pct=100.0)
    r = s.size(capital=CAP, entry_price=100.0, win_rate=0.4, payoff=1.0)
    assert r["fraction"] == 0.0


def test_kelly_missing_inputs_zero():
    s = PositionSizer(method="kelly")
    r = s.size(capital=CAP, entry_price=100.0, win_rate=0.6)  # no payoff
    assert r["qty"] == 0.0


# --------------------------------------------------------------------------- #
# ai_meta (AFML Ch.10): ~0 at p=0.5, grows toward cap as p->1
# --------------------------------------------------------------------------- #
def test_afml_bet_size_zero_at_half():
    assert abs(afml_bet_size(0.5, "LONG")) < 1e-9


def test_afml_bet_size_grows_to_one():
    sizes = [afml_bet_size(p, "LONG") for p in (0.5, 0.6, 0.75, 0.9, 0.99)]
    # strictly increasing and bounded in (0, 1]
    assert all(b > a for a, b in zip(sizes, sizes[1:]))
    assert sizes[-1] <= 1.0
    assert afml_bet_size(0.999999, "LONG") == pytest.approx(1.0, abs=1e-3)


def test_ai_meta_zero_at_half_and_caps_near_one():
    s = PositionSizer(method="ai_meta", max_position_pct=25.0)
    r_half = s.size(capital=CAP, entry_price=100.0, prob=0.5, side="LONG")
    assert abs(r_half["fraction"]) < 1e-9
    assert r_half["notional"] < 1.0

    r_hi = s.size(capital=CAP, entry_price=100.0, prob=0.999999, side="LONG")
    # approaches the per-position cap (25%) as prob -> 1
    assert r_hi["fraction"] == pytest.approx(0.25, abs=1e-3)
    assert r_hi["notional"] == pytest.approx(0.25 * CAP, rel=1e-3)


def test_ai_meta_monotonic_in_prob():
    s = PositionSizer(method="ai_meta", max_position_pct=25.0)
    fr = [
        s.size(capital=CAP, entry_price=100.0, prob=p, side="LONG")["fraction"]
        for p in (0.5, 0.6, 0.7, 0.85, 0.95)
    ]
    assert all(b > a for a, b in zip(fr, fr[1:]))


# --------------------------------------------------------------------------- #
# vol_target
# --------------------------------------------------------------------------- #
def test_vol_target_formula():
    s = PositionSizer(method="vol_target", max_position_pct=100.0)
    # target_vol default 0.15; realized 0.30 -> fraction 0.5
    r = s.size(capital=CAP, entry_price=300.0, volatility=0.30, side="LONG")
    assert math.isclose(r["fraction"], 0.5, rel_tol=1e-9)
    # higher vol -> smaller size
    r2 = s.size(capital=CAP, entry_price=300.0, volatility=0.60, side="LONG")
    assert r2["fraction"] < r["fraction"]


# --------------------------------------------------------------------------- #
# max_position_pct cap binds
# --------------------------------------------------------------------------- #
def test_max_position_pct_cap_binds():
    # huge ATR-risk budget would imply a large fraction; cap clips it.
    s = PositionSizer(method="atr_risk", max_risk_pct=50.0, max_position_pct=10.0)
    r = s.size(capital=CAP, entry_price=100.0, atr=1.0, side="LONG")
    assert r["fraction"] == pytest.approx(0.10, rel=1e-9)
    assert r["notional"] == pytest.approx(0.10 * CAP, rel=1e-9)
    assert "capped" in r["reason"]


def test_kelly_cap_binds():
    s = PositionSizer(method="kelly", kelly_fraction=1.0, max_position_pct=5.0)
    r = s.size(capital=CAP, entry_price=100.0, win_rate=0.8, payoff=2.0)
    assert r["fraction"] == pytest.approx(0.05, rel=1e-9)


# --------------------------------------------------------------------------- #
# short side flips sign
# --------------------------------------------------------------------------- #
def test_short_flips_sign_atr():
    s = PositionSizer(method="atr_risk", max_risk_pct=1.0, max_position_pct=100.0)
    long = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="LONG")
    short = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="SHORT")
    assert long["qty"] > 0 and short["qty"] < 0
    assert math.isclose(long["qty"], -short["qty"], rel_tol=1e-9)
    # magnitudes (notional/risk) stay positive for both
    assert short["notional"] > 0 and short["risk_amount"] > 0
    assert short["side"] == "SHORT"


def test_short_flips_sign_ai_meta():
    s = PositionSizer(method="ai_meta", max_position_pct=25.0)
    long = s.size(capital=CAP, entry_price=100.0, prob=0.8, side="LONG")
    short = s.size(capital=CAP, entry_price=100.0, prob=0.8, side="SHORT")
    assert long["fraction"] > 0 and short["fraction"] < 0
    assert afml_bet_size(0.8, "SHORT") == pytest.approx(-afml_bet_size(0.8, "LONG"))


# --------------------------------------------------------------------------- #
# auto blend
# --------------------------------------------------------------------------- #
def test_auto_blend_takes_min_of_edge_and_atr():
    # default 'kelly_atr' alias -> auto
    s = PositionSizer(method="kelly_atr", max_risk_pct=1.0,
                      kelly_fraction=0.5, max_position_pct=100.0)
    r = s.size(capital=CAP, entry_price=100.0, atr=2.0,
               win_rate=0.6, payoff=2.0, side="LONG")
    # atr fraction here = (500*100)/100k = 0.5 ; kelly half = 0.2 -> min = 0.2
    assert r["method"] == "auto"
    assert r["fraction"] == pytest.approx(0.2, rel=1e-6)


def test_auto_drawdown_reduces_size():
    s = PositionSizer(method="auto", max_risk_pct=1.0, max_position_pct=100.0,
                      max_drawdown_pct=20.0)
    base = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="LONG")
    s.update_drawdown(10.0)  # halfway to the 20% limit -> 0.5x
    reduced = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="LONG")
    assert reduced["fraction"] == pytest.approx(0.5 * base["fraction"], rel=1e-6)
    s.update_drawdown(20.0)  # at the limit -> 0 size
    killed = s.size(capital=CAP, entry_price=100.0, atr=2.0, side="LONG")
    assert killed["fraction"] == 0.0


def test_auto_falls_back_when_no_signal():
    s = PositionSizer(method="auto", max_position_pct=25.0)
    r = s.size(capital=CAP, entry_price=100.0)  # nothing actionable
    assert 0.0 < r["fraction"] < 0.25  # minimal fixed fraction
    assert "no edge/stop" in r["reason"]


# --------------------------------------------------------------------------- #
# guards / structure / status / demo
# --------------------------------------------------------------------------- #
def test_zero_capital_returns_empty():
    s = PositionSizer(method="auto")
    r = s.size(capital=0.0, entry_price=100.0)
    assert r["qty"] == 0.0 and r["notional"] == 0.0


def test_return_keys_present():
    s = PositionSizer(method="auto")
    r = s.size(capital=CAP, entry_price=100.0, atr=2.0)
    for k in ("qty", "notional", "capital_used", "risk_amount",
              "method", "fraction", "reason"):
        assert k in r


def test_invalid_method_raises():
    with pytest.raises(ValueError):
        PositionSizer(method="nope")


def test_status_shape():
    s = PositionSizer(method="auto")
    st = s.status()
    assert st["sizer"] == "PositionSizer"
    assert st["deterministic"] is True and st["offline"] is True
    assert "AFML" in st["ai_feature"]


def test_build_demo_sizing_deterministic():
    a = build_demo_sizing()
    b = build_demo_sizing()
    assert a["examples"]["ai_meta_short"]["qty"] == b["examples"]["ai_meta_short"]["qty"]
    assert a["examples"]["ai_meta_short"]["qty"] < 0  # short
    assert a["examples"]["atr_long"]["qty"] > 0
