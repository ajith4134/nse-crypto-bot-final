"""Tests for trading/direction/micro_features — D4 microstructure direction lanes."""
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


def _feather(root: Path, rel: str, col_open=None, closes=None, hours=False):
    import pandas as pd
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    n = len(col_open or closes)
    step = 3600 if hours else 300
    t0 = int(time.time()) - step * n
    data = {"date": pd.to_datetime([(t0 + i * step) * 10**9 for i in range(n)],
                                   utc=True)}
    if col_open is not None:
        data.update(open=[float(x) for x in col_open], high=[0.0] * n,
                    low=[0.0] * n, close=[0.0] * n, volume=[0.0] * n)
    else:
        data["close"] = [float(x) for x in closes]
    pd.DataFrame(data).to_feather(p)


class _Iso(unittest.TestCase):
    def setUp(self):
        import os
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self._c = tempfile.TemporaryDirectory()
        os.environ["DIRECTION_CANDLE_DIR"] = self._c.name
        os.environ["MULTI_VENUE_POOL"] = "0"               # no network in tests
        from trading.direction import micro_features as mf
        from trading.direction import truth_ledger as tl
        tl._CANDLE_CACHE.clear()
        mf._venue_cache.clear()
        self.mf = mf

    def tearDown(self):
        import os
        state.STATE_DIR = self._o
        for k in ("DIRECTION_CANDLE_DIR", "MULTI_VENUE_POOL"):
            os.environ.pop(k, None)
        self._t.cleanup()
        self._c.cleanup()


class TestFundingExtreme(_Iso):
    def test_crowded_longs_vote_short(self):
        rates = [0.0001] * 30 + [0.0009]                   # last is a huge outlier
        _feather(Path(self._c.name),
                 "futures/ETH_USDT_USDT-1h-funding_rate.feather",
                 col_open=rates, hours=True)
        r = self.mf.funding_extreme("ETH/USDT:USDT")
        self.assertEqual(r["vote"], "SHORT")
        self.assertGreater(r["funding_z"], 1.0)

    def test_normal_funding_no_vote(self):
        base = [0.0001, 0.00012, 0.00008, 0.00011] * 8
        _feather(Path(self._c.name),
                 "futures/ETH_USDT_USDT-1h-funding_rate.feather",
                 col_open=base, hours=True)
        self.assertIsNone(self.mf.funding_extreme("ETH/USDT:USDT")["vote"])

    def test_missing_feather_honest_none(self):
        self.assertIsNone(self.mf.funding_extreme("NOPE/USDT:USDT")["funding_z"])


class TestMtfAgree(_Iso):
    def test_all_frames_up_votes_long(self):
        root = Path(self._c.name)
        _feather(root, "futures/SOL_USDT_USDT-5m-futures.feather",
                 closes=[100 + i for i in range(60)])
        for tf in ("15m", "1h", "4h"):
            _feather(root, f"futures/SOL_USDT_USDT-{tf}-futures.feather",
                     closes=[100 + i for i in range(40)])
        r = self.mf.mtf_agree("SOL/USDT:USDT")
        self.assertEqual(r["vote"], "LONG")
        self.assertEqual(len(r["frames"]), 3)

    def test_disagreement_no_vote(self):
        root = Path(self._c.name)
        _feather(root, "futures/SOL_USDT_USDT-5m-futures.feather",
                 closes=[100 + i for i in range(60)])
        _feather(root, "futures/SOL_USDT_USDT-15m-futures.feather",
                 closes=[100 + i for i in range(40)])      # up
        _feather(root, "futures/SOL_USDT_USDT-1h-futures.feather",
                 closes=[200 - i for i in range(40)])      # down
        self.assertIsNone(self.mf.mtf_agree("SOL/USDT:USDT")["vote"])


class TestRecordClaims(_Iso):
    def test_offline_claims_recorded_to_ledger(self):
        root = Path(self._c.name)
        _feather(root, "futures/ETH_USDT_USDT-1h-funding_rate.feather",
                 col_open=[0.0001] * 30 + [0.0009], hours=True)
        _feather(root, "futures/ETH_USDT_USDT-5m-futures.feather",
                 closes=[100 + i for i in range(60)])
        for tf in ("15m", "1h", "4h"):
            _feather(root, f"futures/ETH_USDT_USDT-{tf}-futures.feather",
                     closes=[100 + i for i in range(40)])
        rep = self.mf.record_claims(["ETH/USDT:USDT"], include_network=False)
        self.assertEqual(rep["symbols"], 1)
        self.assertEqual(rep["by_lane"],
                         {"funding_extreme": 1, "mtf_agree": 1})
        import json
        pend = (Path(state.STATE_DIR) / "direction_truth_pending.jsonl").read_text()
        sources = {json.loads(x)["source"] for x in pend.splitlines()}
        self.assertEqual(sources, {"funding_extreme", "mtf_agree"})

    def test_kill_switch(self):
        import os
        os.environ["MICRO_FEATURES"] = "0"
        try:
            rep = self.mf.record_claims(["ETH/USDT:USDT"], include_network=False)
            self.assertEqual(rep["claims"], 0)
        finally:
            os.environ.pop("MICRO_FEATURES")

    def test_venue_gap_disabled_pool_is_honest(self):
        r = self.mf.venue_gap("BTC/USDT:USDT")
        self.assertIsNone(r["vote"])
        self.assertEqual(r["n_venues"], 0)


if __name__ == "__main__":
    unittest.main()
