"""CORTEX B9 — the 13 PARTIAL→FULL canon gap-closers.

Backend coverage for CANON-01 (gap map), 02 (pattern levels), 05 (downloaders
importable + offline-safe), 06 (timeframe arbitration), 09 (categorical one-hot),
34 (sweep harness), 37/58 (classification eval + confusion-structure verdict),
43 (anti-overfit telemetry). The UI gaps (45/54/55/56) are exercised by the web
build + verify-live, not unittest."""
import os
import tempfile
import unittest

import numpy as np
import pandas as pd


class TestGapMap(unittest.TestCase):        # CANON-01
    def test_gap_map_shape_and_bias(self):
        from trading.brain.psychology import gap_map, BookSnapshot
        snap = BookSnapshot(ts=0.0,
                            bids=[(100, 5), (99, 3), (98, 10)],
                            asks=[(101, 2), (102, 8), (110, 1)])
        g = gap_map(snap, depths=(1, 5, 10, 20))
        self.assertEqual(set(g["depths"]), {"1", "5", "10", "20"})
        # wider ask span (jump to 110) → positive gap bias (thin resistance above)
        self.assertGreater(g["gap_map_bias"], 0.0)
        for d in g["depths"].values():
            self.assertIn("span_bid_bps", d)
            self.assertIn("gap_bias", d)

    def test_gap_map_empty_book(self):
        from trading.brain.psychology import gap_map, BookSnapshot
        self.assertEqual(gap_map(BookSnapshot(ts=0, bids=[], asks=[]))["gap_map_bias"], 0.0)


class TestPatternLevels(unittest.TestCase):     # CANON-02
    def test_emits_entry_stop_target(self):
        from trading.features_ta import pattern_levels
        rng = np.random.RandomState(1)
        px = 100 + np.cumsum(rng.randn(80))
        df = pd.DataFrame({"open": px, "high": px + abs(rng.randn(80)),
                           "low": px - abs(rng.randn(80)), "close": px + rng.randn(80) * 0.2})
        out = pattern_levels(df)
        for row in out:
            self.assertIn(row["side"], ("long", "short"))
            self.assertTrue(all(k in row for k in ("entry", "stop", "target", "rr")))
            self.assertGreaterEqual(row["rr"], 0.0)
            if row["side"] == "long":
                self.assertGreater(row["target"], row["entry"])
            else:
                self.assertLess(row["target"], row["entry"])


class TestOneHot(unittest.TestCase):            # CANON-09
    def test_train_only_vocab_and_apply(self):
        from trading.features_ta import one_hot_features
        tr = pd.DataFrame({"sess": ["a", "b", "a"], "x": [1, 2, 3]})
        enc, cats = one_hot_features(tr, ["sess"])
        self.assertEqual(set(cats["sess"]), {"a", "b"})
        self.assertIn("sess=a", enc.columns)
        self.assertNotIn("sess", enc.columns)
        # unseen category at apply time → all-zero, no new column (no leakage)
        te = pd.DataFrame({"sess": ["c"], "x": [9]})
        enc2, _ = one_hot_features(te, ["sess"], categories=cats)
        self.assertEqual(int(enc2["sess=a"].iloc[0]), 0)
        self.assertEqual(int(enc2["sess=b"].iloc[0]), 0)


class TestArbitrate(unittest.TestCase):         # CANON-06
    def test_short_tf_wins_and_tie_breaks_to_daily(self):
        from trading.fitness import arbitrate_timeframe
        self.assertEqual(arbitrate_timeframe("x", {"sharpe": 2.0}, {"sharpe": 1.0})["verdict"], "short_tf")
        self.assertEqual(arbitrate_timeframe("x", {"sharpe": 1.02}, {"sharpe": 1.0})["verdict"], "daily")
        self.assertEqual(arbitrate_timeframe("x", {"sharpe": 1.0}, {"sharpe": 2.0})["verdict"], "daily")


class TestClassificationEval(unittest.TestCase):    # CANON-37 + 58
    def test_bundle_and_collapse_verdict(self):
        from trading.classification_eval import classification_eval, confusion_structure_verdict
        yt = [0, 1, 0, 1, 1, 0, 1, 0]
        yp_collapse = [0, 0, 0, 0, 0, 0, 0, 0]      # model always says 0
        v = confusion_structure_verdict(yt, yp_collapse)
        self.assertEqual(v["verdict"], "fail")
        self.assertTrue(any(f["kind"] == "majority-collapse" for f in v["flags"]))
        ev = classification_eval(yt, [0, 1, 0, 1, 1, 0, 1, 0])
        self.assertEqual(ev["report"]["accuracy"], 1.0)
        self.assertEqual(ev["structure_verdict"]["verdict"], "ok")
        self.assertIn("confusion", ev)


