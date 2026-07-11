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
import hashlib
import json
import os
import threading
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
    # Each candidate is (litellm model id, extra kwargs, provider label). The label is the
    # dashboard/telemetry identity: for OpenAI-compatible providers it comes from the config
    # key so ZAI/Alibaba/local don't all collapse to "openai" (see _label_from_key).
    out: list[tuple[str, dict, str]] = []
    for key, model, env, api_base in providers:
        val = settings.get(key)
        if val:
            if api_base:                     # OpenAI-compatible provider → pass key+base inline
                out.append((model, {"api_base": api_base, "api_key": val}, _label_from_key(key)))
            else:
                if env and not os.getenv(env):   # map our key name to the one litellm expects
                    os.environ[env] = val
                out.append((model, {}, provider_name(model)))
    base = settings.get("LOCAL_LLM_BASE_URL")
    if allow_local and base:                  # Ollama / llama.cpp OpenAI-compatible fallback
        model = "openai/" + (os.getenv("LOCAL_LLM_MODEL") or "llama3")
        out.append((model, {"api_base": base, "api_key": os.getenv("LOCAL_LLM_API_KEY", "ollama")},
                    "local"))
    return out


def active_model() -> tuple[str, dict] | None:
    """The first usable (model, extra) or None if nothing is configured."""
    c = _candidates()
    return (c[0][0], c[0][1]) if c else None    # public 2-tuple; drop the internal provider label


def provider_name(model: str) -> str:
    return model.split("/", 1)[0]


def _label_from_key(key: str) -> str:
    """Distinct dashboard/telemetry name for an OpenAI-compatible provider.

    Many providers (ZAI, Alibaba, the local LLM) share litellm's `openai/` prefix, so
    provider_name(model) collapses them all to "openai" — merging their telemetry, pacing,
    and dashboard rows. We name them by their config key instead so each is shown, cooled,
    and paced independently. e.g. ZAI_API_KEY → "zai", ALIBABA_API_KEY → "alibaba"."""
    return key.split("_API_KEY")[0].lower()


# ── LLM budget governor (2026-07-10) ──────────────────────────────────────────────
# The 2026-07-10 audit found ~95% of the day's 4.5k calls dying on self-inflicted 429s:
# every caller walked the FULL chain on every call, re-hitting providers that had just
# rate-limited us. Three layers fix it (kill-switch: LLM_GOVERNOR=0):
#   1. cooldown-skip — providers inside a recorded cooldown (llm_telemetry.reload_at,
#      shared cross-process) are skipped instead of re-hammered;
#   2. pacing — a per-provider minimum interval within this process, so a burst of brain
#      calls spreads across the chain instead of draining one free tier;
#   3. response cache — identical (messages, max_tokens, temperature) within
#      LLM_CACHE_TTL (default 900s, 0 disables) returns the cached reply, free.
_MIN_INTERVAL = {         # seconds between calls PER PROVIDER, per process (free-tier RPM)
    "groq": 2.5, "cerebras": 2.5, "sambanova": 6.0, "gemini": 8.0, "openrouter": 4.0,
    "deepseek": 3.0, "deepinfra": 3.0, "fireworks_ai": 3.0, "mistral": 2.5,
    "nvidia_nim": 3.0, "openai": 1.0, "zai": 2.0, "alibaba": 2.0,  # "local" = unpaced
}
_last_call: dict[str, float] = {}
_CACHE_MAX = 512
_cache: dict[str, tuple[float, str]] = {}
_cache_lock = threading.Lock()


def _governor_on() -> bool:
    return os.getenv("LLM_GOVERNOR", "1").strip().lower() not in ("0", "false", "off")


def _cache_ttl() -> float:
    try:
        return float(os.getenv("LLM_CACHE_TTL", "900"))
    except ValueError:
        return 900.0


def _cache_key(messages, max_tokens, temperature) -> str:
    raw = json.dumps([messages, max_tokens, temperature], sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    ttl = _cache_ttl()
    if ttl <= 0:
        return None
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] <= ttl:
            return hit[1]
        if hit:
            _cache.pop(key, None)
    return None


def _cache_put(key: str, text: str) -> None:
    if _cache_ttl() <= 0:
        return
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:          # drop the oldest entries
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:_CACHE_MAX // 8]:
                _cache.pop(k, None)
        _cache[key] = (time.time(), text)


