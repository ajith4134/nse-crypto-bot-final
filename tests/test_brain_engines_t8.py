"""Trading Phase T8 (Brain engines, deferred A2/A3) acceptance tests — fully offline.

Pins KNOWN-VALUE / behavioural assertions against the two new brain engines without
ever touching the network or a real LLM:

  • trading/brain/researcher.py  — AutonomousResearcher: web search + LLM synthesis with
    BOTH the searcher and summariser INJECTED as deterministic stubs (no ddgs, no LLM).
    We cover the happy path, the no-LLM extractive fallback, the no-sources path, the
    symbol-research query shaping, and status() introspection.

  • trading/brain/rl_exit.py      — QLearningExit: tabular Q-learning exit policy trained
    on deterministic synthetic trajectories (pure numpy, seeded). We assert it actually
    learns (trained != untrained), banks big profits, cuts losers, that predict_proba is a
    well-formed probability vector usable as an EntryExitPolicy exit_model, that two seed-0
    agents are bit-for-bit identical, and that the deep-RL hook is gated without importing
    torch.

Deterministic throughout; nothing in the repo is touched.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import unittest

from trading.brain.researcher import AutonomousResearcher
from trading.brain.rl_exit import QLearningExit, _state_key, deep_rl_available


# ── injected stubs (NEVER the real ddgs / LLM) ───────────────────────────────
_STUB_ROWS = [
    {"title": "Cat A surges", "href": "https://ex.com/a", "body": "Strong earnings beat, guidance raised."},
    {"title": "Cat B risk", "href": "https://ex.com/b", "body": "Regulatory probe weighs on sentiment."},
    {"title": "Cat C flow", "href": "https://ex.com/c", "body": "Institutional inflows up 12% this week."},
]
_STUB_SUMMARY = "Brief: bullish catalysts [1][3] offset by regulatory risk [2]."


def _stub_searcher(query):
    return [dict(r) for r in _STUB_ROWS]


def _stub_summarizer(prompt):
    return _STUB_SUMMARY


def _raising_summarizer(prompt):
    raise RuntimeError("no LLM configured")


def _empty_summarizer(prompt):
    return ""


class TestAutonomousResearcher(unittest.TestCase):
    def test_research_happy_path_with_injected_stubs(self):
        r = AutonomousResearcher(searcher=_stub_searcher, summarizer=_stub_summarizer)
        out = r.research("q")
        self.assertEqual(out["query"], "q")
        self.assertEqual(out["n_sources"], 3)
        self.assertEqual(out["summary"], _STUB_SUMMARY)
        self.assertEqual(len(out["sources"]), 3)
        self.assertTrue(out["available"])
        self.assertTrue(out["llm_used"])
        # sources carry title+href only, and the result is JSON-able end to end
        self.assertEqual(out["sources"][0]["href"], "https://ex.com/a")
        json.dumps(out)

    def test_search_returns_cleaned_rows(self):
        r = AutonomousResearcher(searcher=_stub_searcher, summarizer=_stub_summarizer)
        rows = r.search("q")
        self.assertEqual(len(rows), 3)
        self.assertEqual(set(rows[0]), {"title", "href", "body"})

    def test_no_llm_fallback_when_summarizer_raises(self):
        r = AutonomousResearcher(searcher=_stub_searcher, summarizer=_raising_summarizer)
        out = r.research("q")
        self.assertTrue(out["available"])
        self.assertFalse(out["llm_used"])
        self.assertTrue(out["summary"])                      # extractive digest non-empty
        self.assertIn("extractive", out["summary"])

    def test_no_llm_fallback_when_summarizer_empty(self):
        r = AutonomousResearcher(searcher=_stub_searcher, summarizer=_empty_summarizer)
        out = r.research("q")
        self.assertFalse(out["llm_used"])
        self.assertTrue(out["summary"])

    def test_no_sources_reports_unavailable(self):
        r = AutonomousResearcher(searcher=lambda q: [], summarizer=_stub_summarizer)
        out = r.research("q")
        self.assertFalse(out["available"])
        self.assertEqual(out["n_sources"], 0)
        self.assertEqual(out["summary"], "")
        self.assertEqual(out["sources"], [])

    def test_research_symbol_builds_market_query(self):
        seen = {}

        def recorder(query):
            seen["q"] = query
            return [dict(r) for r in _STUB_ROWS]

        r = AutonomousResearcher(searcher=recorder, summarizer=_stub_summarizer)
        crypto = r.research_symbol("BTCUSDT", market="crypto")
        self.assertIn("crypto", seen["q"].lower())
        self.assertIn("BTCUSDT", seen["q"])
        self.assertEqual(crypto["symbol"], "BTCUSDT")
        self.assertEqual(crypto["market"], "crypto")

        stock = r.research_symbol("RELIANCE", market="stock")
        self.assertIn("stock", seen["q"].lower())
        self.assertEqual(stock["market"], "stock")

    def test_status_reports_injected_and_is_json_able(self):
        r = AutonomousResearcher(searcher=_stub_searcher, summarizer=_stub_summarizer)
        st = r.status()
        self.assertEqual(st["searcher"], "injected")
        self.assertEqual(st["llm"], "injected")
        json.dumps(st)


# ── deterministic synthetic trajectories for the Q-learning exit ─────────────
def _trajectories():
    """A winner that holds a small early profit then banks a big one, and a loser
    whose continued holding bleeds (large negative step cost) so it should be cut."""
    winner = [
        {"unrealized_r": 0.3, "bars_held": 1, "anomaly_high": 0, "step_reward": -0.01},
        {"unrealized_r": 2.5, "bars_held": 12, "anomaly_high": 0, "step_reward": -0.01},
    ]
    loser = [
        {"unrealized_r": -1.5, "bars_held": 15, "anomaly_high": 1, "step_reward": -2.0},
    ]
    return [winner, loser]


class TestQLearningExit(unittest.TestCase):
    def test_trained_differs_from_untrained_and_banks_profit(self):
        untrained = QLearningExit(seed=0)
        trained = QLearningExit(seed=0).train(_trajectories(), epochs=200)

        # untrained Q is all-zero -> never exits anywhere
        self.assertFalse(untrained.should_exit(2.5, 12, False))
        # trained agent banks a big profit
        self.assertTrue(trained.should_exit(2.5, 12, False))
        # ... so trained and untrained DIFFER on that state
        self.assertNotEqual(untrained.should_exit(2.5, 12, False),
                            trained.should_exit(2.5, 12, False))
        self.assertGreater(trained.epochs_trained, 0)

    def test_small_early_profit_decision_differs_from_big_profit(self):
        trained = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        big = trained.should_exit(2.5, 12, False)
        small = trained.should_exit(0.3, 1, False)
        self.assertTrue(big)
        self.assertFalse(small)          # hold while edge persists
        self.assertNotEqual(big, small)

    def test_cuts_losers(self):
        trained = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        self.assertTrue(trained.should_exit(-1.5, 15, True))

    def test_predict_proba_is_probability_vector(self):
        trained = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        probs = trained.predict_proba([[2.5, 12, 0], [-1.5, 15, 1]])
        self.assertEqual(len(probs), 2)
        for p in probs:
            self.assertIsInstance(p, float)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)
        # higher EXIT-Q state should carry higher p(EXIT)
        self.assertGreater(probs[0], 0.5)

    def test_predict_proba_single_row_is_float_for_exit_model(self):
        trained = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        p = trained.predict_proba([[2.5, 12, 0]])[0]
        self.assertIsInstance(p, float)   # fits EntryExitPolicy(exit_model=...)

    def test_determinism_two_seed0_agents_identical(self):
        a = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        b = QLearningExit(seed=0).train(_trajectories(), epochs=200)
        grid = [
            (2.5, 12, False), (0.3, 1, False), (-1.5, 15, True),
            (0.5, 5, False), (1.5, 8, True), (-0.5, 3, False),
        ]
        for ur, bh, ah in grid:
            self.assertEqual(a.should_exit(ur, bh, ah), b.should_exit(ur, bh, ah))
        self.assertEqual(a.predict_proba([list(g[:2]) + [int(g[2])] for g in grid]),
                        b.predict_proba([list(g[:2]) + [int(g[2])] for g in grid]))

    def test_state_key_discretization(self):
        self.assertEqual(_state_key(2.5, 12, False), (4, 2, 0))
        self.assertEqual(_state_key(-1.5, 15, True), (0, 2, 1))
        self.assertEqual(_state_key(0.3, 1, 0), (2, 0, 0))

    def test_deep_rl_gated_and_status_json_able(self):
        flag = deep_rl_available()
        self.assertIsInstance(flag, dict)
        self.assertIn("available", flag)
        self.assertIsInstance(flag["available"], bool)
        st = QLearningExit(seed=0).train(_trajectories(), epochs=10).status()
        self.assertEqual(st["type"], "QLearningExit")
        self.assertGreater(st["n_states"], 0)
        json.dumps(st)


if __name__ == "__main__":
    unittest.main()
