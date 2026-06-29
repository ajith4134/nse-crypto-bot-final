"""core/observability.py — P4.6 durable observability (the brain "watches itself") via Langfuse.

Reuse-first, secrets-safe, offline-safe — mirrors core/llm.py exactly:

  * keys (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST) are read by NAME from
    config.settings (gitignored .env); values are never logged or returned.
  * langfuse is imported LAZILY inside the accessor, so import-time stays network-free.
  * with NO keys configured the real Langfuse client self-disables to a SILENT NO-OP — every
    span/trace call runs without network and without raising — so the brain is fully traceable
    in code while tests/CLI demos stay deterministic and offline (exactly like NoLLMConfigured).
  * the moment all three keys resolve (Langfuse cloud or a self-hosted LANGFUSE_HOST), the same
    spans become a DURABLE trace store the brain can read back (replay its own thought-history).

Public surface:
  enabled() -> bool                      # are real keys configured?
  tracer()  -> langfuse client | None    # the (possibly no-op) client, or None if dep missing
  trace(name, **meta) -> context manager # a root observation; .span()/.event() nest under it
  flush()                                # push batched spans before a short-lived process exits
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

from config import settings

# Langfuse prints a one-line stderr warning when constructed without keys; silence it so the
# offline no-op path is clean (we surface configured/!configured via status() instead).
logging.getLogger("langfuse").setLevel(logging.CRITICAL)

# (config key in .env, env var the langfuse SDK reads).
_KEYS = [
    ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY"),
    ("LANGFUSE_SECRET_KEY", "LANGFUSE_SECRET_KEY"),
    ("LANGFUSE_HOST", "LANGFUSE_HOST"),
]


def enabled() -> bool:
    """True only when both Langfuse keys are configured (host optional → cloud default)."""
    return bool(settings.get("LANGFUSE_PUBLIC_KEY") and settings.get("LANGFUSE_SECRET_KEY"))


def _export_keys() -> None:
    """Map our .env key NAMES into the env vars the langfuse SDK expects (values stay secret)."""
    import os
    for key, env in _KEYS:
        val = settings.get(key)
        if val and not os.getenv(env):
            os.environ[env] = val


_CLIENT = None
_TRIED = False


def tracer():
    """The Langfuse client (a silent no-op when unconfigured), or None if the dep is absent.

    Cached: built once. Lazy import keeps module import network-free and dep-optional.
    """
    global _CLIENT, _TRIED
    if _TRIED:
        return _CLIENT
    _TRIED = True
    try:
        _export_keys()
        import contextlib
        import io
        from langfuse import get_client
        # silence the one-time "client disabled (no key)" notice on the offline no-op path
        with contextlib.redirect_stderr(io.StringIO()):
            _CLIENT = get_client()          # disabled→no-op if keys absent; durable if present
    except Exception:
        _CLIENT = None                      # langfuse not installed → tracing simply off
    return _CLIENT


class _Span:
    """Thin wrapper so callers needn't know langfuse's context-manager API (and it no-ops cleanly)."""

    def __init__(self, cm):
        self._cm = cm
        self._obs = None

    def __enter__(self):
        try:
            self._obs = self._cm.__enter__() if self._cm is not None else None
        except Exception:
            self._obs = None
        return self

    def __exit__(self, *exc):
        try:
            if self._cm is not None:
                self._cm.__exit__(*exc)
        except Exception:
            pass
        return False

    def update(self, **kw) -> "_Span":
        try:
            if self._obs is not None:
                self._obs.update(**kw)
        except Exception:
            pass
        return self

    def span(self, name: str, *, as_type: str = "span", **meta) -> "_Span":
        """Open a nested child observation (recall / reason / calibrate / audit / workspace …)."""
        c = tracer()
        if c is None:
            return _Span(None)
        try:
            return _Span(c.start_as_current_observation(name=name, as_type=as_type, metadata=meta))
        except Exception:
            return _Span(None)

    def event(self, name: str, **meta) -> "_Span":
        """Record a point-in-time observation (a single thought/tick) under the current span."""
        return self.span(name, as_type="span", **meta)


@contextmanager
def trace(name: str, *, as_type: str = "span", **meta):
    """Root observation for one brain operation. Yields a _Span; nest with .span()/.event().

    No-ops safely offline; when Langfuse keys are set, this becomes a durable trace.
    """
    c = tracer()
    if c is None:
        yield _Span(None)
        return
    try:
        cm = c.start_as_current_observation(name=name, as_type=as_type, metadata=meta)
    except Exception:
        cm = None
    span = _Span(cm)
    with span:
        yield span


def flush() -> None:
    """Push batched spans (needed before a short-lived process exits). No-op if unconfigured."""
    c = tracer()
    try:
        if c is not None:
            c.flush()
    except Exception:
        pass


def status() -> dict:
    """Honest observability status for the dashboard (no secret values)."""
    c = tracer()
    auth = None
    if c is not None and enabled():
        try:
            auth = bool(c.auth_check())
        except Exception:
            auth = False
    return {
        "engine": "langfuse",
        "installed": c is not None,
        "configured": enabled(),
        "auth_ok": auth,
        "mode": "durable-trace" if (enabled() and auth) else "offline-noop",
        "host": "set" if settings.get("LANGFUSE_HOST") else "default-cloud",
    }
