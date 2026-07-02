"""trading/crypto/freqtrade/config_template.py — build a Freqtrade config from OUR config.

Single source of truth: `dry_run`, exchange, stake currency and the REST creds are derived from
`trading.crypto.config.crypto_config` + the shared TRADING_MODE, so the Freqtrade bot can never
silently disagree with the rest of the system (paper→dry_run true, live→dry_run false).

    from trading.crypto.freqtrade.config_template import build_config, write_config
    path = write_config()          # -> trading/crypto/freqtrade/config.json (gitignored)
"""
from __future__ import annotations

import json
import os
import secrets

from trading.crypto.config import CryptoConfig, crypto_config

# Sane default majors in the configured quote currency; the Phase C library adapter will drive
# the real pair whitelist. Kept small so a fresh dry-run bot starts instantly.
_DEFAULT_BASES = ("BTC", "ETH", "SOL", "BNB", "XRP")

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
STRATEGY = "MlBridgeStrategy"


def _pairs(cfg: CryptoConfig) -> list[str]:
    # futures uses the ccxt perp pair format BASE/QUOTE:QUOTE (e.g. BTC/USDT:USDT)
    suffix = f":{cfg.quote}" if cfg.is_futures else ""
    return [f"{b}/{cfg.quote}{suffix}" for b in _DEFAULT_BASES]


def _freqai_block() -> dict:
    """FreqAI config — trains a per-pair model on engineered OHLCV features (real ML)."""
    return {
        "enabled": True,
        "identifier": "mlnetbrain",
        "train_period_days": 15,
        "backtest_period_days": 7,
        "live_retrain_hours": 6,
        "purge_old_models": 2,
        "feature_parameters": {
            "include_timeframes": ["5m", "15m"],
            "include_corr_pairlist": ["BTC/USDT", "ETH/USDT"],
            "label_period_candles": 12,
            "include_shifted_candles": 2,
            "indicator_periods_candles": [10, 20],
            "DI_threshold": 0.0,
        },
        "data_split_parameters": {"test_size": 0.25, "shuffle": False},
        "model_training_parameters": {},
    }


def build_config(cfg: CryptoConfig | None = None, *, freqai: bool = False) -> dict:
    """Return a Freqtrade config dict derived from our crypto_config + TRADING_MODE.
    `freqai=True` adds the FreqAI block + selects the FreqAIDirection ML strategy."""
    cfg = cfg or crypto_config
    keys = cfg.keys_for(cfg.default_exchange)
    futures = {"trading_mode": "futures", "margin_mode": "isolated"} if cfg.is_futures else {}
    ai = {"freqai": _freqai_block()} if freqai else {}
    return {
        **futures,
        **ai,
        "$schema": "https://schema.freqtrade.io/schema.json",
        "max_open_trades": int(cfg.max_open_trades),
        "stake_currency": cfg.quote,
        "stake_amount": (cfg.stake_amount if cfg.stake_amount and cfg.stake_amount > 0 else "unlimited"),
        "tradable_balance_ratio": 0.99,
        "dry_run": not cfg.is_live,            # paper => dry-run; MUST match TRADING_MODE
        "dry_run_wallet": float(cfg.paper_balance),   # editable paper starting balance (USDT)
        "cancel_open_orders_on_exit": True,
        # allow REST-driven manual entries (CryptoEngineClient.place_order -> /forceenter); the
        # bot is the execution venue, our system drives the signals.
        "force_entry_enable": True,
        "timeframe": "5m",
        "exchange": {
            "name": cfg.default_exchange,
            # creds are blank in paper/dry-run; only used when TRADING_MODE=live
            "key": (keys._api_key or "") if cfg.is_live else "",
            "secret": (keys._secret or "") if cfg.is_live else "",
            # VolumePairList populates the whitelist dynamically; seed kept for the very first
            # refresh. Blacklist stablecoin↔stable pairs + leveraged tokens (noise, not "symbols").
            "pair_whitelist": _pairs(cfg),
            "pair_blacklist": [
                "(USDC|TUSD|BUSD|FDUSD|DAI|USDP|PAX|EUR|GBP|AEUR)/.*",
                ".*(UP|DOWN|BULL|BEAR)/.*",
            ],
        },
        # ALL liquid AND volatile symbols (user ask): VolumePairList ranks ~300 by 24h quote
        # volume (liquidity) → VolatilityFilter keeps the volatile ones → ~250 liquid+volatile.
        # Refreshed live, so FreqUI always lists the current best symbols for the active segment.
        "pairlists": [
            {"method": "VolumePairList", "number_assets": 300, "sort_key": "quoteVolume",
             "refresh_period": 1800},
            {"method": "VolatilityFilter", "lookback_days": 10, "min_volatility": 0.02,
             "max_volatility": 1.0, "refresh_period": 86400},
        ],
        "entry_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "exit_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "api_server": {
            "enabled": True,
            "listen_ip_address": "127.0.0.1",
            "listen_port": int(cfg.ft_host.rsplit(":", 1)[-1]) if ":" in cfg.ft_host else 8080,
            "verbosity": "error",
            "enable_openapi": True,
            # MUST be >= 32 chars (Freqtrade schema). Replace with a real random secret in .env-driven runs.
            "jwt_secret_key": "CHANGE_ME_set_a_random_32char_plus_secret_in_your_real_config",
            "ws_token": "CHANGE_ME_random_ws_token",
            "username": cfg.ft_username,
            "password": cfg.ft_password,           # read from .env (FREQTRADE_PASSWORD)
        },
        "ml_leverage": float(cfg.leverage),    # custom: read by strategies' leverage() (futures)
        "bot_name": "mlnetworkbrain-crypto",
        "initial_state": "running",
        "internals": {"process_throttle_secs": 5},
        "strategy": STRATEGY,
    }


def write_config(path: str = CONFIG_PATH, cfg: CryptoConfig | None = None,
                 dry_run_wallet: float | None = None) -> str:
    """Write the derived config to `path` (gitignored) and return the path.

    Reuses an existing file's jwt_secret_key/ws_token if present (so restarts keep stable
    tokens), else generates fresh random secrets — the REST API is secure by default, no
    operator action needed. `dry_run_wallet` overrides the paper starting balance. The file is
    gitignored (holds the REST password + secrets)."""
    conf = build_config(cfg)
    if dry_run_wallet is not None:
        conf["dry_run_wallet"] = float(dry_run_wallet)
    jwt, ws = secrets.token_hex(32), secrets.token_hex(24)
    if os.path.exists(path):
        try:
            with open(path) as fh:
                prev = json.load(fh).get("api_server", {})
            jwt = prev.get("jwt_secret_key", jwt) or jwt
            ws = prev.get("ws_token", ws) or ws
        except Exception:
            pass
    conf["api_server"]["jwt_secret_key"] = jwt
    conf["api_server"]["ws_token"] = ws
    with open(path, "w") as fh:
        json.dump(conf, fh, indent=2)
    return path


if __name__ == "__main__":
    print(json.dumps(build_config(), indent=2))
