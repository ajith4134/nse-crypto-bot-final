# FABLE-5 IDEAS + READY-TO-PASTE PROMPTS

> **How to use.** Open a NEW Claude Code session → `/model` → **Claude Fable 5** → paste the
> **Preamble** (§0) then ONE prompt below. One prompt per session — these are long-horizon runs.
>
> **The bar.** Every idea here is something **Opus 4.8 genuinely cannot do as well** — it needs
> Fable 5's long-horizon autonomy, 1M-context whole-repo reasoning, dense/degraded-image vision,
> sustained parallel subagents, or first-shot correctness on a well-specified system. Fable 5 costs
> **2× Opus 4.8** ($10/$50 vs $5/$25 per MTok) and its turns run for many minutes. If Opus 4.8 could
> do it, it is not on this list.
>
> **Money-lens: mode = PAPER.** The question for every item is *"does this teach us the most about a
> real edge?"* Verdicts below are per-idea.
>
> **Grounding:** all seven target a problem measured in `BRIEF.md` §4 — not invented here.

---

## §0 — THE PREAMBLE (paste FIRST, every session)

```text
Read research/fable5/BRIEF.md first — it is your grounding for this repo. Then read INDEX.md for
the code map. Never load the whole repo.

Why I'm asking: I'm a non-coder. I direct this system entirely through prompts, and I need it to
earn a consistent, risk-managed income. Everything runs in PAPER mode, where unlimited risk is
allowed because blowups are training data. Honesty about what does and does not work matters far
more to me than reassurance. Plain language, please — I won't follow jargon.

Ground truth you must respect:
- Direction accuracy is measured at ~40-52%. The bottleneck is measured to be decision-time INPUTS,
  not models (LightGBM AUC 0.477, TabPFN 0.523 — at or below chance). Do not hand me another model
  as the answer unless you can show the inputs justify it.
- Honest wiring only: never fabricate a node, edge, metric, or result. A true-but-ugly result beats
  a pretty-but-false one, always.
- GPU-only is the ONLY valid reason to skip something. Missing data → download it.
- Reuse real OSS first — but that is a default, not a cap. If something far better exists, use it
  and tell me why.
- Never cost me money if a free path exists. Never hand me a "pay/top-up" action item.

Before reporting progress, audit each claim against a tool result from this session. Only report
work you can point to evidence for; if something is not yet verified, say so explicitly. Report
outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when
something is done and verified, state it plainly without hedging.

When you have enough information to act, act. Do not re-derive facts already established, or
narrate options you will not pursue. If you are weighing a choice, give a recommendation, not an
exhaustive survey.

Don't add features, refactor, or introduce abstractions beyond what the task requires. Don't design
for hypothetical future requirements.

Pause for me only when the work genuinely requires it: a destructive or irreversible action, a real
scope change, or input only I can provide. If you hit one of these, ask and end the turn, rather
than ending on a promise.

Establish a method for checking your own work as you build, and run it at intervals — verify with
fresh-context subagents against the specification, not self-critique.

Store what you learn: one lesson per file under research/fable5/lessons/, one-line summary at the
top. Record corrections and confirmed approaches alike, including why they mattered. Update an
existing note rather than duplicating; delete notes that turn out to be wrong.

Write your final summary for someone who did not watch you work: outcome first, complete sentences,
terms spelled out, no arrow chains or invented shorthand.
```

> ⚠️ **Subagents:** the owner's standing rule is `one-agent-at-a-time` (strictly sequential). Fable 5
> is *much* better at parallel subagents than prior models, and several prompts below would benefit.
> **The prompts ASK the owner before fanning out.** Do not silently override the rule.

---

## THE RANKED IDEAS

