"""Tests for the Direction Brain Mission X-batch: day-bucket half-life reliability,
horizon emission, cost gate, control variant."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        from trading.direction import learned_direction as ld
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        ld.clear_cache()
        for k in ("LEDGER_HALF_LIFE_D", "COST_GATE", "FEE_BPS", "SLIP_BPS"):
            os.environ.pop(k, None)

    def tearDown(self):
        from trading.direction import learned_direction as ld
        ld.clear_cache()
        self._p.stop()
        self._tmp.cleanup()


def _day(offset_days: int) -> str:
    return time.strftime("%Y%m%d", time.gmtime(time.time() - offset_days * 86400))


class TestDayBucketsAndDecay(_Base):
    def _seed(self, buckets):
        from trading import state
        state.save_json("direction_truth.json", {"day_buckets": buckets})

    def test_fold_writes_day_bucket(self):
        from trading.direction import truth_ledger as tl
        agg: dict = {}
        row = {"ts": time.time(), "source": "lens_x", "market": "CRYPTO",
               "segment": "futures", "direction": "LONG", "regime": "chop",
               "taken": False}
        tl._fold(agg, row, "1h", True, "mirror:markprice")
        key = f"lens_x|CRYPTO|chop|1h|{_day(0)}"
        self.assertEqual(agg["day_buckets"][key], {"n": 1, "correct": 1})

    def test_decay_weights_recent_over_stale(self):
        from trading.direction import truth_ledger as tl
        # yesterday the source was RIGHT (60/100); 10 days ago it was WRONG (20/100)
        self._seed({f"s|CRYPTO|chop|1h|{_day(1)}": {"n": 100, "correct": 60},
                    f"s|CRYPTO|chop|1h|{_day(10)}": {"n": 100, "correct": 20}})
        dec = tl.source_reliability_decayed("s", market="CRYPTO", regime="chop",
                                            half_life_days=2.0)
        cum_rate = 80 / 200                          # cumulative pools say 0.40 (wrong-ish)
        self.assertGreater(dec["rate"], 0.5)         # decayed says the RECENT truth: right
        self.assertGreater(dec["rate"], cum_rate)

    def test_no_day_evidence_returns_zero_n(self):
        from trading.direction import truth_ledger as tl
        self._seed({})
        self.assertEqual(tl.source_reliability_decayed("ghost")["n"], 0)

    def test_backfill_folds_clean_rows_once(self):
        from trading import state
        from trading.direction import truth_ledger as tl
        p = Path(self._tmp.name) / "train.jsonl"
        rows = [{"ts": time.time(), "source": "lens_x", "market": "CRYPTO",
                 "regime": "chop", "horizon": "1h", "correct": True},
                {"ts": 1_000_000.0, "source": "lens_x", "market": "CRYPTO",
                 "regime": "chop", "horizon": "1h", "correct": False},   # pre-clean → excluded
                {"ts": time.time(), "source": "lens_x", "market": "CRYPTO",
                 "regime": "chop", "horizon": "exit", "correct": True}]  # exit → excluded
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        out = tl.backfill_day_buckets(p)
        self.assertEqual(out["folded"], 1)
        self.assertEqual(tl.backfill_day_buckets(p)["reason"], "already backfilled")
        agg = state.load_json("direction_truth.json", {})
        self.assertEqual(sum(b["n"] for b in agg["day_buckets"].values()), 1)


class TestReliabilityChainDecayed(_Base):
    def test_decayed_evidence_outranks_polluted_cumulative(self):
        from trading import state
        from trading.direction import learned_direction as ld
        # cumulative (all-era) pool says 0.42 over 5000 rows (polluted history);
        # the last two days say 0.62 over 260 rows (clean truth)
        state.save_json("direction_truth.json", {
            "buckets": {"s|CRYPTO|chop|1h": {"n": 5000, "correct": 2100}},
            "day_buckets": {f"s|CRYPTO|chop|1h|{_day(0)}": {"n": 130, "correct": 81},
                            f"s|CRYPTO|chop|1h|{_day(1)}": {"n": 130, "correct": 80}}})
        rel_live = ld.reliability("s", "chop", "CRYPTO", decayed=True)
        ld.clear_cache()
        rel_ctl = ld.reliability("s", "chop", "CRYPTO", decayed=False)
        self.assertGreater(rel_live["rate"], 0.55)       # follows recent truth
        self.assertLess(rel_ctl["rate"], 0.45)           # control keeps legacy behavior

    def test_zero_half_life_env_restores_legacy(self):
        from trading import state
        from trading.direction import learned_direction as ld
        os.environ["LEDGER_HALF_LIFE_D"] = "0"
        try:
            state.save_json("direction_truth.json", {
                "buckets": {"s|CRYPTO|chop|1h": {"n": 500, "correct": 300}},
                "day_buckets": {f"s|CRYPTO|chop|1h|{_day(0)}": {"n": 50, "correct": 10}}})
            rel = ld.reliability("s", "chop", "CRYPTO", decayed=True)
            self.assertGreater(rel["rate"], 0.55)        # day buckets ignored
        finally:
            os.environ.pop("LEDGER_HALF_LIFE_D", None)


class TestHorizonEmission(_Base):
    def test_decide_emits_best_supported_horizon(self):
        from trading import state
        from trading.direction import learned_direction as ld
        day = _day(0)
        state.save_json("direction_truth.json", {
            "buckets": {"lens_a|CRYPTO|any|1h": {"n": 400, "correct": 260}},
            "day_buckets": {
                f"lens_a|CRYPTO|unknown|15m|{day}": {"n": 100, "correct": 52},
                f"lens_a|CRYPTO|unknown|1h|{day}": {"n": 100, "correct": 55},
                f"lens_a|CRYPTO|unknown|4h|{day}": {"n": 100, "correct": 68}}})
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("lens_a", 0.8)], market="CRYPTO", symbol="AKEUSDT",
                            log=False)
        self.assertEqual(out["direction"], "long")
        self.assertEqual(out.get("horizon"), "4h")
        # session 3 superseded the post-hoc emission with specialized fusion; either
        # mechanism must still land on the strongest horizon
        self.assertTrue(out.get("horizon_mode") == "specialized"
                        or "horizon_scores" in out)

    def test_control_variant_marked(self):
        from trading.direction import learned_direction as ld
        out = ld.decide([], market="CRYPTO", symbol="X", log=False, variant="control")
        self.assertEqual(out["variant"], "control")


class TestCostGate(_Base):
    def _mirror(self, atr_frac, price=100.0):
        m = mock.Mock()
        rows = []
        for i in range(16):
            rows.append([i, price, price * (1 + atr_frac / 2),
                         price * (1 - atr_frac / 2), price])
        m.candles.return_value = rows
        return m

    def test_small_edge_small_move_fails(self):
        from trading.direction import learned_direction as ld
        ld._ATR_CACHE.clear()
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(0.0005)):   # 5bp ATR
            g = ld.cost_gate(0.52, symbol="AKEUSDT", horizon="15m")
        # E|move| ≈ 5bp*√3 ≈ 8.7bp; edge 0.04 → EV ≈ 0.35bp - 12bp < 0
        self.assertFalse(g["pass"])

    def test_real_edge_big_move_passes(self):
        from trading.direction import learned_direction as ld
        ld._ATR_CACHE.clear()
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(0.004)):    # 40bp ATR
            g = ld.cost_gate(0.60, symbol="TAOUSDT", horizon="1h")
        # E|move| ≈ 40bp*√12 ≈ 138bp; edge 0.2 → EV ≈ 27.7 - 12 > 0
        self.assertTrue(g["pass"])
        self.assertGreater(g["ev_bps"], 0)

    def test_cold_mirror_fails_open_with_reason(self):
        from trading.direction import learned_direction as ld
        ld._ATR_CACHE.clear()
        m = mock.Mock()
        m.candles.return_value = []
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=m):
            g = ld.cost_gate(0.6, symbol="COLDUSDT")
        self.assertTrue(g["pass"])
        self.assertEqual(g["reason"], "no_atr")

    def test_disabled(self):
        from trading.direction import learned_direction as ld
        os.environ["COST_GATE"] = "0"
        try:
            self.assertTrue(ld.cost_gate(0.5, symbol="X")["pass"])
        finally:
            os.environ.pop("COST_GATE", None)


if __name__ == "__main__":
    unittest.main()


class TestSession2(unittest.TestCase):
    """Mission session 2: candle-fallback price_at, conditioner merge, sel conditioner."""

    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def test_price_at_falls_back_to_candle_close(self):
        import threading
        from trading.broker_sense.binance_stream import BinanceUniverseMirror
        m = BinanceUniverseMirror.__new__(BinanceUniverseMirror)
        m._lock = threading.RLock()
        m._hist = {}
        m._mark = {}
        epoch = 1_784_000_000.0
        m._candles = {"AKEUSDT": {300: [[epoch - 300, 99, 99, 99, 99.5],
                                        [epoch, 100, 101, 99, 100.5]]}}
        self.assertEqual(m.price_at("AKEUSDT", epoch + 60), 100.5)
        self.assertEqual(m.price_at("AKEUSDT", epoch - 200), 99.5)
        self.assertIsNone(m.price_at("AKEUSDT", epoch - 900))

    def test_record_merges_explicit_conditioners_over_auto(self):
        from trading.direction import truth_ledger as tl
        with mock.patch.object(tl, "current_conditioners",
                               return_value={"clock": "off_mark", "liq": "calm"}), \
             mock.patch.object(tl, "_mirror_price", return_value=100.0):
            tl.record(symbol="AKEUSDT", market="CRYPTO", segment="futures",
                      direction="LONG", source="lens_x",
                      conditioners={"sel": "momentum"})
        import json as _j
        line = open(tl._pending_path()).readline()
        cond = _j.loads(line)["cond"]
        self.assertEqual(cond["sel"], "momentum")       # explicit added
        self.assertEqual(cond["clock"], "off_mark")     # auto preserved

    def test_decide_merges_extra_conditioners(self):
        from trading.direction import learned_direction as ld
        seen = {}

        def spy(source, regime, market, conditioners=None, **kw):
            seen["cond"] = conditioners
            return {"n": 0, "correct": 0, "rate": None, "ci_low": None,
                    "ci_high": None, "edge": None}
        with mock.patch.object(ld, "reliability", side_effect=spy), \
             mock.patch.object(ld._tl, "current_conditioners",
                               return_value={"liq": "calm"}):
            ld.decide([("lens_a", 0.7)], market="CRYPTO", symbol="AKEUSDT",
                      log=False, extra_conditioners={"sel": "momentum"})
        self.assertEqual(seen["cond"], {"liq": "calm", "sel": "momentum"})


class TestHorizonSpecialized(_Base):
    """Session 3: the horizon whose fused read is strongest OWNS the decision."""

    def _seed(self, per_horizon):
        from trading import state
        day = _day(0)
        db = {}
        for h, (n, c) in per_horizon.items():
            db[f"lens_a|CRYPTO|unknown|{h}|{day}"] = {"n": n, "correct": c}
        state.save_json("direction_truth.json", {"day_buckets": db})

    def test_strongest_horizon_owns_the_decision(self):
        from trading.direction import learned_direction as ld
        # 15m barely-positive, 4h strongly positive → 4h must own it
        self._seed({"15m": (200, 104), "1h": (200, 108), "4h": (200, 130)})
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("lens_a", 0.8)], market="CRYPTO", symbol="AKEUSDT",
                            log=False)
        self.assertEqual(out["direction"], "long")
        self.assertEqual(out["horizon"], "4h")
        self.assertEqual(out["horizon_mode"], "specialized")

    def test_control_variant_stays_pooled(self):
        from trading.direction import learned_direction as ld
        self._seed({"4h": (200, 130)})
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("lens_a", 0.8)], market="CRYPTO", symbol="AKEUSDT",
                            log=False, variant="control")
        self.assertNotEqual(out.get("horizon_mode"), "specialized")

    def test_flag_off_restores_pooled_plus_posthoc(self):
        from trading.direction import learned_direction as ld
        os.environ["HORIZON_SPECIALIZED"] = "0"
        try:
            self._seed({"4h": (200, 130), "1h": (200, 120), "15m": (200, 118)})
            with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
                out = ld.decide([("lens_a", 0.8)], market="CRYPTO", symbol="AKEUSDT",
                                log=False)
            self.assertNotEqual(out.get("horizon_mode"), "specialized")
            self.assertIn(out.get("horizon"), ("15m", "1h", "4h"))  # post-hoc emission
        finally:
            os.environ.pop("HORIZON_SPECIALIZED", None)

    def test_no_horizon_clears_falls_back_to_pooled(self):
        from trading.direction import learned_direction as ld
        self._seed({})                              # no per-horizon evidence at all
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("lens_a", 0.8)], market="CRYPTO", symbol="AKEUSDT",
                            log=False)
        self.assertIsNone(out.get("horizon_mode"))


class TestCorrectDirectionNeverInverts(_Base):
    def test_reliably_wrong_source_passes_through(self):
        from trading.direction import learned_direction as ld
        wrong = {"n": 800, "correct": 240, "rate": 0.30, "ci_low": 0.27,
                 "ci_high": 0.33, "edge": -0.20}
        with mock.patch.object(ld, "reliability", return_value=wrong):
            chosen, info = ld.correct_direction("LONG", source="bad_lens",
                                                market="CRYPTO")
        self.assertEqual(chosen, "LONG")            # NEVER flipped
        self.assertEqual(info["action"], "pass")


class TestMagnitudeCap(_Base):
    """X-F: measured on 16,525 clean labels — claimed confidence is anti-informative;
    only the sign contributes, capped by LEARNED_DIR_MAG_CAP."""

    def _seed_two_sources(self):
        from trading import state
        day = _day(0)
        # trusted_a: strong measured edge; loud_b: weaker edge but screams p=0.99
        state.save_json("direction_truth.json", {"day_buckets": {
            f"trusted_a|CRYPTO|unknown|1h|{day}": {"n": 300, "correct": 186},   # 0.62
            f"loud_b|CRYPTO|unknown|1h|{day}": {"n": 300, "correct": 168}}})    # 0.56

    def test_loud_source_cannot_dominate_by_magnitude(self):
        from trading.direction import learned_direction as ld
        self._seed_two_sources()
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("trusted_a", 0.65), ("loud_b", 0.01)],   # b screams SHORT
                            market="CRYPTO", symbol="AKEUSDT", log=False)
        # raw magnitudes: b's 0.49 pull × w≈0.06 would swamp a's capped 0.10 × w≈0.12;
        # with the cap the trusted higher-weight source owns the side
        self.assertEqual(out["direction"], "long")

    def test_control_variant_keeps_raw_magnitudes(self):
        from trading.direction import learned_direction as ld
        self._seed_two_sources()
        with mock.patch.object(ld._tl, "current_conditioners", return_value={}):
            out = ld.decide([("trusted_a", 0.65), ("loud_b", 0.01)],
                            market="CRYPTO", symbol="AKEUSDT", log=False,
                            variant="control")
        self.assertEqual(out["direction"], "short")   # pre-mission behavior preserved


class TestCleanWindowRows(unittest.TestCase):
    """Brain-health 2026-07-17: nets train on the clean window only."""

    def test_filters_pre_cutoff_and_unparseable(self):
        from trading.brain.trade_features import clean_window_rows
        rows = [{"exit_datetime": "2026-07-17T09:00:00+00:00", "id": "clean"},
                {"exit_datetime": "2026-07-10T09:00:00+00:00", "id": "dirty"},
                {"exit_datetime": "garbage", "id": "bad"},
                {"id": "missing"}]
        out = clean_window_rows(rows)
        self.assertEqual([r["id"] for r in out], ["clean"])

    def test_zero_env_disables(self):
        import os
        from trading.brain.trade_features import clean_window_rows
        os.environ["TRADE_NET_CLEAN_TS"] = "0"
        try:
            rows = [{"exit_datetime": "2026-07-10T09:00:00+00:00"}]
            self.assertEqual(len(clean_window_rows(rows)), 1)
        finally:
            os.environ.pop("TRADE_NET_CLEAN_TS", None)


class TestDeepScanFixes(_Base):
    """2026-07-17 pipeline deep-scan (the JCT/KORU case): range position primitive,
    pos conditioner, reflex fire-time re-validation, live-loop tag attribution."""

    def _mirror(self, closes_hi_lo):
        m = mock.Mock()
        m.candles.return_value = [[i, c, h, l, c] for i, (c, h, l) in
                                  enumerate(closes_hi_lo)]
        return m

    def test_range_position_top_and_bottom(self):
        from trading.direction import truth_ledger as tl
        bars = [(100, 110, 90)] * 6 + [(110, 110, 108)]      # current close at prior high
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(bars)):
            self.assertEqual(tl.range_position("AKEUSDT"), 1.0)
        bars2 = [(100, 110, 90)] * 6 + [(90, 92, 90)]        # current at prior low
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(bars2)):
            self.assertEqual(tl.range_position("AKEUSDT"), 0.0)

    def test_pos_conditioner_stamped(self):
        from trading.direction import truth_ledger as tl
        with mock.patch.object(tl, "range_position", return_value=0.95), \
             mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        side_effect=RuntimeError):        # no book → no liq, pos still set
            cond = tl.current_conditioners("AKEUSDT")
        self.assertEqual(cond.get("pos"), "top")

    def test_reflex_gate_refuses_long_at_top_and_records(self):
        import trading.crypto.freqtrade.brain_executor as bx
        ex = bx.BrainExecutor.__new__(bx.BrainExecutor)
        ex.segment = "futures"
        cli = mock.Mock()
        cli.tradeable_form.return_value = "JCT/USDT:USDT"
        row = {"symbol": "JCT/USDT:USDT", "direction": "LONG", "source": "account_path"}
        with mock.patch("trading.direction.pullback.enabled", return_value=True), \
             mock.patch("trading.direction.pullback.sweep", return_value=[row]), \
             mock.patch("trading.direction.truth_ledger.range_position",
                        return_value=0.95), \
             mock.patch("trading.direction.truth_ledger.record") as rec:
            rep = ex.sweep_pullbacks(cli)
        self.assertEqual(rep["entered"], [])
        cli.place_order.assert_not_called()
        self.assertEqual(rec.call_args.kwargs.get("source"), "reflex_poscut")

    def test_reflex_gate_lets_bottom_long_through_to_placement(self):
        import trading.crypto.freqtrade.brain_executor as bx
        ex = bx.BrainExecutor.__new__(bx.BrainExecutor)
        ex.segment = "futures"
        cli = mock.Mock()
        cli.tradeable_form.return_value = "KORU/USDT:USDT"
        cli.place_order.return_value = {"ok": True}
        row = {"symbol": "KORU/USDT:USDT", "direction": "LONG", "source": "account_path"}
        os.environ["LEARNED_DIRECTION"] = "0"
        try:
            with mock.patch("trading.direction.pullback.enabled", return_value=True), \
                 mock.patch("trading.direction.pullback.sweep", return_value=[row]), \
                 mock.patch("trading.direction.truth_ledger.range_position",
                            return_value=0.1), \
                 mock.patch("trading.direction.truth_ledger.record"):
                ex.sweep_pullbacks(cli)
            cli.place_order.assert_called()
        finally:
            os.environ.pop("LEARNED_DIRECTION", None)
