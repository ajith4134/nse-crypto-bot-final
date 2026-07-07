# vp5 — "Autonomous Kraken Trading Bot — Self-Improving AI Workflow" (videoplayback (5).mp4, 6:20)

## One-paragraph summary
A solo dev ("The Efficient Dev", German channel) runs a Python **Kraken crypto bot on a
Raspberry Pi** that is fully self-improving: 3 parallel AI sub-agents (running via
OpenClaw sessions with grok-code-fast models, visible in the left terminal) — **Strategy
Agent** (pulls setups from trading classics: Bollinger-band breakouts, 1-2-3 reversals),
**Data Pattern Miner** (mines tick-level NAS data for patterns, e.g. lowered the RSI
threshold 33→30), **Risk Metrics Improver** (Sharpe/Sortino/Kelly sizing, max-drawdown
limits, auto-stops) — generate CODE changes with Grok, push to a **dev git branch**, the
system backtests dev vs main on BOTH a 30-day and a 1-year tick-level simulation with
real fees/slippage, and only if dev beats main on equity + Sharpe + drawdown does it
**auto-merge and restart the live bot** — a 24/7 autonomous optimization loop, watchable
on a 24/7 YouTube live log stream.

## Every distinct idea (timestamp + frame refs)
1. **The flow diagram** (static, all frames): Bot Startup & Config → Load Historical Data
   from NAS (tick-level + trade history) → AI Agents Generate Improvements (Grok model;
   Strategy Agent ⚙ / Data Pattern Miner 📊 / Risk Metrics Improver 🛡) → Push Changes to
   Dev Branch (git) → Backtest Dev vs Main (30 days + 1 year NAS data) → Check if Dev >
   Main (Equity + Sharpe Ratio + Drawdown) → No: Discard & Retry (generate new
   improvements) / Yes: Merge & Restart Bot (deploy to live trading) → 24/7 Autonomous
   Optimization (24/7 self-optimization loop).
2. **Base bot** [00:36–01:27]: Python, trades EUR pairs (BTC/ETH/SOL+) on Kraken API from
   a Raspberry Pi; indicators RSI/SMA/momentum scoring; reconstructs positions from trade
   history; fee-aware; built-in stop losses, drawdown limits, volatility adjustments;
   currently ~€20 live capital (started €200, bought SOL) — will add funds after next
   improvements.
3. **Multi-edge signal engine** [01:52–02:18]: mean reversion for oversold (buy RSI<30 in
   bull regime) + trend following; profit targets (~10%) or hard stops; shorting with
   leverage caps.
4. **Risk-off behavior** [02:18–02:35]: switches to risk-off in volatile periods, reduces
   position size, pauses after losses — "designed to survive crypto markets".
5. **Backtesting discipline** [02:35–03:02]: >1 year of Kraken tick-level history on a
   NAS; simulations include real fees and slippage; baseline ≈17% annual return; pushing
   for better risk-adjusted returns.
6. **Books as strategy source** [03:12–03:30]: Strategy Agent implements setups from
   trading literature (John Carter's "Mastering the Trade", price-action books).
7. **Promotion gate** [04:07–04:25]: agents (Grok) write code → dev branch → auto
   backtest vs main on 30d AND 1y → merge + live restart only if better on all three
   metrics; no manual intervention.
8. **Status** [04:45–05:21]: ~90 trades, ~39% win ratio, conservative due to low capital;
   loop actively improving RSI, sizing, patterns; target 5–10% above baseline annually;
   "you're not gambling, we are engineering".
9. **Next steps** [05:28]: more agents, multiple LLMs, external data integration, Monte
   Carlo simulations.
10. **Transparency** [05:50–06:12]: open GitHub repo, Discord, and a 24/7 YouTube LIVE
    LOG STREAM of the bot trading (f_0610: "KRAKEN BOT — LIVE LOG STREAM", balances, top
    movers, open positions, risk hub panels).

## Open questions
- None blocking ("ASE/ASI" in transcript = RSI mis-transcription; "SMR" = SMA; confirmed
  by diagram).
