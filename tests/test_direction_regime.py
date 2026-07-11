"""Tests for trading/direction/regime — D5 direction regime classifier."""
import math
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self._c = tempfile.TemporaryDirectory()
        import os
        os.environ["DIRECTION_CANDLE_DIR"] = self._c.name
        from trading.direction import regime
        from trading.direction import truth_ledger as tl
        tl._CANDLE_CACHE.clear()
        self.rg = regime

    def tearDown(self):
        import os
        state.STATE_DIR = self._o
        os.environ.pop("DIRECTION_CANDLE_DIR", None)
        self._t.cleanup()
        self._c.cleanup()


class TestClassifyCloses(_Iso):
    def test_steady_rise_is_trend_up(self):
        closes = [100 + i for i in range(60)]              # ER = 1.0
        self.assertEqual(self.rg._classify_closes(closes)["regime"], "trend_up")

    def test_steady_fall_is_trend_down(self):
        closes = [200 - i for i in range(60)]
        self.assertEqual(self.rg._classify_closes(closes)["regime"], "trend_down")

    def test_oscillation_is_chop(self):
        closes = [100 + 3 * math.sin(i / 2.0) for i in range(80)]
        r = self.rg._classify_closes(closes)
        self.assertEqual(r["regime"], "chop")
        self.assertLess(r["er"], 0.35)

    def test_state_change_is_transition(self):
        closes = ([100 + 3 * math.sin(i / 2.0) for i in range(24)]   # chop half…
                  + [100 + i * 1.5 for i in range(24)])              # …then hard trend
        self.assertEqual(self.rg._classify_closes(closes)["regime"], "transition")

    def test_too_short_is_unknown(self):
        self.assertEqual(self.rg._classify_closes([1, 2, 3])["regime"], "unknown")


class TestClassifyIO(_Iso):
    def _feather(self, rel: str, closes):
        import pandas as pd
        p = Path(self._c.name) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        t0 = int(time.time()) - 300 * len(closes)
        pd.DataFrame({"date": pd.to_datetime([(t0 + i * 300) * 10**9
                                              for i in range(len(closes))], utc=True),
                      "close": [float(c) for c in closes]}).to_feather(p)

    def test_symbol_feather_used_and_cached(self):
        self._feather("futures/ETH_USDT_USDT-5m-futures.feather",
                      [100 + i for i in range(60)])
        r = self.rg.classify("ETH/USDT:USDT")
        self.assertEqual(r["regime"], "trend_up")
        self.assertEqual(r["basis"], "symbol")
        r2 = self.rg.classify("ETH/USDT:USDT")             # served from 60s cache
        self.assertEqual(r2["ts"], r["ts"])

    def test_falls_back_to_market_then_unknown(self):
        self._feather("futures/BTC_USDT_USDT-5m-futures.feather",
                      [200 - i for i in range(60)])
        r = self.rg.classify("NOFEATHER/USDT:USDT")
        self.assertEqual(r["regime"], "trend_down")
        self.assertEqual(r["basis"], "market")
        self.assertEqual(self.rg.market_regime(), "trend_down")

    def test_stale_candles_are_not_trusted(self):
        import pandas as pd
        p = Path(self._c.name) / "futures/BTC_USDT_USDT-5m-futures.feather"
        p.parent.mkdir(parents=True, exist_ok=True)
        t0 = int(time.time()) - 10 * 3600                  # 10h-old data
        pd.DataFrame({"date": pd.to_datetime([(t0 + i * 300) * 10**9
                                              for i in range(60)], utc=True),
                      "close": [100.0 + i for i in range(60)]}).to_feather(p)
        self.assertEqual(self.rg.classify(None)["regime"], "unknown")


if __name__ == "__main__":
    unittest.main()
