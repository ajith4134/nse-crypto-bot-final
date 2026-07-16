# B2 — DOES THE BRAIN ACTUALLY LEARN? Verdict (2026-07-16, evening)

**One-line verdict: No — not yet, and the evidence is specific. The measured accuracy improvement
is a one-time REPAIR STEP (2026-07-09) from session-shipped code, not a learning slope; after the
step there is zero within-era improvement over 8 days; the learned decision channel is no more
accurate than its own unlearned explore control; and the flagship "online learner" has never
received a single live outcome — its learn() has no production caller.**

Everything below is era-controlled per the standing lessons (bucket accuracy is non-stationary;
era-control every journal metric). The drift-proof metric used throughout is **per-day balanced
accuracy** — (long-accuracy + short-accuracy)/2 — which a coin-flip scores 0.5 on regardless of
market direction, so a falling market cannot masquerade as learning and a regime shift cannot hide
it. Substrate: 6,985 usable closed crypto trades (journal, 2026-06-29 → 07-16, entry→exit sign,
ties excluded).

---

## 1. The improvement is a step, not a slope

Daily balanced accuracy, weighted model comparison (AIC, lower = better):

| model | RSS | AIC |
|---|---|---|
| constant | 21.80 | +7.6 |
| linear "learning" slope | 9.01 | −3.6 |
| **step at 2026-07-09** | **4.79** | **−13.1** |
| step + post-slope | 4.11 | −13.4 (post-slope **−0.013/day**, i.e. negative) |

Pre-step balanced accuracy **0.337 fitted / 0.351 pooled** (independent re-derivation) —
systematically *anti*-accurate either way, the poisoned-inverter / Mirror-era signature.
Post-step **0.533**. The step coincides exactly with the direction-equation
P2–P4 deployment, the in-RAM WS mirror data migration, and the direction-accuracy diagnosis
commits (c9e1ee7, 6058d1a, b355cf5, 8b7e3b0, 750bb82 — all 2026-07-08→10). **The brain got better
because sessions repaired it, not because it learned.**

## 2. After the repair: a real edge, and no learning on top of it

- Pooled post-2026-07-09 balanced accuracy: **0.5269 ± 0.0080 (z = +3.37 vs coin-flip)** on
  nL=3,401 / nS=1,367. The system genuinely calls direction slightly better than chance now.
- Within-era trend: **−0.013/day (t = −1.26)** over 8 days. No continuing improvement; mild
  (insignificant) decay. If the 30-minute learn loop, FSRS, self-evolve, school, or the
  experience machinery were improving decisions, this is where it would show. It doesn't.

## 3. The learned channel does not beat its own unlearned control

Post-era, drift-honest (both sides ≥ n=93), same window, same market:

| channel | nL | nS | balanced acc | z vs 0.5 | mean net P&L % |
|---|---|---|---|---|---|
| learned_direction (ledger-weighted learner, money path) | 1,330 | 960 | 0.5399 | +3.79 | −0.91 |
| **explore_open_all (unlearned explore lane — the control)** | 577 | 207 | **0.5620** | +3.08 | −1.16 |
| filter:momentum | 124 | 93 | 0.4624 | −1.11 | −1.62 |

The unlearned explorer is *at least as accurate* as the learned selector (difference not
significant). The learning machinery's contribution to direction, measured against its own
built-in control, is **zero within current power**. Note also: every channel still loses money
per trade despite above-chance accuracy — the loss lives in exits/fees, not signs (consistent
with the exit horizon measuring 0.44 in B1). (`momentum`'s mean-P&L field shows a ~7700% scaling
artifact in `net_pnl_pct` — data bug, flagged, excluded from conclusions.)

## 4. The "online learner" never learns — and B1's poisoning was learning-in-reverse

- **river_online has no learning input.** `river_source.learn()` — "online update from one
  realized outcome, safe to call from the trade-close path" — has **zero callers** in the
  production tree (grep: the only non-test reference to river_source is the predict path in
  brain_sources.py:274). It bootstraps once from the journal at process start and is frozen
  thereafter. Trained on a loss-heavy label set, it latched at 96.7% LONG with the worst ledger
  accuracy (0.4456). The one component built to learn continuously receives nothing to learn from.
- **Where feedback DID flow, it made things worse.** The one genuinely closed learning loop on the
  money path — truth-ledger reliability → learned_direction weights → Mirror-era inversion — is
  the loop that produced the funnel×learned negation (B1: phi −0.950) and the 31-SHORT-vs-1-LONG
  inverter scar. The strongest evidence about this brain's learning apparatus is that its only
  working feedback loop amplified a measurement artifact into systematic wrongness until sessions
  killed it (MIRROR_GATE=0, 19:44 today).

## 5. What each learning subsystem writes, and who actually reads it

