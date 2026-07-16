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

class TestTier5LabelAndCost(unittest.TestCase):
    """Tier-5 is what makes the data FITTABLE: without barriers the triple-barrier labels are
    irreproducible [14][36], and without costs the target is a fiction — a fee-only model inflates
    annualized return by ~58% [72] and 0.3 ticks of slippage flipped most configs negative [43]."""

    def test_barriers_are_volatility_scaled_and_reproducible(self):
        b = ev.barriers(price=100.0, sigma=0.01, pt_mult=2.0, sl_mult=1.0, vertical_s=3600)
        self.assertAlmostEqual(b["ev_pt_price"], 100.0 * (1 + 2.0 * 0.01))   # sigma x multiple [14]
        self.assertAlmostEqual(b["ev_sl_price"], 100.0 * (1 - 1.0 * 0.01))
        self.assertEqual(b["ev_pt_mult"], 2.0)
        self.assertEqual(b["ev_vertical_barrier_s"], 3600)
        self.assertGreater(b["ev_vertical_barrier_ts"], time.time())        # the t1 deadline

    def test_barriers_without_volatility_are_none_not_guessed(self):
        b = ev.barriers(price=100.0, sigma=None)
        self.assertIsNone(b["ev_pt_price"])
        self.assertIsNone(b["ev_sl_price"])

    def test_costs_record_the_fill_side_that_can_flip_the_sign(self):
        """[89][124]: same signal, taker profited through the flash crash while maker took
        catastrophic adverse selection. The assumption is recorded, never assumed."""
        t = ev.costs("BTCUSDT", size_usd=1000.0, entry_type="taker")
        m = ev.costs("BTCUSDT", size_usd=1000.0, entry_type="maker")
        self.assertEqual(t["ev_entry_type"], "taker")
        self.assertEqual(m["ev_entry_type"], "maker")
        self.assertGreater(t["ev_fee_bps"], m["ev_fee_bps"])       # taker pays more
        self.assertEqual(t["ev_size_usd"], 1000.0)

    def test_slippage_uses_the_fitted_059_exponent_not_the_textbook_05(self):
        """[52]: on Binance perps the square-root law fits delta=0.59, not 0.5. [19]: walking the
        book (the naive alternative our 20-level snapshot invites) UNDER-predicts impact."""
        with mock.patch.object(ev, "_impact_inputs",
                               return_value={"ev_sigma_1h": 0.01, "ev_volume_1h": 1_000_000.0,
                                             "ev_impact_delta_ref": 0.59}):
            c = ev.costs("BTCUSDT", size_usd=10_000.0)
        part = 10_000.0 / 1_000_000.0
        self.assertAlmostEqual(c["ev_participation"], part, 10)
        self.assertAlmostEqual(c["ev_slippage_bps_est"], 0.01 * (part ** 0.59) * 1e4, 3)

    def test_entry_vector_threads_caller_price_and_size_into_tier5(self):
        m = get_mirror()
        m._book["BTCUSDT"] = {"bids": [[100.0, 5.0]], "asks": [[101.0, 3.0]], "ts": time.time()}
        self.addCleanup(m._book.pop, "BTCUSDT", None)
        v = ev.entry_vector("BTC/USDT:USDT", price=100.5, size_usd=5000.0, entry_type="maker")
        self.assertEqual(v["ev_entry_type"], "maker")
        self.assertEqual(v["ev_size_usd"], 5000.0)
        self.assertIn("ev_vertical_barrier_ts", v)
        self.assertIn("ev_decision_ts", v)                          # [48] staleness audit
        self.assertIsNotNone(v["ev_build_ms"])


class TestEntryVectorExtras(unittest.TestCase):
    def test_cross_asset_ofi_is_recorded_for_forecasting(self):
        """[128]: cross-asset OFI adds nothing contemporaneously but DOES raise OOS R2 when
        forecasting. [129]: sparse — the two majors only, never all 200 coins."""
        import pandas as pd
        from trading.broker_sense import book_ofi
        fake = pd.DataFrame([{"ts": time.time(), "of_ofi_n": 2.5}])
        with mock.patch.object(book_ofi, "series", return_value=fake):
            x = ev._cross_asset("SOLUSDT")
        self.assertEqual(x["ev_btc_ofi_n"], 2.5)
        self.assertEqual(x["ev_eth_ofi_n"], 2.5)

    def test_cross_asset_does_not_duplicate_a_coin_against_itself(self):
        import pandas as pd
        from trading.broker_sense import book_ofi
        fake = pd.DataFrame([{"ts": time.time(), "of_ofi_n": 2.5}])
        with mock.patch.object(book_ofi, "series", return_value=fake):
            x = ev._cross_asset("BTCUSDT")
        self.assertIsNone(x["ev_btc_ofi_n"])          # BTC vs BTC is not a cross-asset feature


