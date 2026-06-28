"""trading/brain/observability.py — brain reasoning tracing (T8.8).

Records the brain's decision steps as structured spans so you can SEE why it acted —
feeding the Stream-of-Mind panel and giving auditable telemetry. Local + offline by
default (an in-memory ring of spans, JSON-able); **Langfuse** export turns on when
LANGFUSE_PUBLIC_KEY/SECRET_KEY are in the env (gated, like the other live integrations),
so the same traces ship to the Langfuse UI in production without changing call sites.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

try:
    from langfuse import Langfuse
    _HAVE_LANGFUSE = True
except Exception:  # pragma: no cover
    _HAVE_LANGFUSE = False


@dataclass
class Span:
    name: str
    kind: str = "thought"
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    ts: float = 0.0
    duration_ms: float = 0.0

    def as_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "inputs": self.inputs,
                "outputs": self.outputs, "meta": self.meta, "ts": self.ts,
                "duration_ms": round(self.duration_ms, 2)}


class BrainTracer:
    """In-memory span recorder (Stream-of-Mind) with optional Langfuse export."""

    def __init__(self, *, maxlen: int = 200, enabled_langfuse: bool | None = None,
                 clock=None):
        self.maxlen = maxlen
        self._spans: list[Span] = []
        self._clock = clock or time.time          # injectable for deterministic tests
        self._lf = None
        want = self._env_langfuse() if enabled_langfuse is None else enabled_langfuse
        if want and _HAVE_LANGFUSE:
            try:
                self._lf = Langfuse()             # reads LANGFUSE_* from env
            except Exception:
                self._lf = None

    @staticmethod
    def _env_langfuse() -> bool:
        return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))

    @property
    def backend(self) -> str:
        return "langfuse" if self._lf is not None else "local"

    def record(self, name: str, *, kind: str = "thought", inputs: dict | None = None,
               outputs: dict | None = None, meta: dict | None = None,
               duration_ms: float = 0.0) -> Span:
        span = Span(name=name, kind=kind, inputs=inputs or {}, outputs=outputs or {},
                    meta=meta or {}, ts=float(self._clock()), duration_ms=duration_ms)
        self._spans.append(span)
        if len(self._spans) > self.maxlen:
            self._spans = self._spans[-self.maxlen:]
        if self._lf is not None:
            try:  # pragma: no cover - network
                self._lf.trace(name=name, input=span.inputs, output=span.outputs,
                               metadata=span.meta)
            except Exception:
                pass
        return span

    @contextmanager
    def trace(self, name: str, *, kind: str = "thought", **inputs):
        t0 = self._clock()
        box = {"outputs": {}}
        try:
            yield box
        finally:
            self.record(name, kind=kind, inputs=inputs, outputs=box.get("outputs", {}),
                        duration_ms=(self._clock() - t0) * 1000.0)

    def recent(self, n: int = 20) -> list[dict]:
        return [s.as_dict() for s in self._spans[-n:]]

    def stream_of_mind(self, n: int = 20) -> list[str]:
        """Render recent spans as human thought-lines for the dashboard panel."""
        out = []
        for s in self._spans[-n:]:
            detail = s.outputs or s.inputs
            bits = ", ".join(f"{k}={v}" for k, v in list(detail.items())[:3])
            out.append(f"{s.name}: {bits}" if bits else s.name)
        return out

    def status(self) -> dict:
        return {"backend": self.backend, "langfuse_installed": _HAVE_LANGFUSE,
                "n_spans": len(self._spans)}
