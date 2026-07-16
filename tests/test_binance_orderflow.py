"""tests/test_binance_orderflow.py — Binance-computed order-flow feature pack.

Offline: monkeypatch _get_json (never the network) with synthetic /futures/data responses, and
seed the in-RAM mirror with synthetic funding + liquidations. Asserts the feature pack + tilt.
"""
import time
import unittest
from unittest import mock

from trading.broker_sense import binance_orderflow as of
from trading.broker_sense.binance_stream import get_mirror


def _fake_rest(url: str):
    if "globalLongShortAccountRatio" in url:
        return [{"longShortRatio": "1.5", "longAccount": "0.60", "shortAccount": "0.40"}]
    if "topLongShortAccountRatio" in url:
        return [{"longShortRatio": "1.2", "longAccount": "0.55"}]
    if "topLongShortPositionRatio" in url:
        return [{"longShortRatio": "0.8", "longAccount": "0.44"}]
    if "takerlongshortRatio" in url:
        return [{"buySellRatio": "1.30"}]
    if "openInterestHist" in url:
        return [{"sumOpenInterestValue": "1000000"}, {"sumOpenInterestValue": "1100000"}]
    return None


class TestOrderFlow(unittest.TestCase):
    def setUp(self):
        of.clear_cache()
        # isolate from any REAL captured app data (2026-07-16): ui_market hydrates its store
        # from the live snapshot file, which flips features() source to 'ui:capture' — this
        # suite tests the mirror+REST path, so the capture store must be empty and stay empty.
        from trading.broker_sense import ui_market
        ui_market._STORE.clear()
        ui_market._LIQS.clear()
        self._hyd = mock.patch.object(ui_market, "_hydrate_from_snapshot", lambda: None)
        self._hyd.start()
        self.addCleanup(self._hyd.stop)
        self.addCleanup(ui_market._STORE.clear)
        # isolate from the LIVE UI-only governor (2026-07-16): ui_data.enabled() reads the durable
        # state file trading/state/ui_only_mode.json, which the running brain FLIPS BY ITSELF. When
        # it is on, features() returns before the /futures/data steps and this suite's REST
        # assertions vanish (KeyError: crowd_long_pct) — a green/red result that depends on what
        # production happened to decide a minute ago. This suite tests the mirror+REST path, so the
        # flag is pinned OFF here rather than inherited.
        self._uio = mock.patch.object(of, "_ui_only", lambda: False)
        self._uio.start()
        self.addCleanup(self._uio.stop)
        # seed the mirror with a funding + two liquidations for BTCUSDT.
        # get_mirror() is a process-wide SINGLETON: since RAM became primary (2026-07-16) this
        # seed OUTRANKS any capture, so leaving it behind silently breaks other suites' capture
        # tests when they run in the same process. Always undo it.
        m = get_mirror()
        m._mark["BTCUSDT"] = {"mark": 64000.0, "funding_rate": 0.0001,
                              "next_funding_ts": int((time.time() + 3600) * 1000), "ts": time.time()}
        self.addCleanup(lambda: m._mark.pop("BTCUSDT", None))
        self.addCleanup(m._liqs.clear)
        m._liqs.clear()
        m._liqs.append({"symbol": "BTCUSDT", "side": "SELL", "qty": 2.0, "price": 64000.0, "ts": time.time()})
        m._liqs.append({"symbol": "BTCUSDT", "side": "BUY", "qty": 1.0, "price": 64000.0, "ts": time.time()})

    def test_features_are_binance_read_not_computed(self):
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("btcusdt")
        # provenance is explicit since the 2026-07-16 motto rewrite: RAM is primary, so a
        # mirror-served funding reads 'ram:mirror' (was the generic 'binance')
        self.assertEqual(f["source"], "ram:mirror")
        self.assertEqual(f["funding_rate"], 0.0001)               # from mirror
        self.assertAlmostEqual(f["crowd_long_pct"], 0.60)         # retail crowd
        self.assertAlmostEqual(f["smart_long_pct"], 0.44)         # top-trader position
        self.assertAlmostEqual(f["taker_buy_sell_ratio"], 1.30)   # aggressor flow
        self.assertAlmostEqual(f["oi_change_pct"], 10.0)          # (1.1M-1.0M)/1.0M
        # liquidation skew: long_liq=2*64000, short_liq=1*64000 → (128000-64000)/192000
        self.assertAlmostEqual(f["liq_skew"], round((128000 - 64000) / 192000, 4))

    def test_ram_mirror_wins_over_browser_capture(self):
        """MOTTO tenet 3 (owner 2026-07-16): RAM is PRIMARY. When BOTH the mirror and the app
        capture carry funding, the mirror's value must win — the browser's per-symbol data is
        stale far past TTL in production (measured 25-44 h median), so it must never override
        the live push stream."""
        from trading.broker_sense import ui_market
        ui_market._STORE[("mark_price", "BTCUSDT")] = {
            "ts": time.time(), "broker": "binance", "url": "",
            "data": {"funding_rate": 0.9999, "mark": 1.0},      # deliberately absurd capture value
        }
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("BTCUSDT")
        self.assertEqual(f["source"], "ram:mirror")
        self.assertEqual(f["funding_rate"], 0.0001)             # mirror's, NOT the capture's
        self.assertEqual(f["mark"], 64000.0)

    def test_browser_capture_fills_only_what_ram_lacks(self):
        """The fallback half of the same tenet: the all-market streams do NOT carry open
        interest, so the app capture must still serve it — and a mirror miss on funding must
        fall back to the capture rather than returning None."""
        from trading.broker_sense import ui_market
        m = get_mirror()
        m._mark.pop("BTCUSDT", None)                            # RAM has no funding for this symbol
        ui_market._STORE[("mark_price", "BTCUSDT")] = {
            "ts": time.time(), "broker": "binance", "url": "",
            "data": {"funding_rate": 0.0007, "mark": 63000.0},
        }
        ui_market._STORE[("open_interest", "BTCUSDT")] = {
            "ts": time.time(), "broker": "binance", "url": "",
            "data": {"open_interest": 1234567.0},               # a kind RAM never carries
        }
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("BTCUSDT")
        self.assertEqual(f["source"], "ui:capture")             # RAM missed → browser served
        self.assertEqual(f["funding_rate"], 0.0007)
        self.assertEqual(f["open_interest_usd"], 1234567.0)     # capture beat the REST backfill

    def test_taker_ratio_derived_from_aggtrade_push_no_api(self):
        """Owner 2026-07-16: 'find a way other than the API'. Taker flow HAS one — `@aggTrade`
        carries m ('was the buyer the maker?'), so m=False → taker BUY and m=True → taker SELL.
        That is Binance's own takerlongshortRatio quantity, derived from the venue's trade push
        with ZERO REST calls (open interest and long/short have no such stream)."""
        m = get_mirror()
        m._taker.clear()
        for m_flag, qty in ((False, 3.0), (False, 1.0), (True, 2.0)):    # 4 taker-buy vs 2 sell
            m._apply_agg_frame({"stream": "btcusdt@aggTrade",
                                "data": {"s": "BTCUSDT", "q": str(qty), "p": "100.0",
                                         "m": m_flag}})
        self.addCleanup(m._taker.clear)
        t = m.taker("BTCUSDT")
        self.assertEqual(t["source"], "ram:aggtrade")
        self.assertAlmostEqual(t["buy_sell_ratio"], 2.0)                 # 400 notional / 200
        # and features() must PREFER it over the REST value (_fake_rest says 1.30)
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("BTCUSDT")
        self.assertAlmostEqual(f["taker_buy_sell_ratio"], 2.0)
        self.assertEqual(f["taker_source"], "ram:aggtrade")

    def test_taker_one_sided_window_is_honest_not_invented(self):
        """A window with taker buys but NO taker sells makes buy/sell undefined. Report None and
        let the caller fall back — never invent a cap. `imbalance` still carries the signal."""
        m = get_mirror()
        m._taker.clear()
        self.addCleanup(m._taker.clear)
        m._apply_agg_frame({"stream": "btcusdt@aggTrade",
                            "data": {"s": "BTCUSDT", "q": "2.0", "p": "100.0", "m": False}})
        t = m.taker("BTCUSDT")
        self.assertIsNone(t["buy_sell_ratio"])          # undefined → honest None
        self.assertAlmostEqual(t["imbalance"], 1.0)     # but the one-sidedness IS reported
        self.assertEqual(t["taker_sell_notional"], 0.0)

    def test_stats_poller_ram_beats_rest_and_capture(self):
        """OI + long/short are the only kinds with no WS stream, so a background poller fills RAM
        and the DECISION path stays pure-RAM (no REST round-trip when the brain decides)."""
        m = get_mirror()
        # a COMPLETE row, as the poller writes it — every field features() would otherwise REST
        # for. (An incomplete row correctly still falls back to REST for the missing kinds.)
        m._stats["BTCUSDT"] = {"ts": time.time(), "source": "ram:stats",
                               "open_interest_usd": 5_000_000.0, "oi_change_pct": 2.5,
                               "crowd_long_short": 1.9, "crowd_long_pct": 0.71,
                               "smart_pos_long_short": 0.5, "smart_long_pct": 0.33,
                               "smart_acct_long_short": 1.1}
        m._taker.clear()
        for m_flag in (False, True):        # BOTH sides: a window with zero taker sells leaves
            m._apply_agg_frame({"stream": "btcusdt@aggTrade",      # buy_sell_ratio undefined
                                "data": {"s": "BTCUSDT", "q": "2.0", "p": "100.0", "m": m_flag}})
        self.addCleanup(m._stats.clear)
        self.addCleanup(m._taker.clear)
        with mock.patch.object(of, "_get_json",
                               side_effect=AssertionError("REST must not run when RAM has it")):
            f = of.features("BTCUSDT")
        self.assertEqual(f["open_interest_usd"], 5_000_000.0)   # RAM, not the REST 1.1M
        self.assertAlmostEqual(f["oi_change_pct"], 2.5)
        self.assertAlmostEqual(f["crowd_long_pct"], 0.71)       # RAM, not the REST 0.60
        self.assertAlmostEqual(f["smart_long_pct"], 0.33)       # RAM, not the REST 0.44

    def test_stale_stats_are_an_honest_miss(self):
        m = get_mirror()
        m._stats["BTCUSDT"] = {"ts": time.time() - 99_999, "open_interest_usd": 1.0}
        self.addCleanup(m._stats.clear)
        self.assertIsNone(m.stats("BTCUSDT"))                   # past TTL → never served as fresh

    def test_browser_capture_never_clobbers_a_ram_value(self):
        """The inversion this whole rewrite exists to prevent: a 25-44 h stale page value must
        never overwrite a live push-stream value."""
        from trading.broker_sense import ui_market
        m = get_mirror()
        m._stats["BTCUSDT"] = {"ts": time.time(), "open_interest_usd": 5_000_000.0}
        self.addCleanup(m._stats.clear)
        ui_market._STORE[("open_interest", "BTCUSDT")] = {
            "ts": time.time(), "broker": "binance", "url": "",
            "data": {"open_interest": 42.0},                    # the stale page number
        }
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("BTCUSDT")
        self.assertEqual(f["open_interest_usd"], 5_000_000.0)   # RAM held

    def test_signal_tilt_in_range_and_directional(self):
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            s = of.signal("BTCUSDT")
        self.assertIsNotNone(s["tilt"])
        self.assertGreaterEqual(s["tilt"], -1.0)
        self.assertLessEqual(s["tilt"], 1.0)
        self.assertGreater(s["n_signals"], 0)

    def test_ttl_cache_avoids_refetch(self):
        calls = {"n": 0}

        def counting(url):
            calls["n"] += 1
            return _fake_rest(url)

        with mock.patch.object(of, "_get_json", side_effect=counting):
            of.features("BTCUSDT")
            n1 = calls["n"]
            of.features("BTCUSDT")           # second call within TTL → served from cache
            self.assertEqual(calls["n"], n1)  # no additional REST calls

    def test_disabled_and_missing_are_honest(self):
        import os
        os.environ["BINANCE_ORDERFLOW"] = "0"
        try:
            self.assertFalse(of.features("BTCUSDT")["enabled"])
        finally:
            os.environ.pop("BINANCE_ORDERFLOW", None)
        # a symbol with no data → no crash, keys simply absent
        with mock.patch.object(of, "_get_json", return_value=None):
            f = of.features("NOTREAL")
            self.assertEqual(f["symbol"], "NOTREAL")
            self.assertNotIn("crowd_long_pct", f)


if __name__ == "__main__":
    unittest.main()
