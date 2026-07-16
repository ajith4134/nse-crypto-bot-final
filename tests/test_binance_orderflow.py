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
        # seed the mirror with a funding + two liquidations for BTCUSDT
        m = get_mirror()
        m._mark["BTCUSDT"] = {"mark": 64000.0, "funding_rate": 0.0001,
                              "next_funding_ts": int((time.time() + 3600) * 1000), "ts": time.time()}
        m._liqs.clear()
        m._liqs.append({"symbol": "BTCUSDT", "side": "SELL", "qty": 2.0, "price": 64000.0, "ts": time.time()})
        m._liqs.append({"symbol": "BTCUSDT", "side": "BUY", "qty": 1.0, "price": 64000.0, "ts": time.time()})

    def test_features_are_binance_read_not_computed(self):
        with mock.patch.object(of, "_get_json", side_effect=_fake_rest):
            f = of.features("btcusdt")
        self.assertEqual(f["source"], "binance")
        self.assertEqual(f["funding_rate"], 0.0001)               # from mirror
        self.assertAlmostEqual(f["crowd_long_pct"], 0.60)         # retail crowd
        self.assertAlmostEqual(f["smart_long_pct"], 0.44)         # top-trader position
        self.assertAlmostEqual(f["taker_buy_sell_ratio"], 1.30)   # aggressor flow
        self.assertAlmostEqual(f["oi_change_pct"], 10.0)          # (1.1M-1.0M)/1.0M
        # liquidation skew: long_liq=2*64000, short_liq=1*64000 → (128000-64000)/192000
        self.assertAlmostEqual(f["liq_skew"], round((128000 - 64000) / 192000, 4))

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
