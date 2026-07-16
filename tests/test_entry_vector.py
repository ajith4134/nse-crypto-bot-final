"""tests/test_entry_vector.py — the entry-time microstructure vector (gate-rebuild step 1).

Pins the behaviour the deep research dictated (research/gate-rebuild/SYNTHESIS-AND-FIELD-LIST.md):
book STATE is recorded over the top-20 levels (3-4x stronger than flow at 1m/5m), the CONDITIONERS
(liquidity regime, clock phase, volatility) are present because a flat pooled model averages the
signal to zero, and every miss is an honest None rather than a fabricated value.
"""
import time
import unittest
from unittest import mock

from trading.brain import entry_vector as ev
from trading.broker_sense.binance_stream import get_mirror


class TestClockPhase(unittest.TestCase):
    """Research: power is strongest at QUARTER-HOUR marks and weaker at 1m/5m; Binance perps burst
    at all three, so pooling across phases mixes structurally different regimes."""

    def test_records_phase_for_every_burst_mark(self):
        p = ev.clock_phase(now=1_000_000_000.0 + 7.0)      # 7s past a round minute
        for m in (60, 300, 900):
            self.assertIn(f"ev_clock_since_{m}s", p)
            self.assertIn(f"ev_clock_to_next_{m}s", p)
            self.assertAlmostEqual(p[f"ev_clock_since_{m}s"] + p[f"ev_clock_to_next_{m}s"], m, 2)

    def test_phase_is_seconds_since_the_mark(self):
        p = ev.clock_phase(now=900.0 + 12.5)               # 12.5s past a quarter-hour mark
        self.assertAlmostEqual(p["ev_clock_since_900s"], 12.5, 2)
        self.assertAlmostEqual(p["ev_clock_since_60s"], 12.5, 2)


class TestLiquidityRegime(unittest.TestCase):
    """Research: flow's predictive increment runs +0.004 (calm) -> +0.038 (stressed), ~10x. Without
    this conditioner the flow features are pooled across regimes that behave differently."""

    def test_regimes_split_on_spread(self):
        self.assertEqual(ev.liquidity_regime(0.5), "calm")
        self.assertEqual(ev.liquidity_regime(4.0), "mixed")
        self.assertEqual(ev.liquidity_regime(20.0), "stressed")

    def test_unknown_spread_is_none_not_a_guess(self):
        # an unconditioned row is worse than a missing one: it silently pools stressed with calm
        self.assertIsNone(ev.liquidity_regime(None))


