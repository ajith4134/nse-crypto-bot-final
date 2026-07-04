"""Phase 1 regression: NSE `fno` segment split into `futures` + `options`.

Isolates trading.state.STATE_DIR to a temp dir (never touches the live journal).
"""
import tempfile
from pathlib import Path

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # MUST precede any state/live_loop import


def test_nse_segments_are_split():
    from trading.online import state as S
    assert S.SEGMENTS["NSE"] == ["intraday", "mtf", "futures", "options", "commodities"]
    assert "fno" not in S.SEGMENTS["NSE"]


def test_legacy_fno_normalizes_to_futures():
    from trading.online import state as S
    assert S.normalize_segment("fno") == "futures"
    assert S.normalize_segment("FNO") == "futures"
    assert S.normalize_segment("options") == "options"


def test_marketstate_migrates_saved_fno():
    from trading.online import state as S
    ms = S.MarketState(market="NSE", segments=["fno", "options", "bogus"])
    assert ms.segments == ["futures", "options"]          # fno→futures, bogus dropped
    ms.set_segments(["fno"])
    assert ms.segments == ["futures"]
    assert ms.has_segment("fno") and ms.has_segment("futures")


def test_loop_maps_cover_futures_and_options():
    from trading.online.live_loop import LiveTradeLoop as L
    o = L.__new__(L)
    assert o._OA_EXCHANGE["futures"] == "NFO"
    assert o._OA_EXCHANGE["options"] == "NFO"
    assert o._instrument_product("NSE", "futures") == ("FUT", "NRML")
    assert o._instrument_product("NSE", "options") == ("OPT", "NRML")
    assert o._is_lot_based("NSE", "futures")
    assert o._is_lot_based("NSE", "options")


def test_max_leverage_is_market_aware():
    # NSE futures must NOT inherit crypto futures 125x.
    from trading.online.live_loop import LiveTradeLoop as L
    o = L.__new__(L)
    assert o.max_leverage_of("futures", "NSE") == 10.0
    assert o.max_leverage_of("futures", "CRYPTO") == 125.0
    assert o.max_leverage_of("options", "NSE") == 1.0


def test_screener_routes_options():
    from trading.screener.screener import SEGMENTS, screen_nse_options
    assert SEGMENTS["NSE"] == ["intraday", "mtf", "futures", "options", "commodities"]
    # Phase-2 impl may be absent → must degrade to [] (never raise)
    assert screen_nse_options(None) == [] or isinstance(screen_nse_options(None), list)
