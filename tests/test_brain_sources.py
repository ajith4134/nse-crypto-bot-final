"""tests/test_brain_sources.py — brain lenses as truth-ledger-weighted direction sources.

Pins the two properties that make wiring these in SAFE:
  1) collect() never raises and degrades to [] when producers are missing/disabled.
  2) an emitted source starts weightless in learned_direction (earn-weight-by-edge), so an
     unproven brain lens cannot move a trade until the ledger scores it.
"""
import os
import pathlib
import tempfile
import unittest

import numpy as np
import pandas as pd


class TestBrainSources(unittest.TestCase):
    def setUp(self):
        # isolate all persisted state to a temp dir (project convention)
        self._tmp = tempfile.mkdtemp()
        import trading.state as state
        self._orig = state.STATE_DIR
        state.STATE_DIR = pathlib.Path(self._tmp)
        # deterministic env: cheap lenses only, no network news
        for k, v in {"BRAIN_SOURCES": "1", "BRAIN_SRC_HYPOTHESIS": "1",
                     "BRAIN_SRC_EXPERIENCE": "1", "BRAIN_SRC_NEWS": "0",
                     "BRAIN_SRC_WORLDMODEL": "0", "BRAIN_SRC_CONCEPT": "0"}.items():
            os.environ[k] = v
        from trading.direction import brain_sources as bs
        self.bs = bs
        bs._CACHE.clear()

    def tearDown(self):
        import trading.state as state
        state.STATE_DIR = self._orig

    def test_bias_to_p_mapping(self):
        self.assertEqual(self.bs._bias_to_p(0.0), 0.5)
        self.assertEqual(self.bs._bias_to_p(1.0), 1.0)
        self.assertEqual(self.bs._bias_to_p(-1.0), 0.0)
        self.assertAlmostEqual(self.bs._bias_to_p(0.5), 0.75)
        self.assertIsNone(self.bs._bias_to_p("nan-ish"))
        # out-of-range clamps, never escapes [0,1]
        self.assertEqual(self.bs._bias_to_p(9.0), 1.0)

    def test_collect_never_raises_and_returns_readings(self):
        out = self.bs.collect("BTC/USDT:USDT", market="CRYPTO", segment="futures",
                              regime="bear", direction_hint="LONG", record=False)
        self.assertIsInstance(out, list)
        for src, p in out:
            self.assertIsInstance(src, str)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_master_switch_off_returns_empty(self):
        os.environ["BRAIN_SOURCES"] = "0"
        self.assertEqual(self.bs.collect("BTC/USDT:USDT", record=False), [])
        os.environ["BRAIN_SOURCES"] = "1"

    def test_deep_lane_never_raises_with_ohlcv(self):
        df = pd.DataFrame({"open": np.linspace(100, 110, 120), "high": np.linspace(101, 111, 120),
                           "low": np.linspace(99, 109, 120), "close": np.linspace(100, 110, 120),
                           "volume": np.ones(120)})
        os.environ["BRAIN_SRC_WORLDMODEL"] = "1"
        out = self.bs.collect("BTC/USDT:USDT", regime="bull", direction_hint="LONG",
                             ohlcv=df, fast=False, record=False)
        self.assertIsInstance(out, list)
        os.environ["BRAIN_SRC_WORLDMODEL"] = "0"

    def test_emitted_source_starts_weightless_in_fusion(self):
        """The safety guarantee: a brain source with no scored outcomes earns ~0 weight, so it
        cannot flip a decision on its own — learned_direction ABSTAINS on it alone."""
        from trading.direction import learned_direction as ld
        # a brand-new source name the ledger has never scored
        out = ld.decide([("hypothesis", 0.99)], market="CRYPTO", segment="futures",
                        regime="bear", symbol="ZZZ/USDT:USDT")
        # unproven ⇒ only a tiny exploration weight, below min_total_w ⇒ abstains alone
        # (it cannot flip a trade until the ledger scores it — the earn-weight guarantee)
        self.assertTrue(out["abstained"])
        w = out["weights"].get("hypothesis", {}).get("w", 0.0)
        self.assertLess(w, 0.015)      # LEARNED_DIR_MIN_TOTAL_W — can't drive on its own

    def test_status_shape(self):
        st = self.bs.status()
        for key in ("enabled", "hypothesis", "experience", "news",
                    "river_online", "world_model", "concept_discovery"):
            self.assertIn(key, st)

    def test_river_source_learns_and_predicts(self):
        """River source abstains until trained, then returns a calibrated P(up) in [0,1]."""
        from trading.direction import river_source as rs
        rs._MODEL = None                              # fresh isolated model in the temp STATE_DIR
        rs._BOOTSTRAPPED = False
        feats = {"m_funding": 0.6, "m_book": 0.55}
        self.assertIsNone(rs.predict(feats))          # untrained → abstain
        for i in range(60):                           # teach: high funding → up
            rs.learn({"m_funding": 0.6 + 0.001 * i, "m_book": 0.55}, up=True)
        p = rs.predict(feats)
        self.assertIsNotNone(p)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)
        self.assertTrue(rs.status()["ready"])

    def test_river_emits_through_collect(self):
        os.environ.update({"BRAIN_SRC_HYPOTHESIS": "0", "BRAIN_SRC_EXPERIENCE": "0",
                           "BRAIN_SRC_RIVER": "1"})
        from trading.direction import river_source as rs
        rs._MODEL = None
        rs._BOOTSTRAPPED = True                        # skip journal bootstrap in the test
        for i in range(60):
            rs.learn({"m_funding": 0.6, "m_book": 0.55}, up=(i % 2 == 0))
        out = self.bs.collect("BTC/USDT:USDT", regime="bear", direction_hint="LONG",
                             features={"m_funding": 0.6, "m_book": 0.55}, record=False)
        srcs = [s for s, _ in out]
        self.assertIn("river_online", srcs)


