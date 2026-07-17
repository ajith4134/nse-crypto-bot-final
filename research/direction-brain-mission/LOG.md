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

### Lessons (also in research/fable5/lessons/)

- Blending a rich parent into a zero-evidence child caps n at k pseudo-obs and silently
  demotes every proven source to "unproven" — zero-evidence levels must hand over verbatim.
- The decider's own recorded claims are the single most informative source row in the
  ledger: they measure the FUSION, not a lens. Watch learned_direction vs
  learned_direction_ctl as the mission's primary scoreboard row.
