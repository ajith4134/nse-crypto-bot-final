"""Integration test for BrainExecutor.open_filter_lane (Stage 1b) — the Binance-filter TOP-N lane
opens ranked picks with the filter-derived side, skips already-open symbols, and no-ops when the
kill-switch is off. Uses a fake client + monkeypatched ranker/reliability so it never touches the
live store, freqtrade, or the truth ledger (neutral reliability ⇒ no inversion ⇒ no ledger writes).
"""
import os
import unittest
from unittest import mock

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
        os.environ["DIRECTION_TRUTH"] = "0"        # no ledger writes from the test (isolate state)
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
        for k in ("BINANCE_FILTER_LANE", "BINANCE_FILTER_PRESET", "DIRECTION_TRUTH"):
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


class FilterLaneSegmentValidityTest(FilterLaneExecutorTest):
    """SEGMENT VALIDITY (2026-07-16). Measured live: the lane burned every cycle on entries the
    engine rejected outright — futures `entered=[] skipped=0 err="Symbol does not exist or market
    is not active"`, spot `err="Can't go short on Spot markets"`. It ranked the whole captured
    universe and derived a side, but never checked what the TARGET SEGMENT can accept."""

    def _sides(self):
        return [o.get("side") for o in self.cli.orders]

    def test_spot_never_receives_a_short_order(self):
        """Spot cannot short. A SHORT read on spot means "do not buy" -> SKIP. It must NEVER be
        flipped to long: that would fabricate a direction the brain did not choose."""
        self.ex.segment = "spot"
        # force both picks SHORT regardless of the preset's own derivation
        self.ex._learned_filter_side = lambda *a, **k: ("SHORT", "filter:momentum", {})
        rep = self.ex.open_filter_lane(allow_live=False)
        self.assertNotIn("short", self._sides())
        self.assertEqual(self.cli.orders, [], "no order may reach a spot worker as a short")
        self.assertGreaterEqual(rep["skipped"], 1)     # skipped, not silently flipped

    def test_futures_still_takes_shorts(self):
        self.ex.segment = "futures"
        self.ex._learned_filter_side = lambda *a, **k: ("SHORT", "filter:momentum", {})
        self.ex.open_filter_lane(allow_live=False)
        self.assertIn("short", self._sides())          # the spot guard must not leak to futures

    def test_pair_absent_from_the_segment_is_skipped(self):
        """_derive() already calls tradeable_form(); None -> the pick never reaches placement."""
        self.ex.segment = "futures"
        self.cli.tradeable_form = lambda sym, seg: None        # engine says: not tradeable here
        rep = self.ex.open_filter_lane(allow_live=False)
        self.assertEqual(self.cli.orders, [], "must not place an order for an absent market")
        self.assertGreaterEqual(rep["skipped"], 1)

    def test_one_raising_symbol_must_not_kill_the_whole_cycle(self):
        """THE root cause of "futures never opens" (2026-07-16). place_order -> _check RAISES
        FreqtradeError on an API refusal; the loop only handled the RETURNED {"ok": False}. The
        raise escaped to the outer except and aborted every remaining candidate — the logs showed
        `entered=[] skipped=0 err=forceenter failed: ...`, and skipped=0 proved it died on pick #1.
        The engine can legitimately refuse a pair our guard accepts: _pair_tradeable FAILS OPEN and
        checks raw ccxt markets, which are WIDER than Freqtrade's internal pairlist."""
        from trading.crypto.engine_client import FreqtradeError
        self.ex.segment = "futures"
        calls = {"n": 0}

        def _place(**kw):
            calls["n"] += 1
            if calls["n"] == 1:                     # first candidate is refused by the engine
                raise FreqtradeError("forceenter failed: Error querying /api/v1/forceenter: "
                                     "Symbol does not exist or market is not active.")
            self.cli.orders.append(kw)
            return {"ok": True}

        self.cli.place_order = _place
        rep = self.ex.open_filter_lane(allow_live=False)
        self.assertEqual(calls["n"], 2, "the cycle must CONTINUE to candidate #2 after a raise")
        self.assertEqual(len(rep["entered"]), 1, "candidate #2 must still open")
        self.assertGreaterEqual(rep["skipped"], 1)  # the refusal is data: logged + skipped
        self.assertIsNone(rep.get("error"), "a per-pick refusal must not become a cycle error")


class ClosedTailCacheTest(unittest.TestCase):
    """THE cycle bottleneck (2026-07-16). py-spy caught the funnel blocked in
    open_filter_lane -> _record_entry_meta -> TradeJournal.__init__ -> _load -> from_dict -> fields().
    TradeJournal() parses EVERY row (7,318 dataclass builds + a confidence update each) while the
    caller used only [-200:] — once PER RECORDED ENTRY (~100/cycle => ~730k constructions/cycle).
    Not the crawl, not the tournament, not the lane budget: THIS is why cycles ran 16 min."""

    def setUp(self):
        be._CLOSED_TAIL.update({"ts": 0.0, "n": 0, "rows": []})
        self.addCleanup(be._CLOSED_TAIL.update, {"ts": 0.0, "n": 0, "rows": []})

    def test_journal_is_loaded_ONCE_not_per_call(self):
        calls = {"n": 0}

        class _FakeJournal:
            def __init__(self, *a, **k):
                calls["n"] += 1
                self.trades = []

        import trading.journal.journal as jmod
        with mock.patch.object(jmod, "TradeJournal", _FakeJournal):
            for _ in range(50):                      # 50 entries in one cycle
                be._closed_tail(200)
        self.assertEqual(calls["n"], 1,
                         "the journal must be parsed ONCE per TTL, not once per recorded entry")

    def test_cache_expires_so_the_tail_stays_fresh(self):
        import trading.journal.journal as jmod
        calls = {"n": 0}

        class _FakeJournal:
            def __init__(self, *a, **k):
                calls["n"] += 1
                self.trades = []

        with mock.patch.object(jmod, "TradeJournal", _FakeJournal):
            be._closed_tail(200)
            be._CLOSED_TAIL["ts"] = 0.0              # simulate TTL expiry
            be._closed_tail(200)
        self.assertEqual(calls["n"], 2, "an expired tail must re-read (advisory data still ages)")

    def test_a_journal_read_failure_never_breaks_an_entry(self):
        import trading.journal.journal as jmod
        be._CLOSED_TAIL.update({"ts": 0.0, "n": 200, "rows": [{"x": 1}]})
        with mock.patch.object(jmod, "TradeJournal", side_effect=RuntimeError("disk gone")):
            out = be._closed_tail(200)
        self.assertEqual(out, [{"x": 1}], "serve the last good tail; attribution is advisory")
