"""Tests for trading/brain/perception.py + researcher.deep_research (Phase D, offline)."""
from memory.associative import AssociativeMemory
from trading.brain.perception import read_any, status
from trading.brain.researcher import AutonomousResearcher


def test_read_any_plain_and_csv(tmp_path):
    md = tmp_path / "report.md"
    md.write_text("# Funding report\nBitcoin funding rates spiked before the crash.")
    out = read_any(md)
    assert out["ok"] and "funding rates" in out["text"].lower()
    assert out["engine"] in {"plain", "docling"}

    csv = tmp_path / "trades.csv"
    csv.write_text("pair,pnl\nBTC/USDT,12.5\nETH/USDT,-3.1\n")
    out = read_any(csv)
    assert out["ok"] and out["tables"] and out["tables"][0]["pair"] == "BTC/USDT"


def test_read_any_feeds_memory(tmp_path):
    mem = AssociativeMemory()
    doc = tmp_path / "lesson.txt"
    doc.write_text("Binance perpetual futures liquidations cascade under high leverage")
    out = read_any(doc, memory=mem, title="liq lesson")
    assert out["remembered"] is True
    hits = mem.recall("perpetual futures leverage", k=2)
    assert hits and hits[0]["title"] == "liq lesson"


def test_perception_status_reports_engines():
    st = status()
    assert "docling" in st and "surya_ocr" in st and st["plain_formats"]


def test_deep_research_falls_back_offline():
    def fake_search(q, max_results=6):
        return [{"title": "src", "href": "https://x", "body": f"snippet about {q}"}]

    def fake_llm(prompt):
        return "critique line" if "Reflexion critic" in prompt else "synth summary"

    r = AutonomousResearcher(searcher=fake_search, summarizer=fake_llm)
    out = r.deep_research("btc funding", heavy=False)
    assert out["available"] and out["engine"].startswith("light")
    assert out["report"] == "synth summary" and out["sources"] == ["https://x"]
    assert out["critique"] == "critique line"          # Reflexion pass ran
