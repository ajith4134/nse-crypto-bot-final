# self-improving-agent — "How To Build A Self-Improving AI Trading Agent" (Lewis Jackson, 18:01)

## One-paragraph summary
Lewis Jackson (same creator as vp6) uses **Hermes Agent** (Nous Research; "touted as even
better than OpenClaw because of its self-learning process") as the BRAIN of a
self-improving trading system, via a one-shot Claude Code prompt that runs in one
terminal session: it detects the OS, defines the strategy + **goal file** ("the agent
uses this file to score every trade — no vibes, just numbers"), deploys (or adopts) a
24/7 **worker** on Railway, converts the worker's trade history into a Hermes-readable
ledger, installs Hermes last, and hands off. Hermes then watches the live worker, scores
outcomes against goal.yaml, writes hypotheses, and edits the strategy file **one variable
at a time (scientific method)** on a weekly reflection cycle — read-only first cycle, and
the human grants write access by flipping `mode: read_only → live`. His four criteria for
a good trading agent: **accurate** (data integrity first), **reliable** (24/7, survives
laptop-off — hence Railway), **well-defined goal** (success AND failure defined
numerically), **self-improving** (outcome → hypothesis → one-variable test → new
baseline).

## Every distinct idea (timestamp + frame refs)
1. **Prompt→outcome is not enough** [00:11–00:42]: build prompt → strategy → outcome →
   learning → new prompt→strategy — a closed self-improvement loop, 24/7.
2. **Four criteria** [01:56–06:25]:
   - **Accurate** [02:13–03:22]: he "tested every AI in existence on trading" — the
     shocking result was DATA inaccuracy (same source, different values); fix = strong,
     reliable API connections + rules so news interpretation is objective (same article
     must yield the same conclusion); frames f_0300: feeds (price ohlcv / on-chain flows /
     news headlines / macro rates·vix) must arrive "parsed & typed — schema match
     required".
   - **Reliable** [03:22–03:41]: always operating 24/7 even if your computer dies →
     cloud worker (Railway).
   - **Well-defined goal** [03:41–05:20]: "90% of people creating a trading strategy
     have no definition of what achieving the goal looks like." Define SUCCESS (realistic
     target, ideally a Sharpe score) and FAILURE; then the agent can judge any result as
     toward-goal (good) or toward-failure (bad).
   - **Self-improving** [05:26–06:25]: organize info → analyze outcomes vs goal → form a
     hypothesis WHY → second hypothesis WHAT NEXT → update strategy — **scientific
     method: change only ONE variable, run tests; every improvement becomes the new
     baseline** (Pillar-04 card f_0100: OUTCOME → HYPOTHESIS → TEST(change one variable)
     → REVISE; strategy v02 example entry rsi<25, stop −2%, size 0.5R, score vs goal
     +0.71).
3. **Community prompt library** [06:42–07:36]: prompts live in ZeroOne Systems and are
   continuously improved from user feedback (versioned one-shot prompts).
4. **Onboarding phases** [08:14–16:51, frames f_1229–f_1651]: 1 environment check (OS
   routing) · 2 define strategy (pick asset BTC/ETH/SOL/custom, or "make me a basic one",
   or "I already have a strategy — find it on my computer": it found his **Wacko Alpha**
   dTAO momentum+yield strategy with 1.5M analyzed data points, 6–8 weeks of manual
   learning) · 3 scaffold Hermes-side state (~/hermes-trading/state/: goal.yaml,
   strategy.yaml, trades.jsonl, hypotheses.jsonl, history/) · 4 deploy worker to Railway
   (skipped — already live; interactive `railway login` must be run by the human: `!`
   prefix pattern, "done, continue") · 5 prove Hermes can SEE the live service (railway
   logs; pulled real insight: winners held ~2 fewer cycles, entered nearer local bottoms,
   0.78% vs 1.74% drawdown-at-entry) · 6 install Hermes LAST · 7 final confirmation.
5. **goal.yaml** [10:53–11:16, f_1340]: asset TAO-subnets-dTAO; target_return_30d 0.47
   (+47%/30d — his public "£50k→£500k in a year" 10x challenge, live dashboard linked);
   max_drawdown 0.20; min_sharpe 1.0; failure_below −0.04; reflection_every 7 days;
   one_variable_only true; worker: type external (railway project wacko-alpha).
6. **strategy.yaml = the bounded control surface** [13:40–14:22, f_1400]: version, mode
   (read_only→live), portfolio_mechanics (max_positions 12, slippage_tolerance 0.02,
   gas_reserve 0.20), scorer_weights (week 40 / month 30 / day 20 / pool 10).
7. **Parameter-ownership split** [15:36–15:47, f_1458]: Hermes owns portfolio mechanics +
   scorer weights; **Cornelius** (his existing weekly analyst agent) owns filter
   thresholds in learned_params.json (untouched) — two optimizers partitioned so they
   never fight; Hermes reviews weekly with a **3-day offset** from Cornelius's cycle.
8. **Autonomy gating** [15:47–16:47]: first Hermes cycle = READ-ONLY markdown review, no
   writes; human approves by setting mode: live; "Hermes will start writing on the next
   weekly cycle"; day-after check-in commands provided (railway logs, cat strategy.yaml,
   cat learned_params.json, ls history/). "Hermes is watching. Close this terminal — the
   agent is running."
9. **Regime tagging** (f_1430): score trades against goal.yaml and tag each trade with
   market regime — use the markov-hedge-fund-method skill (~/.claude/skills/) if present,
   else a 20-day rolling-return classifier. (His previous video = "The Hedge Fund Method"
   Markov-regime framework, packaged as an installable skill.)
10. **Real money + honest caveats** [10:28–10:52]: Wacko Alpha trades real money; he
    locks in the proposal "because I trust this system"; progress dashboard public.

## Open questions
- None blocking.
