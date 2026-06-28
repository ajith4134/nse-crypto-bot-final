"""Trading Phase T4 (Options Intelligence) acceptance tests — fully offline.

Pins KNOWN-VALUE assertions against the pure-Python options analytics so CI passes
with no broker/exchange access: Black-76 Greeks + implied vol, IV rank/percentile,
max pain, PCR, dealer gamma exposure (GEX), OI heatmap/tracker, multi-leg payoff,
and the OptionsChain container that stitches them together. The live chain feed is
exercised separately by the run_* scripts; here every input is injected.
"""
from __future__ import annotations

import math
import unittest

from trading.options.chain import OptionLeg, OptionQuote, OptionsChain
from trading.options.gex import gamma_exposure, zero_gamma_level
from trading.options.greeks import black76_price, get_all_greeks, implied_vol
from trading.options.iv import IVHistory, iv_percentile, iv_rank
from trading.options.max_pain import max_pain
from trading.options.oi import OITracker, classify_oi_change, oi_heatmap
from trading.options.payoff import PayoffLeg, payoff_summary
from trading.options.pcr import put_call_ratio


class TestBlack76Greeks(unittest.TestCase):
    def test_put_call_parity_at_atm_zero_rate(self):
        c = black76_price("c", 100.0, 100.0, 0.5, 0.0, 0.2)
        p = black76_price("p", 100.0, 100.0, 0.5, 0.0, 0.2)
        self.assertAlmostEqual(c, p, places=10)        # F=K, r=0 → symmetric
        self.assertGreater(c, 0.0)

    def test_delta_difference_equals_discount(self):
        gc = get_all_greeks("c", 100.0, 100.0, 0.5, 0.05, 0.2)
        gp = get_all_greeks("p", 100.0, 100.0, 0.5, 0.05, 0.2)
        # Black-76: Δcall − Δput = e^(−rt)
        self.assertAlmostEqual(gc["delta"] - gp["delta"], math.exp(-0.05 * 0.5), places=8)
        self.assertEqual(gc["backend"], "analytic")

    def test_gamma_vega_positive_theta_negative(self):
        g = get_all_greeks("c", 100.0, 100.0, 0.5, 0.05, 0.2)
        self.assertGreater(g["gamma"], 0.0)
        self.assertGreater(g["vega"], 0.0)
        self.assertLess(g["theta"], 0.0)              # long option bleeds time value
        # put shares gamma/vega sign, long put theta also negative
        gp = get_all_greeks("p", 100.0, 100.0, 0.5, 0.05, 0.2)
        self.assertGreater(gp["gamma"], 0.0)
        self.assertGreater(gp["vega"], 0.0)

    def test_deep_itm_and_otm_call_delta(self):
        df = math.exp(-0.05 * 0.5)
        itm = get_all_greeks("c", 1000.0, 100.0, 0.5, 0.05, 0.2)
        otm = get_all_greeks("c", 10.0, 1000.0, 0.5, 0.05, 0.2)
        self.assertAlmostEqual(itm["delta"], df, places=4)   # deep ITM → e^(−rt)
        self.assertAlmostEqual(otm["delta"], 0.0, places=4)  # deep OTM → 0

    def test_all_greeks_keys(self):
        g = get_all_greeks("c", 100.0, 100.0, 0.25, 0.065, 0.18)
        for key in ("price", "delta", "gamma", "vega", "theta", "rho", "backend"):
            self.assertIn(key, g)


