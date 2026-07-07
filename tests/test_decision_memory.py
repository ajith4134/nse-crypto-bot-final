"""Decision-memory subsystem (trading/brain/decision_memory.py + attribution.py) and the
closed-view P&L / brain-column fixes in freqtrade_ingest. State ALWAYS isolated to a temp
dir (never the live journal/episode store)."""
import datetime as dt
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp())
        # the module-level singleton must not leak episodes across tests / into live state
        import trading.brain.decision_memory as dm
        dm._SINGLETON = None

    def tearDown(self):
        state.STATE_DIR = self._old
        import trading.brain.decision_memory as dm
        dm._SINGLETON = None


class TestDecisionMemory(_IsolatedState):
    def _mem(self):
        from trading.brain.decision_memory import DecisionMemory
        return DecisionMemory()

    def test_open_resolve_reflection_and_feedback(self):
        m = self._mem()
        eid = m.open_episode(symbol="BTC/USDT", market="CRYPTO", segment="futures",
                             direction="LONG", entry_price=100.0, strategy="trend_macd",
                             decision_snapshot={"brain": {"confidence": 0.7}},
                             attribution={"top": [{"feature": "psych_obi", "value": 0.5,
                                                   "impact": 0.12}]})
        ep = m.find(episode_id=eid)
        self.assertTrue(ep["pending"])
        imp0 = ep["importance"]
        out = m.resolve(episode_id=eid, net_pnl=25.0, r_multiple=2.5,
                        exit_price=110.0, exit_reason="roi", brain_correct=True,
                        use_llm=False)
        self.assertFalse(out["pending"])
        self.assertGreater(out["importance"], imp0)          # FinMem positive feedback
        self.assertIn("psych_obi", out["reflection"])         # attribution cited in lesson
        self.assertIn("correct", out["reflection"])
        # idempotent under polling (ingest re-calls resolve every 30s)
        again = m.resolve(episode_id=eid, net_pnl=-999, use_llm=False)
        self.assertEqual(again["outcome"]["net_pnl"], 25.0)

    def test_loss_demotes_and_layer_jumps(self):
        m = self._mem()
        eid = m.open_episode(symbol="ETH/USDT", direction="SHORT", entry_price=50.0)
        ep = m.find(episode_id=eid)
        ep["importance"] = 74.0                # one good outcome from the promote line
        m.resolve(episode_id=eid, net_pnl=10.0, r_multiple=1.0, use_llm=False)
        self.assertEqual(ep["layer"], "mid")   # FinMem jump: importance >= 75 → mid
        # losses drain importance
        eid2 = m.open_episode(symbol="ETH/USDT", direction="SHORT", entry_price=50.0)
        ep2 = m.find(episode_id=eid2)
        imp = ep2["importance"]
        m.resolve(episode_id=eid2, net_pnl=-10.0, r_multiple=-2.0, use_llm=False)
        self.assertLess(ep2["importance"], imp)

    def test_decay_step_and_cleanup(self):
        m = self._mem()
        eid = m.open_episode(symbol="DOGE/USDT", direction="LONG", entry_price=0.1)
        m.resolve(episode_id=eid, net_pnl=-1.0, r_multiple=-0.5, use_llm=False)
        ep = m.find(episode_id=eid)
        ep["importance"] = 3.0                 # nearly forgotten already
        for _ in range(200):                   # decay far past the shallow half-life
            m.step(force=True)
        self.assertIsNone(m.find(episode_id=eid))   # cleaned up (shallow + faded)

    def test_recall_and_bias(self):
        m = self._mem()
        for i, pnl in enumerate([5.0, 7.0, -2.0, 4.0]):
            eid = m.open_episode(symbol="BTC/USDT", direction="LONG",
                                 entry_price=100.0 + i, strategy="meanrev")
            m.resolve(episode_id=eid, net_pnl=pnl, r_multiple=pnl / 5, use_llm=False)
        hits = m.recall(symbol="BTC/USDT", query="meanrev", k=3)
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0]["symbol"], "BTC/USDT")
        b = m.bias("BTC/USDT", "LONG")
        self.assertEqual(b["n"], 4)
        self.assertGreater(b["bias"], 0)       # 3 wins / 1 loss → positive bias
        ctx = m.past_context("BTC/USDT")
        self.assertIn("BTC/USDT", ctx)

    def test_persistence_roundtrip(self):
        m = self._mem()
        m.open_episode(symbol="SOL/USDT", direction="LONG", entry_price=20.0)
        m2 = self._mem()                        # fresh instance, same temp STATE_DIR
        self.assertEqual(len(m2.episodes), 1)
        self.assertEqual(m2.episodes[0]["symbol"], "SOL/USDT")


