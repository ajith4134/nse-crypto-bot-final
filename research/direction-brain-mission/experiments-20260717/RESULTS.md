# Discussion-session experiments — 2026-07-17 (E1–E6)

Owner asked for a scientist-discussion session, then "do all experiments and check the
results." All six are offline measurement over: `direction_truth_train.jsonl` (40k labeled
claims), feather OHLCV (122 spot + 533 futures pairs, → 07-16 18:55), today's mirror-candle
snapshot (877 symbols, ~10:00→now), `tradesv3.dryrun.sqlite` (6,500 closed trades).
Scripts in this directory; every number below is reproducible by re-running them.
Sanity anchor: the offline scorer reproduces recorded ledger accuracy exactly (0.499 = 0.499).

Clean window = ts ≥ 1784236980 (07-16 21:23, post B1/B2 fixes).

## E1 — The bottom-of-range entry "discovery" DOES NOT REPLICATE (it inverts)

Yesterday (n=35): bottom-entry longs 90% win, top 40%. At scale:

| sample | bottom | mid | top |
|---|---|---|---|
| ALL closed longs, n=3,709 | win 0.405, avgP −1.50% | 0.441, −1.39% | **0.519, +0.16%** |
| CLEAN closed longs, n=223 | 0.512 | 0.565 | **0.596** |

The null grid (8,768 random pseudo-entries, no signal) explains the confusion: at the TOP
of a 30m range the market drifts slightly DOWN (P(up)=0.434 @15m, 0.458 @1h); bottom is a
coin flip. So fixed-horizon LONG **claims** at top score badly (0.368 @1h) while actual
**trades** entered at top win the most — exits harvest the initial momentum before the
fade. Claim-sign-at-horizon and trade-outcome are different quantities; conflating them
is how the n=35 result got believed.

One real positive: SHORT claims at top-of-range score **0.672 @1h (n=583)** vs 0.542
mechanical baseline — genuine skill above mechanics, in the opposite corner from where
we built the gate.

**Consequence:** REFLEX_POS_GATE (refuse LONG at pos>0.85 / SHORT at pos<0.15) was built
on the failed finding and may be refusing the best trade entries. It records refusals as
`reflex_poscut` counterfactuals — the pre-registered rule stands and will adjudicate:
if refused entries score BETTER than taken ones, the gate goes.

## E2 — BTC-residual hypothesis FALSIFIED (my own discussion claim was wrong)

Median BTC R² on 5m returns across 336 symbols: **0.107** (p25 0.016, p75 0.242). This
universe of small alts is overwhelmingly idiosyncratic — "per-coin direction ≈ predicting
BTC" is false here. Residualizing changes pooled accuracy not at all (0.501→0.499); no
hidden cross-sectional skill unlocked. Side-finds: `breadth_tilt`'s 1h badness lives in
the common factor (raw 0.393 → resid 0.476 — it calls the market wrong, not the coins);
`spillover_seesaw` 1h raw 0.823 (n=113) is E3-suspect but survives residualization (0.646).

## E3 — Null harness: the ledger is NOT hallucinating, but ~30% of "proven" buckets are noise

Buckets = source×horizon×regime, n≥30, "proven" = Wilson 95% LB > 0.5, clean window
(33,521 claims). Real: **22 proven buckets**. Shuffled labels (500 perms, base rates
preserved): mean 6.6, p95 10, max 14 → P(null ≥ 22) < 0.002. Signal is real, **but
empirical FDR ≈ 0.30** — ~7 of our 22 trusted buckets are fake, and fakes concentrate in
the spectacular small-n rows (0.90+ acc at n≈30: `onchain_flow 1h trend_down` 0.938/n=32,
`spillover_seesaw 1h transition` 0.903/n=31…). The trustworthy core is the large-n rows:
`indicator_fusion 1h` 0.647/n=623, `river_online 1h` 0.569/n=1447, `funnel_mtf_vote 15m`
0.565/n=1263.

