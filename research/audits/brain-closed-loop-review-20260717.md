# Whole-Brain Closed-Loop Review — 2026-07-17 (PhD-professor pass)

Method: static import audit (research/audits/independent-audit-20260717-074900.md) + 3 read-only
runtime-CONSUMPTION traces (research→trade, memory, learning) each verified against live state
(ledger n, file mtimes, live pids) + direct journal forensics. Yardstick = the "Threepio" video's
genuinely-closed loop (research→cite→strategy→validate→graveyard→portfolio→fails-closed gate).

## The one-sentence verdict
**The brain is not a dumb hotdog/not-hotdog classifier — its LEARNING spine genuinely closes
(truth-ledger, exit-bandit, strategy-evolution all learn from real outcomes and steer trades).
The failure is the opposite: a good learner wired to a STARVED actuator, with three severed links
that stop its intelligence from reaching trades and one poisoned dataset it grades itself on.**

## What is REAL-CLOSED (do not "fix" — verified live)
- truth-ledger reliability: outcome→backfill→decayed day-buckets (2d half-life, clean-window
  cutoff)→_signed_weight→decide(). direction_truth.json fresh (18:40). THE learning spine.
- exit-policy Thompson bandit: arms actually ACT (not shadow), learn Beta posteriors, steer next
  draw. bandit.json 18:42.
- strategy evolution/foundry: STRATEGY_EVOLUTION_ENABLED=1; breed()→SkillLibrary→strategy_table→
  enter_tag→`strategy_tournament` reading in decide(). Tournament cap fixed. Closed.
- river online-learning: learn() IS called at close (B2 fix confirmed), persists, decide() reads it.
  Honestly earns 0 weight (measures 0.485) — retired, never inverted. Real, not theater.
- FinMem decision_memory bias(): closed — scales brain confidence ±20% at n≥3.
- hypothesis lens: closed (but journal-fed, NOT web).

## THE SEVERED LINKS (ranked — this is the correction list)

