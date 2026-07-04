"""CORTEX B6 acceptance tests — forecast heads + data downloaders.

Head tests are network-free (synthetic forecasters); download tests use local fixtures /
the real on-disk freqtrade dump, and guard live network behind availability checks.
"""
from __future__ import annotations

import io
import unittest
from unittest import mock

import numpy as np

from data import downloads
from trading.heads import RolloutHead, build_foundation_heads, evaluate_head


def _windows(series, L=30, k=5, n=50):
    W, Y = [], []
    for i in range(L, len(series) - k):
        W.append(series[i - L:i]); Y.append(series[i:i + k])
    return W[:n], np.array(Y[:n])


class TestRolloutHead(unittest.TestCase):
    def test_direct_callable_head(self):
        f = lambda y, k: np.full(k, y[-1] + 1.0)          # +1 above last, k times
        head = RolloutHead(f, name="c", direct=True)
        out = head.forecast(np.arange(10.0), 5)
        self.assertEqual(out.shape, (5,))
        np.testing.assert_allclose(out, 10.0)

    def test_autoregressive_mode(self):
        # forecaster returns last + 1 => AR should ramp by 1 each step
        f = lambda y, k: np.array([y[-1] + 1.0])
        head = RolloutHead(f, name="ar", direct=False)
        out = head.rollout(np.arange(10.0), 4)
        np.testing.assert_allclose(out, [10.0, 11.0, 12.0, 13.0])

    def test_2d_window_uses_target_col(self):
        f = lambda y, k: np.full(k, y[-1])
        head = RolloutHead(f, name="col", direct=True, col=0)
        w = np.column_stack([np.arange(10.0), np.zeros(10)])
        self.assertAlmostEqual(head.forecast(w, 3)[0], 9.0)

    def test_error_falls_back_to_persistence(self):
        def boom(y, k):
            raise RuntimeError("model down")
        head = RolloutHead(boom, name="b", direct=True)
        out = head.forecast(np.array([1.0, 2.0, 7.0]), 3)
        self.assertTrue(head.fell_back)
        np.testing.assert_allclose(out, 7.0)              # last value repeated

    def test_short_direct_output_padded(self):
        f = lambda y, k: np.array([1.0, 2.0])             # returns 2 for k=5
        head = RolloutHead(f, name="short", direct=True)
        out = head.forecast(np.zeros(5), 5)
        self.assertEqual(out.shape, (5,))
        np.testing.assert_allclose(out[2:], 2.0)          # padded with last


class TestEvaluateHead(unittest.TestCase):
    def _sine(self):
        return np.sin(np.linspace(0, 40, 400)) * 5 + 100

    def test_oracle_head_is_trusted(self):
        series = self._sine()
        W, Y = _windows(series)
        # oracle: returns the true future (beats persistence + passes DM)
        rows = {tuple(np.round(w[-3:], 6)): y for w, y in zip(W, Y)}
        def oracle(y, k):
            return rows[tuple(np.round(y[-3:], 6))]
        head = RolloutHead(oracle, name="oracle", direct=True)
        res = evaluate_head(head, W, Y, k=5)
        self.assertTrue(res["beats_persistence"])
        self.assertTrue(res["trusted"])

    def test_persistence_head_not_trusted(self):
        series = self._sine()
        W, Y = _windows(series)
        head = RolloutHead(lambda y, k: np.full(k, y[-1]), name="pers", direct=True)
        res = evaluate_head(head, W, Y, k=5)
        self.assertFalse(res["beats_persistence"])        # can't beat itself
        self.assertFalse(res["trusted"])

    def test_report_shape(self):
        series = self._sine()
        W, Y = _windows(series)
        head = RolloutHead(lambda y, k: np.full(k, y[-1]), name="p", direct=True)
        res = evaluate_head(head, W, Y, k=5)
        for key in ("head", "beats_persistence", "dm_gate", "trusted", "per_horizon"):
            self.assertIn(key, res)


class TestBuildFoundationHeads(unittest.TestCase):
    def test_registry_is_crash_free(self):
        heads = build_foundation_heads()
        self.assertIsInstance(heads, dict)
        for h in heads.values():
            self.assertIsInstance(h, RolloutHead)


class TestDownloads(unittest.TestCase):
    _CSV = ("Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,100,101,99,100.5,1000\n"
            "2024-01-03,100.5,102,100,101.5,1200\n")

    def test_stooq_parse_from_fixture(self):
        fake = mock.MagicMock()
        fake.read.return_value = self._CSV.encode()
        fake.__enter__.return_value = fake
        with mock.patch("urllib.request.urlopen", return_value=fake):
            d = downloads.download_stooq_daily("spy.us", save=False)
        self.assertEqual(len(d["close"]), 2)
        self.assertAlmostEqual(d["close"][-1], 101.5)
        self.assertEqual(d["symbol"], "spy.us")

    def test_stooq_blocked_raises(self):
        fake = mock.MagicMock()
        fake.read.return_value = b"<!DOCTYPE html><html>robots</html>"
        fake.__enter__.return_value = fake
        with mock.patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(RuntimeError):
                downloads.download_stooq_daily("spy.us", save=False)

    def test_locate_freqtrade_1m_pattern(self):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "binance", "futures"))
        for fn in ("BTC_USDT_USDT-1m-futures.feather", "ETH_USDT-1m.feather",
                   "BTC_USDT-5m.feather", "notes.txt"):
            open(os.path.join(d, "binance", "futures", fn), "w").close()
        hits = downloads.locate_freqtrade_1m(base=d)
        self.assertEqual(len(hits), 2)                    # both 1m files, not 5m/txt

    def test_locate_freqtrade_1m_missing_dir(self):
        self.assertEqual(downloads.locate_freqtrade_1m(base="/no/such/dir"), [])


if __name__ == "__main__":
    unittest.main()