class TestLiquidityMeasures(unittest.TestCase):
    """Roll + VPIN + a NON-tautological Kyle's lambda [103]. Caveats from the full read: [104] the
    study behind that ranking used ONLY 1m OHLCV (no book), and [100] its labels were the sign of
    change in VOLATILITY/liquidity — not direction. So this trio informs the liquidity_regime
    conditioner, not the direction call."""

    def setUp(self):
        self.m = get_mirror()
        self.m._taker.clear()
        self.addCleanup(self.m._taker.clear)

    def _seed_taker(self, buckets):
        from collections import deque
        self.m._taker["XUSDT"] = deque(buckets, maxlen=8)

    def test_kyle_lambda_is_a_real_regression_not_the_tick_rule_tautology(self):
        """The OLD vendored lambda regressed Δp on sign(Δp)·√vol — x derived from y, so the slope
        was mechanically positive and meaningless. Ours takes the sign from @aggTrade's maker flag,
        which is INDEPENDENT of Δp. Here price RISES when takers BUY → positive lambda, high R²."""
        import math
        import time as _t
        base = int(_t.time() // 60)
        # Build a ground truth: each minute's price move is CAUSED by that minute's signed taker
        # flow, y = LAM * sign*sqrt(|signed|) bps. A recoverable lambda proves we regress Δp on
        # real trade flow. (The old fixture moved price a constant amount regardless of volume —
        # no relationship existed, so there was nothing to recover.)
        LAM = 2.0
        signed = [-100.0, 25.0, 400.0, 900.0]                 # sells then increasing buys
        buckets, closes, c = [], [], 100.0
        for i, s in enumerate(signed):
            k = base - (len(signed) - i)
            buy, sell = (s, 0.0) if s > 0 else (0.0, -s)
            buckets.append({"bucket": k, "buy": buy, "sell": sell})
            closes.append(((k - 1), c))                       # the PREVIOUS minute's close
            c = c * (1.0 + LAM * math.copysign(math.sqrt(abs(s)), s) / 1e4)
            closes.append((k, c))                             # this minute's close
        self._seed_taker(buckets)
        rows = [[k * 60_000, 0, 0, 0, px, 0] for k, px in sorted(dict(closes).items())]
        with mock.patch("trading.broker_sense.binance_stream.ohlcv", return_value=rows):
            out = ev._liquidity_measures("XUSDT")
        self.assertIsNotNone(out["ev_kyle_lambda"])
        self.assertGreater(out["ev_kyle_lambda"], 0)          # buys lift price → positive impact
        self.assertAlmostEqual(out["ev_kyle_lambda"], LAM, delta=0.25)   # recovers the true slope
        self.assertGreater(out["ev_kyle_r2"], 0.95)           # near-perfect fit on clean data
        self.assertGreaterEqual(out["ev_kyle_n"], 3)          # thin sample is REPORTED, not hidden

    def test_kyle_needs_enough_buckets_and_is_none_otherwise(self):
        import time as _t
        base = int(_t.time() // 60)
        self._seed_taker([{"bucket": base, "buy": 10.0, "sell": 1.0}])      # only 1 pair
        rows = [[(base - i) * 60_000, 100, 100, 100, 100.0, 0] for i in range(3, 0, -1)]
        with mock.patch("trading.broker_sense.binance_stream.ohlcv", return_value=rows):
            out = ev._liquidity_measures("XUSDT")
        self.assertIsNone(out["ev_kyle_lambda"])              # honest None, never a 1-point "slope"

    def test_roll_measure_only_when_serial_covariance_is_negative(self):
        """Roll (1984) = 2*sqrt(-cov(Δp_t, Δp_t-1)) is DEFINED only under bid-ask bounce (cov<0).
        A trending series has cov>0 and the model does not apply — reporting a number would fabricate."""
        base = int(time.time() // 60)
        bounce = [100.0 + (0.5 if i % 2 else -0.5) for i in range(30)]      # alternating = bounce
        rows = [[(base - 30 + i) * 60_000, 0, 0, 0, bounce[i], 0] for i in range(30)]
        with mock.patch("trading.broker_sense.binance_stream.ohlcv", return_value=rows):
            out = ev._liquidity_measures("XUSDT")
        self.assertIsNotNone(out["ev_roll_spread_bps"])
        self.assertGreater(out["ev_roll_spread_bps"], 0)

        trend = [100.0 + i * 0.5 for i in range(30)]                        # monotone = cov >= 0
        rows2 = [[(base - 30 + i) * 60_000, 0, 0, 0, trend[i], 0] for i in range(30)]
        with mock.patch("trading.broker_sense.binance_stream.ohlcv", return_value=rows2):
            out2 = ev._liquidity_measures("XUSDT")
        self.assertIsNone(out2["ev_roll_spread_bps"])         # model inapplicable → honest None

    def test_vpin_is_the_normalized_taker_imbalance(self):
        for flag, q in ((False, 8.0), (True, 2.0)):           # 800 buy vs 200 sell notional
            self.m._apply_agg_frame({"stream": "xusdt@aggTrade",
                                     "data": {"s": "XUSDT", "q": str(q), "p": "100.0", "m": flag}})
        out = ev._liquidity_measures("XUSDT")
        self.assertAlmostEqual(out["ev_vpin"], abs(800 - 200) / 1000.0, 4)
        self.assertGreaterEqual(out["ev_vpin"], 0.0)
        self.assertLessEqual(out["ev_vpin"], 1.0)             # VPIN is a probability-like [0,1]

    def test_measures_never_raise_and_are_in_the_vector(self):
        v = ev.entry_vector("BTC/USDT:USDT")
        for k in ("ev_kyle_lambda", "ev_roll_spread_bps", "ev_vpin", "ev_kyle_r2"):
            self.assertIn(k, v)


class TestCoverage(unittest.TestCase):
    def setUp(self):
        m = get_mirror()
        m._book["BTCUSDT"] = {"bids": [[100.0 - i, 2.0] for i in range(20)],
                              "asks": [[101.0 + i, 1.0] for i in range(20)], "ts": time.time()}
        self.addCleanup(m._book.pop, "BTCUSDT", None)

    def test_coverage_meter_counts_filled_fields(self):
        v = ev.entry_vector("BTC/USDT:USDT")
        self.assertGreater(v["ev_filled"], 8)


if __name__ == "__main__":
    unittest.main()


class TestPsychologyKyleTautologyRemoved(unittest.TestCase):
    """The vendored compute_kyles_lambda falls back to the TICK RULE (sign = np.sign(Δp)) when
    `last_trade_side` is missing — which our ring_to_frame never populates — regressing Δp on a
    function of Δp. That tautology fed psych_fear (a live trade VETO) and decision_snapshot.
    Research [103] called Kyle's λ near-worthless in crypto; for us that was this bug."""

    def test_kyle_is_none_without_real_trade_side_data(self):
        import numpy as np
        import pandas as pd
        from trading.brain import psychology as ps
        if ps.LOBF is None:
            self.skipTest("lob_regime_scanner donor not available")
        # a frame shaped exactly like ring_to_frame's output: NO last_trade_side column
        n = 40
        df = pd.DataFrame({
            "timestamp": np.arange(n, dtype=float),
            "bid_price_1": 100.0 - np.arange(n) * 0.01,
            "ask_price_1": 100.1 - np.arange(n) * 0.01,
            "bid_qty_1": np.full(n, 5.0), "ask_qty_1": np.full(n, 4.0),
        })
        df["mid_price"] = (df["bid_price_1"] + df["ask_price_1"]) / 2.0
        self.assertNotIn("last_trade_side", df.columns)      # the real-world condition
        # the donor would still return a finite (tautological) slope here...
        lam = ps.LOBF.compute_kyles_lambda(df, window=20).iloc[-1]
        # ...so our guard is what must suppress it: the gate is the column check
        self.assertTrue("last_trade_side" not in df.columns or df.get("last_trade_side") is None)
        del lam


class TestCryptoEntryPathRecordsTheVector(unittest.TestCase):
    """The recorder was wired into live_loop._snapshot — but CRYPTO trades never pass through it
    (brain_executor -> freqtrade -> entry_meta.record). A live check found the newest crypto entry
    carrying NO entry_vector: the recorder was recording nothing on the only path opening trades.
    entry_meta.record's own docstring calls itself the one chokepoint for every crypto entry."""

    def test_record_attaches_entry_vector_to_the_snapshot(self):
        import tempfile
        from pathlib import Path
        import trading.state as state
        from trading.crypto.freqtrade import entry_meta
        tmp = tempfile.mkdtemp()
        with mock.patch.object(state, "STATE_DIR", Path(tmp)):
            m = get_mirror()
            m._book["SOLUSDT"] = {"bids": [[100.0, 5.0]], "asks": [[100.1, 4.0]], "ts": time.time()}
            self.addCleanup(m._book.pop, "SOLUSDT", None)
            meta = {"decision_snapshot": {"symbol": "SOL/USDT", "direction": "LONG"},
                    "price": 100.05, "stake_amount": 200.0}
            entry_meta.record("SOL/USDT", "futures", meta)
            ev_ = meta["decision_snapshot"].get("entry_vector")
        self.assertIsNotNone(ev_, "crypto entries must carry the entry vector")
        self.assertEqual(ev_["ev_symbol"], "SOLUSDT")
        self.assertEqual(ev_["ev_size_usd"], 200.0)          # threaded from the real stake
        self.assertIsNotNone(ev_["ev_spread_bps"])

    def test_record_never_blocks_an_entry_when_the_vector_faults(self):
        import tempfile
        from pathlib import Path
        import trading.state as state
        from trading.crypto.freqtrade import entry_meta
        tmp = tempfile.mkdtemp()
        with mock.patch.object(state, "STATE_DIR", Path(tmp)), \
             mock.patch("trading.brain.entry_vector.entry_vector",
                        side_effect=RuntimeError("boom")):
            meta = {"decision_snapshot": {"symbol": "SOL/USDT"}}
            entry_meta.record("SOL/USDT", "futures", meta)   # must not raise
        self.assertNotIn("entry_vector", meta["decision_snapshot"])
