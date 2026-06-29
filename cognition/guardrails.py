"""cognition/guardrails.py — the constitution / self-audit rail (Phase P4.5).

A runtime **constitution** the brain's every answer must pass before it reaches the user —
the "conscience" layer. Reuse-first: a real **NeMo-Guardrails** ``LLMRails`` instance holds a
genuine Colang output-rail config (parsed + validated by the real engine, and the runtime when
an LLM is configured). The constitutional principles are registered as NeMo *output-rail
actions*; offline (no LLM) the same actions run deterministically — so the constitution is
enforced either way, with no network and no API key.

Principles enforced on every output:
  1. **secrets-safe** (project rule) — never emit an API key / token / password; such spans are
     redacted, not leaked. Hard-fails the audit.
  2. **grounded / no-fabrication** — if the answer claims facts, they should trace to recalled
     memory; an ungrounded confident claim is flagged.
  3. **honest-uncertainty** — when the brain has abstained (calibration said "ask the human"),
     the output must not assert a confident answer.
  4. **non-harmful** — block overtly harmful/destructive instructions.

``audit()`` returns {ok, violations, safe_text} — safe_text has secrets redacted so a partial
failure still degrades safely. Deterministic, CPU-only, offline.
"""
from __future__ import annotations

import re

# secret patterns (kept conservative — redact, never echo). Aligned with the project's
# "secrets-safe" rule: real keys must never be committed or echoed.
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),                       # OpenAI-style
    re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*\S+", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                           # AWS access key id
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),                       # GitHub PAT
]
_HARM_PATTERNS = [
    re.compile(r"\b(rm\s+-rf\s+/|drop\s+table|delete\s+from\s+\w+\s*;?\s*$)", re.I),
    re.compile(r"\bhow to (make|build) a (bomb|weapon|explosive)\b", re.I),
]

_COLANG = """
define flow constitution audit
  $ok = execute constitution_check(text=$bot_message)
  if not $ok
    bot refuse
define bot refuse
  "[blocked: violates the brain's constitution]"
"""
_YAML = "models: []\nrails:\n  output:\n    flows:\n      - constitution audit\n"


class Constitution:
    """Runtime self-audit rails over the brain's outputs (NeMo-Guardrails)."""

    def __init__(self):
        self.engine = "programmatic"
        self._rails = None
        self._build_rails()

    def _build_rails(self) -> None:
        """Parse+hold a real NeMo-Guardrails constitution (the runtime when an LLM is set)."""
        try:
            from nemoguardrails import LLMRails, RailsConfig
            from nemoguardrails.actions import action

            @action(name="constitution_check")
            async def constitution_check(text: str = ""):           # noqa: D401 (NeMo action)
                return self.audit(text or "")["ok"]

            cfg = RailsConfig.from_content(colang_content=_COLANG, yaml_content=_YAML)
            rails = LLMRails(cfg)
            rails.register_action(constitution_check, "constitution_check")
            self._rails = rails
            self.engine = "nemoguardrails"
        except Exception:
            self._rails = None
            self.engine = "programmatic"

    # ── individual principles ───────────────────────────────────────────────────────
    @staticmethod
    def _find_secrets(text: str) -> list[str]:
        hits = []
        for pat in _SECRET_PATTERNS:
            hits += pat.findall(text)
        return [h if isinstance(h, str) else h[0] for h in hits]

    @staticmethod
    def redact(text: str) -> str:
        for pat in _SECRET_PATTERNS:
            text = pat.sub("[REDACTED]", text)
        return text

    @staticmethod
    def _harmful(text: str) -> bool:
        return any(p.search(text) for p in _HARM_PATTERNS)

    # ── the audit ───────────────────────────────────────────────────────────────────
    def audit(self, text: str, *, grounded_in: list | None = None,
              abstained: bool = False) -> dict:
        """Check an output against the constitution. Returns {ok, violations, safe_text}."""
        text = text or ""
        violations: list[str] = []

        if self._find_secrets(text):
            violations.append("secrets-safe: output contained a secret/API key (redacted)")
        if self._harmful(text):
            violations.append("non-harmful: output contained a harmful/destructive instruction")
        if abstained and self._asserts_answer(text):
            violations.append("honest-uncertainty: asserted an answer while flagged to abstain")
        if grounded_in is not None and not grounded_in and self._asserts_answer(text):
            violations.append("grounded: confident claim not traceable to any recalled memory")

        safe = self.redact(text)
        ok = not violations
        return {"ok": ok, "violations": violations, "safe_text": safe, "engine": self.engine}

    @staticmethod
    def _asserts_answer(text: str) -> bool:
        # a non-trivial, non-hedged statement counts as "asserting an answer"
        t = text.strip().lower()
        if len(t) < 12:
            return False
        hedges = ("i don't know", "not sure", "not confident", "ask the human", "cannot answer",
                  "no relevant memory", "escalat", "abstain", "(no llm", "confirm or add")
        return not any(h in t for h in hedges)

    def status(self) -> dict:
        return {"engine": self.engine,
                "principles": ["secrets-safe", "grounded", "honest-uncertainty", "non-harmful"],
                "rails_loaded": self._rails is not None}
