"""B3 lens paper lane: nominations honest (abstain-by-default), rotation covers, entries
carry the lens identity and a taken=True truth-ledger claim."""
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock


class _Iso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import trading.state as state
        self._orig = state.STATE_DIR
        state.STATE_DIR = pathlib.Path(self.tmp)
        os.environ["LENS_LANE"] = "1"
        from trading.brain import lens_lane
        self.ll = lens_lane
        lens_lane._CURSOR.clear()

    def tearDown(self):
        import trading.state as state
        state.STATE_DIR = self._orig


class TestNominations(_Iso):
    def _run(self, lens_fn, symbols=("A", "B", "C"), **env):
        with mock.patch.dict(os.environ, {k: str(v) for k, v in env.items()}), \
             mock.patch.object(self.ll, "LENSES", {"fake": (lens_fn, "cheap")}):
            return self.ll.nominations(symbols=list(symbols), segment="futures",
                                       ohlcv_fn=lambda s: None,
                                       features_fn=lambda s: {"m_momentum": 0.7})

    def test_strongest_edge_wins_and_direction_matches(self):
        p_by_sym = {"A": 0.55, "B": 0.12, "C": 0.61}
        noms = self._run(lambda ctx: p_by_sym[ctx["symbol"]])
        self.assertEqual(len(noms), 1)
        self.assertEqual(noms[0]["symbol"], "B")           # |0.12-0.5|=0.38 is strongest
        self.assertEqual(noms[0]["direction"], "SHORT")
        self.assertEqual(noms[0]["lens"], "fake")

    def test_weak_edges_abstain(self):
        noms = self._run(lambda ctx: 0.52, LENS_LANE_MIN_EDGE="0.08")
        self.assertEqual(noms, [])                          # 0.02 edge < 0.08 bar

    def test_none_and_raising_lenses_abstain_silently(self):
        self.assertEqual(self._run(lambda ctx: None), [])

        def _boom(ctx):
            raise RuntimeError("lens down")
        self.assertEqual(self._run(_boom), [])

    def test_kill_switch(self):
        with mock.patch.dict(os.environ, {"LENS_LANE": "0"}):
            self.assertEqual(self.ll.nominations(symbols=["A"], segment="futures",
                                                 ohlcv_fn=lambda s: None,
                                                 features_fn=lambda s: {}), [])

    def test_per_lens_disable(self):
        noms = self._run(lambda ctx: 0.9, LENS_LANE_DISABLE="fake")
        self.assertEqual(noms, [])

    def test_rotation_advances_coverage(self):
        seen = []
        self._run(lambda ctx: seen.append(ctx["symbol"]) or None,
                  symbols=list("ABCDE"), LENS_LANE_SCAN_N="2")
        first = list(seen); seen.clear()
        self._run(lambda ctx: seen.append(ctx["symbol"]) or None,
                  symbols=list("ABCDE"), LENS_LANE_SCAN_N="2")
        self.assertNotEqual(first, seen)                    # cursor moved


class TestExecutorLane(_Iso):
    def test_entry_carries_identity_and_claim(self):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        ex = BrainExecutor.__new__(BrainExecutor)            # no engine boot
        ex.segment = "futures"
        ex.decider = mock.Mock(_ohlcv=lambda s: None)
        ex.symbols = lambda: ["X/USDT:USDT"]
        placed = []
        cli = mock.Mock()
        cli.open_pairs.return_value = []
        cli.tradeable_form = lambda s, seg: s
        cli.place_order = lambda **kw: placed.append(kw) or {"ok": True}
        ex.client = lambda: cli
        ex._record_entry_meta = mock.Mock()
        with mock.patch.object(self.ll, "LENSES",
                               {"cortex": (lambda ctx: 0.9, "cheap")}), \
             mock.patch("trading.direction.app_signals.signals", lambda s, **k: []), \
             mock.patch("trading.direction.regime.classify", lambda s: {"regime": "chop"}):
            rep = ex.open_lens_lane(allow_live=False)
        self.assertEqual(rep["entered"], ["X/USDT:USDT"])
        self.assertEqual(placed[0]["enter_tag"], "lens:cortex")
        self.assertEqual(placed[0]["side"], "long")
        self.assertFalse(placed[0]["allow_live"])
        ex._record_entry_meta.assert_called_once()
        # taken=True identity claim landed in the pending ledger
        import trading.state as state
        pend = pathlib.Path(state.STATE_DIR) / "direction_truth_pending.jsonl"
        rows = [json.loads(l) for l in pend.read_text().splitlines()]
        mine = [r for r in rows if r["source"] == "lens:cortex"]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0]["taken"])
        self.assertEqual(mine[0]["direction"], "LONG")

    def test_refused_order_is_skip_not_entry(self):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        ex = BrainExecutor.__new__(BrainExecutor)
        ex.segment = "futures"
        ex.decider = mock.Mock(_ohlcv=lambda s: None)
        ex.symbols = lambda: ["X/USDT:USDT"]
        cli = mock.Mock()
        cli.open_pairs.return_value = []
        cli.tradeable_form = lambda s, seg: s
        cli.place_order = lambda **kw: {"ok": False, "error": "no such symbol"}
        ex.client = lambda: cli
        ex._record_entry_meta = mock.Mock()
        with mock.patch.object(self.ll, "LENSES",
                               {"river_online": (lambda ctx: 0.1, "cheap")}), \
             mock.patch("trading.direction.app_signals.signals", lambda s, **k: []), \
             mock.patch("trading.direction.regime.classify", lambda s: {"regime": "chop"}):
            rep = ex.open_lens_lane(allow_live=False)
        self.assertEqual(rep["entered"], [])
        self.assertEqual(rep["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
