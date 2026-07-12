# Deep-Connect Audit — Findings Ledger (2026-07-12)

Task: connect all brain/learning/research features so real data flows into the open-trade
decision + learning; make non-working features work; then modernize weak subsystems.
Authority: full autonomy, report at end. Wire+fix existing FIRST, then aggressive SOTA modernize.

## A. RUNTIME-CONTRIBUTION GAPS (built but not reaching the open-trade decision)

Static import graph says these are "connected", but runtime trace shows their OUTPUT never
gates a trade. This is the core of "features never included in opening trade".

1. **indicator_fusion.fuse() output — THE big one.** `funnel.py:343` computes a rich fused
   signal (multi-TF confluence + vision 35% + order-flow ±0.12 + sectors ±0.08 + ai-select
   +0.05 + volume-profile ±0.15 + YOLO ±0.10 + **direction-equation ±0.15** + on-chain ±0.06
   + options-regime sizing) and stores it in `app_signals` → `decision_snapshot.app_signals`
   (brain_executor.py:1177). But the executor decision reads only `extra_signals[sym]["vote"]`
   (the simple `_vote(charts)` CNN/candle vote), `book`, `screener` — **never `indicator_fusion`**.
   → The entire fusion stack, INCLUDING the owner's flagship direction-equation, is logged but
   does NOT influence direction/score. HIGHEST-VALUE WIRE.

2. **CORTEX network** — shadow only (`_cortex_shadow`, brain_executor.py:420). Changes the
   trade only under `CORTEX_TRADE=1`; default `CORTEX_SIGNAL=1` = shadow (records, no effect).

3. **debate_gate** (multi-agent debate before trade) — only caller is
   `dashboard/routes/trading_ext.py` (an API endpoint). Never gates a live entry.

4. **rl_exit** (RL exit policy) — only re-exported in `brain/__init__.py`, never invoked.
   Exits actually run via `trading.direction.dir_exit`. rl_exit is dead.

5. **metalearn, selfeval, selfimprove** — only re-exported in `brain/__init__.py`, never called
   in any loop. Inert.

6. **rnd** (Random Network Distillation curiosity) — only `dashboard/routes/brain_ext.py`.
   Not driving exploration in the decision (explore uses vote p_up / lane instead).

## B. GENUINE ORPHANS (never imported at runtime)