## E4 — Within the clean window, source RANKINGS are noise at half-day scale

Clean-window split-half Spearman over 15 sources (n≥60/half): **rho = −0.286 (p=0.30)** —
first-half accuracy predicts nothing about second-half. Day-to-day (07-16→07-17)
rho = +0.559, but that straddles the era fix so it partly measures artifact persistence.
Only `indicator_fusion` stays near the top in every cut (0.598/0.552 clean halves).
**Consequence:** decayed "recent reliability" computed over hours ranks noise; it needs
longer windows and/or much harder shrinkage toward pooled estimates (E3's FDR points the
same direction).

## E5 — Profit decomposition: the bottleneck is LOSS SIZE, not direction

Clean window (825 trades): win% **0.565** (fine!), P&L **−1,973 USDT**, because
avgWin +10.09 vs avgLoss −18.59 → payoff 0.54 vs breakeven-at-that-win% 0.77.
Exit table: `stop_loss` 234 trades **−5,900** (−25 avg); `tailgate_lock` 350 wins of
**+4.1 avg** (locks pennies); `roi` +2,874. We cut winners at +4 and ride losers to −25.
Only `filter:momentum` clears both bars (win 0.650, payoff 0.836, +144). Top-5% of trades
= 31–43% of gross wins (tail-heavy confirmed).

## E6 — Adverse selection is real; passive entries would make it WORSE

Winners bounce: median adverse excursion 35bps; 26% of clean winners never gave back
10bps (bounce trades win **0.968**). Losers run **202bps** median against entry.
Counterfactual "limit 10bps better" book keeps only dip-fills: win 0.565→0.493, P&L
−941 worse. Retires the wait-for-bottom-fill idea (with E1) AND warns that live slippage
asymmetry will eat some paper edge.

## E6b — Early-abort counterfactual: the single biggest lever found today

Abort any trade at X bps adverse excursion (exit at −(X+10)bps, estimate):

| X | est clean P&L | vs actual −1,979 |
|---|---|---|
| 30 | −743 | +62% |
| **50** | **−316** | **+84%** |
| 100 | −724 | +63% |
| 200 | −998 | +50% |

Monotone improvement across the whole grid even while cutting 177/466 winners at X=50.
The 35-vs-202bps winner/loser excursion separation means losers announce themselves
early; current stop geometry ignores this.

## Combined verdict

1. Direction accuracy is not the profit bottleneck (E5); loss geometry is (E5+E6b).
2. The reliability machinery has real signal (E3) but trusts noise at small n (E3 FDR
   0.30) and at short windows (E4) — raise evidence bars, shrink harder.
3. Two shipped features rest on shaky premises: REFLEX_POS_GATE (E1 — inverted at scale;
   its own counterfactual will adjudicate) and any small-n bucket promotion (E3).
4. Real new edges found: SHORT-at-top-of-range claims 0.672@1h (E1b); winners-bounce
   early-abort structure (E6/E6b).
5. Two of the discussion hypotheses died honestly: BTC-residual reframing (E2),
   wait-for-bottom entries (E1+E6).

## Proposed next actions (need owner approval — none implemented)

- A) Exit geometry experiment ON PAPER: add an early-abort arm (~50bps adverse, as a new
  exit-policy bandit arm so it must EARN its place) + widen tailgate lock threshold.
- B) Raise ledger promotion bar: bucket trusted only at n≥100 AND Wilson LB>0.52 (or BH
  correction across buckets); keep small-n buckets learning but not steering.
- C) Reflex gate: let the pre-registered reflex_poscut verdict run; if refused ≥ taken
  accuracy at n≥100 → remove the gate (E1 predicts it will be removed or inverted).
- D) New lens candidate: short-at-range-top (0.672@1h, n=583) — paper lens lane first.
- E) Un-cut the winners: tailgate_lock locking +4 avg while roi makes +27 suggests the
  lock threshold is far too tight; sweep it in OPE replay.
