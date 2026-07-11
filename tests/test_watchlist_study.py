"""Tests for trading/broker_sense/watchlist_study — W watchlist study funnel."""
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


class _FakeReader:
    """Stands in for fast_candles/vision: multi-TF chart reads with fixed p_up."""
    def __init__(self, p_up):
        self.p_up = p_up

    def read(self, picks, market, timeframes=(), deadline=None):
        return {p["symbol"]: {tf: {"p_up": self.p_up, "source": "fake"}
                              for tf in timeframes} for p in picks}


class _Iso(unittest.TestCase):
    def setUp(self):
        import os
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self._c = tempfile.TemporaryDirectory()
        os.environ["DIRECTION_CANDLE_DIR"] = self._c.name
        os.environ["MULTI_VENUE_POOL"] = "0"
        from trading.broker_sense import watchlist_study as ws
        from trading.direction import truth_ledger as tl
        tl._CANDLE_CACHE.clear()
        self.ws = ws

    def tearDown(self):
        import os
        state.STATE_DIR = self._o
        for k in ("DIRECTION_CANDLE_DIR", "MULTI_VENUE_POOL"):
            os.environ.pop(k, None)
        self._t.cleanup()
        self._c.cleanup()


class TestPropose(_Iso):
    def test_admits_up_to_cap_and_exposes_set(self):
        rep = self.ws.propose([f"S{i}/USDT:USDT" for i in range(10)],
                              market="crypto", segment="futures")
        self.assertEqual(len(rep["added"]), 6)             # STUDY_MAX default
        self.assertEqual(len(self.ws.study_symbols("crypto")), 6)
        self.assertEqual(self.ws.study_symbols("nse"), [])

    def test_studied_and_gone_symbol_is_dropped(self):
        self.ws.propose(["A/USDT:USDT"], market="crypto", segment="futures")
        def _mark(d):
            d["set"]["A/USDT:USDT"]["studied"] = True
            return d
        state.mutate_json("watchlist_study.json", _mark, default={})
        rep = self.ws.propose(["B/USDT:USDT"], market="crypto", segment="futures")
        self.assertIn("A/USDT:USDT", rep["dropped"])       # studied + not a candidate
        self.assertIn("B/USDT:USDT", rep["added"])

    def test_stale_entry_expires(self):
        self.ws.propose(["A/USDT:USDT"], market="crypto", segment="futures")
        def _age(d):
            d["set"]["A/USDT:USDT"]["ts"] = time.time() - 300 * 60
            return d
        state.mutate_json("watchlist_study.json", _age, default={})
        rep = self.ws.propose([], market="crypto", segment="futures")
        self.assertIn("A/USDT:USDT", rep["dropped"])


_NO_FUSION = {"available": False}


class TestStudyRound(_Iso):
    def test_studies_records_claim_and_marks_done(self):
        import json
        from unittest.mock import patch
        self.ws.propose(["ETH/USDT:USDT"], market="crypto", segment="futures")
        with patch("trading.broker_sense.indicator_fusion.fuse",
                   return_value=_NO_FUSION):
            rep = self.ws.study_round(vision=_FakeReader(0.8), market="crypto")
        self.assertEqual(rep["studied"], ["ETH/USDT:USDT"])
        self.assertEqual(rep["claims"], 1)
        st = self.ws.status()
        self.assertTrue(st["set"]["ETH/USDT:USDT"]["studied"])
        self.assertEqual(st["reports"][0]["verdict"], "LONG")
        pend = (Path(state.STATE_DIR) / "direction_truth_pending.jsonl").read_text()
        row = json.loads(pend.splitlines()[-1])
        self.assertEqual(row["source"], "app_study")
        # second round: nothing left to study
        with patch("trading.broker_sense.indicator_fusion.fuse",
                   return_value=_NO_FUSION):
            rep2 = self.ws.study_round(vision=_FakeReader(0.8), market="crypto")
        self.assertEqual(rep2["studied"], [])

    def test_tie_evidence_gives_no_verdict_and_no_claim(self):
        from unittest.mock import patch
        self.ws.propose(["ETH/USDT:USDT"], market="crypto", segment="futures")
        with patch("trading.direction.micro_features.snapshot", return_value={}), \
                patch("trading.broker_sense.indicator_fusion.fuse",
                      return_value=_NO_FUSION):
            rep = self.ws.study_round(vision=_FakeReader(0.5), market="crypto")
        self.assertEqual(rep["claims"], 0)
        self.assertIsNone(self.ws.status()["reports"][0]["verdict"])

    def test_indicator_fusion_stakes_its_own_claim(self):
        import json
        from unittest.mock import patch
        self.ws.propose(["ETH/USDT:USDT"], market="crypto", segment="futures")
        fusion = {"available": True, "direction": "long", "p_up": 0.72,
                  "confluence": 0.44, "regime": "trend", "veto": None}
        with patch("trading.broker_sense.indicator_fusion.fuse",
                   return_value=fusion):
            rep = self.ws.study_round(vision=_FakeReader(0.8), market="crypto")
        self.assertEqual(rep["claims"], 2)                 # app_study + app_indicators
        pend = (Path(state.STATE_DIR) / "direction_truth_pending.jsonl").read_text()
        sources = {json.loads(x)["source"] for x in pend.splitlines()}
        self.assertIn("app_indicators", sources)
        ev = self.ws.status()["reports"][0]["evidence"]
        self.assertEqual(ev["indicator_fusion"]["direction"], "long")

    def test_kill_switch(self):
        import os
        os.environ["WATCHLIST_STUDY"] = "0"
        try:
            self.assertEqual(self.ws.propose(["A/USDT"], market="crypto",
                                             segment="spot")["added"], [])
            self.assertEqual(self.ws.study_round(vision=_FakeReader(0.8),
                                                 market="crypto")["studied"], [])
        finally:
            os.environ.pop("WATCHLIST_STUDY")


