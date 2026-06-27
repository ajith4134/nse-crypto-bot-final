"""Acceptance test: the PhD-domain node modules import and conform to NodeProtocol.

Covers the expanded node families (physics/chaos/signal/quant/math/ml/control).
Uses only FAST representative nodes (the slow ones — STUMPY/EVT/GaussianProcess —
are deliberately off the hot path) so the gate stays quick. Verifies protocol
conformance + correct multi-output width on a small benchmark.
"""
from __future__ import annotations

import unittest

from core.node_protocol import NodeProtocol
from data.benchmarks import make_benchmark_dataset
from data.dataset import chrono_split


class TestDomainNodes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = make_benchmark_dataset("mackey_glass", 500, 0.05)
        cls.Xtr, cls.ytr, cls.Xte, cls.yte = chrono_split(d["X"], d["targets"]["direction"], 0.7)

    def _check(self, factory):
        nd = factory()
        nd.task = "binary"
        nd.fit(self.Xtr, self.ytr)
        out = nd.predict_output(self.Xte)
        self.assertIsInstance(nd, NodeProtocol)
        self.assertEqual(len(out[0]), 2)                 # binary -> [p0, p1]
        self.assertEqual(len(out), len(self.Xte))

    def test_modules_import(self):
        import nodes.dynamics_nodes, nodes.frontier_nodes, nodes.ml_nodes  # noqa
        import nodes.probabilistic_nodes, nodes.quant_nodes, nodes.signal_nodes  # noqa
        import nodes.spectral_nodes, nodes.structure_nodes  # noqa

    def test_fast_nodes_conform(self):
        from nodes import dynamics_nodes as D
        from nodes import frontier_nodes as F
        from nodes import ml_nodes as M
        from nodes import probabilistic_nodes as P
        from nodes import quant_nodes as Q
        from nodes import signal_nodes as S
        from nodes import spectral_nodes as SP
        from nodes import structure_nodes as ST
        for f in (D.permentropy_node, D.sindy_node, S.rmt_signal_node,
                  M.catch22_node, Q.ewma_vol_node, Q.garch_vol_node,
                  SP.lombscargle_node, SP.regime_node, ST.optimal_transport_node,
                  P.gplearn_symbolic_node, F.rl_policy_node):
            with self.subTest(node=f.__name__):
                self._check(f)


if __name__ == "__main__":
    unittest.main()
