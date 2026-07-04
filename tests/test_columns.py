"""Column-architecture acceptance tests (A → B → C → D + dynamic brain I/O).

Proves the connected column network the user asked for, on synthetic data with a KNOWN
generating process so 'beats baseline' is meaningful (matches tests/test_phase3.py style):

  A  ColumnNode ensembles same-type members and beats baseline.
  B  ColumnNetworkNode's cross-column gate beats baseline; learned column weights are a
     non-collapsed simplex; the dashboard layout lists the real columns.
  C  grow=True grows depth (cascade over columns) and beats baseline; pruning is reported.
  D  brain-context gate input trains and predicts (brain drives routing).
  +  open-to-future: a brand-new node name auto-lands in a column with no code change.
  +  dynamic OUTPUT: ColumnNetwork computes ONLY the heads the brain requests.
"""
from __future__ import annotations

import os
import unittest

from core.columns import column_for, group_factories
from core.heads import HEAD_MAGNITUDE, HEAD_REGIME
from core.node_protocol import NodeProtocol
from data.benchmarks import make_benchmark_dataset, make_regime_dataset
from eval.golden import baseline_for, score_head
from nodes import pool
from nodes.column_node import ColumnNode
from nodes.column_network import ColumnNetwork, ColumnNetworkNode


def _pool(want):
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in want]
    return [f for f, _ in chosen], [n for _, n in chosen]


# a diverse pool spanning several columns (linear/neighbors/trees/boosting/regime)
WANT = ["sk_logreg", "sk_knn10", "sk_rf100", "xgboost", "hmm_regime2"]
REG_WANT_FACTORIES = None


def _reg_factories():
    from nodes import oss_nodes as O
    return [O.ridge_reg_node, lambda: O.rf_reg_node(100), O.gbdt_reg_node]


def _reg_names():
    return ["ridge_reg", "rf_reg", "gbdt_reg"]


def _split(X, y, frac=0.7, seed=7):
    import random as _r
    idx = list(range(len(X)))
    _r.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def _naive(y):
    top = max(set(y), key=y.count)
    up = sum(1 for v in y if v == top) / len(y)
    return max(up, 1 - up)


class TestColumnTaxonomy(unittest.TestCase):
    def test_nodes_route_to_expected_columns(self):
        self.assertEqual(column_for("sk_logreg"), "linear")
        self.assertEqual(column_for("sk_knn10"), "neighbors")
        self.assertEqual(column_for("sk_rf100"), "trees")
        self.assertEqual(column_for("xgboost"), "boosting")
        self.assertEqual(column_for("hmm_regime2"), "regime")
        self.assertEqual(column_for("esn150"), "reservoir")

    def test_unknown_node_lands_in_other(self):
        """Open-to-future: a brand-new node with no rule still gets a column."""
        self.assertEqual(column_for("totally_new_experimental_2027"), "other")

    def test_grouping_preserves_column_order_and_drops_empties(self):
        facs, nms = _pool(WANT)
        grouped = group_factories(facs, nms)
        # order follows the COLUMNS stack (boosting first, linear last), empties dropped
        self.assertEqual(list(grouped), ["boosting", "regime", "neighbors", "trees", "linear"])
        self.assertTrue(all(len(v) >= 1 for v in grouped.values()))


