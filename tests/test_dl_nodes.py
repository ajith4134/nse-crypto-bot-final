"""DL-node acceptance tests: the darts neural forecasters, the PyTorch
autoencoder, the new LSTM node, and the TabPFN foundation transformer.

Closes the audit gap that NHiTS/TCN/N-BEATS/TSMixer/GRU/AE had no dedicated
assertions. Every node is exercised on a KNOWN-signal benchmark (mackey_glass —
deterministic chaos, so 'beats naive baseline' is meaningful, not flaky), and we
assert the REAL training path ran (`fell_back is False`) — not a silent fallback.

  1. Each darts forecast node fits, trains (no fallback), and satisfies the
     NodeProtocol surface (proba in [0,1], predict_output row width).
  2. The new LSTMNode trains as a real RNN(model="LSTM") and is a distinct class
     from GRUNode.
  3. AEAnomalyNode trains a genuine torch.nn autoencoder (no fallback).
  4. TabPFNNode predicts binary / multiclass / regression via the pretrained
     transformer (no fallback) and beats the naive baseline on the binary signal.
  5. LSTM + TabPFN are registered in the live run_multi pool.
"""
from __future__ import annotations

import unittest

from core.node_protocol import NodeProtocol
from data.benchmarks import make_benchmark_dataset
from nodes import dl_nodes as DL


def _data(n: int = 280):
    """A learnable benchmark: deterministic Mackey-Glass chaos (real signal)."""
    return make_benchmark_dataset("mackey_glass", n=n, noise=0.0)


def _split(X, y, frac: float = 0.75):
    """Chronological split — these nodes forecast one step ahead causally."""
    cut = int(len(X) * frac)
    return X[:cut], list(y[:cut]), X[cut:], list(y[cut:])


def _naive(y) -> float:
    """Majority-class accuracy of the test labels (the baseline to beat)."""
    counts = {v: list(y).count(v) for v in set(y)}
    return max(counts.values()) / len(y)


def _assert_protocol(tc: unittest.TestCase, node, X):
    """The shared NodeProtocol output contract."""
    tc.assertIsInstance(node, NodeProtocol)
    proba = node.predict_proba(X)
    tc.assertEqual(len(proba), len(X))
    tc.assertTrue(all(0.0 <= float(p) <= 1.0 for p in proba), "proba out of [0,1]")
    out = node.predict_output(X)
    tc.assertEqual(len(out), len(X))
    tc.assertTrue(all(len(row) >= 1 for row in out))
    tc.assertEqual(len(node.predict(X)), len(X))


class TestDartsForecastNodes(unittest.TestCase):
    """The CPU darts neural forecasters all train (no fallback) + conform."""

    @classmethod
    def setUpClass(cls):
        d = _data()
        cls.Xtr, cls.ytr, cls.Xte, cls.yte = _split(d["X"], d["y"])

    def _check(self, node):
        node.fit(self.Xtr, self.ytr)
        # real neural training ran — not the linear/AR fallback
        self.assertFalse(node.fell_back, f"{node.name} silently fell back to linear/AR")
        self.assertGreater(node.fit_seconds, 0.0)
        _assert_protocol(self, node, self.Xte)

    def test_nhits(self):    self._check(DL.nhits_node())
    def test_tcn(self):      self._check(DL.tcn_node())
    def test_nbeats(self):   self._check(DL.nbeats_node())
    def test_tsmixer(self):  self._check(DL.tsmixer_node())
    def test_gru(self):      self._check(DL.gru_node())

    def test_lstm_trains_and_is_distinct_from_gru(self):
        node = DL.lstm_node()
        self.assertIsInstance(node, DL.LSTMNode)
        self.assertNotIsInstance(node, DL.GRUNode)
        self._check(node)
        # it really built an LSTM RNN, not a GRU
        self.assertEqual(node._build_model().rnn_type_or_module, "LSTM")


class TestAutoencoderNode(unittest.TestCase):
    """AEAnomalyNode trains a genuine torch autoencoder (no fallback)."""

    def test_ae_trains_real_net(self):
        d = _data()
        Xtr, ytr, Xte, _ = _split(d["X"], d["y"])
        node = DL.ae_anomaly_node()
        node.fit(Xtr, ytr)
        self.assertFalse(node.fell_back, "AE fell back from torch to numpy")
        self.assertIsNotNone(node._net, "AE did not build a torch net")
        _assert_protocol(self, node, Xte)


class TestTabPFNNode(unittest.TestCase):
    """TabPFN pretrained transformer predicts all three head types (no fallback)."""

    @classmethod
    def setUpClass(cls):
        cls.d = _data()

    def test_binary_beats_naive(self):
        Xtr, ytr, Xte, yte = _split(self.d["X"], self.d["targets"]["direction"])
        node = DL.tabpfn_node()
        node.fit(Xtr, ytr)
        self.assertFalse(node.fell_back, "TabPFN fell back to the sklearn pipeline")
        _assert_protocol(self, node, Xte)
        acc = sum(int(p == t) for p, t in zip(node.predict(Xte), yte)) / len(yte)
        self.assertGreaterEqual(acc, _naive(yte),
                                f"TabPFN acc {acc:.3f} < naive {_naive(yte):.3f}")

    def test_multiclass(self):
        node = DL.tabpfn_node()
        node.task = "multiclass"
        Xtr, ytr, Xte, _ = _split(self.d["X"], self.d["targets"]["regime"])
        node.fit(Xtr, ytr)
        self.assertFalse(node.fell_back)
        self.assertEqual(node.task, "multiclass")
        out = node.predict_output(Xte)
        self.assertEqual(len(out[0]), len(set(self.d["targets"]["regime"])))
        _assert_protocol(self, node, Xte)

    def test_regression(self):
        node = DL.tabpfn_node()
        node.task = "regression"
        Xtr, ytr, Xte, _ = _split(self.d["X"], self.d["targets"]["magnitude"])
        node.fit(Xtr, ytr)
        self.assertFalse(node.fell_back)
        out = node.predict_output(Xte)
        self.assertTrue(all(len(row) == 1 for row in out))
        _assert_protocol(self, node, Xte)


class TestPoolRegistration(unittest.TestCase):
    """The new nodes are wired into the live run_multi pool (usable by the network)."""

    def test_lstm_and_tabpfn_registered(self):
        import run_multi
        names = {n for n, _ in run_multi._task_aware_specs()} \
            if hasattr(run_multi, "_task_aware_specs") else set()
        if not names:                                  # fall back to source scan
            import inspect
            src = inspect.getsource(run_multi)
            self.assertIn('"lstm", DL.lstm_node', src)
            self.assertIn('"tabpfn", DL.tabpfn_node', src)
        else:
            self.assertIn("lstm", names)
            self.assertIn("tabpfn", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
