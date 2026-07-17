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