class TestColumnA(unittest.TestCase):
    def test_column_node_beats_baseline(self):
        # a real multi-member 'trees' column (random-forest + gradient-boost, same family)
        tfacs, tnms = _pool(["sk_rf100", "sk_gbdt", "sk_tree5"])
        ds = make_regime_dataset(n=1100, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        col = ColumnNode("trees", tfacs, epochs=120).fit(Xtr, ytr)
        self.assertIsInstance(col, NodeProtocol)
        acc = sum(int(a == b) for a, b in zip(col.predict(Xte), yte)) / len(yte)
        self.assertGreater(acc, _naive(yte))
        self.assertGreaterEqual(len(col.members), 2)          # ≥2 surviving members ensembled


class TestColumnNetworkB(unittest.TestCase):
    def test_cross_column_gate_beats_baseline_and_is_balanced(self):
        facs, nms = _pool(WANT)
        ds = make_regime_dataset(n=1200, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        net = ColumnNetworkNode(facs, nms, epochs=120, folds=2, intra_folds=2).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(net.predict(Xte), yte)) / len(yte)
        self.assertGreater(acc, _naive(yte), f"colnet {acc:.3f} ≤ baseline")
        w = net.column_weights(Xte)
        self.assertEqual(round(sum(w.values()), 2), 1.0)      # softmax simplex over columns
        self.assertGreater(sum(1 for v in w.values() if v > 0.02), 1,
                           "cross-gate collapsed onto one column (load-balance failed)")
        self.assertEqual({d["key"] for d in net.layout()},
                         {"linear", "neighbors", "trees", "boosting", "regime"})
        self.assertIsInstance(net.pruned_columns(Xte), list)
        self.assertTrue(net.column_intra_weights(Xte))        # nested A-weights for dashboard


class TestColumnNetworkC(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("MLNB_HEAVY"),
        "grow=True depth-cascade refits every column (incl. hmm_regime2) many times over "
        "1100 rows — a heavy stress test, not for the fast path. Set MLNB_HEAVY=1 to run.")
    def test_grow_depth_beats_baseline(self):
        facs, nms = _pool(WANT)
        ds = make_regime_dataset(n=1100, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        net = ColumnNetworkNode(facs, nms, grow=True, max_layers=3, epochs=100,
                                folds=2, intra_folds=2).fit(Xtr, ytr)
        acc = sum(int(a == b) for a, b in zip(net.predict(Xte), yte)) / len(yte)
        self.assertGreater(acc, _naive(yte), f"grown colnet {acc:.3f} ≤ baseline")
        self.assertGreaterEqual(net.depth, 1)
        self.assertLessEqual(net.depth, 3)
        self.assertIsInstance(net.pruned_columns(Xte), list)


class TestColumnNetworkD(unittest.TestCase):
    def test_brain_context_gate_trains_and_predicts(self):
        """Option D: brain context appended to the CROSS-GATE input only; still learns."""
        facs, nms = _pool(WANT)
        ds = make_regime_dataset(n=1100, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        # a 1-column brain context = a crude regime score (mean of raw feats) per row
        ctx_tr = [[sum(r) / len(r)] for r in Xtr]
        ctx_te = [[sum(r) / len(r)] for r in Xte]
        net = ColumnNetworkNode(facs, nms, brain_ctx_dim=1, epochs=120,
                                folds=2, intra_folds=2).fit(Xtr, ytr, brain_ctx=ctx_tr)
        out = net.predict_output(Xte, brain_ctx=ctx_te)
        amax = lambda r: max(range(len(r)), key=lambda i: r[i])
        acc = sum(int(amax(r) == t) for r, t in zip(out, yte)) / len(yte)
        self.assertGreater(acc, _naive(yte), f"brain-gated colnet {acc:.3f} ≤ baseline")


class TestDynamicBrainOutputs(unittest.TestCase):
    def test_brain_requests_subset_of_heads(self):
        """The brain-driven dynamic OUTPUT layer: request a subset → only those heads computed."""
        ds = make_benchmark_dataset("mackey_glass", n=1200, noise=0.02)
        facs, nms = _pool(WANT)
        rfacs, rnms = _reg_factories(), _reg_names()
        Xa, ya, Xb, yb = _split(ds["X"], ds["targets"]["regime"])
        _, ma, _, mb = _split(ds["X"], ds["targets"]["magnitude"])

        net = ColumnNetwork(heads={})
        net.add_net("regime", ColumnNetworkNode(facs, nms, task="multiclass", head="regime",
                                                epochs=100, folds=2, intra_folds=2))
        net.add_net("magnitude", ColumnNetworkNode(rfacs, rnms, task="regression",
                                                   head="magnitude", epochs=100, folds=2,
                                                   intra_folds=2))
        net.nets["regime"].fit(Xa, ya)
        net.nets["magnitude"].fit(Xa, ma)

        self.assertEqual(set(net.trained_heads()), {"regime", "magnitude"})
        # brain asks for ONLY regime → only that head is computed/returned
        got = net.predict(Xb, request=["regime"])
        self.assertEqual(set(got), {"regime"})
        self.assertEqual(len(got["regime"][0]), HEAD_REGIME.n_outputs)
        self.assertGreater(score_head(HEAD_REGIME, got["regime"], yb)["value"],
                           baseline_for(HEAD_REGIME, ya, yb)["value"])
        # brain asks for both → both computed, correct widths
        both = net.predict(Xb)
        self.assertEqual(set(both), {"regime", "magnitude"})
        self.assertEqual(len(both["magnitude"][0]), HEAD_MAGNITUDE.n_outputs)
        # requesting an untrained head type is rejected (out-of-scope by design)
        with self.assertRaises(KeyError):
            net.predict(Xb, request=["sentiment"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
