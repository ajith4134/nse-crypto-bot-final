"""Phase 2: pure CE/PE generation logic (no live broker/market needed).

Feeds mocked option-chain rows to the pure helpers so the ATM/expiry/mode logic is
verified deterministically. Live wiring (broker LTP + search) is exercised only when
a Zerodha session is up during market hours — out of scope for unit tests.
"""
import tempfile

import trading.state as _state

_state.STATE_DIR = tempfile.mkdtemp()

from trading.screener import options as O  # noqa: E402


def _chain(expiry="07-Jul-2026"):
    """A small NIFTY-like chain: strikes 24800..25200 step 100, CE+PE each."""
    rows = []
    for k in range(24800, 25201, 100):
        for t in ("CE", "PE"):
            rows.append({"symbol": f"NIFTY07JUL26{k}{t}", "strike": float(k),
                         "expiry": expiry, "opt_type": t})
    return rows


def test_atm_strike_picks_nearest_listed():
    assert O.atm_strike(25040, [24900, 25000, 25100]) == 25000
    assert O.atm_strike(25060, [24900, 25000, 25100]) == 25100
    assert O.atm_strike(0, [25000]) is None


def test_nearest_expiry():
    assert O.nearest_expiry(["28-Jul-2026", "07-Jul-2026", "14-Jul-2026"]) == "07-Jul-2026"
    assert O.nearest_expiry([]) is None


def test_atm_mode_gives_one_ce_one_pe_at_atm():
    picks = O.pick_contracts(_chain(), ltp=25010, mode="atm")
    assert {p["opt_type"] for p in picks} == {"CE", "PE"}
    assert all(p["strike"] == 25000 for p in picks)
    assert len(picks) == 2


def test_ladder_mode_adds_otm_strikes():
    picks = O.pick_contracts(_chain(), ltp=25010, mode="ladder", otm_depth=2)
    strikes = sorted({p["strike"] for p in picks})
    # ATM 25000 ± 2 steps of 100
    assert strikes == [24800, 24900, 25000, 25100, 25200]
    assert {p["opt_type"] for p in picks} == {"CE", "PE"}


def test_chain_mode_returns_capped_chain():
    picks = O.pick_contracts(_chain(), ltp=25010, mode="chain", chain_cap=6)
    assert len(picks) == 6
    # closest-to-ATM first
    assert abs(picks[0]["strike"] - 25000) <= abs(picks[-1]["strike"] - 25000)


def test_picks_only_nearest_expiry():
    rows = _chain("07-Jul-2026") + _chain("14-Jul-2026")
    picks = O.pick_contracts(rows, ltp=25010, mode="atm")
    assert all(p["expiry"] == "07-Jul-2026" for p in picks)


def test_norm_rows_derives_opt_type_from_symbol_suffix():
    raw = {"data": [
        {"symbol": "NIFTY07JUL2625000CE", "strike": 25000, "expiry": "07-Jul-2026"},
        {"symbol": "NIFTY07JUL2625000PE", "strike": 25000, "expiry": "07-Jul-2026"},
        {"symbol": "RELIANCE", "strike": 0},  # not an option → dropped
    ]}
    rows = O._norm_rows(raw)
    assert {r["opt_type"] for r in rows} == {"CE", "PE"}
    assert len(rows) == 2


def test_no_broker_returns_empty(monkeypatch):
    monkeypatch.setattr(O, "_broker", lambda: None)
    assert O.screen_nse_options(None, filters={"option_mode": "atm"}) == []
