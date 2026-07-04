"""CORTEX B3 acceptance tests — reflex arc + hierarchical gates + trust.

Mirrors tests/test_cortex_b1.py style: unittest, synthetic data with a KNOWN
generating process, tiny epochs, ZERO live state touched (MLNB_TRUST_PATH is
monkeypatched to a tmpdir before any TrustLedger is built).

  T  core/trust.py — AdaHedge/EXP3 multiplicative-weights trust moves toward
     low-loss nodes; bias_vector ordering + beta scaling; the vendored BOCD
     resets trust on an obvious changepoint stream; JSON persistence roundtrips.
  G  nodes/gated_node.py — prior_bias shifts gate weights toward the trusted
     expert while prior_bias=None stays byte-identical (regression guard);
     the vendored KANLinear gate path trains.
  H  nodes/active_subnet.py — HierarchicalGateNode beats naive baseline, active
     masks vary per input, firing_records match the SigmaNetwork contract,
     graph_snapshot exposes real weights, Leiden→networkx fallback works.
  R  nodes/reflex.py — easy inputs exit at tier-1, hard (XOR) inputs escalate,
     pure noise stays flat, compute_log + per-tier anytime predictions present.
"""
from __future__ import annotations

import os
import random
import tempfile
import unittest

import numpy as np

# isolate trust persistence BEFORE importing/constructing anything trust-shaped
_TMP = tempfile.TemporaryDirectory(prefix="mlnb_trust_test_")
os.environ["MLNB_TRUST_PATH"] = os.path.join(_TMP.name, "node_trust.json")

from core.trust import TrustLedger                                   # noqa: E402
from data.benchmarks import make_regime_dataset                      # noqa: E402
from nodes import pool                                               # noqa: E402
from nodes.active_subnet import (HierarchicalGateNode,               # noqa: E402
                                 _nx_communities, detect_communities)
from nodes.gated_node import gate_train, gate_weights                # noqa: E402
from nodes.reflex import FLAT, ReflexArc, ltt_threshold              # noqa: E402

_KAN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "vendor", "efficient_kan", "kan.py")


def _pool(want):
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in want]
    return [f for f, _ in chosen], [n for _, n in chosen]


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _naive(y):
    top = max(set(y), key=list(y).count)
    up = sum(1 for v in y if v == top) / len(y)
    return max(up, 1 - up)


def _fresh_path(name):
    path = os.path.join(_TMP.name, name)
    if os.path.exists(path):
        os.remove(path)
    return path


# ── T. trust ledger ──────────────────────────────────────────────────────────

class TestTrustLedger(unittest.TestCase):
    def test_multiplicative_weights_move_toward_low_loss(self):
        led = TrustLedger(path=_fresh_path("t_mw.json"))
        for _ in range(20):
            led.update("good", 0.0)
            led.update("bad", 1.0)
        self.assertGreater(led.trust("good"), led.trust("bad"))
        snap = led.snapshot()
        self.assertEqual(set(snap), {"good", "bad"})
        self.assertAlmostEqual(sum(snap.values()), 1.0, places=4)
        for v in snap.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_exp3_importance_weighting_variant(self):
        led = TrustLedger(path=_fresh_path("t_exp3.json"), exp3=True)
        for _ in range(15):
            led.update("routed_bad", 1.0)     # only the routed node's loss observed
            led.update("routed_good", 0.05)
        self.assertGreater(led.trust("routed_good"), led.trust("routed_bad"))

    def test_bias_vector_ordering_and_beta_scaling(self):
        led = TrustLedger(path=_fresh_path("t_bias.json"))
        for _ in range(10):
            led.update("good", 0.0)
            led.update("bad", 1.0)
        b1 = led.bias_vector(["bad", "good"], beta=1.0)
        self.assertIsInstance(b1, np.ndarray)
        self.assertEqual(b1.shape, (2,))
        self.assertGreater(b1[1], b1[0])                    # trusted expert gets the higher logit
        b2 = led.bias_vector(["bad", "good"], beta=2.0)
        np.testing.assert_allclose(b2, 2.0 * b1, rtol=1e-9)
        # an unseen node gets a finite (uniform-prior) bias — open to future nodes
        b3 = led.bias_vector(["brand_new_2027"])
        self.assertTrue(np.isfinite(b3).all())

    def test_bocd_reset_fires_on_obvious_changepoint(self):
        led = TrustLedger(path=_fresh_path("t_bocd.json"), reset_strength=0.9)
        for _ in range(20):
            led.update("good", 0.0)
            led.update("bad", 1.0)
        gap_before = led.trust("good") - led.trust("bad")
        fired = []
        for x in [0.0] * 30 + [8.0] * 10:                  # mean 0 → mean 8: obvious break
            out = led.observe_regime_signal(x)
            fired.append(out["changepoint"])
        self.assertTrue(any(fired), "BOCD never fired on a mean-0→mean-8 jump")
        self.assertIsNotNone(led.last_changepoint)
        self.assertGreaterEqual(led.last_changepoint, 30)   # at/after the true break
        gap_after = led.trust("good") - led.trust("bad")
        self.assertLess(gap_after, gap_before)              # reset moved trust toward uniform
        self.assertGreater(led.trust("good"), led.trust("bad"))  # …but kept the ordering

    def test_persistence_roundtrip_at_env_path(self):
        path = _fresh_path("t_persist.json")
        led = TrustLedger(path=path)
        for _ in range(8):
            led.update("keeper", 0.1)
            led.update("loser", 0.9)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.startswith(_TMP.name))         # never the live brain_memory file
        led2 = TrustLedger(path=path)                       # fresh process would do the same
        self.assertAlmostEqual(led2.trust("keeper"), led.trust("keeper"), places=6)
        self.assertGreater(led2.trust("keeper"), led2.trust("loser"))

    def test_default_path_comes_from_env(self):
        led = TrustLedger()                                 # no explicit path
        self.assertEqual(led.path, os.environ["MLNB_TRUST_PATH"])


