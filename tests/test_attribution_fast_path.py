"""tests/test_attribution_fast_path.py — the hot-path attribution must be cheap.

Regression for the 2026-07-11 freeze: explain_trade(fast=True) ran the occlusion fallback
(~len(features)+2 net._proba calls). With TRADE_NET_ENGINE=tabpfn each _proba is a heavy
TabPFN forward, so ~44 calls per tick-fired entry saturated every CPU core and froze the
headed browser. The fast path must make at most ONE net call and return p_win only.
"""
import unittest
from unittest import mock

from trading.brain import attribution


class _CountingNet:
    """Stand-in outcome net that counts _proba calls."""
    trained = True

    def __init__(self):
        self.calls = 0

    def _proba(self, _row):
        self.calls += 1
        return 0.6


class TestAttributionFastPath(unittest.TestCase):
    def _run(self, fast):
        net = _CountingNet()
        feats = list(range(42))                       # 42-feature vector, like the real one
        with mock.patch.object(attribution, "trade_feature_row", return_value=feats), \
             mock.patch.dict(attribution._tf._CACHE if hasattr(attribution, "_tf") else {},
                             {}, clear=False):
            # inject the cached net the fast path reads
            from trading.brain import trade_features as tf
            with mock.patch.dict(tf._CACHE, {"net": net}, clear=False), \
                 mock.patch.object(attribution, "get_outcome_net", return_value=net), \
                 mock.patch.object(attribution, "_background",
                                   return_value=[[0.0] * len(feats) for _ in range(5)]):
                out = attribution.explain_trade(
                    {"symbol": "BTC/USDT", "direction": "long"},
                    [{"x": 1}] * 10, fast=fast)
        return out, net.calls

    def test_fast_path_makes_at_most_one_net_call(self):
        out, calls = self._run(fast=True)
        self.assertLessEqual(calls, 1, f"fast path made {calls} net calls (must be ≤1)")
        self.assertEqual(out["engine"], "fast-pwin")
        self.assertEqual(out["p_win"], 0.6)
        self.assertEqual(out["top"], [])              # no per-feature occlusion on the hot path

    def test_slow_path_still_attributes(self):
        # the NON-fast path may make many calls (occlusion/SHAP) — that's expected off the hot
        # path; assert it still produces feature drivers, proving we only gated the fast path.
        out, calls = self._run(fast=False)
        self.assertGreater(calls, 1)                  # full attribution is allowed to be heavy
        self.assertIn(out["engine"], ("shap-kernel", "occlusion"))


if __name__ == "__main__":
    unittest.main()
