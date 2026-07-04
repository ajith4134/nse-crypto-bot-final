"""CORTEX B4 acceptance tests — brain hub meta-controller.

Covers the vendored DFA broadcaster, jumpmodels regime wrapper (+ fallback),
drift sentries, the champion-challenger manager, and the composed BrainHub.step.
Trust persistence is isolated to a temp dir BEFORE importing anything trust-shaped.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np

_TMP = tempfile.mkdtemp(prefix="cortex_b4_")
os.environ["MLNB_TRUST_PATH"] = os.path.join(_TMP, "trust.json")

from trading.brain import regime_hub as RH                          # noqa: E402
from trading.brain.regime_hub import (BrainHub, ChampionManager,    # noqa: E402
                                       DriftSentry, JumpRegime)
from vendor.dfa import DFABroadcaster                               # noqa: E402


def _trust_path(name: str) -> str:
    return os.path.join(_TMP, f"{name}.json")


class TestDFABroadcaster(unittest.TestCase):
    def test_fixed_matrix_and_shapes(self):
        b = DFABroadcaster(error_dim=1, seed=1)
        b.register("g1", 4)
        b.register("g2", 3)
        out = b.broadcast(0.5)
        self.assertEqual(out["g1"].shape, (4,))
        self.assertEqual(out["g2"].shape, (3,))

    def test_matrices_are_frozen(self):
        b = DFABroadcaster(seed=1)
        B1 = b.register("g", 5).copy()
        b.broadcast(1.0)
        b.broadcast(-2.0)
        np.testing.assert_array_equal(B1, b._B["g"])   # never updated

    def test_deterministic_by_seed(self):
        a = DFABroadcaster(seed=7); a.register("x", 6)
        c = DFABroadcaster(seed=7); c.register("x", 6)
        np.testing.assert_array_equal(a._B["x"], c._B["x"])

    def test_error_width_validated(self):
        b = DFABroadcaster(error_dim=2, seed=0); b.register("x", 3)
        with self.assertRaises(ValueError):
            b.broadcast(1.0)                            # scalar != error_dim 2

    def test_sign_only_drtp(self):
        b = DFABroadcaster(seed=3, sign_only=True); b.register("x", 8)
        self.assertTrue(np.all(np.abs(b._B["x"]) == 1.0))

    def test_linear_in_error(self):
        b = DFABroadcaster(seed=2); b.register("x", 4)
        d1 = b.broadcast(1.0)["x"]
        d2 = b.broadcast(2.0)["x"]
        np.testing.assert_allclose(d2, 2.0 * d1)


class TestJumpRegime(unittest.TestCase):
    def test_proba_normalised_and_labeled(self):
        rng = np.random.default_rng(0)
        feats = np.vstack([rng.normal(-1, 0.2, (60, 3)),
                           rng.normal(1, 0.2, (60, 3))])
        jr = JumpRegime(n_regimes=2, seed=0).fit(feats)
        p = jr.proba_online(feats[-1])
        self.assertAlmostEqual(float(p.sum()), 1.0, places=5)
        self.assertEqual(len(p), 2)

    def test_flap_free_labels_stable(self):
        # a persistent regime should not flap every bar
        rng = np.random.default_rng(1)
        feats = rng.normal(2.0, 0.1, (80, 3))
        jr = JumpRegime(n_regimes=3, jump_penalty=50.0, seed=0).fit(feats)
        labels = [jr.label(jr.proba_online(feats[i])) for i in range(60, 80)]
        # at most a couple of distinct labels across a stable window
        self.assertLessEqual(len(set(labels)), 2)

    def test_fallback_when_jumpmodels_absent(self):
        orig = RH._HAS_JUMP
        try:
            RH._HAS_JUMP = False
            feats = np.random.default_rng(0).standard_normal((40, 2))
            jr = JumpRegime(n_regimes=3, seed=0).fit(feats)
            p = jr.proba_online(feats[-1])
            self.assertAlmostEqual(float(p.sum()), 1.0, places=5)
            self.assertTrue(jr._fitted and jr._model is None)
        finally:
            RH._HAS_JUMP = orig

    def test_too_few_rows_stays_uniform(self):
        jr = JumpRegime(n_regimes=3, seed=0).fit(np.zeros((2, 3)))
        self.assertFalse(jr._fitted)
        np.testing.assert_allclose(jr._last_proba, np.full(3, 1 / 3))


class TestDriftSentry(unittest.TestCase):
    def test_detects_loss_shift(self):
        s = DriftSentry()
        fired = False
        for _ in range(80):
            fired |= s.update_node("n", 0.05)          # stable low loss
        for _ in range(80):
            fired |= s.update_node("n", 0.95)          # abrupt shift up
        self.assertTrue(fired)

    def test_stable_stream_no_false_drift(self):
        s = DriftSentry()
        fired = any(s.update_node("n", 0.5) for _ in range(120))
        self.assertFalse(fired)

    def test_input_drift_runs(self):
        s = DriftSentry()
        out = s.update_input(np.array([0.1, 0.2, 0.3]))
        self.assertIn(out, (True, False))              # returns a bool either backend


class TestChampionManager(unittest.TestCase):
    def test_picks_k_lowest_loss(self):
        cm = ChampionManager(["a", "b", "c", "d"], k=2, window=16)
        for _ in range(10):
            cm.observe("a", 0.1); cm.observe("b", 0.9)
            cm.observe("c", 0.2); cm.observe("d", 0.8)
        champs = cm.champions("bull")
        self.assertEqual(len(champs), 2)
        self.assertIn("a", champs)
        self.assertNotIn("b", champs)

    def test_per_regime_memory(self):
        cm = ChampionManager(["a", "b", "c"], k=1)
        cm.observe("a", 0.1); cm.observe("b", 0.5); cm.observe("c", 0.9)
        self.assertEqual(cm.champions("bull"), ["a"])
        self.assertIn("bull", cm._champions)


class TestBrainHub(unittest.TestCase):
    def _hub(self, name, **kw):
        return BrainHub(["tcn", "lstm", "tfm", "mlp"], trust_path=_trust_path(name), **kw)

    def test_step_shapes_and_trust_order(self):
        hub = self._hub("order", n_regimes=3, k_online=2, seed=0)
        feats = np.random.default_rng(0).standard_normal((120, 4))
        hub.fit_regime(feats)
        d = None
        for t in range(30):
            d = hub.step({"tcn": 0.1, "lstm": 0.9, "tfm": 0.4, "mlp": 0.6},
                         feature_row=feats[t], trade_error=0.3, perf_signal=0.5)
        self.assertAlmostEqual(float(d.regime_probs.sum()), 1.0, places=5)
        self.assertGreater(d.trust["tcn"], d.trust["lstm"])         # lower loss = more trust
        self.assertEqual(len(d.champions), 2)
        self.assertIn("tcn", d.champions)
        self.assertEqual(set(d.dfa_deltas), {"tcn", "lstm", "tfm", "mlp"})

    def test_trust_bias_matches_ledger(self):
        hub = self._hub("bias", seed=1)
        hub.step({"tcn": 0.2, "lstm": 0.7, "tfm": 0.5, "mlp": 0.5})
        d = hub.step({"tcn": 0.2, "lstm": 0.7, "tfm": 0.5, "mlp": 0.5})
        # more-trusted node has a higher (less negative) gate prior logit
        self.assertGreater(d.trust_bias["tcn"], d.trust_bias["lstm"])

    def test_dfa_absent_when_no_trade_error(self):
        hub = self._hub("nodfa")
        d = hub.step({"tcn": 0.3, "lstm": 0.3, "tfm": 0.3, "mlp": 0.3})
        self.assertEqual(d.dfa_deltas, {})

    def test_new_node_absorbed(self):
        hub = self._hub("newnode")
        d = hub.step({"tcn": 0.2, "surprise": 0.4}, trade_error=0.1)
        self.assertIn("surprise", d.trust)
        self.assertIn("surprise", d.dfa_deltas)

    def test_status_reports_backends(self):
        hub = self._hub("status")
        b = hub.status()["backends"]
        self.assertEqual(set(b), {"jumpmodels", "river", "frouros"})
        for v in b.values():
            self.assertIsInstance(v, bool)

    def test_bocd_reset_runs_on_perf_stream(self):
        hub = self._hub("bocd", seed=2)
        # feed a performance stream with an abrupt level change; must not crash and
        # must keep trust a valid distribution
        for t in range(20):
            hub.step({"tcn": 0.3, "lstm": 0.5}, perf_signal=(0.0 if t < 10 else 5.0))
        snap = hub.trust.snapshot()
        self.assertTrue(all(0.0 <= v <= 1.0 for v in snap.values()))


if __name__ == "__main__":
    unittest.main()
