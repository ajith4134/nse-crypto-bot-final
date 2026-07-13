"""Tests for feed_selfheal (adopt item 2) — web-feed schema-drift detection + diagnosis.
Protobuf (Upstox) drift runs protobuf-inspector on a captured frame; JSON (Binance) drift
reports the observed keys. A healthy feed never alerts; nothing ever raises into the hot path."""
import unittest

from trading.broker_sense import feed_selfheal as fs

# field1 varint=5, field2 varint=300, field3 len-delim "hi" — a valid protobuf blob
_BLOB = bytes([0x08, 0x05, 0x10, 0xAC, 0x02, 0x1A, 0x02, 0x68, 0x69])


class _Base(unittest.TestCase):
    def setUp(self):
        fs._STATE.clear()

    def tearDown(self):
        fs._STATE.clear()


class TestProtobuf(_Base):
    def test_drift_detected_and_structure_inferred(self):
        for _ in range(fs._WINDOW):
            fs.note("upstox", stored=0, raw=_BLOB)          # frames flowing, nothing decodes
        st = fs.status()["brokers"]["upstox"]
        self.assertEqual(st["drift_events"], 1)
        self.assertEqual(st["decode_rate"], 0.0)
        self.assertIn("varint", st["last_structure"])       # protobuf-inspector parsed it

    def test_healthy_feed_never_alerts(self):
        for _ in range(fs._WINDOW * 2):
            fs.note("upstox", stored=3, raw=None)
        st = fs.status()["brokers"]["upstox"]
        self.assertEqual(st["drift_events"], 0)
        self.assertEqual(st["decode_rate"], 1.0)

    def test_inspect_protobuf_direct(self):
        out = fs.inspect_protobuf(_BLOB)
        self.assertIn("varint", out)
        self.assertIn("5", out)


class TestJson(_Base):
    def test_json_drift_reports_keys(self):
        for _ in range(fs._WINDOW):
            fs.note_json("binance", {"stream": "!ticker@arr", "data": {"weird": 1}}, ok=False)
        st = fs.status()["brokers"]["binance"]
        self.assertEqual(st["drift_events"], 1)
        self.assertIn("keys", st["last_structure"])

    def test_json_healthy_no_alert(self):
        for _ in range(fs._WINDOW):
            fs.note_json("binance", {"stream": "!ticker@arr", "data": []}, ok=True)
        self.assertEqual(fs.status()["brokers"]["binance"]["drift_events"], 0)

    def test_never_raises_on_junk(self):
        # note_json must survive non-dict / weird input (hot-path safety). Control-frame
        # gating (skip frames without a "stream") is the CALLER's job in binance_stream.
        for junk in (None, 42, "x", {"stream": "!ticker", "data": None}):
            fs.note_json("binance", junk, ok=False)         # must not raise
        fs.note("upstox", stored=0, raw=None)               # no sample → no crash
        self.assertTrue(fs.status()["enabled"])


if __name__ == "__main__":
    unittest.main()
