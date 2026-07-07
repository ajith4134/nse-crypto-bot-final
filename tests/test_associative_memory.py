"""Tests for memory/associative.py — HippoRAG PPR recall + A-MEM evolution (offline path)."""
import json

from memory.associative import AssociativeMemory


def _seed(mem):
    mem.add("Bitcoin funding rates spiked before the crash; perpetual futures traders "
            "were over-leveraged on binance bitcoin positions", title="funding spike")
    mem.add("Breakouts on low volume NSE smallcaps tend to fail after 2pm",
            title="nse breakout lesson")
    mem.add("Binance perpetual futures liquidations cascade when bitcoin funding "
            "rates stay elevated and leverage builds up", title="liquidation cascade")


def test_add_links_related_notes():
    mem = AssociativeMemory()
    _seed(mem)
    notes = list(mem.notes.values())
    # the two bitcoin/funding notes must have auto-linked (A-MEM evolution, heuristic path)
    linked = [n for n in notes if n.links]
    assert len(linked) >= 2
    st = mem.status()
    assert st["notes"] == 3 and st["links"] >= 1
    assert st["graph"]["nodes"] > 3          # entities + notes in the knowledge graph


def test_recall_is_associative_multihop():
    mem = AssociativeMemory()
    _seed(mem)
    # query on a RELATED topic (leverage/liquidation) must surface the old funding note
    hits = mem.recall("bitcoin leverage liquidation risk", k=3)
    assert hits, "PPR recall returned nothing"
    titles = [h["title"] for h in hits]
    assert "liquidation cascade" in titles
    assert "funding spike" in titles          # multi-hop: reached via shared entities/links
    assert all(h["via"].startswith("associative") for h in hits)
    # the unrelated NSE note must not outrank the associated pair
    assert titles.index("liquidation cascade") < 2


def test_persistence_across_instances(tmp_path):
    path = tmp_path / "assoc.json"
    mem = AssociativeMemory(path=path)
    _seed(mem)
    assert path.exists() and json.loads(path.read_text())["notes"]
    # fresh instance (new process equivalent) reloads notes + graph and can recall
    mem2 = AssociativeMemory(path=path)
    assert len(mem2.notes) == 3
    hits = mem2.recall("bitcoin funding rates", k=2)
    assert hits and hits[0]["title"] in {"funding spike", "liquidation cascade"}


def test_llm_path_used_when_available():
    calls = []

    def fake_llm(messages):
        calls.append(messages)
        sys = messages[0]["content"]
        if "triples" in sys:
            return json.dumps({"triples": [["bitcoin", "has", "funding rate"]]})
        if "memory-evolution" in sys:
            return json.dumps({"should_evolve": False, "actions": [],
                               "suggested_connections": [], "tags_to_update": [],
                               "new_tags_neighborhood": []})
        return json.dumps({"keywords": ["bitcoin", "funding"], "context": "crypto",
                           "tags": ["crypto"]})

    mem = AssociativeMemory(llm_chat=fake_llm)
    out = mem.add("Bitcoin funding rates matter", title="t")
    assert out["llm"] is True and out["triples"] == 1
    assert calls, "LLM was not consulted"
