"""Pillar 17 — conformal calibrated uncertainty (trading/uq) + sizing gate tests.

State isolation: every test that touches TradeUQ persistence points
trading.state.STATE_DIR at a temp dir first (project rule: never mutate the
live paper journal/state from tests).
"""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


def _synth_trades(n: int = 400, seed: int = 7) -> list[dict]:
    """Synthetic closed trades whose pnl is driven by the recorded confidence."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        conf = float(rng.uniform(0.3, 0.9))
        pnl_pct = (conf - 0.5) * 12 + float(rng.normal(0, 2.0))
        rows.append({
            "symbol": "BTC/USDT" if i % 2 else "RELIANCE",
            "direction": "LONG" if i % 3 else "SHORT",
            "instrument_type": "PERP" if i % 2 else "EQ",
            "brain_confidence_entry": conf,
            "trader_psychology": float(rng.uniform(-0.5, 0.5)),
            "net_pnl_pct": pnl_pct,
            "net_pnl": pnl_pct * 10,
            "exit_datetime": f"2026-01-{(i % 28) + 1:02d}T10:00:00",
        })
    return rows


class TestSelfUncertainty(unittest.TestCase):
    def test_vote_entropy(self):
        from trading.uq import self_uncertainty_from_votes as su
        self.assertEqual(su(5, 5), 1.0)               # perfect disagreement
        self.assertEqual(su(10, 0), 0.0)              # unanimous
        self.assertAlmostEqual(su(9, 1), -(0.9 * math.log2(0.9) + 0.1 * math.log2(0.1)), places=3)
        self.assertIsNone(su(0, 0))
        self.assertIsNone(su(None, None))


class TestTradeUQ(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        import trading.state as st
        self._patch = mock.patch.object(st, "STATE_DIR", Path(self.tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def _uq(self, **kw):
        from trading.uq.conformal import TradeUQ
        return TradeUQ(**kw)

    def test_calibrates_and_covers(self):
        uq = self._uq()
        s = uq.recalibrate(_synth_trades())
        self.assertEqual(s["engine"], "crepes_cps")
        # ACI-adapted coverage must be near the 90% target on the holdout
        self.assertGreaterEqual(s["coverage_holdout_aci"], 0.78)
        self.assertTrue(s["reliability"])             # reliability bins exist

    def test_p_up_tracks_confidence(self):
        uq = self._uq()
        uq.recalibrate(_synth_trades())
        hi = uq.assess(confidence=0.85, direction="LONG", market="CRYPTO")
        lo = uq.assess(confidence=0.32, direction="LONG", market="CRYPTO")
        self.assertGreater(hi["p_up"], lo["p_up"])
        self.assertGreater(hi["p_up"], 0.55)          # profitable regime → tradeable
        for k in ("p_up", "interval", "interval_width", "self_uncertainty",
                  "abstain", "abstain_reason", "size_scale", "engine"):
            self.assertIn(k, hi)

    def test_abstains_on_low_p_up_and_logs(self):
        uq = self._uq()
        uq.recalibrate(_synth_trades())
        out = uq.assess(confidence=0.32, direction="LONG", market="CRYPTO",
                        symbol="ETH/USDT")
        self.assertTrue(out["abstain"])
        self.assertIn("p_up", out["abstain_reason"])
        log = uq.abstentions()
        self.assertTrue(log and log[0]["symbol"] == "ETH/USDT")   # first-class, logged

    def test_abstains_on_extreme_self_uncertainty(self):
        uq = self._uq()
        uq.recalibrate(_synth_trades())
        out = uq.assess(confidence=0.85, direction="LONG", market="CRYPTO",
                        longs=5, shorts=5)
        self.assertTrue(out["abstain"])
        self.assertIn("self-uncertainty", out["abstain_reason"])

    def test_half_size_on_high_disagreement(self):
        uq = self._uq()
        uq.recalibrate(_synth_trades())
        out = uq.assess(confidence=0.85, direction="LONG", market="CRYPTO",
                        longs=7, shorts=4)            # entropy ≈ 0.946 ∈ [0.85, 0.97)
        self.assertFalse(out["abstain"])
        self.assertEqual(out["size_scale"], 0.5)

    def test_fallback_on_thin_journal(self):
        uq = self._uq()
        s = uq.recalibrate(_synth_trades(30))
        self.assertEqual(s["engine"], "fallback")
        out = uq.assess(confidence=0.6, direction="LONG", market="NSE")
        self.assertIn("p_up", out)                    # still gates, never crashes

    def test_advisory_mode_never_blocks(self):
        uq = self._uq(p_up_min=0.99)                  # would abstain on everything
        uq.enforce = False
        uq.recalibrate(_synth_trades())
        out = uq.assess(confidence=0.6, direction="LONG", market="CRYPTO")
        self.assertFalse(out["abstain"])
        self.assertTrue(out["would_abstain"])
        self.assertIn("advisory", out["abstain_reason"])

    def test_maybe_recalibrate_time_gate(self):
        uq = self._uq()
        self.assertIsNotNone(uq.maybe_recalibrate())  # never fitted → fits
        self.assertIsNone(uq.maybe_recalibrate())     # fresh → skipped


class TestSizerConsumesUQ(unittest.TestCase):
    def test_abstain_returns_zero_with_reason(self):
        from trading.sizing import PositionSizer
        out = PositionSizer(method="auto").size(
            capital=10_000, entry_price=100, atr=2, side="LONG",
            uq={"abstain": True, "abstain_reason": "p_up 0.25 < θ 0.55"})
        self.assertEqual(out["qty"], 0.0)
        self.assertEqual(out["method"], "abstain")
        self.assertIn("p_up 0.25", out["reason"])

    def test_p_up_used_as_prob_and_scale_applied(self):
        from trading.sizing import PositionSizer
        sizer = PositionSizer(method="auto")
        full = sizer.size(capital=10_000, entry_price=100, atr=2, side="LONG",
                          uq={"abstain": False, "p_up": 0.7, "size_scale": 1.0})
        half = sizer.size(capital=10_000, entry_price=100, atr=2, side="LONG",
                          uq={"abstain": False, "p_up": 0.7, "size_scale": 0.5})
        self.assertGreater(full["qty"], 0)
        self.assertAlmostEqual(half["qty"], full["qty"] * 0.5, places=6)
        self.assertIn("ai_meta", full["reason"])      # p_up drove the edge sizing


class TestJournalColumns(unittest.TestCase):
    def test_schema_has_uq_columns(self):
        from trading.journal.schema import COLUMNS, ClosedTrade
        for col in ("p_up", "interval_width", "self_uncertainty", "abstain_reason"):
            self.assertIn(col, COLUMNS)
        t = ClosedTrade(p_up=0.61, interval_width=12.5, self_uncertainty=0.3,
                        abstain_reason="")
        d = t.to_dict()
        self.assertEqual(d["p_up"], 0.61)


if __name__ == "__main__":
    unittest.main()
