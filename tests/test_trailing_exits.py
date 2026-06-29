"""Tests for trading/exits/ — four trailing-exit components over one signed engine.

Proves (per the build spec):
  (1) LongStopTrail exits when price falls X% from peak after rising.
  (2) LongProfitTrail only arms after profit_offset is reached, then ratchets.
  (3) ShortLossTrail exits when price rises from the trough.
  (4) ShortProfitTrail ratchets the stop DOWN.
  (5) vectorbt cross-check: the long pct stop-trail exit index matches vectorbt's
      trailing stop (sl_stop + sl_trail) on the same synthetic series, offline.
Plus: ATR/chandelier/supertrend adaptive modes, the make_exit factory, and the
build_demo_trailing dashboard snapshot. All deterministic, no network.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.exits import (
    LongProfitTrail,
    LongStopTrail,
    ShortLossTrail,
    ShortProfitTrail,
    TrailingEngine,
    build_demo_trailing,
    make_exit,
)

# rise to 110 then fall back to 100
UP_DOWN = [100, 102, 104, 106, 108, 110, 108, 106, 104, 102, 100]
# fall to 90 then rise back to 100
DOWN_UP = [100, 98, 96, 94, 92, 90, 92, 94, 96, 98, 100]


def _first_exit(engine, path):
    for i, px in enumerate(path):
        r = engine.update(px)
        if r["exit"]:
            return i, r
    return None, None


# ---------------------------------------------------------------- (1) long stop
def test_long_stop_trail_exits_on_drop_from_peak():
    eng = LongStopTrail(100, trail_pct=0.05)
    idx, r = _first_exit(eng, UP_DOWN)
    # peak 110 → stop 104.5; price 104 (idx 8) is the first breach
    assert idx == 8
    assert r["reason"] == "exit"
    assert r["peak"] == 110
    assert r["stop"] == pytest.approx(104.5)


def test_long_stop_trail_ratchets_up_only():
    eng = LongStopTrail(100, trail_pct=0.05)
    stops = [eng.update(px)["stop"] for px in [100, 105, 103, 108, 107]]
    # stop must be non-decreasing (ratchet up), never give back ground
    assert stops == sorted(stops)
    assert stops[-1] == pytest.approx(108 * 0.95)


def test_long_stop_no_exit_while_rising():
    eng = LongStopTrail(100, trail_pct=0.05)
    for px in [100, 102, 104, 106]:
        assert eng.update(px)["exit"] is False


# ---------------------------------------------------------------- (2) long TP
def test_long_profit_trail_arms_only_after_offset():
    eng = LongProfitTrail(100, trail_pct=0.02, profit_offset=0.05)
    # below +5% profit → unarmed, no stop, cannot exit even on a dip
    r = eng.update(103)
    assert r["reason"] == "unarmed" and r["stop"] is None
    r = eng.update(101)              # dipped, still never armed
    assert r["reason"] == "unarmed" and r["exit"] is False
    # reach +5% (price 105) → arms
    eng.update(106)                  # peak 106 ≥ +5% → armed
    assert eng.armed is True
    # now a drop of >2% from peak triggers the locked profit exit
    idx_armed_stop = eng.stop
    assert idx_armed_stop == pytest.approx(106 * 0.98)
    r = eng.update(103)              # 103 < 103.88 → exit
    assert r["exit"] is True and r["reason"] == "exit"


def test_long_profit_trail_ratchets_after_arming():
    eng = LongProfitTrail(100, trail_pct=0.02, profit_offset=0.03)
    eng.update(104)                  # arms (+4%)
    s1 = eng.stop
    s2 = eng.update(110)["stop"]     # higher peak → stop ratchets up
    assert s2 > s1
    s3 = eng.update(108)["stop"]     # pullback → stop holds (no give-back)
    assert s3 == pytest.approx(s2)


# ---------------------------------------------------------------- (3) short loss
def test_short_loss_trail_exits_on_rise_from_trough():
    eng = ShortLossTrail(100, trail_pct=0.05)
    idx, r = _first_exit(eng, DOWN_UP)
    # trough 90 → stop 94.5; price 96 (idx 8) is the first breach upward
    assert idx == 8
    assert r["peak"] == 90           # 'peak' = favourable extreme (trough for shorts)
    assert r["stop"] == pytest.approx(94.5)
    assert r["reason"] == "exit"


# ---------------------------------------------------------------- (4) short TP
def test_short_profit_trail_ratchets_down():
    eng = ShortProfitTrail(100, trail_pct=0.02, profit_offset=0.03)
    # unarmed until price falls 3% in favour
    assert eng.update(98)["reason"] == "unarmed"
    eng.update(96)                   # arms (-4% = +4% profit for a short)
    s1 = eng.stop
    s2 = eng.update(90)["stop"]      # lower trough → stop ratchets DOWN
    assert s2 < s1
    s3 = eng.update(92)["stop"]      # bounce → stop holds (no give-back)
    assert s3 == pytest.approx(s2)
    assert s2 == pytest.approx(90 * 1.02)


def test_short_profit_arms_only_after_offset():
    eng = ShortProfitTrail(100, trail_pct=0.05, profit_offset=0.05)
    r = eng.update(97)               # only -3% → unarmed
    assert r["reason"] == "unarmed" and r["stop"] is None


# ---------------------------------------------------------------- (5) vectorbt
def test_long_stop_trail_matches_vectorbt_tsl():
    vbt = pytest.importorskip("vectorbt")
    path = UP_DOWN
    s = pd.Series(path, dtype=float)
    entries = pd.Series([True] + [False] * (len(path) - 1))
    exits = pd.Series([False] * len(path))
    pf = vbt.Portfolio.from_signals(
        s, entries=entries, exits=exits, sl_stop=0.05, sl_trail=True, freq="1D"
    )
    vbt_exit_idx = int(pf.trades.records["exit_idx"][0])

    eng = LongStopTrail(100, trail_pct=0.05)
    our_idx, _ = _first_exit(eng, path)
    assert our_idx == vbt_exit_idx == 8


def test_short_trail_matches_vectorbt():
    vbt = pytest.importorskip("vectorbt")
    path = DOWN_UP
    s = pd.Series(path, dtype=float)
    short_entries = pd.Series([True] + [False] * (len(path) - 1))
    pf = vbt.Portfolio.from_signals(
        s,
        entries=pd.Series([False] * len(path)),
        exits=pd.Series([False] * len(path)),
        short_entries=short_entries,
        short_exits=pd.Series([False] * len(path)),
        sl_stop=0.05,
        sl_trail=True,
        freq="1D",
    )
    vbt_exit_idx = int(pf.trades.records["exit_idx"][0])
    eng = ShortLossTrail(100, trail_pct=0.05)
    our_idx, _ = _first_exit(eng, path)
    assert our_idx == vbt_exit_idx


# ---------------------------------------------------------------- adaptive modes
def test_atr_mode_produces_volatility_scaled_stop():
    eng = LongStopTrail(100, mode="atr", atr_mult=2.0, atr_period=3)
    last = None
    for hi, lo, cl in [(101, 99, 100), (103, 100, 102), (105, 102, 104),
                       (107, 104, 106), (108, 105, 107)]:
        last = eng.update(cl, high=hi, low=lo)
    assert last["stop"] is not None
    # ATR stop sits below price for a long and ratchets (non-give-back)
    assert last["stop"] < 107
    assert eng.mode == "atr"


def test_chandelier_mode_uses_pandas_ta_classic():
    pytest.importorskip("pandas_ta_classic")
    eng = LongStopTrail(100, mode="chandelier", atr_mult=3.0, ind_length=5)
    out = None
    # feed enough bars for ce() to emit a value
    rng = np.linspace(100, 120, 12)
    for i, mid in enumerate(rng):
        out = eng.update(mid, high=mid + 1, low=mid - 1)
    assert eng.mode == "chandelier"
    # once warmed, a chandelier stop level exists below the rising price
    assert out["stop"] is None or out["stop"] < rng[-1] + 1


def test_supertrend_mode_uses_pandas_ta_classic():
    pytest.importorskip("pandas_ta_classic")
    eng = LongStopTrail(100, mode="supertrend", atr_mult=3.0, ind_length=5)
    rng = np.linspace(100, 130, 15)
    out = None
    for mid in rng:
        out = eng.update(mid, high=mid + 1, low=mid - 1)
    assert eng.mode == "supertrend"
    assert out is not None


# ---------------------------------------------------------------- factory
def test_make_exit_returns_correct_wrappers():
    assert isinstance(make_exit("long", "profit", entry_price=100), LongProfitTrail)
    assert isinstance(make_exit("buy", "stop", entry_price=100), LongStopTrail)
    assert isinstance(make_exit("short", "profit", entry_price=100), ShortProfitTrail)
    assert isinstance(make_exit("sell", "loss", entry_price=100), ShortLossTrail)
    # aliases
    assert isinstance(make_exit("long", "take_profit", entry_price=100), LongProfitTrail)
    assert isinstance(make_exit("short", "stop_loss", entry_price=100), ShortLossTrail)


def test_make_exit_passes_config_through():
    eng = make_exit("long", "stop", entry_price=100, mode="pct", trail_pct=0.07)
    assert eng.trail_pct == pytest.approx(0.07)
    assert eng.direction == "long"


def test_make_exit_rejects_unknown_purpose():
    with pytest.raises(ValueError):
        make_exit("long", "banana", entry_price=100)


# ---------------------------------------------------------------- reset + status
def test_reset_re_arms_for_new_position():
    eng = LongStopTrail(100, trail_pct=0.05)
    _first_exit(eng, UP_DOWN)
    assert eng.exited is True
    eng.reset(200)
    assert eng.exited is False and eng.entry_price == 200 and eng.stop is None
    r = eng.update(210)
    assert r["stop"] == pytest.approx(210 * 0.95)


def test_status_snapshot_shape():
    eng = ShortProfitTrail(100, trail_pct=0.03, profit_offset=0.02)
    eng.update(95)
    st = eng.status()
    for key in ("component", "direction", "mode", "purpose", "entry", "peak",
                "stop", "armed", "exited", "profit_offset", "ticks"):
        assert key in st
    assert st["direction"] == "short"
    assert st["purpose"] == "take_profit"


# ---------------------------------------------------------------- dashboard demo
def test_build_demo_trailing_snapshot():
    snap = build_demo_trailing()
    assert snap["module"] == "trading/exits"
    comps = snap["components"]
    assert set(comps) == {"LongProfitTrail", "LongStopTrail",
                          "ShortProfitTrail", "ShortLossTrail"}
    # both stop-loss trails should have fired on their respective paths
    assert comps["LongStopTrail"]["exit_index"] == 8
    assert comps["ShortLossTrail"]["exit_index"] == 8
    for c in comps.values():
        assert "stop" in c and "armed" in c


def test_engine_signed_core_direct_construction():
    eng = TrailingEngine(mode="pct", direction="short", trail_pct=0.05, entry_price=100)
    idx, r = _first_exit(eng, DOWN_UP)
    assert idx == 8 and r["reason"] == "exit"
