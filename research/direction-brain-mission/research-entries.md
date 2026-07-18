# Entry / direction research — 2026-07-18 (owner re-authorized online research)

Workflow wf_5d8279d1-443. 42/106 agents completed; the rest died on a session limit
mid-verification. NOTE: "unverified" below = the 3-vote check could not RUN, not that the
claim was refuted. Zero claims were refuted.

## VERIFIED (2-3 vote adversarial confirmation)

1. **Intraday trend-following in BTC had NO edge, even pre-fees** (2011-2019, exhaustive
   MA scan 1-1000h). arXiv 2009.12155: "notable absence of profitable intra-day trend
   following strategies for BTCUSD spot... in spite of the considerable interest afforded
   to such strategies." → our momentum/live_loop lanes are chasing a documented non-edge.
2. **Walk-forward optimal trend lookbacks were 6-40 DAYS, not hours** (SMA 141h/781h;
   EMA 721/951; DEMA 791/981). Same source. → crypto trend edge lives far above our
   15m-4h horizon.
3. **BTC intraday predictability is REAL but contains BOTH momentum and reversal**
   components (HF data 2013-2020). ScienceDirect S1062940822000833. → a pure-momentum
   reading of an intraday signal is right only half the time by construction.
4. **That predictability is REGIME-DEPENDENT** — the momentum-vs-reversal pattern flips
   with large intraday jumps, FOMC events, liquidity level, and crisis regimes. Same
   source. → regime/jump/liquidity conditioning BEFORE applying a momentum signal has
   direct empirical support. This is the single most actionable verified finding.

## UNVERIFIED (verification never ran — treat as LEADS, not evidence)

- Cost-aware trade filtering on hourly BTC futures: acting only when forecast magnitude
  > lambda x cost (lambda=2.0, c=10bps) cut trades 10,619 -> 251 and flipped annualized
  return -64.0% -> +65.4% (arXiv 2606.00060v1). Directly matches our fee problem (fees =
  31% of losses) — but UNVERIFIED, so it justifies an EXPERIMENT, not a belief.
- Unfiltered sign-based ML entries: +73.5% gross -> -64.0% net at 10bps (same source).
- No-trade-region theory: optimal policy skips trades inside a band of width O(cost^1/3);
  welfare loss O(cost^2/3) (arXiv 1612.01302).
- Daily-frequency crypto: filter + channel-breakout rule families beat MA/oscillator
  families; breakeven costs 7.9-147.6 bps (Hudson-Urquhart 2019). DAILY, not intraday.

## What this says about OUR system
Verified findings 1+2 explain the measured bleed: live_loop (momentum fallback) and the
momentum-family lanes hunt an edge the literature says does not exist at our horizon,
while our only green lane (filter:squeeze) is volatility-compression = NOT trend-chasing.
Finding 4 says the fix is regime conditioning, not a better momentum indicator.
Finding 3 warns that any intraday signal read as pure-momentum is ~coin-flip.

## RECOVERED from the stopped run (138 agent results preserved in journal.jsonl; 73
## substantive claims). Owner stopped new agents 2026-07-18 — nothing was lost.

### Directly contradicts what our momentum lanes assume
- **Crypto momentum is real at MULTI-DAY horizons, not intraday**: top-quintile 30-day
  returns kept outperforming over the NEXT 7 DAYS (37.8% ann. vs −33.8% bottom,
  Apr2018-Nov2022, gross). Our lanes trade 15m-4h.
- **Fee drag erodes even that**: at ~50bp round-trip, top-quintile annualized returns fell
  30pp in-sample / 12pp out-of-sample — at WEEKLY rebalance. We rebalance ~50x/hour.
- **Momentum's cross-sectional edge DEGRADES in the liquid large-cap subset** (no decile
  structure in top-30 Binance perps) while it may work on a broader universe.
- CTREND (ML trend, price+volume, multi-horizon, 3,000+ coins) DOES survive costs and
  persists in big liquid coins — but at portfolio-rebalance frequency, not intraday.

### Selectivity / fee drag (validates X12, extends it)
- Optimal policy under proportional costs has a NO-TRADE REGION of width O(cost^1/3);
  welfare loss O(cost^2/3). Act only when desired change exceeds a cost-set threshold.
- Costs are KNOWN and certain; expected returns are UNCERTAIN — so the cost side should
  dominate marginal decisions when edges are small. (Exactly our regime.)
- Prefer SLOWLY-DECAYING alphas: equal predictive power but less turnover. A system
  bleeding on fees should shift to slower signals, not better fast ones.
- Time-varying-signal strategies (momentum/mean-reversion) suffer AMPLIFIED cost losses
  vs static portfolios — they can't just trade less without losing the timing.

### Session / time (actionable, crypto-specific)
- BTC has persistent intraday seasonality: **21:00-23:00 UTC** (after global equity closes)
  delivers the highest average returns; a hold-only-that-window strategy ~33% annualized.
- On NYSE-open days most BTC gains accrue OVERNIGHT; US-hours returns modest and volatile.
  Pattern REVERSES on weekends/holidays → session-aware switching, not always-on.

### Symbol selection (concrete floors)
- Remove the bottom 20% of contracts by trailing 30-day dollar volume before any signal.
- Reference universe: top-30 Binance perps by trailing 30-day dollar volume, ex-stables
  and wrapped tokens.
- Relative volume: >=2.0x average (10-20d lookback) to concentrate on participation;
  breakouts at RVOL>=1.5x have better follow-through, >=3.0x stronger, but >10x can be
  climax/exhaustion. **Use TIME-ADJUSTED RVOL** (vs same time-of-day) — raw RVOL is biased
  by the U-shaped intraday volume curve.

### Funding / carry (our filter:funding_extreme lane)
- Funding buckets: +0.01%..+0.05%/8h = bullish crowding; -0.01%..-0.03% = bearish;
  beyond +/-0.1% = stress. Fixed interest component 0.01%/8h = ~10.95%/yr cost floor.
- Sustained +0.05%/8h ~= 54.75% annualized cost on longs → crowded longs self-limiting.
- Carry is driven by TREND-CHASING (past week/month BTC returns → larger basis): elevated
  funding marks crowded speculative longs, NOT bullish confirmation.
- Extreme positive carry FORECASTS CRASHES; +10% standardized carry predicts +22% sell
  liquidations (% of OI) next month. Contrarian direction, quantified.
- Caveat logged honestly: the popular "extreme funding = top/bottom" blog claims carry NO
  thresholds, horizons, or backtests — folklore until measured.
