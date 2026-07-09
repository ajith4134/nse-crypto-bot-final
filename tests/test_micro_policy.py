"""Tests for invent-beyond #4 — distilled entry micro-policy (teacher table + student)."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

import trading.state as tstate


def _df(n=600, seed=7):
    import pandas as pd
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.004, n))
    return pd.DataFrame({"open": c, "high": c * 1.002, "low": c * 0.998,
                         "close": c, "volume": rng.uniform(1e5, 2e5, n)})


class _Sandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)
        import trading.crypto.freqtrade.micro_policy as mp
        mp.invalidate()

    def tearDown(self):
        import trading.crypto.freqtrade.micro_policy as mp
        mp.invalidate()
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()


class _StubDecider:
    """Teacher stub: momentum winner on coin A (gates pass), gated-out coin B."""
    _min_final = 0.5

    def __init__(self):
        self.dfs = {"A/USDT:USDT": _df(seed=1), "B/USDT:USDT": _df(seed=2)}

    def tournament(self, symbol):
        df = self.dfs[symbol]
        c = df["close"].to_numpy()
        sig = np.sign(np.diff(c, prepend=c[0]))          # 1-bar momentum "winner"
        if symbol.startswith("B"):
            return {"ranked": [], "best": {"name": "s_b", "final": 0.1, "sharpe": 0.2,
                                           "win_rate": 0.4, "n_active": 50},
                    "deflated_psr": 0.1, "deflated_ok": False, "sr_bench": 1.0,
                    "close": c, "last_price": float(c[-1]), "df": df,
                    "winner_signal": sig}
        return {"ranked": [], "best": {"name": "s_a", "final": 2.0, "sharpe": 2.5,
                                       "win_rate": 0.6, "n_active": 300},
                "deflated_psr": 0.9, "deflated_ok": True, "sr_bench": 1.0,
                "close": c, "last_price": float(c[-1]), "df": df,
                "winner_signal": sig}


class TestCheapFeatures(unittest.TestCase):
    def test_shape_and_warmup_nans(self):
        from trading.crypto.freqtrade.micro_policy import _FEATURE_NAMES, _feats_from_df
        f = _feats_from_df(_df())
        self.assertEqual(f.shape, (600, len(_FEATURE_NAMES)))
        self.assertTrue(np.all(np.isfinite(f[100:])))    # finite after warmup
        self.assertTrue(np.any(np.isnan(f[:10])))        # honest NaN warmup rows

    def test_fast_enough_for_the_cycle_budget(self):
        from trading.crypto.freqtrade.micro_policy import _feats_from_df
        df = _df()
        _feats_from_df(df)                               # warm numpy
        t0 = time.monotonic()
        _feats_from_df(df)
        self.assertLess(time.monotonic() - t0, 0.25)     # ms-scale, generous CI margin


class TestDistillAndDecide(_Sandbox):
    def test_distill_persists_table_and_trains_student(self):
        from trading.crypto.freqtrade import micro_policy as mp
        rep = mp.distill_once(decider=_StubDecider(),
                              symbols=["A/USDT:USDT", "B/USDT:USDT"])
        self.assertEqual(rep["coins"], 2)
        self.assertTrue(rep["trained"]["ok"], rep["trained"])
        d = tstate.load_json("micro_policy.json", {})
        self.assertTrue(d["coins"]["A/USDT:USDT"]["gates_ok"])
        self.assertFalse(d["coins"]["B/USDT:USDT"]["gates_ok"])
        self.assertGreater(rep["trained"]["teacher_agreement"], 0.5)

    def test_decide_gated_coin_sits_out_without_the_student(self):
        from trading.crypto.freqtrade import micro_policy as mp
        stub = _StubDecider()
        mp.distill_once(decider=stub, symbols=["A/USDT:USDT", "B/USDT:USDT"])
        m = mp.get_micro()
        self.assertIsNotNone(m)
        d = m.decide("B/USDT:USDT", stub.dfs["B/USDT:USDT"], in_position=False)
        self.assertEqual(d["action"], "FLAT")
        self.assertEqual(d["_brain"]["source"], "micro_policy")

    def test_decide_unknown_or_stale_coin_abstains_to_teacher(self):
        from trading.crypto.freqtrade import micro_policy as mp
        stub = _StubDecider()
        mp.distill_once(decider=stub, symbols=["A/USDT:USDT"])
        m = mp.get_micro()
        self.assertIsNone(m.decide("Z/USDT:USDT", stub.dfs["A/USDT:USDT"],
                                   in_position=False))   # unknown coin
        d = tstate.load_json("micro_policy.json", {})
        d["coins"]["A/USDT:USDT"]["ts"] = time.time() - 40 * 3600
        tstate.save_json("micro_policy.json", d)
        mp.invalidate()
        m = mp.get_micro()
        self.assertIsNone(m.decide("A/USDT:USDT", stub.dfs["A/USDT:USDT"],
                                   in_position=False))   # stale teacher

    def test_decide_speed_is_millisecond_scale(self):
        from trading.crypto.freqtrade import micro_policy as mp
        stub = _StubDecider()
        mp.distill_once(decider=stub, symbols=["A/USDT:USDT"])
        m = mp.get_micro()
        df = stub.dfs["A/USDT:USDT"]
        m.decide("A/USDT:USDT", df, in_position=False)   # warm
        t0 = time.monotonic()
        for _ in range(20):
            m.decide("A/USDT:USDT", df, in_position=False)
        per = (time.monotonic() - t0) / 20
        self.assertLess(per, 0.05)                       # ≤50ms each, generous CI margin

    def test_no_distill_yet_gives_none_micro(self):
        from trading.crypto.freqtrade import micro_policy as mp
        self.assertIsNone(mp.get_micro())
        st = mp.status()
        self.assertFalse(st["trained"]["ok"])


if __name__ == "__main__":
    unittest.main()
