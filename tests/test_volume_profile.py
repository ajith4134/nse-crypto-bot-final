"""Tests for trading/broker_sense/volume_profile.py — VP / Value-Area engine.

Constructed candles with known answers: POC lands on the heavy price, the value area brackets
it and encloses ~70%, sessions bucket by UTC day (crypto) / IST day (nse), value migration
reads a rising POC as bullish, a failed auction below VAL that closes back inside fires long,
and absorption flags a down-move on declining volume. Honest degrade on too-few bars.
"""
from __future__ import annotations

import unittest

from trading.broker_sense import volume_profile as vp

DAY = 86_400_000        # ms


def _bar(ts, o, h, l, c, v):
    return [ts, o, h, l, c, v]


def _flat_at(price, n=40, vol=100.0, ts0=1_700_000_000_000, step=300_000):
    """n bars hugging one price → POC/VA must center there."""
    return [_bar(ts0 + i * step, price, price + 1, price - 1, price, vol) for i in range(n)]


class TestProfile(unittest.TestCase):
    def test_poc_on_heavy_price(self):
        rows = _flat_at(100.0, 30)
        # inject 5 very heavy bars at ~120 → POC should move up there
        rows += [_bar(1_700_000_000_000 + (30 + i) * 300_000, 120, 121, 119, 120, 5000)
                 for i in range(5)]
        p = vp.volume_profile(rows)
        self.assertTrue(p["available"])
        self.assertGreater(p["poc"], 115)
        self.assertGreaterEqual(p["vah"], p["poc"])
        self.assertLessEqual(p["val"], p["poc"])
        self.assertGreaterEqual(p["va_pct"], 0.68)

    def test_va_brackets_poc(self):
        p = vp.volume_profile(_flat_at(50.0, 40))
        self.assertLessEqual(p["val"], p["poc"] + 1e-6)
        self.assertGreaterEqual(p["vah"], p["poc"] - 1e-6)

    def test_too_few_bars_degrades(self):
        self.assertFalse(vp.volume_profile(_flat_at(100.0, 5)).get("available"))
        self.assertFalse(vp.volume_profile([]).get("available"))


class TestSessionKey(unittest.TestCase):
    def test_crypto_utc_day(self):
        a = vp.session_key(1_700_000_000_000, "crypto")
        b = vp.session_key(1_700_000_000_000 + DAY, "crypto")
        self.assertEqual(b - a, 1)

    def test_nse_ist_shift(self):
        # a ts late in UTC evening falls on the NEXT day in IST → different key vs crypto
        ts = 1_700_074_800_000        # ~20:00 UTC
        self.assertNotEqual(vp.session_key(ts, "nse"), vp.session_key(ts, "crypto"))

    def test_seconds_or_ms(self):
        self.assertEqual(vp.session_key(1_700_000_000_000, "crypto"),
                         vp.session_key(1_700_000_000, "crypto"))


class TestMigration(unittest.TestCase):
    def test_rising_poc_bullish(self):
        rows = []
        for d in range(4):                       # 4 daily sessions, POC steps up each day
            base = 100.0 + d * 8
            for i in range(30):
                ts = 1_700_000_000_000 + d * DAY + i * 300_000
                rows.append(_bar(ts, base, base + 1, base - 1, base, 100))
        mig = vp.value_migration(rows, "crypto")
        self.assertEqual(mig["bias"], "bullish")
        self.assertGreater(mig["slope"], 0)
        self.assertEqual(mig["n_sessions"], 4)

    def test_falling_poc_bearish(self):
        rows = []
        for d in range(4):
            base = 200.0 - d * 8
            for i in range(30):
                ts = 1_700_000_000_000 + d * DAY + i * 300_000
                rows.append(_bar(ts, base, base + 1, base - 1, base, 100))
        self.assertEqual(vp.value_migration(rows, "crypto")["bias"], "bearish")


class TestFailedAuction(unittest.TestCase):
    def test_failed_below_fires_long(self):
        rows = _flat_at(100.0, 38)               # value area ~100
        # poke below, then close back inside with a volume pickup
        rows.append(_bar(rows[-1][0] + 300_000, 100, 100, 90, 92, 80))     # dips under VAL
        rows.append(_bar(rows[-1][0] + 300_000, 92, 101, 92, 100, 900))    # closes back inside
        fa = vp.failed_auction(rows, "crypto")
        self.assertEqual(fa["signal"], "long")
        self.assertGreater(fa["strength"], 0.5)

    def test_inside_value_no_signal(self):
        fa = vp.failed_auction(_flat_at(100.0, 40), "crypto")
        self.assertEqual(fa["signal"], "none")


class TestAbsorption(unittest.TestCase):
    def test_down_move_declining_volume_bid(self):
        rows = [_bar(1_700_000_000_000 + i * 300_000, 100 - i, 100 - i + 0.5, 100 - i - 0.5,
                     100 - i, 500 - i * 60) for i in range(8)]     # price down, volume fading
        ab = vp.absorption(rows)
        self.assertTrue(ab["absorbing"])
        self.assertEqual(ab["side"], "bid")

    def test_insufficient_bars(self):
        self.assertFalse(vp.absorption(_flat_at(100.0, 3))["absorbing"])


class TestOrderPlan(unittest.TestCase):
    def test_long_targets_vah_stops_below(self):
        rows = _flat_at(100.0, 40)
        plan = vp.order_plan(rows, "long", "crypto")
        self.assertIsNotNone(plan)
        self.assertGreaterEqual(plan["target"], plan["entry"] - 2)   # VAH near/above entry
        self.assertLess(plan["stop"], plan["entry"])                 # stop below
        self.assertEqual(plan["basis"], "volume_profile_value_area")

    def test_neutral_and_short_bars_none(self):
        self.assertIsNone(vp.order_plan(_flat_at(100.0, 40), "neutral", "crypto"))
        self.assertIsNone(vp.order_plan(_flat_at(100.0, 5), "long", "crypto"))


class TestFeatures(unittest.TestCase):
    def test_shape_and_tilt_bounded(self):
        f = vp.features(_flat_at(100.0, 40), "crypto")
        self.assertTrue(f["available"])
        self.assertIn(f["zone"], ("above_value", "below_value", "in_value"))
        self.assertGreaterEqual(f["tilt"], -1.0)
        self.assertLessEqual(f["tilt"], 1.0)

    def test_degrade(self):
        f = vp.features(_flat_at(100.0, 5), "crypto")
        self.assertFalse(f["available"])
        self.assertEqual(f["tilt"], 0.0)


if __name__ == "__main__":
    unittest.main()
