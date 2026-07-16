"""tests/test_nse_ram_first_reads.py — NSE selection reads off the Zerodha Kite in-RAM mirror.

Proves the owner's 2026-07-14 wiring: with the Kite mirror WARM, the three NSE consumers
(screener quote, psychology depth, stock X-Ray) serve from RAM and make ZERO OpenAlgo calls;
with the mirror COLD, they honour the honest-fallback rule — abstain under NSE_UI_ONLY (still no
API), else fall back to the OpenAlgo REST. No socket, no kiteconnect, no network.
"""
import os
import time
import unittest


class _FakeOA:
    """Recording stand-in for trading.openalgo_client.OpenAlgoClient (quotes/depth)."""
    calls: list = []

    def __init__(self, *a, **k):
        pass

    def _client(self):
        return self

    def quotes(self, exchange=None, symbol=None):
        _FakeOA.calls.append(("quotes", symbol))
        return {"data": {"ltp": 111.0, "prev_close": 110.0, "volume": 9.0}}

    def depth(self, symbol=None, exchange=None):
        _FakeOA.calls.append(("depth", symbol))
        return {"data": {"ltp": 10.5, "prev_close": 10.0,
                         "bids": [{"price": 10.0, "quantity": 5}],
                         "asks": [{"price": 11.0, "quantity": 6}]}}


def _force_global_ui_off():
    os.environ["UI_ONLY_DATA"] = "0"
    os.environ["UI_ONLY_DATA_FORCE_ENV"] = "1"


class _Base(unittest.TestCase):
    def setUp(self):
        import trading.broker_sense.kite_stream as ks
        import trading.openalgo_client as oac
        self.ks = ks
        self.oac = oac
        self._saved_env = {k: os.environ.get(k) for k in
                           ("KITE_STREAM", "NSE_UI_ONLY", "UI_ONLY_DATA", "UI_ONLY_DATA_FORCE_ENV")}
        self._saved_cls = oac.OpenAlgoClient
        os.environ["KITE_STREAM"] = "1"
        _force_global_ui_off()
        _FakeOA.calls = []
        oac.OpenAlgoClient = _FakeOA
        ks._MIRROR = None
        self.m = ks.get_kite_mirror()

    def tearDown(self):
        self.oac.OpenAlgoClient = self._saved_cls
        self.ks._MIRROR = None
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _warm(self, sym="RELIANCE"):
        with self.m._lock:
            self.m._ltp[sym] = {"last": 2500.0, "pct_change": 0.8, "high": 2520.0, "low": 2480.0,
                                "open": 2490.0, "close": 2480.0, "volume": 1000.0, "oi": 0.0,
                                "ts": time.time()}
            self.m._book[sym] = {"bids": [[2499.0, 100.0]], "asks": [[2501.0, 120.0]],
                                 "ts": time.time()}


class TestScreenerQuoteRamFirst(_Base):
    def test_warm_ram_serves_no_api(self):
        from trading.screener.sources import LiveNSESource
        self._warm()
        q = LiveNSESource()._oa_quote("RELIANCE", "NSE")
        self.assertEqual(q, {"data": {"ltp": 2500.0, "prev_close": 2480.0, "volume": 1000.0}})
        self.assertEqual(_FakeOA.calls, [])                    # OpenAlgo never touched

    def test_cold_ui_only_abstains_no_api(self):
        from trading.screener.sources import LiveNSESource
        os.environ["NSE_UI_ONLY"] = "1"
        q = LiveNSESource()._oa_quote("ZZUNKNOWN", "NSE")
        self.assertIsNone(q)                                   # honest miss → abstain
        self.assertEqual(_FakeOA.calls, [])                    # still zero API

    def test_cold_not_ui_only_falls_back_to_api(self):
        from trading.screener.sources import LiveNSESource
        os.environ["NSE_UI_ONLY"] = "0"
        q = LiveNSESource()._oa_quote("ZZUNKNOWN", "NSE")
        self.assertEqual(q, {"data": {"ltp": 111.0, "prev_close": 110.0, "volume": 9.0}})
        self.assertIn(("quotes", "ZZUNKNOWN"), _FakeOA.calls)  # fallback path taken

    def test_liquid_movers_uses_ram(self):
        from trading.screener.sources import LiveNSESource
        self._warm("RELIANCE")
        with self.m._lock:
            self.m._ltp["INFY"] = {"last": 1500.0, "close": 1490.0, "volume": 2000.0,
                                   "high": 1510.0, "low": 1480.0, "ts": time.time()}
        movers = LiveNSESource().liquid_movers(limit=50)
        syms = {r["symbol"] for r in movers}
        self.assertTrue({"RELIANCE", "INFY"} & syms)
        self.assertEqual(_FakeOA.calls, [])                    # whole ranking off RAM


class TestPsychologyDepthRamFirst(_Base):
    def test_warm_ram_book_no_api(self):
        from trading.brain.psychology import TraderPsychology, BookSnapshot
        self._warm()
        tp = TraderPsychology(record=False)
        tp._nse_client = lambda: (_ for _ in ()).throw(AssertionError("OpenAlgo must not be called"))
        snap = tp.fetch_snapshot("NSE", "RELIANCE")
        self.assertIsInstance(snap, BookSnapshot)
        self.assertEqual(snap.bids[0], (2499.0, 100.0))
        self.assertEqual(snap.asks[0], (2501.0, 120.0))

    def test_cold_ui_only_abstains(self):
        from trading.brain.psychology import TraderPsychology
        os.environ["NSE_UI_ONLY"] = "1"
        tp = TraderPsychology(record=False)
        tp._nse_client = lambda: (_ for _ in ()).throw(AssertionError("OpenAlgo must not be called"))
        self.assertIsNone(tp.fetch_snapshot("NSE", "ZZUNKNOWN"))

    def test_cold_not_ui_only_falls_back(self):
        from trading.brain.psychology import TraderPsychology, BookSnapshot
        os.environ["NSE_UI_ONLY"] = "0"
        tp = TraderPsychology(record=False)
        snap = tp.fetch_snapshot("NSE", "ZZUNKNOWN")           # cold RAM → OpenAlgo depth
        self.assertIsInstance(snap, BookSnapshot)
        self.assertIn(("depth", "ZZUNKNOWN"), _FakeOA.calls)


class TestXrayQuoteRamFirst(_Base):
    def test_warm_ram_quote_depth_no_api(self):
        import trading.broker_sense.stock_xray as xr

        class _XrayOA:
            depth_called = False

            def depth(self, symbol, exchange="NSE"):
                _XrayOA.depth_called = True
                return {"data": {}}

            def history(self, *a, **k):
                return {"data": []}                            # no deep history in the test

        saved = xr._oa
        xr._oa = lambda: _XrayOA()
        try:
            self._warm()
            snap = xr.capture("RELIANCE", "NSE", "intraday")
            self.assertIn("kite:mirror", snap["sources"])
            self.assertIn("depth", snap)
            self.assertEqual(snap["quote"]["ltp"], 2500.0)
            self.assertFalse(_XrayOA.depth_called)             # live quote/depth came from RAM
        finally:
            xr._oa = saved


if __name__ == "__main__":
    unittest.main()
