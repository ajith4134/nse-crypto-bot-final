"""Boss command engine (trading/brain/boss.py) + mind-event bus (mind_events.py) + R&D drive
(rnd.py). State ALWAYS isolated to a temp dir; every engine side-effect (Freqtrade restart,
NSE controls) is stubbed — tests never touch the live bot or .env."""
import tempfile
import unittest
from pathlib import Path

import trading.state as state


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp())
        import trading.brain.boss as boss
        # neuter background engine pushes (set_params/set_segments_enabled restart the bot)
        self._old_bg = boss._bg
        boss._bg = lambda *a, **k: None
        boss._last_progress.clear()

    def tearDown(self):
        import trading.brain.boss as boss
        boss._bg = self._old_bg
        state.STATE_DIR = self._old


class TestMindEvents(_IsolatedState):
    def test_emit_since_peek_status(self):
        from trading.brain import mind_events as me
        e1 = me.emit("discovery", "found an edge", salience=0.9)
        e2 = me.emit("problem", "gate blocked entries", detail="uq abstained")
        self.assertEqual(e1["kind"], "discovery")
        self.assertGreater(e2["id"], e1["id"])
        newer = me.since(e1["id"])
        self.assertEqual([x["id"] for x in newer], [e2["id"]])
        self.assertEqual(me.peek(10)[0]["id"], e2["id"])          # newest first
        st = me.status()
        self.assertEqual(st["n"], 2)
        self.assertEqual(st["by_kind"]["problem"], 1)

    def test_unknown_kind_coerced(self):
        from trading.brain import mind_events as me
        self.assertEqual(me.emit("nonsense", "x")["kind"], "thought")


class TestDeterministicParser(_IsolatedState):
    def parse(self, msg):
        from trading.brain import boss
        return boss.parse_deterministic(msg)

    def test_open_n_trades_crypto_futures(self):
        calls = self.parse("open atleast 50 open trades in crypto futures")
        tgt = [c for c in calls if c["tool"] == "set_target_open_trades"]
        self.assertTrue(tgt)
        self.assertEqual(tgt[0]["args"], {"market": "CRYPTO", "segment": "futures",
                                          "target": 50})

    def test_segment_on_off(self):
        calls = self.parse("turn off spot and enable options")
        tools = {(c["tool"], tuple(c["args"].get("disable", []) or c["args"].get("enable", [])))
                 for c in calls}
        self.assertIn(("set_segments", ("spot",)), tools)
        self.assertIn(("set_segments", ("options",)), tools)

    def test_focus_and_modes(self):
        calls = self.parse("focus more on options and try to be more profitable")
        self.assertIn({"tool": "focus_segment", "args": {"market": "CRYPTO",
                                                         "segment": "options"}}, calls)
        self.assertIn({"tool": "set_mode", "args": {"mode": "profit"}}, calls)

    def test_data_collect_mode(self):
        calls = self.parse("collect more data by doing more trades")
        self.assertIn({"tool": "set_mode", "args": {"mode": "data_collect"}}, calls)

    def test_balanced_mode(self):
        calls = self.parse("set mode balanced")
        self.assertIn({"tool": "set_mode", "args": {"mode": "balanced"}}, calls)

    def test_nse_market_detected(self):
        calls = self.parse("open at least 10 trades in NSE equity")
        tgt = [c for c in calls if c["tool"] == "set_target_open_trades"][0]
        self.assertEqual(tgt["args"]["market"], "NSE")
        self.assertEqual(tgt["args"]["segment"], "equity")


