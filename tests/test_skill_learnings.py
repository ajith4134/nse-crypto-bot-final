"""Tests for tools/skill_learnings.py — the self-improving-skills learning loop (isolated tmp dir)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import skill_learnings as sl


class TestSkillLearnings(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = sl.SKILLS_DIR
        sl.SKILLS_DIR = Path(self._tmp.name)
        (sl.SKILLS_DIR / "demo-skill").mkdir()          # a real skill dir

    def tearDown(self):
        sl.SKILLS_DIR = self._old
        self._tmp.cleanup()

    def test_record_then_read(self):
        r = sl.record("demo-skill", worked="did X", failed="missed Y", edge="empty input",
                      note="remember Z", score=0.8)
        self.assertTrue(r["ok"])
        self.assertEqual(r["entries"], 1)
        text = sl.read("demo-skill")
        for frag in ("did X", "missed Y", "empty input", "remember Z", "eval 0.8"):
            self.assertIn(frag, text)

    def test_read_empty_when_none(self):
        self.assertEqual(sl.read("demo-skill"), "")

    def test_record_rejects_empty_lesson(self):
        self.assertFalse(sl.record("demo-skill")["ok"])

    def test_record_rejects_unknown_skill(self):
        self.assertFalse(sl.record("no-such-skill", note="x")["ok"])

    def test_multiple_entries_accumulate(self):
        sl.record("demo-skill", note="first")
        sl.record("demo-skill", note="second")
        self.assertEqual(sl._count_entries(sl.read("demo-skill")), 2)

    def test_status_reports_counts(self):
        sl.record("demo-skill", note="a")
        st = sl.status()
        self.assertEqual(st["skills_with_learnings"], 1)
        self.assertEqual(st["total_lessons"], 1)
        self.assertEqual(st["by_skill"]["demo-skill"], 1)

    def test_cap_keeps_recent(self):
        for i in range(50):
            sl.record("demo-skill", note=("padding " * 200) + f"entry{i}")
        text = sl.read("demo-skill")
        self.assertLessEqual(len(text), sl._MAX_BYTES + 2000)
        self.assertIn("entry49", text)                  # newest kept


if __name__ == "__main__":
    unittest.main()
