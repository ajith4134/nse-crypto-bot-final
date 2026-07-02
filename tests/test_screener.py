"""tests/test_screener.py — per-segment screener: offline-safe, deterministic.

All tests run with NO network: live sources are replaced by injected fakes that
return fixtures, and the pure-offline path falls back to the deterministic stub.
"""
from __future__ import annotations

import math

import pytest

from trading.screener import (
    Screener,
    apply_technical_filters,
    build_demo_screener,
    oi_buildup,
    percent_change_filter,
    range_stability,
    realized_volatility,
    relative_volume,
    screen_crypto_spot,
    screen_nse_movers,
    stub_candidates,
    volume_filter,
)
from trading.screener.screener import SEGMENTS


# ── deterministic fakes (injected sources) ────────────────────────────────────
class FakeNSESource:
    name = "fake-nse"

    def movers(self, kind="gainers"):
        if kind.startswith("gain"):
            return [
                {"symbol": "ADANIENT", "ltp": 100, "pct_change": 8.5, "volume": 5_000_000},
                {"symbol": "TATAMOTORS", "ltp": 50, "pct_change": 4.2, "volume": 9_000_000},
            ]
        return [{"symbol": "WIPRO", "ltp": 40, "pct_change": -6.1, "volume": 3_000_000}]

    def most_active(self):
        return [{"symbol": "TATAMOTORS", "ltp": 50, "pct_change": 4.2, "volume": 9_000_000},
                {"symbol": "SBIN", "ltp": 60, "pct_change": 0.5, "volume": 8_000_000}]

    def week_52(self):
        return [{"symbol": "ADANIENT"}]

    def active_underlying(self):
        return [{"symbol": "NIFTY", "volume": 1_000_000},
                {"symbol": "BANKNIFTY", "volume": 800_000},
                {"symbol": "RELIANCE", "volume": 200_000}]


class FakeCryptoSource:
    name = "fake-ccxt"

    def tickers(self, market_type="spot"):
        if market_type == "spot":
            return {
                "BTC/USDT": {"percentage": 3.0, "quoteVolume": 1.0e10, "last": 60000},
                "ETH/USDT": {"percentage": 2.0, "quoteVolume": 5.0e9, "last": 3000},
                "SOL/USDT": {"percentage": 9.0, "quoteVolume": 1.0e9, "last": 150},
                "DOGE/BTC": {"percentage": 1.0, "quoteVolume": 1.0e6, "last": 0.0000002},
            }
        if market_type == "futures":
            return {
                "BTC/USDT:USDT": {"percentage": 3.0, "quoteVolume": 2.0e10, "last": 60000},
                "ETH/USDT:USDT": {"percentage": 2.0, "quoteVolume": 8.0e9, "last": 3000},
            }
        if market_type == "options":
            return {"BTC/USDT:USDT-260101-60000-C": {"quoteVolume": 1000, "last": 1500}}
        return {}

    def funding_rates(self, market_type="futures"):
        return {"BTC/USDT:USDT": {"fundingRate": 0.0005},
                "ETH/USDT:USDT": {"fundingRate": 0.0001}}

    def greeks(self, market_type="options"):
        return {}


# ── pure filter algorithms ────────────────────────────────────────────────────
def test_percent_change_filter_sorts_and_clips():
    rows = [{"symbol": "A", "pct_change": 5}, {"symbol": "B", "pct_change": -3},
            {"symbol": "C", "pct_change": 9}]
    top = percent_change_filter(rows, min_value=0)
    assert [r["symbol"] for r in top] == ["C", "A"]
    losers = percent_change_filter(rows, sort_direction="asc", max_value=0)
    assert losers[0]["symbol"] == "B"


def test_volume_filter_ranks_desc_with_min():
    rows = [{"symbol": "A", "quote_volume": 10}, {"symbol": "B", "quote_volume": 99},
            {"symbol": "C", "quote_volume": 1}]
    out = volume_filter(rows, min_value=5)
    assert [r["symbol"] for r in out] == ["B", "A"]