# ── G. gate prior_bias + KAN gate ────────────────────────────────────────────

def _gate_problem(seed=3, n=240, d=4):
    """Expert 0 is the oracle, expert 1 anti-oracle, expert 2 coin-flip."""
    rng = np.random.RandomState(seed)
    Xz = rng.randn(n, d)
    y = (Xz[:, 0] > 0).astype(int)
    meta = np.zeros((n, 3, 2))
    meta[np.arange(n), 0, y] = 1.0                          # oracle
    meta[np.arange(n), 1, 1 - y] = 1.0                      # anti-oracle
    meta[:, 2, :] = 0.5                                     # uninformative
    return Xz, meta, y


class TestGatePriorBias(unittest.TestCase):
    def test_prior_bias_none_is_deterministic_regression_guard(self):
        Xz, meta, y = _gate_problem()
        g1, n1 = gate_train(Xz, meta, y, True, 40, 0.05, 0.01, True, 0, 7)
        g2, n2 = gate_train(Xz, meta, y, True, 40, 0.05, 0.01, True, 0, 7,
                            prior_bias=None, use_kan=False)
        w1 = gate_weights(g1, n1, Xz, 0, 3)
        w2 = gate_weights(g2, n2, Xz, 0, 3, prior_bias=None)
        np.testing.assert_allclose(w1, w2, atol=1e-7)       # None == old positional path
        self.assertGreater(w1.mean(0)[0], w1.mean(0)[1])    # gate finds the oracle

    def test_trust_prior_bias_shifts_weights_toward_trusted_expert(self):
        Xz, meta, y = _gate_problem()
        led = TrustLedger(path=_fresh_path("g_bias.json"))
        for _ in range(12):
            led.update("e2", 0.0)                           # brain trusts the flat expert
            led.update("e0", 1.0)
            led.update("e1", 1.0)
        bias = led.bias_vector(["e0", "e1", "e2"], beta=1.0)
        self.assertGreater(bias[2], bias[0])
        gb, nb = gate_train(Xz, meta, y, True, 40, 0.05, 0.01, True, 0, 7,
                            prior_bias=bias)
        g0, n0 = gate_train(Xz, meta, y, True, 40, 0.05, 0.01, True, 0, 7)
        wb = gate_weights(gb, nb, Xz, 0, 3, prior_bias=bias).mean(0)
        w0 = gate_weights(g0, n0, Xz, 0, 3).mean(0)
        self.assertGreater(wb[2], w0[2])                    # trust pulled weight to expert 2

    @unittest.skipUnless(os.path.exists(_KAN), "vendor/efficient_kan missing")
    def test_kan_gate_path_trains(self):
        Xz, meta, y = _gate_problem()
        gate, noise = gate_train(Xz, meta, y, True, 30, 0.02, 0.01, False, 0, 7,
                                 use_kan=True)
        self.assertEqual(type(gate).__name__, "KANLinear")  # really the vendored layer
        w = gate_weights(gate, noise, Xz, 0, 3)
        self.assertEqual(w.shape, (len(Xz), 3))
        self.assertTrue(np.isfinite(w).all())
        np.testing.assert_allclose(w.sum(axis=1), 1.0, atol=1e-5)
        self.assertGreater(w.mean(0)[0], w.mean(0)[1])      # KAN gate also finds the oracle


# ── H. hierarchical active subnetwork ────────────────────────────────────────

H_WANT = ["sk_logreg", "sk_knn10", "sk_stump", "sk_tree5", "sk_gaussnb",
          "sk_rf100", "sk_gbdt"]


class TestHierarchicalGateNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        facs, _ = _pool(H_WANT)
        ds = make_regime_dataset(n=900, noise_hi=0.15, seed=7)
        cls.Xtr, cls.ytr, cls.Xte, cls.yte = _split(ds["X"], ds["y"])
        cls.node = HierarchicalGateNode(facs, top_k_communities=2, flat_top_k=3,
                                        epochs=100, folds=2, seed=7).fit(cls.Xtr, cls.ytr)

    def test_beats_naive_baseline(self):
        acc = sum(int(a == b) for a, b in zip(self.node.predict(self.Xte), self.yte)) \
            / len(self.yte)
        self.assertGreater(acc, _naive(self.yte), f"hgate {acc:.3f} ≤ baseline")
        self.assertGreaterEqual(len(self.node.community_keys), 1)

    def test_active_masks_vary_per_input(self):
        w, active = self.node.active_subnetwork(self.Xte)
        E = len(self.node.experts)
        self.assertEqual(active.shape, (len(self.Xte), E))
        distinct = {tuple(r) for r in active.astype(int).tolist()}
        if len(self.node.community_keys) > self.node.top_k_communities:
            self.assertGreater(len(distinct), 1, "routing is static, not per-input")
            self.assertLess(active.sum(1).mean(), E)        # top-k really sparsifies
        np.testing.assert_allclose(w.sum(axis=1), 1.0, atol=1e-4)

    def test_firing_records_match_contract(self):
        recs = self.node.firing_records(self.Xte, self.yte, n_samples=16)
        self.assertEqual(len(recs), 16)
        E = len(self.node.experts)
        for r in recs:
            self.assertEqual(set(r), {"i", "active", "weights", "community_path",
                                      "correct"})
            self.assertTrue(0 <= r["i"] < len(self.Xte))
            self.assertEqual(len(r["active"]), len(r["weights"]))
            for i in r["active"]:
                self.assertTrue(0 <= i < E)                 # GLOBAL expert indices
            for c in r["community_path"]:
                self.assertIn(c, self.node.community_keys)
            self.assertIsInstance(r["correct"], bool)

    def test_graph_snapshot_exposes_real_trained_weights(self):
        snap = self.node.graph_snapshot(self.Xte)
        self.assertEqual(set(snap), {"nodes", "edges", "communities", "active_subnet"})
        names = {n["name"] for n in snap["nodes"]}
        for nm in self.node.expert_names:
            self.assertIn(nm, names)
            self.assertIn(nm, snap["communities"])
        for e in snap["edges"]:
            self.assertIn(e["source"], names)
            self.assertIn(e["target"], names)
            self.assertTrue(np.isfinite(e["weight"]))
        self.assertEqual(snap["active_subnet"]["n_experts"], len(self.node.experts))

    def test_leiden_fallback_path_on_import_error(self):
        import nodes.active_subnet as A
        coact = np.zeros((6, 6))
        coact[:3, :3] = 0.9                                  # two obvious blocks
        coact[3:, 3:] = 0.9
        real = A._igraph_communities

        def _boom(_):
            raise ImportError("igraph forced away")
        A._igraph_communities = _boom
        try:
            comm = detect_communities(coact)
        finally:
            A._igraph_communities = real
        self.assertEqual(len(comm), 6)
        self.assertEqual(len({comm[0], comm[1], comm[2]}), 1)
        self.assertEqual(len({comm[3], comm[4], comm[5]}), 1)
        self.assertNotEqual(comm[0], comm[3])                # blocks split by networkx too
        self.assertEqual(comm, _nx_communities(coact))       # fallback really was networkx

    def test_trust_ledger_biases_fit_without_breaking_it(self):
        facs, _ = _pool(["sk_logreg", "sk_stump", "sk_tree5"])
        led = TrustLedger(path=_fresh_path("h_trust.json"))
        for _ in range(6):
            led.update("sk_tree5", 0.0)
        node = HierarchicalGateNode(facs, epochs=60, folds=2, trust=led,
                                    trust_beta=1.0).fit(self.Xtr[:400], self.ytr[:400])
        out = np.asarray(node.predict_output(self.Xte[:50]))
        self.assertEqual(out.shape, (50, 2))
        np.testing.assert_allclose(out.sum(axis=1), 1.0, atol=1e-6)


# ── R. reflex arc ────────────────────────────────────────────────────────────