class TestDirectivesAndPolicy(_IsolatedState):
    def test_handle_executes_and_persists(self):
        from trading.brain import boss, mind_events
        out = boss.handle("open at least 50 trades in crypto futures")
        self.assertIsNotNone(out)
        self.assertIn("Yes boss", out["reply"])
        self.assertTrue(any(a["result"].get("ok") for a in out["actions"]))
        self.assertEqual(boss.target_for("CRYPTO", "futures"), 50)
        kinds = {e["kind"] for e in mind_events.peek(20)}
        self.assertIn("boss", kinds)
        self.assertTrue(boss.directives()["history"])

    def test_non_command_falls_through(self):
        from trading.brain import boss
        self.assertIsNone(boss.handle("what is a hypothesis ledger?"))

    def test_entry_policy_pressure_relaxes_gates(self):
        from trading.brain import boss
        boss.set_target_open_trades("CRYPTO", "futures", 50)
        p = boss.entry_policy("CRYPTO", "futures", open_now=10)
        self.assertTrue(p["pressure"] and p["uq_advisory"])
        self.assertGreater(p["psych_veto"], 0.6)
        p2 = boss.entry_policy("CRYPTO", "futures", open_now=50)
        self.assertFalse(p2["pressure"])

    def test_profit_mode_keeps_gates_hard(self):
        from trading.brain import boss
        boss.set_mode("profit")
        boss.set_target_open_trades("CRYPTO", "futures", 50)
        p = boss.entry_policy("CRYPTO", "futures", open_now=1)
        self.assertFalse(p["uq_advisory"])       # profit mode never bypasses UQ
        self.assertEqual(p["psych_veto"], 0.5)

    def test_pause_focus_intensity_segments(self):
        from trading.brain import boss
        boss.pause_trading("CRYPTO")
        self.assertTrue(boss.is_paused("CRYPTO"))
        boss.resume_trading("CRYPTO")
        self.assertFalse(boss.is_paused("CRYPTO"))
        boss.focus_segment("CRYPTO", "options")
        self.assertEqual(boss.focus_of("CRYPTO"), "options")
        boss.set_intensity(9)                     # clamped
        self.assertEqual(boss.intensity(), 4.0)
        boss.set_segments("CRYPTO", disable=["spot"])
        self.assertIs(boss.segment_enabled("CRYPTO", "spot"), False)
        self.assertIsNone(boss.segment_enabled("CRYPTO", "futures"))

    def test_goals_and_progress_event(self):
        from trading.brain import boss, mind_events
        r = boss.add_goal("grow the paper book learning rate")
        self.assertTrue(r["ok"])
        boss.set_target_open_trades("CRYPTO", "futures", 5)
        boss.report_progress("CRYPTO", "futures", 3)
        evs = [e for e in mind_events.peek(20) if e["kind"] == "directive"]
        self.assertTrue(evs and "3/5" in evs[0]["text"])


class TestRnd(_IsolatedState):
    def test_run_once_with_stubbed_research(self):
        import trading.brain.researcher as researcher
        from trading.brain import mind_events, rnd

        class _Stub:
            def research(self, q):
                return {"query": q, "n_sources": 2, "available": True, "llm_used": False,
                        "summary": "digest about volatility regimes", "sources": []}
        old = researcher.AutonomousResearcher
        old_invent = rnd._invent_from
        researcher.AutonomousResearcher = _Stub
        rnd._invent_from = lambda topic, summary: {          # no live LLM in tests
            "feature_name": "vol_regime_filter",
            "description": "gate entries by a volatility regime flag",
            "hypothesis": {"field": "market_regime_entry", "op": "==", "value": "trend",
                           "statement": "trades in trend regime have higher r_multiple"}}
        try:
            out = rnd.run_once()
        finally:
            researcher.AutonomousResearcher = old
            rnd._invent_from = old_invent
        self.assertTrue(out["ok"])
        self.assertTrue(out["hypothesis_seeded"])
        self.assertEqual(rnd.status()["n_inventions"], 1)
        self.assertTrue(any(e["kind"] == "invention" for e in mind_events.peek(20)))
        from trading.brain.hypothesis import HypothesisLedger
        led = HypothesisLedger(persist=True)
        self.assertIn(out["hid"], led.hypotheses)

    def test_maybe_run_disabled(self):
        import os
        from trading.brain import rnd
        os.environ["RND_LOOP"] = "0"
        try:
            self.assertIsNone(rnd.maybe_run())
        finally:
            os.environ.pop("RND_LOOP", None)


class TestChatRouting(_IsolatedState):
    def test_chat_routes_commands_to_boss(self):
        from core import chat_brain
        out = chat_brain.chat("turn off crypto spot segment")
        self.assertIsNone(out["error"])
        self.assertIn("Yes boss", out["reply"])

    def test_chat_stream_routes_commands(self):
        from core import chat_brain
        evs = list(chat_brain.chat_stream("focus on futures"))
        types = [e["type"] for e in evs]
        self.assertIn("token", types)
        self.assertEqual(types[-1], "done")
        joined = "".join(e.get("text", "") for e in evs if e["type"] == "token")
        self.assertIn("Yes boss", joined)


if __name__ == "__main__":
    unittest.main()