| # | Idea | Why only Fable 5 | Money-lens (PAPER) | Est. session |
|---|---|---|---|---|
| **0** | **⭐ REBUILD THE MEASUREMENT LAYER** — exit labels frozen, 4h edge gone, inversion falsified. Several plans rest on false numbers. | Multi-hour: re-derive every conclusion across 98k labels + rewrite the planning docs it invalidates. Needs sustained autonomy + whole-history reasoning. | **PROCEED — do this FIRST** | 3–6 h |
| 1 | **The Input Hunt** — exhaustive search for inputs that actually carry signal (esp. true L2 OFI/GOFI, which we never compute) | Long-horizon autonomy: hours of continuous search/evolve/measure | **PROCEED** — highest information gain, *after* #0 | 4–8 h |
| 2 | **Selection & Timing Autopsy** — the 8.5-pt gap between 48.8% predicted and 40.3% realized | Ambiguous, multi-threaded, needs whole-history search | **PROCEED** — direct P&L | 2–4 h |
| 3 | **Chart-Vision Teacher** — Fable 5 labels a golden chart set → distil into local qwen2.5-vl | Fable 5's dense/degraded-image vision is its standout edge; Opus 4.8 is materially weaker | **PROCEED** — one-time cost, improves inputs, keeps prod free | 3–6 h |
| 4 | **Whole-Repo Truth Audit** — the money path in one 1M context | Needs 1M context + best-in-class code review/history search | **ADJUST** — scope to the money path | 3–5 h |
| 5 | **Wake the Sleeping Brain** — genius-use 5.7%; two decision paths | Ambiguity + whole-system reasoning | **PROCEED** — but measure the denominator first | 2–4 h |
| 6 | **De-scaffold for Fable 5** — this repo's 29 skills degrade Fable 5 (Anthropic's explicit warning) | Only Fable 5 can judge what Fable 5 doesn't need | **ADJUST** — cheap, one-off | 1–2 h |
| 7 | **The Equation Quest, finished** — run the re-evolution daemon for real | Multi-hour evolutionary search + honest OOS gating | **PROCEED** — owner's explicit active quest | 4–8 h |

> **Recommended order: 6 → 0 → 1 → 2.**
> **#6 first** (cheap; makes every later session better).
> **Then #0 — non-negotiable.** Until the measurement layer is honest, #1/#2/#7 would be optimising
> against numbers that are provably wrong. Three prior sessions built plans on a 4h edge that no
> longer exists.

---

## PROMPT 0 — REBUILD THE MEASUREMENT LAYER ⭐⭐ DO THIS FIRST

**Why this is now #1:** on 2026-07-16 three load-bearing project beliefs were re-measured against the
live ledger and **falsified**. Several planning documents are built on numbers that are provably wrong.
Optimising anything before fixing this is optimising against fiction.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: my measurement layer is lying to me, and I've been making plans on top of it. Fix it, then
re-derive every conclusion that depended on it.

Three things I believed, that were re-checked against the live ledger
(trading/state/direction_truth.json, 486 buckets, 98,528 labels) on 2026-07-16 and found FALSE.
Verify each one yourself before acting on it — don't take my word, and don't take the docs' word:

1. THE 4h EDGE IS GONE. research/direction-accuracy-diagnosis-2026-07-11.md:9 claims 4h = 55.2%
   (n=2,858) is a "GENUINE EDGE", and the whole plan says "bias to the 4h/1h horizon where edge is
   real." Live now: 4h = 0.502 on n=18,543. A coin-flip. Every plan resting on that is resting on
   nothing.

2. THE EXIT LABELS ARE FROZEN. The `exit` horizon has n=3,459 today, and it had n=3,459 five days
   ago — while 3,108 trades closed in between. Root cause: exit labels are only written by
   backfill_journal() (trading/direction/truth_ledger.py:434), documented as a "one-shot idempotent
   label pass" — and it has NO production caller. Only tests/test_truth_ledger.py:144,152 ever call
   it. So the single worst horizon (36.5%) — the one every doc blames for destroying good calls — is
   measured from stale data and is not being tracked at all.