class TestAttribution(_IsolatedState):
    def test_untrained_and_trained_paths(self):
        from trading.brain import trade_features
        from trading.brain.attribution import explain_trade
        trade_features._NET_CACHE = getattr(trade_features, "_NET_CACHE", None) and None
        trade = {"symbol": "BTC/USDT", "direction": "LONG", "exchange": "binance",
                 "quantity": 1.0, "brain_confidence_entry": 0.7}
        self.assertEqual(explain_trade(trade, [])["engine"], "untrained")
        closed = [{"symbol": "BTC/USDT", "direction": "LONG" if i % 2 else "SHORT",
                   "exchange": "binance", "quantity": 1.0, "leverage": 2.0,
                   "brain_confidence_entry": 0.4 + (i % 5) / 10,
                   "net_pnl": 1.0 if i % 3 else -1.0} for i in range(40)]
        out = explain_trade(trade, closed)
        if out["engine"] != "untrained":        # tiny sets may legitimately not train
            self.assertIn(out["engine"], ("shap-kernel", "occlusion"))
            self.assertIsInstance(out["top"], list)
            self.assertIsNotNone(out["p_win"])


class TestFreqtradeIngestFixes(_IsolatedState):
    FT = {"trade_id": 9, "pair": "BTC/USDT:USDT", "is_short": False, "open_rate": 100.0,
          "close_rate": 110.0, "amount": 2.0, "trading_mode": "futures",
          "profit_abs": 19.6, "profit_ratio": 0.098, "fee_open_cost": 0.2,
          "fee_close_cost": 0.22, "funding_fees": -0.05, "stake_amount": 40.0,
          "leverage": 5.0, "initial_stop_loss_abs": 95.0, "max_rate": 112.0,
          "min_rate": 99.0, "open_date": "", "close_date": "2026-07-03 09:00:00",
          "enter_tag": "trend_macd", "exit_reason": "roi", "exchange": "binance"}

    def test_closed_view_pnl_carried(self):
        """Root cause 2 regression: NET_PNL/TOTAL_CHARGES must NOT be schema-default 0."""
        from trading.crypto.freqtrade_ingest import map_trade
        t = map_trade(dict(self.FT, open_date="2026-07-03 08:00:00"))
        self.assertEqual(t.net_pnl, 19.6)
        self.assertEqual(t.total_charges, 0.42)
        self.assertAlmostEqual(t.gross_pnl, 20.02)
        self.assertEqual(t.net_pnl_pct, 9.8)
        self.assertEqual(t.r_multiple, 1.96)
        self.assertEqual(t.signal_source, "freqtrade")

    def test_brain_columns_from_sidecar(self):
        """Root cause 4 regression: sidecar brain meta → BRAIN_* columns + episode resolve."""
        from trading.brain.decision_memory import get_memory
        from trading.crypto.freqtrade import entry_meta
        from trading.crypto.freqtrade_ingest import map_trade
        eid = get_memory().open_episode(symbol="BTC/USDT:USDT", market="CRYPTO",
                                        segment="futures", direction="LONG",
                                        entry_price=100.0, engine="freqtrade")
        entry_meta.record("BTC/USDT:USDT", "futures", {
            "psychology": None, "episode_id": eid,
            "feature_attribution": {"engine": "occlusion", "top": []},
            "decision_snapshot": {"direction": "LONG",
                                  "brain": {"confidence": 0.66, "action": "LONG",
                                            "regime": "Trending"}}})
        open_date = dt.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        t = map_trade(dict(self.FT, open_date=open_date))
        self.assertEqual(t.signal_source, "brain")
        self.assertEqual(t.brain_confidence_entry, 0.66)
        self.assertEqual(t.brain_prediction, "UP")
        self.assertTrue(t.brain_correct)                   # LONG, closed higher
        self.assertEqual(t.market_regime_entry, "Trending")
        self.assertEqual(t.episode_id, eid)
        ep = get_memory().find(episode_id=eid)
        self.assertFalse(ep["pending"])                    # resolved by ingest
        self.assertEqual(ep["outcome"]["net_pnl"], 19.6)
        self.assertTrue(t.exit_reflection)


if __name__ == "__main__":
    unittest.main()
