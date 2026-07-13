"""Tests for trading/direction/mirror_gate — D2 of the Direction Accuracy Program."""
import tempfile
import unittest
from pathlib import Path

import trading.state as state


def _seed(buckets: dict, market: str = "CRYPTO") -> None:
    """Seed truth buckets. Keys are given as legacy "source|regime|horizon" and the market
    is injected → "source|MARKET|regime|horizon" (the 2026-07-13 market-scoped key format)."""
    scoped = {}
    for k, v in buckets.items():
        src, rest = k.split("|", 1)
        scoped[f"{src}|{market.upper()}|{rest}"] = v
    state.save_json("direction_truth.json", {"buckets": scoped})


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import mirror_gate as mg
        mg._CACHE.update(ts=0.0, buckets=None)     # drop cross-test cache
        self.mg = mg

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestMirrorGate(_Iso):
    def test_reliably_wrong_source_is_inverted(self):
        _seed({"stochrsi|any|1h": {"n": 200, "correct": 60}})     # 30% — CI high < .45
        g = self.mg.decide("LONG", source="stochrsi", regime="any")
        self.assertEqual(g["action"], "invert")
        self.assertEqual(g["direction"], "SHORT")

    def test_trusted_source_passes(self):
        _seed({"momentum|any|1h": {"n": 200, "correct": 130}})    # 65%
        g = self.mg.decide("SHORT", source="momentum", regime="any")
        self.assertEqual(g["action"], "pass")
        self.assertEqual(g["direction"], "SHORT")

    def test_proven_coin_flip_abstains(self):
        _seed({"noise|any|1h": {"n": 400, "correct": 200}})       # 50%, tight CI
        g = self.mg.decide("LONG", source="noise", regime="any")
        self.assertEqual(g["action"], "abstain")
        self.assertIsNone(g["direction"])

    def test_unproven_source_explores_untouched(self):
        _seed({"newbie|any|1h": {"n": 5, "correct": 0}})          # 0% but n=5
        g = self.mg.decide("LONG", source="newbie", regime="any")
        self.assertEqual(g["action"], "pass")
        self.assertEqual(g["direction"], "LONG")

    def test_regime_bucket_beats_cross_regime_sum(self):
        _seed({"s|trend|1h": {"n": 60, "correct": 40},            # 67% in trend
               "s|chop|1h": {"n": 200, "correct": 50}})           # 25% in chop
        g_tr = self.mg.decide("LONG", source="s", regime="trend")
        self.assertEqual(g_tr["action"], "pass")                  # trend bucket rules
        g_ch = self.mg.decide("LONG", source="s", regime="chop")
        self.assertEqual(g_ch["action"], "invert")                # chop bucket rules

    def test_kill_switch_and_unknown_pass_through(self):
        import os
        _seed({"stochrsi|any|1h": {"n": 200, "correct": 60}})
        os.environ["MIRROR_GATE"] = "0"
        try:
            g = self.mg.decide("LONG", source="stochrsi", regime="any")
            self.assertEqual(g["action"], "off")
            self.assertEqual(g["direction"], "LONG")
        finally:
            os.environ.pop("MIRROR_GATE")
        self.assertEqual(self.mg.decide("FLAT", source="x")["direction"], None)

    def test_apply_records_mirror_source(self):
        import json
        _seed({"stochrsi|any|1h": {"n": 200, "correct": 60}})
        final, g = self.mg.apply("LONG", source="stochrsi", symbol="ETH/USDT:USDT",
                                 segment="futures", regime="any")
        self.assertEqual(final, "SHORT")
        pend = (Path(state.STATE_DIR) / "direction_truth_pending.jsonl").read_text()
        row = json.loads(pend.splitlines()[0])
        self.assertEqual(row["source"], "mirror:stochrsi")        # flip earns its own record
        self.assertEqual(row["direction"], "SHORT")

    def test_pools_clean_horizons_to_catch_stable_anti_signal(self):
        # meanrev-like: below chance at EVERY clean horizon, none clearing the invert
        # bar alone, but pooled the CI tightens under 0.45 → invert. "exit" is ignored.
        _seed({"meanrev|any|15m": {"n": 113, "correct": 35},          # 31%
               "meanrev|any|1h": {"n": 113, "correct": 43},           # 38% (CI too wide alone)
               "meanrev|any|4h": {"n": 110, "correct": 46},           # 42%
               "meanrev|any|exit": {"n": 138, "correct": 33}})        # polluted — must be dropped
        g = self.mg.decide("LONG", source="meanrev", regime="any")
        self.assertEqual(g["action"], "invert")
        self.assertEqual(g["direction"], "SHORT")
        self.assertGreater(g["n"], 300)                               # pooled 15m+1h+4h, not exit
        self.assertLess(g["n"], 400)                                  # exit's 138 excluded

    def test_horizon_specific_error_is_left_alone(self):
        # 30% at 1h but ~50% elsewhere → error NOT stable → pooled CI clears the bar → pass.
        _seed({"unstable|any|15m": {"n": 100, "correct": 50},
               "unstable|any|1h": {"n": 60, "correct": 18},           # 30% at 1h only
               "unstable|any|4h": {"n": 100, "correct": 52}})
        self.assertEqual(self.mg.decide("LONG", source="unstable")["action"], "pass")
        # but a caller pinning the 1h horizon still sees the single-horizon inversion
        g1 = self.mg.decide("LONG", source="unstable", horizon="1h")
        self.assertEqual(g1["action"], "invert")

    def test_market_isolation_no_crosspollination(self):
        # SAME source, OPPOSITE reliability per market: reliably-wrong in CRYPTO (invert),
        # reliably-right in NSE (pass). The gate must judge each market on its OWN bucket and
        # never pool them (multi-market isolation, 2026-07-13).
        state.save_json("direction_truth.json", {"buckets": {
            "shared|CRYPTO|any|1h": {"n": 200, "correct": 60},    # 30% → invert
            "shared|NSE|any|1h": {"n": 200, "correct": 140},      # 70% → trust/pass
        }})
        self.mg._CACHE.update(ts=0.0, buckets=None)
        g_c = self.mg.decide("LONG", source="shared", regime="any", market="CRYPTO")
        g_n = self.mg.decide("LONG", source="shared", regime="any", market="NSE")
        self.assertEqual(g_c["action"], "invert")                 # crypto bucket only
        self.assertEqual(g_c["direction"], "SHORT")
        self.assertEqual(g_n["action"], "pass")                   # nse bucket only
        self.assertEqual(g_n["direction"], "LONG")

    def test_status_lists_actions(self):
        _seed({"bad|any|1h": {"n": 200, "correct": 60},
               "good|any|1h": {"n": 200, "correct": 130}})
        s = self.mg.status()
        acts = {a["source"]: a["action"] for a in s["active"]}
        self.assertEqual(acts["bad"], "invert")
        self.assertEqual(acts["good"], "trusted")


if __name__ == "__main__":
    unittest.main()
