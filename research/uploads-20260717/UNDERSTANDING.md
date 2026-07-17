# Owner's saved posts — read & understood 2026-07-17

Ten phone screenshots, two sets. Images kept locally (not committed — repo convention).

## Set A — seb.ai: "I built an AI hedge fund with Claude Fable" (7 slides of an 8-slide carousel)

An "investment committee, not one agent" architecture — each slide one layer:
1. **Pipeline**: Research → Debate → Backtest → Risk → Verdict; "treat every trade like an
   investment committee would"; built from open-source GitHub projects.
2. **Committee roles**: Research (market scanning) / Bull Case / Bear Case / Trader
   (execution logic) / Risk (sign-off) / Verdict (approve-reject).
3. **Research layer**: price feed + news feed + market data + sentiment → synthesized
   "research brief" → decision input.
4. **Debate layer**: bull thesis vs bear thesis → debate engine ("agents challenge
   assumptions, stress-test evidence, weight the cases") → verdict w/ confidence score.
5. **Backtest layer**: "No backtest. No trade." Strategy input → data layer → backtest
   engine → results review (win rate / profit factor / max DD / trades) → risk filters →
   deploy to paper/live.
6. **Risk layer**: position size, drawdown guard, stop loss, exposure, kill switch; a RISK
   GATE that can BLOCK the trade — "that's the whole point"; "no exceptions, discipline is
   the edge."
7. **Execution**: "Only then does it PAPER TRADE. Simulation first. Real money stays off
   until the system proves itself." Live trading: DISABLED behind a lock.

### How it maps to OUR brain (honest comparison)
Every layer already exists here, mostly in a more measured form:
research layer = mirror/filters/news/onchain/VP lenses → app_signals; debate = debate_gate
(bull/bear/risk contest, deep lane); backtest gate = foundry/tournament CPCV+DSR promotion
gate ("no backtest no trade" = PROMOTED gate + cycle_gate nulls); risk = caps, market_guard,
cost gate, UQ (armed for live), NSE/crypto isolation, kill switches; verdict+log = decide()
+ truth/direction ledgers (auditable "why this side"); paper-first = the repo's founding
doctrine (§15). What WE have that the post doesn't: measured per-source trust with recency
half-life, a permanent control lane, pre-registered verdicts, OPE counterfactual replay,
conditioner-refined reliability, and the no-inversion law. Takeaway: the owner's saved
architecture VALIDATES the current design; nothing structural to adopt. One phrase worth
keeping: risk "no exceptions" — matches our gate discipline.

## Set B — techwith.ram "Data Literacy" series (3 infographics)
101 **Hypothesis testing** (H0/H1, p-values, α, Type I/II, power, common-tests cheat sheet),
102 **Chi-square** (goodness-of-fit / independence / homogeneity, df, expected≥5 rule),
103 **ANOVA** (3+ group means, F-ratio, post-hoc Tukey/Bonferroni, effect size η²).

### Relevance to our system
These are the exact statistical disciplines the mission already operationalizes: Wilson CIs
(interval-based significance), pre-registered hypotheses before data, "underpowered ≠
wrong", min_edge as an effect-size floor, Bonferroni-style multiple-testing awareness in the
OPE grid. Possible future tool (noted, not built): a chi-square INDEPENDENCE test over the
E8 conditioner sub-buckets (does source correctness actually depend on liq/clock/sel?) as a
formal admission test before a conditioner refines weights — the shrinkage chain currently
handles this softly. Low priority; revisit when cond_buckets are dense.
