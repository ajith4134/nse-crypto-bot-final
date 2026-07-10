"""state.update_json — locked cross-process merge (2026-07-10 review fix).

The crypto and NSE funnels write broker_sense_status.json from separate processes;
unlocked load→modify→save lost the other market's tile. update_json must merge only
the caller's top-level keys and survive concurrent writers.
"""
import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path


def _writer(state_dir: str, key: str, n: int) -> None:
    from trading import state
    state.STATE_DIR = Path(state_dir)
    for i in range(n):
        state.update_json("merge_test.json", {key: i})


class UpdateJsonTest(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        from trading import state
        state.STATE_DIR = self._old
        self._tmp.cleanup()

    def test_merges_only_own_keys(self):
        from trading import state
        state.save_json("merge_test.json", {"crypto": {"ts": 1}, "nse": {"ts": 2}})
        merged = state.update_json("merge_test.json", {"crypto": {"ts": 3}})
        self.assertEqual(merged["crypto"], {"ts": 3})
        self.assertEqual(merged["nse"], {"ts": 2})          # other market's tile intact

    def test_non_dict_file_recovers(self):
        from trading import state
        state.save_json("merge_test.json", ["not", "a", "dict"])
        merged = state.update_json("merge_test.json", {"k": 1})
        self.assertEqual(merged, {"k": 1})

    def test_concurrent_writers_lose_nothing(self):
        from trading import state
        procs = [mp.Process(target=_writer, args=(self._tmp.name, k, 25))
                 for k in ("a", "b", "c")]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
        final = state.load_json("merge_test.json", {})
        # every writer's LAST value must have survived the interleaving
        self.assertEqual({final.get("a"), final.get("b"), final.get("c")}, {24})


if __name__ == "__main__":
    unittest.main()
