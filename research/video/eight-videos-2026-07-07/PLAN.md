# Eight-Video Ultra-Upgrade Plan (2026-07-07)

Source videos ingested to research/video/{vp0..vp6, self-improving-agent}/ (frames +
transcript + understanding.md each). This plan maps every concept from the 8 videos onto
the ML-network-brain project, keeping only what we DON'T already have (or have weaker),
reuse-first, paper-first.

## The 8 videos in one line each
- **vp0** Polymarket copy-research bot: rank wallets (ROI/consistency/copyability per
  category) → copy/watchlist/skip filter → tiered paper trades → decision journal →
  judge decisions later → auto rule-updates w/ versions → beat a BLIND-COPY baseline →
  autonomy must be earned (30d+, 100 trades, baseline win, sane DD).
- **vp1** $50→$500→$0 blow-up (fee bleed, regime change, manual tweaks made it worse) →
  Karpathy **autoresearch** adapted to trading: LLM generates a new strategy per cycle,
  hold-out backtest, auto-reject look-ahead cheaters, keep only champions (gen 61 best).
- **vp2** RL (PPO/stable-baselines3) gym env: action = no-trade or (direction, SL, TP)
  from a pip menu; reward = trade PnL; SL+TP-same-candle counted as LOSS; in-sample vs
  out-of-sample overfitting lesson.
- **vp3** Hermes Agent as 24/7 Telegram trading analyst: persistent user-profile memory,
  agent-created cron briefings (regime gate → positions → setups → options lens → stance
  + sizing math), insider-filing research, data-provenance lines, multi-agent
  one-job-per-agent pattern.
- **vp4** Dennis Yu RSI: skill.md → definitive article (after 3 supervised runs) →
  persistent runtime w/ scheduled triggers ("fleet audit") → **meta article per
  execution** (self-notes + token cost) → per-agent track records (1000/200/50 runs) →
  loop back into the definitive article; proof/track-record = the moat.
- **vp5** Kraken Pi bot: 3 agents (Strategy-from-books, Data-Pattern-Miner, Risk-Metrics
  Sharpe/Sortino/Kelly) write CODE to a **dev git branch** → auto-backtest dev-vs-main on
  30d AND 1y tick data → auto-merge + live restart only if equity+Sharpe+DD all better.
- **vp6** 7 named agents: 5 scouts on public gov/market data (SEC Form-4 insider buys,
  13F whale funds, Fed speeches, on-chain whale flows, portfolio drift) → **Sophie
  consensus oracle** (fire only when ≥3/5 agree on ticker+direction within 7 days) →
  **Ross dispatcher** (email/Telegram; NEVER trades); SQLite state; model tiering.
- **self-improving-agent** Hermes as BRAIN over a Railway worker: **goal.yaml
  scoreboard** (target return / max DD / min Sharpe / failure line; every trade scored —
  "no vibes, just numbers"), weekly reflection w/ **one-variable-only** scientific
  method, hypotheses.jsonl, regime-tagging each trade, **read-only first cycle → human
  flips mode: live**, **parameter-ownership split** so two optimizers never fight.

## What we already have (do NOT rebuild)
Paper-first dual-mode risk; 85-col journal + decision_snapshot; FinMem decision memory +
SHAP + reflections; HypothesisLedger + world-model + self_evolve; strategy foundry +
generator portfolio behind ONE CPCV+DSR gate; CORTEX; broker-sense funnel (THE trade
driver) w/ indicator fusion + regime gate + UQ meta-label; conformal UQ gate; boss
directives + Brain Chat; continuous learn loop (FSRS); HippoRAG/A-MEM memory + FTS5
search; per-skill LEARNINGS.md self-improvement; provider telemetry; computer-use/ocular.

## Workstreams (ranked by impact; each = one /build-feature run)

### W1 — Goal Scoreboard layer (from self-improving-agent §goal.yaml)  [S]
Machine-readable `trading/goal.yaml` per segment: target_return_30d, max_drawdown,
min_sharpe, failure_below, reflection_every, one_variable_only. Score EVERY closed trade
and every daily equity point against it (toward-goal / toward-failure); expose
`/api/trading/goal_score` + panel tile; boss + self_evolve read it as the single
optimization target. Files: trading/goal.py (new), boss.py, learn_loop.py, dashboard.

### W2 — Scientific-method reflection + ownership map (self-improving-agent, vp0)  [M]
(a) `one_variable_only` guardrail in self_evolve/learn-loop rule updates; every change
recorded as **rule vN → vN+1 with old value, new value, evidence, reason** (vp0's
versioned rules; we have hypothesis.py — extend to a RuleVersionLedger).
(b) **Parameter-ownership map** (`trading/brain/surface.py`): declare which optimizer
owns which knobs (boss / self_evolve / foundry / percoin_decider / funnel weights) —
enforced at write time; mirrors Hermes-vs-Cornelius split; offset their cycles (3-day
style) so two learners never tune the same knob in the same window.
(c) `mode: read_only|live` flag per optimizer: first cycle of any NEW optimizer produces
a markdown review only; owner flips mode (dashboard toggle) to grant writes.

