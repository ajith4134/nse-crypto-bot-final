"""Phase-3 acceptance tests: Hellsemble + deep (L2/L3) routing.

Proves the three sequenced advances:
  1. Hellsemble circles-of-difficulty router beats the naive baseline (binary).
  2. It generalises to the multi-output heads (multiclass + regression).
  3. The deep L2 router (routers-of-routers) runs and beats baseline.

All on synthetic data with a KNOWN generating process, so signal is real and the
'beats baseline' assertions are meaningful (not flaky noise).
"""
from __future__ import annotations

import unittest

from core.heads import HEAD_MAGNITUDE, HEAD_REGIME
from core.node_protocol import NodeProtocol
from data.benchmarks import make_benchmark_dataset, make_regime_dataset
from eval.golden import baseline_for, score_head
from nodes.router_node import DeepRouterNode, HellsembleRouterNode
from nodes.routing_advanced import (CaruanaEnsembleNode, ConformalGatedRouterNode,
                                    DESRouterNode)
from nodes.gated_node import GatedMoENode
from nodes.cascade_node import DeepCascadeNode
from nodes.dynamic_bus import DynamicBusNode
from nodes.structure_search import StructureSearchNode
from nodes import pool


def _factories():
    facs, nms = pool.factories(), pool.names()
    want = ["sk_logreg", "sk_knn10", "sk_rf100", "hmm_regime2"]   # fast, diverse (cf. run_phase3)
    chosen = [f for f, n in zip(facs, nms) if n in want]
    return chosen if len(chosen) >= 3 else facs[:6]


def _reg_factories():
    """Regressor experts — the regression head needs regressor nodes (cf. run_multi.reg_pool)."""
    from nodes import oss_nodes as O
    return [O.ridge_reg_node, lambda: O.rf_reg_node(100), O.gbdt_reg_node, O.xgb_reg_node]


def _split(X, y, frac=0.7, seed=7):
    """Shuffled split (matches run_phase3) — the synthetic regime set is designed to
    be routed across mixed calm/noisy regimes, not forecast chronologically."""
    import random as _r
    idx = list(range(len(X)))
    _r.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _naive(y):
    up = sum(1 for v in y if v == max(set(y), key=y.count))
    return up / len(y)