if __name__ == "__main__":
    unittest.main()


class TestHintRelativeRecordingFix(unittest.TestCase):
    """B1 fix (2026-07-16): hypothesis/experience biases score the HINTED side; the emitted
    p_up must be converted to an absolute direction. Before the fix, `hypothesis` recorded
    LONG 100% of the time (measured on 903 ledger rows)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        import trading.state as state
        self._orig = state.STATE_DIR
        state.STATE_DIR = pathlib.Path(self._tmp)
        for k, v in {"BRAIN_SOURCES": "1", "BRAIN_SRC_HYPOTHESIS": "1",
                     "BRAIN_SRC_EXPERIENCE": "0", "BRAIN_SRC_NEWS": "0",
                     "BRAIN_SRC_RIVER": "0", "BRAIN_SRC_WORLDMODEL": "0",
                     "BRAIN_SRC_CONCEPT": "0"}.items():
            os.environ[k] = v
        from trading.direction import brain_sources as bs
        self.bs = bs
        bs._CACHE.clear()

    def tearDown(self):
        import trading.state as state
        state.STATE_DIR = self._orig
        self.bs._CACHE.clear()

    def _with_support(self, bias, side=None):
        class _Led:
            def support(self, ctx):
                # side=None models GENERIC hypotheses (same answer for both directions —
                # must be gated out); side="LONG"/"SHORT" models hypotheses that genuinely
                # distinguish the sides (only the favored side gets support)
                if side is not None and ctx.get("direction") != side:
                    return {"bias": 0.0, "n": 0, "statements": []}
                return {"bias": bias, "n": 3, "statements": []}
        import time as _t
        self.bs._CACHE["hypothesis"] = (_Led(), _t.time())

    def test_short_hint_with_positive_support_votes_short(self):
        self._with_support(0.8, side="SHORT")     # "the hinted side wins" — hint is SHORT
        out = dict(self.bs.collect("BTC/USDT:USDT", market="CRYPTO", segment="futures",
                                   direction_hint="SHORT", record=False))
        self.assertIn("hypothesis", out)
        self.assertLess(out["hypothesis"], 0.5)   # absolute p_up must say DOWN

    def test_long_hint_with_positive_support_votes_long(self):
        self._with_support(0.8, side="LONG")
        out = dict(self.bs.collect("BTC/USDT:USDT", market="CRYPTO", segment="futures",
                                   direction_hint="LONG", record=False))
        self.assertGreater(out["hypothesis"], 0.5)

    def test_no_hint_emits_nothing(self):
        self._with_support(0.8, side="LONG")      # relative support needs a hint to interpret
        out = dict(self.bs.collect("BTC/USDT:USDT", market="CRYPTO", segment="futures",
                                   direction_hint=None, record=False))
        self.assertNotIn("hypothesis", out)

    def test_direction_agnostic_support_abstains(self):
        # generic hypotheses (same support both sides) carried no direction info yet used to
        # emit a constant ~0.976 vote — the side-differential gate must silence them
        self._with_support(0.8, side=None)
        out = dict(self.bs.collect("BTC/USDT:USDT", market="CRYPTO", segment="futures",
                                   direction_hint="LONG", record=False))
        self.assertNotIn("hypothesis", out)