3. INVERSION DOESN'T WORK. mirror_gate.py:5 asserts "a 30%-accurate source inverted is a
   70%-accurate source." Live: meanrev_stochrsi raw = 0.310 (n=113, 15m); mirror:meanrev_stochrsi =
   0.362 (n=58, 15m). Inverting a 31% signal should give ~69%. Both directions lose. The gate code
   looks correct, so this is empirical. The tie-rate explanation was tested and falsified (0.86%
   ties). But the buckets are NOT paired samples (113 vs 58, "any" vs "chop") — so the honest state
   is "unexplained".

What I want:
1. Fix the exit-label wedge. Give backfill_journal a real production caller (or replace it with
   continuous labelling), backfill the 5 days of missing exits, and make sure the exit horizon
   tracks live from here on. This is probably the single highest-value hour in the project: we are
   blind on the horizon we claim is killing us.
2. Run a CONTROLLED PAIRED experiment on the Mirror Gate. Same samples, same regime, same horizon,
   raw vs inverted. Settle it. If inversion genuinely doesn't recover accuracy, the D2 Mirror Gate
   and every plan that assumes "free accuracy from inversion" need to be retired or rewritten — tell
   me straight, even though I approved that whole program.
3. Re-derive the direction story from the 98k-row ledger. My docs say direction is a "systematic
   ANTI-signal exploitable by inversion" (ideas-ledger.md:224). But raw predictors are 48.8% —
   coin-flips, not anti-signals — while realized closed trades are 40.3%. If that's right, the 8.5
   point gap is trade SELECTION and TIMING and the EXIT PATH, not a sign error, and we've been
   chasing the wrong fix for weeks. Confirm or refute that with data.
4. Then rewrite the docs the truth invalidates. research/direction-accuracy-diagnosis-2026-07-11.md,
   research/direction-equation-quest/SYNTHESIS-AND-PLAN.md, and the ideas ledger all contain claims
   that are now false. Correct them in place, dated, with the evidence. I can't audit my own docs —
   stale numbers in them cost me weeks.

Be blunt. I would rather find out that a program I approved was built on a bad premise than keep
building on it. A rigorous negative result here is worth more to me than any feature.

