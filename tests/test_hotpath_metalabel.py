"""Regression: the numba triple_barrier_labels hot path (Pillar 9) must EXACTLY equal the
reference pure-python loop — same side/label/ret/bars_held/barrier on random inputs, varied
barriers, and edge sizes. This is the correctness oracle that lets the compiled path be trusted.
"""
import unittest

import numpy as np
import pandas as pd

from trading.strategy.metalabel import _atr, triple_barrier_labels


def _reference(ohlcv, signal, *, pt=2.0, sl=1.0, max_hold=24, atr_n=14):
    """The original pure-python triple-barrier loop, kept verbatim as the oracle."""
    close = ohlcv["close"].to_numpy(dtype=float)
    atr = _atr(ohlcv, atr_n)
    sig = np.asarray(signal, dtype=float)
    n = len(close)
    rows = []
    for i in range(n - 1):
        side = 1 if sig[i] > 0 else (-1 if sig[i] < 0 else 0)
        if side == 0:
            continue
        entry = close[i]
        a = atr[i] if atr[i] > 0 else entry * 0.01
        up = entry + pt * a
        dn = entry - sl * a
        end = min(i + max_hold, n - 1)
        label, ret, barrier, bars = 0, 0.0, "time", end - i
        for j in range(i + 1, end + 1):
            px = close[j]
            hit_up = px >= up
            hit_dn = px <= dn
            if side > 0 and hit_up or side < 0 and hit_dn:
                label, ret, barrier, bars = 1, side * (px - entry) / entry, "profit", j - i
                break
            if side > 0 and hit_dn or side < 0 and hit_up:
                label, ret, barrier, bars = 0, side * (px - entry) / entry, "stop", j - i
                break
        else:
            ret = side * (close[end] - entry) / entry
            label = 1 if ret > 0 else 0
        rows.append({"bar": i, "side": side, "label": label, "ret": float(ret),
                     "bars_held": bars, "barrier": barrier})
    return pd.DataFrame(rows).set_index("bar") if rows else pd.DataFrame(
        columns=["side", "label", "ret", "bars_held", "barrier"])


def _make(n, seed):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    high = close + np.abs(rng.standard_normal(n) * 0.3)
    low = close - np.abs(rng.standard_normal(n) * 0.3)
    ohlcv = pd.DataFrame({"high": high, "low": low, "close": close})
    sig = pd.Series(np.where(rng.random(n) < 0.3, rng.choice([-1, 1, 0], n), 0))
    return ohlcv, sig


class TestTripleBarrierHotPath(unittest.TestCase):
    def test_numba_matches_reference(self):
        for seed in range(5):
            for n in (2, 50, 500, 2000):
                o, s = _make(n, seed)
                pd.testing.assert_frame_equal(
                    triple_barrier_labels(o, s), _reference(o, s),
                    check_dtype=False, obj=f"seed={seed} n={n}")

    def test_varied_barriers(self):
        o, s = _make(1000, 7)
        for pt, sl, mh in [(1.0, 1.0, 5), (3.0, 0.5, 50), (2.0, 2.0, 10)]:
            pd.testing.assert_frame_equal(
                triple_barrier_labels(o, s, pt=pt, sl=sl, max_hold=mh),
                _reference(o, s, pt=pt, sl=sl, max_hold=mh),
                check_dtype=False, obj=f"pt={pt} sl={sl} mh={mh}")

    def test_no_signals_empty(self):
        o, _ = _make(100, 1)
        df = triple_barrier_labels(o, pd.Series(np.zeros(100)))
        self.assertEqual(len(df), 0)
        self.assertListEqual(list(df.columns), ["side", "label", "ret", "bars_held", "barrier"])


if __name__ == "__main__":
    unittest.main()