### W3 — Evidence lane: baselines + counterfactuals + autonomy gates (vp0, vp1)  [M]
(a) **Blind-baseline shadow ledger** per segment (blind momentum / buy-hold / follow-all-
signals-uncritically) so every dashboard PnL chart shows "brain vs blind" — proves the
filter adds alpha (vp0's PAPER PNL VS BLIND COPY).
(b) **Missed-winners / avoided-losers counterfactual tracker**: every SKIPPED/vetoed
candidate (UQ gate, funnel veto, min-score) gets a shadow outcome at +1h/+6h/+24h/close;
good-skip vs bad-skip stats feed rule review (vp0 §9, our uq_abstentions.json is the seed).
(c) **Autonomy gates** codified: promote any strategy/segment to bigger size or live only
after ≥30 profitable paper days + ≥100 trades + beats blind baseline + no data failures +
sane DD (vp0 §17); shown as a checklist panel.
(d) **Blow-up watchdogs** (vp1): fee-bleed monitor (fees/PnL ratio alarm), balance-
stopped-changing watchdog, "market regime changed vs validation period" alarm.

### W4 — Smart-money scout swarm + consensus oracle (vp6, vp3, vp0)  [L]
Named scouts as small schedulable jobs writing to SQLite + funnel:
- **NSE insider scout**: NSE/BSE insider-trading disclosures + bulk/block deals (nselib/
  nsepython endpoints we already vendor).
- **Whale-fund scout**: FII/DII daily flows (NSE) as our "13F" equivalent.
- **Cenbank scout**: RBI/Fed speech sentiment (dovish/hawkish) weekly.
- **On-chain whale scout**: exchange↔private wallet accumulation/distribution for
  BTC/ETH/SOL (free APIs), every 6h (complements our order-book trader-psychology).
- **Leaderboard copyability scout** (vp0): Binance futures leaderboard → wallet profiles
  scored ROI / consistency / copyability PER category; output = candidate tickers w/
  direction, never blind copies.
- **Sophie consensus node**: fires only when ≥3 scouts agree same symbol+direction in a
  7-day window (DELPHI_MIN_AGREE/WINDOW env) → new interception kind
  `smart_money_consensus` fused in funnel decision_snapshot + boosts entry score.
- **Ross dispatcher**: read-only alert agent → Brain Chat + optional Telegram; never
  trades. Model tiering: cheap model for scouts, deep model for consensus (vp6 env).

### W5 — Auto-researcher champion loop hardening (vp1, vp5)  [M]
Add to our generator portfolio: (a) **champion/challenger lineage** (gen counter, best-
strategy provenance, score-progression chart = "Trading Researcher" panel);
(b) **look-ahead tripwire**: any backtest "too good" (e.g. >X·DSR-implied bound or
absurd PnL) auto-rejected as leakage (cheap complement to CPCV+DSR);
(c) **git-branch promotion mechanic** (vp5): strategy-code changes land on a `dev`
strategy slot, auto-backtested on BOTH 30-day and 1-year windows, promoted to `main`
only if equity + Sharpe + maxDD ALL improve, then hot-reload; every discard logged;
(d) fixed per-experiment compute budget (autoresearch's 5-min rule → our CPU budget).

### W6 — RL execution-policy node (vp2)  [M]
SB3 PPO node (`ml/nodes/rl_exec_node.py` + gym env): observation = window of our fused
features; action = no-trade | (direction, SL, TP) from an ATR-scaled menu; reward =
realized PnL; ambiguous SL+TP candle = LOSS (vp2's honesty rule — also audit our
backtester for this); strict train/holdout; wired as ONE MORE cortex node (paper only),
Optuna-tuned. Deps: stable-baselines3 (+gymnasium) — ask-to-install.

### W7 — Meta-articles + track records (vp4)  [S/M]
(a) Every significant brain action/strategy run appends a **meta-note** (what/why/edge
cases/cost) to brain_memory (extend existing file-notes; the LEARNINGS.md loop we built
for Claude skills, applied to the brain's own skills/strategies).
(b) **Track-record registry**: per strategy/node/scout counters (runs, wins, cost in
tokens/CPU-sec) → trust weighting + "rule of three" (nothing auto-scales until 3
supervised successes) → per-agent report card panel.
(c) Definitive-article docs: auto-maintained doc per strategy linking its meta-notes.

### W8 — Chat-employee layer (vp3)  [S]
(a) **Daily morning briefing** cron (already have scheduler pieces): regime gate (VIX-
equiv / our regime engine) → open positions review → top setups → options lens (NSE) →
clear stance + sizing math from OUR capital rules; delivered to Brain Chat panel (+
optional Telegram bot with allowed-user-ID gating).
(b) **Provenance lines** on every market answer ("sources checked: … dated …").
(c) Owner profile (style, rules, segments) persisted and injected into all briefings
(we have boss/memory — formalize a profile.yaml).

## Sequencing
1. W1+W2 first (small, they give every other loop its scoreboard + safety rails).
2. W3 (evidence lane) — makes all existing claims honest and gates autonomy.
3. W4 (scouts+consensus) — biggest new signal alpha; independent of W1-3.
4. W5 → W7 → W8 → W6 (RL last; heaviest, CPU-bound training).
Per workstream: /research-projects → /build-from-oss → tests → /verify-live →
/dashboard-visual-qa → /commit-safe. All paper-first; live only via W3 gates.

## Reuse-first dependency notes
- SB3 + gymnasium (W6) — pip, ask-to-install; pandas_ta already used patterns (vp2).
- nselib/nsepython insider+bulk-deal endpoints (W4) — already vendored/known.
- Telegram: python-telegram-bot or plain Bot API via stdlib requests (W4/W8).
- No Hermes/OpenClaw install needed: our brain already fills that role; we lift its
  PATTERNS (goal file, surface split, read-only-first, one-variable) not the framework.
