"""Trading Phase T8 (Advanced Intelligence) acceptance tests — fully offline.

Pins behaviour of the deferred `trading/advintel/` package with NO network of
any kind: every scraper/metric class is driven through INJECTED stub fetchers,
and the numeric modules run on seeded numpy data. One TestCase per module:

    portfolio_risk  — VaR/CVaR loss-sign + ordering, HRP/optimize weights,
                      drawdown, portfolio heat, Kelly, JSON report, degenerate.
    stress          — directional shock P&L (long loses / short gains on a
                      down move), what_if, scenario_analysis, report, empty-safe.
    fii_dii         — latest/trend/status over a stub of 5 days, empty-safe.
    nse_announcements — recent(kinds=)/for_symbol/classify/status over a stub.
    onchain         — fear&greed range, SOPR flip at 1.0, MVRV z-score zones,
                      honest available flags, empty-stub -> unavailable.
    liquidations    — heatmap/clusters/nearest_cluster/status, no-data unavail.
    arbitrage       — spot spread detection + direction + actionable, funding
                      farm profitability + leg direction, ranking, JSON-able.

Deterministic throughout. riskfolio/cvxpy deprecation noise is suppressed.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")  # riskfolio / cvxpy / pandas deprecation noise

import json
import unittest

import numpy as np
import pandas as pd

from trading.advintel.portfolio_risk import (
    PortfolioRisk,
    var,
    cvar,
    kelly_fraction,
    hrp_weights,
    max_drawdown,
    portfolio_heat,
    optimize,
)
from trading.advintel.stress import (
    Position,
    StressTester,
    stress_test,
    scenario_analysis,
    what_if,
)
from trading.advintel.fii_dii import FiiDiiFlows
from trading.advintel.nse_announcements import NseAnnouncements, classify
from trading.advintel.onchain import OnChainMetrics
from trading.advintel.liquidations import LiquidationHeatmap
from trading.advintel.arbitrage import ArbitrageScanner


# --------------------------------------------------------------------------- #
def _seeded_returns(n: int = 250, k: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    data = rng.normal(loc=0.0005, scale=0.012, size=(n, k))
    return pd.DataFrame(data, columns=[f"A{i}" for i in range(k)])


class TestPortfolioRisk(unittest.TestCase):
    def setUp(self):
        self.returns = _seeded_returns()
        self.pr = PortfolioRisk(self.returns, alpha=0.05)

    def test_var_cvar_floats_loss_sign_and_ordering(self):
        v = self.pr.var()
        c = self.pr.cvar()
        self.assertIsInstance(v, float)
        self.assertIsInstance(c, float)
        # 5% loss tail -> negative under the loss-sign convention
        self.assertLess(v, 0.0)
        self.assertLess(c, 0.0)
        # CVaR is the mean of the worst tail -> at least as extreme as VaR
        self.assertLessEqual(c, v)

    def test_module_level_var_matches_class(self):
        self.assertAlmostEqual(var(self.returns, 0.05), self.pr.var(), places=9)
        self.assertAlmostEqual(cvar(self.returns, 0.05), self.pr.cvar(), places=9)

    def test_hrp_weights_sum_to_one_and_nonnegative(self):
        w = self.pr.hrp()
        self.assertEqual(len(w), 4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=6)
        self.assertTrue(all(x >= 0.0 for x in w.values()))

    def test_optimize_returns_weights(self):
        w = optimize(self.returns, "MinRisk")
        self.assertEqual(len(w), 4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=4)
        self.assertTrue(all(np.isfinite(list(w.values()))))

    def test_max_drawdown_nonpositive(self):
        dd = self.pr.max_drawdown()
        self.assertIsInstance(dd, float)
        self.assertLessEqual(dd, 0.0)

    def test_kelly_fraction_shape(self):
        k = self.pr.kelly()
        self.assertEqual(set(k), set(self.returns.columns))
        for d in k.values():
            self.assertIn("kelly", d)
            self.assertIn("half_kelly", d)
            self.assertIn("capped", d)

    def test_portfolio_heat_fraction_in_unit_interval(self):
        positions = [
            {"symbol": "RELIANCE", "capital_at_risk": 5000.0},
            {"symbol": "TCS", "capital_at_risk": 3000.0},
        ]
        h = portfolio_heat(positions, total_capital=100000.0)
        self.assertGreaterEqual(h["heat"], 0.0)
        self.assertLessEqual(h["heat"], 1.0)
        self.assertAlmostEqual(h["heat"], 0.08, places=9)
        self.assertAlmostEqual(h["at_risk"], 8000.0, places=6)

    def test_report_is_json_dumps_able(self):
        rep = self.pr.report()
        self.assertEqual(rep["n_assets"], 4)
        self.assertEqual(rep["n_periods"], 250)
        json.dumps(rep)  # must not raise

    def test_single_asset_degenerate_does_not_crash(self):
        one = self.returns.iloc[:, [0]]
        pr1 = PortfolioRisk(one)
        self.assertEqual(hrp_weights(one), {"A0": 1.0})
        self.assertEqual(optimize(one), {"A0": 1.0})
        json.dumps(pr1.report())

    def test_all_zero_inputs_safe(self):
        zeros = pd.DataFrame(np.zeros((50, 3)), columns=["x", "y", "z"])
        prz = PortfolioRisk(zeros)
        # VaR/CVaR of a flat series -> 0.0, drawdown 0.0, weights still valid
        self.assertEqual(prz.var(), 0.0)
        self.assertEqual(prz.cvar(), 0.0)
        self.assertEqual(prz.max_drawdown(), 0.0)
        self.assertAlmostEqual(sum(hrp_weights(zeros).values()), 1.0, places=6)
        json.dumps(prz.report())


class TestStress(unittest.TestCase):
    def _book(self):
        return [
            Position("RELIANCE", "equity", "LONG", 100, 2900.0, beta=1.0),
            Position("BTCUSDT", "crypto", "SHORT", 2, 60000.0, beta=1.0),
        ]

    def test_down_scenario_long_loses_short_gains(self):
        res = stress_test(self._book(), "covid_2020")
        rows = {r["symbol"]: r for r in res["positions"]}
        self.assertLess(rows["RELIANCE"]["pnl_impact"], 0.0)   # long hit by crash
        self.assertGreater(rows["BTCUSDT"]["pnl_impact"], 0.0)  # short profits
        self.assertEqual(res["n_positions"], 2)
        self.assertEqual(res["scenario"], "covid_2020")

    def test_what_if_hits_the_long_only(self):
        res = what_if(self._book(), {"equity": -0.05})
        rows = {r["symbol"]: r for r in res["positions"]}
        # equity -5% hits the long equity position
        self.assertLess(rows["RELIANCE"]["pnl_impact"], 0.0)
        # exact first-order pnl: 100 * 2900 * -0.05 = -14500
        self.assertAlmostEqual(rows["RELIANCE"]["pnl_impact"], -14500.0, places=2)
        # DOCUMENTED contract (stress.shock_for): an unspecified asset class
        # falls back to the equity shock, so the crypto SHORT profits from it.
        self.assertGreater(rows["BTCUSDT"]["pnl_impact"], 0.0)
        self.assertAlmostEqual(rows["BTCUSDT"]["pnl_impact"], 6000.0, places=2)

    def test_scenario_analysis_covers_all(self):
        out = scenario_analysis(self._book())
        self.assertIsInstance(out, dict)
        self.assertIn("covid_2020", out)
        self.assertIn("gfc_2008", out)
        for v in out.values():
            self.assertIn("total_pnl_impact", v)

    def test_report_json_able(self):
        rep = StressTester().report(self._book())
        self.assertEqual(rep["n_positions"], 2)
        self.assertTrue(rep["generated_offline"])
        self.assertIsNotNone(rep["worst_scenario"])
        json.dumps(rep)

    def test_empty_positions_safe(self):
        res = stress_test([], "gfc_2008")
        self.assertEqual(res["n_positions"], 0)
        self.assertEqual(res["total_pnl_impact"], 0.0)
        json.dumps(StressTester().report([]))


class TestFiiDii(unittest.TestCase):
    def _stub(self):
        rows = [
            {"date": "2026-06-27", "fii_net": 1200.0, "dii_net": -300.0},
            {"date": "2026-06-26", "fii_net": 800.0, "dii_net": 200.0},
            {"date": "2026-06-25", "fii_net": -500.0, "dii_net": 600.0},
            {"date": "2026-06-24", "fii_net": 300.0, "dii_net": 100.0},
            {"date": "2026-06-23", "fii_net": -100.0, "dii_net": 50.0},
        ]
        return lambda: list(rows)

    def test_latest_is_most_recent(self):
        f = FiiDiiFlows(fetcher=self._stub())
        latest = f.latest()
        self.assertEqual(latest["date"], "2026-06-27")
        self.assertAlmostEqual(latest["fii_net"], 1200.0, places=6)

    def test_trend_cumulative_and_bias(self):
        f = FiiDiiFlows(fetcher=self._stub())
        t = f.trend(5)
        self.assertEqual(t["days"], 5)
        # cum fii = 1200+800-500+300-100 = 1700 (bullish)
        self.assertAlmostEqual(t["fii_net_cum"], 1700.0, places=2)
        self.assertEqual(t["fii_bias"], "FII bullish")
        # cum dii = -300+200+600+100+50 = 650 (bullish)
        self.assertAlmostEqual(t["dii_net_cum"], 650.0, places=2)
        self.assertEqual(t["dii_bias"], "DII bullish")

    def test_status_json_able(self):
        f = FiiDiiFlows(fetcher=self._stub())
        st = f.status()
        self.assertEqual(st["rows"], 5)
        json.dumps(st)

    def test_empty_stub_safe(self):
        f = FiiDiiFlows(fetcher=lambda: [])
        self.assertEqual(f.latest(), {})
        self.assertEqual(f.trend(5)["days"], 0)
        json.dumps(f.status())


class TestNseAnnouncements(unittest.TestCase):
    def _stub(self):
        rows = [
            {"symbol": "RELIANCE", "subject": "Q2 Results", "datetime": "2026-06-27"},
            {"symbol": "TCS", "subject": "Dividend declared", "datetime": "2026-06-26"},
            {"symbol": "INFY", "subject": "Board Meeting Intimation",
             "datetime": "2026-06-25"},
        ]
        return lambda: list(rows)

    def test_classify_mapping(self):
        self.assertEqual(classify("Q2 Results"), "earnings")
        self.assertEqual(classify("Dividend declared"), "corp_action")
        self.assertEqual(classify("Random update"), "other")

    def test_recent_filters_by_kind(self):
        a = NseAnnouncements(fetcher=self._stub())
        earnings = a.recent(kinds=["earnings"])
        self.assertEqual(len(earnings), 1)
        self.assertEqual(earnings[0]["symbol"], "RELIANCE")
        self.assertEqual(earnings[0]["type"], "earnings")

    def test_for_symbol_case_insensitive(self):
        a = NseAnnouncements(fetcher=self._stub())
        hits = a.for_symbol("reliance")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["symbol"], "RELIANCE")

    def test_status_json_able(self):
        a = NseAnnouncements(fetcher=self._stub())
        st = a.status()
        self.assertEqual(st["rows"], 3)
        self.assertEqual(st["by_type"]["earnings"], 1)
        self.assertEqual(st["by_type"]["corp_action"], 1)
        json.dumps(st)


class TestOnChain(unittest.TestCase):
    def _stub(self, sopr_val=1.05, mvrv_z=4.0):
        def fetch(kind):
            if kind == "fear_greed":
                return {"value": 40, "value_classification": "Fear"}
            if kind == "sopr":
                return {"sopr": sopr_val}
            if kind == "mvrv":
                return {"mvrvZscore": mvrv_z}
            return {}
        return fetch

    def test_fear_greed_in_range(self):
        m = OnChainMetrics(fetcher=self._stub())
        fg = m.fear_greed()
        self.assertTrue(fg["available"])
        self.assertGreaterEqual(fg["value"], 0.0)
        self.assertLessEqual(fg["value"], 100.0)

    def test_sopr_signal_flips_around_one(self):
        hi = OnChainMetrics(fetcher=self._stub(sopr_val=1.05)).sopr()
        lo = OnChainMetrics(fetcher=self._stub(sopr_val=0.95)).sopr()
        self.assertEqual(hi["signal"], "profit-taking")
        self.assertEqual(lo["signal"], "capitulation")

    def test_mvrv_signal_by_zscore(self):
        over = OnChainMetrics(fetcher=self._stub(mvrv_z=4.0)).mvrv()
        under = OnChainMetrics(fetcher=self._stub(mvrv_z=-1.0)).mvrv()
        self.assertEqual(over["signal"], "overvalued")
        self.assertEqual(under["signal"], "undervalued")

    def test_report_json_able_and_honest_flags(self):
        m = OnChainMetrics(fetcher=self._stub())
        rep = m.report()
        self.assertTrue(rep["available"])
        self.assertTrue(rep["fear_greed"]["available"])
        self.assertTrue(rep["sopr"]["available"])
        self.assertTrue(rep["mvrv"]["available"])
        json.dumps(rep)

    def test_empty_stub_unavailable(self):
        m = OnChainMetrics(fetcher=lambda kind: {})
        self.assertFalse(m.fear_greed()["available"])
        self.assertFalse(m.report()["available"])


class TestLiquidations(unittest.TestCase):
    def _stub(self):
        def fetch(symbol):
            return {"levels": [
                {"price": 58000.0, "notional": 5_000_000.0, "side": "long"},
                {"price": 62000.0, "notional": 9_000_000.0, "side": "short"},
                {"price": 55000.0, "notional": 1_000_000.0, "side": "long"},
            ]}
        return fetch

    def test_heatmap_returns_levels(self):
        h = LiquidationHeatmap(fetcher=self._stub()).heatmap("BTCUSDT")
        self.assertTrue(h["available"])
        self.assertEqual(len(h["levels"]), 3)

    def test_clusters_top_n_by_notional(self):
        c = LiquidationHeatmap(fetcher=self._stub()).clusters("BTCUSDT", n=2)
        self.assertEqual(len(c["clusters"]), 2)
        # ranked by notional desc -> 9M first, 5M second
        self.assertAlmostEqual(c["clusters"][0]["notional"], 9_000_000.0, places=2)
        self.assertAlmostEqual(c["clusters"][1]["notional"], 5_000_000.0, places=2)

    def test_nearest_cluster(self):
        nc = LiquidationHeatmap(fetcher=self._stub()).nearest_cluster("BTCUSDT", 57500.0)
        self.assertTrue(nc["available"])
        self.assertAlmostEqual(nc["cluster"]["price"], 58000.0, places=2)
        self.assertAlmostEqual(nc["distance"], 500.0, places=2)

    def test_status_json_able(self):
        st = LiquidationHeatmap(fetcher=self._stub()).status()
        self.assertEqual(st["source"], "injected")
        self.assertTrue(st["available"])
        json.dumps(st)

    def test_no_data_unavailable(self):
        h = LiquidationHeatmap(fetcher=lambda s: {})
        self.assertFalse(h.heatmap("BTCUSDT")["available"])
        self.assertFalse(h.clusters("BTCUSDT")["available"])
        self.assertFalse(h.nearest_cluster("BTCUSDT", 60000.0)["available"])


class TestArbitrage(unittest.TestCase):
    def _price_stub(self, big_spread=True):
        # binance cheap ask, bybit rich bid -> buy binance, sell bybit
        if big_spread:
            book = {
                "binance": {"bid": 99.9, "ask": 100.0},
                "bybit": {"bid": 100.4, "ask": 100.5},
            }
        else:
            book = {
                "binance": {"bid": 99.99, "ask": 100.0},
                "bybit": {"bid": 100.02, "ask": 100.03},
            }
        return lambda ex, sym: book[ex]

    def _funding_stub(self):
        rates = {"binance": 0.0001, "bybit": -0.0002}
        return lambda ex, sym: rates[ex]

    def test_scan_spot_detects_spread_and_direction(self):
        sc = ArbitrageScanner(price_source=self._price_stub())
        r = sc.scan_spot("BTC/USDT")
        self.assertEqual(r["best_ask_exch"], "binance")  # BUY here
        self.assertEqual(r["best_bid_exch"], "bybit")    # SELL here
        self.assertAlmostEqual(r["spread_abs"], 0.4, places=6)
        self.assertAlmostEqual(r["spread_pct"], 0.4 / 100.2 * 100.0, places=6)
        self.assertTrue(r["actionable"])
        json.dumps(r)

    def test_tiny_spread_not_actionable(self):
        sc = ArbitrageScanner(price_source=self._price_stub(big_spread=False))
        r = sc.scan_spot("BTC/USDT")
        self.assertFalse(r["actionable"])  # net spread below round-trip cost

    def test_scan_universe_ranks(self):
        sc = ArbitrageScanner(price_source=self._price_stub())
        out = sc.scan_universe(["BTC/USDT", "ETH/USDT"])
        self.assertEqual(len(out), 2)
        self.assertGreaterEqual(out[0]["spread_pct"], out[1]["spread_pct"])
        json.dumps(out)

    def test_funding_farm_profitable_and_legs(self):
        sc = ArbitrageScanner(funding_source=self._funding_stub())
        r = sc.funding_farm("BTC/USDT")
        # positive rate -> longs pay shorts: SHORT the high venue, LONG the low
        self.assertEqual(r["short_exch"], "binance")  # +0.0001 (high)
        self.assertEqual(r["long_exch"], "bybit")     # -0.0002 (low)
        self.assertAlmostEqual(r["net_funding_rate"], 0.0003, places=9)
        self.assertTrue(r["profitable"])
        json.dumps(r)

    def test_status_json_able(self):
        sc = ArbitrageScanner(price_source=self._price_stub(),
                              funding_source=self._funding_stub())
        st = sc.status()
        self.assertEqual(st["price_source"], "injected")
        self.assertEqual(st["funding_source"], "injected")
        json.dumps(st)


if __name__ == "__main__":
    unittest.main()
