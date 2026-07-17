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

### Lessons (also in research/fable5/lessons/)

- Blending a rich parent into a zero-evidence child caps n at k pseudo-obs and silently
  demotes every proven source to "unproven" — zero-evidence levels must hand over verbatim.
- The decider's own recorded claims are the single most informative source row in the
  ledger: they measure the FUSION, not a lens. Watch learned_direction vs
  learned_direction_ctl as the mission's primary scoreboard row.