PAPER mode. Verify with fresh-context subagents against the ledger itself, not against the docs.
```

---

## PROMPT 1 — THE INPUT HUNT ⭐ highest value (run AFTER #0)

**Problem (measured):** every direction model lands at AUC 0.477–0.582. LightGBM 0.477 (*below
chance*), TabPFN 0.523, live `direction_meta.pkl` **0.487**, `direction_model` 0.582. Multiple
sessions concluded the same thing: **the inputs are the ceiling, not the models** — and stopped there.
**And there is a concrete, named gap:** the research's own **#1 and #2 ranked drivers — true L2-book
OFI / GOFI — are not computed at all.** Only OHLCV proxies exist.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: find inputs that actually predict direction. This has defeated several previous sessions,
each of which correctly concluded "the inputs are the ceiling, not the model" — and then stopped
there. I want you to keep going. Take hours. This is a long-horizon run.

Run this only after the measurement layer is fixed (see PROMPT 0) — otherwise you'll be scoring
against broken labels.

The measured ground truth (verify it, don't assume it — BRIEF.md §3):
- Direction is 0.488 over 98,528 live truth-ledger labels: a coin-flip at every horizon
  (15m 0.488 / 1h 0.493 / 4h 0.502). The "4h edge" in the older docs is GONE.
- LightGBM AUC 0.477, TabPFN 0.523, direction_meta.pkl 0.487, direction_model 0.582.
- Best broad source: direction_equation 0.530 (n=4,107); best sub-bucket trend|4h 0.573 (n=436).

The single most concrete lead — start here:
  research/direction-equation-quest/COVERAGE-AUDIT.md:58-64 says our own research ranked true L2-book
  ORDER FLOW IMBALANCE (OFI) and GOFI as the #1 and #2 price drivers — and we DO NOT COMPUTE THEM.
  We only have OHLCV-derived proxies (buy_press, cvd, tick_ofi). There is no stored per-bar
  historical order-flow series. That is a named, ranked, uncollected input. Go get it.

What I want:
1. Confirm or refute "the inputs are the ceiling" with your own measurement. If the diagnosis is
   wrong, tell me — that's a valuable result.
2. Audit our capture coverage against the COMPLETE set of price-driving forces the owner asked for
   (research/direction-equation-quest/REQUIREMENTS.md): order flow, positioning, liquidity,
   funding/basis, on-chain, macro, sentiment, microstructure. Be honest about what's missing.
3. Go get the missing ones — starting with true L2 OFI/GOFI. Never-skip: missing data means collect
   it, not skip it. THE MOTTO says market data comes from navigating the Binance/Upstox web apps
   (their own order book, filters, screeners, funding, OI, long/short, taker ratio, liquidations) —
   not from data APIs. Free paths only. This needs a STORED per-bar series, so design the capture +
   persistence, then let it accumulate.
4. Search the space properly. gplearn, Operon, PySR, DEAP and trading/strategy/direction_equation.py
   are already wired — use them. Try COMBINATIONS and transformations, not just raw features:
   interactions, lags, cross-venue spreads, regime-conditional forms.
5. Measure out-of-sample on the Truth Ledger with purged CPCV. Report Rank-IC by horizon. An
   in-sample win is worthless to me and I cannot tell the difference — so the rigor has to be yours.
6. The honest deliverable: either a named input set that measurably lifts direction AUC above 0.60
   out-of-sample, OR a rigorous negative result naming which inputs are exhausted and what
   information we'd need that we can't currently get. Both are wins. A fabricated improvement is the
   only failure.

PAPER mode; unlimited risk allowed; nothing touches real money. CPU-first. Log every experiment.

Work autonomously — I'm not watching. Verify with fresh-context subagents against the measurement
spec. Ask me before running several subagents in parallel; my standing rule is one-at-a-time.
```

---

## PROMPT 2 — SELECTION & TIMING AUTOPSY (the 8.5-point gap)

**Reframed 2026-07-16.** The old framing ("entries are 54–69% right, the exit destroys them") rests on
the **4h edge that no longer exists**. The *real* measured gap is different and more interesting:

> **Predictors: 48.8%** (98,528 labels, coin-flip). **Realized closed trades: 40.3%** (1,665 trades).
> **The 8.5-point gap is where the money goes** — and it is selection + entry timing + exit, not sign.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: find out where 8.5 percentage points disappear between what we predict and what we get.

The measured fact (verify it yourself — BRIEF.md §3 F4):
- Our raw direction predictors score 0.488 across 98,528 truth-ledger labels. Coin-flip.
- The trades we ACTUALLY TOOK came in at 40.3% (1,665 closed trades, entry->exit sign).
So we perform ~8.5 points WORSE on the trades we chose than on our predictions in general. We are
somehow selecting the trades we're worst at. That's the opposite of what selection should do.

Note: the older docs blame "the exit path destroys good calls" and cite entries being 54-69% right at
1h/4h. That was based on a 4h edge that has since regressed to 0.502 — a coin-flip. Don't inherit
that framing. Re-derive it.

What I want:
1. Decompose the 8.5 points honestly. How much is (a) SELECTION — we pick symbols/setups we're worse
   at; (b) ENTRY TIMING — the call was right but we entered at a bad price; (c) EXIT — we held past
   the window? Give me the split with numbers, from the journal + truth ledger. This is the core
   question and nobody has answered it.
2. For selection specifically: is there an adverse-selection mechanism? Do we systematically enter
   the candidates where our own confidence is miscalibrated? The conf~=1.0 bucket was measured at
   29% — confidence appears INVERTED. Check whether that still holds on live data.
