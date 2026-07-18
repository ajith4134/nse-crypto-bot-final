# X22 — Deep self-analysis + "the assistant trades" experiment (2026-07-18)
Owner: "self evaluate... you did not reach anything close to the goal... find the right advanced
way... find patterns ALL winning/losing trades have... take the place of the brain and do trades."

## 1. THE DECISIVE MEASUREMENT (should have been hour one, not hour twelve)
Across 1,504 closes / 30h, tested EVERY recorded feature for winner-vs-loser separation:

| feature | winners | losers | t | verdict |
|---|---|---|---|---|
| MFE (max favorable) | 5.34% | 1.15% | +25.1 | separates — but it is an OUTCOME |
| MAE (max adverse) | 1.69% | 5.03% | −21.0 | separates — also an OUTCOME |
| hold minutes | 22.95 | 23.01 | −0.02 | nothing |
| entry minute | 29.96 | 28.73 | +1.36 | nothing |
| entry hour | 13.03 | 12.01 | +3.05 | marginal (regime, not signal) |
| direction (short) | 0.38 | 0.38 | +0.34 | nothing |
| leverage | 4.85 | 4.88 | −0.94 | nothing |

Then the decisive one — the brain's OWN decision inputs, on 805 trades with matched entry meta:

| entry-time feature | nW | meanW | nL | meanL | t |
|---|---|---|---|---|---|
| fusion_p_up | 121 | 0.5618 | 144 | 0.5616 | +0.01 |
| ld_p_up | 217 | 0.4592 | 254 | 0.4730 | −1.59 (slightly INVERTED) |
| psych_fear | 372 | 0.0400 | 433 | 0.0402 | −0.02 |
| psych_obi | 372 | 0.0193 | 433 | 0.0297 | −0.39 |
| psych_score | 372 | 0.0103 | 433 | 0.0121 | −0.13 |

**NOT ONE entry-time feature separates winners from losers.** The pattern the owner asked for
is the ABSENCE of one: at entry, winners and losers are statistically indistinguishable in
every dimension we record. We are taking coin flips and then arguing about exit management.

## 2. SELF-EVALUATION — my approach was wrong, specifically
I did ENGINEERING when the situation demanded SCIENCE. Ten experiments (X11-X21), and the
scoreboard splits cleanly:
- **Fixing DEFECTS worked.** X14 (router could only ever choose LONG) is the one clear win.
- **Tuning PARAMETERS did not.** X15/X18 ratchet: −1.95/trade vs −1.94 baseline at n=146 —
  dead even. X17: −2.18 vs −1.94 — worse. X19 halved avg loss (−5.47% → −2.93%) but avg win
  shrank too (+1.86% → +1.10%), so payoff barely moved (0.44 → 0.38 vs 0.93 needed).
**Why:** exit tuning redistributes a distribution; it cannot create an edge that is not there.
I should have run §1 FIRST and refused to tune anything until an entry signal showed edge.

## 3. THE ADVANCED APPROACH (what to do instead)
The correct method, in order, and NONE of it was done:
1. **Label first.** Build (features at decision time) → (forward return at horizon H) for every
   candidate the funnel SEES, not just the ones it traded (survivorship!).
2. **Test for edge before deploying anything.** Purged/embargoed walk-forward CV (López de
   Prado) — never a random split on overlapping time series.
3. **Rank features by information, not by story.** Mutual information / permutation importance
   against the forward label. Our current lenses would score ~0 on today's evidence.
4. **Only then** size, gate, and tune exits — on a signal with demonstrated out-of-sample edge.
5. **Kill the rest.** Ten lenses with no measured information are ten sources of noise and fees.

## 4. "ASSISTANT TRADES" — the result is a NO-TRADE, and that is the finding
I scanned all 877 symbols from raw price structure (no brain signals) requiring: multi-horizon
agreement (1h + 4h + the validated 7d), liquidity ≥ $2.5M/day, room left in the 4h range
(pos < 0.72 long / > 0.28 short), and bar noise ≤ 1.2% (must fit inside the 4% stop).
- First pass (1h+4h only) → 8 candidates. **All 4 I tried to place were REFUSED BY MY OWN GATES**:
  2 illiquid (X16), 2 counter-7d-trend (X17). I had ignored the one rule we validated. The gates
  caught me making the brain's exact mistake — strong evidence the gates are doing real work.
- Second pass (all three horizons + liquidity) → **1 of 877 symbols (0.11%)**, and on inspection
  I reject it too: NFP is +251% in 7 days (vertical repricing, not trend) sitting at pos 0.69.
**My decision as the trader: NO TRADE.** In current conditions a strict multi-horizon filter
finds essentially nothing — while the brain is opening ~40 trades/hour into that same market.
**That gap IS the diagnosis.** The brain has no ability to say "nothing qualifies today"; it is
structurally obliged to trade. A "0% of the universe qualifies" state should produce zero
entries, not forty an hour.

## 5. HONEST ANSWER ON THE 85-90% GOAL
On this evidence it is not reachable by tuning this system, and I should say so plainly rather
than keep shipping increments. 85-90% win rate requires either (a) a genuine predictive signal —
we have measured that we currently have NONE — or (b) an exit structure that books tiny wins and
hides losses, which is the X15 trap: it produced 92%-green ratchet exits while still LOSING money.
The reachable goal is POSITIVE EXPECTANCY, which needs payoff > (1−p)/p. Chasing win-rate as the
target actively causes the losing structure.