class TestEntryVector(unittest.TestCase):
    def setUp(self):
        m = get_mirror()
        m._book["BTCUSDT"] = {
            "bids": [[100.0 - i, 2.0] for i in range(20)],     # 20 levels, 40.0 total depth
            "asks": [[101.0 + i, 1.0] for i in range(20)],     # 20 levels, 20.0 total depth
            "ts": time.time(),
        }
        m._mark["BTCUSDT"] = {"mark": 100.5, "funding_rate": 0.0002,
                              "next_funding_ts": int((time.time() + 1800) * 1000),
                              "ts": time.time()}
        m._stats["BTCUSDT"] = {"ts": time.time(), "open_interest_usd": 5e6,
                               "oi_change_pct": 1.5, "crowd_long_pct": 0.62,
                               "smart_long_pct": 0.41}
        self.addCleanup(m._book.pop, "BTCUSDT", None)
        self.addCleanup(m._mark.pop, "BTCUSDT", None)
        self.addCleanup(m._stats.clear)
        self.addCleanup(m._taker.clear)

    def test_book_state_uses_all_20_levels(self):
        """The measured edge is specifically top-20 depth/imbalance — not the top-5 the existing
        psychology engine reads."""
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertEqual(v["ev_depth_bid_20"], 40.0)          # 20 levels x 2.0 — not 5 x 2.0
        self.assertEqual(v["ev_depth_ask_20"], 20.0)
        self.assertAlmostEqual(v["ev_obi_20"], (40.0 - 20.0) / 60.0, 6)
        self.assertAlmostEqual(v["ev_spread_bps"], (101.0 - 100.0) / 100.5 * 1e4, 2)

    def test_conditioners_are_present(self):
        """Tier-1: without regime + clock phase a fit pools structurally different regimes."""
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertIn("ev_liquidity_regime", v)
        self.assertIn("ev_clock_since_900s", v)
        self.assertIsNotNone(v["ev_liquidity_regime"])

    def test_carry_fields_including_the_funding_that_was_always_none(self):
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertEqual(v["ev_funding_rate"], 0.0002)        # was None on EVERY trade before this
        self.assertIsNotNone(v["ev_next_funding_in_s"])
        self.assertEqual(v["ev_oi_usd"], 5e6)
        self.assertAlmostEqual(v["ev_crowd_long_pct"], 0.62)

    def test_taker_from_the_aggtrade_push(self):
        m = get_mirror()
        for flag in (False, True):
            m._apply_agg_frame({"stream": "btcusdt@aggTrade",
                                "data": {"s": "BTCUSDT", "q": "2.0", "p": "100.0", "m": flag}})
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertIsNotNone(v["ev_taker_imbalance"])

    def test_missing_data_is_an_honest_none_never_fabricated(self):
        v = ev.entry_vector("ZZZNOTREAL/USDT:USDT")
        self.assertIsNone(v["ev_spread_bps"])
        self.assertIsNone(v["ev_obi_20"])
        self.assertIsNone(v["ev_funding_rate"])
        self.assertEqual(v["ev_symbol"], "ZZZNOTREALUSDT")

    def test_non_crypto_and_disabled_are_empty(self):
        self.assertEqual(ev.entry_vector("RELIANCE", market="nse"), {})
        with mock.patch.dict("os.environ", {"ENTRY_VECTOR": "0"}):
            self.assertEqual(ev.entry_vector("BTC/USDT:USDT"), {})

    def test_never_raises_on_a_broken_mirror(self):
        """A recorder fault must never block a trade."""
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        side_effect=RuntimeError("mirror down")):
            v = ev.entry_vector("BTC/USDT:USDT")
        self.assertEqual(v["ev_symbol"], "BTCUSDT")           # degraded, not crashed

    def test_flow_reads_book_ofi_s_REAL_column_names(self):
        """book_ofi.series() renames the raw jsonl columns to its BOOK_FIELDS contract
        (of_ofi/of_gofi_book/of_ofi_n/of_book_n). Reading the raw names (ofi/gofi/n) silently
        returns all-None with the data sitting right there — the live bug found 2026-07-16.
        Asserted against the module's own BOOK_FIELDS so a rename breaks this test, not prod."""
        import pandas as pd
        from trading.broker_sense import book_ofi
        for col in ("of_ofi", "of_ofi_n", "of_gofi_book", "of_book_n"):
            self.assertIn(col, book_ofi.BOOK_FIELDS)         # the contract we read against
        fake = pd.DataFrame([{"ts": time.time(), "of_ofi": -323.0, "of_ofi_n": -15.9,
                              "of_gofi_book": -277.7, "of_book_n": 362.0, "of_obi": -0.17,
                              "of_microdev_bp": -0.001, "of_spread_bp": 0.015}])
        with mock.patch.object(book_ofi, "series", return_value=fake):
            v = ev.entry_vector("BTC/USDT:USDT")
        self.assertEqual(v["ev_ofi"], -323.0)
        self.assertEqual(v["ev_ofi_n"], -15.9)
        self.assertEqual(v["ev_gofi"], -277.7)
        self.assertEqual(v["ev_book_n"], 362.0)

    def test_coverage_meter_counts_filled_fields(self):
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertGreater(v["ev_filled"], 8)


if __name__ == "__main__":
    unittest.main()
