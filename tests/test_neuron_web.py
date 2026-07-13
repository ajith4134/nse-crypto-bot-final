"""Tests for memory/neuron_web.py — converters + idempotent backfill (R15)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import memory.neuron_web as nw
from memory.neurons import NeuronStore


def _fixture_state(tmp: Path) -> None:
    (tmp / "journal.json").write_text(json.dumps([
        {"trade_id": "T1", "symbol": "BTCUSDT", "direction": "LONG",
         "entry_datetime": "2026-07-01 10:00", "exit_datetime": "2026-07-01 11:00",
         "entry_price": 100, "exit_price": 110, "net_pnl": 10.0, "r_multiple": 2.0,
         "strategy_name": "vp_reversion", "setup_type": "VAL bounce",
         "market_regime_entry": "range", "lesson_learned": "wait for absorption",
         "signal_source": "fusion"},
        {"trade_id": "T2", "symbol": "ETHUSDT", "direction": "SHORT",
         "entry_datetime": "2026-07-02 10:00", "exit_datetime": None},  # open → skipped
    ]))
    (tmp / "news_memory.json").write_text(json.dumps(
        {"items": [{"title": "BTC ETF inflows surge", "url": "https://x/1",
                    "source": "rss", "symbols": ["BTC"], "compound": 0.6,
                    "ts": 1783800000}]}))
    (tmp / "hypotheses.json").write_text(json.dumps(
        {"hypotheses": [{"hid": "H1", "statement": "high OBI predicts up-move",
                         "status": "validated", "credence": 0.7, "field": "psych_obi",
                         "op": ">", "value": 0.5}],
         "failures": [{"hid": "H9", "statement": "friday always red", "credence": 0.1}]}))


class NeuronWebTest(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp())
        self.brainmem = Path(tempfile.mkdtemp())
        self.research = Path(tempfile.mkdtemp())
        _fixture_state(self.state)
        (self.research / "topic-x.md").write_text("# Topic X findings\nbody")
        self.patches = [
            mock.patch.object(nw, "STATE_DIR", self.state),
            mock.patch.object(nw, "BRAIN_MEMORY", self.brainmem),
            mock.patch.object(nw, "RESEARCH_DIR", self.research),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.store = NeuronStore(tempfile.mkdtemp())

    def test_backfill_converts_and_is_idempotent(self):
        r1 = nw.backfill(self.store)
        self.assertEqual(r1["journal"], {"added": 1, "errors": 0})   # open trade skipped
        self.assertEqual(r1["news"]["added"], 1)
        self.assertEqual(r1["hypotheses"]["added"], 2)               # 1 finding + 1 failure
        self.assertEqual(r1["research_docs"]["added"], 1)
        self.assertEqual(r1["store"]["action_coverage"], 1.0)        # R24 everywhere
        n_before = self.store.status()["neurons"]
        r2 = nw.backfill(self.store)                                 # second run: no dupes
        self.assertEqual(self.store.status()["neurons"], n_before)
        self.assertTrue(all(v["added"] == 0 for k, v in r2.items()
                            if isinstance(v, dict) and "added" in v))

    def test_actions_derived_from_row_data(self):
        nw.backfill(self.store)
        hit = self.store.search("BTCUSDT VAL bounce", kind="episode")[0]
        self.assertIn("REPEAT", hit["action"])                       # pnl>0 → repeat
        self.assertIn("wait for absorption", hit["action"])          # real lesson text
        failed = self.store.search("friday always red", kind="lesson")[0]
        self.assertIn("Do NOT trade on this", failed["action"])

    def test_changed_row_updates_in_place(self):
        nw.backfill(self.store)
        j = json.loads((self.state / "journal.json").read_text())
        j[0]["lesson_learned"] = "changed lesson"
        (self.state / "journal.json").write_text(json.dumps(j))
        r = nw.backfill(self.store)
        self.assertEqual(r["journal"]["added"], 1)                   # update, not dupe
        hit = self.store.search("BTCUSDT", kind="episode")[0]
        self.assertIn("changed lesson", hit["action"])


if __name__ == "__main__":
    unittest.main()
