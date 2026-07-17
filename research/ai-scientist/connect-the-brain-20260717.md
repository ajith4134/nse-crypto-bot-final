# Connect the Brain — 2026-07-17 whole-system audit + P0 repairs + extension proposals

Owner ask: "look at ALL the brain's features, connect them, find advanced extensions + learning
upgrades." Grounding: `research/audits/independent-audit-20260717-074900.md` (874 modules, 3045
edges) + a hand runtime-consumption trace of the money path (brain_executor →
learned_direction.decide). Method note: the static graph's 128 "orphans" are mostly dynamic-loader
false positives (lib_* strategies load by config, nodes autoload, cortex/native bind at runtime);
everything below was verified by reading the actual call sites or measuring live state.

## A. What was BROKEN-connected (found + FIXED this session, commit pending)

1. **The regime conditioner was dead system-wide.** `regime.classify()` read only feather files;
   `candle_updater` (their refresher) was deliberately disabled 2026-07-12 for API load — from that
   day every feather aged past the 3h staleness bound and classify() answered "unknown" for
   **258/258 cached keys** (measured; vote log: 799 unknown / 176 chop / 0 trend). Every
   regime-bucketed structure — truth-ledger buckets, regime-aware fusion, mirror-gate research —
   silently collapsed into one pool. **Fix:** classify() now reads the in-RAM mirror's 5m bars
   first (fresh for every USDⓈ-M perp, zero API — THE MOTTO), feathers as fallback.
2. **Fixing #1 would have reset every source to "unproven" per regime** (buckets keyed
   source|market|regime|horizon start at n=0 for real regimes). **Fix:** hierarchical
   empirical-Bayes shrinkage in `learned_direction.reliability()` — a thin regime bucket borrows up
   to `LEARNED_DIR_SHRINK_K` (24) pseudo-observations from the source's across-regime pool, so
   earned trust carries over and regime evidence takes over as it accumulates. Replaces the old
   all-or-nothing step fallback.
3. **The two decision lanes had drifted apart.** Breadth lane read ~15 lenses; the SELECTIVE lane —
   which opened 19 of 28 post-restart trades — read only 4 (funnel_mtf_vote ≈47% anti-signal,
   indicator_fusion, strategy_library, direction_model). A lens could earn weight in the lane that
   rarely fires and never touch the lane that trades. **Fix:** one shared
   `BrainExecutor._lens_reads()` collector used by BOTH lanes.
4. **The deep lenses were unreachable.** `_learned_filter_side` had exactly one caller, always
   `fast=True` — so the bull/bear debate (DEBATE_DIRECTION=1!) and brain_sources' deep lane
   (worldmodel/concept flags) could NEVER run in production. **Fix:** the selective lane (≈19
   decisions/hour — LLM-affordable) now calls the shared collector with `fast=False`.

Tests: `tests/test_brain_connect_upgrades.py` (10) + 104 regression green. Pre-existing failures in
`test_mirror_gate` (2) are stale tests for the RETIRED Mirror Gate, untouched by this batch.

## B. Verified-wired (audit false-alarms — do NOT "fix")
cortex (`_cortex_shadow` + M1 stacking features), decision_memory (`_apply_decision_memory`),
native/rolling_vp (numba kernel in features_ext), curiosity + worldmodel-planner + researcher +
evolution (inside `BrainLearningCycle`, which runs in the FUNNEL, not the disabled run_brain_loop),
postmortem (win-quality/sizing via fusion by design, deliberately not a direction lens),
river close-learning + truth backfill (post-B2 fixes, live in funnel/live_loop).

## C. Proposed extensions (propose→approve; ranked impact×confidence÷effort)