class TestSweep(unittest.TestCase):             # CANON-34
    def test_logged_sweep_leaderboard(self):
        from trading.sweep import run_sweep, grid, chrono_split
        tr, va = chrono_split(100, 0.2)
        self.assertEqual(len(tr), 80)
        self.assertEqual(va[0], 80)             # ordered, no shuffle
        rng = np.random.RandomState(0)
        X = rng.randn(160, 4); y = (X[:, 0] > 0).astype(int)

        class Dummy:
            def __init__(self, p, seed): self.t = p["thr"]
            def fit(self, X, y): return self
            def predict(self, X): return (X[:, 0] > self.t).astype(int)

        with tempfile.TemporaryDirectory() as d:
            res = run_sweep(lambda p, s: Dummy(p, s), X, y,
                            grid(thr=[0.0, 0.5]), log_name="unit_sweep")
            self.assertEqual(res["n_ok"], 2)
            self.assertIsNotNone(res["best"])
            self.assertTrue(os.path.exists(res["log_path"]))


class TestAntiOverfit(unittest.TestCase):       # CANON-43
    def test_telemetry_and_counter(self):
        from trading.antioverfit import telemetry, register_backtest, param_count
        n0 = register_backtest(0)
        register_backtest(2)
        t = telemetry()
        self.assertGreaterEqual(t["backtests_run"], n0 + 2)
        self.assertIn(t["overfit_risk"], ("ok", "watch", "high"))
        pc = param_count({"nodes": [{"kept": True}], "edges": [1, 2, 3]})
        self.assertEqual(pc["free_params"], 4)


class TestSelectiveAccuracy(unittest.TestCase):     # abstaining-trader metric
    def test_accuracy_rises_with_confidence(self):
        from eval.golden import selective_accuracy
        rng = np.random.RandomState(0)
        y = rng.randint(0, 2, 400)
        # informative but noisy proba: confident subset should score higher
        p = np.clip(np.where(y == 1, 0.7, 0.3) + rng.randn(400) * 0.25, 0, 1)
        rows = selective_accuracy(p, y, coverages=(0.5, 0.1))
        self.assertEqual([r["coverage"] for r in rows], [0.5, 0.1])
        self.assertGreater(rows[1]["accuracy"], rows[0]["accuracy"] - 1e-9)
        for r in rows:
            self.assertGreaterEqual(r["baseline"], 0.5)
            self.assertEqual(r["n"], max(1, int(np.ceil(r["coverage"] * 400))))


class TestFeatureBus(unittest.TestCase):        # brain feature bus (all data streams)
    def _df(self, n=300):
        rng = np.random.RandomState(3)
        px = 100 + np.cumsum(rng.randn(n))
        return pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=n, freq="15min"),
            "open": px, "high": px + 1, "low": px - 1, "close": px,
            "volume": rng.rand(n) * 10})

    def test_feature_vector_shape_and_names(self):
        from trading.cortex_signal import FEATURE_NAMES, build_features
        X, c = build_features(self._df(), "FAKE/PAIR")
        self.assertEqual(X.shape[1], len(FEATURE_NAMES))
        self.assertEqual(len(X), len(c))
        # unknown pair → psych/live blocks zero-filled with ok flags = 0 (honest)
        names = {n: i for i, n in enumerate(FEATURE_NAMES)}
        self.assertTrue((X[:, names["psych_ok"]] == 0).all())
        self.assertTrue((X[:, names["live_ok"]] == 0).all())

    def test_live_recorder_roundtrip(self):
        import tempfile
        from trading import feature_bus as fb
        with tempfile.TemporaryDirectory() as d:
            old = fb._LIVE_DIR
            fb._LIVE_DIR = d
            try:
                df = self._df(50)
                ts = float(pd.to_datetime(df["date"].iloc[-1]).timestamp())
                fb.record_live("X/Y", {"ts": ts, "regime_p0": 0.7, "psych_fear": 0.2})
                block = fb.live_block(df, "X/Y")
                self.assertEqual(block.shape, (50, len(fb.LIVE_NAMES)))
                self.assertEqual(block[-1, -1], 1.0)          # live_ok on last bar
                self.assertAlmostEqual(block[-1, 0], 0.7)     # regime_p0 joined
            finally:
                fb._LIVE_DIR = old


class TestDownloadersImportable(unittest.TestCase):     # CANON-05 (offline-safe)
    def test_symbols_present(self):
        from data import downloads
        for fn in ("download_dukascopy", "download_nse_bhavcopy"):
            self.assertTrue(hasattr(downloads, fn))


if __name__ == "__main__":
    unittest.main()
