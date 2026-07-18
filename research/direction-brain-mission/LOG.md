# Direction Brain Mission — running log

Prompt: `research/fable5/PROMPT-DIRECTION-BRAIN.md`. Mode: paper. Started 2026-07-17.

## Session 1 (2026-07-17) — Phase 0 + X-A/B/C shipped (commit 9fd0e75)

### Grounded findings (re-measured, artifacts cited)

| Claim | Prompt/docs said | Re-measured (clean window: 15,550 rows, 12.1h, post-1784236980) | Artifact |
|---|---|---|---|
| Overall by horizon | 15m .507 / 1h .524 / 4h .575 (all-era) | **15m .518 / 1h .534 / 4h .594** — asymmetry REAL; method splits agree (probe .537 / mirror .546) | Phase-0 script over direction_truth_train.jsonl |
| The decider itself | not measured | **learned_direction claims score 0.393** (n=382) while its inputs score .575-.658 — the fusion DESTROYED its inputs | same |
| indicator_fusion | 0.5335 all-era | **0.6575 clean (0.6818 at 1h)** — the strongest lens | same |
| funnel_mtf_vote | "47% anti-signal" (memory) | **0.5746 clean** — a real positive source now | same |
| hypothesis | positive-era weights | **0.3961 clean (0.3376 at 1h)** — confidently wrong → weight 0 by decayed reader (retired, NOT inverted) | same |
| Drift | assumed slow | river .680→.525, momentum .672→.576, liquidations .658→.522 between ~6h halves of ONE day | same |
| Exit labels | 0.4236 all-era | 0.5661 clean (n=560) — the B4/E2 exit fixes appear to be working; keep watching | same |

Root cause of the 0.393 decider: reliability weights read ALL-ERA cumulative pools
(pre-clean contamination + fast drift) — the decider trusted what USED to be right.

### Shipped (each pre-tested, 106 tests green)

- **X-A evidence half-life** — day-buckets in the ledger + `source_reliability_decayed()`
  (half-life 2d) + chain recent(regime)→recent(all)→era→conditioner; zero-evidence levels
  hand to parents VERBATIM. Cold-started via `backfill_day_buckets()` (15,424 rows).
  **Measured live effect:** indicator_fusion weight .032→.138; river 0→.063;
  symbol_move_net .035→0 (recently wrong, retired). This directly attacks the 0.393.
- **X-B horizon emission** — decide() emits the horizon where agreeing sources have their
  strongest recent edge; travels via entry_meta → exit_policy assignment.
- **X-C cost gate** — (2p−1)·E|move@horizon| (ATR·√bars, RAM) must clear 2·FEE+SLIP bps;
  refused overrides fall back to the explore prior (labels keep flowing); fail-open with
  recorded reason on a cold mirror.
- **Control lane** — deterministic ~20% (crc32(symbol+UTC-day)%5==0) trades the pre-mission
  decider as `learned_direction_ctl` in BOTH lanes. Permanent benchmark. Never delete.

### Pre-registered verdicts (state the rule BEFORE the data)

1. **X-A/B/C vs control:** after ≥100 closed labels per variant at 15m+1h, `learned_direction`
   must beat `learned_direction_ctl` on sign accuracy (Wilson CIs non-overlapping OR
   ≥+3pp point estimate with n≥200) AND on capture. If it loses → revert to control defaults
   (LEDGER_HALF_LIFE_D=0, COST_GATE=0) and write the negative result.
