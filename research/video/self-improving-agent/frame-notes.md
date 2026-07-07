# self-improving-agent (18:01) — frame observations (pre-transcript)

Same creator as vp6 (Lewis Jackson, ZeroOne Systems). Title: "How To Build A
Self-Improving AI Trading Agent". One-shot skool prompt: **"Self-Improving Trading Agent
on Hermes"** — paste into Claude Code, one terminal session, no tab-switching.

## What the prompt builds (f_0715 requirements card)
- Requirements: Claude Code (running), Git, Node.js (for the Railway CLI — agent installs
  if missing).
- Builds: (1) a **trading worker deployed to Railway** running your strategy 24/7 in
  paper mode; (2) a **goal config** — "what success looks like, what failure looks like";
  (3) a **local Hermes install** (Nous Research's open agent) "that takes over as the
  brain at the end. Hermes watches the worker's outcomes, writes hypotheses, and edits
  the strategy file — one variable at a time, scientific-method style."
- Onboarding hard rules: one terminal session; install Hermes LAST (just before hand-off
  so the shell reload doesn't break); wait-gates are gates (don't proceed until viewer
  confirms); detect OS first (Darwin/Linux/Windows → correct `open` command).

## Pillar cards (concept sections)
- [01:00] PILLAR 04 · THE REFLECTION LOOP — "One variable at a time." Strategy card v02
  (entry: rsi<25, stop −2.0%, size 0.5R; SCORE vs GOAL +0.71, cycle 02) + circular loop:
  OUTCOME (trade closed) → HYPOTHESIS (why it happened) → TEST (change one variable) →
  REVISE (update strategy) → …
- [03:00] (another pillar) Data feeds → AGENT: PRICE FEED (ohlcv), ON-CHAIN (flows), NEWS
  (headlines), MACRO (rates·vix) → "parsed & typed — schema match required".

## Setup walkthrough (his real instance)
- Phase 1: env check (✓ Mac ✓ Git ✓ Node.js ✓ Claude Code).
- Phase 2 DEFINE YOUR STRATEGY (7 steps): pick asset (BTC/USDT most liquid default,
  ETH/USDT, SOL/USDT higher vol thinner book, or custom) — "the agent uses this file to
  score every trade. No vibes, just numbers."
- His adaptation: he ALREADY runs "**wacko-alpha**" on Railway (production, DRY_RUN
  paper) — a dTAO momentum + yield strategy on Bittensor subnets, firing every 30 min,
  with an existing weekly analyst agent "**Cornelius**" tuning learned_params.json. The
  onboarding agent ADAPTS: no new worker deployed; Hermes lives locally and watches the
  live service.
- **goal.yaml** (~/hermes-trading/state/goal.yaml, 28 lines): asset "TAO-subnets-dTAO";
  target_return_30d 0.47 (10x in 6 months ≈ +47%/30d compounding); max_drawdown 0.20
  (portfolio bail-out); min_sharpe 1.0 (high-vol quality bar); failure_below −0.04;
  reflection_every 7_days (offset 3 days from Cornelius's weekly cycle);
  one_variable_only true (scientific-method guardrail); worker: type "external",
  railway_project/service "wacko-alpha".
- **strategy.yaml** (Hermes-controlled surface v01, mode read_only first cycle):
  portfolio_mechanics: max_positions 12, slippage_tolerance 0.02, gas_reserve 0.20 (from
  .env); scorer_weights: week 40, month 30, day 20, pool 10.
- **Surface split (do NOT violate)**: Hermes owns max_positions, slippage_tolerance,
  gas_reserve, scorer_weights{week,month,day,pool}; Cornelius owns everything in
  ~/wacko-alpha/learned_params.json (filter thresholds — leave alone). Two self-improving
  agents partitioned by parameter ownership so they can't fight.
- State scaffold: ~/hermes-trading/state/{goal.yaml, strategy.yaml, trades.jsonl,
  hypotheses.jsonl, history/}.
- Phase 5 PROVE HERMES CAN SEE THE LIVE SERVICE: railway status/logs; pulled a real
  finding from logs: "Winners held for ~2 fewer cycles AND had much lower drawdown from
  peak at entry (0.78% vs 1.74%). Winners entered closer to local bottoms; losers entered
  after larger prior drawdowns (suggesting the asset was already hurt)." Snapshot of
  Cornelius's learned_params.json for baseline.
- Phase 6: install Hermes (curl install.sh), Hermes TUI on claude-opus-4-7; the "brain"
  loop (its standing instructions): 1. every 6h tail railway logs for new closed trades +
  Cornelius's latest analysis; 2. once/week (3-day offset) pull trade ledger
  (trades.jsonl, 46 events pre-staged; refresh by copying wacko-alpha/learning.db and
  re-exporting gain/loss events as JSONL), current strategy.yaml, Cornelius's filters
  (read-only); 3. score trades against goal.yaml, **tag each trade with market regime**
  (use the markov-hedge-fund-method skill in ~/.claude/skills/ if available, else a
  20-day rolling-return classifier).
- FINAL CONFIRMATION: Worker = Railway wacko-alpha production DRY_RUN; Brain = Hermes
  (local) watching live service, weekly cadence; first cycle READ-ONLY markdown review,
  no writes; **you approve go-live by editing strategy.yaml mode: read_only → live**;
  day-after check-in commands (railway logs, cat strategy.yaml, cat learned_params.json,
  ls history/). "Hermes is watching. Close this terminal — the agent is running."
- Railway CLI login hiccup: interactive login can't run inside the session → agent asks
  the user to run `! railway login` themselves and resume ("done, continue").
- Community frames [17:30–18:00]: ZeroOne skool — "Groundbreaking New Prompt in
  Classroom": "The Hedge Fund Method" — a 10-feature strategy framework used by actual
  quants, made into a SKILL ("install the hedge-fund-method **Markov-regime framework**"
  prompt in the library); 3x Money-Back Challenge; Monthly Agent Roast; members
  installing via Claude or Cursor.

## Concepts to carry into the plan
1. Goal file as scoreboard (target return / max DD / min Sharpe / failure line) — every
   trade scored against goal.yaml; success/failure DEFINED before autonomy.
2. Reflection loop with ONE-VARIABLE-ONLY guardrail + hypotheses.jsonl ledger + history/
   of weekly reviews; first cycle read-only; human flips a mode flag to grant writes.
3. Brain/worker separation: worker executes 24/7 (cloud), brain (agent) watches
   outcomes and edits a bounded "surface" of parameters it OWNS; other optimizers own
   disjoint parameter sets (no fights).
4. Regime tagging of every trade (Markov-regime skill or rolling-return fallback).
5. Schema-typed ingestion of price/on-chain/news/macro feeds ("parsed & typed — schema
   match required").