Wiring census by an independent read-only agent (file:line for every read claim, verified
against today's tree). "Money path" = funnel → brain_executor → learned_direction. "Advisory" =
read only by the T8 paper loop (live_loop.py) or dashboards.

| subsystem | writes | actually read by |
|---|---|---|
| learn_loop (30-min daemon) | learn_loop.json, KnowledgeBrain/FSRS | study output: **advisory only** (attribution at indicator_fusion.py:605, no tilt). BUT its side-effects maintain money-path signals: truth_ledger tick/backfill, direction_model.train, meta_labeler, uq.recalibrate |
| self_evolve (DEAP) | self_evolve.json; admits survivors to skill library | **nothing it produced reaches trades**: promoted=0/admitted=0; its pipeline attach is advisory-only (live_loop.py:134) |
| skill_library (311 strategies) | ← rd_agent/pysr/gplearn/alpha-mining/QD/optuna/operon/sindy — **none from DEAP** | **money path**: LibraryBrainDecider (funnel.py:428/732 `strategy_library` source) + per-coin tournament → strategy_table → brain_executor.py:497 |
| hypothesis ledger | state.hypotheses.json | **money path** via the brain_sources hypothesis lens only (brain_sources.py:238) — fixed today (B1); no other decision consumer |
| river_online | river_source.pkl (bootstrap-once) | **money path read** (predict) — but `learn()` has **zero realized-outcome callers**: frozen after boot, degenerate 96.7% LONG, ~0 weight |
| learned_direction | (pure function) | **IS the money-path decider**; weights = truth_ledger reliability. Post-inverter-kill honest note: with all sources in the CI-straddles-0.5 band it now frequently **abstains → neutral** |
| symbol_move_net | in-RAM net, retrained every ~30 min from journal | **money path** (brain_executor.py:474; smart_exit.py:70). Genuinely learning — and it learned its way into a 99.3%-SHORT constant (B1) |
| strategy_table | strategy_table.json ← separate daemon (300s) | **money path** (strategy_tournament source, STRATEGY_DIRECTION=1). If the daemon dies the table goes TTL-stale silently |
| postmortem miner | postmortem_patterns.json (30 min) | **wired to money path** (indicator_fusion.py:698-711 size_mult + ideal-entry) **but POSTMORTEM_FEEDBACK defaults 0 = OFF** — computed, shown, never moves a trade |
| decision_episodes/FinMem + school | decision_episodes.json, school.json | **advisory only** (live_loop recall; self_evaluation) — never a real trade |
| exit_reflection / lesson_learned | journal text fields on every close | **nothing reads them, anywhere** — pure write-only narration |

The census's three most damning dead ends: (1) river_online's "learns online as trades close"
is unwired — bootstrap-once, frozen; (2) every trade close writes an LLM "lesson" that no code
ever reads back; (3) the one properly-wired feedback loop into sizing/entry (postmortem) is
default-OFF, so it computes and displays but never acts. And the loop named "self-evolve" has
promoted zero strategies ever — the 311 strategies that DO trade came from the other generators.

**Synthesis with §1–4:** of the eleven learning subsystems, only four touch real trades
(skill_library/tournament, symbol_move_net, learned_direction weights, hypothesis lens). Of
those four: one learned itself into a constant (symbol_move_net), one's only feedback episode
was the Mirror-era self-poisoning (learned_direction), one was recording garbage until today
(hypothesis), and the tournament is the only one with a plausible ongoing learning claim — and
§3 shows the aggregate learned channel doesn't beat unlearned exploration. The measured
no-learning result and the wiring census agree.

## 6. Power calculation — what it would take to SEE learning

At current post-era volume (≈425 long + 171 short closed trades/day → per-day balanced-accuracy
SE ≈ 0.023):

- A **+2 pt/week** learning slope is detectable (t≥2) in ≈ **14 days** of *frozen-code* trading.
- A **+1 pt/week** slope needs ≈ **23 days** frozen.

"Frozen-code" is the binding constraint, not volume: sessions currently ship repairs several
times a week, and every repair is a step that swamps any slope. **If you want to prove or refute
learning, pick a 2–3 week window, freeze the decision path, and let only the autonomous learners
run.** Until then, learning claims are unmeasurable by construction.

## 7. Recommended reading of this result (no fixes applied — B2 is measure-only)

1. The learning apparatus as currently wired is **paying rent in CPU and complexity without
   measurable return on the money path**. The honest options: wire its outputs into the money
   path properly and re-measure (B3's program), or cut the loops that provably feed nothing.
2. **Close the river loop or retire the lens** — one call at trade-close would make it a real
   online learner; today it is dead weight with a misleading name.
3. The +3.4σ post-repair edge is real but small and NOT growing. The gains so far have come from
   *removing self-sabotage* (inverter, mirror, dead pipes) — which supports the audit-and-repair
   loop (sessions) as the current best "learning mechanism", and that is exactly what B1-style
   measurement finds cheaply.
4. Re-run this analysis after the vote log accrues and after any code-freeze window.

## Post-verdict correction & fixes (2026-07-16 ~21:30)

- **Data note:** 374 poisoned NSE|USDT journal rows (market-isolation breach, last written 07-14
  02:18 — the writer guard already holds) were inside this study's crypto filter. Recomputed
  without them: post-era balanced accuracy 0.5264 vs 0.5267 — no conclusion changes. The rows are
  now tagged `poisoned_market_isolation` in the journal (backup kept).
- **The owner ordered everything fixed.** Applied same evening (see the fix batch in
  ensemble-delusion-B1 report + memory): river learns at every close from price-sign labels
  (degenerate pickle reset), symbol_move_net rebuilt on leak-free serve-safe features, dir_exit
  claims deduped to one-per-opinion, mirror-era buckets quarantined (42 buckets / 29,101 labels),
  hypothesis lens side-differential gated, POSTMORTEM_FEEDBACK defaulted ON, exit reflections wired
  into the debate gate via lesson_recall. The no-learning verdict above describes the system
  BEFORE these fixes; the fixes give the learning apparatus its first honest chance. Re-measure
  after a stable window.

## Method

Balanced accuracy per day from journal entry→exit sign; WLS with min-side-count weights;
changepoint scan over all interior days; AIC for model choice; pooled z vs 0.5 with binomial SE;
channel comparison restricted to channels with both sides n>10 post-era. Scripts inline in the
session transcript; all numbers re-derivable from journal.json as of 21:00 2026-07-16.
