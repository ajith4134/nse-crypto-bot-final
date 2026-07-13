# 🧠 BRAIN ULTRA UPGRADE — the 10-star goal

**Status:** THE NEW ACTIVE NORTH-STAR GOAL (owner, 2026-07-12 — "this is the new goal"; registered in the /goal skill and memory index; the human-trading-system goal continues as this goal's trading-domain track) · **Source of truth:** [OWNER_MESSAGE_VERBATIM.md](OWNER_MESSAGE_VERBATIM.md) — every requirement **R1–R28** there must stay traceable here. Nothing may be dropped. *(R21–R28 recovered in the owner's cross-check of 2026-07-12 — first pass missed them.)*

---

## North star (one paragraph)

Turn the brain from a pile of disconnected features into **one continuously-flowing intelligence** that is *taught* — the way a teacher takes a student from kindergarten basics to PhD — through a staged curriculum with real exams, until it can **learn on its own**: research any topic on the web, study it, store everything it knows in **one common neuron format**, convert knowledge into **instructions it can follow, edit, and mutate** (keeping the mutations that work), evaluate itself honestly, and invent new things. By graduation it is an expert at **trading**, at **navigating the Binance web app**, at **navigating the Upstox web app**, and at **searching the web for anything it needs and turning what it finds into executable instructions** — an ultra-advanced self-evaluating, self-improving AI grounded in the best published architectures.

**Motto compliance:** CPU = the brain's full intelligence (all of this runs locally) · APIs = execution only · data = web navigation only · charts read by local vision · maximize browser surface · RAM for speed.

---

## Pillar 1 — ONE common language: the Neuron format (R15, R16)

Every kind of brain data — strategies, research, books studied, news read, findings, inventions, knowledge, memories, episodes, exam results, lessons — becomes the **same atomic unit: a Neuron**, connected in one graph (the "web of neurons").

