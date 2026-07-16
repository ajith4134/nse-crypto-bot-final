# FABLE-5 BRAIN PROMPTS — 2026-07-16

**Scope:** the owner asked for new prompts **mainly on the brain**. This file supersedes nothing —
`PROMPTS.md` (10:04 today) holds the direction/measurement set (Prompts 0–7). This file is the
**brain-focused** set, generated at 12:20 from a fresh `fable5_snapshot.py` run.

**Every number below was re-derived at 12:20 today. Where it contradicts a doc, the measurement wins.**

---

## §A — WHAT CHANGED SINCE THIS MORNING (read before using PROMPTS.md)

| Claim in this morning's docs | Measured 12:20 | Status |
|---|---|---|
| Exit labels **frozen at n=3,459** for 5 days; `backfill_journal()` has no production caller | **n=7,301**, `frozen_label_check.WEDGED = false` | **FIXED — stale claim.** The exit-label fix works. Prompt 0's premise is partly spent. |
| Overall direction accuracy 0.488 | **0.4922** (111,426 labels, 536 buckets) | holds |
| "4h genuine edge = 55.2%" | **0.5092** (n=23,099) | **still falsified** — do not build on 55.2% |

**New fact this morning's docs don't contain:** the **exit** horizon is the *worst* bucket at
**0.4427** (n=7,301) while 15m/1h/4h sit at 0.4887 / 0.4952 / 0.5092. The brain predicts marginally
better than a coin flip on clock horizons and materially *worse* on the horizon it actually trades.
That gap is the money.

---

## §B — THE MEASURED BRAIN (12:20 today)

**Scale** (exclusions: `srv/`, `.julia/`, vendored): 914 modules / 160,714 lines / 223 test files /
36 vendored forks / 7,170 neurons / 125 brain-OS boots.

**Live state:** hypotheses 130 (+47 failures) · self_evolve 100 · skill_library 260 · 8 live loops
(crypto funnel, NSE funnel, live_loop, micro_distill, autoresearch, strategy_table, freqtrade, dashboard).

**Every direction source, measured:**

| Source | n | acc |
|---|---|---|
| direction_equation | 4,557 | **0.5267** |
| learned_direction | 6,078 | **0.5235** |
| strategy_library | 2,493 | 0.5142 |
| symbol_move_net | 9,208 | 0.5094 |
| indicator_fusion | 5,650 | 0.5042 |
| explore_open_all | 3,905 | 0.5017 |
| filter:funding | 2,376 | 0.4983 |
| dir_exit | 25,191 | 0.4970 |
| hypothesis | 1,808 | 0.4934 |
| mtf_agree | 1,766 | 0.4904 |
| direction_model | 2,102 | 0.4895 |
| funnel_mtf_vote | 18,926 | 0.4765 |
| filter:momentum | 2,592 | 0.4657 |
| river_online | 5,949 | **0.4456** |

**The pattern that should alarm us:** fourteen supposedly independent lenses — a GBM, an online
learner, a symbolic equation, a neural net, a strategy tournament, order-flow fusion, broker filters
— span **0.4456 to 0.5267**. Every one is within ~3 points of a coin flip. Independent lenses on a
real signal do not cluster like that. Either they are all reading the same inputs, or the inputs
carry no signal at these horizons.

**The structural gap that blocks the obvious study:** `direction_truth.json` stores **only
aggregates** (`source|market|regime|horizon → {correct, n}`). There are **no per-decision rows**, so
the 111k labels **cannot** be correlated against each other. Per-trade lens outputs exist only in
`journal.json` — all **7,318** rows carry a rich `decision_snapshot` (per-timeframe `chart`
direction + `p_up`, `book`, `psychology` walls/gap_map, `app_signals`, `strategy`). That substrate
is real but **selection-biased**: it only contains trades the brain chose to open.

