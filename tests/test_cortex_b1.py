"""CORTEX B1 (Foundations) acceptance tests — segments + labels + fitness.

Mirrors tests/test_columns.py style: unittest, synthetic data with a KNOWN
generating process, zero live state touched (nothing is written anywhere).

  S  core/segments.py — market-segment overlay routes real node names to the
     expected segments, unknown names land in `general`, every segment carries
     a valid pipeline stage, grouping/layout mirror the columns.py contract.
  L  trading/labels.py — barrier labeler (CANON-28, PNP-14/15) reproduces
     HAND-COMPUTED labels on a hand-built price path; SLTPRatio asymmetry
     works; the mandatory class-balance check warns on imbalance.
  F  trading/fitness.py — on a synthetic trending series, perfect-foresight
     signals PASS the honesty gates while naive/random signals FAIL them
     (CANON-36/38); the scorecard has every CANON-39 key fee-inclusive
     (CANON-40); underwater_fitness ranks a smooth equity path above a choppy
     one with the same profit (CANON-41).
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from core.segments import (SEGMENTS, STAGES, group_by_segment, segment_for,
                           segment_layout)
from trading.fitness import (benchmark_gate, honest_report, majority_gate,
                             persistence_gate, run_signals, scorecard,
                             underwater_fitness)
from trading.labels import DOWN, UNCLEAR, UP, barrier_label, class_balance


# ── S. segment taxonomy ──────────────────────────────────────────────────────

class TestSegmentTaxonomy(unittest.TestCase):
    def test_real_node_names_route_to_expected_segments(self):
        # vocabulary from nodes/pool.py + run_multi.domain_pool (real catalog)
        self.assertEqual(segment_for("option_iv"), "options")
        self.assertEqual(segment_for("freqtrade_ingest"), "crypto")
        self.assertEqual(segment_for("openalgo_nifty_fut"), "nse_equity")
        self.assertEqual(segment_for("dukascopy_eurusd"), "forex")
        self.assertEqual(segment_for("garch_vol"), "risk_regime")
        self.assertEqual(segment_for("hmm_regime2"), "risk_regime")
        self.assertEqual(segment_for("conformal"), "meta_routing")
        self.assertEqual(segment_for("nbeats"), "forecasting")
        self.assertEqual(segment_for("sk_logreg"), "forecasting")
        self.assertEqual(segment_for("xgboost"), "forecasting")
        self.assertEqual(segment_for("catch22"), "features")
        self.assertEqual(segment_for("pandas_ta"), "features")
        # kind-based routing (same contract as columns.py)
        self.assertEqual(segment_for("anything", kind="router"), "meta_routing")
        self.assertEqual(segment_for("mystery_net", kind="dl"), "forecasting")

    def test_unknown_node_lands_in_general(self):
        """Open-to-future: a brand-new node with no rule still gets a segment."""
        self.assertEqual(segment_for("totally_new_experimental_2027"), "general")

    def test_every_segment_has_a_valid_pipeline_stage(self):
        self.assertEqual(STAGES, ("data", "features", "detection", "forecasting",
                                  "decision", "execution"))
        for seg in SEGMENTS:
            self.assertIn(seg.stage, STAGES, f"{seg.key} has invalid stage {seg.stage}")

    def test_grouping_preserves_segment_order_and_drops_empties(self):
        names = ["xgboost", "garch_vol", "catch22", "option_iv", "hmm_regime2"]
        facs = [object()] * len(names)
        grouped = group_by_segment(facs, names)
        # order follows the SEGMENTS stack, empties dropped
        self.assertEqual(list(grouped),
                         ["options", "risk_regime", "forecasting", "features"])
        self.assertEqual([nm for _, nm in grouped["risk_regime"]],
                         ["garch_vol", "hmm_regime2"])
        layout = segment_layout(grouped)
        self.assertEqual([d["key"] for d in layout], list(grouped))
        for d in layout:
            self.assertIn(d["stage"], STAGES)          # stage travels to the dashboard
            self.assertEqual(d["size"], len(d["members"]))


# ── L. barrier labeler (CANON-28, PNP-14/15) ─────────────────────────────────

class TestBarrierLabels(unittest.TestCase):
    # hand-built path; pipdiff=1.0, ratio=1.0, horizon=3 → labels computed by hand
    CLOSE = np.array([100.0, 100.2, 101.1, 99.4, 99.5, 99.6, 100.0, 100.05,
                      100.0, 99.95])

    def test_hand_computed_labels(self):
        labels = barrier_label(self.CLOSE, pipdiff=1.0, sl_tp_ratio=1.0,
                               horizon_bars=3)
        #  i=0: +1.1 at j=2 → UP;  i=1: max +0.9/min −0.8 → UNCLEAR;
        #  i=2: −1.7 first → DOWN;  i=3.. never ±1.0 in window → UNCLEAR
        expected = [UP, UNCLEAR, DOWN, UNCLEAR, UNCLEAR, UNCLEAR, UNCLEAR,
                    UNCLEAR, UNCLEAR, UNCLEAR]
        self.assertEqual(labels.tolist(), expected)

    def test_sl_tp_ratio_tightens_the_down_barrier(self):
        """PNP-14 SLTPRatio: ratio=0.5 halves the stop barrier → bar 1 flips to DOWN
        (−0.8 hits the −0.5 barrier before +0.9 reaches the +1.0 target)."""
        labels = barrier_label(self.CLOSE, pipdiff=1.0, sl_tp_ratio=0.5,
                               horizon_bars=3)
        self.assertEqual(labels[1], DOWN)
        self.assertEqual(labels[0], UP)                # up barrier unchanged

    def test_invalid_params_rejected(self):
        with self.assertRaises(ValueError):
            barrier_label(self.CLOSE, pipdiff=0.0)
        with self.assertRaises(ValueError):
            barrier_label(self.CLOSE, pipdiff=1.0, sl_tp_ratio=0.0)

    def test_class_balance_warns_on_imbalance(self):
        """PNP-15: the class-balance check is mandatory — a <10% (or missing)
        class raises the warn flag; a balanced target does not."""
        bad = class_balance([UNCLEAR] * 95 + [UP] * 5)
        self.assertTrue(bad["warn"])
        self.assertIn(UP, bad["warn_classes"])         # 5% < 10%
        self.assertIn(DOWN, bad["warn_classes"])       # missing class flagged too
        self.assertEqual(bad["counts"][DOWN], 0)
        good = class_balance([DOWN] * 34 + [UNCLEAR] * 33 + [UP] * 33)
        self.assertFalse(good["warn"])
        self.assertEqual(good["warn_classes"], [])
        self.assertAlmostEqual(sum(good["shares"].values()), 1.0)


# ── F. fitness engine + honesty gates (CANON-36/38/39/40/41) ─────────────────

def _trending_market(n_cycles=12, up_len=8, dn_len=4, up=0.02, dn=-0.015):
    """Deterministic up-trending series with periodic dips (KNOWN process):
    up_len bars of +2% then dn_len bars of −1.5%, repeated. Perfect foresight
    = long during up-runs, flat during dips → beats buy-and-hold honestly."""
    rets, longs = [], []
    for _ in range(n_cycles):
        rets += [up] * up_len + [dn] * dn_len
        longs += [True] * up_len + [False] * dn_len
    close = 100.0 * np.cumprod(1.0 + np.array([0.0] + rets[:-1]))
    idx = pd.date_range("2024-01-01", periods=len(close), freq="1D")
    longs = np.array(longs)
    # enter when the NEXT bar rises, exit when it falls (foresight of `rets`)
    entries = pd.Series(longs & ~np.roll(longs, 1), index=idx)
    exits = pd.Series(~longs & np.roll(longs, 1), index=idx)
    return pd.Series(close, index=idx), entries, exits


class TestFitnessEngine(unittest.TestCase):
    def setUp(self):
        self.close, self.entries, self.exits = _trending_market()
        self.pf = run_signals(self.close, self.entries, self.exits,
                              fee=0.0005, freq="1D")

    def test_scorecard_keys_present_and_fee_inclusive(self):
        card = scorecard(self.pf)
        for key in ("sharpe", "sortino", "cagr", "max_dd", "expectancy",
                    "win_rate", "n_trades", "profit_per_trade", "total_return",
                    "total_fees_paid"):
            self.assertIn(key, card)
        self.assertGreater(card["n_trades"], 5)
        self.assertGreater(card["profit_per_trade"], 0.0)   # $/round-trip headline
        self.assertGreater(card["total_fees_paid"], 0.0)    # CANON-40: fees really charged
        self.assertEqual(card["win_rate"], 1.0)             # foresight never loses

    def test_perfect_foresight_passes_benchmark_gate(self):
        """CANON-38: skipping every dip beats buy-and-hold's CAGR/MaxDD ratio."""
        passed, detail = benchmark_gate(self.pf, self.close)
        self.assertTrue(passed, detail)
        self.assertGreater(detail["model_cagr_over_maxdd"],
                           detail["buy_hold_cagr_over_maxdd"])

    def test_persistence_gate_pass_and_fail(self):
        """CANON-36 regression: near-perfect forecasts pass; noise fails."""
        rng = np.random.RandomState(7)
        y_true = self.close.values
        good = y_true + rng.randn(len(y_true)) * 1e-4        # ≈ perfect forecast
        passed, detail = persistence_gate(y_true, good)
        self.assertTrue(passed, detail)
        self.assertLess(detail["mse_model"], detail["mse_persistence"])
        self.assertLess(detail["dm_p"], 0.1)
        bad = y_true + rng.randn(len(y_true)) * 50.0         # noise-dominated forecast
        passed, detail = persistence_gate(y_true, bad)
        self.assertFalse(passed, detail)

    def test_majority_gate_pass_and_fail(self):
        """CANON-36 classification: beat the majority share, strictly."""
        rng = np.random.RandomState(7)
        y = np.array([1] * 60 + [0] * 40)
        passed, detail = majority_gate(y, y)                 # perfect predictor
        self.assertTrue(passed)
        self.assertEqual(detail["majority_share"], 0.6)
        passed, _ = majority_gate(y, np.ones_like(y))        # majority parrot: acc == share
        self.assertFalse(passed)
        passed, detail = majority_gate(y, rng.randint(0, 2, size=len(y)))  # coin flip
        self.assertFalse(passed, detail)

    def test_underwater_fitness_prefers_smooth_equity(self):
        """CANON-41: same total profit, but the choppy path (deep dip) scores lower."""
        n = 120
        idx = pd.date_range("2024-01-01", periods=n, freq="1D")
        smooth = pd.Series(np.linspace(100.0, 150.0, n), index=idx)
        dip = np.linspace(100.0, 150.0, n)
        dip[30:70] -= 35.0 * np.sin(np.linspace(0, np.pi, 40))  # −35% underwater trough
        choppy = pd.Series(dip, index=idx)
        hold = pd.Series([True] + [False] * (n - 1), index=idx)
        none = pd.Series(False, index=idx)
        pf_smooth = run_signals(smooth, hold, none, fee=0.0005, freq="1D")
        pf_choppy = run_signals(choppy, hold, none, fee=0.0005, freq="1D")
        fit_smooth, fit_choppy = underwater_fitness(pf_smooth), underwater_fitness(pf_choppy)
        # same realized+unrealized profit …
        self.assertAlmostEqual(float(pf_smooth.total_profit()),
                               float(pf_choppy.total_profit()), places=6)
        # … but the underwater term ranks the smooth path strictly higher
        self.assertGreater(fit_smooth, fit_choppy)
        self.assertGreater(fit_choppy, 0.0)

    def test_honest_report_combines_gates_and_never_hides_failures(self):
        rng = np.random.RandomState(7)
        y_cls = np.array([1] * 60 + [0] * 40)
        report = honest_report(pf=self.pf, close=self.close,
                               y_true=self.close.values,
                               y_pred=self.close.values + rng.randn(len(self.close)) * 1e-4,
                               y_true_cls=y_cls, y_pred_cls=np.ones_like(y_cls))
        self.assertEqual(set(report["gates"]), {"persistence", "majority", "benchmark"})
        self.assertIn("scorecard", report)
        self.assertIn("underwater_fitness", report)
        # the majority gate FAILED and the report says so — honestly
        self.assertFalse(report["gates"]["majority"]["passed"])
        self.assertFalse(report["all_passed"])
        self.assertTrue(report["gates"]["persistence"]["passed"])
        self.assertTrue(report["gates"]["benchmark"]["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
