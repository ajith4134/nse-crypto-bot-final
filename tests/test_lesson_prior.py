"""Tests for trading/direction/lesson_prior.py (E4 — lessons → measured direction lens)."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        os.environ.pop("LESSON_PRIOR", None)

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()


def _seed_lessons(lessons_by_symbol):
    from trading.brain import lesson_recall as lr
    lr._SEEDED = True
    with lr._LOCK:
        lr._LESSONS.clear()
        lr._LESSONS.update({k: list(v) for k, v in lessons_by_symbol.items()})


class TestDistill(_Base):
    def test_distills_llm_json_into_table(self):
        from trading import state
        from trading.direction import lesson_prior as lp
        _seed_lessons({"AKEUSDT": ["Shorts keep getting squeezed here; wait for longs."],
                       "TAOUSDT": ["Sizing was too big; nothing directional."]})
        reply = json.dumps({"AKEUSDT": {"side": "long", "confidence": 0.8, "why": "squeeze"},
                            "TAOUSDT": {"side": "none", "confidence": 0.0, "why": "sizing"}})
        with mock.patch("core.llm.chat", return_value=reply):
            out = lp.distill()
        self.assertEqual(out["distilled"], 2)
        table = state.load_json("lesson_prior.json", {})
        self.assertAlmostEqual(table["AKEUSDT"]["p_up"], 0.66)   # 0.5 + 0.2*0.8
        self.assertEqual(table["TAOUSDT"]["p_up"], 0.5)          # none → abstain later

    def test_unchanged_lessons_skip_llm(self):
        from trading.direction import lesson_prior as lp
        _seed_lessons({"AKEUSDT": ["lesson one"]})
        reply = json.dumps({"AKEUSDT": {"side": "short", "confidence": 0.5, "why": "x"}})
        with mock.patch("core.llm.chat", return_value=reply) as ch:
            lp.distill()
            out2 = lp.distill()
        self.assertEqual(ch.call_count, 1)                       # hash-guarded
        self.assertEqual(out2.get("reason"), "all up to date")

    def test_llm_failure_is_honest(self):
        from trading.direction import lesson_prior as lp
        _seed_lessons({"AKEUSDT": ["l"]})
        with mock.patch("core.llm.chat", side_effect=RuntimeError("no provider")):
            out = lp.distill()
        self.assertEqual(out["distilled"], 0)
        self.assertIn("llm", out["error"])


class TestReadings(_Base):
    def _table(self, p_up, ts=None):
        from trading import state
        state.save_json("lesson_prior.json",
                        {"AKEUSDT": {"p_up": p_up, "side": "long", "confidence": 0.8,
                                     "lesson_hash": "x", "ts": ts or time.time()}})

    def test_reading_emitted_and_recorded(self):
        from trading.direction import lesson_prior as lp
        self._table(0.66)
        with mock.patch("trading.direction.truth_ledger.record") as rec:
            reads = lp.readings("AKE/USDT:USDT", regime="chop")
        self.assertEqual(reads, [("lessons", 0.66)])
        self.assertEqual(rec.call_args.kwargs["source"], "lessons")

    def test_stale_row_abstains(self):
        from trading.direction import lesson_prior as lp
        self._table(0.66, ts=time.time() - 2 * 86400)
        self.assertEqual(lp.readings("AKEUSDT"), [])

    def test_no_lean_abstains(self):
        from trading.direction import lesson_prior as lp
        self._table(0.5)
        self.assertEqual(lp.readings("AKEUSDT"), [])

    def test_disabled_flag(self):
        from trading.direction import lesson_prior as lp
        os.environ["LESSON_PRIOR"] = "0"
        try:
            self._table(0.66)
            self.assertEqual(lp.readings("AKEUSDT"), [])
        finally:
            os.environ.pop("LESSON_PRIOR", None)


if __name__ == "__main__":
    unittest.main()
