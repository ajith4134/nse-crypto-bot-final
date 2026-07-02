"""core/llm.py — P4.1 cloud-LLM access (the brain's "mouth"), reuse-first via LiteLLM.

One call surface over many free providers: auto-selects whichever API key is present in
`.env` (priority order = fast/free first), falls back across the other present providers,
and finally to a local LLM (Ollama/llama.cpp via LOCAL_LLM_BASE_URL) if configured. The
brain never needs to know which provider answered.

Secrets-safe: keys are read by NAME from config.settings (loaded from gitignored .env);
values are never logged or returned. If no provider is configured, active_model() returns
None and callers degrade gracefully (the chat reports "no LLM key configured").
"""
from __future__ import annotations

import os

from config import settings

# (config key in .env, litellm model id, env var litellm expects, optional api_base for
# OpenAI-compatible providers litellm has no native prefix for).
# Priority order = the failover chain: confirmed fast/reliable free tiers first, then
# generous-but-rate-limited, then the rest. `chat()` walks this order and moves to the
# next provider on ANY error (rate limit / quota / timeout / model-not-found), so a
# throttled or exhausted key never blocks the brain — it just falls through. (Ranked from
# a 2026-07-02 live health-check: Groq 0.21s and SambaNova 1.3s were the fastest working.)
PROVIDERS = [
    ("GROQ_API_KEY", "groq/llama-3.3-70b-versatile", "GROQ_API_KEY", None),
    ("CEREBRAS_API_KEY", "cerebras/llama-3.3-70b", "CEREBRAS_API_KEY", None),
    ("SAMBANOVA_API_KEY", "sambanova/Meta-Llama-3.3-70B-Instruct", "SAMBANOVA_API_KEY", None),
    ("GOOGLE_AISTUDIO_API_KEY", "gemini/gemini-2.0-flash", "GEMINI_API_KEY", None),
    ("OPENROUTER_API_KEY", "openrouter/meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY", None),
    ("DEEPSEEK_API_KEY", "deepseek/deepseek-chat", "DEEPSEEK_API_KEY", None),
    ("DEEPINFRA_API_KEY", "deepinfra/meta-llama/Llama-3.3-70B-Instruct", "DEEPINFRA_API_KEY", None),
    ("FIREWORKS_API_KEY", "fireworks_ai/accounts/fireworks/models/llama-v3p3-70b-instruct", "FIREWORKS_AI_API_KEY", None),
    ("MISTRAL_API_KEY", "mistral/mistral-large-latest", "MISTRAL_API_KEY", None),
    ("NVIDIA_API_KEY", "nvidia_nim/meta/llama-3.3-70b-instruct", "NVIDIA_NIM_API_KEY", None),
    # OpenAI-compatible endpoints (litellm 'openai/<model>' + api_base + api_key):
    ("ZAI_API_KEY", "openai/glm-4-flash", None, "https://api.z.ai/api/paas/v4"),
    ("ALIBABA_API_KEY", "openai/qwen-plus", None,
     "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
]


class NoLLMConfigured(RuntimeError):
    """Raised/handled when no cloud key and no local LLM are configured."""


def _candidates() -> list[tuple[str, dict]]:
    """Ordered (model, extra_kwargs) list of usable providers — cloud first, local last."""
    out: list[tuple[str, dict]] = []
    for key, model, env, api_base in PROVIDERS:
        val = settings.get(key)
        if val:
            if api_base:                     # OpenAI-compatible provider → pass key+base inline
                out.append((model, {"api_base": api_base, "api_key": val}))
            else:
                if not os.getenv(env):       # map our key name to the one litellm expects
                    os.environ[env] = val
                out.append((model, {}))
    base = settings.get("LOCAL_LLM_BASE_URL")
    if base:                                  # Ollama / llama.cpp OpenAI-compatible fallback
        model = "openai/" + (os.getenv("LOCAL_LLM_MODEL") or "llama3")
        out.append((model, {"api_base": base, "api_key": os.getenv("LOCAL_LLM_API_KEY", "ollama")}))
    return out


def active_model() -> tuple[str, dict] | None:
    """The first usable (model, extra) or None if nothing is configured."""
    c = _candidates()
    return c[0] if c else None


def provider_name(model: str) -> str:
    return model.split("/", 1)[0]


def chat(messages: list[dict], max_tokens: int = 600, temperature: float = 0.4,
         timeout: int = 45) -> str:
    """Complete a chat over the first working provider; falls back across the rest."""
    import litellm
    litellm.drop_params = True                # ignore params a given provider doesn't support
    cands = _candidates()
    if not cands:
        raise NoLLMConfigured("no LLM provider configured")
    last: Exception | None = None
    for model, extra in cands:
        try:
            r = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                   temperature=temperature, timeout=timeout, **extra)
            return r["choices"][0]["message"]["content"]
        except Exception as e:                # try the next provider in the chain
            last = e
    raise last if last else NoLLMConfigured("all providers failed")


def chat_stream(messages: list[dict], max_tokens: int = 600, temperature: float = 0.4,
                timeout: int = 45):
    """Yield reply text deltas as they stream. Falls back to the next provider only if a
    provider fails BEFORE emitting any token (mid-stream failure just stops cleanly)."""
    import litellm
    litellm.drop_params = True
    cands = _candidates()
    if not cands:
        raise NoLLMConfigured("no LLM provider configured")
    last: Exception | None = None
    for model, extra in cands:
        emitted = False
        try:
            resp = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                      temperature=temperature, timeout=timeout, stream=True, **extra)
            for chunk in resp:
                try:
                    delta = chunk["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, AttributeError):
                    delta = None
                if delta:
                    emitted = True
                    yield delta
            return
        except Exception as e:
            last = e
            if emitted:                       # don't restart a partially-streamed answer
                return
    if last:
        raise last
    raise NoLLMConfigured("all providers failed")
