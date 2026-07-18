# X23 RESULT — the market is MEAN-REVERTING intraday, not momentum-continuing
Dataset: 1,449,379 labelled rows, 533 symbols, 5m bars, 2026-03-08 → 07-18.
Out-of-sample = chronological holdout with embargo, n=550,765. Shuffled-label controls ~0.002.

## 1. THE CORE RESULT — monotone, huge t, survives the null
Mean forward 1h return, bucketed by the PAST 1h return (the "momentum" the strategy chases):

| past 1h | forward 1h |
|---|---|
| −1.74% (biggest fallers) | **+0.0561%** |
| −0.42% | +0.0108% |
| −0.03% | −0.0121% |
| +0.35% | −0.0287% |
| +1.78% (biggest risers) | **−0.0727%** |

Perfectly MONOTONE across 5 buckets of 110,153 each. ret_1h IC = −0.062, t = −46.1.
Every momentum feature is NEGATIVE: dist_ema1h −0.060, ret_4h −0.058, pos_4h −0.052,
pos_1h −0.051, ret_15m −0.039. All beat their shuffled controls by >20x.

**⇒ Entering ON momentum earns −0.229% per trade NET of cost.** That is not an exit problem,
a sizing problem, or a direction-classifier problem. Our momentum lanes have been
systematically buying what is about to fall, ~40 times an hour. This single number explains
the entire 2026-07-18 audit: ~50% win rate, no entry feature separating winners from losers,
and ten experiments unable to move net P&L.

## 2. THE ONE POSITIVE EDGE — buy big intraday drops
After a ~3.6% hourly DROP (bottom 5% of ret_1h): forward 1h = **+0.174%** (+0.074% net),
n=27,539 out-of-sample. Shorting big RISES also works but is ~breakeven (+0.004% net) —
**dip-buying beats rip-shorting**, an asymmetry worth remembering.
Filtered by our own liquidity floor: +0.165% (+0.065% net), n=23,929.

## 3. ⚠️ TWO OF MY OWN CHANGES ARE CONTRADICTED BY THIS DATA
**(a) X17 (counter-trend refusal) would BLOCK the best signal.** Split the dips by 7d trend:
- dip in a 7d DOWNTREND: **+0.281% (+0.181% net)**, n=13,542 ← the best edge in the dataset
- dip in a 7d UPTREND: +0.014% (−0.086% net), n=10,387 ← LOSES
Buying a dip in a downtrend IS a counter-trend long — exactly what X17 refuses. X17 was
validated UNCONDITIONALLY on live trades (t=2.38); this is CONDITIONAL on a dip having just
happened. Both can be true, and the conditional one is where the money is.

**(b) X19 (4% stake stop) would stop out most of these winners.** Median MAE inside the hour
for dip trades is −1.15% of PRICE; at 5x leverage our 4%-of-stake clamp = 0.8% price, so
**62.6% of these trades would be stopped before the reversion arrives.** The edge exists but
is NOT harvestable at current leverage+stop. Harvesting it requires lower leverage or a wider
stop — the opposite direction from X19.

## 4. HONEST LIMITS
- The edge is THIN: +0.065-0.181% net per trade. Real slippage on a fast-falling symbol
  (exactly our entry condition) can erase it. Paper-verify before believing it.
- Win rate is **53.5%** — nowhere near the 85-90% goal, and this is the BEST signal in
  1.45M rows. The goal as stated is not reachable; positive expectancy is.
- FAT LEFT TAIL: p1 = −8.89%, worst = −64.75%. Dip-buying dies from the dip that does not
  stop. Position sizing and a catastrophe stop matter more than the average.
- One regime (Mar-Jul 2026). Re-test after any regime change.

## 5. WHAT THIS OBLIGES US TO DO (per the pre-registration)
The pre-registration said a PASS means "build the entry rule from the winning features ONLY".
The winning rule is the INVERSE of what the system currently does:
1. Stop entering on momentum ignition — it is measurably negative-expectancy.
2. Test a dip-entry lane: liquid symbol, bottom-5% hourly move, 7d downtrend, LONG.
3. Re-examine X17 (it blocks this) and X19 (its stop pre-empts the reversion) — do NOT
   simply revert them; they were validated on the unconditional population. The correct
   move is to make the dip lane EXEMPT from both, and A/B it.
