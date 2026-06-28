# NSE off-hours paper trading — how OSS bots do it (web research, 2026-06-28)

> Ideas only (not code to copy). Saved verbatim. CPU-first lens. License noted, never a filter.

NSE trades 09:15–15:30 IST weekdays (minus holidays); to paper-trade 24/7, projects use 5 patterns.

## OpenAlgo — Sandbox/Analyzer mode (closest to our stack)
- https://github.com/marketcalls/openalgo · docs.openalgo.in/new-features/api-analyzer · docs.openalgo.in/developers/design-documentation/configuration
- Simulated-order engine intercepts API order calls (Analyzer toggle → Sandbox vs Real engine). Uses broker REAL-TIME data, fills locally, never hits exchange. Default ₹1cr capital, leverage 5x eq/10x fut.
- Fill loop: background thread polls **every 5s** — fetch open orders → quotes → fill (BUY@ask/SELL@bid market; LIMIT when LTP crosses). Square-off via APScheduler cron (NSE 15:15, CDS 16:45, MCX 23:30); CNC→holdings at midnight (T+1).
- **Off-hours (partly unverified):** engine runs 24/7 but **fills depend on a live quote feed** — when NSE shut and quotes stale, orders sit pending. So feed it cached prices off-hours. AGPL, CPU.

## Backtrader — replaydata() (replay history as if live)
- backtrader.com/docu/data-replay — feeds historical bars incrementally, resampled up, so strategy "sees" each bar build tick-by-tick like live. Preloading auto-disabled; can pace to wall-clock. Point at cached intraday history → strategy can't tell it's not live. GPLv3, CPU.

## Freqtrade — dry_run (crypto; the one-codepath pattern)
- freqtrade.io/en/stable/bot-basics — identical live loop, simulated wallet (`dry_run_wallet`), market fills vs orderbook w/ ≤5% slippage, limit fills when price reached. Crypto never closes; borrow the "boolean flips real vs sim execution" design. GPLv3.

## Jesse — unified backtest→paper→live codebase (MIT). Monte-Carlo candle-perturbation mode = idea for varied synthetic off-hours scenarios.

## AI-Trader (aaryansinha16) — explicit LIVE/PAPER/REPLAY for NSE F&O (MIT)
- https://github.com/aaryansinha16/AI-trader — LIVE (9:15–15:30, TrueData WS); PAPER (live signals, no capital); **REPLAY/BACKTEST = off-market tick-level sim** over historical ranges; exit loop walks individual option ticks within each minute (tick-precise SL/target). Tick/min data in TimescaleDB, REST backfill for gaps. **Same 80 macro + 5 micro indicators in live AND replay → signal parity.** Cleanest NSE-specific 3-mode design.

## Session/calendar awareness
- `pandas_market_calendars` (https://github.com/rsheftel/pandas_market_calendars) ships NSE calendar under MIC **XNSE** (holidays + open/close, no network). `exchange_calendars`/`trading-calendars` also cover India. Data libs: nsepython, jugaad-data, breeze-connect. Gate: `is_open = XNSE.open_at_time(now_ist)` → false → switch LIVE→REPLAY.

## Synthetic ticks within a bar (when only OHLC cached)
- MT5 model: 4 OHLC ticks/bar OR full interpolation O→H→L→C. OHLC→tick ordering heuristic: up-bar O→H→L→C, down-bar O→L→H→C (so SL/target evaluated on a plausible path). Brownian-bridge/GBM pinned to O/C touching H/L = most realistic. Inverse of `df.resample('1Min').ohlc()`.

## Broker sandboxes mostly absent for NSE
- Zerodha Kite: **no sandbox** (only postback URLs) → must paper-trade locally (why OpenAlgo analyzer exists). Upstox/Fyers limited test tokens (unverified).

## PATTERNS TO ADOPT (CPU-first, we have OpenAlgo analyzer + tick cache + per-market toggle)
1. **Calendar-gated mode switch (the spine):** every loop, ask XNSE "open now?" → open=LIVE/analyzer; closed=REPLAY against tick cache (AI-Trader's split). Drive the per-market toggle automatically.
2. **Candle/tick replay as a live feed (off-hours engine):** Backtrader replaydata idea — stream cached history bar-by-bar, optionally wall-clock-paced; identical strategy+indicators live vs replay (signal parity).
3. **Keep OpenAlgo analyzer as the order/fill simulator, but feed it prices** off-hours (inject cached LTPs into the quote path → reuse its accounting/square-off, swap only price origin).
4. **Synthetic-tick interpolation for gaps** (OHLC ordering heuristic / Brownian bridge) so SL/target/trailing fire realistically off-hours. CPU-trivial.
5. **One continuous asyncio/APScheduler loop, mode-aware payload:** never-stopping loop; only branch = what feeds the strategy (live vs replay/synthetic) + which fill path. Journal + UI stay identical across modes.

Unverified: OpenAlgo exact 24/7-vs-quote behaviour off-hours; Upstox/Fyers sandbox availability.
