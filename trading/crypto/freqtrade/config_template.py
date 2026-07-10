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


def enabled_segments() -> list[str]:
    """Segments the multi-segment engine should run (persisted in .env CRYPTO_SEGMENTS)."""
    raw = os.environ.get("CRYPTO_SEGMENTS", "futures,spot,options,prediction")
    valid = ("futures", "spot", "options", "prediction")
    segs = [s.strip().lower() for s in raw.split(",") if s.strip().lower() in valid]
    return segs or ["futures"]


def _seg_max_open(segment: str) -> dict:
    """Optional per-segment trade cap (.env CRYPTO_MAX_OPEN_TRADES_<SEG>); absent = global."""
    raw = os.environ.get(f"CRYPTO_MAX_OPEN_TRADES_{segment.upper()}", "").strip()
    return {"max_open_trades": int(raw)} if raw.lstrip("-").isdigit() else {}


def _segments_block(cfg: CryptoConfig) -> dict:
    """Per-segment engine config for the forked Freqtrade's MultiWorker."""
    on = set(enabled_segments())
    spot_pairs = [f"{b}/{cfg.quote}" for b in _DEFAULT_BASES]
    return {
        "futures": {"enabled": "futures" in on, "overrides": {**_seg_max_open("futures")}},
        "spot": {
            "enabled": "spot" in on,
            # VolumePairList works on spot markets too; seed whitelist in spot pair format.
            # strategy: spot cannot short — Freqtrade REFUSES to boot a can_short strategy
            # in spot mode, and the base MlBridgeStrategy is can_short=True. Without this
            # override the spot worker died at every boot (ImportError) and all "spot"
            # API calls silently fell back to the futures bot (found 2026-07-09).
            "overrides": {"exchange": {"pair_whitelist": spot_pairs}, "ml_leverage": 1.0,
                          "strategy": "MlBridgeStrategySpot",
                          **_seg_max_open("spot")},
        },
        # Options/prediction universes are dynamic (strikes roll, markets rotate) — the
        # fork's AllMarketsPairList plugin lists live tradable markets, no static seeds.
        "options": {
            "enabled": "options" in on,
            "overrides": {
                "exchange": {"name": "deribit", "key": "", "secret": "",
                             "pair_whitelist": [], "pair_blacklist": []},
                "stake_currency": "USDC",   # Deribit linear options quote/settle in USDC
                "stake_amount": 200,
                "pairlists": [{"method": "AllMarketsPairList", "number_assets": 100}],
                # Illiquid strikes can have EMPTY order books — price options off the
                # ticker (bid/ask/last) instead of the book so entries never 500.
                "entry_pricing": {"price_side": "other", "use_order_book": False,
                                  "order_book_top": 1},
                "exit_pricing": {"price_side": "other", "use_order_book": False,
                                 "order_book_top": 1},
                "ml_leverage": 1.0,
                **_seg_max_open("options"),
            },
        },
        "prediction": {
            "enabled": "prediction" in on,
            "overrides": {
                "exchange": {"name": "predictionpaper", "key": "", "secret": "",
                             "pair_whitelist": [], "pair_blacklist": []},
                "stake_currency": "USDC",   # Polymarket outcomes priced 0..1 USDC
                "stake_amount": 100,
                "pairlists": [{"method": "AllMarketsPairList", "number_assets": 50}],
                "ml_leverage": 1.0,
                **_seg_max_open("prediction"),
            },
        },
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
        # mlnb E3: each segment bot consumes <state>/decisions_inbox.jsonl (push model).
        # Harmless no-op while the funnel side is off (CRYPTO_DECISION_INBOX unset).
        "mlnb_decision_inbox": True,
        "timeframe": "5m",
        "exchange": {
            "name": cfg.default_exchange,
            # creds are blank in paper/dry-run; only used when TRADING_MODE=live
            "key": (keys._api_key or "") if cfg.is_live else "",
            "secret": (keys._secret or "") if cfg.is_live else "",
            # WEBSOCKET pricing (ccxt.pro) — THE way to hold 100s of open trades without an IP ban:
            # data is PUSHED over one persistent socket instead of REST-polled per trade every cycle
            # (the 2026-07-03 -1003 ban came from REST order-book polling × many open trades). This
            # is what pro/HFT desks use to run huge position counts on one connection. Near-zero
            # REST weight → max_open_trades can be unlimited safely.
            "enable_ws": True,
            # VolumePairList populates the whitelist dynamically; seed kept for the very first
            # refresh. Blacklist stablecoin↔stable pairs + leveraged tokens (noise, not "symbols").
            "pair_whitelist": _pairs(cfg),
            "pair_blacklist": [
                "(USDC|TUSD|BUSD|FDUSD|DAI|USDP|PAX|EUR|GBP|AEUR)/.*",
                ".*(UP|DOWN|BULL|BEAR)/.*",
            ],
        },
        # ALL Binance symbols (owner ask 2026-07-06): number_assets=1000 ranks the WHOLE Binance
        # USDT universe by 24h quote volume (Binance has ~450 USDT perps, so 1000 = effectively
        # all) → VolatilityFilter keeps the volatile ones. Refreshed live, so FreqUI always lists
        # the current best symbols for the active segment; trades can open on any of them.
        "pairlists": [
            {"method": "VolumePairList", "number_assets": 1000, "sort_key": "quoteVolume",
             "refresh_period": 1800},
            {"method": "VolatilityFilter", "lookback_days": 10, "min_volatility": 0.02,
             "max_volatility": 1.0, "refresh_period": 86400},
        ],
        # Order-book pricing is MANDATORY on Binance futures (freqtrade: Binance swap
        # tickers have tickers_have_price=False → "Ticker pricing not available for
        # Binance" config error, engine won't start). The 2026-07-03 IP ban (418/-1003)
        # came from VOLUME: ~60 unlimited open dry-run trades × order-book exit pricing
        # every 5s ≈ 1400 req/min — so the throttle below cuts cycles 3×, order_book_top
        # stays 1 (cheapest depth call), and all non-Freqtrade data reads moved to the
        # multi-venue pool (trading/crypto/exchange_pool.py).
        # price_side "other" (the aggressive side) is REQUIRED for MARKET entry/exit orders
        # (owner's default: guaranteed immediate fill, long+short) — Freqtrade rejects market
        # orders with price_side "same".
        "entry_pricing": {"price_side": "other", "use_order_book": True, "order_book_top": 1},
        "exit_pricing": {"price_side": "other", "use_order_book": True, "order_book_top": 1},
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
        # 15s, not 5s: each cycle prices EVERY open trade off the order book (mandatory
        # on Binance futures) and open trades are uncapped — 5s cycles at ~60 trades is
        # what tripped Binance's -1003 IP ban. 15s keeps exits responsive (stops are %
        # -based, not tick-critical) at 1/3 the request volume.
        "internals": {"process_throttle_secs": 15},
        "strategy": STRATEGY,
        # Multi-segment fork (vendor/freqtrade): ONE engine process runs one bot per enabled
        # segment behind the one API port/URL. Segment set comes from CRYPTO_SEGMENTS in .env
        # (comma list); trading_mode/dry_run per segment are enforced by worker_multi.
        "mlnb_segments": _segments_block(cfg),
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
