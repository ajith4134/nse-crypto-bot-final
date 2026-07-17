"""Tests for the 2026-07-17 connect-the-brain batch.

Three connection repairs, each pinned here:
1. regime.classify reads the in-RAM mirror FIRST (the feather path starved when
   candle_updater was disabled 2026-07-12 → 258/258 cached keys "unknown").
2. learned_direction.reliability does hierarchical (empirical-Bayes) shrinkage:
   a thin regime bucket borrows pseudo-observations from the source's
   across-regime pool instead of the old all-or-nothing step fallback.
3. brain_executor._lens_reads is the ONE lens family shared by both decision
   lanes, so the selective lane can no longer drift to a 4-source subset.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest import mock


def _trend_closes(n: int = 64) -> list[float]:
    return [100.0 + i for i in range(n)]                     # ER = 1.0 → trend_up


class _FakeMirror:
    def __init__(self, closes, *, ts_last=None, tf=300):
        now = ts_last if ts_last is not None else time.time()
        self._rows = [[now - (len(closes) - 1 - i) * tf,
                       c, c, c, c] for i, c in enumerate(closes)]

    def candles(self, symbol, tf, n):
        return self._rows[-n:]

    def ticker(self, symbol):
        return {}


class TestRegimeMirrorFirst(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def test_mirror_supplies_regime_without_feathers(self):
        from trading.direction import regime as rg
        fake = _FakeMirror(_trend_closes())
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake):
            out = rg.classify("MIRRORONLY1USDT")
        self.assertEqual(out["regime"], "trend_up")
        self.assertEqual(out["basis"], "symbol")

    def test_stale_mirror_is_not_trusted(self):
        from trading.direction import regime as rg
        stale = _FakeMirror(_trend_closes(), ts_last=time.time() - 3600)
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=stale):
            closes = rg._mirror_closes("STALEONE2USDT")
        self.assertIsNone(closes)

    def test_short_history_is_not_trusted(self):
        from trading.direction import regime as rg
        fake = _FakeMirror(_trend_closes(8))
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake):
            self.assertIsNone(rg._mirror_closes("SHORTHIST3USDT"))

    def test_slashed_symbol_normalized(self):
        from trading.direction import regime as rg
        fake = _FakeMirror(_trend_closes())
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake) as gm:
            rg._mirror_closes("ETH/USDT:USDT")
        # the mirror keys flat upper-case symbols
        self.assertEqual(gm.return_value._rows[0][1], 100.0)


class TestReliabilityShrinkage(unittest.TestCase):
    def setUp(self):
        from trading.direction import learned_direction as ld
        ld.clear_cache()
        self._env = {}
        for k in ("LEARNED_DIR_SHRINK_K", "LEARNED_DIR_MIN_N"):
            self._env[k] = os.environ.pop(k, None)

    def tearDown(self):
        from trading.direction import learned_direction as ld
        ld.clear_cache()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    @staticmethod
    def _fake_reliability(regime_bucket, parent):
        def fake(source, *, market=None, regime=None, horizon=None, min_n=1):
            return dict(regime_bucket if regime else parent)
        return fake

    def test_thin_regime_bucket_borrows_from_parent(self):
        from trading.direction import learned_direction as ld
        thin = {"n": 4, "correct": 3, "rate": 0.75, "ci_low": 0.3,
                "ci_high": 0.95, "edge": 0.25}
        parent = {"n": 200, "correct": 116, "rate": 0.58, "ci_low": 0.51,
                  "ci_high": 0.65, "edge": 0.08}
        with mock.patch.object(ld._tl, "source_reliability",
                               side_effect=self._fake_reliability(thin, parent)):
            rel = ld.reliability("some_lens", "trend_up", "CRYPTO")
        self.assertEqual(rel["n_regime"], 4)
        self.assertEqual(rel["borrowed"], 24)
        self.assertEqual(rel["n"], 28)
        # blended rate sits BETWEEN the noisy bucket (0.75) and the parent (0.58)
        self.assertGreater(rel["rate"], 0.58)
        self.assertLess(rel["rate"], 0.75)

    def test_rich_regime_bucket_dominates(self):
        from trading.direction import learned_direction as ld
        rich = {"n": 500, "correct": 300, "rate": 0.60, "ci_low": 0.56,
                "ci_high": 0.64, "edge": 0.10}
        parent = {"n": 520, "correct": 270, "rate": 0.52, "ci_low": 0.48,
                  "ci_high": 0.56, "edge": 0.02}
        with mock.patch.object(ld._tl, "source_reliability",
                               side_effect=self._fake_reliability(rich, parent)):
            rel = ld.reliability("some_lens", "chop", "CRYPTO")
        # only 20 borrowable rows exist beyond the bucket → blend barely moves it
        self.assertGreater(rel["rate"], 0.59)

    def test_shrink_zero_restores_step_fallback(self):
        from trading.direction import learned_direction as ld
        os.environ["LEARNED_DIR_SHRINK_K"] = "0"
        thin = {"n": 2, "correct": 2, "rate": 1.0, "ci_low": 0.2,
                "ci_high": 1.0, "edge": 0.5}
        parent = {"n": 100, "correct": 55, "rate": 0.55, "ci_low": 0.45,
                  "ci_high": 0.65, "edge": 0.05}
        with mock.patch.object(ld._tl, "source_reliability",
                               side_effect=self._fake_reliability(thin, parent)):
            rel = ld.reliability("some_lens", "trend_down", "CRYPTO")
        self.assertEqual(rel["n"], 100)                       # parent verbatim, no blend

    def test_no_regime_passes_through(self):
        from trading.direction import learned_direction as ld
        parent = {"n": 50, "correct": 30, "rate": 0.6, "ci_low": 0.46,
                  "ci_high": 0.72, "edge": 0.1}
        with mock.patch.object(ld._tl, "source_reliability",
                               return_value=dict(parent)):
            rel = ld.reliability("some_lens", None, "CRYPTO")
        self.assertEqual(rel["n"], 50)
        self.assertNotIn("borrowed", rel)


class TestSharedLensReads(unittest.TestCase):
    """_lens_reads must surface the same lens family to any caller lane."""

    def _executor(self):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        ex = BrainExecutor.__new__(BrainExecutor)              # no client/loop needed
        ex.segment = "futures"
        return ex

    def test_lens_family_reaches_reads_and_bf_passthrough(self):
        os.environ["DEBATE_DIRECTION"] = "0"                   # no LLM in tests
        ex = self._executor()
        base = [("funnel_mtf_vote", 0.44)]
        fake_row = {"signal": "LONG", "cleared_gate": True, "best_strategy": "lib_X"}
        with mock.patch("trading.direction.vp_events.readings",
                        return_value=[("vp_trap:utc", 0.2)]), \
             mock.patch("trading.direction.market_state.readings",
                        return_value=[("spillover_large", 0.61)]), \
             mock.patch("trading.direction.brain_sources.collect",
                        return_value=[("news_sentiment", 0.57)]), \
             mock.patch("trading.crypto.freqtrade.strategy_table.lookup",
                        return_value=fake_row), \
             mock.patch("trading.brain.symbol_move_net.enabled",
                        return_value=False), \
             mock.patch("trading.direction.truth_ledger.record",
                        return_value=True):
            reads, bf = ex._lens_reads("AKEUSDT", base=base, regime="trend_up",
                                       fast=True)
        srcs = {s for s, _ in reads}
        for expected in ("funnel_mtf_vote", "vp_trap:utc", "spillover_large",
                         "news_sentiment", "strategy_tournament"):
            self.assertIn(expected, srcs)
        self.assertEqual(bf, fake_row)
        self.assertEqual(base, [("funnel_mtf_vote", 0.44)])    # base not mutated

    def test_every_lens_failing_still_returns_base(self):
        ex = self._executor()
        with mock.patch("trading.direction.vp_events.readings",
                        side_effect=RuntimeError), \
             mock.patch("trading.direction.market_state.readings",
                        side_effect=RuntimeError), \
             mock.patch("trading.direction.brain_sources.collect",
                        side_effect=RuntimeError), \
             mock.patch("trading.crypto.freqtrade.strategy_table.lookup",
                        side_effect=RuntimeError), \
             mock.patch("trading.brain.symbol_move_net.enabled",
                        side_effect=RuntimeError):
            reads, bf = ex._lens_reads("AKEUSDT", base=[("x", 0.5)],
                                       regime=None, fast=True)
        self.assertEqual(reads, [("x", 0.5)])
        self.assertIsNone(bf)


class TestConditionerBuckets(unittest.TestCase):
    """E8: conditioner recording, sub-bucket aggregation, and the shrinkage chain."""

    def setUp(self):
        from pathlib import Path
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def test_current_conditioners_shapes(self):
        from trading.direction import truth_ledger as tl
        fake = mock.Mock()
        fake.book.return_value = {"bids": [[100.0, 1]], "asks": [[100.5, 1]],
                                  "ts": time.time()}                 # 50 bps → stressed
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake):
            cond = tl.current_conditioners("AKEUSDT")
        self.assertIn(cond["clock"], ("at_mark", "off_mark"))
        self.assertEqual(cond["liq"], "stressed")

    def test_fold_writes_cond_sub_buckets(self):
        from trading.direction import truth_ledger as tl
        agg: dict = {}
        row = {"source": "lens_x", "market": "CRYPTO", "segment": "futures",
               "direction": "LONG", "regime": "chop", "taken": False,
               "cond": {"liq": "stressed", "clock": "at_mark"}}
        tl._fold(agg, row, "15m", True, "mirror:markprice")
        self.assertEqual(agg["cond_buckets"]["lens_x|CRYPTO|liq:stressed|15m"],
                         {"n": 1, "correct": 1})
        self.assertEqual(agg["cond_buckets"]["lens_x|CRYPTO|clock:at_mark|15m"],
                         {"n": 1, "correct": 1})
        from trading import state
        state.save_json(tl._AGG, agg)                    # the reader loads the state file
        rel = tl.source_reliability_conditioned("lens_x", market="CRYPTO",
                                                kind="liq", value="stressed")
        self.assertEqual(rel["n"], 1)

    def test_reliability_chain_refines_by_conditioner(self):
        from trading.direction import learned_direction as ld
        ld.clear_cache()
        parent = {"n": 200, "correct": 116, "rate": 0.58, "ci_low": 0.51,
                  "ci_high": 0.65, "edge": 0.08}
        cond_bucket = {"n": 40, "correct": 12, "rate": 0.30, "ci_low": 0.17,
                       "ci_high": 0.45, "edge": -0.20}    # source is BAD when stressed
        with mock.patch.object(ld._tl, "source_reliability",
                               return_value=dict(parent)), \
             mock.patch.object(ld._tl, "source_reliability_conditioned",
                               return_value=dict(cond_bucket)):
            rel = ld.reliability("lens_x", None, "CRYPTO",
                                 conditioners={"liq": "stressed"})
        self.assertLess(rel["rate"], 0.50)                # stressed evidence pulled it down
        self.assertGreater(rel["rate"], 0.30)             # but parent still tempers it
        ld.clear_cache()


class TestDepthRequests(unittest.TestCase):
    """E6: priority depth-watch requests merge ahead of the volume ranking."""

    def _mirror(self):
        from trading.broker_sense.binance_stream import BinanceUniverseMirror
        m = BinanceUniverseMirror.__new__(BinanceUniverseMirror)
        import threading
        m._lock = threading.RLock()
        m._depth_requests = {}
        return m

    def test_request_normalizes_and_expires(self):
        m = self._mirror()
        m.request_depth(["AKE/USDT:USDT", "taousdt"], ttl_s=3600)
        self.assertEqual(set(m.requested_depth()), {"AKEUSDT", "TAOUSDT"})
        m._depth_requests["AKEUSDT"] = time.time() - 1          # expire one
        self.assertEqual(m.requested_depth(), ["TAOUSDT"])

    def test_request_set_bounded(self):
        m = self._mirror()
        m.request_depth([f"S{i}USDT" for i in range(500)])
        self.assertLessEqual(len(m._depth_requests), 401)

    def test_never_raises_on_garbage(self):
        m = self._mirror()
        m.request_depth([None, "", 42])
        self.assertEqual(m.requested_depth(), [])


class TestDeepLensesMirrorBacked(unittest.TestCase):
    """E3: worldmodel/concept lenses build their ohlcv from the RAM mirror and default ON."""

    def _mirror_rows(self, n=60):
        now = time.time()
        return [[now - (n - i) * 300, 100 + i, 101 + i, 99 + i, 100 + i]
                for i in range(n)]

    def test_deep_lane_builds_ohlcv_from_mirror(self):
        from trading.direction import brain_sources as bs
        fake = mock.Mock()
        fake.candles.return_value = self._mirror_rows()
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake), \
             mock.patch.object(bs, "_worldmodel_p", return_value=0.62) as wm, \
             mock.patch.object(bs, "_concept_p", return_value=None):
            reads = bs.collect("AKEUSDT", fast=False, record=False)
        self.assertIn(("world_model", 0.62), reads)
        self.assertIsNotNone(wm.call_args[0][0])           # got a real DataFrame

    def test_fast_lane_never_runs_deep_lenses(self):
        from trading.direction import brain_sources as bs
        with mock.patch.object(bs, "_worldmodel_p", return_value=0.62) as wm:
            bs.collect("AKEUSDT", fast=True, record=False)
        wm.assert_not_called()

    def test_cold_mirror_skips_honestly(self):
        from trading.direction import brain_sources as bs
        fake = mock.Mock()
        fake.candles.return_value = self._mirror_rows(5)   # < 30 bars
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake):
            self.assertIsNone(bs._mirror_ohlcv("AKEUSDT"))


if __name__ == "__main__":
    unittest.main()