7. `nodes.advanced_ml_nodes`, `nodes.loop_nodes`, `nodes.symbolic_node` — NN node modules never
   loaded (autoload/registry/run_multi don't reference them).
8. `trading.crypto.freqtrade.ml_decider` — superseded by percoin_decider; only a doc-comment ref.
9. `trading.advintel`, `trading.alerts.bot`, `trading.altdata` (pkg __init__) — orphan pkgs
   (onchain.py inside altdata IS used by fusion, but the pkg entry is orphan).

## C. STRUCTURE ISSUES

10. Import cycles (25): notably `direction_equation ↔ indicator_fusion ↔ direction_equation_deploy`,
    `percoin_decider ↔ brain_executor` (lazy-guarded), and a big `boss/live_loop/truth_ledger/
    broker_features` tangle. Lazy imports mask them at runtime but they're fragile.
11. INDEX.md drift: 497 stale entries, 1 undocumented (`.cortex_build_job.py`). gen-index overdue.
12. Dashboard: 37 endpoints with no UI caller (many are on-click /status = false positives, but
    /api/trading/onchain, /dreams, /curiosity, /learning_curve, /gate_tuning, /memory_search,
    /brain/librarian/status, /brain/quiz/status likely surface real features with no panel).

## D. LEARNING LOOP (what the continuous daemon actually trains)

- `brain/learn_loop.run_once` runs: learner, dreamer, connectivity_monitor, news_ingest, gate_tuner.
- `brain/learner.py` reads PDFs (pypdf) + memory.librarian + self_quiz.MasteryQuiz = the "books"
  learning. NEED to verify its output reaches the trade decision (else books don't contribute).
- Distill: run_micro_distill uses challenger (teacher tournament) → micro_policy student (IS used).

## E. DASHBOARD SYSTEM-MAP EVIDENCE (screenshots 2026-07-12)

The dashboard's own Whole-Brain System Map (29 working / 11 resting / 0 off) corroborates:
- **Brain self-flagged it**: Stream-of-Mind "⚠ PROBLEM 07:19: Connectivity REGRESSION: 5 newly-
  orphaned module(s), 7 newly-dead endpoint(s) — wire them" (connectivity_monitor = "Wiring watchdog").
- **Per-coin decider: "decider idle (last 10.9h ago)"** — the live decision-maker node is stale.
- **Strategy library (239): RESTING** — "config 5.9d ago"; **Regime hub: RESTING** "hub not fitted
  in the live loop yet"; **Model catalog (228 classes/108 experts): RESTING** "training in progress".
- **CORTEX network: accuracy 0.495 < naive baseline 0.546** at EVERY selectivity (top50 .503<.564,
  top30 .517<.573, top10 .536<.602). Built 179.7h ago (7.5d stale). = an anti-signal (matches the
  40.3% direction-accuracy memo). ⇒ do NOT blind-promote cortex to trade; route via mirror-gate.
- On-demand/resting (not continuously contributing): World model (MuZero), Foundation TS heads
  (TTM/Chronos/TabPFN), NEAT evolution lane, Computer-use GUI agent.
- Holdout accuracy 0.495 vs naive 0.546 — whole network underperforms naive baseline.
- Trades DO open/close via explore_open_all (profitable close SYN/USDT +9.0 R0.45). 0 page errors,
  46 trading panels render. data_consistency_qa: 0 mismatches on 5 sources (shown data is honest).

## KEY PRINCIPLE FOR WIRING (paper lab)
Several orphaned signals (cortex, raw direction) UNDERPERFORM naive baseline. Wiring a bad signal
straight into trades makes trades worse. So the honest wire = route every newly-connected signal
through the EXISTING evidence machinery (truth_ledger → mirror_gate self-inversion → meta_labeler
calibrated gate) so its weight tracks its MEASURED reliability and self-inverts if it's an anti-
signal. This is the project's own D1–D9 direction program — reuse it, don't blind-trust.

## VERDICT SO FAR
The trade decision is driven by: micro_policy → percoin_decider (153-strat tournament) →
account-path/explore (simple vote) → gates (mirror_gate, meta_labeler, hypothesis-veto,
decision_memory, concept-discovery, psychology, UQ, regime-block). The SOPHISTICATED fusion/NN
lenses (indicator_fusion, cortex, debate, rnd, rl_exit, metalearn) are NOT in that path.

## F. LIVE-STATE DIAGNOSIS (2026-07-12)
- Funnel IS cycling: `[funnel:crypto:options] 07:21:36 entered=[] skipped=7 universe=98
  reasons={no_direction:5, hollow_book:2}` (recent, decider producing decisions).
- **BUG (real, non-fatal):** crypto funnel log (8.2MB) is flooded with Playwright
  `greenlet.error: cannot switch to a different thread (which happens to have exited)` —
  sync Playwright touched across threads. Non-fatal (cycles complete) but pollutes logs and
  signals an unstable browser session. → debug-error backlog item.
- "per-coin decider idle 10.9h" = stale heartbeat metric (decider.decide runs each cycle);
  heartbeat likely only stamped on the futures segment. → cosmetic wiring fix backlog.

## G. WORK DONE THIS TURN (verified)
1. **WIRED indicator_fusion → the live decision** (the flagship gap A#1):
   - brain_executor `_apply_fusion()` adjuster: fusion agreement scales confidence ±25%×conviction.
   - brain_executor FLAT-fallback now PREFERS fusion.direction (tagged "indicator_fusion",
     routed through mirror_gate) over the raw mtf vote.
   - funnel records fusion as a measured directional source in truth_ledger → mirror_gate can
     invert it if it becomes an anti-signal (reliability-weighted, per SOTA meta-labeling research).
   - VERIFIED: unit smoke (agree 0.5→0.575, disagree →0.425, unavail→None) + 47 tests green
     (test_broker_sense 29, test_indicator_fusion + test_direction_equation_deploy 18).
   - EFFECT: order-flow, volume-profile, YOLO, on-chain, sectors, ai-select, AND the owner's
     direction-equation now reach real trades (previously computed + logged only).

## H. PRIORITIZED BACKLOG (remaining wires + modernizations)
WIRE/FIX (do first):
- W2. ✅ DONE 2026-07-12. Root cause (py-spy): reflex/pullback-sweeper thread drove the main
  loop's thread-bound sync-Playwright browser → greenlet crash-loop (funnel never finished a
  cycle). Fix: SessionManager owner-thread guard (claim_browser_owner on main thread; foreign
  threads → API/None fallback). Verified: 0 greenlet (was 101+), first full 422s cycle completed,
  funnel alive; regression test tests/test_sessions_thread_guard.py (2 passed) + 29 broker_sense.
- W3. ASSESSED 2026-07-12: Strategy Library (239) ALREADY contributes to live decisions via
  percoin_decider→LibraryBrainDecider; "RESTING" = foundry breeding cadence (last 5.9d), not
  disuse. Regime hub (BrainHub: JumpRegime+EXP3 trust+DriftSentry+ChampionManager) is a full
  per-bar meta-controller that OVERLAPS already-wired systems (direction.regime.classify +
  mirror_gate/truth_ledger trust + champion_bandit) → half-wiring adds competing noise. → M-tier
  consolidation (pick best impl), NOT a Phase-1 wire.

- SUPERSEDED-NOT-MISSING (key reframe): several "orphans" are earlier/alternative impls already
  superseded by the systems wired into the executor — force-wiring duplicates would add decision
  noise (money-lens: don't). Retire OR M-tier consolidate, do NOT blind-wire:
  · selfeval.reflect_and_store  ← decision_memory already does FinMem reflections
  · selfimprove (SelfImprover/DSPy) ← champion_bandit + gate_tuner already optimize
  · metalearn (MetaLearner few-shot) ← node network already adapts online
  · rl_exit ← dir_exit is the wired exit path
  · regime_hub ← direction.regime.classify is wired
- W4. Per-coin decider heartbeat across all segments (kill the false "idle 10.9h").
- W5. debate_gate (Adversarial Debate panel) → advisory gate in the decision (currently endpoint-only).
- W6. rl_exit → exit path (or confirm dir_exit supersedes and retire rl_exit); metalearn/selfeval/
      selfimprove → learn loop (currently re-exported, never invoked).
- W7. rnd (RND curiosity) → drive exploration selection (currently endpoint-only).
- W8. NN node orphans (advanced_ml_nodes, loop_nodes, symbolic_node) → wire into node network or retire.
- W9. Confirm "books" learner (pypdf + librarian + self_quiz) output reaches the decision.
- W10. gen-index (497 stale INDEX entries) + break the direction_equation↔indicator_fusion cycle.
MODERNIZE (do after wiring, per owner: aggressive):
- M1. CORTEX underperforms naive baseline (0.495<0.546) → retrain/rebuild (7.5d stale) or replace
      the hierarchical-gate with a stronger learned stacking meta-learner over ALL lens outputs
      (research: stacking > averaging for heterogeneous alphas) — this ALSO subsumes the direction
      accuracy problem (40.3% anti-signal).
- M2. Replace hand-tuned bounded-tilt fusion with a learned, calibrated stacking meta-model.
- M3. SOTA hunt for hypothesis engine / strategy generators / order-flow per owner directive.
