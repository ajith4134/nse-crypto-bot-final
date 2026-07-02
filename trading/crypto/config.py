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
    # crypto execution engine (T-split B): Freqtrade runs as a separate self-hosted process.
    engine: str = "freqtrade"
    ft_host: str = "http://127.0.0.1:8080"
    _ft_user: str | None = field(repr=False, default=None)
    _ft_pass: str | None = field(repr=False, default=None)
    trading_mode: str = "spot"          # "spot" (long-only) | "futures" (perp, shorting allowed)
    # operator-adjustable Freqtrade params (applied via the guarded restart) — dashboard controls
    paper_balance: float = 10000.0      # dry_run_wallet (paper starting capital, USDT)
    max_open_trades: int = 5            # max concurrent open positions
    stake_amount: float = 0.0           # per-trade capital (USDT); 0 = "unlimited"
    leverage: float = 1.0               # futures leverage (ignored in spot)

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def is_futures(self) -> bool:
        return self.trading_mode == "futures"

    @property
    def ft_username(self) -> str:
        return self._ft_user or "freqtrader"

    @property
    def ft_password(self) -> str:
        return self._ft_pass or ""

    @property
    def ft_configured(self) -> bool:
        """True once Freqtrade REST creds are present (password set)."""
        return bool(self._ft_pass)

    ft_public_url: str = ""             # public FreqUI url (cloudflared tunnel); else use ft_host

    @property
    def freqtrade_url(self) -> str:
        """Where to open FreqUI from a browser — the public tunnel if set, else the local host."""
        return self.ft_public_url or self.ft_host

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
            "engine": self.engine,
            "ft_host": self.ft_host,
            "ft_configured": self.ft_configured,
            "trading_mode": self.trading_mode,
        }


def _load() -> CryptoConfig:
    # CRYPTO_MODE lets crypto go paper/live INDEPENDENTLY of NSE (TRADING_MODE drives OpenAlgo).
    # Falls back to the shared TRADING_MODE when unset.
    raw_mode = (settings.get("CRYPTO_MODE") or settings.get("TRADING_MODE") or "paper").strip().lower()
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
        engine=(settings.get("CRYPTO_ENGINE") or "freqtrade").strip().lower(),
        ft_host=(settings.get("FREQTRADE_HOST") or "http://127.0.0.1:8080").rstrip("/"),
        _ft_user=settings.get("FREQTRADE_USERNAME"),
        _ft_pass=settings.get("FREQTRADE_PASSWORD"),
        trading_mode=("futures" if (settings.get("CRYPTO_TRADING_MODE") or "spot").strip().lower()
                      == "futures" else "spot"),
        ft_public_url=(settings.get("FREQTRADE_PUBLIC_URL") or "").strip().rstrip("/"),
        paper_balance=float(settings.get("CRYPTO_PAPER_BALANCE") or 10000.0),
        max_open_trades=int(float(settings.get("CRYPTO_MAX_OPEN_TRADES") or 5)),
        stake_amount=float(settings.get("CRYPTO_STAKE_AMOUNT") or 0.0),
        leverage=float(settings.get("CRYPTO_LEVERAGE") or 1.0),
    )


crypto_config = _load()


if __name__ == "__main__":
    import json
    print(json.dumps(crypto_config.as_status(), indent=2))
