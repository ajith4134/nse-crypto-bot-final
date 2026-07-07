"""Regression: NSE futures/options screeners must emit BROKER-TRADABLE symbols.

Two live bugs made the futures + options segments open ZERO trades:
  1. screen_nse_fno emitted bare underlyings (NIFTY) — NFO quotes 400'd on them.
     It must resolve to the near-month FUT contract (NIFTY28JUL26FUT).
  2. options._ltp used the SDK's websocket get_ltp() (returns {'ltp': {}} without a
     subscription) — LTP 0 → no ATM strike → screener returned [] forever.
     It must use the REST quotes() endpoint.
Run: pytest tests/test_futures_options_symbols.py
"""
import tempfile
from pathlib import Path

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # isolate: never touch live state


class _FakeClient:
    """Mimics the openalgo SDK: broken get_ltp, working quotes/search."""

    def __init__(self, search_rows):
        self._rows = search_rows

    def get_ltp(self, **kw):          # the websocket helper — no REST data
        return {"ltp": {}}

    def quotes(self, **kw):           # the REST endpoint that actually works
        return {"status": "success", "data": {"ltp": 24364.2}}

    def search(self, query=None, exchange=None):
        return {"data": self._rows}


_NFO_ROWS = [
    {"symbol": "NIFTY28JUL26FUT", "instrumenttype": "FUT", "expiry": "28-JUL-26"},
    {"symbol": "NIFTY25AUG26FUT", "instrumenttype": "FUT", "expiry": "25-AUG-26"},
    {"symbol": "NIFTYNXT5028JUL26FUT", "instrumenttype": "FUT", "expiry": "28-JUL-26"},
    {"symbol": "NIFTY07JUL2624350CE", "instrumenttype": "CE", "strike": 24350,
     "expiry": "07-JUL-26"},
    {"symbol": "NIFTY07JUL2624350PE", "instrumenttype": "PE", "strike": 24350,
     "expiry": "07-JUL-26"},
]


def test_ltp_uses_rest_quotes_not_websocket_get_ltp():
    from trading.screener.options import _ltp
    assert _ltp(_FakeClient(_NFO_ROWS), "NIFTY") == 24364.2


def test_nse_futures_resolve_to_near_month_contract(monkeypatch):
    from trading.screener import screener as S

    class _Src:
        def active_underlying(self):
            return [{"symbol": "NIFTY", "volume": 1000000}]

    monkeypatch.setattr("trading.screener.options._broker",
                        lambda: _FakeClient(_NFO_ROWS))
    out = S.screen_nse_fno(_Src(), limit=3)
    syms = [c["symbol"] for c in out]
    assert syms == ["NIFTY28JUL26FUT"], syms       # near-month, exact-base, never bare
    assert out[0]["metrics"]["underlying"] == "NIFTY"


def test_min_open_legacy_fno_key_lands_on_futures():
    from trading.online.live_loop import LiveTradeLoop as L
    o = L.__new__(L)
    o.cfg = {"min_open_by_segment": {}, "min_open_per_segment": 0,
             "leverage_by_segment": {}, "lot_size_by_segment": {}}
    o._sizer = None
    o.set_config(min_open_by_segment={"fno": 4})
    assert o.cfg["min_open_by_segment"] == {"futures": 4}
    assert o._min_open_for("futures") == 4


def test_lot_size_prefers_real_master_contract_over_segment_default():
    """Regression 2026-07-03: NFO entries bounced with 'Quantity must be in multiples
    of lot size 65' — the loop guessed lot 50 per segment while NIFTY trades in 65s.
    _lot_size_of must prefer OpenAlgo's real per-symbol lotsize when given a symbol."""
    from trading.online.live_loop import LiveTradeLoop as L

    class _OA:
        def lot_size(self, symbol, exchange):
            assert exchange == "NFO"
            return {"NIFTY07JUL2624350CE": 65, "BANKNIFTY28JUL2658000CE": 30}[symbol]

    o = L.__new__(L)
    o.cfg = {"lot_size_by_segment": {}}
    o._oa, o._oa_synced = _OA(), True
    assert o._lot_size_of("NSE", "options", "NIFTY07JUL2624350CE") == 65
    assert o._lot_size_of("NSE", "options", "BANKNIFTY28JUL2658000CE") == 30
    # no symbol → falls back to segment default (unchanged behavior)
    assert o._lot_size_of("NSE", "options") == 50
    # equity is always whole shares
    assert o._lot_size_of("NSE", "intraday", "RELIANCE") == 1


def test_lot_size_falls_back_when_openalgo_unreachable():
    from trading.online.live_loop import LiveTradeLoop as L

    class _Down:
        def lot_size(self, symbol, exchange):
            raise RuntimeError("server down")

    o = L.__new__(L)
    o.cfg = {"lot_size_by_segment": {"options": 75}}
    o._oa, o._oa_synced = _Down(), True
    assert o._lot_size_of("NSE", "options", "NIFTY07JUL2624350CE") == 75