def _easy_data(n=400, seed=5):
    """Linearly separable with a clean margin — tier-1 experts all agree."""
    rng = np.random.RandomState(seed)
    x0 = np.concatenate([rng.uniform(-2.0, -0.5, n // 2), rng.uniform(0.5, 2.0, n - n // 2)])
    rng.shuffle(x0)
    X = np.stack([x0, 0.1 * rng.randn(n)], axis=1)
    y = (x0 > 0).astype(int)
    return X.tolist(), y.tolist()


def _xor_data(n=400, seed=5):
    """XOR — linear tier-1 experts disagree/fail, trees solve it at tier-2."""
    rng = np.random.RandomState(seed)
    X = rng.uniform(-1.0, 1.0, size=(n, 2))
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(int)
    return X.tolist(), y.tolist()


def _noise_data(n=400, seed=5):
    rng = np.random.RandomState(seed)
    return rng.randn(n, 3).tolist(), rng.randint(0, 2, n).tolist()


class TestReflexArc(unittest.TestCase):
    T1 = ["sk_logreg", "sk_stump", "sk_gaussnb"]
    T2 = ["sk_rf100", "sk_gbdt", "sk_tree5"]

    def _arc(self, **kw):
        t1, _ = _pool(self.T1)
        t2, _ = _pool(self.T2)
        args = dict(escalate_margin=0.7, patience=1, capacity=0.5, alpha=0.15,
                    epochs=60, folds=2, seed=7)
        args.update(kw)
        return ReflexArc([t1, t2], **args)

    def test_easy_inputs_exit_at_tier_one(self):
        X, y = _easy_data()
        Xtr, ytr, Xte, yte = _split(X, y)
        arc = self._arc().fit(Xtr, ytr)
        preds = arc.predict(Xte)
        tiers = [rec["tier"] for rec in arc.compute_log]
        self.assertGreaterEqual(tiers.count(0) / len(tiers), 0.6,
                                "easy inputs did not exit at tier-1")
        decided = [(p, t) for p, t in zip(preds, yte) if p is not FLAT]
        self.assertGreater(len(decided), 0)
        acc = sum(int(p == t) for p, t in decided) / len(decided)
        self.assertGreater(acc, 0.85)

    def test_hard_inputs_escalate_to_deep_tier(self):
        X, y = _xor_data()
        Xtr, ytr, Xte, yte = _split(X, y)
        arc = self._arc().fit(Xtr, ytr)
        preds = arc.predict(Xte)
        tiers = [rec["tier"] for rec in arc.compute_log]
        self.assertGreater(tiers.count(1), len(tiers) * 0.3,
                           "XOR inputs did not escalate past the linear tier")
        decided = [(p, t) for p, t in zip(preds, yte) if p is not FLAT]
        self.assertGreater(len(decided), 0)
        acc = sum(int(p == t) for p, t in decided) / len(decided)
        self.assertGreater(acc, 0.7)                        # trees solve XOR at tier-2

    def test_pure_noise_stays_flat(self):
        X, y = _noise_data()
        Xtr, ytr, Xte, _ = _split(X, y)
        arc = self._arc(alpha=0.1).fit(Xtr, ytr)
        preds = arc.predict(Xte)
        flat_share = sum(1 for p in preds if p is FLAT) / len(preds)
        self.assertGreater(flat_share, 0.5, "noise should mostly abstain (CANON-49)")
        flats = [r for r in arc.compute_log if r["exit"] == "stay_flat"]
        self.assertGreater(len(flats), 0)

    def test_compute_log_and_anytime_predictions(self):
        X, y = _easy_data(n=300, seed=9)
        Xtr, ytr, Xte, _ = _split(X, y)
        arc = self._arc().fit(Xtr, ytr)
        by_tier = arc.predictions_by_tier(Xte)
        self.assertEqual(len(by_tier), 2)                   # one anytime head per tier
        self.assertEqual(len(by_tier[0]), len(Xte))
        self.assertTrue(all(p in (0, 1) for p in by_tier[0]))   # tier-1 always votes
        self.assertTrue(all(p in (0, 1) for p in by_tier[1]))   # carry-forward fills exits
        self.assertEqual(len(arc.compute_log), len(Xte))
        for rec in arc.compute_log:
            self.assertIsNotNone(rec)
            for key in ("i", "tier", "experts", "confidence", "agreement", "exit",
                        "prediction"):
                self.assertIn(key, rec)
            self.assertGreater(len(rec["experts"]), 0)      # who actually fired
            self.assertIn(rec["tier"], (0, 1))

    def test_ltt_threshold_semantics(self):
        # accurate tier → finite permissive λ; garbage tier → +inf (never exits)
        conf = np.linspace(0.5, 1.0, 100)
        good = ltt_threshold(conf, np.ones(100), alpha=0.1)
        self.assertLessEqual(good, 0.51)
        rng = np.random.RandomState(0)
        bad = ltt_threshold(conf, (rng.rand(100) < 0.5).astype(float), alpha=0.05,
                            min_support=10)
        self.assertEqual(bad, float("inf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
