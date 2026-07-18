# X23 pre-registration — "catch momentum as it ignites, take profit every time"
Written BEFORE looking at the result. Owner's strategy, stated 2026-07-18:
"scan and pick trades that are going to rise or entering momentum, enter at the momentum,
take some profit every time."

## The claim in testable form
At an intraday horizon (15m-2h), a symbol that has JUST STARTED moving (short-horizon return
turning positive, volume expanding, range breaking out of compression) continues far enough,
often enough, to clear round-trip cost (0.10% of notional).

## Features that encode "entering momentum" (all causal, from bars strictly before entry)
- `ret_15m` — the ignition itself (just started moving)
- `vol_ratio` — recent volume vs 24h baseline (participation arriving)
- `squeeze` — current 1h range vs the 24h norm (compression → expansion)
- `pos_1h` / `pos_4h` — where in its range (ignition early vs already extended)
- `trend_agree` — 15m/1h/4h/7d agreement (the one live-validated rule, X17)
- `range_1h_pct`, `med_bar_pct` — is there enough movement to pay for the trade

## PASS criteria (any ONE is a genuine finding; all must beat the shuffled control)
1. **IC**: out-of-sample rank IC vs forward return |IC| > 0.02 AND |t| > 3 AND at least 3x
   the shuffled-label control IC.
2. **Monotone gradient**: quintile means of forward return increase (or decrease) in ORDER
   across all 5 buckets — the signature that convinced us on liquidity, and the one a fluke
   almost never produces.
3. **Net-of-cost spread**: top-minus-bottom quintile spread EXCEEDS 0.10% round-trip cost.

## FAIL means (state it now so it cannot be rationalised later)
If no ignition feature clears the bar, then "enter as momentum starts" has NO measurable edge
at 15m-2h in this universe — and the honest conclusion is that the strategy cannot be made
profitable by better execution, sizing, or exits. That would explain every result of
2026-07-18: win rate ~50%, no entry-time feature separating winners from losers, and ten
experiments that could not move net P&L.

## What we do on each outcome
- **PASS** → build the entry rule from the winning feature(s) ONLY, size it, and A/B it live
  against the existing lanes with a pre-registered verdict.
- **FAIL** → stop tuning this system. Either find a different data source with real
  information (order-book microstructure at sub-second scale, liquidations, cross-exchange
  flow) or accept that intraday perp scalping on public candles is not a solvable problem
  with what we have. Do NOT ship more exit tweaks.

## Honesty notes
- Labels are non-overlapping (sample_every=12 bars = 1h stride) so significance is not inflated.
- Train/test is CHRONOLOGICAL with an embargo — never random.
- Every test runs beside a shuffled-label control; the control is the referee.
- ~533 symbols x ~4.5 months of 5m bars — the whole universe, not the traded subset, so there
  is no survivorship bias.
