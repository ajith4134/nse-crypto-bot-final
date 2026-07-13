"""Integration test for BrainExecutor.open_filter_lane (Stage 1b) — the Binance-filter TOP-N lane
opens ranked picks with the filter-derived side, skips already-open symbols, and no-ops when the
kill-switch is off. Uses a fake client + monkeypatched ranker/reliability so it never touches the
live store, freqtrade, or the truth ledger (neutral reliability ⇒ no inversion ⇒ no ledger writes).
"""
import os
import unittest

from trading.crypto.freqtrade import brain_executor as be
from trading.broker_sense import binance_filter_lane as bfl
from trading.direction import learned_direction as ld


class FakeCli:
    def __init__(self):
        self.orders = []
        self._open = set()

    def open_pairs(self, segment=None):
        return list(self._open)

    def tradeable_form(self, sym, seg):
        # the lane now passes pair form (via binance_filter_lane.to_pair) — accept it as-is
        return sym if sym else None

    def place_order(self, **kw):
        self.orders.append(kw)
        return {"ok": True}


class FilterLaneExecutorTest(unittest.TestCase):
    def setUp(self):
        os.environ["BINANCE_FILTER_LANE"] = "1"
        os.environ["BINANCE_FILTER_PRESET"] = "momentum"
        self.ex = object.__new__(be.BrainExecutor)      # skip heavy __init__
        self.ex.segment = "futures"
        self.cli = FakeCli()
        self.ex.client = lambda: self.cli
        self.ex._record_entry_meta = lambda *a, **k: None
        self._orig_tp = bfl.top_picks
        bfl.top_picks = lambda seg, preset=None, n=None: [
            {"symbol": "AAAUSDT", "pct_change": 10.0, "filter_score": 10.0,
             "filter_preset": preset, "funding_rate": None},
            {"symbol": "BBBUSDT", "pct_change": -8.0, "filter_score": 8.0,
             "filter_preset": preset, "funding_rate": None}]
        self._orig_rel = ld._tl.source_reliability      # neutral → no inversion, no ledger write
        ld._tl.source_reliability = lambda *a, **k: {
            "n": 0, "rate": None, "ci_low": None, "ci_high": None, "edge": None}
        ld.clear_cache()

    def tearDown(self):
        bfl.top_picks = self._orig_tp
        ld._tl.source_reliability = self._orig_rel
        ld.clear_cache()
        for k in ("BINANCE_FILTER_LANE", "BINANCE_FILTER_PRESET"):
            os.environ.pop(k, None)

    def test_opens_topn_with_filter_derived_side(self):
        rep = self.ex.open_filter_lane()
        self.assertEqual(sorted(rep["entered"]),
                         ["AAA/USDT:USDT", "BBB/USDT:USDT"])
        # AAA +10% momentum → long; BBB -8% → short
        sides = {o["symbol"]: o["side"] for o in self.cli.orders}
        self.assertEqual(sides["AAA/USDT:USDT"], "long")
        self.assertEqual(sides["BBB/USDT:USDT"], "short")
        # tag is the filter preset when not inverted
        self.assertTrue(all(o["enter_tag"] == "filter:momentum" for o in self.cli.orders))

    def test_skips_already_open(self):
        self.cli._open = {"AAA/USDT:USDT"}
        rep = self.ex.open_filter_lane()
        self.assertEqual(rep["entered"], ["BBB/USDT:USDT"])
        self.assertEqual(rep["skipped"], 1)

    def test_disabled_is_no_op(self):
        os.environ["BINANCE_FILTER_LANE"] = "0"
        rep = self.ex.open_filter_lane()
        self.assertEqual(rep["entered"], [])
        self.assertEqual(self.cli.orders, [])


if __name__ == "__main__":
    unittest.main()