### S1 — OPE is a disconnected recommender (HIGHEST leverage)
ope.evaluate() writes ope_report.json ranking decider-knob configs against live counterfactually;
current report shows the LIVE config is the WORST candidate (live −7.88 vs min_n_15 +0.32 @1h).
**Only ope.py reads the report** (grep-confirmed) → the self-improvement is computed and discarded.
This is the exact "identifies the better answer but cannot act on it" symptom.
FIX: `ope.py` self_tune() persists the winning LEARNED_DIR_* knob-set when it beats live_cfg at
sufficient n + margin; `learned_direction._cfg()` overlays that file over env. Evidence-gated,
logged, reversible, kill-switch. (This is the mission's own E1 proposal, never finished.)

### S2 — The reliability gate STARVES decisions (systemic, by-design side effect)
min_lb=0.52 is so strict that only ONE source (spillover_seesaw, LB 0.522, n=660) currently earns
any weight; river/indicator_fusion/symbol_move_net/direction_model learn correctly but are gated to
0.0 → the decider trades on ~one weak source + explore prior → direction ≈ coin-flip (F2).
FIX (proposal, needs pre-registered verdict per mission culture): softer floor via the existing
empirical-Bayes shrinkage — let a proven across-regime source contribute a shrunk weight instead of
a hard 0 below LB; OR lower min_lb with the cost-gate + magnitude-cap already damping bad calls.
DO NOT just yank the knob — register the verdict first (this is the money-sensitive one).

### S3 — Web/online research is 100% open-loop (theater)
researcher.py→research_findings.json (0 readers); news_ingest→news_memory.json (unread by decide);
the `news` lens is built with NO fetcher → always n_articles=0 → DEAD; foundry keeps result TITLES,
discards content. The video's headline "goes online, reads papers, turns them into edge" — ours
cannot change an opened trade at all.
FIX (`brain_sources.py`): (1) give _news_node a fetcher reading the already-written news_memory.json
→ lights the `news` source; (2) add `_research_p(symbol)` reading research_findings.json per-symbol
sentiment → p_up as new truth-ledger source `web_research`. §16-safe: earns weight only once proven.

### S4 — Memory is write-only; the `lessons` lens is DEAD (dead-wire bug)
lesson_prior.distill() writes table[sym] with the slashed key ("AKE/USDT:USDT"); readings() looks up
the flat form ("AKEUSDT") → always None. Proof: 0 `lessons` buckets in aggregate/7064 pending/40k
train; readings() returns [] for all 22 live leans. "Brain writes lessons nobody reads" — literally.
FIX: `lesson_prior.py:125` normalize key to flat-upper on write + one-time migrate existing keys.
Also: knowledge-testing (self_eval/quiz/FSRS/parity) is dashboard-only + behavior-inert — the brain
never TESTS its knowledge in a way that changes a trade (open loop, lower priority).

## CROSS-CUTTING DATA / RESULT DEFECTS

### F1 — Evaluation dataset poisoned (data-integrity, found-not-fixed)
journal.json: 380 corrupt rows (symbol="USDT", exchange mislabeled NSE, entry 0.70→exit 0.0076 =
100x scale fake −99%, capital_at_risk up to 28.9M on a 100k acct, fake ΣP&L +3.86 BILLION).
Concentrated 07-13 (NSE replay burst), none after 07-15 (writer stopped) but NEVER purged. Memory
named these 07-16 and left them in. Every journal-wide win-rate/source-accuracy read is contaminated.
FIX: one-shot quarantine → journal_quarantine.json + write-time guard in trading/journal/journal.py
rejecting symbol∈{USDT,USD,""}/cap>account/entry-exit ratio>10.

### F2 — Win-rate ≠ profit (payoff asymmetry, already under attack)
Clean recent: ~53% win but NET NEGATIVE. Money lost on loser SIZE + exits, not entry sign.
Mission already attacking (exit bandit + early_abort + tailgate tightening). Confirmed bandit really
steers. Watch, don't re-litigate.

### F3 — No cause-of-death graveyard (feature gap vs reference)
We retire lanes/strategies (lane_gate, tournament) but log ZERO why/which-stage. The video's
standout feature. Additive fix: death ledger {strategy, died_at_stage, metric, bred_ts, killed_ts}
written by lane_gate + tournament + foundry DSR gate; surfaced as a panel. Turns silent kills into
learnable data.

## Suggested correction order (impact × confidence ÷ risk)
1. F1 poison quarantine + guard  (pure hygiene, no downside) — DO NOW
2. S4 lesson-lens key fix         (dead-wire bug, §16-safe)   — DO NOW
3. S3 web-research reader         (lights dead pipes, §16-safe)
4. S1 OPE self-tune              (highest leverage; evidence-gated, reversible)
5. F3 graveyard ledger           (additive; new learnable data)
6. S2 gate-starvation            (money-sensitive → pre-register a verdict first, do last)

## OUTCOMES — session 2026-07-17 (commit pending)
- **F1 SHIPPED**: 374 poison rows quarantined → journal_quarantine.json (backup .bak kept);
  `is_poison_row` guard in journal.record() rejects degenerate-symbol / impossible-cap rows at
  the door. Journal now 0 poison. Tests: TestPoisonGuard (incl. legit option near-zero survives).
- **S4 SHIPPED**: `_flat()` normalizer keys the lesson table on write == read; on-disk table
  migrated (51 slashed → 49 flat). VERIFIED LIVE: readings('AKEUSDT')→[('lessons',0.68)]; 21
  leans now emit into decide() under the §16 earn-weight gate. Was permanently dead.
- **S3 SHIPPED (news half)**: `_news_p` now reads the already-scored news_memory.json (zero
  network, symbol-scoped, recency-gated, floored). VERIFIED: BASEDUSDT 0.644 / XRPUSDT 0.359.
  DELIBERATELY NOT DONE: a `web_research` direction vote from research_findings.json — those are
  MARKET-WIDE link/title briefs, not per-symbol directional; fabricating a side would violate
  "DIRECTION MUST BE EARNED". Briefs belong as context/knowledge (follow-up), not a vote.
- **S1 SHIPPED**: ope._self_tune() persists the LEARNED_DIR_* config that beats live_cfg on
  per-trade capture at acted≥30 + margin≥0.10 + net-positive; learned_direction._overlay() adopts
  it; auto-reverts when live catches up; inert during OPE replay (OPE_REPLAY guard); kill-switch
  OPE_SELF_TUNE=0. 6-way state machine tested. Honestly DARK today (acted counts ~5-6 < 30) —
  activates only when counterfactual evidence clears the bar. The metacognitive loop is closed.
- **F3 SHIPPED (core)**: trading/brain/graveyard.py cause-of-death ledger, idempotent per entity;
  wired into lane_gate.check() (the live kill site). Follow-up: same one-liner at the tournament
  cull + foundry DSR gate, and a dashboard panel (data + read API already exist).
- **S2 — NO CODE CHANGE (reversed on reflection).** Loosening min_lb/min_n to un-starve decisions
  would re-admit exactly the noise the mission's own null-harness (E3) measured at FDR≈0.30. The
  starvation is real but the correct cure is MORE SOURCES legitimately clearing the bar — which
  S3/S4/S1 directly advance — NOT lowering the evidence bar. Recommendation stands as analysis.

## Pre-registered verdicts for the shipped changes (check at ≥24h uptime)
- S1: once any candidate reaches acted≥30 at 1h, self_tune must APPLY the higher-capture config
  AND that config's live claims must then beat the prior live_cfg's on realized capture, else the
  margin/min_acted bar is too low → raise it. ope_report.json.self_tune records every decision.
- S4/S3: `lessons` and `news_sentiment` must accrue truth-ledger buckets; neither may earn weight
  until n≥100 + Wilson LB>0.52 (the existing §16 gate). If either measures <0.5 at n≥100 → it is
  retired (never inverted), same law as every source.
- F1: no new poison row may appear in journal.json (guard); quarantine count stays 374.

## Loose ends flagged (not owned by this batch)
- test_brain_connect_upgrades::TestReliabilityShrinkage::test_thin_regime_bucket_borrows_from_parent
  FAILS ON HEAD (pre-existing, not from this batch) — the empirical-Bayes shrinkage the
  connect-the-brain session shipped may have a real regression. Worth the mission's attention.
- test_app_signals passes alone but fails inside a big -k batch → a non-hermetic test reads real
  state another test mutates. Test-isolation hygiene debt.
- research_findings.json briefs + foundry result-titles: still orphaned as knowledge (S3 note).
