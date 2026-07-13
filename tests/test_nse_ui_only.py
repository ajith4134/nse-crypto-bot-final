"""Tests for NSE_UI_ONLY — the hard, NSE-scoped UI-only data mode (owner 2026-07-13, motto).

Under NSE_UI_ONLY=1 every NSE market-data read comes ONLY from the Upstox web UI captures
(ui_market / ui_data) and ABSTAINS (honest None / empty) on a miss — never a broker/data API
(OpenAlgo, nselib). Crypto is unaffected; execution (OpenAlgo orders) is out of scope here.
Default OFF, so the API paths are preserved when the flag is not set.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

from trading import state
from trading.broker_sense import ui_data, ui_market


class _Iso(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("NSE_UI_ONLY")
        os.environ["NSE_UI_ONLY"] = "1"
        os.environ.pop("UI_ONLY_DATA", None)          # keep the GLOBAL governor out of it
        # isolate STATE_DIR so ui_market never hydrates the LIVE snapshot (real captures) and
        # our reads/writes never touch production state (isolate-state-in-tests).
        self._state_dir = state.STATE_DIR
        self._tmp = tempfile.mkdtemp()
        state.STATE_DIR = Path(self._tmp)
        self._store_backup = dict(ui_market._STORE)
        self._hits_backup = dict(ui_market._HITS)     # our _feed_ticker sets fed=1; restore it
        ui_market._STORE.clear()

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("NSE_UI_ONLY", None)
        else:
            os.environ["NSE_UI_ONLY"] = self._prev
        state.STATE_DIR = self._state_dir
        ui_market._STORE.clear()
        ui_market._STORE.update(self._store_backup)
        ui_market._HITS.clear()
        ui_market._HITS.update(self._hits_backup)
        # our reads call _hydrate_from_snapshot, which throttles via this module global —
        # reset it so a following test's hydration isn't skipped (test isolation).
        for g in ("_last_hydrate", "_last_snap"):
            if hasattr(ui_market, g):
                setattr(ui_market, g, 0.0)

    def _feed_ticker(self, sym, pct, last):
        ui_market._STORE[("ticker", sym)] = {
            "data": {"pct_change": pct, "last": last}, "ts": time.time(),
            "url": "u", "broker": "upstox"}
        ui_market._HITS["fed"] = 1


class TestGate(_Iso):
    def test_nse_scoped_not_crypto(self):
        # NSE_UI_ONLY gates NSE only; it must NOT force crypto into UI-only by itself.
        os.environ.pop("UI_ONLY_DATA", None)
        # (the durable global flag may be on in the live env, but the NSE gate itself is scoped)
        self.assertTrue(ui_data.nse_ui_only())
        self.assertTrue(ui_data.ui_only_for("NSE"))
        self.assertTrue(ui_data.ui_only_for("BSE"))


class TestDataFailsafeNSE(_Iso):
    def test_nse_abstains_and_never_calls_openalgo(self):
        import trading.openalgo_client as oac
        from trading.broker_sense import data_failsafe as df
        orig = oac.OpenAlgoClient

        class _Boom:
            def __init__(self, *a, **k):
                raise AssertionError("OpenAlgo must not be called under NSE_UI_ONLY")
        oac.OpenAlgoClient = _Boom
        try:
            self.assertIsNone(df.quote("RELIANCE", "nse"))
            self.assertIsNone(df.ohlcv("RELIANCE", "nse", timeframe="5m", limit=5))
            self.assertIsNone(df.top_of_book("RELIANCE", "nse"))
        finally:
            oac.OpenAlgoClient = orig

    def test_nse_serves_ui_capture(self):
        from trading.broker_sense import data_failsafe as df
        self._feed_ticker("RELIANCE", 2.4, 2900.0)
        q = df.quote("RELIANCE", "nse")
        self.assertIsNotNone(q)
        self.assertEqual(q["last"], 2900.0)
        self.assertEqual(q["source"], "ui:capture")


class TestScreenerNSE(_Iso):
    def test_candidates_from_ui_movers_and_exclude_crypto(self):
        from trading.screener.screener import Screener
        self._feed_ticker("RELIANCE", 2.4, 2900.0)
        self._feed_ticker("TCS", -1.8, 3800.0)
        self._feed_ticker("BTCUSDT", 5.0, 60000.0)     # crypto — must be excluded
        sc = Screener(nse_source=None, crypto_source=None)
        cands = sc.candidates("NSE", "intraday", limit=5)
        syms = [c["symbol"] for c in cands]
        self.assertIn("RELIANCE", syms)
        self.assertNotIn("BTCUSDT", syms)
        self.assertTrue(all(c["metrics"]["source"] == "ui:upstox-movers" for c in cands))

    def test_hard_abstain_no_stub_when_empty(self):
        from trading.screener.screener import Screener
        sc = Screener(nse_source=None, crypto_source=None)
        cands = sc.candidates("NSE", "intraday", limit=5)   # no UI coverage fed
        self.assertEqual(cands, [])                          # abstain, NOT the fake stub
        self.assertEqual(sc._last.get("NSE:intraday"), "ui-abstain")


class TestOptionsNSE(_Iso):
    def test_abstains_without_ui_option_chain(self):
        from trading.screener import options as O

        class _Cli:
            def search(self, query, exchange="NFO"):
                return [{"symbol": f"{query}25000CE", "strike": 25000,
                         "expiry": "2026-07-31", "opt_type": "CE"}]

            def quotes(self, exchange, symbol):
                raise AssertionError("no OpenAlgo quote under NSE_UI_ONLY")
        O._broker = lambda: _Cli()
        self.assertEqual(O.screen_nse_options(None, limit=5), [])   # no UI chain → abstain

    def test_uses_ui_ltp_when_chain_present(self):
        from trading.screener import options as O

        class _Cli:
            def search(self, query, exchange="NFO"):
                return [{"symbol": f"{query}25000CE", "strike": 25000,
                         "expiry": "2026-07-31", "opt_type": "CE"}]

            def quotes(self, exchange, symbol):
                raise AssertionError("no OpenAlgo quote under NSE_UI_ONLY")
        O._broker = lambda: _Cli()
        ui_market._STORE[("option_chain", "NIFTY")] = {
            "data": {"greeks": {"delta": 0.5}}, "ts": time.time(), "url": "u", "broker": "upstox"}
        ui_market._STORE[("ticker", "NIFTY")] = {
            "data": {"last": 25010.0}, "ts": time.time(), "url": "u", "broker": "upstox"}
        ui_market._HITS["fed"] = 1
        out = O.screen_nse_options(None, limit=5)
        self.assertTrue(out)
        self.assertEqual(out[0]["metrics"]["ltp"], 25010.0)         # UI-sourced LTP


if __name__ == "__main__":
    unittest.main()