def _skippable(prov: str) -> bool:
    """True when the governor says don't hit `prov` right now (cooling or paced-out)."""
    if not _governor_on():
        return False
    try:
        from core import llm_telemetry
        if llm_telemetry.cooling(prov):
            return True
    except Exception:
        pass
    gap = _MIN_INTERVAL.get(prov)
    return bool(gap) and (time.time() - _last_call.get(prov, 0.0)) < gap


def chat(messages: list[dict], max_tokens: int = 600, temperature: float = 0.4,
         timeout: int = 45, total_timeout: float | None = None) -> str:
    """Complete a chat over the first working provider; falls back across the rest.

    `timeout` bounds each provider ATTEMPT; `total_timeout` bounds the WHOLE failover
    chain — without it a caller with a wall-clock budget can wedge for n_providers×timeout
    (the Broker-Sense LOOK-stage hang, 2026-07-05). Governed: cooldown-skip + pacing +
    response cache (see the governor block above; LLM_GOVERNOR=0 disables)."""
    import litellm
    litellm.drop_params = True                # ignore params a given provider doesn't support
    cands = _candidates()
    if not cands:
        raise NoLLMConfigured("no LLM provider configured")
    ck = _cache_key(messages, max_tokens, temperature)
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    last: Exception | None = None
    chain_t0 = time.time()
    # pass 1 honors the governor; pass 2 (blackout guard) runs ONLY if pass 1 skipped the
    # entire chain without a single attempt — a fully-cooling chain still gets one honest
    # attempt rather than a guaranteed raise. Real pass-1 failures are never re-attempted.
    for honor_governor in (True, False):
        attempted = 0
        for model, extra, *rest in cands:
            if total_timeout is not None and time.time() - chain_t0 > total_timeout:
                break                         # budget exhausted → surface the last error
            prov = rest[0] if rest else provider_name(model)   # distinct label if _candidates gave one
            if honor_governor and _skippable(prov):
                continue
            attempted += 1
            t0 = time.time()
            _last_call[prov] = t0
            try:
                r = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                       temperature=temperature, timeout=timeout, **extra)
                _telemetry("record", prov, True, (time.time() - t0) * 1000.0, None)
                text = r["choices"][0]["message"]["content"]
                _cache_put(ck, text)
                return text
            except Exception as e:            # try the next provider in the chain
                _telemetry("record", prov, False, (time.time() - t0) * 1000.0, str(e))
                last = e
        if attempted:
            break                             # real attempts happened → don't double-hit
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
    # governed like chat(): skip cooling/paced providers, one blackout-guard pass if the
    # whole chain was skipped without a single attempt (vision cooldowns key on ":vision").
    for honor_governor in (True, False):
        attempted = 0
        for model, extra, *rest in cands:
            if total_timeout is not None and time.time() - chain_t0 > total_timeout:
                break
            prov = rest[0] if rest else provider_name(model)   # distinct label if _candidates gave one
            if honor_governor and _skippable(prov + ":vision"):
                continue
            attempted += 1
            t0 = time.time()
            _last_call[prov + ":vision"] = t0
            try:
                r = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                       temperature=temperature, timeout=timeout, **extra)
                _telemetry("record", prov + ":vision", True, (time.time() - t0) * 1000.0, None)
                return r["choices"][0]["message"]["content"]
            except Exception as e:
                _telemetry("record", prov + ":vision", False, (time.time() - t0) * 1000.0, str(e))
                last = e
        if attempted:
            break
    raise last if last else NoLLMConfigured("all vision providers failed")


def vision_order() -> list[str]:
    """Vision provider names in failover priority order (only those with a key present)."""
    return [t[2] if len(t) > 2 else provider_name(t[0])
            for t in _candidates(VISION_PROVIDERS, allow_local=False)]


def _telemetry(_fn, provider, ok, latency_ms, err):
    """Record a provider attempt (best-effort; never breaks the call)."""
    try:
        from core import llm_telemetry
        llm_telemetry.record(provider, ok, latency_ms, err)
    except Exception:
        pass


def configured_order() -> list[str]:
    """Provider names in failover priority order (only those with a key present)."""
    return [t[2] if len(t) > 2 else provider_name(t[0]) for t in _candidates()]


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
    for model, extra, *rest in cands:
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
