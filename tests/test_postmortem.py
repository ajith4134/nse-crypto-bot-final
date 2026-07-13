"""tests/test_postmortem.py — Trade Post-Mortem & Excursion Engine (trading/brain/postmortem.py).

Exercises the real logic against a synthetic journal with KNOWN winning/losing patterns:
feature extraction, subgroup mining (+ market isolation + leakage exclusion), the MFE/MAE
feather-replay math and its fallback, per-trade attribution, and the close-the-loop signal.
STATE_DIR is monkeypatched to a temp dir so nothing touches the real journal (isolate-state rule).
"""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from trading import state as tstate
from trading.brain import postmortem as pm


def _trade(symbol, direction, regime, preset, net_pnl, *, market="CRYPTO",
           exchange="binance", entry=100.0, qty=1.0, lev=5.0, hour=10):
    """One synthetic closed-trade dict with the entry context the miner reads."""
    return {
        "symbol": symbol, "direction": direction, "market": market, "exchange": exchange,
        "instrument_type": "PERP" if market == "CRYPTO" else "FUT",
        "segment": "futures", "strategy_name": "s", "leverage": lev, "entry_hour": hour,
        "entry_price": entry, "quantity": qty, "net_pnl": net_pnl,
        "market_regime_entry": regime,
        "entry_datetime": "2026-07-01T10:00:00+00:00",
        "exit_datetime": "2026-07-01T11:00:00+00:00",
        "decision_snapshot": {"regime": regime, "segment": "futures",
                              "brain": {"filter": {"filter_preset": preset, "filter_score": 20.0}}},
    }


class PostmortemBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)
        pm._OHLC_CACHE.clear()

    def tearDown(self):
        tstate.STATE_DIR = self._orig
        self._tmp.cleanup()

    def _write_journal(self, trades):
        tstate.save_json("journal.json", trades)


class TestFeatures(PostmortemBase):
    def test_feature_extraction_and_win_label(self):
        t = _trade("BTC/USDT:USDT", "LONG", "trend", "momentum", 12.0)
        f = pm.trade_features(t)
        self.assertEqual(f["direction"], "LONG")
        self.assertEqual(f["regime"], "trend")
        self.assertEqual(f["filter_preset"], "momentum")
        self.assertEqual(f["leverage"], 5.0)
        self.assertTrue(pm._win_of(t))
        self.assertFalse(pm._win_of({**t, "net_pnl": -3.0}))
        self.assertIsNone(pm._win_of({"symbol": "X"}))

    def test_exit_only_fields_excluded_from_features(self):
        # setup_type / exit_reason are known only at exit — must NOT be mineable (leakage).
        t = _trade("BTC/USDT:USDT", "LONG", "trend", "momentum", 5.0)
        t["setup_type"] = "roi"
        self.assertNotIn("setup", pm.trade_features(t))

    def test_market_of(self):
        self.assertEqual(pm._market_of(_trade("BTC/USDT:USDT", "LONG", "trend", "m", 1)), "CRYPTO")
        self.assertEqual(pm._market_of({"symbol": "NSE:INFY", "exchange": "NSE",
                                        "instrument_type": "EQ"}), "NSE")