2. **Cost gate specifically:** measure the counterfactual accuracy of REFUSED overrides
   (they're logged in decide_out.cost_gate). Refused trades must score WORSE than accepted
   ones, else the gate is theater → remove it.
3. **Horizon emission:** post-mortem the closed trades by emitted horizon: 4h-tagged trades
   must show higher direction hold-rate than 15m-tagged at their respective label horizons.

### Open experiment queue (next sessions)

- X-D selection-conditioning (pick preset/lane → ledger conditioner + vote-log field).
- X-E lens redundancy pruning (pairwise φ over vote vectors → drop duplicated opinion mass).
- OPE grid re-run now that reliability is decayed (ope_labeled.jsonl accruing since 09:05).
- Meta-labeler as NO-TRADE second stage (clean AUC 0.528 — weak alone; test as gate).
- Horizon-specialized decide (per-horizon weights end-to-end, not just emission).
- Watch: regime warm-up (mirror-first classify needs ~2.5h post-restart); day-buckets carry
  regime="unknown" for most backfilled rows — regime-conditioned decay gets dense as the
  revived classifier labels new rows.

## Session 2 (2026-07-17, commit ee17455) — measurement round + unblocks

- **X-E lens redundancy → NEGATIVE RESULT.** Over 1,217 simultaneous vote vectors the max
  pairwise correlation is 0.533 (direction_model~hypothesis, both currently weight-0);
  funding~river 0.466 is the strongest weighted pair — moderate, not duplicate (>0.9).
  Nothing to prune. Re-run when funnel_mtf_vote (n=19 in the log) and the new lenses have
  presence.
- **OPE was structurally blocked**: 0 of 1,082 rows labeled — the mirror's tick history is
  ~80min deep, so every older row was unresolvable. ROOT FIX: `price_at()` now falls back
  to the 5m candle close covering the epoch (candles persist for the process lifetime).
  This also unblocks 4h truth-ledger resolution generally after 4h of uptime.
- **OPE grid** now replays the half-life dial (off/0.5/1/5d) — first report with real rows
  expected within hours of the restart.
- **X-D shipped**: sel:<preset> is a ledger conditioner + decide() weight dimension + a
  vote-log field in both lanes. Verdict later, from the sub-buckets.
- **Meta NO-TRADE stage → already built, correctly self-disarmed** (gate() enforces only at
  AUC ≥ 0.55; clean refit is 0.528). No code. It arms itself when a refit clears the bar.
- Killed the stale "anti-signal becomes a real signal" docstring in learned_direction —
  the header now matches the no-inversion law.
- Queue remaining: horizon-specialized decide (per-horizon weights end-to-end); OPE report
  read-out once rows accrue; verdict checks when n≥100-200 per variant.

## Session 3 (2026-07-17, commit 3921c27) — horizon-specialized fusion

- **The big architecture item shipped**: decide() re-fuses the same readings under each
  horizon's own recent reliability; the strongest fused read (weight × conviction) OWNS the
  decision and its horizon tag. Pooled fallback when nothing clears; control stays pooled;
  HORIZON_SPECIALIZED=0 kill-switch.
- **Third-inverter trap excised**: correct_direction() carried a dead invert branch (dead
  since the 07-16 kills, but loaded for a refactor to re-arm). Now pass-through only,
  test-pinned: a reliably-wrong source is NEVER flipped.
- **Scoreboard hygiene**: 233 'learned_direction' ledger rows predate the control split —
  ALL variant verdicts must filter ts ≥ 1784282640 (session-1 restart 10:04). Control claims
  = 0 so far — expected (~20% allocation × abstentions × minutes of uptime); wait for n.
- OPE cursor still pre-restart at last check; the candle-fallback fix needs matured
  post-restart rows + a learn pass. Verify on next session before any grid conclusions.
- Remaining before verdicts: data accrual only. The three pre-registered checks stand.

## Verdict check #1 (2026-07-17 10:27, commit 96bc7c9) — INSUFFICIENT DATA (all three)

- Variant race: 2 pending live claims post-10:04, 0 labeled, 0 control claims. NO VERDICT.
- Cost gate: found a MEASUREMENT GAP — refusals weren't durably recorded, so verdict 2 was
  unmeasurable. Fixed: refused sides now recorded as `learned_direction_costcut`
  (taken=False) in both lanes; the labeler scores the counterfactual automatically.
- Horizon verdict: all 20 open assignments carry horizon=None (pre-session-3 entries). Wait.
- OPE: skips grew 1082→1146 — matured rows still predate the CURRENT process's candle
  history. **Root operational lesson: every mission restart wipes the RAM history that
  labeling, regime and 4h resolution depend on.** Initially handled with a restart freeze;
  then FIXED AT THE ROOT per owner ask (commit 8a1f424): mirror candles persist to
  trading/state/mirror_candles.json.gz every 180s and reload at start() — a restart now
  costs only the outage gap (which stays an honest gap in the bars). First snapshot
  verified live 10:36 (78KB, growing). Restarts are cheap now but not free (ticks/book/
  depth re-earn): still don't restart gratuitously.
- Exit-policy bandit is visibly learning already: 48 outcomes — va_trail 11/16 wins,
  ratchet 8/11, forecast 6/10, scale_out 1/4, ratchet_direction 0/2. Small n; no verdict.
- Next verdict check: ≥24h of uninterrupted uptime, then filter ts ≥ 1784282640.

### Lessons (also in research/fable5/lessons/)

- Blending a rich parent into a zero-evidence child caps n at k pseudo-obs and silently
  demotes every proven source to "unproven" — zero-evidence levels must hand over verbatim.
- The decider's own recorded claims are the single most informative source row in the
  ledger: they measure the FUSION, not a lens. Watch learned_direction vs
  learned_direction_ctl as the mission's primary scoreboard row.

## Session 4 (2026-07-17, commit c455053) — X-F: magnitudes are noise

- **Calibration measurement (16,525 clean labels): claimed confidence is anti-informative.**
  ~0.95 claims realize 0.490; modest 0.65 claims realize 0.560 (the best band); per-source,
  hi-conf beats lo-conf only for indicator_fusion (+.028) and dir_exit (+.012);
  symbol_move_net's confident calls realize 0.398. The cost gate and fusion were consuming
  fantasy magnitudes.
- **Fix**: LEARNED_DIR_MAG_CAP (0.10) clamps every source's magnitude contribution in both
  fusion paths — sign × measured weight carries the decision. Control keeps raw magnitudes;
  OPE replays magcap off/0.05.
- **Behavior audit** (300 live vote rows replayed under today's weights): 95% abstain; all 15
  actual calls came via specialized fusion (9× 4h, 6× 15m). The "fewer, better" shape.
- Verdict check at 10:41: still data-starved (1 labeled variant row; bandit 57 outcomes,
  va_trail 13/19 leading; OPE cursor chewing the pre-persistence skip backlog).
- Candle persistence verified across THIS restart (see funnel log "candle history reloaded").

## Session 5 (2026-07-17, commit 7812372) — owner's deep pipeline scan (JCT/KORU)

Water-flow trace RAM→brain→Freqtrade of two owner-flagged trades found THREE defects:
1. **Stale-arm reflex entries** (JCT, MFE=0): pullbacks armed on a live trend fire minutes
   later with no re-validation — JCT armed on the 11:20-25 pump, fired 11:32 into the fade.
   FIX: fire-time range-position gate (REFLEX_POS_GATE, refusals scored as reflex_poscut).
2. **The timing dimension nobody checked**: entry position in the prior-30m range. Measured
   (35 clean longs): bottom-entries 90% win / 0% never-favorable; top-entries 40% win.
   FIX: "pos" (top/mid/bottom) is now an E8 conditioner on every claim — all sources'
   trust becomes position-aware as labels accrue. Watch cond_buckets |pos:*.
3. **Half the book was invisible**: live_loop's crypto router placed with no enter_tag —
   318/633 clean closed trades landed as "force_entry" (and it's the BEST lane, 60.4% win).
   FIX: decision tag travels with the order. Attribution restored going forward.
Verdict on the owner's question: NOT coincidence — a systematic, fixable timing pattern +
one attribution hole. Pre-registered check: reflex_poscut's labeled accuracy must come in
WORSE than taken reflex entries (else the gate is theater → remove); "pos" conditioner
effect visible in cond_buckets within days.

## Session 6 (2026-07-17) — discussion-session experiments E1-E6 (offline, no code changes)

Owner requested a two-scientists discussion, then "do all experiments". Full write-up:
experiments-20260717/RESULTS.md (scripts alongside, all reproducible). Headlines:
- **E1: session-5's pos finding DOES NOT REPLICATE — it inverts.** All-time longs:
  bottom win 0.405 vs top 0.519; clean-window: bottom 0.512 vs top 0.596 (n=223).
  The n=35 "90%/40%" was noise + claim-vs-trade conflation (null grid: top drifts DOWN
  at fixed horizons, so top-long CLAIMS score badly while top-long TRADES win via exits).
  REFLEX_POS_GATE premise shaky → let its reflex_poscut counterfactual adjudicate.
  Real edge found: SHORT claims at range-top 0.672@1h (n=583) vs 0.542 mechanics.
- **E2: BTC-residual hypothesis falsified** — median BTC R²=0.107; residualizing changes
  nothing pooled. breadth_tilt's errors are common-factor; spillover_seesaw survives.
- **E3: null harness** — 22 proven buckets real vs 6.6 shuffled (signal real, p<0.002)
  but **FDR≈0.30**; fakes live in the 0.9-acc/n≈30 rows. Trust the large-n core only.
- **E4: clean-window split-half source ranking rho=−0.286** — recent-reliability over
  hours ranks NOISE. Only indicator_fusion is stable-top everywhere.
- **E5: bottleneck is loss size, not direction.** Clean: win 0.565 but payoff 0.54
  (breakeven 0.77). stop_loss −5,900/234; tailgate_lock +4.1 avg × 350. We lock pennies,
  donate quarters.
- **E6/E6b: winners bounce (35bps median adverse) / losers run (202bps).** Limit entries
  would be WORSE (adverse selection, −941). Early-abort at 50bps adverse: est clean P&L
  −1,979 → −316 (monotone improvement across 30-200bps grid).
Proposed (awaiting owner): abort-arm in exit bandit, raise bucket promotion bar
(n≥100 + LB>0.52), sweep tailgate lock threshold in OPE, short-at-top paper lens.

## Session 6b (2026-07-17, commit b35e5c9) — owner approved "do A and E first then the rest"

- **A shipped**: `early_abort` exit-bandit arm (XP_ABORT_BPS=50, price-bps, leverage-blind;
  survivors ratchet). Competes via Thompson like every arm — it earns its place or dies.
- **E ran and REFUTED my own E5 proposal**: the tailgate sweep (269 replayed clean trades,
  optimistic + pessimistic variants) ranks TIGHTER arm/giveback better in BOTH variants —
  "loosen the locks" was wrong; the tape fades. Applied crypto-only:
  TAILGATE_ARM_PROFIT_PCT_CRYPTO=1.0 + TAILGATE_DIST_MAX_CRYPTO=0.2 (new market-scoped
  override code; NSE/sandbox untouched). VERIFIED LIVE: fresh locks show dist=0.2 and
  arming at 1.5-2.7% peaks (impossible under the old 3% arm).
- **B shipped**: trust bar n≥100 real labels (n_raw — decay shrinks power, not evidence)
  + Wilson LB>0.52 + shrink_k 96. Small-n buckets learn but can't steer.
- **D shipped**: lens:range_top_short (SHORT only at range_pos>0.8, p_up=0.328; long
  mirror unproven → not traded). Verdict at n≥100 closed like every lens.
- **C**: no code — reflex_poscut counterfactuals already recording; pre-registered verdict
  will adjudicate the gate (E1 predicts removal).
- 102 targeted tests green; loop restarted 16:41:45, dashboard 16:46 — both post-commit.
- Two measurement-integrity fixes en route: tailgate tests now pin their own env (prod
  .env knobs were leaking in via conftest), and source_reliability_decayed reports n_raw.

## Session 7 (2026-07-17, commits fe092dc + 03cc99e) — selection overhaul + re-verification

Owner: build the inception ranker + phase conditioner + all critique improvements, switch
momentum selection off 24h data ("professor's choice": 60m default, FILTER_MOMENTUM_TF_MIN
5-240), then re-verify the whole project again.

SHIPPED (fe092dc): inception.py (attention = P(move starting): fresh-breakout/accel/
squeeze/taker/liq-onset scoring, rank/order/phase/fresh_ok, 45s cache); funnel LOOK order
by inception score; filter lane momentum preset + side on the SHORT-TF move with 24h
fallback; "phase" conditioner (quiet/fresh/mid/stale/extended) on every crypto claim;
lane_gate.py at place_order (kill-parity n≥100 + material loss, freshness gate with
freshcut counterfactuals); tools/refresh_ohlcv.sh + daily 05:10 UTC cron (first run
refreshed 533 futures + 122 spot pairs — measurement gap closed). Plus a REAL pre-existing
bug the new tests caught: filter-lane thread-pool refactor NameError (_ldout) silently
killed every candidate after the first entry each cycle since this morning.

RE-VERIFICATION (03cc99e): 3-angle review (32 candidates) + live observation found:
core-lane kill catastrophe (gate would retire learned_direction/live_loop → exemptions +
25-USDT hysteresis + 6h PAROLE so killed lanes can redeem), uncached inception reads on
the claim hot path (cached_features), tailgate zero-knob falsy bugs, stf partial-window
inflation, loop_keeper kill/restart pgrep race, silent inception fallback, gate telemetry
into /api/trading/upgrades/status (VERIFIED live: 4 real lanes retired — explore_open_all
−1338, force_entry −3056, meanrev_stochrsi −468, filter:momentum −446 → parole added the
same hour). Brain suite 21/21 (computer_use timeout = load, GUI API alive). 103 tests.

🚨 BIGGEST CATCH: "restarting the loop" had only ever restarted run_live_loop — the crypto
FUNNEL (run_funnel_loop crypto, separate setsid group) ran 11:50 code ALL DAY; start_all's
pgrep guard kept it alive through every restart. All five loop processes bounced 18:08
onto 03cc99e; verified BY BEHAVIOR: fresh claims now carry phase {quiet/mid/fresh/
extended/stale} + pos. Lesson recorded in verify-live LEARNINGS.

Watches: first early_abort arm draws + range_top_short nominations + freshcut/parole
counters need hours of accrual; verdict runbook unchanged (V1-V5 pre-registered).

## Session 8 (2026-07-17 ~20:45 UTC) — "close in profit" deep check + Batch-1 experiments

DEEP-CHECK MEASUREMENTS (crypto closes since clean cutoff 07-16 21:23):
- Headline P&L −288,883 was **97% ONE lane**: live_loop wallet-lane `momentum` fallback
  (262 trades, −286,775). Root cause: strategy_config.json min_capital_per_trade=100000
  → line ~1399 bumps EVERY wallet trade to full-balance notional (100k), brain_unlimited
  top-ups made it bottomless, LONG-only SMA fallback revenge-looped dumping coins
  (HOME/USDT ×94, worst single trade −52k).
- Core lanes (excl. that lane): n=995, win 55.7%, **but payoff 0.57** (avg win +9.32 vs
  avg loss −16.49) → net −2,108. Exit-reason economics: stop_loss n=243 avg −25.58 (the
  loss bucket) vs tailgate_lock avg +2.70, roi avg +25.85 (100% green).
- MAE separation (n=899): winners median MAE 0.42% of notional, p90 1.47%, only 0.4%
  exceed 2.5%; losers ride to the −10% hard stop. → a tight backstop barely touches winners.
- V2 verdict data: learned_direction_costcut n=719 acc 0.426 [0.390,0.462] ≪ live 0.513
  → the cost gate's refusals are genuinely bad trades; GATE VALIDATED (opposite of theater).
- V1 still underpowered (ctl n=47 < 100). No direction-knob action; race continues.

BATCH-1 CHANGES (all live 20:27–20:45 UTC, each with revert token):
- X1 min_capital_per_trade 100000 → 0 (PositionSizer 4%/1% rules again). REVERT: restore
  100000 in trading/state/strategy_config.json + loop restart.
- X2 live_loop loss-cooldown: same-symbol+same-direction re-entry blocked
  LOOP_LOSS_COOLDOWN_MIN (45m) after a losing close; direction flip allowed. REVERT:
  LOOP_LOSS_COOLDOWN_MIN=0.
- X3 ML_STOPLOSS=-0.03 (.env; config_template now emits env-driven "stoploss", default
  −0.10). Freqtrade restarted on regenerated config. Expect one-time flush of old
  open trades below −3%. REVERT: delete ML_STOPLOSS / set −0.10 + restart freqtrade.
- Hygiene: purged 4 orphaned CRYPTO:* tailgate locks (stale dist=0.33 rows from dead
  wallet trades — live code writes dist=0.2 correctly; live_loop _open is RAM-only and
  orphans locks on every restart — cleanup candidate).
- Universe check: mirror candle store carries 877 symbols (1m/5m/15m, fresh) — filter
  lane ranks the whole market; ranked≈106 = rows with non-zero signal. Owner's
  "consider all symbols" requirement is MET by mechanism + data.

MEASUREMENT: live_watch.py (per-trade grades vs epoch 20:27) + persistent monitor feed
emitting every open/close + sizing anomalies. Pre-registered keep/revert:
- X1/X2 keep if wallet-lane notionals ≤5k and no revenge chains; revert on starvation
  (wallet lane opens ~0 trades for 12h+).
- X3 keep if stop_loss bucket avg loss shrinks toward ≈−7 (−3.5% of 200 stake) without
  win-rate collapse (>5pp drop on n≥100 post-change closes → revert).

Session 8 correction (stake-basis re-derivation): freqtrade stoploss is LEVERAGE-SCALED;
at 5x, −3% of stake = 0.6% price. Re-measured in stake terms: winners MAE median 1.62%/
p90 6.49% of stake; losers median 9.95%. Counterfactual totals (core lanes n=995):
stop 3% → −30 | 4% → −161 | 5% → −423 | 8% → −537 | 10% (old) → −752 | actual −2108.
DECISION: keep ML_STOPLOSS=−0.03 (best total; matches E6b 50bps price abort). Known cost:
~30% of winners stopped early → short-term WIN-RATE dips while P&L improves. Green-ratio
recovery path: any trade reaching +1% stake now closes green (arm 1.0/dist 0.2/locked>0),
so green% ≈ P(+0.2% price move before −0.6% against) — entry timing = inception's job.

## Session 8, Batch 2 (2026-07-17 ~20:50 UTC) — stop-churn + direction-at-entry

LIVE CATCH (first 19 post-Batch-1 freqtrade closes): every tailgate close GREEN
(+0.44…+2.24%) + roi +10.69 ✓, BUT the live_loop ROUTER lane (live_loop._route_crypto_engine
forwarding the SMA momentum fallback into freqtrade) CHURNED: ESPORTS stop→re-enter→re-stop
in 4 min, DODOX stopped 14s after entry, BANK ×3. Stops gapped to −3.5…−5.9% (entries into
mid-dump). X2's cooldown only covered the wallet-lane path (_open_trade), not this router.

- X4 stop-churn cooldown at the ONE chokepoint (lane_gate.check, engine_client.place_order):
  refuse same pair+direction re-entry for STOP_REENTRY_COOLDOWN_MIN (30m) after a stop_loss
  close (DB-read, fail-open, refusal recorded + 'stopcool' counterfactual claim so the
  truth labeler adjudicates whether blocking was right). Direction flips allowed.
  4 new tests (21 green). REVERT: STOP_REENTRY_COOLDOWN_MIN=0.
- X5 direction-at-entry: added live_loop to MOMENTUM_FRESH_TAGS so the router's momentum
  fallback passes the EXISTING inception freshness gate (fresh_ok + freshcut
  counterfactuals) like every other momentum-family lane. Zero new code.
  REVERT: remove live_loop from MOMENTUM_FRESH_TAGS.
- Decision-snapshot evidence for the entry-quality problem: explore/fallback entries were
  LONGing +16%-pumped movers; ESPORTS opened LONG while its own learned read said p_up
  0.338. The freshness gate is the measured counter to exactly this cohort.
- run_live_loop + crypto funnel restarted ~20:50 with X4+X5; keep/revert on stopcool +
  freshcut counterfactual verdicts + per-lane closes.
- Background research agent launched: published evidence on stop distance vs MAE,
  re-entry cooldowns, high-win-rate exit engineering → research-exits-reentry.md.

Batch-2 baseline (freqtrade DB, closes 20:27→20:55): live_loop n=23 green 0.35 stop% 0.65
net −93.71 (the churn window, pre-gate); filter:squeeze n=3 net −7; ctl n=2 net +25.
Research (research-exits-reentry.md): −3% stake stop at 5x = 0.6% price ≈ inside 1σ 4h
noise (stop-outs partly forced by geometry — X3 revert rule covers it; vol-scaled stop =
Batch-3 lead); hollow-win 6:1 asymmetry (arm +1% nets ~+0.5% after fees vs −3% stops →
≥86% green needed to break even at current geometry); cooldown validated (Coval & Shumway),
upgrade candidate = price-reclaim re-entry condition. live_watch now prints a per-lane
epoch scoreboard (green/stop/hollow/net) straight from the DB.

## Session 8 (2026-07-17) — R1 time-series momentum (the direction-ceiling reframe)

Owner: "loop until trades open in correct direction + close in profit; research online, invent."
Online research (research/ai-scientist/direction-ceiling-research-20260717.md) reframed the ceiling:
at a 15m–4h hold, microstructure/OFI/book is NOISE (power lives at 0.5–5s) — our ~0.523 is EXACTLY
what microstructure direction should score at multi-hour holds. The only replicated multi-hour edge
is TIME-SERIES MOMENTUM (trend factor Sharpe ~1.2) + carry; it's what real desks run.

SHIPPED: `mom_ts` truth-ledger source in brain_sources (vol-scaled trend t-stat → p_up; abstains
below 1.5σ so a random walk isn't called a trend — validated 84% noise-abstention; §16 earn-weight).
BRAIN_SRC_MOM_TS=1, MOM_TS_LOOKBACK_BARS=48 (4h of 5m), MOM_TS_MIN_T=1.5. Never inverts.

PRE-REGISTERED VERDICT (revert rule): at n≥200 taken trades with a mom_ts reading, sign accuracy
must be ≥0.55 (binomial p<0.05) AND realized edge positive vs the −0.213% baseline; if <0.52 →
mom_ts is retired (weight already 0 via §16, but drop the source). Gated subset (mom_ts agrees with
fused side) ≥0.57 → promote to a heavier prior. Check via truth_ledger `mom_ts` bucket + verdict_check.

## Session 8, Batch 3 (2026-07-17 ~21:01 UTC) — the gate was blind in the router process

- X4 CONFIRMED LIVE: stop_cooldown refusals = 4 within 10 min of restart (churn stopped).
- X5b: fresh_ok was PERMANENT fail-open inside run_live_loop — the RAM mirror only
  streams in the funnel process; the router's gate saw "no-data" forever. inception now
  falls back to the funnel's persisted mirror_candles.json.gz (mtime-cached, 15-min
  staleness guard, honest [] on stale) — the write_snapshot cross-process convention.
- COHORT MEASUREMENT (n=397 closes since 12:00, r240/r60 reconstructed at entry):
  mild-early (|4h aligned|<3%)  win 0.635  net  −93   ← best
  counter-accel                 win 0.553  net   +8   (n=38, underpowered)
  chase-fresh                   win 0.495  net −146
  counter-basing                win 0.489  net  −55   (n=45, no action — underpowered)
  chase-stalled                 win 0.444  net −199   ← toxic; gate's target cohort ✓
  REFUTED my own knife-catch hypothesis (counter-trend is NOT the worst cohort — chasing
  is). Rule honored: measure before gating.
- X6: INCEPTION_FRESH_R240 5.0 → 3.0 (.env) — the 3-5% chase-stalled band is toxic too.
  One-predicate design means score/phase/gate all shift together. REVERT: delete env.
- run_live_loop + crypto funnel restarted 21:01 with X5b+X6.

## Session 8, X7 (2026-07-17 ~21:15 UTC) — the router finally gets a brain

Owner: "check the new trades opening in correct direction". Graded every trade opened
since 21:01: router lane ALL LONG, matured grades 0/2 (AKE LONG after +34.8%/4h chase,
US LONG both stopped). ROOT CAUSE: BRAIN_LOOP env was never set → _brain_decider()
returns None BY DESIGN → the live_loop router has ALWAYS been the LONG-only SMA fallback;
it structurally cannot emit SHORT. X7: BRAIN_LOOP=1 (.env), BrainDecider smoke-tested,
run_live_loop restarted 21:14. Expect: router tags shift from 'live_loop' to brain source
names, SHORTs possible, direction from the T8 pipeline instead of price>SMA(12 ticks).
REVERT: remove BRAIN_LOOP from .env + restart (also revert if CPU load climbs toward
wedge territory — VM history). Verdict: matured direction grade + lane net of post-21:14
router entries vs the 0/2 LONG-chase baseline.

## Session 8, X8 (2026-07-17 ~21:55 UTC) — vol-scaled stop, in-engine A/B

X7 scorecard at ~40min: matured 3/11 (0.27), closed-net −62; 6 of 8 matured deaths were
stop_loss at 0.7–1.4% PRICE adverse — inside one 5m candle of noise on high-vol perps.
The research brief's structural warning materialized: a fixed 0.6%-price stop across a
universe whose ATR% spans 10x forces noise stop-outs regardless of entry quality.
Positive signals: LAB SHORT green (brain flipped the symbol it used to knife-LONG);
router direction mix now ~balanced; wallet lane still ~zero-cost.

X8: MlBridgeStrategy.custom_stoploss with per-trade A/B by trade-id parity —
  EVEN ids: fixed ml_stop_fixed (=ML_STOPLOSS −3% stake) — the X3 control.
  ODD ids: K×ATR14(5m)×lev of stake, clamp [ML_STOP_MIN 2%, ML_STOP_MAX 8%], K=1.5.
  Static config stoploss now carries the −8% backstop (freqtrade: static stop is the
  WIDEST bound; custom_stoploss can only tighten, so BOTH arms enforced there).
  Arm recoverable from trade_id%2 — zero extra state. Fail path = fixed arm / backstop.
  REVERT: ML_STOP_AB=0 (all trades → fixed −3%) + freqtrade restart.
Verdict rule (pre-registered): compare arms on trades opened post-21:55 at n≥50/arm —
green ratio AND net per trade; vol arm must beat fixed on net without halving green ratio.

## Session 8, X9 (2026-07-17 ~22:35 UTC) — minimum lock floor: tailgates must clear fees

X7 verdict forming: matured router (live_loop) direction grade 10/13 = 0.77 (was 0/3
fallback); overall X7-era 15/29 = 0.52, sides balanced. X8 first 6 closes: ZERO stop_loss
exits (was 57% of closes). NEW leak isolated: the ATR-scaled tailgate ARM lets low-vol
symbols arm near 0.3% of stake → locks fire BELOW round-trip fee drag → "correct
direction, red close" (1000BONK move +0.10% → −0.02; DODOX +0.00% → −0.96).

X9 (task 6): TAILGATE_MIN_LOCK_PCT=0.7 (% of stake, covers ~0.5% fees + slip):
- ratchet side (profit_tailgate.locked_profit): sub-floor locks are RECORDED (ratchet
  keeps climbing) but never fire the exit;
- engine side (MlBridgeStrategy.custom_exit): sub-floor locks not enforced
  (ml_tailgate_min_lock config key, env-driven via template).
Hard-stop arms still protect sub-floor trades. 2 new tests (12 green; module-frozen
_MIN_ARM_PROFIT patched via mock, not env). REVERT: TAILGATE_MIN_LOCK_PCT=0 + restarts.
Verdict rule: post-22:35 tailgate_lock closes must be ≥90% green with avg ≥ +1.0 per
close (fee-clearing), without total tailgate-exit count collapsing (<25% of prior rate).

## Session 9 (2026-07-18 ~07:00 UTC) — "one day completed" verdict check (runbook run)

Scoreboard: verdict_check.py + live_watch.py + windowed DB queries (cut = 2026-07-17
22:35, the X8+X9 restart; actual proc start 22:15).

**V1 live-vs-ctl — WIN (provisional):** learned_direction ALL n=407 acc .572
[.524,.620] vs ctl n=199 acc .503 [.434,.571]. Gap +6.9pp ≥ +3pp with ctl 1 row shy of
the n≥200 bar (CIs overlap, so the +3pp branch decides). Realized lanes agree: brain
lane −0.38/trade vs ctl −1.96/trade since epoch. KEEP mission knobs; race continues;
re-affirm when ctl crosses 200.

**V2 cost gate — VALIDATED:** costcut n=2600 acc .511 [.492,.530] vs accepted .572
[.524,.620] — CIs NON-overlapping; refused trades genuinely score worse. COST_GATE stays.

**V3 horizon — INSUFFICIENT at trade level** (open assignments all horizon=None — the
horizon isn't reaching exit_policy assignment; wiring gap to fix). Claims-level is
directionally consistent: 15m .529 / 1h .605 / 4h .600.

**V4 OPE — PROPOSAL (not auto-applied):** shrink_8 beats live_cfg on BOTH hit (.5588 vs
.5563) and capture (168.6 vs 145.9); shrink_0 has top capture (217) but worse hit
(.5334). Proposal for owner: SHRINK_K 96 → 8.

**V5 exit bandit standings** (all arms n≥30 except ratchet_direction n=10): va_trail
72/136 .53, scale_out 65/123 .53, ratchet .48, early_abort .49, direction .49,
forecast .47. No verdict yet — leaders are the two trail-style arms.

**X8 — VOL STOP PROMOTED (pre-registered rule met):** trades opened post-cut, n=194
fixed / n=192 vol: net −338.77 vs −126.91, green .29 vs .40, stop-rate .60 vs .33.
Vol wins net WITHOUT halving green (it raises it). Shipped: ml_stop_mode config knob
(ab|vol|fixed), ML_STOP_MODE=vol in .env → ATR stop for ALL trades. Re-check path:
ML_STOP_MODE=ab restores the parity A/B.

**X9 — REVERTED (pre-registered rule failed):** post-cut tailgate closes n=20: green
80% (<90% target), avg +2.59 (pass), rate 2.4/h = 6.7% of prior 35.6/h (<25% floor —
fail). Deeper truth: the pre-X9 tailgate population was NOT sub-fee junk — 285 closes,
74% green, avg +1.53, net +435/8h (the system's profit engine; only 28/285 hollow).
The floor suppressed 93% of those exits; stop-outs doubled (95 → 184) as trades that
would have banked +0.3–0.7% rode to their stops. The BONK/DODOX anecdotes were the
tail, not the body. TAILGATE_MIN_LOCK_PCT=0 (env), code stays as dormant knob.
Honest note: system net/h still improved −95.6 → −56.1 across the window, but the
decomposition credits X8 (stop severity), not X9.

**X7 — KEEP** (BRAIN_LOOP=1): matured-open direction grades stay above the 0/3
fallback baseline (latest feed 3/4; era ~.56); SHORTs flowing (23/118 post-cut).
Watch item: live_loop lane realized net −194 post-cut is the worst lane — next
experiment target after X9 revert takes effect (many of its reds were stop-outs
under the fixed arm, now removed).

Actions: config_template ml_stop_mode + MlBridgeStrategy mode branch + .env
(ML_STOP_MODE=vol, TAILGATE_MIN_LOCK_PCT=0); 33 tests green (tailgate+lane_gate);
freqtrade + crypto funnel + live_loop bounced ~07:03 on regenerated config.

### Session 9 follow-on (07:14) — V3 wiring fix
Root cause of "[V3] OPEN assignments by horizon: {None: 14}": brain_executor's lazy
exit-arm assignment read meta.brain.learned_direction.horizon but entry_meta nests the
brain block under meta.decision_snapshot — None for EVERY trade. Fixed (legacy fallback
kept); fixed reader finds horizon on 53/60 newest real records (rest = non-brain lanes,
honest Nones). Crypto funnel bounced 07:14. Commit 88dcaf1. V3 becomes judgeable as
closes accrue (needs ≥30/group). Ops trap hit TWICE today: background wait-loops whose
command lines contain 'freqtrade trade'/'run_funnel_loop crypto' self-match start_all's
pgrep guards → services silently not launched. Keep guarded strings OUT of watcher
command lines.

### Session 9, X10 (2026-07-18 07:43) — throughput for data accrual (owner: "make more
### trades open for more data for experiment")
Levers chosen to raise opens/h WITHOUT loosening any validated quality gate (X2/X4/X5/X6
cooldowns + freshness stay): BINANCE_FILTER_TOPN 100→150 (owner blessed 150 on 07-16) and
LENS_LANE_MAX_PER_LENS 1→2. LOOK_TOPK deliberately NOT raised (it lengthens the CPU-bound
LOOK stage → slower cycles could LOWER opens/h + wedge risk). Baseline: 40.3 opens/h
(121/3h). Verdict rule (pre-registered): opens/h ≥ +25% (≥50/h) within 3h of 07:43;
GUARD: post-07:43 cohort green% at n≥100 must not fall >5pp vs the .35 baseline.
REVERT: TOPN=100 + delete LENS_LANE_MAX_PER_LENS + funnel restart. Funnel bounced 07:43.

### Session 9 follow-on 2 (08:16) — V3 real root cause + loud assignment telemetry
88dcaf1 was the WRONG level: entry_meta.lookup() returns best.get("meta") already;
brain_executor's extra .get("meta") reduced every record to {} → horizon None forever
(LAB 9414: record hz=15m, reader None). Fixed (efe86bf), verified against the real
lookup, open assignments backfilled (horizon only; arms untouched — re-assigning would
re-randomize the bandit mid-trade). Assignment except now LOUD. Debug detour lesson: the
"assignments stopped" scare was budget-squeezed execute stages (budget ok=False cycles),
not a wedge — grade_fills mtime + numeric-lock ownership (live_loop writes those too)
misled; the instrumented log settled it in one cycle. Funnel bounced 08:16.

### Session 9, X11 (2026-07-18 08:21) — dead-market entry floor (owner "do X11")
Trigger: owner asked why symbols show no movement; measured Sat 08:00 UTC — universe
median 4h range 1.18%, p10 = 0.00%; open trades sat in closed-hours stock-perps (XAU
0.13%, MU 0.43%, DELL 0.56%). Shipped: lane_gate._range_pct_4h (persisted mirror, works
in every process) + floor in check() — refuse ANY entry whose 4h range < X11_MIN_RANGE_PCT
(0.8, env), both directions, counterfactual source "deadcut", fail-OPEN on no data,
refusal kind "dead_market", dashboard status carries dead_floor_pct. 4 new tests (25
green). Verified live pre-ship: MU refused, LAB (11.9%) passes.
KNOWN TENSION (pre-registered): compressed MAJORS also get refused (BTC 0.17% Sat am) —
i.e. filter:squeeze entries. Verdict rule: deadcut claims must score WORSE than accepted
contemporaneous entries at n≥100; if squeeze-tagged deadcuts score WELL, refine to a
squeeze exemption instead of full revert. REVERT: X11_MIN_RANGE_PCT=0 + bounce
funnel+live_loop. Both bounced 08:21.

### Session 9, X12 (2026-07-18 11:44) — cost-gate lambda (research-driven; owner: research
### then experiment on picking/direction/filters)
Research: research/direction-brain-mission/research-entries.md (workflow wf_5d8279d1-443,
partial — verification hit a session limit; resumed as w0hyaoje6). VERIFIED findings that
matter: (1) intraday BTC trend-following had NO edge 2011-2019 even pre-fees, exhaustive
1-1000h MA scan (arXiv 2009.12155); (2) walk-forward optimal trend lookbacks were 6-40
DAYS, far above our 15m-4h; (3) BTC intraday predictability is real but contains BOTH
momentum AND reversal; (4) it is REGIME-DEPENDENT (jumps/liquidity/events). Together these
explain the measured bleed: our momentum-family lanes (live_loop −76/3h, learned_direction
−72/3h) hunt a documented non-edge at our horizon, while the only green lane
(filter:squeeze) is volatility-compression, not trend-chasing.

X12 (first experiment from it): cost_gate required EV > 1x round-trip cost — an edge inside
its own error bar. Now EV must clear COST_GATE_LAMBDA x cost (2.0; 1.0 = old). Measured
motivation: fees = 31% of losses (255 closes/6h paid 137 in fees, 0.54/trade). Research
lead (UNVERIFIED, arXiv 2606.00060v1): lambda=2.0 on hourly BTC futures cut trades
10,619→251 and flipped −64%→+65% annualized — a lead, hence an EXPERIMENT not a belief.
Verified live pre-ship (ATR 0.4%, cost 12bps): p_up .55 passes at lambda 1.0, REFUSED at
2.0; p_up .60/.70 still pass. 20 tests green. Baseline (2h pre-X12): 54.0 opens/h, 122
closes, green .52, net −386.9 (−3.17/close).
Verdict rule (pre-registered, n>=100 closes post-11:44): net per close must IMPROVE vs
−3.17 AND costcut-refused claims must keep scoring worse than accepted (V2 rule). Expect
opens/h to FALL — that is the mechanism, not a failure; but if opens/h < 15 (data starved)
or net/close worsens, REVERT: COST_GATE_LAMBDA=1.0 + bounce funnel+live_loop.
NOTE vs X10: X10 raised throughput for data, X12 cuts weak trades — deliberate opposition;
X12 owns the entry-quality axis, X10 the candidate-width axis.

### Session 9, X14 (2026-07-18 12:02) — the long-only fallback stands down
### (owner: "all loss trades' reason is placing the WRONG DIRECTION")
Owner's claim MEASURED properly this time (my first pass answered the wrong question —
aggregate win rate instead of WHY the losers lost). Of 691 losing closes in 24h:
  A) WRONG FROM THE START (never gained +0.5% of stake): 318 = 46%, cost −4,046.5
  B) direction right FIRST, then reversed: 373 = 54%, cost −3,341.3
     (median peak +1.53% of stake before turning red; 136 were up ≥2% and STILL closed red)
So the owner is RIGHT that wrong-direction is the single biggest loss cause — 46%.

ATTRIBUTION of the 318: live_loop 155 (49% of them, −2,318 = 57% of the wrong-direction
money). Next worst learned_direction 52 (−550). The router's wrong trades split
141 LONG / 14 SHORT — a 10:1 long skew. Cause: router opened 91% LONG (606) vs 9% SHORT
(63) in 24h while the brain funnel BESIDE it ran 68% SHORT on the same market and squeeze
ran 50/50. Router LONGs lose −2.12/trade; router SHORTs −0.49/trade.
ROOT CAUSE: momentum_decider (the _decide fallback whenever the brain path is absent or
throws) returns only LONG/EXIT/FLAT — it is STRUCTURALLY incapable of SHORT, so every
fallback tick fabricates a LONG regardless of the market.

X14: per CONVENTIONS §16 (direction must be EARNED — never fabricate, never invert), the
fallback no longer OPENS. It still returns EXIT/FLAT so open positions stay managed while
the brain is down. Suppressed entries record a momentum_longonly_cut counterfactual, so
the ledger adjudicates whether standing down beat entering. ROUTER_MOMENTUM_ENTRIES=1
restores the old behavior. Also fixed: `os` was never imported at module level in
live_loop.py — X13's ROUTER_COST_GATE lookup would have raised into its own except and
silently failed open. Verified functionally: same rising-price stream returns LONG with
=1 and FLAT with =0, and the EXIT path still exits. 63 tests green.
BASELINE (live_loop, 6h pre-X14): n=113, 21% short, green .469, net −330.6 (−2.93/trade).
Verdict rule (pre-registered, n>=100 router closes post-12:02): net/trade must beat −2.93
AND the router's wrong-from-start share must fall below 23%. If router volume collapses to
near zero AND the brain path is the reason (not the market), that is a FINDING not a
failure — it means the router was living on fabricated longs. REVERT: ROUTER_MOMENTUM_ENTRIES=1.
