"""Tests for trading/brain/memory_search.py — FTS5 full-text memory search (offline, isolated).

STATE_DIR is redirected to a temp dir with fixture corpora so the live memory is never touched;
the agent-md / skill-learnings dirs are pointed at temp dirs too.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import trading.state as state
from trading.brain import memory_search as ms


class TestMemorySearch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        # fixture corpora across several sources
        (state.STATE_DIR / "associative_notes.json").write_text(json.dumps({"notes": [
            {"id": "n1", "title": "Funding arbitrage", "content": "perpetual funding rate carry",
             "keywords": ["funding", "carry"], "tags": ["crypto"], "created": 1.0},
            {"id": "n2", "title": "Regime", "content": "ADX supertrend trend detection", "created": 2.0},
        ]}))
        (state.STATE_DIR / "decision_episodes.json").write_text(json.dumps({"episodes": [
            {"episode_id": "e1", "symbol": "BTC", "direction": "long", "engine": "brain",
             "reflection": "entered on supertrend flip with strong ADX", "ts": 3.0},
        ]}))
        (state.STATE_DIR / "gui_reflections.json").write_text(json.dumps({"lessons": [
            {"task": "widen stop", "lesson": "trailing stop too tight caused early exit",
             "detail": "ATR based", "outcome": "win", "ts": 4.0},
        ]}))
        self._md = tempfile.TemporaryDirectory()
        self._skills = tempfile.TemporaryDirectory()
        (Path(self._md.name) / "note.md").write_text("# note\nliquidation heatmap idea")
        skdir = Path(self._skills.name) / "commit-safe"
        skdir.mkdir()
        (skdir / "LEARNINGS.md").write_text("# Learnings\n## x\n**Worked:** secret scan clean")
        self._omd, self._osk = ms._MEMORY_MD_DIR, ms._SKILLS_DIR
        ms._MEMORY_MD_DIR = Path(self._md.name)
        ms._SKILLS_DIR = Path(self._skills.name)
        self.s = ms.MemorySearch()

    def tearDown(self):
        state.STATE_DIR = self._old
        ms._MEMORY_MD_DIR, ms._SKILLS_DIR = self._omd, self._osk
        for t in (self._tmp, self._md, self._skills):
            t.cleanup()

    def test_reindex_counts_all_sources(self):
        rep = self.s.reindex(force=True)
        self.assertFalse(rep["reused"])
        self.assertGreaterEqual(rep["indexed"], 6)     # 2 notes + 1 ep + 1 lesson + 1 md + 1 skill
        srcs = rep["sources"]
        for k in ("associative", "episode", "reflection", "memory_md", "skill_learning"):
            self.assertIn(k, srcs)

    def test_search_finds_across_sources(self):
        hits = self.s.search("supertrend", k=10)
        found = {h["source"] for h in hits}
        self.assertTrue({"associative", "episode"} & found)   # both mention supertrend
        self.assertTrue(all("score" in h and "snippet" in h for h in hits))

    def test_search_specific_source_filter(self):
        hits = self.s.search("funding", sources=["associative"])
        self.assertTrue(hits)
        self.assertTrue(all(h["source"] == "associative" for h in hits))

    def test_skill_learning_indexed(self):
        hits = self.s.search("secret scan clean")
        self.assertTrue(any(h["source"] == "skill_learning" for h in hits))

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.s.search(""), [])
        self.assertEqual(self.s.search("   "), [])

    def test_no_match_is_honest_empty(self):
        self.assertEqual(self.s.search("zzznonexistenttermzzz"), [])

    def test_reindex_reused_when_unchanged(self):
        self.s.reindex(force=True)
        rep = self.s.reindex()                          # nothing changed → reuse
        self.assertTrue(rep.get("reused"))

    def test_dedup_no_duplicate_refs(self):
        # duplicate the same note text; results must collapse by (source, ref)
        d = json.loads((state.STATE_DIR / "associative_notes.json").read_text())
        d["notes"].append(dict(d["notes"][0]))          # same id n1 → same ref
        (state.STATE_DIR / "associative_notes.json").write_text(json.dumps(d))
        hits = self.s.search("funding carry", k=10)
        refs = [(h["source"], h["ref"]) for h in hits]
        self.assertEqual(len(refs), len(set(refs)))


if __name__ == "__main__":
    unittest.main()
