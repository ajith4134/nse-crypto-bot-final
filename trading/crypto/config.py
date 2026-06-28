"""trading/crypto/config.py — crypto trading configuration (T2).

Reuses the project-root `config.settings` (.env) and the shared TRADING_MODE so
paper/live is consistent across NSE (T1) and crypto (T2). API keys are OPTIONAL —
public data and the paper simulator need none. Keys, when present, are never
printed in full.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config import settings

VALID_MODES = ("paper", "live")

# ccxt market type per blueprint crypto scope (§1.B).
#   spot   -> 1x cash
#   swap   -> perpetual futures (USDⓈ-M / COIN-M)
#   future -> dated/quarterly futures
#   option -> options
MARKET_TYPES = ("spot", "swap", "future", "option")

# Typical taker maintenance-margin rate (fraction) used for liquidation estimates
# when the exchange doesn't supply one. 0.5% is a common linear-perp default.
DEFAULT_MMR = 0.005


@dataclass(frozen=True)
class ExchangeKeys:
    """Optional per-exchange credentials. Absent => public/paper only."""
    exchange: str
    _api_key: str | None = field(repr=False, default=None)
    _secret: str | None = field(repr=False, default=None)

    @property
    def present(self) -> bool:
        return bool(self._api_key and self._secret)

    def as_ccxt(self) -> dict:
        return {"apiKey": self._api_key, "secret": self._secret} if self.present else {}


@dataclass(frozen=True)
class CryptoConfig:
    mode: str
    exchanges: tuple[str, ...]
    default_exchange: str
    quote: str
    _keys: dict[str, ExchangeKeys] = field(default_factory=dict)

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    def keys_for(self, exchange: str) -> ExchangeKeys:
        return self._keys.get(exchange, ExchangeKeys(exchange))

    def has_keys(self, exchange: str) -> bool:
        return self.keys_for(exchange).present

    def as_status(self) -> dict:
        """Honest, secrets-safe snapshot for the dashboard / logs."""
        return {
            "mode": self.mode,
            "is_live": self.is_live,
            "exchanges": list(self.exchanges),
            "default_exchange": self.default_exchange,
            "quote": self.quote,
            "keys_present": {ex: self.has_keys(ex) for ex in self.exchanges},
        }


def _load() -> CryptoConfig:
    raw_mode = (settings.get("TRADING_MODE") or "paper").strip().lower()
    mode = raw_mode if raw_mode in VALID_MODES else "paper"

    raw_ex = (settings.get("CRYPTO_EXCHANGES") or "binance,bybit").strip()
    exchanges = tuple(e.strip().lower() for e in raw_ex.split(",") if e.strip())
    if not exchanges:
        exchanges = ("binance", "bybit")

    default_ex = (settings.get("CRYPTO_DEFAULT_EXCHANGE") or exchanges[0]).strip().lower()
    if default_ex not in exchanges:
        default_ex = exchanges[0]

    keys: dict[str, ExchangeKeys] = {}
    for ex in exchanges:
        prefix = ex.upper()
        keys[ex] = ExchangeKeys(
            ex,
            settings.get(f"{prefix}_API_KEY"),
            settings.get(f"{prefix}_API_SECRET"),
        )

    return CryptoConfig(
        mode=mode,
        exchanges=exchanges,
        default_exchange=default_ex,
        quote=(settings.get("CRYPTO_QUOTE") or "USDT").strip().upper(),
        _keys=keys,
    )


crypto_config = _load()


if __name__ == "__main__":
    import json
    print(json.dumps(crypto_config.as_status(), indent=2))