3. Profit-tailgate only arms at +0.5%, so underwater trades have no directional stop at all. Quantify
   what that costs.
4. dir_exit.py is stuck in SHADOW because every lane has n<30 so cal_strength=0.0 and it never cuts.
   Decide honestly: is the gate too conservative, or do we genuinely lack evidence? If we lack it,
   design the cheapest way to accrue it in paper. (Note: the exit labels themselves were frozen —
   PROMPT 0 fixes that. Coordinate.)
5. Search the git history — 288 commits. Previous sessions touched the exit path repeatedly (commits
   76e7d50, a8f715e are named in my memories). Find what was tried and why it didn't take. Don't
   repeat a failed fix.
6. Then fix the biggest contributor. Attribution-only by default (record + grade, no trade change),
   any real behavior change behind an env flag defaulting OFF — that's this project's pattern for
   live-path changes in paper.

Deliverable: a numeric decomposition of the 8.5 points, and a wired, tested, flag-gated fix for the
largest term. Show me before/after on real closed trades.

Work autonomously; verify with fresh-context subagents against the real journal data, not against
your own reasoning.
```

---

## PROMPT 3 — CHART-VISION TEACHER

**Why only Fable 5:** its standout capability is *"interprets dense technical images, web applications,
and detailed screenshots with substantially higher accuracy… trained to use bash and crop tools to
handle flipped, blurry, or noisy images."* This project's entire data path is **screenshots of trading
charts** read by a local 7B model (`qwen2.5-vl` via Ollama). Fable 5 is a dramatically better chart
reader than qwen2.5-vl — but must NOT become the production reader (that would cost money forever and
break `zero-cost-first` + `local-vision-permanent`).

**The move: Fable 5 as a one-time TEACHER, not a runtime dependency.**

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: make our local chart-reading eyes measurably better, using yourself as a one-time teacher
rather than a permanent dependency.

Context: per THE MOTTO (BRIEF.md §1), all our market data comes from navigating the Binance and
Upstox web apps and READING THE CHARTS AS SCREENSHOTS with a free local vision model (qwen2.5-vl via
Ollama). That local model must stay the production reader — it is free and unthrottled, and paying
per-chart forever would violate the owner's zero-cost rule. You are much better at reading dense,
noisy chart images than qwen2.5-vl is. So be its teacher, not its replacement.

What I want:
1. Find the vision lane. Read trading/broker_sense/ (indicator_fusion vision lens), the 3-lane vision
   cascade (CNN/VLM/YOLO), research/local-vision-vlm.md, research/chart-image-models.md, and
   research/video/*/frames/ (there are many captured frames already on disk).
2. Measure how good the local eyes actually are right now. Build an honest scored benchmark: take
   real captured chart screenshots, and compare what qwen2.5-vl reports against ground truth derived
   from the feather candle data we already have (price levels, trend direction, indicator states,
   candle patterns). Give me a hit-rate. I suspect nobody has ever measured this.
3. Where the local model is wrong, diagnose why — resolution, cropping, prompt, the ask being too
   broad, missing chart context.
4. Then teach it. Read the charts yourself (use your crop/bash image tooling on the noisy ones),
   produce a golden labeled set, and use it to improve the local lane: better prompts, better
   crops/pre-processing, a distilled/fine-tuned local head, or a cheap CNN trained on your labels —
   whichever the measurement says wins. Reuse-first: vendor/candlestick_cnn and vendor/ChartScanAI
   already exist.
5. Re-run the benchmark and show me the honest before/after. If your teaching does not measurably
   improve the local reader, say so plainly — that is a real result.

Hard constraint: the production path must remain free and local. You are allowed to be the teacher
once; you may not be the runtime.

Work autonomously. This is a long run. Verify with fresh-context subagents against the candle ground
truth, not against your own reading of the image.
```

---

## PROMPT 4 — WHOLE-REPO TRUTH AUDIT

