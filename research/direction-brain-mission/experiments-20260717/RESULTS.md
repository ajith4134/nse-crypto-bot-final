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

## Follow-up: owner approved "do A and E first then the rest" — ALL IMPLEMENTED same day

- **A) early_abort exit arm — SHIPPED.** New bandit arm in exit_policy (XP_ABORT_BPS=50,
  price-based bps so leverage never scales the trigger); survivors managed by the normal
  ratchet; wired in brain_executor._tailgate_pass. It must earn its place via Thompson
  sampling like every arm. 6 new tests.
- **E) tailgate sweep — RAN (e_tailgate_sweep.py), and it REFUTED the E5 proposal text.**
  269 replayable clean trades, (arm × giveback) grid, optimistic (exit at lock) and
  pessimistic (exit at 5m bar close) variants: magnitudes disagree (+1,248 vs −676 at the
  tight corner) but the ORDERING is identical in both — tighter arm and tighter giveback
  rank better monotonically, and both variants beat the current (3.0, 0.30) point.
  "Loosen the locks" was wrong; the fade-y tape wants profits taken fast. APPLIED
  crypto-only (market isolation): TAILGATE_ARM_PROFIT_PCT_CRYPTO=1.0 +
  TAILGATE_DIST_MAX_CRYPTO=0.2 in .env, backed by new market-scoped override code in
  profit_tailgate (+2 tests). NSE and sandbox untouched.
- **B) trust bar raised — SHIPPED.** LEARNED_DIR_MIN_N 30→100, new LEARNED_DIR_MIN_LB
  0.52 (Wilson lower bound must clear it, not just 0.5), LEARNED_DIR_SHRINK_K 24→96 so
  thin child buckets lean on rich parents instead of falling off the higher bar
  (zero-evidence-blend lesson). Decayed reader now returns n_raw (undecayed labels) and
  the evidence gate counts THAT — decay shrinks power (priced by Wilson), not evidence.
  Small-n buckets keep learning; they just can't steer. 2 regression tests pin the E3
  failure profile (0.94-acc n=32 bucket → unproven; 0.65 n=600 → full weight).
- **C) reflex gate — nothing to build.** reflex_poscut counterfactuals verified recording
  live; the pre-registered verdict adjudicates at n≥100 (E1 predicts removal).
- **D) range_top_short lens — SHIPPED.** lens_lane lens: SHORT only when
  range_position>0.8 (measured 0.672@1h, n=583 vs 0.542 mechanics), p_up=0.328, abstains
  everywhere else; long mirror NOT traded (unproven, §16). Trades as lens:range_top_short
  on paper; verdict at n≥100 closed like every lens. 1 test.