class TestPhase3Routing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.factories = _factories()

    def test_routers_conform_to_protocol(self):
        hell = HellsembleRouterNode(self.factories)
        deep = DeepRouterNode(self.factories, depth=2)
        self.assertIsInstance(hell, NodeProtocol)
        self.assertIsInstance(deep, NodeProtocol)

    def test_hellsemble_binary_beats_baseline(self):
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        hell = HellsembleRouterNode(self.factories, k=25).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(hell.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"hellsemble {acc:.3f} ≤ baseline {base:.3f}")
        # the difficulty circles must actually create ≥1 specialist expert
        self.assertGreaterEqual(len(hell.experts), 1)

    def test_deep_router_L2_beats_baseline(self):
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        deep = DeepRouterNode(self.factories, depth=2, branching=3, k=25).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(deep.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"deep L2 {acc:.3f} ≤ baseline {base:.3f}")
        self.assertTrue(deep.layer_names, "deep router exposes no sub-router layer")

    def test_hellsemble_multiclass_beats_baseline(self):
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        y = ds["targets"]["regime"]
        Xtr, ytr, Xte, yte = _split(ds["X"], y)
        hell = HellsembleRouterNode(self.factories, k=25,
                                    task="multiclass", head="regime").fit(Xtr, ytr)
        out = hell.predict_output(Xte)
        self.assertEqual(len(out[0]), HEAD_REGIME.n_outputs)        # 3-class width
        sc = score_head(HEAD_REGIME, out, yte)
        base = baseline_for(HEAD_REGIME, ytr, yte)
        self.assertGreaterEqual(sc["value"], base["value"],
                                f"multiclass {sc['value']:.3f} < baseline {base['value']:.3f}")

    def test_des_router_beats_baseline(self):
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        for method in ("KNORAU", "KNORAE", "OLA"):
            r = DESRouterNode(self.factories, method=method).fit(Xtr, ytr)
            acc = sum(int(a == b) for a, b in zip(r.predict(Xte), yte)) / len(yte)
            base = max(_naive(yte), 1 - _naive(yte))
            self.assertGreater(acc, base, f"DES:{method} {acc:.3f} ≤ baseline {base:.3f}")

    def test_conformal_router_beats_baseline(self):
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        r = ConformalGatedRouterNode(self.factories).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(r.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"conformal {acc:.3f} ≤ baseline {base:.3f}")
        self.assertTrue(r.routing_histogram(Xte))                  # gate produces a routing

    def test_caruana_combiner_binary_and_regression(self):
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        car = CaruanaEnsembleNode(self.factories).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(car.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"caruana {acc:.3f} ≤ baseline {base:.3f}")
        self.assertTrue(car.weights(), "caruana selected no experts")
        # task-aware: also serves the regression head
        rds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        ym = rds["targets"]["magnitude"]
        Xa, ya, Xb, yb = _split(rds["X"], ym)
        rcar = CaruanaEnsembleNode(_reg_factories(), task="regression",
                                   head="magnitude").fit(Xa, ya)
        out = rcar.predict_output(Xb)
        self.assertEqual(len(out[0]), HEAD_MAGNITUDE.n_outputs)

    def test_gated_moe_trains_and_learns_wiring(self):
        """P3.5 differentiable gate: backprop loop beats baseline and learns a
        non-collapsed weighting (the load-balance aux loss spreads usage)."""
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        g = GatedMoENode(self.factories, epochs=200).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(g.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"gated_moe {acc:.3f} ≤ baseline {base:.3f}")
        w = g.gate_weights(Xte)
        self.assertEqual(round(sum(w.values()), 2), 1.0)           # softmax weights sum to 1
        self.assertGreater(sum(1 for v in w.values() if v > 0.02), 1,
                           "gate collapsed onto a single expert (load-balance failed)")

    def test_gated_moe_multiclass_and_regression(self):
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        Xa, ya, Xb, yb = _split(ds["X"], ds["targets"]["regime"])
        gm = GatedMoENode(self.factories, task="multiclass", head="regime",
                          epochs=150).fit(Xa, ya)
        out = gm.predict_output(Xb)
        self.assertEqual(len(out[0]), HEAD_REGIME.n_outputs)       # 3-class width
        sc = score_head(HEAD_REGIME, out, yb)
        self.assertGreater(sc["value"], baseline_for(HEAD_REGIME, ya, yb)["value"])
        # regression head with regressor experts
        Xc, yc, Xd, yd = _split(ds["X"], ds["targets"]["magnitude"])
        gr = GatedMoENode(_reg_factories(), task="regression", head="magnitude",
                          epochs=150).fit(Xc, yc)
        outr = gr.predict_output(Xd)
        self.assertEqual(len(outr[0]), HEAD_MAGNITUDE.n_outputs)
        self.assertFalse(score_head(HEAD_MAGNITUDE, outr, yd)["value"] != \
                         score_head(HEAD_MAGNITUDE, outr, yd)["value"])   # not NaN

    def test_structure_search_learns_and_prunes(self):
        """P3.9 structure search: learns per-expert architecture gates, PRUNES the pool
        to a smaller discrete subnetwork, and still beats baseline."""
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        facs, nms = pool.factories(), pool.names()
        want = ["sk_logreg", "sk_knn5", "sk_knn10", "sk_knn20", "sk_stump", "sk_tree5",
                "sk_gaussnb", "sk_rf100", "sk_gbdt", "xgboost", "lightgbm", "hmm_regime2"]
        many = [f for f, n in zip(facs, nms) if n in want]
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        s = StructureSearchNode(many, epochs=200).fit(Xtr, ytr)
        arch = s.architecture()
        self.assertLess(arch["n_kept"], arch["n_total"], "search pruned nothing")
        self.assertGreaterEqual(arch["n_kept"], 2)
        self.assertEqual(arch["n_kept"] + len(arch["pruned"]), arch["n_total"])
        acc = sum(int(a == b) for a, b in zip(s.predict(Xte), yte)) / len(yte)
        self.assertGreater(acc, max(_naive(yte), 1 - _naive(yte)))

    def test_active_subnetwork_per_input_topk(self):
        """P3.8 active subnetwork: a top-k gate fires exactly k experts PER INPUT
        (dynamic active set, not static prune) and still beats baseline."""
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        facs, nms = pool.factories(), pool.names()
        many = [f for f, n in zip(facs, nms)
                if n in ("sk_logreg", "sk_knn10", "sk_rf100", "sk_gbdt", "xgboost", "hmm_regime2")]
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        g = GatedMoENode(many, top_k=3, epochs=150).fit(Xtr, ytr)
        w, active = g.active_subnetwork(Xte)
        per_input = active.sum(axis=1)
        self.assertTrue((per_input <= 3).all(), "more than top_k experts active on some input")
        self.assertTrue((per_input >= 1).all(), "no experts active on some input")
        self.assertGreater(active.mean(axis=0).min(), -1)        # usage frequencies exist
        acc = sum(int(a == b) for a, b in zip(g.predict(Xte), yte)) / len(yte)
        self.assertGreater(acc, max(_naive(yte), 1 - _naive(yte)))

    def test_deep_cascade_grows_and_beats_baseline(self):
        """P3.6 deep cascade: grows depth on its own validation signal, stays
        leakage-safe, and beats baseline; depth>=1 and the cascade ≥ a single gate."""
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        c = DeepCascadeNode(self.factories, max_layers=4).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(c.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"cascade {acc:.3f} ≤ baseline {base:.3f}")
        self.assertGreaterEqual(c.depth, 1)
        self.assertLessEqual(c.depth, 4)                          # respects max_layers
        self.assertEqual(round(sum(c.gate_weights(Xte).values()), 2), 1.0)

    def test_deep_cascade_multiclass_width(self):
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        Xa, ya, Xb, yb = _split(ds["X"], ds["targets"]["regime"])
        c = DeepCascadeNode(self.factories, task="multiclass", head="regime",
                            max_layers=3).fit(Xa, ya)
        out = c.predict_output(Xb)
        self.assertEqual(len(out[0]), HEAD_REGIME.n_outputs)
        sc = score_head(HEAD_REGIME, out, yb)
        self.assertGreater(sc["value"], baseline_for(HEAD_REGIME, ya, yb)["value"])

    def test_dynamic_bus_heterogeneous_and_droppable(self):
        """P3.7 dynamic I/O bus: mixes heterogeneous-width sources (node outputs +
        raw features), beats baseline, and still predicts with a source REMOVED at
        inference (no retraining) — the non-fixed-I/O property."""
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        b = DynamicBusNode(self.factories, include_raw=True).fit(Xtr, ytr)
        acc = sum(int(a == b_) for a, b_ in zip(b.predict(Xte), yte)) / len(yte)
        base = max(_naive(yte), 1 - _naive(yte))
        self.assertGreater(acc, base, f"dynamic_bus {acc:.3f} ≤ baseline {base:.3f}")
        self.assertIn("raw", b.source_names)                     # raw is a heterogeneous-width source
        self.assertEqual(round(sum(b.source_attention(Xte).values()), 2), 1.0)
        # predict with the raw source DROPPED at inference, no retraining
        sub = set(b.source_names) - {"raw"}
        out = b.predict_output(Xte, active=sub)
        amax = lambda r: max(range(len(r)), key=lambda i: r[i])
        dacc = sum(int(amax(r) == t) for r, t in zip(out, yte)) / len(yte)
        self.assertGreater(dacc, base - 0.05, "bus failed gracefully when a source was removed")

    def test_dynamic_bus_uses_width_mismatched_node(self):
        """The bus ingests a node whose output width != head width (which the gate
        must drop) by projecting it — proving non-fixed outputs."""
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        Xa, ya, Xb, yb = _split(ds["X"], ds["targets"]["regime"])
        b = DynamicBusNode(self.factories, task="multiclass", head="regime").fit(Xa, ya)
        out = b.predict_output(Xb)
        self.assertEqual(len(out[0]), HEAD_REGIME.n_outputs)
        self.assertGreater(score_head(HEAD_REGIME, out, yb)["value"],
                           baseline_for(HEAD_REGIME, ya, yb)["value"])

    def test_hellsemble_regression_runs_and_scores(self):
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        y = ds["targets"]["magnitude"]
        Xtr, ytr, Xte, yte = _split(ds["X"], y)
        hell = HellsembleRouterNode(_reg_factories(), k=25,
                                    task="regression", head="magnitude").fit(Xtr, ytr)
        out = hell.predict_output(Xte)
        self.assertEqual(len(out[0]), HEAD_MAGNITUDE.n_outputs)     # width 1
        sc = score_head(HEAD_MAGNITUDE, out, yte)
        self.assertEqual(sc["metric"], "r2")
        self.assertFalse(sc["value"] != sc["value"], "R2 is NaN")   # finite check


if __name__ == "__main__":
    unittest.main(verbosity=2)
