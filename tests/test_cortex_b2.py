"""CORTEX B2 tests — video lanes, scratch core, risk overlay, rollout, TA.

Fast synthetic data only (sine+noise / regime shifts); tiny epochs; NO network
downloads (the MNIST self-check lives behind nodes/scratch_core.py __main__)."""
from __future__ import annotations

import unittest

import numpy as np

from core.node_protocol import NodeProtocol


def _sine_data(n=240, f=6, seed=0):
    """Chronological features + next-bar-up labels from a noisy sine regime."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    base = np.sin(t / 9.0) + 0.05 * rng.standard_normal(n)
    base[n // 2:] += 0.5                                     # regime shift
    X = np.stack([base] + [np.roll(base, k) + 0.02 * rng.standard_normal(n)
                           for k in range(1, f)], axis=1)
    y = (np.diff(base, append=base[-1]) > 0).astype(int)
    return X, y


class TestBuildWindows(unittest.TestCase):
    def test_shapes_and_alignment_hand_checked(self):
        from nodes.video_lanes import build_windows
        A = np.arange(24, dtype=float).reshape(8, 3)         # rows 0..7, F=3
        X, y = build_windows(A, lookback=3, target_col=2, horizon=1)
        # N = 8 - 3 - 1 + 1 = 5
        self.assertEqual(X.shape, (5, 3, 3))
        self.assertEqual(y.shape, (5,))
        # window 0 = rows 0..2; its target = row 3, col 2 = 3*3+2 = 11
        np.testing.assert_array_equal(X[0], A[0:3])
        self.assertEqual(y[0], 11.0)
        # last window = rows 4..6, target row 7 col 2 = 23
        np.testing.assert_array_equal(X[-1], A[4:7])
        self.assertEqual(y[-1], 23.0)

    def test_horizon_and_no_target(self):
        from nodes.video_lanes import build_windows
        A = np.arange(20, dtype=float).reshape(10, 2)
        X, y = build_windows(A, lookback=4, target_col=0, horizon=2)
        self.assertEqual(X.shape, (5, 4, 2))                 # 10-4-2+1
        self.assertEqual(y[0], A[5, 0])                      # 4+2-1 = row 5
        X2, y2 = build_windows(A, lookback=4)
        self.assertIsNone(y2)
        self.assertEqual(X2.shape, (6, 4, 2))


class TestVideoLanes(unittest.TestCase):
    """Every lane fits on tiny data and predicts finite, correctly shaped
    probabilities; every lane satisfies NodeProtocol."""

    @classmethod
    def setUpClass(cls):
        X, y = _sine_data(n=160, f=4)
        cls.X = [[float(v) for v in row] for row in X]
        cls.y = [int(v) for v in y]

    def _check(self, node):
        self.assertIsInstance(node, NodeProtocol)
        node.fit(self.X, self.y)
        p = node.predict_proba(self.X)
        self.assertEqual(len(p), len(self.X))
        self.assertTrue(all(np.isfinite(p)))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))
        labels = node.predict(self.X)
        self.assertTrue(set(labels) <= {0, 1})
        return node

    def test_tcn_prob_node(self):
        from nodes.video_lanes import TCNProbNode
        node = self._check(TCNProbNode(lookback=16, channels=(8, 8), epochs=2))
        # streaming mode emits one finite prob per bar
        node.reset_stream()
        s = [node.predict_stream_step(self.X[i]) for i in range(5)]
        self.assertTrue(all(np.isfinite(s)) and all(0 <= v <= 1 for v in s))

    def test_encoder_transformer_node(self):
        from nodes.video_lanes import EncoderTransformerNode
        node = EncoderTransformerNode(lookback=12, epochs=2)
        self._check(node)
        # spec-faithful internals: 2 layers / d_model 64 / learnable pos-emb
        self.assertEqual(node._model.pos_embedding.shape, (1, 12, 64))
        self.assertEqual(len(node._model.encoder.layers), 2)

    def test_lstm_lane_node(self):
        from nodes.video_lanes import LSTMLaneNode
        node = LSTMLaneNode(backcandles=10, epochs=2)
        self._check(node)
        self.assertEqual(node._model.lstm.hidden_size, 150)  # Keras twin

    def test_mlp_lanes(self):
        from nodes.video_lanes import SkMLPLaneNode, TorchMLPLaneNode
        self._check(SkMLPLaneNode(hidden_layer_sizes=(8, 8, 4)))
        self._check(TorchMLPLaneNode(hidden_layer_sizes=(8, 8), epochs=10))

    def test_dlinear_node(self):
        from nodes.video_lanes import DLinearNode
        node = DLinearNode(lookback=12, epochs=3, kernel_size=5)
        node.fit(self.X, self.y)
        out = node.predict_output(self.X)
        self.assertEqual(len(out), len(self.X))
        self.assertTrue(all(len(r) == 1 and np.isfinite(r[0]) for r in out))
        v = node.rollout_step(np.linspace(0, 1, 12))         # rollout hook
        self.assertTrue(np.isfinite(v))

    def test_factories(self):
        from nodes import video_lanes as vl
        for fac in (vl.tcn_prob_node, vl.encoder_transformer_node,
                    vl.lstm_lane_node, vl.mlp_lane_sklearn_node,
                    vl.mlp_lane_torch_node, vl.dlinear_node):
            self.assertIsInstance(fac(), NodeProtocol)


class TestScratchCore(unittest.TestCase):
    def test_scratchnet_learns_xor(self):
        from nodes.scratch_core import ScratchNet
        rng = np.random.default_rng(0)
        base = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], float)
        X = np.tile(base, (100, 1)) + 0.05 * rng.standard_normal((400, 2))
        y = (np.abs(np.round(X[:, 0]) - np.round(X[:, 1])) > 0.5).astype(int)
        net = ScratchNet([2, 16, 16, 2], lr=0.3, seed=0, init_scale=0.5)
        net.fit(X, y, epochs=120, batch_size=16)
        self.assertGreater(net.accuracy(X, y), 0.90)
        # per-epoch train (+val) loss log exists and decreased
        self.assertEqual(len(net.history), 120)
        self.assertLess(net.history[-1]["train_loss"],
                        net.history[0]["train_loss"])

    def test_validate_forward_external_weights(self):
        from nodes.scratch_core import ScratchNet, validate_forward
        rng = np.random.default_rng(1)
        X = rng.standard_normal((200, 3))
        y = (X.sum(axis=1) > 0).astype(int)
        trained = ScratchNet([3, 8, 2], lr=0.2, seed=0).fit(X, y, epochs=60)
        fresh = ScratchNet([3, 8, 2], seed=99)               # different init
        acc = validate_forward(fresh, trained.get_weights(), X, y)
        self.assertAlmostEqual(acc, trained.accuracy(X, y))  # GRC-13
        self.assertGreater(acc, 0.85)

    def test_scratchrnn_loss_decreases(self):
        from nodes.scratch_core import ScratchRNN
        rng = np.random.default_rng(2)
        t = np.arange(140)
        s = np.sin(t / 5.0) + 0.05 * rng.standard_normal(len(t))
        seqs = np.stack([np.stack([s[i:i + 10], np.roll(s, 1)[i:i + 10]],
                                  axis=1) for i in range(len(s) - 10)])
        tgt = s[10:]
        rnn = ScratchRNN(feature_count=2)                    # defaults 10/64/.01
        self.assertEqual((rnn.lookback, rnn.hidden_size, rnn.learning_rate),
                         (10, 64, 0.01))
        rnn.fit(seqs, tgt, epochs=4)
        self.assertLess(rnn.history[-1]["train_loss"],
                        rnn.history[0]["train_loss"])

    def test_node_wrappers_are_neurons(self):
        from nodes.scratch_core import scratch_net_node, scratch_rnn_node
        X, y = _sine_data(n=120, f=3)
        X = [[float(v) for v in r] for r in X]
        y = [int(v) for v in y]
        for fac in (scratch_net_node, scratch_rnn_node):
            node = fac()
            self.assertIsInstance(node, NodeProtocol)
            self.assertEqual(node.kind, "scratch")
            if node.name == "scratch_net":
                node.epochs = 5
            else:
                node.epochs = 1
            node.fit(X, y)
            p = node.predict_proba(X)
            self.assertEqual(len(p), len(X))
            self.assertTrue(all(0.0 <= v <= 1.0 for v in p))


class TestRiskOverlay(unittest.TestCase):
    def test_dead_band_abstains(self):
        from trading.risk_overlay import RiskOverlay
        ro = RiskOverlay(dead_band=0.05, target_risk=0.01, exposure_cap=0.5)
        self.assertEqual(ro.position(0.52, 0.02), 0.0)       # inside band
        self.assertEqual(ro.position(0.5, 0.02), 0.0)
        self.assertNotEqual(ro.position(0.60, 0.02), 0.0)    # outside band

    def test_inverse_vol_and_cap_and_sign(self):
        from trading.risk_overlay import RiskOverlay
        ro = RiskOverlay(dead_band=0.02, target_risk=0.01, exposure_cap=0.5)
        lo = ro.position(0.7, 0.10)                          # high vol
        hi = ro.position(0.7, 0.02)                          # low vol
        self.assertGreater(hi, lo)                           # size ~ 1/sigma
        self.assertLessEqual(abs(ro.position(0.9, 1e-9)), 0.5)   # hard cap
        self.assertLess(ro.position(0.2, 0.02), 0.0)         # short side
        self.assertLess(ro.position(-0.03, 0.02), 0.0)       # return-mode sig

    def test_forecast_sigma_fallback_and_garch(self):
        from trading.risk_overlay import forecast_sigma
        rng = np.random.default_rng(3)
        short = 0.01 * rng.standard_normal(30)               # EWMA path
        s1 = forecast_sigma(short)
        self.assertTrue(np.isfinite(s1) and s1 > 0)
        long = 0.01 * rng.standard_normal(400)               # GARCH path
        s2 = forecast_sigma(long)
        self.assertTrue(np.isfinite(s2) and s2 > 0)
        self.assertLess(abs(s2 - 0.01), 0.01)                # sane magnitude


class TestRollout(unittest.TestCase):
    def test_autoregressive_length_and_feedback(self):
        from trading.rollout import autoregressive_rollout
        seen = []

        def model(w):                                        # echo last + 1
            seen.append(w.copy())
            return w[-1] + 1.0

        out = autoregressive_rollout(model, np.arange(5, dtype=float), k=4)
        np.testing.assert_allclose(out, [5.0, 6.0, 7.0, 8.0])
        # feedback: the second call's window must contain the first prediction
        self.assertEqual(seen[1][-1], 5.0)

    def test_direct_multi_horizon_head(self):
        from trading.rollout import autoregressive_rollout
        out = autoregressive_rollout(lambda w: np.array([1., 2., 3., 4., 5.]),
                                     np.zeros(8), k=3)
        np.testing.assert_allclose(out, [1.0, 2.0, 3.0])     # direct (H,) head

    def test_per_horizon_errors_shape(self):
        from trading.rollout import per_horizon_errors
        T = np.zeros((6, 4))
        P = np.ones((6, 4)) * np.array([1, 2, 3, 4])
        e = per_horizon_errors(T, P)
        self.assertEqual(e["mae"].shape, (4,))
        self.assertEqual(e["rmse"].shape, (4,))
        np.testing.assert_allclose(e["mae"], [1, 2, 3, 4])   # compounding

    def test_compare_to_floors_persistence(self):
        from trading.rollout import compare_to_floors
        windows = [np.linspace(0, 1, 10), np.linspace(1, 2, 10)]
        truth = np.stack([w[-1] + 0.1 * np.arange(1, 4) for w in windows])
        res = compare_to_floors(lambda w: w[-1] + 0.1, windows, truth, k=3)
        self.assertIn("model", res)
        self.assertIn("persistence", res)
        self.assertTrue(res["beats_persistence"])            # model > naive


class TestFeaturesTA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pandas as pd
        rng = np.random.default_rng(4)
        n = 260
        c = pd.Series(100 + np.cumsum(rng.normal(0, 1, n)))
        cls.df = pd.DataFrame({
            "open": c.shift(1).fillna(c.iloc[0]),
            "high": c + np.abs(rng.normal(0, .5, n)),
            "low": c - np.abs(rng.normal(0, .5, n)),
            "close": c, "volume": 1000.0})

    def test_indicators_and_warmup_gate(self):
        from trading.features_ta import (INDICATOR_COLS, add_indicators,
                                         gate_warmup)
        out = add_indicators(self.df, ema_lens=(20, 50, 100))
        for col in INDICATOR_COLS:
            self.assertIn(col, out.columns)
        self.assertTrue(out["ema_slow"].head(50).isna().all())   # warm-up NaN
        gated = gate_warmup(out)
        self.assertFalse(gated[INDICATOR_COLS].isna().any().any())
        self.assertLess(len(gated), len(out))                # rows were gated

    def test_fractals_monotonic(self):
        import pandas as pd
        from trading.features_ta import fractal_levels, resistance, support
        # hand-built V-shape low at index 3 and peak high at index 3
        lows = [5, 4, 3, 2, 3, 4, 5]
        highs = [5, 6, 7, 8, 7, 6, 5]
        df = pd.DataFrame({"open": lows, "high": highs, "low": lows,
                           "close": lows})
        self.assertEqual(support(df, 3, 2, 2), 1)
        self.assertEqual(support(df, 2, 2, 2), 0)            # not the trough
        self.assertEqual(resistance(df, 3, 2, 2), 1)
        lv = fractal_levels(df, 2, 2)
        self.assertEqual(lv["support"][0], (3, 2.0))
        self.assertEqual(lv["resistance"][0], (3, 8.0))

    def test_proximity_signal_and_admission_gate(self):
        from trading.features_ta import admission_gate, proximity_signal
        sig = proximity_signal(self.df)
        self.assertEqual(len(sig), len(self.df))
        self.assertTrue(set(np.unique(sig)) <= {0, 1, 2})
        verdict = admission_gate(self.df, sig)
        self.assertIn(verdict["status"], {"pending", "ok", "error"})
        self.assertIn("admitted", verdict)


if __name__ == "__main__":
    unittest.main()
