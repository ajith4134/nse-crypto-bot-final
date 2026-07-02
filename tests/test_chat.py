"""P4.1 acceptance tests: the brain-chat plumbing is well-formed and degrades gracefully.

Offline only — never makes a live LLM call (CI has no network). Verifies the provider table,
secrets-safe selection, and that chat() always returns the {reply, sources, thoughts, error}
contract without crashing (the graceful no-key / empty-message paths).
"""
from __future__ import annotations

import os
import unittest

from core import chat_brain, llm


class TestChat(unittest.TestCase):
    def test_provider_table_wellformed(self):
        self.assertTrue(llm.PROVIDERS)
        for row in llm.PROVIDERS:
            self.assertEqual(len(row), 4)              # (config key, model, litellm env var, api_base)
            key, model, env, api_base = row
            self.assertTrue(key and model)
            self.assertTrue(env or api_base)           # native providers set env; OpenAI-compat set api_base
            self.assertIn("/", model)                  # litellm "provider/model" form

    def test_active_model_no_crash(self):
        m = llm.active_model()                          # tuple or None depending on .env
        self.assertTrue(m is None or (isinstance(m, tuple) and len(m) == 2))

    def test_empty_message_is_graceful(self):
        out = chat_brain.chat("   ")
        self.assertEqual(set(out), {"reply", "sources", "thoughts", "error"})
        self.assertEqual(out["error"], "empty message")

    def test_stream_yields_events(self):
        self.assertTrue(hasattr(llm, "chat_stream") and hasattr(chat_brain, "chat_stream"))
        evs = list(chat_brain.chat_stream("   "))          # empty → single error event, no network
        self.assertEqual(evs, [{"type": "error", "error": "empty message"}])

    @unittest.skipIf(os.getenv("ML_NETWORK_SKIP_HEAVY"),
                     "builds KnowledgeBrain + may call the network")
    def test_chat_returns_contract(self):
        """A normal message returns the full contract; if no LLM/network, error is a
        string (never an exception). We assert structure, not live content."""
        out = chat_brain.chat("hello brain")
        self.assertEqual(set(out), {"reply", "sources", "thoughts", "error"})
        self.assertIsInstance(out["sources"], list)
        self.assertIsInstance(out["thoughts"], list)
        self.assertTrue(out["thoughts"])               # always emits at least one thought


if __name__ == "__main__":
    unittest.main(verbosity=2)
