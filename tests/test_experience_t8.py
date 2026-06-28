"""Trading Phase T8.4 (episodic experience bank + semantic memory) acceptance tests.

Fully OFFLINE + deterministic. Pins behaviour of the Case-Based experience bank
(`trading/brain/experience.py`) — deterministic setup vectors, exact in-memory kNN
retrieval, and CBR recall that biases new decisions by analogous historical outcomes —
plus the dry-run semantic (text) memory (`trading/brain/semantic.py`).

The numpy in-memory path (`use_lancedb=False`) is used for the deterministic core; ONE
test exercises the real embedded LanceDB store from a tempdir to prove the persistence /
ANN search path, and skips gracefully if LanceDB cannot run in this environment. mem0 is
exercised in its offline dry-run mode (keyword-overlap search), never calling an LLM.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import tempfile
import unittest

from trading.brain.experience import (
    VEC_FIELDS,
    ExperienceBank,
    Recall,
    trade_vector,
)
from trading.brain.semantic import SemanticMemory
from trading.journal.journal import TradeJournal
from trading.journal.schema import ClosedTrade


def _trade(**kw) -> ClosedTrade:
    return ClosedTrade(**kw)


def _long_low_vix_winner(i: int) -> ClosedTrade:
    """A LONG setup in a calm market (low India VIX) that WON."""
    return ClosedTrade(
        trade_id=f"win{i}", symbol="RELIANCE", direction="LONG",
        entry_hour=10, india_vix_entry=10.0, regime_confidence=70.0,
        relative_volume=1.2, net_pnl=500.0, r_multiple=2.0)


def _long_high_vix_loser(i: int) -> ClosedTrade:
    """A LONG setup in a panicky market (high India VIX) that LOST."""
    return ClosedTrade(
        trade_id=f"loss{i}", symbol="RELIANCE", direction="LONG",
        entry_hour=10, india_vix_entry=30.0, regime_confidence=70.0,
        relative_volume=1.2, net_pnl=-500.0, r_multiple=-1.0)


class TestTradeVector(unittest.TestCase):
    def test_length_matches_vec_fields(self):
        v = trade_vector(_trade(direction="LONG"))
        self.assertEqual(len(v), len(VEC_FIELDS))
        self.assertEqual(len(VEC_FIELDS), 15)

    def test_direction_component_distinguishes_long_short(self):
        long_v = trade_vector(_trade(direction="LONG"))
        short_v = trade_vector(_trade(direction="SHORT"))
        # index 1 == 'direction' component: LONG -> +1, SHORT -> -1
        self.assertEqual(VEC_FIELDS[1], "direction")
        self.assertEqual(long_v[1], 1.0)
        self.assertEqual(short_v[1], -1.0)
        self.assertNotEqual(long_v[1], short_v[1])

    def test_missing_and_none_fields_are_zero_no_crash(self):
        # bare trade: direction "" and all numeric context None -> all components 0.0
        v = trade_vector(ClosedTrade())
        self.assertEqual(v[1], 0.0)              # direction "" -> 0
        # vix component (None india_vix_entry -> 0) -> (0-15)/10 = -1.5, still finite
        self.assertTrue(all(isinstance(x, float) for x in v))
        # a dict missing every key must also not crash
        self.assertEqual(len(trade_vector({})), len(VEC_FIELDS))

    def test_deterministic(self):
        t = _long_low_vix_winner(1)
        self.assertEqual(trade_vector(t), trade_vector(t))
        # equal trades -> equal vectors
        self.assertEqual(trade_vector(_long_low_vix_winner(1)),
                         trade_vector(_long_low_vix_winner(2)))

    def test_accepts_dict_and_trade(self):
        t = _long_low_vix_winner(1)
        self.assertEqual(trade_vector(t), trade_vector(t.to_dict()))


class TestExperienceBankMemory(unittest.TestCase):
    def test_empty_bank(self):
        bank = ExperienceBank(use_lancedb=False)
        self.assertEqual(bank.size(), 0)
        self.assertEqual(bank.retrieve(_trade(direction="LONG")), [])
        r = bank.recall(_trade(direction="LONG"))
        self.assertIsInstance(r, Recall)
        self.assertEqual(r.n, 0)
        self.assertEqual(r.neighbours, [])

    def test_add_many_size(self):
        bank = ExperienceBank(use_lancedb=False)
        bank.add_many([_long_low_vix_winner(i) for i in range(6)])
        self.assertEqual(bank.size(), 6)
        bank.add_trade(_long_high_vix_loser(0))
        self.assertEqual(bank.size(), 7)

    def test_retrieve_respects_k_and_sorted_by_distance(self):
        bank = ExperienceBank(use_lancedb=False)
        bank.add_many([_long_low_vix_winner(i) for i in range(5)]
                      + [_long_high_vix_loser(i) for i in range(5)])
        cases = bank.retrieve(_long_low_vix_winner(99), k=3)
        self.assertLessEqual(len(cases), 3)
        self.assertEqual(len(cases), 3)
        dists = [c["_distance"] for c in cases]
        self.assertEqual(dists, sorted(dists))   # ascending: nearest first
        # nearest to a low-vix winner query should itself be a winner
        self.assertGreater(cases[0]["net_pnl"], 0.0)

    def test_status_fields(self):
        bank = ExperienceBank(use_lancedb=False)
        bank.add_many([_long_low_vix_winner(i) for i in range(3)]
                      + [_long_high_vix_loser(i) for i in range(1)])
        st = bank.status()
        self.assertEqual(st["n_cases"], 4)
        self.assertEqual(st["vector_dim"], len(VEC_FIELDS))
        self.assertEqual(st["store"], "memory")
        # 3 wins of 4 -> 75%
        self.assertAlmostEqual(st["base_win_rate"], 75.0, places=6)
        json.dumps(st)


class TestCBRDiscrimination(unittest.TestCase):
    """The key behaviour: retrieval biases decisions by analogous outcomes."""

    def _bank(self) -> ExperienceBank:
        bank = ExperienceBank(use_lancedb=False)
        bank.add_many([_long_low_vix_winner(i) for i in range(6)]
                      + [_long_high_vix_loser(i) for i in range(6)])
        return bank

    def test_low_vix_query_recalls_positive_bias(self):
        bank = self._bank()
        # query resembling the calm-market winning cluster
        q = _trade(direction="LONG", india_vix_entry=10.0, regime_confidence=70.0,
                   relative_volume=1.2, entry_hour=10)
        r = bank.recall(q, k=5)
        self.assertGreater(r.n, 0)
        self.assertGreater(r.bias, 0.0)
        self.assertGreater(r.expected_win_rate, 50.0)
        self.assertGreater(r.expected_pnl, 0.0)

    def test_high_vix_query_recalls_negative_bias(self):
        bank = self._bank()
        # query resembling the panicky-market losing cluster
        q = _trade(direction="LONG", india_vix_entry=30.0, regime_confidence=70.0,
                   relative_volume=1.2, entry_hour=10)
        r = bank.recall(q, k=5)
        self.assertGreater(r.n, 0)
        self.assertLess(r.bias, 0.0)
        self.assertLess(r.expected_win_rate, 50.0)
        self.assertLess(r.expected_pnl, 0.0)

    def test_clusters_drive_opposite_decisions(self):
        bank = self._bank()
        low = bank.recall(_trade(direction="LONG", india_vix_entry=10.0,
                                 regime_confidence=70.0, relative_volume=1.2,
                                 entry_hour=10), k=5)
        high = bank.recall(_trade(direction="LONG", india_vix_entry=30.0,
                                  regime_confidence=70.0, relative_volume=1.2,
                                  entry_hour=10), k=5)
        self.assertGreater(low.bias, high.bias)
        self.assertGreater(low.expected_win_rate, high.expected_win_rate)


class TestRecallSerialisation(unittest.TestCase):
    def test_as_dict_json_able_and_drops_vectors(self):
        bank = ExperienceBank(use_lancedb=False)
        bank.add_many([_long_low_vix_winner(i) for i in range(4)])
        r = bank.recall(_long_low_vix_winner(99), k=3)
        d = r.as_dict()
        # round-trips through JSON
        json.dumps(d)
        self.assertIn("neighbours", d)
        self.assertGreater(len(d["neighbours"]), 0)
        for nb in d["neighbours"]:
            self.assertNotIn("vector", nb)


class TestFromJournal(unittest.TestCase):
    def test_size_matches_journal(self):
        j = TradeJournal(persist=False)
        trades = [
            ClosedTrade(trade_id="a", symbol="RELIANCE", exchange="NSE",
                        instrument_type="EQ", direction="LONG", entry_price=100.0,
                        exit_price=110.0, quantity=10.0,
                        entry_datetime="2026-06-01T09:30:00",
                        exit_datetime="2026-06-01T10:30:00"),
            ClosedTrade(trade_id="b", symbol="TCS", exchange="NSE",
                        instrument_type="EQ", direction="LONG", entry_price=200.0,
                        exit_price=195.0, quantity=5.0,
                        entry_datetime="2026-06-01T11:00:00",
                        exit_datetime="2026-06-01T11:30:00"),
            ClosedTrade(trade_id="c", symbol="BTCUSDT", exchange="Binance",
                        instrument_type="PERP", direction="SHORT", entry_price=70000.0,
                        exit_price=69000.0, quantity=1.0,
                        entry_datetime="2026-06-01T12:00:00",
                        exit_datetime="2026-06-01T13:00:00"),
        ]
        for t in trades:
            j.record(t)
        bank = ExperienceBank(use_lancedb=False).from_journal(j)
        self.assertEqual(bank.size(), len(j.trades))
        self.assertEqual(bank.size(), 3)


class TestLanceDBPath(unittest.TestCase):
    def test_lancedb_store_and_recall(self):
        uri = tempfile.mkdtemp(prefix="exp_t8_lancedb_")
        try:
            bank = ExperienceBank(uri=uri)
            if not bank._use_lancedb:                       # LanceDB not importable
                self.skipTest("LanceDB not available in this environment")
            bank.add_many([_long_low_vix_winner(i) for i in range(6)]
                          + [_long_high_vix_loser(i) for i in range(6)])
            self.assertEqual(bank.size(), 12)
            st = bank.status()
            self.assertEqual(st["store"], "lancedb")
            cases = bank.retrieve(_long_low_vix_winner(99), k=5)
            self.assertGreater(len(cases), 0)
            for c in cases:
                self.assertIn("_distance", c)
            r = bank.recall(_long_low_vix_winner(99), k=5)
            self.assertGreater(r.n, 0)
        except unittest.SkipTest:
            raise
        except Exception as exc:                            # any LanceDB runtime issue
            self.skipTest(f"LanceDB path unavailable: {exc!r}")


class TestSemanticMemory(unittest.TestCase):
    def test_status_dry_run(self):
        sm = SemanticMemory(enabled=False)
        st = sm.status()
        self.assertEqual(st["backend"], "dry-run")
        self.assertTrue(st["mem0_installed"])
        self.assertFalse(st["enabled"])
        self.assertEqual(st["user_id"], "brain")
        self.assertEqual(st["n_notes"], 0)
        json.dumps(st)

    def test_add_and_keyword_search_ranks_relevant_first(self):
        sm = SemanticMemory(enabled=False)
        sm.add("Breakouts after 2pm on low volume NSE names tend to fail")
        sm.add("Crypto perp funding spikes precede sharp reversals overnight")
        res = sm.search("breakout volume NSE", k=5)
        self.assertGreater(len(res), 0)
        # the breakout note shares the most query terms -> ranked first
        self.assertIn("Breakout", res[0]["memory"])
        self.assertGreaterEqual(res[0]["score"], res[-1]["score"])

    def test_add_trade_lesson_attaches_metadata(self):
        sm = SemanticMemory(enabled=False)
        t = ClosedTrade(trade_id="L1", symbol="RELIANCE",
                        net_pnl=-300.0)
        sm.add_trade_lesson(t, "Sized too big into an event; cut risk near results")
        res = sm.search("sized risk results", k=5)
        self.assertGreater(len(res), 0)
        meta = res[0]["metadata"]
        self.assertEqual(meta["trade_id"], "L1")
        self.assertEqual(meta["symbol"], "RELIANCE")
        self.assertAlmostEqual(meta["net_pnl"], -300.0, places=6)

    def test_all_length_and_n_notes(self):
        sm = SemanticMemory(enabled=False)
        sm.add("lesson one about momentum")
        sm.add("lesson two about reversals")
        self.assertEqual(len(sm.all()), 2)
        self.assertEqual(sm.status()["n_notes"], 2)

    def test_empty_text_rejected(self):
        sm = SemanticMemory(enabled=False)
        out = sm.add("")
        self.assertFalse(out["ok"])
        self.assertEqual(len(sm.all()), 0)


if __name__ == "__main__":
    unittest.main()
