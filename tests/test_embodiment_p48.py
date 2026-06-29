"""Phase P4.8 (Multimodal + identity + society + affect) acceptance tests.

Deterministic and fast: BRAIN_NO_MODELS=1 forces the model-free path for the heavy senses, the
society debate uses an INJECTED stub chat (no LLM/network), and identity persists to a temp file.
The real models (GoEmotions/whisper/kokoro/BLIP) are exercised by run_embodiment_p48.py; here we
prove the WIRING + the offline-degrade contract + the deterministic faculties.

Mirrors tests/test_thinking_p45.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import os
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore")

os.environ["BRAIN_NO_MODELS"] = "1"      # force the fast, model-free senses path for the suite

from cognition.affect import Mood
from cognition.embodiment import Embodiment
from cognition.identity import Identity
from cognition.society import InternalDebate


class TestAffect(unittest.TestCase):
    def test_valence_sign_tracks_sentiment(self):
        m = Mood()
        pos = m.read("We won a huge profit, a great success and joy!")
        self.assertGreater(pos["valence"], 0)
        neg = Mood().read("A terrible crash, heavy loss, fear and anger.")
        self.assertLess(neg["valence"], 0)

    def test_running_mood_ema_and_label(self):
        m = Mood(ema=0.5)
        for _ in range(3):
            m.read("great win, profit, joy, success")
        self.assertGreater(m.valence, 0)
        self.assertIn(m.label(), ("content", "excited"))

    def test_degrades_to_real_lexicon_or_stub(self):
        # BRAIN_NO_MODELS=1 → never the goemotions tier; nrclex (real lexicon) or stub
        eng = Mood().read("good win")["engine"]
        self.assertIn(eng, ("nrclex", "stub"))


class TestIdentity(unittest.TestCase):
    def test_persists_and_reloads(self):
        p = os.path.join(tempfile.mkdtemp(), "id.json")
        a = Identity(p)
        a.remember("Operator prefers blueprint-named tools.")
        a.reflect_mood("content", 0.4)
        self.assertTrue(os.path.exists(p))
        b = Identity(p)                                   # reload from disk
        self.assertIn("blueprint-named", b.get("human"))
        self.assertEqual(len(b.notes), 1)

    def test_engine_is_letta_or_dict(self):
        self.assertIn(Identity(os.path.join(tempfile.mkdtemp(), "id.json")).engine,
                      ("letta", "dict"))


class TestSociety(unittest.TestCase):
    def test_debate_votes_and_verdict_with_stub_chat(self):
        # injected chat → deterministic 'yes' from every role → consensus yes
        chat = lambda msgs: "Strong upside, supports growth. VOTE: yes"
        d = InternalDebate(chat=chat)
        out = d.debate("Add a new node?", context="accuracy gains")
        self.assertEqual(out["verdict"], "yes")
        self.assertTrue(out["consensus"])
        self.assertEqual(out["mode"], "llm")
        self.assertEqual(set(out["votes"]), {"bull", "bear", "risk"})

    def test_offline_stub_is_deterministic(self):
        # a chat that yields nothing simulates "no LLM" → deterministic heuristic vote
        d = InternalDebate(chat=lambda msgs: None)
        a = d.debate("market is up with strong gains and profit")
        b = d.debate("market is up with strong gains and profit")
        self.assertEqual(a["verdict"], b["verdict"])
        self.assertEqual(a["mode"], "stub")


class TestSensesDegrade(unittest.TestCase):
    def test_senses_degrade_to_stub_when_models_off(self):
        from cognition.multimodal import Ears, Eyes, Voice
        self.assertEqual(Ears.transcribe("nope.wav")["engine"], "stub")
        self.assertFalse(Voice.speak("hi", out_path="/tmp/x.wav")["ok"])
        self.assertEqual(Eyes.describe("nope.png")["engine"], "stub")


class TestEmbodiment(unittest.TestCase):
    def setUp(self):
        self.emb = Embodiment(identity_path=os.path.join(tempfile.mkdtemp(), "id.json"),
                              chat=lambda msgs: "supportive case. VOTE: yes")

    def test_perceive_shifts_mood_and_persona(self):
        before = self.emb.mood.valence
        self.emb.perceive_text("Huge win, great profit and success!")
        self.assertNotEqual(self.emb.mood.valence, before)
        self.assertIn("mood:", self.emb.identity.get("persona"))     # self-model updated

    def test_deliberate_returns_verdict_with_mood(self):
        out = self.emb.deliberate("Add a node?")
        self.assertIn(out["verdict"], ("yes", "no", "tie"))
        self.assertIn("mood", out)

    def test_introspect_and_status(self):
        self.emb.remember("works CPU-first")
        intro = self.emb.introspect()
        self.assertIn("persona", intro["identity"])
        st = self.emb.status()
        for k in ("identity", "mood", "society", "senses"):
            self.assertIn(k, st)


class TestDemo(unittest.TestCase):
    def test_build_demo_snapshot_stub_path(self):
        import json

        from run_embodiment_p48 import build_demo_embodiment
        snap = build_demo_embodiment()
        self.assertEqual(snap["phase"], "P4.8")
        self.assertEqual(len(snap["affect"]["reads"]), 3)
        self.assertIn("verdict", snap["society"])
        self.assertIn("senses", snap)
        json.dumps(snap, default=str)                                # dashboard-serialisable


if __name__ == "__main__":
    unittest.main(verbosity=2)
