# Brain Ultra Upgrade — OSS selection (2026-07-12, research-projects phase 1)

Map-first result: the stack ALREADY owns nearly everything; this build is a stitch+extend, not an adopt.

| Capability | Choice | Why | Status |
|---|---|---|---|
| Reflective instruction mutation + Pareto archive (R9, R26) | **gepa** (pip) | ICLR-2026 method; `gepa.optimize(seed_candidate, trainset, adapter=…, candidate_selection_strategy='pareto', use_merge=True)` gives reflective mutation + Pareto frontier + merge/crossover out of the box; `reflection_lm` accepts a callable → wire core/llm (free-floor local) | **ALREADY INSTALLED 0.0.27** in .venv (arrived as a dep). Full optimize loop needs eval rollouts; for cheap per-instruction mutation we call its ideas via core/llm reflective prompts and use gepa's Pareto/merge machinery where rollout counts justify it |
| Atomic self-linking notes (R15/R16/R24 base) | vendor/a_mem + memory/associative.py | already built (A-MEM + HippoRAG PPR) | REUSE |
| Exams / spaced recall / mastery | memory/self_quiz.py (FSRS cloze quiz), memory/knowledge_tracing.py (DKT) | already built | REUSE |
| Curriculum/skill library | vendor/voyager patterns + trading/brain/skills.py SkillLibrary | already built | REUSE |
| Web research → knowledge | memory/librarian.py + trading/brain/researcher.py (ddgs/arxiv/trafilatura + gpt-researcher) | already built | REUSE |
| Continual learning | trading/brain/continual.py (Avalanche) | already built | REUSE |
| Graph viz for neuron web | sigma 3 + graphology (dashboard/web package.json) | already used by SigmaNetwork.jsx | REUSE |

**Verdict:** no new dependency to install. New code = the missing connective tissue: `memory/neurons.py` (unified store), `memory/neuron_web.py` (converters), `trading/brain/instructions.py` (lifecycle + gepa), `trading/brain/school.py` (teacher/exams over self_quiz+tracing), `trading/brain/self_evaluation.py` (R3/R22/R23/R28 metrics), `trading/brain/flow_health.py` (R1 monitor), routes + ONE unified brain page.