class TestFuse(_Iso):
    def test_micro_lanes_break_mtf_silence(self):
        side, conf, detail = self.ws._fuse(
            {}, {"psych_ofi": {"vote": "SHORT"}, "funding_extreme": {"vote": "SHORT"}})
        self.assertEqual(side, "SHORT")
        self.assertEqual(conf, 1.0)

    def test_conflict_resolves_by_majority(self):
        side, conf, _ = self.ws._fuse(
            {"1h": {"p_up": 0.7, "source": "fake"}},          # LONG ×2
            {"psych_ofi": {"vote": "SHORT"}})                 # SHORT ×1
        self.assertEqual(side, "LONG")
        self.assertAlmostEqual(conf, 2 / 3, places=2)

    def test_fusion_and_patterns_vote(self):
        side, conf, detail = self.ws._fuse(
            {}, {},
            {"available": True, "direction": "short", "p_up": 0.3,
             "confluence": -0.4, "regime": "trend", "veto": None},   # SHORT ×2
            {"vote": "SHORT", "frames": {"1h": ["bearish_engulfing"]}})  # SHORT ×1
        self.assertEqual(side, "SHORT")
        self.assertEqual(conf, 1.0)
        self.assertEqual(detail["candle_patterns"], {"1h": ["bearish_engulfing"]})

    def test_fusion_outvotes_single_micro_lane(self):
        side, _, _ = self.ws._fuse(
            {}, {"psych_ofi": {"vote": "LONG"}},              # LONG ×1
            {"available": True, "direction": "short", "p_up": 0.3})   # SHORT ×2
        self.assertEqual(side, "SHORT")


class TestPatterns(_Iso):
    def test_bullish_engulfing(self):
        o = [100.0, 101.0, 100.5, 99.2]
        c = [101.0, 100.0, 99.3, 100.8]     # last bar engulfs the prior red body
        h = [max(a, b) + 0.1 for a, b in zip(o, c)]
        l = [min(a, b) - 0.1 for a, b in zip(o, c)]
        names, sign = self.ws._patterns_from_ohlc(o, h, l, c)
        self.assertIn("bullish_engulfing", names)
        self.assertEqual(sign, 1)

    def test_three_black_crows(self):
        o = [100.0, 99.0, 98.0, 97.0]
        c = [99.0, 98.0, 97.0, 96.0]
        h = [x + 0.05 for x in o]
        l = [x - 0.05 for x in c]
        names, sign = self.ws._patterns_from_ohlc(o, h, l, c)
        self.assertIn("three_black_crows", names)
        self.assertEqual(sign, -1)

    def test_too_few_bars_is_silent(self):
        self.assertEqual(self.ws._patterns_from_ohlc([1, 2], [1, 2], [1, 2], [1, 2]),
                         ([], 0))

    def test_no_feather_no_vote(self):
        out = self.ws._candle_patterns("ETH/USDT:USDT", "futures")
        self.assertIsNone(out["vote"])


if __name__ == "__main__":
    unittest.main()