class TestMining(PostmortemBase):
    def _dataset(self):
        # DIRECTION is the clean signal (regime is mixed so it can't stand in for it):
        # crypto LONG wins / SHORT loses; NSE the OPPOSITE — proves markets don't cross-pollinate.
        trades = []
        for i in range(80):
            reg = "trend" if i % 2 else "range"
            trades.append(_trade(f"C{i%8}/USDT:USDT", "LONG", reg, "momentum", 10.0))
        for i in range(80):
            reg = "trend" if i % 2 else "range"
            trades.append(_trade(f"C{i%8}/USDT:USDT", "SHORT", reg, "reversal", -8.0))
        for i in range(60):
            reg = "trend" if i % 2 else "range"
            trades.append(_trade(f"N{i%6}", "SHORT", reg, "breakout", 7.0,
                                 market="NSE", exchange="NSE"))
        for i in range(60):
            reg = "trend" if i % 2 else "range"
            trades.append(_trade(f"N{i%6}", "LONG", reg, "breakout", -6.0,
                                 market="NSE", exchange="NSE"))
        return trades

    def test_mine_finds_winning_and_losing_patterns(self):
        self._write_journal(self._dataset())
        rep = pm.mine_patterns("CRYPTO")
        self.assertGreater(rep["CRYPTO"]["winning"], 0)
        self.assertGreater(rep["CRYPTO"]["losing"], 0)
        st = pm.status("CRYPTO")["markets"]["CRYPTO"]
        # the top winning rule must reference the real winning context (LONG / momentum)
        top_win = " ".join(r["rule"] for r in st["winning"][:5])
        self.assertTrue(any(k in top_win for k in ("LONG", "momentum")), top_win)
        # every winning rule genuinely beats base; every losing rule is below base
        for r in st["winning"]:
            self.assertGreater(r["win_rate"], st["base_rate"])
        for r in st["losing"]:
            self.assertLess(r["win_rate"], st["base_rate"])
        # rule text and its stats describe the same set (recomputed from cleaned predicates)
        for r in st["winning"] + st["losing"]:
            self.assertGreaterEqual(r["n"], pm._MIN_SUBGROUP)

    def test_market_isolation(self):
        self._write_journal(self._dataset())
        pm.mine_patterns()                              # both markets
        # A LONG candidate scored in each market must give OPPOSITE leans: LONG is the winning
        # side in crypto but the losing side in NSE → isolation, no cross-pollination. (Include
        # the preset because direction/preset are collinear here and the coverage-dedup keeps
        # only one of the identical-coverage rules.)
        c = pm.pattern_signal({"direction": "LONG", "filter_preset": "momentum"}, "CRYPTO", None)
        n = pm.pattern_signal({"direction": "LONG", "filter_preset": "breakout"}, "NSE", None)
        self.assertFalse(c["abstained"])
        self.assertFalse(n["abstained"])
        self.assertGreater(c["p_up"], 0.5)      # LONG wins in crypto → bullish on taking the trade
        self.assertLess(n["p_up"], 0.5)         # LONG loses in NSE → bearish
        # and the winning-rule text carries the OPPOSITE winning context per market (direction and
        # preset are collinear here, so accept either token for crypto's LONG/momentum winner).
        c_win = " ".join(r["rule"] for r in pm.status("CRYPTO")["markets"]["CRYPTO"]["winning"])
        n_win = " ".join(r["rule"] for r in pm.status("NSE")["markets"]["NSE"]["winning"])
        self.assertTrue("LONG" in c_win or "momentum" in c_win, c_win)  # crypto winner = LONG side
        self.assertIn("SHORT", n_win)                                    # NSE winner = SHORT side
        self.assertNotIn("SHORT", c_win)                                 # crypto winner is NOT short

    def test_insufficient_data_is_honest(self):
        self._write_journal([_trade("BTC/USDT:USDT", "LONG", "trend", "momentum", 1.0)] * 5)
        rep = pm.mine_patterns("CRYPTO")
        self.assertTrue(rep["CRYPTO"]["insufficient"])
        self.assertTrue(pm.status("CRYPTO")["markets"]["CRYPTO"]["insufficient"])


