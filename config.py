"""
config.py — central, safe secrets/config loader.

Rules:
  • Reads from a gitignored .env (see .env.example for the template).
  • NEVER hard-code keys here. NEVER print full key values.
  • Missing keys return None and are reported by name only.

Usage:
    from config import settings
    key = settings.require("GROQ_API_KEY")   # raises if absent
    key = settings.get("NVIDIA_API_KEY")     # None if absent
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:  # dotenv optional; real env vars still work
    pass


# All recognized config keys (kept in sync with .env.example).
KNOWN_KEYS = (
    "GITHUB_TOKEN", "ETHERSCAN_API_KEY", "COINGECKO_API_KEY", "COINALYZE_API_KEY",
    "CEREBRAS_API_KEY", "GROQ_API_KEY", "SAMBANOVA_API_KEY", "HUGGINGFACE_TOKEN",
    "NVIDIA_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_AISTUDIO_API_KEY",
    "DEEPINFRA_API_KEY", "FIREWORKS_API_KEY", "ZAI_API_KEY", "ZAI_API_KEY_ID",
    "DEEPSEEK_API_KEY", "ALIBABA_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_KEY",
    "LOCAL_LLM_BASE_URL",
    # ── Trading Execution Phase (T1+) ──
    # Broker credentials (Zerodha/Upstox/Angel) live INSIDE the OpenAlgo server's
    # own config, not here. Our system only needs the OpenAlgo API key + host.
    "OPENALGO_API_KEY", "OPENALGO_HOST", "OPENALGO_WS_URL", "TRADING_MODE",
    # ── Crypto (T2) via ccxt. Keys OPTIONAL — public market data + paper sim need
    # none; only LIVE order placement requires them. ──
    "BINANCE_API_KEY", "BINANCE_API_SECRET", "BYBIT_API_KEY", "BYBIT_API_SECRET",
    "CRYPTO_EXCHANGES", "CRYPTO_DEFAULT_EXCHANGE", "CRYPTO_QUOTE",
)


class Settings:
    def get(self, name: str) -> str | None:
        return os.getenv(name)

    def require(self, name: str) -> str:
        val = os.getenv(name)
        if not val:
            raise RuntimeError(
                f"Missing required config '{name}'. Add it to .env "
                f"(see .env.example)."
            )
        return val

    def available(self) -> list[str]:
        """Names of keys that are present — values are never returned."""
        return [k for k in KNOWN_KEYS if os.getenv(k)]

    def __repr__(self) -> str:
        return f"<Settings: {len(self.available())}/{len(KNOWN_KEYS)} keys present>"


settings = Settings()


if __name__ == "__main__":
    # Safe diagnostic: prints which keys are present, never their values.
    print(settings)
    for k in KNOWN_KEYS:
        print(f"  {'✓' if settings.get(k) else '·'} {k}")
