"""cognition/embodiment.py — the P4.8 orchestrator: a personality with senses.

``Embodiment`` ties the four P4.8 faculties into one coherent "personality" layer on top of the
thinking brain (P4.5) and stream-of-mind (P4.6):

  * **Identity** (persona/human self-model, persistent via Letta blocks),
  * **Mood** (affect channel — emotion read + a persistent EMA mood),
  * **InternalDebate** (society of mind — specialist roles argue → vote),
  * **Senses** (multimodal — hear/speak/see).

It exposes one method per "experience": ``perceive_text`` (read + feel), ``deliberate`` (internal
debate, mood-aware), ``hear``/``speak``/``see`` (senses), and ``introspect`` (who am I + how do I
feel right now). Reading something charged shifts the mood, which is reflected back into the
persona — a self-model that genuinely updates. Everything degrades offline (stubs) and is
deterministic with injected stubs, like the rest of Phase 4.
"""
from __future__ import annotations

from cognition.affect import Mood
from cognition.identity import Identity
from cognition.multimodal import Ears, Eyes, Voice
from cognition.society import InternalDebate


class Embodiment:
    def __init__(self, *, identity_path: str = "state/identity.json", chat=None,
                 mood: Mood | None = None):
        self.identity = Identity(identity_path)
        self.mood = mood or Mood()
        self.debate = InternalDebate(chat=chat)

    # ── experience: read + feel ─────────────────────────────────────────────────────
    def perceive_text(self, text: str) -> dict:
        """Read text: get the emotion, shift the running mood, reflect it into the persona."""
        feeling = self.mood.read(text)
        self.identity.reflect_mood(feeling["mood"], feeling["valence"])
        return {"text": text[:120], "feeling": feeling,
                "mood": self.mood.label(), "valence": round(self.mood.valence, 3)}

    # ── society of mind, mood-aware ─────────────────────────────────────────────────
    def deliberate(self, question: str, *, context: str = "") -> dict:
        """Internal debate → verdict, annotated with the brain's current mood."""
        out = self.debate.debate(question, context=context)
        out["mood"] = self.mood.label()
        out["valence"] = round(self.mood.valence, 3)
        return out

    # ── senses ──────────────────────────────────────────────────────────────────────
    def hear(self, audio_path: str) -> dict:
        return Ears.transcribe(audio_path)

    def speak(self, text: str, *, out_path: str, voice: str = "af_sky") -> dict:
        return Voice.speak(text, out_path=out_path, voice=voice)

    def see(self, image_path: str, *, question: str = "Describe this image.") -> dict:
        return Eyes.describe(image_path, question=question)

    # ── introspection ───────────────────────────────────────────────────────────────
    def introspect(self) -> dict:
        return {"identity": self.identity.card(), "mood": self.mood.status(),
                "feels": self.mood.label()}

    def remember(self, fact: str) -> None:
        self.identity.remember(fact)

    def status(self) -> dict:
        from cognition import multimodal
        return {"identity": self.identity.status(), "mood": self.mood.status(),
                "society": self.debate.status(), "senses": multimodal.status()}
