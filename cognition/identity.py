"""cognition/identity.py — persistent self-model / persona (Phase P4.8).

The brain's stable IDENTITY — who it is and who it's working with — that survives across
sessions. Reuse-first: the already-installed **Letta** ``ChatMemory`` core-memory blocks
(``persona`` / ``human``) — the exact offline, embedded, no-server, no-key primitive the project
already uses in memory/hybrid_memory.py. Letta holds the blocks in memory; we add the missing
piece (durable persistence) by serialising the block values to JSON on disk, so the persona is
truly persistent. Degrades to a plain dict if Letta is unavailable — always works, fully offline.

The persona can also *evolve*: ``remember(fact)`` appends a durable note to the human block (how
the operator's preferences accrue over time) and ``reflect_mood(mood)`` records the brain's
current felt state into the persona — a self-model that updates, not a static string.
"""
from __future__ import annotations

import json
import os

DEFAULT_PERSONA = ("I am the ML Network Brain — a CPU-first network of hundreds of prediction "
                   "model-nodes with a learning brain. I reason over my own memory, stay "
                   "calibrated, ask for help when unsure, and improve myself by inventing and "
                   "benchmark-gating new nodes. I am honest about what I know and what I don't.")
DEFAULT_HUMAN = ("The operator builds me: CPU-first, reuse-first, trades NSE + crypto, wants "
                 "real wired capability over decoration.")


class Identity:
    """A durable persona/human self-model over Letta core-memory blocks (offline, embedded)."""

    def __init__(self, path: str = "state/identity.json"):
        self.path = path
        saved = {}
        if os.path.exists(path):
            try:
                saved = json.load(open(path, encoding="utf-8"))
            except Exception:
                saved = {}
        persona = saved.get("persona", DEFAULT_PERSONA)
        human = saved.get("human", DEFAULT_HUMAN)
        self.notes: list[str] = saved.get("notes", [])
        self._mem = None
        self.engine = "dict"
        try:
            from letta.schemas.memory import ChatMemory
            self._mem = ChatMemory(persona=persona, human=human)
            self.engine = "letta"
        except Exception:
            self._mem = {"persona": persona, "human": human}      # dict fallback

    # ── block access (works over Letta or the dict fallback) ───────────────────────
    def get(self, label: str) -> str:
        if self.engine == "letta":
            try:
                return self._mem.get_block(label).value
            except Exception:
                return ""
        return self._mem.get(label, "")

    def set(self, label: str, value: str) -> None:
        if self.engine == "letta":
            try:
                self._mem.get_block(label).value = value
            except Exception:
                pass
        else:
            self._mem[label] = value

    # ── evolution ──────────────────────────────────────────────────────────────────
    def remember(self, fact: str) -> None:
        """Accrue a durable fact about the operator/world into the human block + notes."""
        fact = (fact or "").strip()
        if not fact:
            return
        self.notes.append(fact)
        human = self.get("human")
        self.set("human", (human + f"\n- {fact}").strip())
        self.save()

    def reflect_mood(self, mood: str, valence: float) -> None:
        """Record the brain's current felt state into the persona (a self-model that updates)."""
        base = self.get("persona").split("\n[mood:")[0].rstrip()
        self.set("persona", f"{base}\n[mood: {mood} (valence {round(valence, 2)})]")
        self.save()

    def save(self) -> None:
        blocks = {"persona": self.get("persona"), "human": self.get("human"), "notes": self.notes}
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            json.dump(blocks, open(self.path, "w", encoding="utf-8"), indent=2)
        except Exception:
            pass

    def card(self) -> dict:
        return {"persona": self.get("persona"), "human": self.get("human"),
                "notes": self.notes[-8:], "engine": self.engine}

    def status(self) -> dict:
        return {"engine": self.engine, "persona_chars": len(self.get("persona")),
                "human_chars": len(self.get("human")), "notes": len(self.notes),
                "persisted_to": self.path}
