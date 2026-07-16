"""Tests for trading/direction/dir_exit — the directional EXIT oracle (Pillar 27).

Seeds REAL Truth-Ledger buckets so the Mirror Gate calibration runs for real; only the
live micro-lane snapshot is stubbed (that's the network/feather boundary)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

import trading.state as state


def _seed(buckets: dict, market: str = "CRYPTO") -> None:
    """Seed truth buckets in the market-scoped key format (2026-07-13): the legacy
    "source|regime|horizon" keys get MARKET injected → "source|MARKET|regime|horizon"."""
    scoped = {}
    for k, v in buckets.items():
        src, rest = k.split("|", 1)
        scoped[f"{src}|{market.upper()}|{rest}"] = v
    state.save_json("direction_truth.json", {"buckets": scoped})


def _snap(votes: dict):
    """Build a micro_features.snapshot-shaped dict from {lane: (vote, conf)}."""
    from trading.direction import micro_features
    snap = {"symbol": "X", "segment": "futures"}
    for lane in micro_features.LANES:
        v = votes.get(lane)
        snap[lane] = {"vote": v[0], "conf": v[1]} if v else {"vote": None}
    return snap


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import dir_exit, micro_features, mirror_gate
        mirror_gate._CACHE.update(ts=0.0, buckets=None)   # drop cross-test cache
        self.de = dir_exit
        self.mf = micro_features
        self._real_snap = micro_features.snapshot
        self._env = {k: os.environ.get(k) for k in
                     ("DIR_EXIT", "DIR_EXIT_STRENGTH", "MIRROR_GATE")}

    def tearDown(self):
        self.mf.snapshot = self._real_snap
        state.STATE_DIR = self._o
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._t.cleanup()

    def _patch_votes(self, votes):
        self.mf.snapshot = lambda *a, **k: _snap(votes)

    def _pending(self):
        p = Path(state.STATE_DIR) / "direction_truth_pending.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


class TestRead(_Iso):
    def test_calibrated_agreeing_lanes_make_a_strong_read(self):
        # calibration machinery needs the gate: enable explicitly (retired in prod, MIRROR_GATE=0)
        os.environ["MIRROR_GATE"] = "1"
        self.addCleanup(os.environ.__setitem__, "MIRROR_GATE", "0")
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 130},   # 65% trusted
               "mtf_agree|chop|1h": {"n": 200, "correct": 128}})
        self._patch_votes({"venue_leadlag": ("LONG", 0.8), "mtf_agree": ("LONG", 0.7)})
        r = self.de.read("ETH/USDT:USDT", "CRYPTO", "futures", regime="chop")
        self.assertEqual(r["direction"], "LONG")
        self.assertGreater(r["strength"], 0.9)
        self.assertEqual(r["n_calibrated"], 2)
        self.assertGreater(r["cal_strength"], 0.9)

    def test_retired_gate_never_inverts_an_anti_signal_lane(self):
        # Mirror Gate RETIRED 2026-07-16 (CONVENTIONS §16: direction must be EARNED — never
        # invert). Production config MIRROR_GATE=0: an "anti-signal" lane passes through raw.
        os.environ["MIRROR_GATE"] = "0"
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 60}})   # 30% — would have inverted
        self._patch_votes({"venue_leadlag": ("LONG", 0.9)})
        r = self.de.read("ETH/USDT:USDT", "CRYPTO", "futures", regime="chop")
        self.assertEqual(r["direction"], "LONG")                      # NOT flipped
        self.assertNotEqual(r["votes"][0].get("action"), "invert")

    def test_uncalibrated_lane_votes_but_does_not_move_cal_strength(self):
        _seed({"venue_leadlag|chop|1h": {"n": 5, "correct": 4}})      # n too small
        self._patch_votes({"venue_leadlag": ("LONG", 0.8)})
        r = self.de.read("ETH/USDT:USDT", "CRYPTO", "futures", regime="chop")
        self.assertEqual(r["direction"], "LONG")                     # still votes
        self.assertEqual(r["n_calibrated"], 0)
        self.assertEqual(r["cal_strength"], 0.0)


class TestEvaluate(_Iso):
    def test_shadow_records_claim_and_advises_but_never_exits(self):
        os.environ["DIR_EXIT"] = "shadow"
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 130}})  # trusted
        self._patch_votes({"venue_leadlag": ("SHORT", 0.9)})          # read = SHORT
        d = self.de.evaluate(symbol="ETH/USDT:USDT", direction="LONG", segment="futures",
                             regime="chop", ref_price=100.0)
        self.assertFalse(d["exit"])                                   # shadow never exits
        self.assertTrue(d["advisory_exit"])                           # but would have
        self.assertEqual(d["mode"], "shadow")
        rows = self._pending()
        self.assertEqual(rows[-1]["source"], "dir_exit")             # earns its own record
        self.assertEqual(rows[-1]["direction"], "SHORT")

    def test_trade_mode_exits_on_calibrated_opposing_read(self):
        os.environ["DIR_EXIT"] = "trade"
        os.environ["MIRROR_GATE"] = "1"                # calibration needs the gate machinery
        self.addCleanup(os.environ.__setitem__, "MIRROR_GATE", "0")
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 130}})  # trusted
        self._patch_votes({"venue_leadlag": ("SHORT", 0.9)})
        d = self.de.evaluate(symbol="ETH/USDT:USDT", direction="LONG", segment="futures",
                             regime="chop", ref_price=100.0)
        self.assertTrue(d["exit"])
        self.assertGreaterEqual(d["cal_opposing"], 0.6)
        self.assertIn("calibrated read flipped", d["reason"])

    def test_trade_mode_holds_on_uncalibrated_opposing_read(self):
        os.environ["DIR_EXIT"] = "trade"
        _seed({"venue_leadlag|chop|1h": {"n": 5, "correct": 4}})      # uncalibrated
        self._patch_votes({"venue_leadlag": ("SHORT", 0.9)})
        d = self.de.evaluate(symbol="ETH/USDT:USDT", direction="LONG", segment="futures",
                             regime="chop", ref_price=100.0)
        self.assertFalse(d["exit"])                                   # never cut on a hunch
        self.assertTrue(d["advisory_exit"])

    def test_thesis_intact_when_read_agrees_with_position(self):
        os.environ["DIR_EXIT"] = "trade"
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 130}})
        self._patch_votes({"venue_leadlag": ("LONG", 0.9)})          # agrees with LONG
        d = self.de.evaluate(symbol="ETH/USDT:USDT", direction="LONG", segment="futures",
                             regime="chop", ref_price=100.0)
        self.assertFalse(d["exit"])
        self.assertFalse(d["advisory_exit"])
        self.assertIn("thesis intact", d["reason"])

    def test_off_switch_is_a_pure_no_op(self):
        os.environ["DIR_EXIT"] = "0"
        _seed({"venue_leadlag|chop|1h": {"n": 200, "correct": 130}})
        self._patch_votes({"venue_leadlag": ("SHORT", 0.9)})
        d = self.de.evaluate(symbol="ETH/USDT:USDT", direction="LONG", segment="futures",
                             regime="chop", ref_price=100.0)
        self.assertFalse(d["exit"])
        self.assertEqual(d["mode"], "off")
        self.assertEqual(self._pending(), [])                        # no claim recorded


if __name__ == "__main__":
    unittest.main()
