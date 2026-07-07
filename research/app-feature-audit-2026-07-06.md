# App Feature Audit — Binance & Upstox vs the brain's App Driving School (2026-07-06)

Online research of the two trading apps' full built-in feature sets, cross-checked against what the
brain has discovered/saved in `app_school_map.json` (routes + pages + links + controls).

## Binance — built-in features (online)
- **Markets:** Spot (600+ coins, 1,500+ pairs), Margin (3x–10x, isolated/cross), Futures (perpetual +
  quarterly, up to 125x, 250+ contracts), **Options** (eoptions).
- **Order book / market depth** — customizable precision, avg price, cumulative view.
- **Futures analytics data** (the "Trading Data" page): open interest, **top-trader long/short ratio**,
  **long/short ratio**, **taker buy/sell volume**, **funding rate** (8h).
  → hub URL: `/en/futures/funding-history/perpetual/trading-data`
- **Liquidation** monitoring (mark-price / forceOrder feed on the trade page).
- Movers / gainers / losers, **screener** (markets filters), Convert, Earn.

## Upstox (Pro Web 3.0) — built-in features (online)
- **Option chain** with full Greeks (delta/gamma/theta/vega/rho), IV per strike, **OI**, **PCR**,
  **max pain**, **India VIX**; option-strategy order mode.
- **Charts** — TradingView, 100+ indicators, 80+ drawing tools.
- **Watchlists** (pin symbols), **Market depth** (30-level on Plus tier, tick-by-tick).
- **Top Gainers / Losers / Market Movers / Shakers**, **Screener** (Dartstock stock analysis).
- **Derivatives across segments:** Equity, **Options**, **Commodities (MCX/NCDEX)**, **Currency** —
  NSE / BSE / NCDEX / MCX. Plus IPO, Mutual Funds (not trading-signal data).

## What the brain has saved (app_school_map.json)
- **Binance — partial (50% goal routes):** 8 pages, 354 links, 643 distinct controls. Reached
  markets/overview, futures/home, futures/BTCUSDT, trade/BTC_USDT, eoptions/BTCUSDT, earn. Learned
  routes: movers, spot_symbols, futures, orderbook. MISSING: long_short, liquidation, options,
  screener — the deep data-panels/tabs weren't catalogued and the Trading-Data page wasn't visited.
- **Upstox — barely (17%, was blocked):** only 6 ACCOUNT pages (holdings/orders/positions/funds/
  charts) + a login redirect. Market-data pages (option-chain, discover, watchlist, F&O) never
  reached because the run_funnel_loop held the Upstox browser profile LOCKED. Freed 2026-07-06.

## Gaps closed / actions
1. **[done]** `import os` fix in the dashboard route (Learn-the-app button crashed).
2. **[done]** Active SEED-SWEEP: navigate straight to each missing goal's data-hub URL + harvest from
   real traffic (wide 60s window + scroll to fire lazy panels). Binance 38%→50% (learned orderbook).
3. **[done]** Freed the Upstox browser profile (stopped the funnel) → Upstox re-explorable.
4. **[done]** Binance `long_short` seed → the authoritative Trading-Data hub (long/short + OI + taker).
5. **[monitor running]** `run_school_monitor` drives both brokers to 100% (or plateau).

## Suggested ADDITIONAL capabilities to pull from the two apps (proposed goal expansion)
- **Binance:** `taker_volume` (taker buy/sell — momentum-of-aggressors), `open_interest` as its own
  goal (OI trend = conviction), `margin` rates/pairs (borrow cost = leverage sentiment).
- **Upstox:** `commodities` (MCX/NCDEX) + `currency` derivatives segments (whole markets currently
  unmapped); options analytics — `greeks`, `pcr`, `max_pain`, `india_vix` (the edge for F&O).
- **Both:** persist per-feature COLUMNS the app exposes (the option-chain Greeks columns, the
  trading-data ratios) into the learning-columns store so the trade table can use them.
