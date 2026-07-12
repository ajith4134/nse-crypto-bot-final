"""Hot-path regression (2026-07-12): the numba rolling-Volume-Profile kernel (native/rolling_vp)
must produce IDENTICAL columns to the pure-Python oracle (features_ext._rolling_vp) on random
inputs — the JIT is a speed rewrite (~1200×), never a behavior change. If numba is absent the
wrapper returns None and the oracle runs, so this test is skipped-safe.
"""
import unittest

import numpy as np
import pandas as pd


class TestRollingVPFast(unittest.TestCase):
    def _data(self, seed, n=220):
        rng = np.random.default_rng(seed)
        close = 100 + np.cumsum(rng.normal(0, 1, n))
        high = close + np.abs(rng.normal(0, 0.5, n))
        low = close - np.abs(rng.normal(0, 0.5, n))
        vol = np.abs(rng.normal(1000, 300, n))
        return pd.DataFrame({"high": high, "low": low, "close": close, "volume": vol})

    def test_kernel_matches_oracle(self):
        from native.rolling_vp.rolling_vp import HAVE_NUMBA, rolling_vp
        if not HAVE_NUMBA:
            self.skipTest("numba not available — oracle path only")
        from trading.strategy.library import features_ext as fx
        for seed in range(4):
            df = self._data(seed)
            # oracle: force the pure-Python path by calling the loop body via a numba-less shim
            oracle = df.copy()
            # run the oracle by temporarily disabling the fast path
            import native.rolling_vp.rolling_vp as rv
            saved = rv.HAVE_NUMBA
            rv.HAVE_NUMBA = False
            try:
                fx._rolling_vp(oracle, oracle["high"], oracle["low"], oracle["close"], oracle["volume"], 96)
            finally:
                rv.HAVE_NUMBA = saved
            poc, vah, val, pos, fl, fs = rolling_vp(
                df["high"].to_numpy(), df["low"].to_numpy(),
                df["close"].to_numpy(), df["volume"].to_numpy(), 96)
            cols = {"vp_poc": poc, "vp_vah": vah, "vp_val": val,
                    "vp_pos": pos, "vp_failed_long": fl, "vp_failed_short": fs}
            for name, arr in cols.items():
                self.assertTrue(
                    np.allclose(oracle[name].to_numpy(), arr, atol=1e-6, equal_nan=True),
                    f"{name} kernel != oracle (seed {seed})")

    def test_short_input_returns_none(self):
        # n <= window → wrapper returns None (oracle then yields all-NaN), matching the reference.
        from native.rolling_vp.rolling_vp import rolling_vp
        a = np.arange(50, dtype="float64")
        self.assertIsNone(rolling_vp(a, a, a, a, 96))


if __name__ == "__main__":
    unittest.main()
