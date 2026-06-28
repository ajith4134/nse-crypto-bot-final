# Always-on loop architecture + notable bot features — OSS patterns (web research, 2026-06-28)

> Ideas only. Saved verbatim. License noted, not a filter.

## Three loop families
1. **Throttled poll loop** (REST-first, simple, CPU-cheap) — `while True` + sleep N, fetch/strategy/orders/persist. Freqtrade.
2. **Async event loop** (WS-first, push-driven) — asyncio/uvloop reactor woken by market-data pushes; no sleep. OctoBot, Nautilus, Hummingbot (clock+async), Jesse.
3. **Webhook listener** — Flask/FastAPI idle until TradingView POSTs a signal.

## Project notes
- **Freqtrade** (GPL-3): `Worker` loop every `process_throttle_secs`; once-per-candle OHLCV; dry/live share logic. ccxt.pro WS w/ **auto REST fallback**. API/Telegram/loop in **separate threads, isolated asyncio loops**. SQLite persistence resumes positions; **separate dry vs live DB**. systemd sd_notify watchdog (not in Docker; Docker = restart policy). Standouts: **stackable Protections** (StoplossGuard/MaxDrawdown/LowProfitPairs/CooldownPeriod), **two-way Telegram** (/forceexit /fx, /reload_config hot-reload, /pause/stop/status), **FreqUI** (don't expose to internet).
- **NautilusTrader** (LGPL): NautilusKernel single-threaded core (MessageBus+strategy+RiskEngine+Cache), uvloop; background Tokio threads for I/O. Optional **Redis** for durable cache/bus → restart. **Crash-only design** (restart = recovery path), **fail-fast on NaN/invalid**, 3 contexts Backtest/Sandbox/Live from one core.
- **OctoBot** (GPL-3): asyncio producer-consumer "Async-Channel" — no polling sleeps; <10 threads; Cython hot paths. **Tentacles** plugin system (evaluators/data/notifiers).
- **Hummingbot** (Apache): **Clock ticks every 1s** notifying TimeIterators in registration order; Strategy-V2 async control loop. Known bug: `ready` flag can stay False after reconnect (#7230) → need explicit readiness re-assert. Gateway = separate dockerized middleware.
- **OpenAlgo** (AGPL, NSE): Flask + React; **APScheduler in IST** — start at open, stop near close, periodic checks, intraday square-off (`flow_scheduler_service.py`). Unified 30+ Indian brokers.
- **TradingView-webhook bots** (MIT): always-on Flask listener; VPS + PM2; passphrase required (public endpoint).

## Equities vs crypto
- Crypto 24/7: keep async/WS loop alive, rely on reconnect+heartbeat not restarts.
- Equities: **scheduler-driven** (APScheduler/cron) start@open / stop@close / square-off before close. Don't use laptop cron; use VPS/service; log each run; **alert on missed/failed runs**.

## PATTERNS TO ADOPT (CPU-first: paper crypto 24/7 + NSE off-hours replay)
1. One supervisor process, one asyncio loop, uvloop on Linux (idle-cheap I/O-wait).
2. **Two engines behind one core** (ports-and-adapters): CryptoEngine (WS-first ccxt.pro, REST fallback) 24/7; NSEEngine scheduler-gated by IST hours, off-hours swap to **replay/sim data source** feeding the same strategy → 24/7 utilization + backtest↔paper parity.
3. WS-first + auto REST fallback + ping-pong heartbeat ~30s + reconnect/backoff task; re-assert `ready` on reconnect (avoid Hummingbot bug).
4. Crash-only + externalized state (persist positions/orders/cooldowns to SQLite — the 85-col journal can double as state); separate paper vs live DB.
5. Run as service + watchdog (systemd sd_notify or Docker `restart: unless-stopped`).
6. Telegram/dashboard/API in own threads/loops so a slow notify never stalls trading.

### Prioritized features to add (have: per-market toggle, paper/live, kill-switch, circuit breaker, 85-col journal, Telegram alerts, Dark-Pro dashboard)
**High:** stackable protection rules (StoplossGuard, MaxDrawdown peak-to-trough, CooldownPeriod, exposure limits); **two-way Telegram control** (/status /pause /fx /reload_config /whitelist — we only push alerts now); config/strategy hot-reload; **APScheduler IST scheduled tasks** (square-off, session start/stop, EOD reports, health pings); reconnect/heartbeat/readiness subsystem surfaced on dashboard.
**Medium:** dashboard remote control (start/stop/force-exit/square-off + auth); explicit backtest↔paper↔live parity + Sandbox context; multi-strategy/pair with task isolation; watchlist management UI.
**Lower:** tentacle-style plugins; TradingView webhook ingestion (passphrase); crash-only design pass.
