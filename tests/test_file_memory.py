"""Tests for memory/file_memory.py — Claude-style durable file memory (Phase B)."""
from memory.associative import AssociativeMemory
from memory.file_memory import FileMemory


def test_write_creates_note_and_index(tmp_path):
    fm = FileMemory(tmp_path)
    out = fm.write("Funding Spike Lesson!", "funding spikes precede crashes",
                   "Bitcoin funding rates spiked before the crash. See [[leverage-risk]].",
                   type="lesson")
    assert out["name"] == "funding-spike-lesson"
    note = fm.get("funding-spike-lesson")
    assert note["type"] == "lesson" and note["links"] == ["leverage-risk"]
    idx = (tmp_path / "MEMORY.md").read_text()
    assert "(funding-spike-lesson.md)" in idx
    # rewrite same name → updated in place, single index line
    fm.write("funding spike lesson", "updated desc", "new body", type="lesson")
    idx = (tmp_path / "MEMORY.md").read_text()
    assert idx.count("funding-spike-lesson.md") == 1


def test_persists_across_processes_and_recalls(tmp_path):
    fm = FileMemory(tmp_path, associative=AssociativeMemory())
    fm.write("btc-funding", "funding lesson",
             "Bitcoin funding rates spiked before the perpetual futures crash on binance")
    fm.write("nse-breakout", "nse lesson",
             "Low volume NSE smallcap breakouts fail after 2pm")
    # fresh instance = new process; notes reload from disk into a fresh associative index
    fm2 = FileMemory(tmp_path, associative=AssociativeMemory())
    assert fm2.status()["notes"] == 2
    hits = fm2.recall("bitcoin perpetual futures leverage", k=2)
    assert hits and hits[0]["title"] == "btc-funding"


def test_keyword_fallback_without_associative(tmp_path):
    fm = FileMemory(tmp_path)
    fm.write("btc-funding", "funding", "bitcoin funding rates and leverage")
    hits = fm.recall("bitcoin leverage", k=2)
    assert hits and hits[0]["via"] == "file-memory(keyword)"