def test_relative_volume_detects_spike():
    vols = [100] * 20 + [350]
    assert relative_volume(vols, window=20) == pytest.approx(3.5)
    assert relative_volume([100]) is None


def test_realized_volatility_and_range_stability():
    closes = [100, 102, 101, 105, 103]
    assert realized_volatility(closes) > 0
    assert realized_volatility([100]) is None
    assert range_stability([110, 120], [90, 100]) == pytest.approx((120 - 90) / 90)


def test_oi_buildup_classification():
    assert oi_buildup(1, 1) == "long_buildup"
    assert oi_buildup(-1, 1) == "short_buildup"
    assert oi_buildup(-1, -1) == "long_unwinding"
    assert oi_buildup(1, -1) == "short_covering"


# ── technical filters (pandas_ta_classic; offline-safe) ───────────────────────
def test_apply_technical_filters_on_synthetic_ohlc():
    bars = [{"open": i, "high": i + 2, "low": i, "close": i + 1, "volume": 100 + i}
            for i in range(40)]
    m = apply_technical_filters(bars)
    assert m, "expected non-empty metrics"
    assert "atr" in m and m["atr"] > 0
    assert 0.0 <= m["range_pos"] <= 1.0
    assert m["bars"] == 40
    # uptrend → breakout_up true at the most recent bar
    assert m.get("breakout_up") is True


def test_apply_technical_filters_handles_garbage():
    assert apply_technical_filters([]) == {}
    assert apply_technical_filters([{"foo": 1}]) == {}


# ── standalone composables over injected fakes ────────────────────────────────
def test_screen_nse_movers_ranks_and_scores():
    out = screen_nse_movers(FakeNSESource(), "intraday", limit=3)
    assert out and out[0]["symbol"] == "ADANIENT"   # biggest % move + 52w + gainer
    assert all(c["market"] == "NSE" and c["segment"] == "intraday" for c in out)
    assert out[0]["score"] >= out[-1]["score"]
    assert out[0]["metrics"]["source"] == "nselib"


def test_screen_crypto_spot_filters_quote_and_ranks():
    out = screen_crypto_spot(FakeCryptoSource(), limit=3)
    syms = [c["symbol"] for c in out]
    assert "DOGE/BTC" not in syms          # non-USDT quote dropped
    assert "BTC/USDT" in syms
    assert out == sorted(out, key=lambda c: c["score"], reverse=True)


# ── Screener routing: live (injected) + stub fallback ─────────────────────────
def test_candidates_uses_live_source_when_available():
    sc = Screener(nse_source=FakeNSESource(), crypto_source=FakeCryptoSource())
    nse = sc.candidates("NSE", "intraday", limit=3)
    assert nse and nse[0]["metrics"]["source"] == "nselib"
    crypto = sc.candidates("CRYPTO", "spot", limit=3)
    assert crypto and crypto[0]["metrics"]["source"] == "ccxt"
    assert sc.status()["last_modes"]["NSE:intraday"] == "live"


def test_candidates_falls_back_to_stub_when_source_empty(monkeypatch):
    # Commodities resolve via the OpenAlgo broker; simulate the offline case (no broker)
    # so the deterministic stub fallback is exercised with NO network.
    from trading.screener import commodities as _C
    monkeypatch.setattr(_C, "_broker", lambda: None)

    class Empty:
        name = "empty"
        def __getattr__(self, _):
            return lambda *a, **k: []
    sc = Screener(nse_source=Empty(), crypto_source=Empty())
    out = sc.candidates("NSE", "commodities", limit=4)
    assert out and out[0]["metrics"]["source"] == "stub"
    assert {c["symbol"] for c in out} & {"GOLD", "CRUDEOIL"}


def test_invalid_segment_returns_empty():
    sc = build_demo_screener()
    assert sc.candidates("NSE", "nonsense") == []


