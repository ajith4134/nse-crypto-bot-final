# Editable paper-money / virtual-wallet engines — OSS patterns (web research, 2026-06-28)

> Ideas only. Saved verbatim. License noted, not a filter.

- **Freqtrade** (GPL-3): `dry_run_wallet` (number) or `--dry-run-wallet/--starting-balance`; effective cash = wallet × tradable_balance_ratio. Restart with new value resets; wallet recomputed = start + closed-trade profits. **PR #11000: dict wallet** = per-currency starting balances (cross-margin groundwork). Market fills vs orderbook ≤5% slippage; limit fills/timeout.
- **Hummingbot** (Apache-2): `balance paper [asset] [amount]` per-asset virtual balances; defaults ~1000 each of stables + 10 ETH; persisted in `conf_client.yml`; per-`<exchange>_paper_trade` namespace; live-orderbook fills. No 1-click reset found.
- **Backtrader** (GPL-3): `broker.setcash()`, `setcommission()` (% or fixed/futures), slippage `slip_perc/slip_fixed/slip_open/slip_limit` or subclass; volume-based fills, bracket/OCO.
- **Backtesting.py** (AGPL): `Backtest(..., cash=, commission=, slippage=)`; `trade_on_close`.
- **Alpaca** (SaaS): paper starts $100k; **can't change after creation → must RESET (arbitrary new amount)** or create/delete **multiple paper accounts**; reset rotates API key. Isolation = separate key + `paper-api.alpaca.markets` endpoint. Fills marketable vs best bid/ask; ~10% partial-fill; NO slippage/impact/fees sim.
- **QuantConnect/LEAN** (Apache): `SetCash()` multi-currency; **reality models = pluggable fee/fill/slippage/buying-power objects per security, selected by brokerage profile** (best modular design).
- **OctoBot** (GPL-3): `starting-portfolio` (any currencies); **resets to starting on every start UNLESS "multi-session-profitability"** (opt-in persistence); configurable taker/maker fees; same config feeds sim + real.
- **Jesse** (MIT): per-route starting balance + fee/slippage; Monte-Carlo (order-shuffle + candle-perturbation).
- **ccxt** (MIT): `set_sandbox_mode` = testnet (realistic infra, **opaque/inconsistent fills**) → custom order-book-walking engine = controllable/reproducible (what we have).
- **OpenAlgo** (AGPL, richest NSE ref): default ₹1cr `starting_capital` (configurable); **`reset_day`/`reset_time` scheduled auto-reset** (→ start capital, clear balance/margin/PnL/positions/holdings); fill engine polls ~5s (market@bid/ask, limit on LTP cross, SL/SL-M trigger); `margin = qty*price/leverage` (CNC 1x/MIS 5x/Fut 10x/Opt 1x); **dedicated `db/sandbox.db`** with SandboxOrders/Positions/Funds/Holdings(T+1)/DailyPnL; thread-safe FundManager mutex; `is_sandbox_mode()` routing; ~5s MTM.
- **AlgoTest / Streak** (India consumer): paper = forward test on live ticks w/ virtual money.

## PATTERNS TO ADOPT (extend our crypto PaperEngine: orderbook-walk + positions/PnL/liquidation)
1. **Per-market wallet objects** (Freqtrade dict + OpenAlgo SandboxFunds): `Wallet` keyed by market/currency (NSE→₹, crypto→USDT) with starting_capital/available/used_margin/realized_pnl. Crypto multi-asset.
2. **Editable balance API:** `set_starting_capital(market, amt)` (clean reset, clears positions), `top_up(market, amt)` (add cash, keep positions), `reset(market)` (back to start, flat).
3. **Multiple named paper portfolios** (Alpaca): `portfolio_id` + leaderboard.
4. **Pluggable reality models** (QuantConnect): FillModel / SlippageModel / FeeModel / MarginModel swappable per market (orderbook-walk = one FillModel).
5. **Realistic fills:** orderbook-walk + slippage cap (5%); limit-on-cross; optional probabilistic partial fills (~10%); commission/brokerage on fill.
6. **Per-product leverage/margin** (OpenAlgo): used_margin + margin_blocked + liquidation (have it).
7. **Persistence + hard isolation:** dedicated `paper.db`/namespace separate from real; tables orders/positions/funds/daily-PnL; thread-safe; `is_paper_mode()` routes all.
8. **Equity curve + EOD DailyPnL snapshots** → curve + leaderboard.

### Nice-to-haves
1-click reset + scheduled auto-reset (OpenAlgo); reset-on-start vs persist toggle (OctoBot); per-market configurable fees/slippage; multiple virtual accounts + leaderboard; Monte-Carlo/replay/what-if (Jesse); periodic MTM; T+1 settlement (NSE ₹ side).