class TestExcursion(PostmortemBase):
    def test_replay_math_long(self):
        # synthetic 5m candles: entry 100 at t0; low dips to 98 (MAE 2%), high runs to 110 (MFE 10%)
        base = 1_700_000_000
        ts = np.array([base + i * 300 for i in range(6)])
        high = np.array([100.5, 101.0, 99.0, 105.0, 110.0, 108.0])
        low = np.array([99.5, 98.0, 97.5, 100.0, 106.0, 104.0])
        close = np.array([100.0, 99.0, 98.0, 104.0, 109.0, 107.0])
        pm._OHLC_CACHE["k"] = (1.0, (ts, high, low, close))
        orig = pm._ohlc
        pm._ohlc = lambda sym, seg: (ts, high, low, close)
        try:
            ex = pm._replay_excursion("BTC/USDT:USDT", "futures", "LONG", 100.0,
                                      base, base + 5 * 300)
        finally:
            pm._ohlc = orig
        self.assertAlmostEqual(ex["mfe_pct"], 10.0, places=1)      # 110 high → +10%
        self.assertGreaterEqual(ex["mae_pct"], 2.4)                # 97.5 low → ~2.5%
        self.assertIsNotNone(ex["minutes_to_mfe"])
        self.assertGreaterEqual(ex["ideal_entry_offset_pct"], 2.0)  # could have entered ~2.5% cheaper

    def test_fallback_uses_stored_mae_mfe(self):
        # no feather for this symbol → falls back to journal-stored currency excursions
        t = _trade("NOFEATHER/USDT:USDT", "LONG", "trend", "momentum", 5.0, entry=100.0, qty=2.0)
        t["mfe"] = 20.0    # 20 quote / 2 qty / 100 entry = 10%
        t["mae"] = 4.0     # 4 / 2 / 100 = 2%
        ex = pm.excursion(t)
        self.assertEqual(ex["basis"], "journal_stored")
        self.assertAlmostEqual(ex["mfe_pct"], 10.0, places=1)
        self.assertAlmostEqual(ex["mae_pct"], 2.0, places=1)
        self.assertAlmostEqual(ex["ideal_entry_offset_pct"], 2.0, places=1)

    def test_excursion_aggregate_and_entry_offset(self):
        trades = [_trade("AAA/USDT:USDT", "LONG", "trend", "momentum", 5.0, entry=100.0, qty=1.0)
                  for _ in range(8)]
        for t in trades:
            t["mfe"] = 10.0
            t["mae"] = 3.0
        self._write_journal(trades)
        pm.build_excursion_aggregates("CRYPTO")
        off = pm.entry_offset("AAA/USDT:USDT", "trend", "CRYPTO")
        self.assertGreaterEqual(off.get("n", 0), 5)
        self.assertAlmostEqual(off["offset_pct"], 3.0, places=1)


class TestSignalAndExplain(PostmortemBase):
    def setUp(self):
        super().setUp()
        trades = []
        for i in range(80):
            trades.append(_trade(f"C{i%8}/USDT:USDT", "LONG", "trend", "momentum", 10.0))
        for i in range(80):
            trades.append(_trade(f"C{i%8}/USDT:USDT", "SHORT", "range", "reversal", -8.0))
        self._write_journal(trades)
        pm.mine_patterns("CRYPTO")

    def test_pattern_signal_prefers_winning_context(self):
        good = pm.pattern_signal({"direction": "LONG", "regime": "trend",
                                  "filter_preset": "momentum"}, "CRYPTO", "trend")
        self.assertFalse(good["abstained"])
        self.assertGreater(good["p_up"], 0.5)               # winning context → bullish on the trade
        self.assertGreaterEqual(good["size_mult"], 1.0)

    def test_pattern_signal_flags_losing_context(self):
        bad = pm.pattern_signal({"direction": "SHORT", "regime": "range",
                                 "filter_preset": "reversal"}, "CRYPTO", "range")
        self.assertFalse(bad["abstained"])
        self.assertLessEqual(bad["size_mult"], 1.0)         # losing context → do not upsize

    def test_pattern_signal_abstains_when_no_rule_matches(self):
        out = pm.pattern_signal({"direction": "LONG", "regime": "nonexistent_regime_xyz"},
                                "CRYPTO", "xyz")
        self.assertTrue(out["abstained"])
        self.assertIsNone(out["p_up"])
        self.assertEqual(out["size_mult"], 1.0)

    def test_explain_trade(self):
        t = _trade("C1/USDT:USDT", "SHORT", "range", "reversal", -8.0)
        ex = pm.explain_trade(t)
        self.assertFalse(ex["won"])
        self.assertTrue(ex["reasons"])
        self.assertIn("market", ex)
        self.assertEqual(ex["market"], "CRYPTO")


class TestGracefulFallback(PostmortemBase):
    def test_commonality_only_when_pysubgroup_absent(self):
        # simulate pysubgroup missing → _discover returns [] → status still has commonality
        trades = [_trade(f"C{i%8}/USDT:USDT", "LONG", "trend", "momentum", 10.0) for i in range(50)]
        trades += [_trade(f"C{i%8}/USDT:USDT", "SHORT", "range", "reversal", -8.0) for i in range(50)]
        self._write_journal(trades)
        orig = pm._discover
        pm._discover = lambda *a, **k: []
        try:
            pm.mine_patterns("CRYPTO")
        finally:
            pm._discover = orig
        st = pm.status("CRYPTO")["markets"]["CRYPTO"]
        self.assertEqual(st["method"], "commonality")
        self.assertGreater(len(st["commonality"]), 0)       # the pure-pandas table always works


if __name__ == "__main__":
    unittest.main()
