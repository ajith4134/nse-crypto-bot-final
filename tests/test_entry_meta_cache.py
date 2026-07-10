"""Regression: entry_meta.lookup must parse the sidecar file ONCE per file change.

2026-07-10 bug: lookup() ran state.load_json on every call; closed_view calls it per
trade row, so one cold view rebuild parsed the multi-MB sidecar ~1100 times while
holding the GIL — the whole dashboard process (including the live-browser login
stream) froze for seconds at a time.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as tstate


class EntryMetaCacheTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)
        from trading.crypto.freqtrade import entry_meta
        entry_meta._CACHE = None
        self.em = entry_meta

    def tearDown(self):
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()

    def test_lookup_parses_file_once_across_many_calls(self):
        self.em.record("BTC/USDT:USDT", "futures", {"psychology": {"fear": 0.2}})
        self.em._CACHE = None                       # simulate a cold process
        real = tstate.load_json
        with mock.patch.object(tstate, "load_json", side_effect=real) as lj:
            open_date = __import__("datetime").datetime.now().isoformat()
            for _ in range(50):
                self.em.lookup("BTC/USDT:USDT", "futures", open_date)
            self.assertEqual(lj.call_count, 1)      # one parse serves all 50 rows

    def test_record_updates_cache_and_lookup_sees_it(self):
        import datetime as dt
        import time
        self.em.record("ETH/USDT:USDT", "futures", {"k": "v1"})
        now = dt.datetime.now().isoformat()
        self.assertEqual(self.em.lookup("ETH/USDT:USDT", "futures", now), {"k": "v1"})
        time.sleep(0.05)
        self.em.record("ETH/USDT:USDT", "futures", {"k": "v2"})
        # lookup matches the entry NEAREST the open time: a fresh open_date must see the
        # just-recorded v2 through the cache (i.e. record() kept readers current)
        got = self.em.lookup("ETH/USDT:USDT", "futures", dt.datetime.now().isoformat())
        self.assertEqual(got.get("k"), "v2")

    def test_external_file_change_invalidates_cache(self):
        self.em.record("SOL/USDT:USDT", "futures", {"k": "old"})
        self.em._load()                             # warm the cache
        # another process rewrites the file (mtime moves)
        import json
        import os
        import time
        p = tstate._path(self.em.FILE)
        data = json.loads(p.read_text())
        data["futures|SOL/USDT:USDT"][0]["meta"] = {"k": "new"}
        p.write_text(json.dumps(data))
        os.utime(p, (time.time() + 5, time.time() + 5))   # guarantee a distinct mtime
        import datetime as dt
        got = self.em.lookup("SOL/USDT:USDT", "futures", dt.datetime.now().isoformat())
        self.assertEqual(got, {"k": "new"})


if __name__ == "__main__":
    unittest.main()
