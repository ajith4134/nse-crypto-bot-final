# Market ON/OFF toggles + safe paper↔real switch — OSS patterns (web research, 2026-06-28)

> Ideas/architecture only. Saved verbatim. License noted, not a filter.

- **Freqtrade** (GPL-3): `dry_run: true` (or `--dry-run` strips secrets) → sim wallet, read-only exchange. Switching dry→live needs a **fresh DB** (separate `db_url`) so paper trades don't taint live = mode switch via restart (a safety gate). Runtime ON/OFF via Telegram/REST/UI: `/pause`/`/stopentry` (stop new entries, still manage exits — ephemeral, not persisted → crash fails safe), `/stop`, `/forceexit`/`/fx`, `/reload_config`, `/blacklist`,`/whitelist`.
- **Hummingbot** (Apache-2): `paper_trade` runtime toggle; persistent top-bar status `paper_trade_mode: ON`; separate paper balances (`balance paper BTC 1000`). `start`/`stop` control execution.
- **Jesse** (MIT): dashboard Paper-Trade toggle; live gated behind licensed plugin; mode bound at session start (restart to change) — same "switch = new session" posture.
- **OctoBot** (GPL-3): paper vs live = **two independent enable flags** — `trader.enabled` (real funds; false = never a real trade = allow_live guard) and `trader-simulator.enabled` (sim portfolio, same execution; no API keys needed). Per-profile per-exchange enable (one bot, many venues each toggled). Real-trader-enabled is orthogonal to simulator → "no real trades" guaranteed independent of strategy/market.
- **OpenAlgo** (AGPL): one Settings "API Analyzer Mode" toggle flips whole platform (real broker ↔ sandbox w/ real prices). Sandbox orders carry **`SB-` ID prefix** (self-evident in logs/journal). Same API both modes (identical strategy code). Don't flip mid-session.
- **ccxt** (MIT): `exchange.set_sandbox_mode(True)` → testnet w/ virtual funds; **must be first call after construction**; **sandbox keys ≠ production keys**. Ideas: bind mode at adapter construction (immutable); separate key sets per mode.
- **NautilusTrader** (LGPL): 3 environment contexts (Backtest / **Sandbox = real data + simulated venue** / Live) sharing one kernel; multi-venue config. **Best kill-switch: RiskEngine 3-state ACTIVE / REDUCING (reduce-only) / HALTED (deny all but cancels)** — one central choke-point. `shutdown_on_error=True`.
- **QuantConnect/Lean** (Apache): paper = a selectable *brokerage* (sim fills on live data), chosen at deploy → model paper/real as interchangeable execution adapters behind one interface.
- **TradingView-webhook bots** (MIT): shared webhook passphrase; optional human-in-the-loop confirm before real orders.
- **Kill-switch convention:** flatten ALL positions + lock account; usually 2 clicks (initiate+confirm).

## PATTERNS TO ADOPT (we have MasterToggle + paper/live + allow_live + kill-switch)
1. **Per-market state objects, not global flags:** each market = `{enabled, mode, allow_live, adapter}`. Order must pass: MasterToggle ON → market.enabled → trading_state ACTIVE (or REDUCING) → (mode REAL → also market.allow_live). Independent Crypto/NSE toggles for free.
2. **Mode = which adapter, not an if-branch:** PaperAdapter (sim fills on real prices) vs LiveAdapter per market; built with mode + creds → immutable per-mode; paper adapters hold NO live keys. Crypto = ccxt set_sandbox_mode; NSE = OpenAlgo analyzer.
3. **Central trading-state gate — adopt Nautilus ACTIVE/REDUCING/HALTED** in front of all execution. Kill-switch = HALTED + flatten + lock. REDUCING = graceful de-risk (exits allowed). Keep Freqtrade `/pause` (per-market soft stop).
4. **Paper↔real = deliberate, confirmed, per-market:** default PAPER; REAL needs allow_live + 2-step confirm; on flip reset/segregate state (separate balances/positions/persistence per mode — Freqtrade fresh-DB, Hummingbot separate balances); don't flip mid-cycle with open orders.
5. **Tag everything with mode + mode-specific ID prefix** (OpenAlgo `SB-`) in the 85-col journal — paper vs real never confusable.
6. **Fail-safe defaults + persistence:** persist enabled/mode/allow_live; keep runtime pause/halt ephemeral (crash → safe config); auto-HALT on internal error.
7. **Dashboard:** color-coded per-market banner (`CRYPTO: REAL ● ACTIVE` / `NSE: PAPER ● HALTED`); buttons: per-market enable, per-market mode (confirm dialog →REAL), global ACTIVE/REDUCING/HALTED, red 2-click flatten-all; show per-mode position/balance counts.