**The common language is INSTRUCTION-SHAPED (owner's design, R24: "my thinking is instructes").** Knowledge that can't be acted on is dead weight. So EVERY neuron — not just `kind: instruction` — carries a mandatory **`action` facet**: *how to USE this knowledge* (when it applies, what to do with it, how to verify it helped). A book chapter's neuron ends in "apply this by…"; a news neuron ends in "this changes decisions by…"; a finding's neuron ends in "exploit this by…". The web of neurons is therefore simultaneously a knowledge graph AND an executable instruction library.

```yaml
# neuron = one atomic unit, one file + one DB row + one graph node
id: n-<ulid>
kind: fact | concept | instruction | skill | strategy | finding |
      invention | episode | source | news | book-chapter | exam | lesson
title: one-line essence
level: L0..L6            # curriculum level where it belongs
body: |                   # markdown; for instructions: numbered steps +
                          # preconditions + expected outcome + how-to-verify
action: |                 # MANDATORY on every kind (R24): how to USE this
                          # knowledge — when it applies, what to do, how to
                          # verify it helped. The instruction-shaped language.
links:                    # typed edges — the web of neurons
  - {to: n-…, rel: supports|contradicts|uses|derived-from|mutated-from|taught-by|tested-by}
provenance: {origin: url|book|trade|experiment|lesson, ref: …, when: …}
confidence: 0.0–1.0       # brain's own belief, updated by outcomes
stats: {times_used, wins, losses, pnl_attributed, last_used}
exam: {last_score, last_tested}
version: 3                # instructions carry mutation lineage
parents: [n-…]            # GEPA-style genetic tree for mutated instructions
```

- **Storage:** markdown file in `brain_memory/neurons/` (human-auditable) mirrored to SQLite (FTS5 search — already built) + the existing memory graph (HippoRAG PPR retrieval — already built). RAM-cached for speed.
- **Auto-linking:** A-MEM style — every new neuron generates its own context and links itself to related neurons without predefined rules; old neurons *evolve* their content when new ones arrive.
- **Migration:** every existing store (strategy library, research/, FinMem episodes, decision memory, trade journal, skill LEARNINGS, boss orders, xray snapshots, book/news ingests) gets a converter → neurons. Old stores keep working; neurons become the shared read layer. **No feature's data is left outside the web.**

## Pillar 2 — Continuous flow: stitch every feature into ONE cognitive loop (R1)

All existing features become lobes on a single always-running loop — no more islands:

```
PERCEIVE  (broker_sense eyes, ocular, vision_worker, ui_market, news)      →
RECALL    (hybrid memory: HippoRAG + A-MEM + FTS5 + FinMem episodes)       →
REASON    (indicator_fusion + cortex + column network + meta_labeler + UQ) →
DECIDE    (funnel → order-preview gate → money-lens guardrails)            →
ACT       (API execution only; web = navigation/data only)                 →
OBSERVE   (trade outcomes, xray, tailgate, decision snapshots)             →
REFLECT   (Reflexion + SHAP attribution + decision memory)                 →
LEARN     (write neurons, FSRS review, continual learner)                  →
EVOLVE    (edit/mutate instructions, promote/demote strategies)            →
TEACH-SELF (curriculum engine picks the next lesson/gap)                   → back to PERCEIVE
```

Every stage **reads and writes neurons** — that shared substrate *is* the stitching. A `flow_health` monitor proves each arrow carries real data hourly (honest wiring, never decorative).

## Pillar 3 — The School: curriculum from basics to PhD (R2, R5, R6, R11–R13)

A **Teacher module** (LLM-driven, Voyager-style automatic curriculum) runs the brain through levels. Promotion requires passing a real exam — never self-asserted.

**TWO tracks taught in parallel (R21 — the subject is INTELLIGENCE itself, trading is the applied domain):**

- **Track A — HOW TO BE INTELLIGENT** (the owner's core ask): how to think (decompose problems, weigh evidence, estimate uncertainty), how to learn (study→neurons→self-quiz), how to research, how to invent, and **how to USE knowledge** — converting anything known into action (R27). Each of these is a *named, taught, separately examined subject*, not a by-product.
- **Track B — the DOMAIN**: trading + Binance/Upstox navigation + web research, where Track A skills get applied and graded on real outcomes.

Every level below examines BOTH tracks (an L3 exam asks "pick the right strategy" — Track B — *and* "show me how you thought and which neurons you used" — Track A):

| Level | Subject | Graduation exam (examples) |
|---|---|---|
| **L0 Literacy** | Read/write/link/search neurons; use its own memory | Store 100 facts, answer multi-hop questions needing 2+ link jumps |
| **L1 Primary** | Market basics: candles, orderbook, fees, spreads, symbols | Read any chart via local vision and narrate what happened |
| **L2 Secondary** | Indicators, volume profile, risk, position sizing, regimes | Compute/explain signals on unseen data; size positions within risk caps |
| **L3 Undergrad** | Strategies: study the 239-strategy library + books as neurons | Pick correct strategy for a regime; explain WHY with cited neurons |
| **L4 Masters — Research** | Web search → read → distill → neurons → **instructions** | Given an unknown topic, produce a correct, executable instruction set from web research alone |
| **L5 PhD — Invention** | Hypothesis → experiment → validated finding → invention neuron | Invent a strategy/feature variant that beats baseline on CPCV+DSR gate |
| **L6 Professor — Self-evolution** | Edit + mutate own instructions; teach itself NEW domains | Runs a full learn→invent→verify cycle on a domain no one taught it |
| **Practicals (all levels)** | Binance web app + Upstox web app navigation | Complete N never-seen navigation tasks per app using only its own learned instruction neurons |

Textbooks = real ingested material (Docling perception is built): trading books, exchange docs, strategy research — all stored as neurons and *examined on*.

## Pillar 4 — Instructions the brain follows, edits, and MUTATES (R7, R8, R9, R14)

The instruction lifecycle (the brain's "hands to its own knowledge"):

1. **Acquire** — from lessons, web research (R14), or its own successful action trajectories: Agent-Workflow-Memory–style *induction* automatically distills every successful Binance/Upstox navigation or trade sequence into a reusable instruction neuron.
2. **Follow** — instruction neurons are executable: steps + preconditions + verification; the loop executes and self-verifies (Voyager-style) before trusting results.
3. **Grade** — every execution updates stats (wins/losses/PnL attributed) and confidence.
4. **Edit** — the brain rewrites unclear/failing steps using reflection on its own failure traces.
5. **Mutate — and etc. (R26, full evolutionary operator set):** GEPA-style *reflective mutation* (analyze failure traces in natural language → targeted semantic mutations, not random) **plus crossover/combine** (splice two working instructions into one), **merge** (dedupe near-identical variants), **spawn** (derive a sibling for a new market/app context), and **retire** — a **Pareto archive** keeps every diverse working variant, full lineage recorded via `parents`. PromptBreeder-style meta-mutation: the *mutation instructions themselves* are also mutable.
6. **Retire/Promote** — working mutations are kept and promoted into the skill library; losers are demoted with the reason stored as a lesson neuron (nothing is silently deleted — negative knowledge is knowledge).

## Pillar 5 — Self-evaluation like an ultra-advanced AI (R3, R4, R10)

- **Exam engine:** auto-generated + held-out question banks per level; graded by an evaluator that never sees the study material (no self-grading leaks).
- **Independent-learning test (R3):** periodically hand the brain a topic it has zero neurons on → it must research, study, build neurons, produce instructions, and pass a quiz **with no help**. Score = learning velocity.
- **Memory tests (R4, R28):** delayed recall (FSRS), multi-hop reasoning across the neuron web, and **accumulation tests** — the web must measurably GROW (neurons + links + covered topics per week), and previously-passed exams are periodically RE-taken so old knowledge never silently decays.
- **Genius-use "on all the thing" (R22):** the usage metric (% of actions citing ≥1 relevant neuron, and whether the *best* neuron was used) is measured on EVERY output the brain produces — trade decisions, Binance/Upstox navigation steps, research summaries, inventions, self-edits — not only trades. Per-domain genius-use scores on the dashboard.
- **LLM-parity benchmark (R23):** a standing test set where the same tasks (explain, plan, research, convert-to-instructions) are given to the brain (its own memory + micro-models + loop) and to a raw LLM; the brain must match or beat the raw LLM on its home domains — proving the BRAIN is intelligent, not just the LLMs it calls.
- **Agentic time horizon:** track how long the brain runs fully autonomously before a critical error — the 2026-standard capability metric; must grow month over month.
- **Darwin-Gödel discipline:** every self-modification is validated empirically on benchmark tasks before adoption; an **archive of brain variants** is kept so evolution is open-ended and reversible, never destructive.

## Pillar 6 — Researched upgrades grafted into the plan (R20)

| Idea | What it adds | Source |
|---|---|---|
| Darwin Gödel Machine | archive-based, empirically-validated self-modification | [arXiv:2505.22954](https://arxiv.org/abs/2505.22954) |
| MetaSkill-Evolve | two timescales: skills evolve fast, *how-to-learn* meta-skills evolve slow | [arXiv:2607.05297](https://arxiv.org/html/2607.05297v1) |
| Voyager | automatic curriculum + executable skill library + self-verification | [arXiv:2305.16291](https://arxiv.org/abs/2305.16291) |
| Agent Workflow Memory | auto-induce reusable workflows from successful web trajectories (+51% web-task success) | [arXiv:2409.07429](https://arxiv.org/abs/2409.07429) |
| A-MEM (Zettelkasten) | atomic self-linking, self-evolving notes — basis of the Neuron format | [arXiv:2502.12110](https://arxiv.org/abs/2502.12110) |
| GEPA | reflective (not random) instruction mutation + Pareto archive of variants | [arXiv:2507.19457](https://arxiv.org/pdf/2507.19457) |
| PromptBreeder | recursively evolve the mutation-prompts themselves | via [GEPA lineage](https://www.emergentmind.com/topics/reflective-prompt-mutation) |
| Group-Evolving Agents | segment workers (crypto/NSE/options/spot) share experience neurons | [arXiv:2602.04837](https://arxiv.org/pdf/2602.04837) |
| Procedural-memory management | control/adapt/evaluate the instruction store over time | [arXiv:2606.23127](https://arxiv.org/pdf/2606.23127) |
| Agentic time horizons | headline self-evaluation metric for autonomy | [Confident AI 2026 guide](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide) |

Reuse-first: HippoRAG+A-MEM associative memory, file memory, Docling perception, Reflexion, continual learner, FSRS auto-learn, skill LEARNINGS, GUI agent (browser-use/voyager vendored) are **already built** — this goal stitches and completes them rather than rebuilding.

## Definition of done (10-star acceptance)

1. **One web:** ≥95% of all feature data readable as neurons in one graph; zero data islands (R1, R15, R16).
2. **Graduated:** passes exams L0→L6 with held-out grading (R2).
3. **Independent learner:** unknown topic → correct instructions + passed quiz, unaided, repeatedly (R3, R5, R14).
4. **Memory genius:** multi-hop recall + measured knowledge-usage rate in live decisions trending up (R4).
5. **Self-mutating:** instruction lineages exist where a *mutated* version measurably beats its parent and was auto-promoted (R7–R9).
6. **Inventor:** ≥1 invention neuron that passed the CPCV+DSR gate (R6).
7. **App expert:** never-seen Binance and Upstox navigation tasks completed from its own instruction neurons (R11–R13).
8. **Self-evaluating:** exam scores, time-horizon, and learning-velocity on the dashboard, honestly wired (R10).
9. Verbatim owner message preserved + traceability table green (R17–R19).
10. Every upgrade above grounded in the cited research (R20).
11. **Intelligence is the taught subject:** Track A subjects (think/learn/research/invent/use-knowledge) each have their own exam record with passing scores (R21, R27).
12. **Genius everywhere:** per-domain genius-use scores exist for trading, navigation, research, and invention — all trending up (R22).
13. **LLM parity:** brain matches/beats a raw LLM on the standing home-domain benchmark (R23).
14. **Instruction-shaped language:** 100% of neurons carry a non-empty `action` facet (R24).
15. **Registered goal:** /goal shows this as the active north-star (R25).
16. **Full operator set:** lineages exist using mutation AND crossover/combine/spawn — not edit-only (R26).
17. **Accumulation proven:** neuron-web growth curve + re-exam pass-rate on old material both healthy (R28).

## Requirement traceability

R1→Pillar 2 · R2→Pillar 3 · R3,R4→Pillar 5 · R5,R6→Pillar 3 (L4,L5) · R7–R9→Pillar 4 · R10→Pillar 5 · R11–R13→Pillar 3 practicals · R14→Pillar 4 step 1 · R15,R16→Pillar 1 · R17→this document · R18→saved as "brain ultra upgrade" · R19→OWNER_MESSAGE_VERBATIM.md · R20→Pillar 6 ·
**R21→Pillar 3 Track A · R22→Pillar 5 genius-use · R23→Pillar 5 LLM-parity benchmark · R24→Pillar 1 action facet · R25→Status line + /goal skill · R26→Pillar 4 step 5 · R27→Pillar 3 Track A (use-knowledge subject) · R28→Pillar 5 accumulation tests.**