| # | Idea | Type | Why / expected gain | Effort/Risk |
|---|------|------|--------------------|-------------|
| E1 | **Off-policy evaluation (OPE) nightly**: vote_log already stores every lane's readings + decision; join with outcomes and run SNIPS/doubly-robust estimates of candidate weight-configs (e.g. different shrink_k, min_edge) WITHOUT trading them. Solves B2's "can't measure learning without a code freeze" forever. | new (learning) | pick weight-configs on evidence, not vibes; continuous counterfactual measurement | M / low |
| E2 | **Exit-policy bandit**: unify dir_exit (advisory), profit-tailgate ratchet, VA-grammar trail (video A), regime-aware + partial scale-out (ledger 07-12 proposals) into ONE per-trade exit-policy choice, chosen by a Thompson bandit keyed (regime, lane), outcome-logged. Exit is the measured gap (direction program). | extension | the exit fixes selection/timing/exit gap where sign accuracy already ≈0.523 | M-L / med |
| E3 | **Worldmodel + concept lenses mirror-backed + ON**: their `_worldmodel_p/_concept_p` fetch OHLCV via ccxt (API, anti-motto) which is why flags default 0. Rewrite to `get_mirror().candles()` and default ON in the deep lane (weightless until earned). | extension | two built-but-dark lenses go live with zero API cost | S / low |
| E4 | **Lesson→prior distillation**: lesson_recall currently feeds only the debate prompt. Distill lessons into per-(symbol, source) priors via existing FTS5 memory-search, consumed as a decide() prior nudge, ledger-tracked as source `lessons`. | extension (learning) | closes the "brain writes lessons nobody reads" loop beyond LLM lanes | M / med |
| E5 | **On-chain/alt-data lens**: `trading/altdata/onchain.py` — flagged unwired 07-07, STILL orphaned. Wrap as truth-ledger lens (same contract as vp_events). | connect | a real, free signal family enters the earn-weight pipeline | S / low |
| E6 | **Order-book depth-watch**: `tools/orderbook_collector.py` is orphaned while P1 Input Hunt explicitly needs wider depth capture for dobi. Wire into the mirror's watch list. | connect | feeds the input-ceiling program's named gap | S / low |
| E7 | **RL execution plug-in**: `trading.execution.rl_exec_env/rl_execution` island (built + tested, never plugged). Use as execution-timing policy (limit vs market, queue position) behind the funnel's order door, paper-logged. | connect | TCA pillar; entry slippage is pure cost today | M / med |
| E8 | **Conditioner sub-buckets**: record clock_phase + liquidity_regime (book-state research: flow only works STRESSED + at quarter-hours) on every ledger row; extend shrinkage chain regime→conditioner→global. | extension (learning) | conditions trust on WHERE a source works | M / med |
| E9 | **Cycle-break refactor**: brain_executor↔micro_policy↔percoin_decider↔strategy_table + the screener↔brain↔live_loop mega-cycle (audit §2). Extract shared leaf modules. | hygiene | kills lazy-import fragility (524-wedge class) | M / low |
| E10 | **Dashboard honest-wiring sweep**: 37 uncalled endpoints (audit §5) — retire dead ones, panel-ize the valuable (curiosity, learning_curve, gate_tuning); verify the `/api/trading/brain/decisions` route/caller pair. | hygiene | honest-dashboard rule | S-M / low |
| E11 | **Meta-labeler refit on clean ledger**: only post-2026-07-16 21:23 rows are uncontaminated (B1/B2 scars); refit D6 + revisit the voided conformal gate on that window. | extension (learning) | calibrated P(correct) on honest data | S / low |
| E12 | **Cross-symbol catalog routes 5/6/7/10/11** (lead-lag graph, cointegration lane, BTC-dominance regime symbol, rank momentum, funding/OI divergence) as further market_state sources. | extension | the rest of today's catalog enters the same earn-weight pipeline | M each / low |

**Explicitly NOT proposed:** re-enabling candle_updater (API-ban contributor; mirror supersedes);
any shadow/advisory mode (CONVENTIONS §15); tuning CRYPTO_MIN_SCORE (measured no-op).
