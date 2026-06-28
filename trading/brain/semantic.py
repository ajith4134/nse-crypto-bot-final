"""trading/brain/semantic.py — semantic (text) memory via mem0 (T8.4).

Complements the numeric Case-Based experience bank with a SEMANTIC memory of free-text
lessons/reflections ("breakouts after 2pm IST on low-volume NSE names tend to fail"),
the kind of knowledge that doesn't fit a feature vector. The engine is **mem0** (LLM-
extracted, consolidated, vector-searchable memory). Because mem0 needs an LLM + embedder,
this follows the same enabled-when-configured pattern as the Telegram channel:

  • configured (MEM0_ENABLED=1 + an LLM/embedder reachable) → real mem0 (extract/consolidate)
  • otherwise → a functional DRY-RUN note store (in-memory, keyword-scored search)

So the capability ships and is fully offline-testable; the LLM path turns on with config.
Secrets-safe: any API key comes from the environment, never hard-coded or logged.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

try:
    from mem0 import Memory as _Mem0Memory
    _HAVE_MEM0 = True
except Exception:  # pragma: no cover
    _HAVE_MEM0 = False


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class SemanticMemory:
    """Free-text trade-lesson memory. Real mem0 when configured, else a dry-run store."""

    user_id: str = "brain"
    enabled: bool | None = None              # None → auto from env (MEM0_ENABLED)
    config: dict | None = None               # explicit mem0 config (overrides env)
    _notes: list = field(default_factory=list, init=False)   # dry-run mirror
    _mem: object = field(default=None, init=False)
    _backend: str = field(default="dry-run", init=False)

    def __post_init__(self) -> None:
        want = _env_truthy("MEM0_ENABLED") if self.enabled is None else bool(self.enabled)
        if want and _HAVE_MEM0:
            try:
                cfg = self.config or self._config_from_env()
                self._mem = _Mem0Memory.from_config(cfg) if cfg else _Mem0Memory()
                self._backend = "mem0"
            except Exception:                # any init failure → safe dry-run
                self._mem = None
                self._backend = "dry-run"

    @staticmethod
    def _config_from_env() -> dict | None:
        """Build a mem0 config from an OpenAI-compatible provider in the env, if present."""
        key = os.environ.get("OPENAI_API_KEY")
        base = os.environ.get("OPENAI_BASE_URL")
        if not key:
            return None
        llm = {"provider": "openai", "config": {"model": os.environ.get("MEM0_LLM_MODEL",
                                                                       "gpt-4o-mini")}}
        if base:
            llm["config"]["openai_base_url"] = base
        return {"llm": llm}

    @property
    def backend(self) -> str:
        return self._backend

    # ── ingest ──────────────────────────────────────────────────────────────────
    def add(self, text: str, *, metadata: dict | None = None) -> dict:
        if not text:
            return {"ok": False, "reason": "empty text"}
        if self._mem is not None:
            try:
                self._mem.add(text, user_id=self.user_id, metadata=metadata or {})
                return {"ok": True, "backend": "mem0"}
            except Exception as exc:         # degrade to dry-run on runtime failure
                self._backend = "dry-run(mem0-error)"
                self._notes.append({"text": text, "metadata": metadata or {}})
                return {"ok": True, "backend": self._backend, "detail": str(exc)[:80]}
        self._notes.append({"text": text, "metadata": metadata or {}})
        return {"ok": True, "backend": "dry-run"}

    def add_trade_lesson(self, trade, lesson: str) -> dict:
        d = trade.to_dict() if hasattr(trade, "to_dict") else dict(trade)
        meta = {"trade_id": d.get("trade_id"), "symbol": d.get("symbol"),
                "market": d.get("market"), "net_pnl": d.get("net_pnl")}
        return self.add(lesson, metadata=meta)

    # ── retrieve ────────────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 5) -> list[dict]:
        if self._mem is not None:
            try:
                res = self._mem.search(query, user_id=self.user_id, limit=k)
                return res.get("results", res) if isinstance(res, dict) else res
            except Exception:
                pass
        # dry-run keyword scoring
        terms = set(re.findall(r"\w+", query.lower()))
        scored = []
        for n in self._notes:
            words = set(re.findall(r"\w+", n["text"].lower()))
            overlap = len(terms & words)
            if overlap:
                scored.append((overlap, n))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"memory": n["text"], "metadata": n["metadata"], "score": s}
                for s, n in scored[:k]]

    def all(self) -> list[dict]:
        if self._mem is not None:
            try:
                res = self._mem.get_all(user_id=self.user_id)
                return res.get("results", res) if isinstance(res, dict) else res
            except Exception:
                pass
        return list(self._notes)

    def status(self) -> dict:
        n = len(self._notes) if self._mem is None else None
        return {"backend": self._backend, "mem0_installed": _HAVE_MEM0,
                "enabled": self._mem is not None, "n_notes": n, "user_id": self.user_id}
