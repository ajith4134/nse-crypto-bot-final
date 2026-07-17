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
        self.assertIn("horizon_scores", out)

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
