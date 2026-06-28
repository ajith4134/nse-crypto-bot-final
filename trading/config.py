"""trading/config.py — central trading configuration (T1).

Pulls secrets from the project-root `config.settings` (gitignored .env) and adds
trading-specific, non-secret defaults (mode, hosts, exchange squareoff times).

Rules honoured:
  • Secrets-safe: the OpenAlgo API key is read from .env via config.settings and
    never printed in full (see `redacted_key`).
  • Honest state: `is_configured` reflects whether an API key is actually present.

Usage:
    from trading.config import trading_config
    if trading_config.is_configured:
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config import settings


# Exchange auto-squareoff times (IST, 24h "HH:MM"). Brokers force-close intraday
# (MIS/NRML-intraday) positions at these times; we square off ~1 min earlier.
SQUAREOFF_TIMES_IST: dict[str, str] = {
    "NSE": "15:15",   # equity intraday
    "BSE": "15:15",
    "NFO": "15:15",   # equity/index options & futures
    "BFO": "15:15",
    "CDS": "16:45",   # currency derivatives
    "BCD": "16:45",
    "MCX": "23:30",   # commodities (evening session)
    "NCDEX": "17:00",
}

VALID_MODES = ("paper", "live")


@dataclass(frozen=True)
class TradingConfig:
    """Resolved trading configuration. Frozen — build once from .env at import."""
    mode: str                       # "paper" | "live"
    openalgo_host: str              # e.g. http://127.0.0.1:5000
    openalgo_ws_url: str            # e.g. ws://127.0.0.1:8765
    _api_key: str | None = field(repr=False, default=None)
    squareoff_times: dict[str, str] = field(default_factory=lambda: dict(SQUAREOFF_TIMES_IST))

    # ── derived / safe accessors ──────────────────────────────────────────────
    @property
    def is_configured(self) -> bool:
        """True only if an OpenAlgo API key is actually present in .env."""
        return bool(self._api_key)

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def redacted_key(self) -> str:
        """Safe-to-log fingerprint of the key — never the full value."""
        if not self._api_key:
            return "<absent>"
        k = self._api_key
        return f"{k[:4]}…{k[-2:]} (len={len(k)})" if len(k) > 6 else "<set>"

    def require_key(self) -> str:
        """Return the API key or raise a clear, key-name-only error."""
        if not self._api_key:
            raise RuntimeError(
                "Missing OPENALGO_API_KEY. Start the OpenAlgo server, copy its API "
                "key from http://127.0.0.1:5000, and add it to .env "
                "(see .env.example)."
            )
        return self._api_key

    def squareoff_for(self, exchange: str) -> str | None:
        return self.squareoff_times.get(exchange.upper())

    def as_status(self) -> dict:
        """Honest, secrets-safe snapshot for the dashboard / logs."""
        return {
            "mode": self.mode,
            "is_live": self.is_live,
            "openalgo_host": self.openalgo_host,
            "openalgo_ws_url": self.openalgo_ws_url,
            "api_key_present": self.is_configured,
            "api_key_fingerprint": self.redacted_key,
            "squareoff_times_ist": self.squareoff_times,
        }


def _load() -> TradingConfig:
    raw_mode = (settings.get("TRADING_MODE") or "paper").strip().lower()
    mode = raw_mode if raw_mode in VALID_MODES else "paper"
    return TradingConfig(
        mode=mode,
        openalgo_host=(settings.get("OPENALGO_HOST") or "http://127.0.0.1:5000").rstrip("/"),
        openalgo_ws_url=settings.get("OPENALGO_WS_URL") or "ws://127.0.0.1:8765",
        _api_key=settings.get("OPENALGO_API_KEY"),
    )


# Module-level singleton, built from .env at import time.
trading_config = _load()


if __name__ == "__main__":
    import json
    print(json.dumps(trading_config.as_status(), indent=2))