class TestImpliedVol(unittest.TestCase):
    def test_round_trip(self):
        price = black76_price("c", 100.0, 100.0, 0.5, 0.05, 0.3)
        iv = implied_vol(price, "c", 100.0, 100.0, 0.5, 0.05)
        self.assertIsNotNone(iv)
        self.assertAlmostEqual(iv, 0.3, places=5)
        # puts round-trip too
        pp = black76_price("p", 105.0, 100.0, 0.4, 0.05, 0.25)
        ivp = implied_vol(pp, "p", 105.0, 100.0, 0.4, 0.05)
        self.assertAlmostEqual(ivp, 0.25, places=5)

    def test_at_intrinsic_returns_zero(self):
        # call F=110 K=100 r=0 t=1 → intrinsic = 10 exactly
        self.assertEqual(implied_vol(10.0, "c", 110.0, 100.0, 1.0, 0.0), 0.0)

    def test_below_intrinsic_returns_none(self):
        self.assertIsNone(implied_vol(5.0, "c", 110.0, 100.0, 1.0, 0.0))

    def test_above_forward_bound_returns_none(self):
        # upper bound = df*F = 110 at r=0; a price above it has no vol
        self.assertIsNone(implied_vol(115.0, "c", 110.0, 100.0, 1.0, 0.0))


