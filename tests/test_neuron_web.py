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

    def test_features_stitched_as_skill_neurons_with_actions(self):
        # R1 stitch: every shipped feature becomes a skill neuron carrying a how-to-use
        # action facet, so the brain KNOWS and can USE its own capabilities.
        r = nw.NeuronWeb(self.store)._run(nw.NeuronWeb(self.store).conv_features)
        self.assertEqual(r["added"], len(nw._FEATURE_CATALOG))
        for key in ("patchright_stealth", "feed_selfheal", "uitars_last_resort",
                    "brain_os"):
            n = self.store.get(nw._det_id("features", key))
            self.assertIsNotNone(n, key)
            self.assertEqual(n.kind, "skill")
            self.assertTrue(n.action.strip())                         # R24 action facet
        r2 = nw.NeuronWeb(self.store)._run(nw.NeuronWeb(self.store).conv_features)
        self.assertEqual(r2["added"], 0)                             # idempotent

    def test_inventions_and_nav_routes_and_recipes(self):
        (self.state / "skill_library.json").write_text(json.dumps([
            {"id": "s1", "name": "gamma_scalp", "kind": "strategy", "market": "CRYPTO",
             "metric": 0.9, "metrics": {"dsr": 0.9, "fwer_passed": True},
             "generation": 0, "payload": {}},
            {"id": "s2", "name": "weak", "kind": "strategy", "market": "CRYPTO",
             "metric": 0.1, "metrics": {"dsr": 0.1, "fwer_passed": False}},  # gate FAILED
        ]))
        (self.state / "strategy_foundry.json").write_text(json.dumps(
            {"specs": [{"sid": "f1", "name": "vp_break", "segment": "crypto_futures",
                        "family": "breakout", "idea": "break the value area high"}]}))
        (self.state / "app_school_map.json").write_text(json.dumps(
            {"routes": {"binance": {"futures": {"confirmed": True, "endpoint": "api/fut"}},
                        "upstox": {"chain": {"confirmed": False, "endpoint": "x"}}}}))
        nw.backfill(self.store)
        # R6: only the GATE-PASSED strategy becomes an invention
        inv = [n for n in self.store.all_neurons() if n.kind == "invention"]
        self.assertEqual(len(inv), 1)
        self.assertIn("gamma_scalp", inv[0].title)
        # R7: strategy recipe is a market-scoped instruction
        rec = self.store.search("vp_break", kind="instruction")
        self.assertTrue(any("[crypto]" in h["title"] for h in rec))
        # R12/R13: only the CONFIRMED nav route becomes an instruction
        nav = [n for n in self.store.all_neurons()
               if n.kind == "instruction" and n.ref.startswith("nav:")]
        self.assertEqual(len(nav), 1)
        self.assertIn("futures", nav[0].title)

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
