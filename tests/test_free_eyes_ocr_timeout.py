"""tests/test_free_eyes_ocr_timeout.py — the OCR read must never block the caller forever.

Regression for the 2026-07-11 mirror-freeze: free_eyes.glance did `_ocr_pool().submit(...).result()`
with NO timeout, so a wedged OCR engine hung the funnel's browser hand → the whole trade loop. The
bounded _ocr_safe must return [] within the cap even when OCR hangs.
"""
import os
import time
import unittest
from unittest import mock

from trading.brain.vision import free_eyes


class TestOCRTimeout(unittest.TestCase):
    def test_ocr_safe_bounded_when_engine_hangs(self):
        os.environ["FREE_EYES_OCR_TIMEOUT"] = "1"
        try:
            def _hang(_shot):
                time.sleep(30)          # simulate a wedged OCR engine
                return ["never"]
            with mock.patch.object(free_eyes, "_ocr_read", _hang):
                t0 = time.monotonic()
                out = free_eyes._ocr_safe(b"\xff\xd8\xff")
                elapsed = time.monotonic() - t0
            self.assertEqual(out, [])                    # degraded to empty, not the hung result
            self.assertLess(elapsed, 5.0)                # returned near the 1s cap, did NOT block 30s
        finally:
            os.environ.pop("FREE_EYES_OCR_TIMEOUT", None)

    def test_ocr_safe_returns_reads_when_fast(self):
        with mock.patch.object(free_eyes, "_ocr_read", lambda _s: ["BTC", "24h"]):
            self.assertEqual(free_eyes._ocr_safe(b"x"), ["BTC", "24h"])

    def test_ocr_safe_never_raises_on_engine_error(self):
        with mock.patch.object(free_eyes, "_ocr_read", mock.Mock(side_effect=RuntimeError("boom"))):
            self.assertEqual(free_eyes._ocr_safe(b"x"), [])


if __name__ == "__main__":
    unittest.main()