class TestIVRankPercentile(unittest.TestCase):
    def test_rank_midpoint(self):
        history = list(range(10, 21))            # 10..20
        self.assertAlmostEqual(iv_rank(15.0, history), 50.0, places=9)

    def test_percentile_differs_from_rank_when_skewed(self):
        history = [10, 10, 10, 10, 10, 20]       # skewed low
        rank = iv_rank(15.0, history)
        pct = iv_percentile(15.0, history)
        self.assertAlmostEqual(rank, 50.0, places=9)         # range midpoint
        self.assertAlmostEqual(pct, 5 / 6 * 100.0, places=6)  # 5 of 6 below 15
        self.assertNotAlmostEqual(rank, pct, places=2)

    def test_degenerate_range_rank_none(self):
        self.assertIsNone(iv_rank(15.0, [12.0, 12.0, 12.0]))

    def test_ivhistory_respects_lookback_maxlen(self):
        h = IVHistory(lookback=3)
        h.extend([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(h.values, [3.0, 4.0, 5.0])          # deque maxlen=3
        self.assertEqual(len(h.values), 3)

    def test_ivhistory_rank_percentile(self):
        h = IVHistory(lookback=252).extend([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        # current defaults to last pushed (20) → top of range
        self.assertAlmostEqual(h.rank(), 100.0, places=9)
        self.assertIsNotNone(h.percentile())


class TestMaxPain(unittest.TestCase):
    def setUp(self):
        # OI concentrated at 100 → pain is clearly minimised there
        self.call_oi = {90: 10, 100: 100, 110: 10}
        self.put_oi = {90: 10, 100: 100, 110: 10}

    def test_strike_is_minimiser(self):
        res = max_pain(self.call_oi, self.put_oi)
        self.assertEqual(res["max_pain_strike"], 100)
        # hand-computed: pain(100)=200, pain(90)=pain(110)=1200
        self.assertAlmostEqual(res["pain_curve"][100], 200.0, places=6)
        self.assertAlmostEqual(res["pain_curve"][90], 1200.0, places=6)
        self.assertAlmostEqual(res["pain_curve"][110], 1200.0, places=6)

    def test_pain_curve_covers_all_strikes(self):
        res = max_pain(self.call_oi, self.put_oi)
        self.assertEqual(set(res["pain_curve"]), {90, 100, 110})
        self.assertEqual(res["total_call_oi"], 120)
        self.assertEqual(res["total_put_oi"], 120)


class TestPCR(unittest.TestCase):
    def test_pcr_oi_hand_computed(self):
        call_oi = {100: 200, 110: 100}   # total 300
        put_oi = {90: 150, 100: 300}     # total 450
        res = put_call_ratio(call_oi, put_oi)
        self.assertAlmostEqual(res["pcr_oi"], 1.5, places=9)
        self.assertNotIn("pcr_volume", res)            # no volumes passed
        self.assertIn(100, res["per_strike"])

    def test_pcr_volume_present_when_passed(self):
        call_oi = {100: 200}
        put_oi = {100: 300}
        res = put_call_ratio(call_oi, put_oi,
                             call_volume={100: 400}, put_volume={100: 200})
        self.assertAlmostEqual(res["pcr_volume"], 0.5, places=9)

    def test_pcr_oi_none_without_call_oi(self):
        res = put_call_ratio({}, {100: 50})
        self.assertIsNone(res["pcr_oi"])


class TestGEX(unittest.TestCase):
    def test_total_sign_flips_with_net_oi(self):
        pos = gamma_exposure([{"strike": 100, "gamma": 0.01, "call_oi": 100, "put_oi": 0}],
                             spot=100.0)
        neg = gamma_exposure([{"strike": 100, "gamma": 0.01, "call_oi": 0, "put_oi": 100}],
                             spot=100.0)
        self.assertGreater(pos["total_gex"], 0.0)
        self.assertEqual(pos["regime"], "positive")
        self.assertLess(neg["total_gex"], 0.0)
        self.assertEqual(neg["regime"], "negative")

    def test_walls_are_extreme_gex_strikes(self):
        rows = [
            {"strike": 100, "gamma": 0.02, "call_oi": 200, "put_oi": 0},    # big +GEX
            {"strike": 105, "gamma": 0.01, "call_oi": 10, "put_oi": 10},    # ~0
            {"strike": 110, "gamma": 0.02, "call_oi": 0, "put_oi": 300},    # big −GEX
        ]
        res = gamma_exposure(rows, spot=100.0)
        self.assertEqual(res["call_wall"], 100)   # largest positive GEX
        self.assertEqual(res["put_wall"], 110)    # largest negative GEX
        self.assertLess(res["total_gex"], 0.0)

    def test_zero_gamma_interpolation(self):
        per_strike = [{"strike": 100, "gex": -10.0}, {"strike": 110, "gex": 30.0}]
        # cumulative crosses 0 a third of the way: 100 + (10/30)*10 = 103.333…
        self.assertAlmostEqual(zero_gamma_level(per_strike), 103.3333333, places=4)
        # no sign change → None
        self.assertIsNone(zero_gamma_level([{"strike": 100, "gex": 5.0},
                                            {"strike": 110, "gex": 5.0}]))


class TestOI(unittest.TestCase):
    def test_classify_four_quadrants(self):
        self.assertEqual(classify_oi_change(1.0, 1.0), "long_buildup")
        self.assertEqual(classify_oi_change(-1.0, 1.0), "short_buildup")
        self.assertEqual(classify_oi_change(1.0, -1.0), "short_covering")
        self.assertEqual(classify_oi_change(-1.0, -1.0), "long_unwinding")
        self.assertEqual(classify_oi_change(0.0, 0.0), "flat")

    def test_heatmap_walls_and_intensity(self):
        res = oi_heatmap({100: 50, 110: 200}, {90: 300, 100: 100}, top_n=1)
        self.assertEqual(res["call_walls"], [110])   # highest call OI
        self.assertEqual(res["put_walls"], [90])     # highest put OI
        # intensities normalised to [0,1]; the max-OI strike hits 1.0
        cell110 = next(c for c in res["cells"] if c["strike"] == 110)
        self.assertAlmostEqual(cell110["call_intensity"], 1.0, places=9)

    def test_tracker_init_then_delta(self):
        t = OITracker()
        first = t.update({100: 1000}, price=50.0)
        self.assertEqual(first["per_strike"][100]["signal"], "init")
        self.assertEqual(first["price_change"], 0.0)
        # price up + OI up → long buildup
        second = t.update({100: 1500}, price=55.0)
        self.assertEqual(second["per_strike"][100]["oi_change"], 500)
        self.assertEqual(second["per_strike"][100]["signal"], "long_buildup")
        self.assertAlmostEqual(second["price_change"], 5.0, places=9)


class TestPayoff(unittest.TestCase):
    def test_long_straddle_breakevens_and_max_loss(self):
        legs = [PayoffLeg("call", "long", 100.0, premium=5.0),
                PayoffLeg("put", "long", 100.0, premium=5.0)]
        s = payoff_summary(legs, lo=50.0, hi=150.0, steps=101)  # step 1.0 hits integers
        self.assertEqual(sorted(round(b, 6) for b in s["breakevens"]), [90.0, 110.0])
        self.assertAlmostEqual(s["max_loss"], -10.0, places=6)  # −(total premium)
        self.assertAlmostEqual(s["max_loss_at"], 100.0, places=6)

    def test_bull_call_spread_bounded(self):
        legs = [PayoffLeg("call", "long", 100.0, premium=6.0),
                PayoffLeg("call", "short", 110.0, premium=2.0)]
        s = payoff_summary(legs, lo=50.0, hi=150.0, steps=101)
        self.assertAlmostEqual(s["max_profit"], 6.0, places=6)   # (110-100)-4 debit
        self.assertAlmostEqual(s["max_loss"], -4.0, places=6)    # net debit
        self.assertAlmostEqual(s["net_premium"], -4.0, places=6)  # debit paid
        # genuinely bounded: both wings are flat (P&L pinned at the edges)
        self.assertAlmostEqual(s["curve"][0]["pnl"], -4.0, places=6)
        self.assertAlmostEqual(s["curve"][-1]["pnl"], 6.0, places=6)

    def test_underlying_leg_linear(self):
        leg = PayoffLeg("underlying", "long", 100.0)
        self.assertAlmostEqual(leg.pnl_at(120.0), 20.0, places=9)
        self.assertAlmostEqual(leg.pnl_at(80.0), -20.0, places=9)


class TestOptionsChain(unittest.TestCase):
    def _chain(self) -> OptionsChain:
        quotes = []
        data = {95: (50, 8.5), 100: (300, 4.5), 105: (200, 2.0), 110: (120, 0.9)}
        for k, (oi, ltp) in data.items():
            quotes.append(OptionQuote(strike=k, opt_type="CE", oi=oi, volume=oi * 2,
                                      ltp=ltp, iv=0.2))
            quotes.append(OptionQuote(strike=k, opt_type="PE", oi=oi + 50, volume=oi,
                                      ltp=ltp, iv=0.2))
        return OptionsChain(quotes, forward=102.0, t=0.05, r=0.065, spot=102.0, lot_size=1)

    def test_atm_and_basic_analytics(self):
        ch = self._chain()
        self.assertEqual(ch.atm_strike(), 100)        # strike nearest forward 102
        self.assertAlmostEqual(ch.atm_iv(), 0.2, places=9)
        mp = ch.max_pain()
        self.assertIn(mp["max_pain_strike"], {95, 100, 105, 110})
        pcr = ch.pcr()
        self.assertIsNotNone(pcr["pcr_oi"])
        self.assertGreater(pcr["pcr_oi"], 0.0)        # puts carry extra OI

    def test_greeks_of_quote(self):
        ch = self._chain()
        q = ch._calls[100]
        g = ch.greeks_of(q)
        self.assertIsNotNone(g)
        self.assertGreater(g["gamma"], 0.0)
        self.assertAlmostEqual(g["iv"], 0.2, places=9)

    def test_payoff_through_chain(self):
        ch = self._chain()
        legs = [OptionLeg(strike=100.0, opt_type="CE", position="long")]
        s = ch.payoff(legs, lo=50.0, hi=150.0, steps=101)
        self.assertIn("breakevens", s)
        self.assertAlmostEqual(s["max_loss"], -4.5, places=6)   # long call premium 4.5

    def test_status_keys_and_no_exception(self):
        ch = self._chain()
        st = ch.status()
        for key in ("forward", "spot", "t_years", "r", "n_strikes", "atm_strike",
                    "atm_iv", "max_pain", "pcr_oi", "gex", "oi_walls"):
            self.assertIn(key, st)
        self.assertEqual(st["n_strikes"], 4)
        for key in ("total_gex", "regime", "zero_gamma", "call_wall", "put_wall"):
            self.assertIn(key, st["gex"])
        self.assertEqual(set(st["oi_walls"]), {"call", "put"})


if __name__ == "__main__":
    unittest.main()
