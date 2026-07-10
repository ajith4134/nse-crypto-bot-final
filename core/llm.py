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

import base64
import os
import time

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
    # llama-3.3-70b was RETIRED by Cerebras (deprecated 2026-02-16 → 100% NotFoundError,
    # 3.8k dead calls by 2026-07-10); gpt-oss-120b is their current production model
    # (~3,000 tok/s, on the free tier) per inference-docs.cerebras.ai/models/overview.
    ("CEREBRAS_API_KEY", "cerebras/gpt-oss-120b", "CEREBRAS_API_KEY", None),
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

# Vision-capable free/low-cost providers — the brain's "eyes". Same tuple shape as
# PROVIDERS (config key, litellm model id, env var litellm expects, optional api_base).
# These accept image content blocks (base64 screenshots). Priority = most-reliable free
# multimodal tiers first (Gemini 2.0 Flash is the fastest reliable free vision model), then
# Groq/OpenRouter/Qwen-VL/Fireworks as failover. `vision_chat()` walks this order and drops
# to the next on ANY error, so a throttled or 404'd vision model never blocks perception.
VISION_PROVIDERS = [
    ("GOOGLE_AISTUDIO_API_KEY", "gemini/gemini-2.0-flash", "GEMINI_API_KEY", None),
    ("GROQ_API_KEY", "groq/meta-llama/llama-4-scout-17b-16e-instruct", "GROQ_API_KEY", None),
    ("OPENROUTER_API_KEY", "openrouter/qwen/qwen2.5-vl-72b-instruct:free", "OPENROUTER_API_KEY", None),
    ("OPENROUTER_API_KEY", "openrouter/meta-llama/llama-3.2-11b-vision-instruct:free",
     "OPENROUTER_API_KEY", None),
    ("FIREWORKS_API_KEY",
     "fireworks_ai/accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
     "FIREWORKS_AI_API_KEY", None),
    ("ALIBABA_API_KEY", "openai/qwen-vl-max", None,
     "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
]


class NoLLMConfigured(RuntimeError):
    """Raised/handled when no cloud key and no local LLM are configured."""


def _candidates(providers=PROVIDERS, *, allow_local: bool = True) -> list[tuple[str, dict]]:
    """Ordered (model, extra_kwargs) list of usable providers — cloud first, local last.

    `providers` selects the chain (text PROVIDERS by default, or VISION_PROVIDERS for the
    eyes). `allow_local` appends the Ollama/llama.cpp fallback (only sensible for text)."""
    out: list[tuple[str, dict]] = []
    for key, model, env, api_base in providers:
        val = settings.get(key)
        if val:
            if api_base:                     # OpenAI-compatible provider → pass key+base inline
                out.append((model, {"api_base": api_base, "api_key": val}))
            else:
                if env and not os.getenv(env):   # map our key name to the one litellm expects
                    os.environ[env] = val
                out.append((model, {}))
    base = settings.get("LOCAL_LLM_BASE_URL")
    if allow_local and base:                  # Ollama / llama.cpp OpenAI-compatible fallback
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
         timeout: int = 45, total_timeout: float | None = None) -> str:
    """Complete a chat over the first working provider; falls back across the rest.

    `timeout` bounds each provider ATTEMPT; `total_timeout` bounds the WHOLE failover
    chain — without it a caller with a wall-clock budget can wedge for n_providers×timeout
    (the Broker-Sense LOOK-stage hang, 2026-07-05)."""
    import litellm
    litellm.drop_params = True                # ignore params a given provider doesn't support
    cands = _candidates()
    if not cands:
        raise NoLLMConfigured("no LLM provider configured")
    last: Exception | None = None
    chain_t0 = time.time()
    for model, extra in cands:
        if total_timeout is not None and time.time() - chain_t0 > total_timeout:
            break                             # budget exhausted → surface the last error
        prov = provider_name(model)
        t0 = time.time()
        try:
            r = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                   temperature=temperature, timeout=timeout, **extra)
            _telemetry("record", prov, True, (time.time() - t0) * 1000.0, None)
            return r["choices"][0]["message"]["content"]
        except Exception as e:                # try the next provider in the chain
            _telemetry("record", prov, False, (time.time() - t0) * 1000.0, str(e))
            last = e
    raise last if last else NoLLMConfigured("all providers failed")