**Why only Fable 5:** 248,951 lines / 1,063 modules / 39 vendored forks. Fable 5 has a 1M context,
higher bug-finding recall than Opus 4.8, and searches *repository history*. The `/independent-audit`
skill exists but runs a static import graph — it cannot reason about semantic dead-ends
(a lane that is wired but always returns `None`, like the `direction_model` dead-pipe bug found on
2026-07-13 where it trained on `f_*` and served `m_*`).

**Money-lens: ADJUST** — an audit doesn't earn. Scope it to the money path first.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: tell me the truth about what in this system is actually connected and actually running —
specifically on the path that decides and places trades.

Scope (keep to this — I don't want a 1,063-module essay): the money path only.
  perception (trading/broker_sense/) -> direction (trading/direction/) ->
  fusion (trading/brain/indicator_fusion.py) -> executor (brain_executor) -> execution -> learning
  (truth_ledger, freqtrade_ingest, journal, learn_loop).

Previous audits found real dead pipes that a static import graph cannot see. The best example:
direction_model was trained on f_* features but served m_* features, so predict() always returned
None — it was fully "wired" and completely dead for weeks. I want you to find every bug of that
shape.

What I want:
1. Trace the money path as live water, not as an import graph. For each hop: what goes in, what
   comes out, and — the key question — does anything downstream actually CONSUME it, or does it
   silently no-op / return None / get overwritten?
2. Use the git history. 288 commits. Find features that were shipped and then quietly stopped being
   called. Find fixes that were reverted or superseded. The memories in
   .claude/projects/-home-karan18190164/memory/ record what previous sessions believed they shipped
   — cross-check those claims against the code that exists today. Where a memory claims something is
   live and it is not, that is exactly what I want to know.
3. Check the flags. Many things default OFF or SHADOW (DIR_EXIT=shadow, INSTRUCTION_APPLY_TILT=0,
   CORTEX_SIGNAL=1 shadow, UI_ONLY_DATA). Tell me which capabilities I believe I have that are
   actually inert, and what it would take to turn each on safely.
4. Verify, don't assume. Run things. Hit the endpoints. Read the state files. My standing rule is
   that no report is true until checked first-hand — that applies to you and to your subagents.

Deliverable: a ranked, evidence-cited list of what is dead, what is inert, and what is lying to me —
each with file:line and the one-line fix. Write it to research/audits/. Report-only: do not fix
anything in this session unless it is a one-line honesty bug and you tell me.

Work autonomously; verify with fresh-context subagents.
```

---

## PROMPT 5 — WAKE THE SLEEPING BRAIN

**Problem (measured):** **genius-use ≈ 5.7% — only ~383 of 6,741 neurons have EVER been consulted in
a decision.** The brain has built a 7,166-neuron memory web, an instruction lifecycle, a school that
reached L5, and evolution operators — and then routes decisions around almost all of it.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: the brain has 6,741 neurons of knowledge and uses 383 of them. Fix that.

The measured fact (research/brain-ultra-upgrade/AUDIT-20260713.md): genius-use is 5.7%. Only
~383 of 6,741 neurons have ever been consulted in a decision. We built a memory web, an instruction
lifecycle, a school that reached level L5, and evolutionary operators — and the trade decisions route
around nearly all of it. That is the gap between "a brain that knows things" and "a brain that uses
what it knows", and it is the heart of the active north-star goal (research/brain-ultra-upgrade/
GOAL.md, requirements R1-R28, none may be dropped).

What I want:
1. Find out WHY coverage is 5.7%. Read trading/brain/consult.py, brain_os.py (the syscall surface),
   apply.py, and the four consult seams (indicator_fusion.fuse, nav_brain.navigate,
   researcher.research, freqtrade_ingest). Is it k too low? Bad retrieval? Neurons that are
   unretrievable because of how they were converted? Neurons that are simply irrelevant to any
   decision? Measure it — don't theorise.
2. Be honest about the denominator. If 6,000 of those neurons are news snippets that SHOULD never be
   consulted for a trade decision, then 5.7% is not a bug and the metric is lying. Tell me that if
   it's true. I would rather have a real 40% on a meaningful denominator than a fake 90%.
3. Fix what is genuinely broken. The audit suggests: higher k, more consult kinds, a cold-neuron
   sweeper that surfaces relevant-but-never-used neurons, and seeding the instruction library from
   the 239-strategy library + research docs (induction is new, so the library is tiny).
4. Prove it changed something real. Coverage going up is not the win — the win is a decision that is
   BETTER because it consulted the right neuron. Measure the win-rate of the consulted cohort vs
   baseline. If consulting more neurons doesn't improve decisions, that is a crucial finding: say so.

Related open requirements you may close if the evidence supports it: R6 (no invention neuron has
passed the CPCV+DSR gate), R27 (no graded knowledge-application exam — "given a situation, did the
brain pick the BEST neuron?").

PAPER mode. Attribution-first: record and grade by default, behavior changes behind flags.

Work autonomously; verify with fresh-context subagents.
```

---

## PROMPT 6 — DE-SCAFFOLD FOR FABLE 5 ⭐ do this first

**Why:** Anthropic's guidance is explicit — *"Skills developed for prior models are often too
prescriptive for Claude Fable 5 and can degrade output quality."* This repo has **29 skills, a
forced prompt-rating protocol, a mandatory rules banner on every reply, and a
`reasoning_extraction` refusal risk from show-your-thinking instructions.** Every other prompt on
this list runs better after this one.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: this repo's own scaffolding was written for older Claude models and may now be making you
worse. Audit it and fix it — you are the only one who can judge this.

Anthropic's own guidance for you says: "Skills developed for prior models are often too prescriptive
for Claude Fable 5 and can degrade output quality. Review and consider removing older instructions if
default performance is better." It also warns that instructions telling a model to echo or explain
its internal reasoning can trigger a reasoning_extraction refusal.

This repo has: 29 custom skills in .claude/skills/, a UserPromptSubmit hook that forces a
prompt-rating protocol and a rules banner on every reply, per-skill LEARNINGS.md files, and a
Stream-of-Mind feature built around surfacing reasoning.

What I want:
1. Read all 29 skills and the hooks in .claude/settings.json. For each, judge honestly: does this
   help you, or is it prescribing steps you'd do better without? Be specific about which
   instructions are load-bearing (the owner's real rules: honest-wiring, never-skip, zero-cost,
   verify-first, paper-first, secrets-safe) versus which are scaffolding for a weaker model.
2. Find any instruction that asks a model to reproduce, transcribe, or explain its internal
   reasoning as response text. Those risk refusals on you. Flag them and propose the fix (read
   structured thinking blocks instead).
3. Tell me honestly whether the prompt-rating protocol and the mandatory rules banner help or hurt
   you. I added them to stop older models from misreading me and drifting. If you don't need them,
   say so — I'd rather have your best work than my old guardrails.
4. Propose (do not yet apply) a Fable-5 profile: which skills to thin, which instructions to cut,
   which to keep verbatim because they encode MY intent rather than model scaffolding. The
   distinction that matters: never cut a rule because it constrains you — only cut it if it makes
   your output worse without protecting anything I care about.
5. Check whether the one-agent-at-a-time rule still makes sense for you. I made that rule because
   parallel agents kept getting lost when sessions died, and they burned my budget. You're supposedly
   much better at sustaining parallel subagents. Give me a recommendation, with the risk stated.

This is propose-then-approve. Show me the diff you'd make and why; change nothing until I say yes.

The deliverable I care most about: an honest answer to "what in my own setup is making you dumber?"
```

---

## PROMPT 7 — THE EQUATION QUEST, FINISHED

**Owner's explicit active quest** (`research/direction-equation-quest/REQUIREMENTS.md`). P1→P4 are
built. The named NEXT step was never done: *"run the re-evolution daemon on real data; let the ledger
accumulate live accuracy before raising the ±0.15 weight; optional AI-Feynman/SINDy generators."*
That is a multi-hour evolutionary search — exactly a Fable 5 run.

```text
[PASTE THE §0 PREAMBLE FIRST]

Your task: finish the direction-equation quest. Read research/direction-equation-quest/
REQUIREMENTS.md FIRST — I explicitly asked that its meaning never be lost or narrowed, so treat
every one of the 8 extracted asks as binding.

What exists: the full P1->P4 chain is built (commits 750bb82, 6058d1a, b355cf5).
  P1 feature bus -> indicator_fusion.fuse()
  P2 trading/strategy/direction_equation.py — discover() fans the bus through gplearn + Operon +
     PySR, scores on an OOS split by horizon-conditioned Rank-IC, keeps top-K + best-horizon +
     invert flag
  P3 validate() — purged CPCV robustness, triple-barrier win-rate, selection PBO
  P4 direction_equation_deploy.py — live IC-weighted invert-aware ensemble -> Truth Ledger, Mirror
     Gate self-inversion, bounded +/-0.15 fusion tilt, reevolve_all() daemon

What was never done — the named next step: run the re-evolution daemon on REAL data, let the ledger
accumulate live accuracy, and only then consider raising the +/-0.15 weight. Plus the optional
AI-Feynman and SINDy generators that were listed and skipped.

What I want:
1. Actually run it. Long, real, on real data. This is the multi-hour evolutionary search the quest
   was designed for and nobody has ever let it run properly.
2. Honor requirement 4 — "try ALL possible combinations/theories/equations". Not one hand-picked
   model. Add the generators that were deferred (AI-Feynman, SINDy) — never-skip applies; if they
   need installing, tell me the command.
3. Honor requirement 5 and 6 — pull in ALL related projects even remotely related, and ADD our
   existing built features to the pool. We have 39 vendored OSS projects; use them.
4. Honor requirement 7 — mutate and evolve, keep the best, self-improving.
5. Measure OUT-OF-SAMPLE on the Truth Ledger only. Requirement: "reliable" means measured OOS,
   robust across regimes and horizons — not an in-sample number. I cannot check your work, so the
   rigor has to be yours.
6. Tell me honestly whether the discovered equation beats coin-flip out-of-sample. If it does not
   after a real search, that is a legitimate and important answer — it tells us the information isn't
   in the inputs we have, which points straight at Prompt 1 (the Input Hunt).

Do not raise the +/-0.15 fusion weight until the ledger shows real accumulated accuracy. That gate
exists to stop me fooling myself.

PAPER mode; unlimited risk allowed; nothing touches real money.

Work autonomously — this is a long run. Verify with fresh-context subagents against the OOS spec.
```

---

## WHAT I DELIBERATELY DID NOT INCLUDE

Honesty about the boundary — these were considered and cut because **Opus 4.8 does them just as well**,
and paying 2× for them would be waste:

- **Motto migration (Freqtrade/funnel API→web).** Real owner rule, real open gap — but it's mechanical
  surgery on a known target. Opus 4.8 territory.
- **The 8 loop-fragility bugs** (loop_keeper flapping, `build_demo_evolution` GIL wedge, serial warmer,
  the misleading `predict` error). Well-diagnosed already; these are ordinary fixes.
- **Dashboard work / new panels.** `/add-panel` + Opus 4.8.
- **Anything cyber-adjacent framed carelessly** — see BRIEF.md §7.3. Fable 5's classifiers may refuse
  browser-automation work if it reads as scraping-evasion. Frame it as *your own authenticated account,
  your own browser, data you're entitled to* — which is the truth.

---

_Regenerate this file from live repo state with `/fable5-prompts`._