**The two-path fact** (`research/audits/brain-stagnated-features-20260714.md`, the most honest doc in
the repo): the **real crypto money path** is a narrow fusion — broker filters + direction_model +
symbol_move_net + strategy_table + UQ gate. The **T8 pipeline** is a separate advisory paper loop.
World-model, evolution, self-improve, continual, concept-discovery, computer-use, news are
**advisory-only or fully orphaned**. Most of the impressive brain does not pick or size a single real trade.

---

## §C — THE PREAMBLE (paste FIRST, every session)

> I'm working on an AI trading brain that is supposed to generate consistent, risk-managed income.
> It runs on paper (Freqtrade `dry_run`) — no real money, no real keys — so the only question that
> matters right now is *what teaches us the most about a real edge*. I'm the owner; I don't code.
> I need conclusions I can act on, not code I can't read.
>
> Ground rules for this session:
>
> - **Measure, don't read.** This repo's planning docs go stale in their key numbers, and sessions
>   keep building on falsified premises. A number in a doc is a hypothesis until you re-derive it
>   from live state. Where they disagree, the data wins and you say so loudly.
> - **Before reporting progress, audit each claim against a tool result from this session.** Only
>   report work you can point to evidence for; if something isn't verified, say so explicitly. If
>   tests fail, say so with the output; if you skipped a step, say that.
> - **A rigorous negative result is a win.** "This doesn't work, here's the evidence" is exactly as
>   valuable to me as a feature. Do not manufacture progress.
> - **Verify with fresh-context subagents**, not self-critique. Establish a checking method as you
>   go and run it periodically against the spec. The owner's standing rule is *one agent at a time
>   for anything that writes*; up to 2–3 read-only agents in parallel is approved. **Ask before
>   exceeding that** — don't silently override it.
> - **Boundaries — and note what is NOT a boundary.** Everything runs on paper (Freqtrade `dry_run`).
>   Paper **is** the experiment, so you have **full access to experiment**: any size, any risk, any
>   trade. A blown-up paper account is training data, not a failure — never hold back on paper, and
>   never ask permission to take paper risk. Don't build "shadow" or flag-gated-off variants of paper
>   work either; shadowing the lab is redundant and it grades the easy half while skipping entry,
>   exit, fees, and slippage — where this brain actually loses. **The real limits:** no real money, no
>   real keys, never touch `.env` or `config.json` secrets, don't cross the crypto↔NSE market
>   isolation boundary, and don't restart production loops (owner action — tell me, I'll do it). The
>   one hard requirement inside the lab: **every outcome must be logged and fed back** to the journal,
>   truth ledger, and hypothesis ledger. An unlogged blowup teaches nothing.
> - **Pause only when the work genuinely requires me:** a destructive or irreversible action, a real
>   scope change, or input only I can give. Otherwise proceed.
> - **Memory:** store one lesson per file in `research/fable5/lessons/`, one-line summary at top.
>   Record corrections and confirmed approaches alike, with why they mattered. Update an existing
>   note rather than duplicating; delete notes that turn out wrong.
> - **Final summary:** I did not watch you work. Write it as a re-grounding, not a continuation —
>   outcome first, plain sentences, no shorthand or labels you invented along the way.
>
> One honesty note about this repo: it does browser automation against broker apps I hold accounts
> with. That is **my own authenticated account, in my own browser, reading data I'm entitled to.**

---

## THE RANKED BRAIN IDEAS

| # | Idea | Why only Fable 5 | Money-lens (PAPER) | Est. |
|---|---|---|---|---|
| **B1** | **⭐ THE ENSEMBLE DELUSION** — are 14 sources one opinion wearing 14 hats? Measure pairwise correlation + effective rank. | Ambiguous ("something is wrong, I don't know what"), needs whole-repo reasoning to reconstruct each lens's vote, plus a long measured run | **PROCEED** — highest information gain in the project | 3–6 h |
| **B2** | **DOES THE BRAIN ACTUALLY LEARN?** — era-controlled proof or refutation of the whole learning apparatus | Long-horizon; requires honest non-stationary statistics the docs keep getting wrong | **PROCEED** — decides whether to keep or cut a large subsystem | 3–5 h |
| **B3** | **THE TWO-PATH RECKONING** — let every orphaned lens actually **trade on paper** and be judged on realized P&L | 1M context to find every lens + wire them uniformly; sustained run to collect | **PROCEED** — paper is the lab; unlimited risk allowed | 4–8 h |
| B4 | **THE GUARDRAIL** — evolution has promoted **0** candidates: honest gate or broken wall? | Multi-hour CPCV/DSR calibration study | **ADJUST** — scope to calibration only; don't loosen a gate to manufacture flow | 2–4 h |