def _image_data_url(img, mime: str = "image/png") -> str:
    """Normalize an image (file path | raw bytes | base64 str | data URL) → data URL.

    This is what LiteLLM's multimodal `image_url` content block expects. Screenshots the
    Ocular Cortex captures are PNG bytes; broker book/chart crops may arrive as paths."""
    if isinstance(img, (bytes, bytearray)):
        b64 = base64.b64encode(bytes(img)).decode("ascii")
        return f"data:{mime};base64,{b64}"
    if isinstance(img, str):
        if img.startswith("data:"):
            return img                                   # already a data URL
        if os.path.exists(img):                          # a file path on disk
            ext = os.path.splitext(img)[1].lower().lstrip(".") or "png"
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            with open(img, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("ascii")
            return f"data:{mime};base64,{b64}"
        return f"data:{mime};base64,{img}"               # assume it's already base64
    raise TypeError(f"unsupported image type: {type(img)!r}")


def vision_available() -> bool:
    """True if at least one vision-capable provider key is present (free eyes online)."""
    return bool(_candidates(VISION_PROVIDERS, allow_local=False))


def vision_chat(prompt: str, images, *, system: str | None = None, max_tokens: int = 700,
                temperature: float = 0.2, timeout: int = 45,
                total_timeout: float | None = None) -> str:
    """The brain's FREE eyes: send screenshot(s) + a prompt to a vision-capable provider.

    `images` is one image or a list (file path | raw PNG/JPEG bytes | base64 str | data URL).
    Walks VISION_PROVIDERS in priority order, falling through on ANY error exactly like
    `chat()`. `total_timeout` bounds the whole failover chain so a per-symbol perception read
    can never exceed its wall-clock budget. Returns the model's text reading of the image(s).

    No paid API and no GPU: runs entirely on free multimodal tiers (Gemini/Groq/Qwen-VL/…).
    Raises NoLLMConfigured if no vision key is present so callers degrade honestly."""
    import litellm
    litellm.drop_params = True
    cands = _candidates(VISION_PROVIDERS, allow_local=False)
    if not cands:
        raise NoLLMConfigured("no vision-capable LLM provider configured")
    if not isinstance(images, (list, tuple)):
        images = [images]
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(img)}})
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    last: Exception | None = None
    chain_t0 = time.time()
    for model, extra in cands:
        if total_timeout is not None and time.time() - chain_t0 > total_timeout:
            break
        prov = provider_name(model)
        t0 = time.time()
        try:
            r = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                   temperature=temperature, timeout=timeout, **extra)
            _telemetry("record", prov + ":vision", True, (time.time() - t0) * 1000.0, None)
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            _telemetry("record", prov + ":vision", False, (time.time() - t0) * 1000.0, str(e))
            last = e
    raise last if last else NoLLMConfigured("all vision providers failed")


def vision_order() -> list[str]:
    """Vision provider names in failover priority order (only those with a key present)."""
    return [provider_name(m) for m, _ in _candidates(VISION_PROVIDERS, allow_local=False)]


def _telemetry(_fn, provider, ok, latency_ms, err):
    """Record a provider attempt (best-effort; never breaks the call)."""
    try:
        from core import llm_telemetry
        llm_telemetry.record(provider, ok, latency_ms, err)
    except Exception:
        pass


def configured_order() -> list[str]:
    """Provider names in failover priority order (only those with a key present)."""
    return [provider_name(m) for m, _ in _candidates()]


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
