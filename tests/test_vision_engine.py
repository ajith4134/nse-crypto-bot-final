"""Tests for the free vision engine (core.llm.vision_chat) — the brain's FREE eyes.

Covers: image normalization (bytes/path/base64/data-url → data URL), multimodal message
construction, vision-provider selection + failover, total_timeout budget, and honest
degradation when no vision key is present. No network: LiteLLM is stubbed.
"""
from __future__ import annotations

import base64
import os
import tempfile
import unittest
from unittest import mock

from core import llm


class TestImageDataUrl(unittest.TestCase):
    def test_raw_bytes(self):
        url = llm._image_data_url(b"\x89PNG\r\n")
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), b"\x89PNG\r\n")

    def test_already_data_url_passthrough(self):
        u = "data:image/png;base64,AAAA"
        self.assertEqual(llm._image_data_url(u), u)

    def test_file_path_jpeg_mime(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff\xe0jpegbytes")
            path = f.name
        try:
            url = llm._image_data_url(path)
            self.assertTrue(url.startswith("data:image/jpeg;base64,"))
            self.assertEqual(base64.b64decode(url.split(",", 1)[1]), b"\xff\xd8\xff\xe0jpegbytes")
        finally:
            os.unlink(path)

    def test_bare_base64_string(self):
        raw = base64.b64encode(b"hello").decode()
        url = llm._image_data_url(raw)
        self.assertEqual(url, f"data:image/png;base64,{raw}")

    def test_bad_type_raises(self):
        with self.assertRaises(TypeError):
            llm._image_data_url(1234)


class TestVisionChat(unittest.TestCase):
    def _fake_completion(self, reply="TOP GAINER: SUMICHEM +43%"):
        def _c(model, messages, **kw):
            self._seen = {"model": model, "messages": messages, "kw": kw}
            return {"choices": [{"message": {"content": reply}}]}
        return _c

    def test_builds_multimodal_message_and_returns_reading(self):
        fake = mock.MagicMock()
        fake.completion.side_effect = self._fake_completion()
        cands = [("gemini/gemini-2.0-flash", {})]
        with mock.patch.dict("sys.modules", {"litellm": fake}), \
             mock.patch.object(llm, "_candidates", return_value=cands):
            out = llm.vision_chat("Read this screen", b"\x89PNGdata", system="You are eyes")
        self.assertIn("SUMICHEM", out)
        msgs = self._seen["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        user = msgs[-1]
        self.assertEqual(user["content"][0], {"type": "text", "text": "Read this screen"})
        self.assertEqual(user["content"][1]["type"], "image_url")
        self.assertTrue(user["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_failover_to_next_provider(self):
        calls = []

        def _c(model, messages, **kw):
            calls.append(model)
            if model == "gemini/gemini-2.0-flash":
                raise RuntimeError("429 rate limit")
            return {"choices": [{"message": {"content": "ok from groq"}}]}

        fake = mock.MagicMock()
        fake.completion.side_effect = _c
        cands = [("gemini/gemini-2.0-flash", {}), ("groq/vision", {})]
        with mock.patch.dict("sys.modules", {"litellm": fake}), \
             mock.patch.object(llm, "_candidates", return_value=cands):
            out = llm.vision_chat("look", [b"img1", b"img2"])
        self.assertEqual(out, "ok from groq")
        self.assertEqual(calls, ["gemini/gemini-2.0-flash", "groq/vision"])

    def test_multiple_images_all_attached(self):
        fake = mock.MagicMock()
        fake.completion.side_effect = self._fake_completion("two images seen")
        cands = [("gemini/gemini-2.0-flash", {})]
        with mock.patch.dict("sys.modules", {"litellm": fake}), \
             mock.patch.object(llm, "_candidates", return_value=cands):
            llm.vision_chat("compare", [b"a", b"b", b"c"])
        imgs = [c for c in self._seen["messages"][-1]["content"] if c["type"] == "image_url"]
        self.assertEqual(len(imgs), 3)

    def test_no_vision_provider_raises(self):
        with mock.patch.object(llm, "_candidates", return_value=[]):
            with self.assertRaises(llm.NoLLMConfigured):
                llm.vision_chat("x", b"img")

    def test_total_timeout_stops_chain(self):
        # first provider slow-fails; total_timeout already exhausted → don't try the rest
        import time as _t

        def _c(model, messages, **kw):
            if model == "slow/one":
                _t.sleep(0.05)
                raise RuntimeError("boom")
            raise AssertionError("second provider must not be tried after budget exhausted")

        fake = mock.MagicMock()
        fake.completion.side_effect = _c
        cands = [("slow/one", {}), ("never/two", {})]
        with mock.patch.dict("sys.modules", {"litellm": fake}), \
             mock.patch.object(llm, "_candidates", return_value=cands):
            with self.assertRaises(RuntimeError):
                llm.vision_chat("x", b"img", total_timeout=0.01)

    def test_vision_available_and_order(self):
        cands = [("gemini/gemini-2.0-flash", {}), ("groq/x", {})]
        with mock.patch.object(llm, "_candidates", return_value=cands):
            self.assertTrue(llm.vision_available())
            self.assertEqual(llm.vision_order(), ["gemini", "groq"])
        with mock.patch.object(llm, "_candidates", return_value=[]):
            self.assertFalse(llm.vision_available())


if __name__ == "__main__":
    unittest.main()
