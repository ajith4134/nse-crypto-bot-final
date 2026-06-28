"""Trading Phase T8.7 (Autonomous news research + sentiment) acceptance tests — fully offline.

Pins KNOWN-VALUE assertions against the pure-Python sentiment + news-research package so CI
passes with NO network access: the vendored-VADER SentimentScorer (finance-lexicon boosted,
[-1,1] compound + positive/negative/neutral label), the NewsItem container, the NewsResearcher
per-symbol aggregator driven by an INJECTED stub fetcher (never the real RSS/feedparser path),
the gated autonomous_research() degrade-to-note behaviour, and the NewsSentimentNode NodeProtocol
node that maps a [-1,1] compound to p(bullish).

No item ever triggers fetch_rss() or any real network/LLM call; GPT_RESEARCHER_ENABLED is left
unset on purpose. Deterministic throughout.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import os
import unittest

from core.node_protocol import NodeProtocol
from trading.brain.news import NewsItem, NewsResearcher, NewsSentimentNode
from trading.brain.sentiment import SentimentScorer


class TestSentimentScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = SentimentScorer(backend="vader")

    def test_bullish_headline_positive(self):
        r = self.scorer.score("Company beats estimates, raises guidance, shares surge")
        self.assertGreater(r["compound"], 0.3)
        self.assertEqual(r["label"], "positive")

    def test_bearish_headline_negative(self):
        r = self.scorer.score("Stock plunges on fraud probe, trading halt")
        self.assertLess(r["compound"], -0.3)
        self.assertEqual(r["label"], "negative")

    def test_neutral_string_label(self):
        r = self.scorer.score("the meeting is scheduled for the afternoon")
        self.assertEqual(r["label"], "neutral")

    def test_empty_string_zero_neutral(self):
        r = self.scorer.score("")
        self.assertEqual(r["compound"], 0.0)
        self.assertEqual(r["label"], "neutral")

    def test_finance_lexicon_boost_direction(self):
        up = self.scorer.score("analyst upgrade")["compound"]
        down = self.scorer.score("analyst downgrade")["compound"]
        self.assertGreater(up, 0.0)
        self.assertLess(down, 0.0)
        self.assertGreater(up, down)

    def test_active_backend_is_vader(self):
        self.assertEqual(self.scorer.active_backend, "vader")

    def test_score_reports_vader_backend(self):
        r = self.scorer.score("shares rally on record growth")
        self.assertEqual(r["backend"], "vader")

    def test_score_many_one_dict_per_input(self):
        texts = ["beats estimates", "plunges on fraud", "a neutral sentence"]
        out = self.scorer.score_many(texts)
        self.assertEqual(len(out), 3)
        self.assertTrue(all(isinstance(d, dict) and "compound" in d for d in out))

    def test_label_thresholds(self):
        self.assertEqual(SentimentScorer._label(0.06), "positive")
        self.assertEqual(SentimentScorer._label(-0.06), "negative")
        self.assertEqual(SentimentScorer._label(0.0), "neutral")
        self.assertEqual(SentimentScorer._label(0.05), "neutral")
        self.assertEqual(SentimentScorer._label(-0.05), "neutral")

    def test_compound_in_range(self):
        for t in ("beats estimates and surges", "plunges on fraud probe", "neutral text"):
            c = self.scorer.score(t)["compound"]
            self.assertGreaterEqual(c, -1.0)
            self.assertLessEqual(c, 1.0)


class TestNewsItem(unittest.TestCase):
    def test_text_concatenates_title_and_summary(self):
        it = NewsItem(title="Reliance beats estimates", summary="shares surge")
        self.assertIn("Reliance beats estimates", it.text)
        self.assertIn("shares surge", it.text)


class TestNewsResearcher(unittest.TestCase):
    def _feed(self):
        return [
            NewsItem(title="RELIANCE beats estimates and shares surge", source="A"),
            NewsItem(title="RELIANCE raises guidance, analyst upgrade", source="B"),
            NewsItem(title="RELIANCE plunges on fraud probe", source="C"),
            NewsItem(title="Weather update for the weekend", source="D"),
            NewsItem(title="TCS announces new office", source="E"),
        ]

    def test_research_filters_to_symbol(self):
        rs = NewsResearcher(fetcher=self._feed)
        out = rs.research("RELIANCE")
        self.assertEqual(out["symbol"], "RELIANCE")
        self.assertEqual(out["n_articles"], 3)

    def test_research_avg_sign_and_counts(self):
        rs = NewsResearcher(fetcher=self._feed)
        out = rs.research("RELIANCE")
        # two bullish, one bearish -> positive average
        self.assertGreater(out["avg_compound"], 0.0)
        self.assertEqual(out["label"], "positive")
        self.assertEqual(out["bullish"], 2)
        self.assertEqual(out["bearish"], 1)

    def test_top_headlines_sorted_and_capped(self):
        rs = NewsResearcher(fetcher=self._feed)
        out = rs.research("RELIANCE", top=2)
        heads = out["top_headlines"]
        self.assertLessEqual(len(heads), 2)
        mags = [abs(h["compound"]) for h in heads]
        self.assertEqual(mags, sorted(mags, reverse=True))

    def test_backend_reported(self):
        rs = NewsResearcher(fetcher=self._feed)
        self.assertEqual(rs.research("RELIANCE")["backend"], "vader")

    def test_explicit_items_without_fetcher(self):
        rs = NewsResearcher()  # no fetcher injected
        out = rs.research("RELIANCE", items=self._feed())
        self.assertEqual(out["n_articles"], 3)

    def test_no_mention_returns_neutral_not_whole_feed(self):
        # Fixed behaviour: a symbol with no matching news yields NO articles → neutral,
        # rather than mis-attributing the whole feed's market-wide sentiment to it.
        rs = NewsResearcher()
        items = self._feed()
        out = rs.research("NOSUCHSYMBOL", items=items)
        self.assertEqual(out["n_articles"], 0)
        self.assertEqual(out["avg_compound"], 0.0)
        self.assertEqual(out["label"], "neutral")

    def test_autonomous_research_gated_unavailable(self):
        self.assertNotIn("GPT_RESEARCHER_ENABLED", os.environ)  # not set in test env
        rs = NewsResearcher()
        out = rs.autonomous_research("what is the outlook for RELIANCE")
        self.assertFalse(out["available"])
        self.assertIn("note", out)
        self.assertEqual(out["query"], "what is the outlook for RELIANCE")


class TestNewsSentimentNode(unittest.TestCase):
    def setUp(self):
        self.node = NewsSentimentNode()

    def test_is_node_protocol(self):
        self.assertIsInstance(self.node, NodeProtocol)

    def test_kind_and_schema(self):
        self.assertEqual(self.node.kind, "news_sentiment")
        self.assertEqual(self.node.schema.input_dim, 1)

    def test_predict_proba_maps_range(self):
        out = self.node.predict_proba([[1.0], [-1.0], [0.0]])
        self.assertAlmostEqual(out[0], 1.0, places=9)
        self.assertAlmostEqual(out[1], 0.0, places=9)
        self.assertAlmostEqual(out[2], 0.5, places=9)

    def test_predict_proba_clips(self):
        out = self.node.predict_proba([[2.0], [-2.0]])
        self.assertAlmostEqual(out[0], 1.0, places=9)
        self.assertAlmostEqual(out[1], 0.0, places=9)

    def test_predict_returns_labels(self):
        labels = self.node.predict([[1.0], [-1.0]])
        self.assertEqual(labels, [1, 0])

    def test_fit_is_noop_returns_self(self):
        self.assertIs(self.node.fit([[0.0]]), self.node)


if __name__ == "__main__":
    unittest.main()
