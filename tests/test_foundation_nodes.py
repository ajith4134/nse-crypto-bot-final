"""Tier-1 foundation / SOTA model nodes (nodes/foundation_nodes.py, groups A–F).

Each test builds a small synthetic series + feature matrix and asserts the node
satisfies the NodeProtocol contract (fit → predict_proba/predict_output/predict,
finite, correct length). Heavy nodes are skipped cleanly if their OSS dep is absent,
so this suite stays green whether or not the foundation stack is installed.
"""
from __future__ import annotations

import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _synth(n=180, seed=0):
    rng = np.random.default_rng(seed)
    ys = np.cumsum(rng.standard_normal(n)) * 0.5 + np.sin(np.arange(n) * 0.1)
    X = [[float(ys[i]),
          float(np.mean(ys[max(0, i - 5):i + 1])),
          float(np.std(ys[max(0, i - 5):i + 1]) + 1e-6)] for i in range(n)]
    ret = np.diff(ys, append=ys[-1])
    yreg = list(ret)
    ybin = [1 if v > 0 else 0 for v in ret]
    cut = int(n * 0.85)
    return X[:cut], X[cut:], yreg[:cut], ybin[:cut]


def _panel(T=160, N=5, seed=1):
    rng = np.random.default_rng(seed)
    R = rng.standard_normal((T, N)) * 0.01
    close = 100 * np.cumprod(1 + np.vstack([np.zeros((1, N)), R]), axis=0)
    panel = {"returns": R.tolist(), "close": close.tolist(), "target": 0}
    X = [[float(close[i, 0]), float(R[i, 0]),
          float(np.mean(R[max(0, i - 5):i + 1, 0]))] for i in range(T)]
    ybin = [1 if v > 0 else 0 for v in R[:, 0]]
    cut = int(T * 0.85)
    return panel, X[:cut], X[cut:], ybin[:cut]


def _try_import():
    try:
        import nodes.foundation_nodes as F  # noqa
        import torch  # noqa
        return F
    except Exception:
        return None


class TestFoundationNodes(unittest.TestCase):
    def _assert_node(self, node, Xtr, Xte, y, task):
        node.task = task
        node.fit(Xtr, y)
        proba = node.predict_proba(Xte)
        out = node.predict_output(Xte)
        lab = node.predict(Xte)
        self.assertEqual(len(proba), len(Xte))
        self.assertEqual(len(out), len(Xte))
        self.assertEqual(len(lab), len(Xte))
        self.assertTrue(all(np.isfinite(v) for v in proba), f"{node.name} non-finite proba")
        self.assertTrue(all(0.0 <= v <= 1.0 for v in proba), f"{node.name} proba out of [0,1]")

    # -- group A/B/C series forecasters + uncertainty --------------------- #
    def test_chronos(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(F.ChronosNode(), Xtr, Xte, ybin, "binary")

    def test_timesfm(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        try:
            import timesfm  # noqa
        except Exception:
            self.skipTest("timesfm absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(F.TimesFMNode(), Xtr, Xte, ybin, "binary")

    def _vendored(self, factory, rel_check):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        import os
        vend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "vendor", rel_check)
        if not os.path.exists(vend):
            self.skipTest(f"vendored repo absent: {rel_check}")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(factory(F), Xtr, Xte, ybin, "binary")

    def test_tinytimemixer(self):
        self._vendored(lambda F: F.TinyTimeMixerNode(), "granite_tsfm")

    def test_moirai(self):
        self._vendored(lambda F: F.MoiraiNode(), "uni2ts")

    def test_lag_llama(self):
        self._vendored(lambda F: F.LagLlamaNode(), "lag_llama")

    def test_patchtst(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert_node(F.PatchTSTNode(), Xtr, Xte, yreg, "regression")

    def test_itransformer(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(F.ITransformerNode(), Xtr, Xte, ybin, "binary")

    def test_tft(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(F.TFTNode(), Xtr, Xte, ybin, "binary")

    def test_gpytorch_gp(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert_node(F.GPyTorchGPNode(), Xtr, Xte, yreg, "regression")

    def test_gluonts_deepar(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, _, ybin = _synth()
        self._assert_node(F.GluonTSDeepARNode(), Xtr, Xte, ybin, "binary")

    # -- group D/E graph + causal ---------------------------------------- #
    def test_cross_asset_gnn(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert_node(F.CrossAssetGNNNode(), Xtr, Xte, yreg, "regression")

    def test_tigramite_causal(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        Xtr, Xte, yreg, _ = _synth()
        self._assert_node(F.TigramiteCausalNode(), Xtr, Xte, yreg, "regression")

    # -- group F portfolio panel nodes ----------------------------------- #
    def test_riskfolio_weight(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        panel, Xtr, Xte, ybin = _panel()
        self._assert_node(F.RiskfolioWeightNode(panel), Xtr, Xte, ybin, "binary")

    def test_pypfopt_weight(self):
        F = _try_import()
        if F is None:
            self.skipTest("foundation stack absent")
        panel, Xtr, Xte, ybin = _panel()
        self._assert_node(F.PyPortfolioOptWeightNode(panel), Xtr, Xte, ybin, "binary")

    # -- pool wiring: importable + gated out of default growth pool ------- #
    def test_pool_exposes_foundation_and_gates_default(self):
        import nodes.pool as pool
        names = pool.foundation_names()
        if not names:
            self.skipTest("foundation stack absent")
        for n in ("chronos", "patchtst", "gpytorch_gp", "tigramite_pcmci"):
            self.assertIn(n, names)
        # default (env unset) must NOT put heavy nodes in the growth pool
        import os
        if os.environ.get("MLNB_FOUNDATION_NODES") != "1":
            self.assertNotIn("chronos", pool.names())


if __name__ == "__main__":
    unittest.main()
