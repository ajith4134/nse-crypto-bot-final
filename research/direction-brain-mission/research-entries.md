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
