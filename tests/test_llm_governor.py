"""tests/test_llm_governor.py — LLM budget governor (2026-07-10).

Pins the three governor layers in core/llm.chat():
  - cooldown-skip: a rate-limited provider is not re-hammered while cooling;
  - permanent-error cooldown: retired-model/dead-key errors cool for ~1h, not 60s;
  - response cache: identical calls within TTL hit the cache, not the API;
  - blackout guard: an all-cooling chain still gets exactly one honest attempt.
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def gov(monkeypatch, tmp_path):
    """Isolated governor world: fake provider chain, fake litellm, temp telemetry file."""
    from core import llm, llm_telemetry

    monkeypatch.setattr(llm_telemetry, "_PATH", str(tmp_path / "telemetry.json"))
    monkeypatch.setattr(llm_telemetry, "_cool_cache", (0.0, {}))
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(llm, "_last_call", {})
    monkeypatch.setenv("LLM_GOVERNOR", "1")
    monkeypatch.setenv("LLM_CACHE_TTL", "900")
    monkeypatch.setattr(llm, "_candidates",
                        lambda *a, **k: [("alpha/m1", {}), ("beta/m2", {})])
    # pacing off by default in tests (each test drives cooldowns explicitly)
    monkeypatch.setattr(llm, "_MIN_INTERVAL", {})

    calls: list[str] = []
    behavior: dict[str, Exception | str] = {"alpha/m1": "A", "beta/m2": "B"}

    import litellm

    def fake_completion(model, messages, **kw):
        calls.append(model)
        out = behavior[model]
        if isinstance(out, Exception):
            raise out
        return {"choices": [{"message": {"content": out}}]}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    # force fresh cooldown reads (no 3s cache) so tests see writes immediately
    monkeypatch.setattr(llm_telemetry, "_COOL_REFRESH", 0.0)
    return llm, llm_telemetry, calls, behavior


MSG = [{"role": "user", "content": "hi"}]


def test_rate_limited_provider_skipped_while_cooling(gov):
    llm, tel, calls, behavior = gov
    behavior["alpha/m1"] = RuntimeError("RateLimitError: 429 too many requests")
    assert llm.chat(MSG) == "B"                       # alpha fails → beta answers
    assert calls == ["alpha/m1", "beta/m2"]
    calls.clear()
    llm._cache.clear()                                # bypass the response cache
    assert llm.chat(MSG) == "B"                       # alpha is cooling → skipped entirely
    assert calls == ["beta/m2"]


def test_permanent_error_gets_hour_cooldown(gov):
    llm, tel, calls, behavior = gov
    behavior["alpha/m1"] = RuntimeError("NotFoundError: Model x does not exist")
    llm.chat(MSG)
    reload_at = tel._load()["alpha"]["reload_at"]
    assert reload_at - time.time() > tel.COOLDOWN_SEC * 10   # ≈1h, far above the 60s tier


def test_response_cache_hits_within_ttl(gov):
    llm, tel, calls, behavior = gov
    assert llm.chat(MSG) == "A"
    assert llm.chat(MSG) == "A"
    assert calls == ["alpha/m1"]                      # second call served from cache


def test_blackout_guard_single_attempt_when_all_cooling(gov):
    llm, tel, calls, behavior = gov
    for prov in ("alpha", "beta"):
        tel.record(prov, False, 1.0, "429 rate limit")
    assert llm.chat(MSG) == "A"                       # pass-2 ignores skips, tries alpha once
    assert calls == ["alpha/m1"]


def test_governor_kill_switch(gov, monkeypatch):
    llm, tel, calls, behavior = gov
    monkeypatch.setenv("LLM_GOVERNOR", "0")
    tel.record("alpha", False, 1.0, "429 rate limit")  # cooling — but governor is off
    assert llm.chat(MSG) == "A"
    assert calls == ["alpha/m1"]
