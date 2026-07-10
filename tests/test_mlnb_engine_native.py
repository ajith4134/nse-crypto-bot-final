"""Tests for the fork's brain-native layer (E-workstreams 2026-07-10):
mlnb_sidecar enrichment (E2), decision inbox consumption (E3), in-engine tailgate
custom_exit (E1). All against a temp state dir — never the live trading/state."""
import json
import tempfile
import time
import unittest
from pathlib import Path


class _TmpState(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.state = Path(self._t.name)
        self.config = {"mlnb_state_dir": str(self.state)}
        # the sidecar caches by (path, mtime); a fresh tmp dir isolates naturally

    def tearDown(self):
        self._t.cleanup()

    def _write(self, name, obj):
        (self.state / name).write_text(json.dumps(obj))


class TestSidecarEnrich(_TmpState):
    def test_native_fields_from_locks_and_entry_meta(self):
        from freqtrade.rpc.api_server.mlnb_sidecar import enrich_trades
        now = time.time()
        self._write("profit_tailgate_locks.json",
                    {"42": {"locked": 2.5, "peak": 4.0, "dist": 0.3}})
        self._write("crypto_entry_meta.json",
                    {"futures|KAT/USDT:USDT": [{"ts": now, "meta": {
                        "strategy": "lib_TrendSupertrend", "direction": "LONG",
                        "brain": {"confidence": 0.72}}}]})
        rows = [{"trade_id": 42, "pair": "KAT/USDT:USDT", "bot_segment": "futures",
                 "is_open": True, "open_timestamp": int(now * 1000), "enter_tag": "x"}]
        enrich_trades(rows, self.config)
        self.assertEqual(rows[0]["tg_locked_pct"], 2.5)
        self.assertEqual(rows[0]["tg_peak_pct"], 4.0)
        self.assertEqual(rows[0]["strategy_label"], "lib_TrendSupertrend")
        self.assertEqual(rows[0]["brain_pred"], "LONG 0.72")

    def test_missing_sidecars_yield_none_never_fabricated(self):
        from freqtrade.rpc.api_server.mlnb_sidecar import enrich_trades
        rows = [{"trade_id": 7, "pair": "BTC/USDT:USDT", "bot_segment": "futures",
                 "is_open": True, "open_timestamp": 0, "enter_tag": None}]
        enrich_trades(rows, self.config)
        self.assertIsNone(rows[0]["tg_locked_pct"])
        self.assertIsNone(rows[0]["brain_pred"])

    def test_closed_trade_gets_no_lock(self):
        from freqtrade.rpc.api_server.mlnb_sidecar import enrich_trades
        self._write("profit_tailgate_locks.json", {"42": {"locked": 2.5, "peak": 4.0}})
        rows = [{"trade_id": 42, "pair": "KAT/USDT:USDT", "bot_segment": "futures",
                 "is_open": False, "open_timestamp": 0}]
        enrich_trades(rows, self.config)
        self.assertIsNone(rows[0]["tg_locked_pct"])   # locks are open-trade state only


class TestDecisionInbox(_TmpState):
    class _Bot:
        def __init__(self, config):
            self.config = config

    def _inbox_write(self, recs):
        with (self.state / "decisions_inbox.jsonl").open("a") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    def test_consume_executes_own_segment_only_and_advances_cursor(self):
        from freqtrade import mlnb_inbox
        executed = []
        orig = mlnb_inbox._execute
        mlnb_inbox._execute = lambda bot, rec: executed.append(rec["id"])
        try:
            now = time.time()
            self._inbox_write([
                {"id": "a", "segment": "futures", "action": "enter", "pair": "X/USDT", "ts": now},
                {"id": "b", "segment": "spot", "action": "enter", "pair": "Y/USDT", "ts": now},
                {"id": "c", "segment": "futures", "action": "enter", "pair": "Z/USDT",
                 "ts": now - 9999},                                   # stale → skipped
            ])
            bot = self._Bot({"mlnb_state_dir": str(self.state), "mlnb_segment": "futures"})
            n = mlnb_inbox.consume(bot)
            self.assertEqual(n, 1)
            self.assertEqual(executed, ["a"])
            # cursor advanced: nothing re-executes on the next pass
            self.assertEqual(mlnb_inbox.consume(bot), 0)
            self.assertEqual(executed, ["a"])
        finally:
            mlnb_inbox._execute = orig

    def test_engine_client_inbox_append_shape(self):
        import os
        import trading.state as tstate
        orig_dir = tstate.STATE_DIR
        tstate.STATE_DIR = self.state
        os.environ["CRYPTO_DECISION_INBOX"] = "1"
        try:
            from trading.crypto.engine_client import _inbox_append, _inbox_enabled
            self.assertTrue(_inbox_enabled())
            res = _inbox_append({"action": "enter", "pair": "BTC/USDT:USDT",
                                 "segment": "futures", "side": "long"})
            self.assertTrue(res["queued"])
            line = (self.state / "decisions_inbox.jsonl").read_text().strip()
            rec = json.loads(line)
            self.assertEqual(rec["action"], "enter")
            self.assertIn("ts", rec)
            self.assertIn("id", rec)
        finally:
            os.environ.pop("CRYPTO_DECISION_INBOX", None)
            tstate.STATE_DIR = orig_dir


class TestInEngineTailgate(_TmpState):
    def _strategy(self):
        import importlib.util
        path = ("/home/karan18190164/trading/crypto/freqtrade/user_data/strategies/"
                "MlBridgeStrategy.py")
        spec = importlib.util.spec_from_file_location("MlBridgeStrategy_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.MlBridgeStrategy(self.config)

    class _Trade:
        id = 42

    def test_custom_exit_fires_at_or_below_lock_any_sign(self):
        self._write("profit_tailgate_locks.json", {"42": {"locked": 2.5, "peak": 4.0}})
        strat = self._strategy()
        # above the lock → ride
        self.assertIsNone(strat.custom_exit("KAT/USDT:USDT", self._Trade(), None, 100.0, 0.031))
        # at/below the lock → exit, even deep negative (gap-through-lock regression)
        self.assertEqual(
            strat.custom_exit("KAT/USDT:USDT", self._Trade(), None, 100.0, 0.020),
            "tailgate_lock")
        self.assertEqual(
            strat.custom_exit("KAT/USDT:USDT", self._Trade(), None, 100.0, -0.027),
            "tailgate_lock")

    def test_custom_exit_silent_without_lock_or_with_killswitch(self):
        strat = self._strategy()
        self.assertIsNone(strat.custom_exit("BTC/USDT:USDT", self._Trade(), None, 100.0, -0.05))
        self._write("profit_tailgate_locks.json", {"42": {"locked": 2.5, "peak": 4.0}})
        strat.config["mlnb_tailgate_enforce"] = False
        self.assertIsNone(strat.custom_exit("KAT/USDT:USDT", self._Trade(), None, 100.0, 0.01))


if __name__ == "__main__":
    unittest.main()
