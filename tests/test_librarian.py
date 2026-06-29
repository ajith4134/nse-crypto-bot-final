"""Phase P4.3 (self-feeding Librarian) acceptance tests — fully offline & deterministic.

The Librarian discovers → fetches+extracts → dedups → ingests internet content into the
brain. Every source callable is INJECTED with a deterministic stub and the brain is a
tiny STUB object that merely captures (title, text) ingest calls — no real KnowledgeBrain,
no network, no scheduler. Recorders pin the args (max_per, urls) the Librarian forwards.

Every persist_path targets the session scratchpad and is cleaned up. Deterministic.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore")

from memory.librarian import Librarian

_SCRATCH = "/tmp/claude-1000/-home-karan18190164/bd731724-5220-4673-838e-92680bac705f/scratchpad"


# ── stubs ─────────────────────────────────────────────────────────────────────────
class StubBrain:
    """Captures ingest calls; hands back deterministic doc ids."""

    def __init__(self, raises=False):
        self.calls = []          # list of (title, text)
        self.raises = raises

    def ingest_text(self, title, text):
        if self.raises:
            raise RuntimeError("boom")
        self.calls.append((title, text))
        return f"doc{len(self.calls)}"


def make_web(items, recorder=None):
    def _web(query, max_results):
        if recorder is not None:
            recorder.append(("web", query, max_results))
        return [dict(it) for it in items]
    return _web


def make_arxiv(items, recorder=None):
    def _arxiv(query, max_results):
        if recorder is not None:
            recorder.append(("arxiv", query, max_results))
        return [dict(it) for it in items]
    return _arxiv


def make_rss(items, recorder=None):
    def _rss(url, limit):
        if recorder is not None:
            recorder.append(("rss", url, limit))
        return [dict(it) for it in items]
    return _rss


def make_extractor(text, recorder=None):
    def _extract(url):
        if recorder is not None:
            recorder.append(url)
        return text
    return _extract


_WEB = [{"title": "Web One", "url": "http://w1", "body": "short web body"}]
_ARXIV = [{"title": "Paper One", "url": "http://arxiv/1", "body": "an arxiv abstract summary"}]
_RSS = [{"title": "News One", "url": "http://rss/1", "body": "rss summary body"}]
_LONG = "EXTRACTED full clean article text " * 20  # >> short web body


def _lib(brain=None, **kw):
    """Librarian with safe no-op stubs by default so nothing ever hits network."""
    kw.setdefault("web_search", make_web([]))
    kw.setdefault("arxiv_search", make_arxiv([]))
    kw.setdefault("rss_fetch", make_rss([]))
    kw.setdefault("extractor", make_extractor(""))
    return Librarian(brain or StubBrain(), **kw)


class TestDiscover(unittest.TestCase):
    def test_union_and_source_tags(self):
        lib = _lib(web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV))
        items = lib.discover("x", sources=("web", "arxiv"))
        self.assertEqual(len(items), 2)
        by_src = {it["source"] for it in items}
        self.assertEqual(by_src, {"web", "arxiv"})
        web = next(it for it in items if it["source"] == "web")
        self.assertEqual(web["title"], "Web One")

    def test_max_per_forwarded_to_stubs(self):
        rec = []
        lib = _lib(web_search=make_web(_WEB, rec), arxiv_search=make_arxiv(_ARXIV, rec))
        lib.discover("topicX", sources=("web", "arxiv"), max_per=3)
        self.assertIn(("web", "topicX", 3), rec)
        self.assertIn(("arxiv", "topicX", 3), rec)

    def test_rss_only_when_requested_and_urls_given(self):
        rec = []
        lib = _lib(web_search=make_web(_WEB), rss_fetch=make_rss(_RSS, rec))
        # rss not in sources -> no rss
        only_web = lib.discover("x", sources=("web",), rss_urls=["http://feed"])
        self.assertTrue(all(it["source"] != "rss" for it in only_web))
        self.assertEqual(rec, [])
        # rss in sources WITH urls -> rss items appear and url+limit forwarded
        with_rss = lib.discover("x", sources=("rss",), rss_urls=["http://feed"], max_per=4)
        self.assertTrue(any(it["source"] == "rss" for it in with_rss))
        self.assertIn(("rss", "http://feed", 4), rec)

    def test_rss_source_without_urls_yields_nothing(self):
        lib = _lib(rss_fetch=make_rss(_RSS))
        items = lib.discover("x", sources=("rss",), rss_urls=None)
        self.assertEqual(items, [])


class TestIngestItem(unittest.TestCase):
    def test_web_item_uses_extractor_full_text(self):
        rec = []
        brain = StubBrain()
        lib = _lib(brain, extractor=make_extractor(_LONG, rec))
        res = lib.ingest_item({"title": "T", "url": "http://w1",
                               "body": "short", "source": "web"})
        self.assertTrue(res["ingested"])
        self.assertEqual(rec, ["http://w1"])               # extractor was called
        self.assertEqual(len(brain.calls), 1)
        ingested_text = brain.calls[0][1]
        self.assertEqual(ingested_text, _LONG)             # extracted, not body
        self.assertGreater(len(ingested_text), len("short"))
        self.assertEqual(res["chars"], len(_LONG))

    def test_arxiv_item_uses_body_no_extractor(self):
        rec = []
        brain = StubBrain()
        lib = _lib(brain, extractor=make_extractor(_LONG, rec))
        res = lib.ingest_item({"title": "P", "url": "http://arxiv/1",
                               "body": "the abstract", "source": "arxiv"})
        self.assertTrue(res["ingested"])
        self.assertEqual(rec, [])                           # extractor NOT called
        self.assertEqual(brain.calls[0][1], "the abstract")
        self.assertEqual(res["source"], "arxiv")

    def test_empty_content_not_ingested(self):
        brain = StubBrain()
        lib = _lib(brain)
        res = lib.ingest_item({"title": "T", "url": "http://x",
                               "body": "   ", "source": "arxiv"})
        self.assertFalse(res["ingested"])
        self.assertEqual(res["reason"], "no content")
        self.assertEqual(brain.calls, [])

    def test_web_item_empty_extraction_falls_back_to_no_content(self):
        # web body empty AND extractor returns "" -> nothing to ingest
        brain = StubBrain()
        lib = _lib(brain, extractor=make_extractor(""))
        res = lib.ingest_item({"title": "T", "url": "http://w1",
                               "body": "", "source": "web"})
        self.assertFalse(res["ingested"])
        self.assertEqual(res["reason"], "no content")

    def test_ingest_error_path(self):
        brain = StubBrain(raises=True)
        lib = _lib(brain)
        res = lib.ingest_item({"title": "T", "url": "http://x",
                               "body": "real body", "source": "arxiv"})
        self.assertFalse(res["ingested"])
        self.assertIn("ingest error", res["reason"])


class TestDedup(unittest.TestCase):
    def test_same_item_twice_is_duplicate(self):
        brain = StubBrain()
        lib = _lib(brain)
        item = {"title": "T", "url": "http://x", "body": "real body", "source": "arxiv"}
        first = lib.ingest_item(dict(item))
        second = lib.ingest_item(dict(item))
        self.assertTrue(first["ingested"])
        self.assertFalse(second["ingested"])
        self.assertEqual(second["reason"], "duplicate")
        self.assertEqual(lib.stats["dupes"], 1)
        self.assertEqual(len(brain.calls), 1)              # ingested only once

    def test_feed_twice_second_run_all_dupes(self):
        brain = StubBrain()
        lib = _lib(brain, web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV),
                   extractor=make_extractor(_LONG))
        r1 = lib.feed("topic", sources=("web", "arxiv"))
        r2 = lib.feed("topic", sources=("web", "arxiv"))
        self.assertEqual(r1["ingested"], 2)
        self.assertEqual(r2["ingested"], 0)
        self.assertGreater(r2["dupes"], 0)


class TestFeed(unittest.TestCase):
    def test_counts_and_by_source(self):
        brain = StubBrain()
        lib = _lib(brain, web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV),
                   extractor=make_extractor(_LONG))
        rep = lib.feed("topic", sources=("web", "arxiv"))
        self.assertEqual(rep["found"], 2)
        self.assertEqual(rep["ingested"], 2)
        self.assertEqual(rep["dupes"], 0)
        self.assertEqual(rep["by_source"], {"web": 1, "arxiv": 1})
        self.assertEqual(len(brain.calls), 2)              # once per unique item
        self.assertEqual(rep["topics"], ["topic"])

    def test_feed_string_topic_normalized_to_list(self):
        lib = _lib(web_search=make_web(_WEB), extractor=make_extractor(_LONG))
        rep = lib.feed("solo", sources=("web",))
        self.assertEqual(rep["topics"], ["solo"])

    def test_feed_by_source_web_vs_arxiv(self):
        two_web = [{"title": f"w{i}", "url": f"http://w{i}", "body": "b"} for i in range(2)]
        brain = StubBrain()
        lib = _lib(brain, web_search=make_web(two_web), arxiv_search=make_arxiv(_ARXIV),
                   extractor=make_extractor(_LONG))
        rep = lib.feed("topic", sources=("web", "arxiv"))
        self.assertEqual(rep["by_source"], {"web": 2, "arxiv": 1})


class TestPersistence(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json", dir=_SCRATCH)
        os.close(fd)
        os.remove(self.path)   # start absent; Librarian creates it on save

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_seen_persisted_and_reloaded_as_dupes(self):
        brain1 = StubBrain()
        lib1 = _lib(brain1, web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV),
                    extractor=make_extractor(_LONG), persist_path=self.path)
        rep1 = lib1.feed("topic", sources=("web", "arxiv"))
        self.assertEqual(rep1["ingested"], 2)
        self.assertTrue(os.path.exists(self.path))
        with open(self.path) as f:
            self.assertEqual(len(json.load(f)), 2)         # seen-set written

        # brand-new Librarian loads same seen-set -> everything is a duplicate
        brain2 = StubBrain()
        lib2 = _lib(brain2, web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV),
                    extractor=make_extractor(_LONG), persist_path=self.path)
        self.assertEqual(lib2.status()["seen"], 2)
        rep2 = lib2.feed("topic", sources=("web", "arxiv"))
        self.assertEqual(rep2["ingested"], 0)
        self.assertGreater(rep2["dupes"], 0)
        self.assertEqual(brain2.calls, [])


class TestStatusAndDeterminism(unittest.TestCase):
    def test_status_keys_and_json_able(self):
        brain = StubBrain()
        lib = _lib(brain, web_search=make_web(_WEB), arxiv_search=make_arxiv(_ARXIV),
                   extractor=make_extractor(_LONG))
        lib.feed("topic", sources=("web", "arxiv"))
        st = lib.status()
        for key in ("seen", "found", "ingested", "dupes", "sources"):
            self.assertIn(key, st)
        self.assertEqual(st["ingested"], 2)
        self.assertEqual(st["seen"], 2)
        json.dumps(st)                                     # fully serialisable

    def test_determinism_same_stubs_same_report(self):
        def run():
            lib = _lib(StubBrain(), web_search=make_web(_WEB),
                       arxiv_search=make_arxiv(_ARXIV), extractor=make_extractor(_LONG))
            rep = lib.feed("topic", sources=("web", "arxiv"))
            rep.pop("items")          # contains doc ids; compare the counts/structure
            return rep
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