def test_demo_screener_is_pure_offline_stub_all_segments():
    sc = build_demo_screener()
    for market, segs in SEGMENTS.items():
        for seg in segs:
            out = sc.candidates(market, seg, limit=3)
            assert out, f"{market}/{seg} empty"
            assert all(c["segment"] == seg and c["market"] == market for c in out)
            assert all(c["metrics"]["source"] == "stub" for c in out)
            # ranked best-first
            assert out == sorted(out, key=lambda c: c["score"], reverse=True)


def test_stub_candidates_known_symbols():
    assert stub_candidates("NSE", "intraday")[0]["symbol"] == "RELIANCE"
    assert stub_candidates("CRYPTO", "spot")[0]["symbol"] == "BTC/USDT"


# ── watchlist union + dedup ───────────────────────────────────────────────────
def test_watchlist_dedupes_and_sorts_across_segments():
    sc = Screener(nse_source=FakeNSESource(), crypto_source=FakeCryptoSource())
    wl = sc.watchlist("NSE", ["intraday", "mtf", "fno"], per_segment=3)
    assert wl
    keys = [f"{c['segment']}:{c['symbol']}" for c in wl]
    assert len(keys) == len(set(keys))          # no dupes within a segment
    assert wl == sorted(wl, key=lambda c: c["score"], reverse=True)


def test_status_snapshot_shape():
    st = build_demo_screener().status()
    assert st["ok"] is True
    assert "segments" in st and "CRYPTO" in st["segments"]
    assert st["nse_source"] is None             # demo is offline


# ── MCX commodities: resolve base names → broker near-month FUT symbols ────────
class FakeMCXClient:
    """Stubs OpenAlgo's broker `search` for MCX — mimics the real row shape."""

    def search(self, query=None, exchange=None):
        assert exchange == "MCX"
        rows = {
            "GOLD": [
                {"symbol": "GOLD05AUG26FUT", "instrumenttype": "FUT", "expiry": "05-AUG-26"},
                {"symbol": "GOLD05OCT26FUT", "instrumenttype": "FUT", "expiry": "05-OCT-26"},
                {"symbol": "GOLDM05AUG26FUT", "instrumenttype": "FUT", "expiry": "05-AUG-26"},
                {"symbol": "GOLD05AUG2614000CE", "instrumenttype": "CE", "expiry": "05-AUG-26"},
            ],
            "CRUDEOIL": [
                {"symbol": "CRUDEOIL19AUG26FUT", "instrumenttype": "FUT", "expiry": "19-AUG-26"},
                {"symbol": "CRUDEOIL20JUL26FUT", "instrumenttype": "FUT", "expiry": "20-JUL-26"},
            ],
        }
        return {"data": rows.get(str(query).upper(), [])}


def test_resolve_near_month_fut_picks_nearest_and_exact_base(monkeypatch):
    from trading.screener import commodities as C

    client = FakeMCXClient()
    gold = C.resolve_near_month_fut(client, "GOLD")
    # nearest expiry FUT, and NOT the GOLDM look-alike, and NOT the CE option
    assert gold["symbol"] == "GOLD05AUG26FUT"
    crude = C.resolve_near_month_fut(client, "CRUDEOIL")
    assert crude["symbol"] == "CRUDEOIL20JUL26FUT"     # 20-JUL before 19-AUG


def test_screen_mcx_commodities_emits_dated_fut_symbols(monkeypatch):
    from trading.screener import commodities as C

    monkeypatch.setattr(C, "_broker", lambda: FakeMCXClient())
    monkeypatch.setattr(C, "MCX_UNDERLYINGS", ["GOLD", "CRUDEOIL"])
    out = C.screen_mcx_commodities(limit=5)
    syms = [c["symbol"] for c in out]
    assert syms == ["GOLD05AUG26FUT", "CRUDEOIL20JUL26FUT"]
    assert all(c["segment"] == "commodities" and c["market"] == "NSE" for c in out)
    # a bare base name must NEVER be emitted (that was the 400 "not found" bug)
    assert "GOLD" not in syms and "CRUDEOIL" not in syms