---

## PROMPT B1 — THE ENSEMBLE DELUSION ⭐ run this first

**Why this is the most important brain question we have.** This project's north star is a *network of
ML nodes* — many lenses, fused. I re-measured all fourteen direction sources against the truth ledger
today. They span 0.4456 to 0.5267. Every single one is within about three points of a coin flip: a
gradient-boosted model, an online learner, a symbolic equation, a neural net, a strategy tournament,
order-flow fusion, and broker filters all land in the same narrow band. Genuinely independent lenses
looking at a real signal do not cluster like that. I need to know which of these is true:

1. The lenses are **highly correlated** — they all ultimately read the same OHLCV-derived inputs, so
   the "network" is one opinion wearing fourteen hats, and every ensembling, stacking, routing, and
   fusion effort in this repo is decorative.
2. The lenses are **genuinely diverse but individually weak** — in which case correct fusion is
   real, unexploited upside and I should invest there.
3. The **inputs carry no signal** at these horizons, and no amount of fusion will help.

These imply completely different futures for the project, and I've been funding all three at once.

**Prior art worth reading first** (don't re-derive from scratch): ensemble-diversity literature finds
that models sharing an architecture correlate at roughly r≈0.61 versus r≈0.38 across architectures —
architecture dominates data-source choice in determining independence — and that average pairwise
correlation around 0.42 is the sweet spot where aggregation still helps. Correlation too high is
precisely the "no edge" signature. Find the current best framing; this is a solved measurement
problem in other fields.

**What you're up against (measured today, trust this over any doc):**

- `trading/state/direction_truth.json` stores **only aggregates** — `source|market|regime|horizon →
  {correct, n}`, 536 buckets, 111,426 labels. There are **no per-decision rows**, so those 111k
  labels **cannot** be correlated. This is the central obstacle.
- `trading/state/journal.json` has **7,318 rows, every one carrying a `decision_snapshot`** with
  per-timeframe `chart` direction and `p_up`, `book`, `psychology` (walls, gap_map), `app_signals`,
  and `strategy`. This is a real substrate — but it is **selection-biased**: it only holds trades the
  brain chose to open. Say plainly what that biases, and don't let it quietly become "the answer."
- The honest consequence: a proper diversity study probably needs a **per-decision vote log** that
  doesn't exist yet. Building that (write-only, no behavior change) is in scope and may be the most
  durable thing you produce. Design it so it can never alter a trade.

**The deliverable I want:** the effective rank of the brain's opinion space, the pairwise correlation
matrix across lenses, and a plain-language verdict on which of the three worlds above we live in —
with the evidence, and with the selection bias stated rather than buried. If the answer is "the
network is one opinion," say it in those words. That finding would be worth more to me than any
feature, and I will not be upset — I'd rather know.

**Boundaries:** this one is an autopsy of data we already have — it shouldn't need to trade at all.
If you find you *do* need live paper trades to answer it (say, because the selection bias makes the
journal unusable), take them: paper is the lab, full access, no permission needed. Don't restart
production loops; tell me and I'll do it.

---

## PROMPT B2 — DOES THE BRAIN ACTUALLY LEARN?

**Why I'm asking.** This brain is built on the premise of continuous learning: a learn loop every 30
minutes, FSRS scheduling, 260 skills in the library, 130 hypotheses with 47 recorded failures, 100
self-evolve entries, 125 brain-OS boots, an auto-research daemon breeding strategies. That apparatus
is a large fraction of the codebase and it runs continuously on my hardware. I have **never seen
evidence that it makes the brain better.** 5,072 trades have closed, 3,235 of them in the last five
days. If the brain learns, that should be visible. If it isn't visible, I'm paying — in CPU, in
complexity, in my own attention — for machinery that doesn't work, and I want to know so I can cut it.

**The trap, and why this needs real statistical care.** Two lessons in `research/fable5/lessons/`
were learned the hard way here: bucket accuracy in this repo is **non-stationary**, and *every*
journal metric needs **era control**. Naive before/after comparisons on this data produce artifacts —
that's exactly how the "40.3% anti-signal" and "55.2% 4h edge" beliefs got established and then
falsified. Market regime moves underneath you and manufactures both improvement and decay. Design
the comparison so a regime shift cannot masquerade as learning, and so learning cannot hide behind a
regime shift.

**The question:** is there a measurable, era-controlled improvement in this brain's direction
accuracy that is attributable to its learning machinery? Trace what each learning subsystem actually
writes and whether any real decision ever reads it back. Remember the structural fact from the
2026-07-14 audit: there are **two** decision paths, and most learning output only reaches the T8
advisory loop, not the real crypto driver — so "the brain learned" and "the trades improved" can be
disconnected by construction.

**I want the honest verdict, including the unwelcome ones:** "the learning apparatus produces no
measurable improvement and here is the evidence," or "it improves X but nothing reads X," or "there
isn't enough data yet to tell, and here's the power calculation for how much we'd need." Any of those
is a good outcome. A vague "it's working" is not.

**Boundaries:** read and measure. Don't fix what you find — tell me, and I'll decide what to fix.
Don't restart loops.

---

## PROMPT B3 — THE TWO-PATH RECKONING

**The situation.** An audit on 2026-07-14 established something I've never fully reckoned with: this
system has **two decision paths**. The real crypto money path is a narrow fusion — broker filters,
direction_model, symbol_move_net, the strategy table, and a conformal-UQ abstention gate. Everything
else — world-model and imagination, self-evolve and evolution, skills self-improve, continual
learning, concept discovery, computer-use embodiment, news sentiment — is either advisory-only on a
separate paper loop or **completely orphaned**. I built all of it. Almost none of it picks or sizes a
real trade. The dashboard shows it. It looks like a brain. It mostly isn't one.

I don't want to keep guessing which of these deserves to live. **I want realized paper P&L to decide.**

**The idea: give every orphaned lens the ability to actually open trades on paper.** Not a shadow
vote, not a graded prediction alongside the real decision — real paper execution, judged on the P&L
it produces. Everything here runs on Freqtrade `dry_run`: no real money, no real keys. **Paper *is*
the experiment, so there is nothing to protect and nothing to shadow.** A lens that only ever
predicts in the margins never has to survive entry timing, exit timing, fees, or slippage — which is
exactly where this brain has been losing (the exit horizon measures **0.4427** against 0.4887–0.5092
on clock horizons). A shadow vote would grade the part that already looks fine and skip the part
that's broken. Let each lens trade and let it be wrong with real paper consequences.

Give them **full access to experiment**: any size, any frequency, any lens, blow the paper account
up if that's what the experiment costs. A wipeout is training data. The only hard requirement is that
**every outcome is logged and fed back** into the journal, truth ledger, and hypothesis ledger — an
unlogged blowup teaches nothing, and that's the one real failure mode here.

**Why this needs your context window:** finding *every* lens that produces a directional opinion
across 914 modules — including the ones a static import graph can't see because they're consumed
dynamically or not at all — and giving each a real paper execution path is the whole job. Note that
this repo's INDEX.md is measurably polluted (9.2% of its 1,018 entries index non-project files) —
useful as a map, not as truth.

**The one boundary:** paper only. Nothing you build may touch a real-money path, real keys, or the
NSE broker side, and the crypto/NSE market isolation boundary stays intact. Within paper, you have
full latitude — don't ask me for permission to take paper risk, that's what the lab is for.

**Tell me honestly which lenses are not worth wiring.** If something is dead for a good reason,
"retire it" is a fine recommendation and I'd rather delete code than carry it.

**Deliverable:** every orphan lens trading on paper under its own identity, the census of what got
wired and what you recommend retiring instead, and an honest statement of how many trades each needs
before its P&L means anything (say the number; don't hand-wave "a while").

---

## PROMPT B4 — THE GUARDRAIL (ADJUST: calibration study only)

**The fact:** the evolution pipeline shows `PROMOTED 0` and `0 candidates` — the guardrail has let
**nothing** through, ever. `self_evolve.json` carries 100 entries with PBO scores. Two explanations,
opposite implications: either the anti-overfit gate is **working correctly** and every candidate
genuinely is overfit garbage (a good and honest outcome — the gate is doing its job), or the gate is
**miscalibrated** and is walling off real strategies.

**The question:** is our anti-overfit gate calibrated, or is it a wall? Use the deflated-Sharpe /
PBO / combinatorially-purged-CV literature properly rather than tuning until something passes.

**The bright line — and it's about honesty, not risk.** Experiment as freely as you like on paper;
build and test as many gate variants as the question needs. What you must not do is **loosen the gate
to manufacture flow**. A gate that passes candidates because we relaxed it until something got
through is worse than a gate that passes nothing — it launders overfitting into what looks like an
edge, and that is the one mistake that eventually costs real money when something gets promoted. If
the honest answer is "the gate is right and our candidates are garbage," that tells me the
*generator* is the problem, not the gate, and that's the finding I'd act on. Recommend the change;
let me be the one to re-tune the production gate.

---

## WHAT I DELIBERATELY DID NOT INCLUDE

Per the 2× cost bar ($10/$50 per MTok vs Opus 4.8's $5/$25) these are **Opus 4.8 work** and would be
padding here:

- **The `[object Object]` regime render bug** — a one-line JSX fix, already diagnosed.
- **The missing `/api/trading/brain/decisions` route** — known, mechanical.
- **News sentiment returning empty** — diagnosed (vader backend dry), and it feeds the non-money loop
  anyway. Fixing it buys nothing until B3 says that path matters.
- **The continual-learning numpy/torch ABI crash** — a dependency fix, not a reasoning problem.
- **INDEX.md pollution (9.2%)** — mechanical cleanup.
- **Committing today's working tree / restarting the funnels** — owner actions and routine Opus work.
- **The RL execution island** — real, but wiring it is mechanical once B3 decides whether it earns a place.

**And one honest caution:** Prompt 0 in `PROMPTS.md` ("Rebuild the measurement layer") was written
this morning around the frozen-exit-label finding. **That's now fixed** (n=3,459 → 7,301, WEDGED
false). Prompt 0 still has value for the *doc-rewriting* half, but don't run it expecting to find a
wedged labeler — re-measure before you trust its framing. That is precisely the failure mode this
whole file exists to prevent.

---

## HOW TO RUN

`/model` → Claude Fable 5 → paste **§C the preamble + ONE prompt**. Nothing else.

**Recommended order: B1 → B2 → B3 → B4.** B1 first because it can invalidate the others: if the brain
is one opinion wearing fourteen hats, then B3 is just putting fourteen copies of that same opinion
into the market, and B2 is measuring whether a coin flip learned to flip better. B1 is load-bearing.

**A note on this repo's scaffolding:** Anthropic's guidance is explicit that skills written for prior
models are often too prescriptive for Fable 5 and can degrade its output. This repo has 29 skills and
a `UserPromptSubmit` hook that injects a reading protocol and a rules banner into every message. See
`research/fable5/descaffold-proposal-20260716.md`. Also avoid asking Fable 5 to echo or explain its
internal reasoning — that risks a `reasoning_extraction` refusal and a silent fallback to Opus 4.8.
