# Brain Ultra Upgrade — online research notes (2026-07-12)

Raw findings behind GOAL.md Pillar 6. Persisted immediately per persist-research-findings.

## Self-improving / self-evolving agents
- **Darwin Gödel Machine** — iteratively modifies its own code, validates every change empirically on benchmarks, keeps an open-ended ARCHIVE of agent variants (never destructive). https://arxiv.org/abs/2505.22954
- **DARWIN (Dynamic Agentically Rewriting Self-Improving Network)** — 2026 follow-on. https://arxiv.org/pdf/2602.05848
- **MetaSkill-Evolve** — two-timescale evolution: task skills evolve fast, meta-skills (how to learn/improve) evolve slowly. https://arxiv.org/html/2607.05297v1
- **Group-Evolving Agents** — open-ended self-improvement via experience sharing across a group. https://arxiv.org/pdf/2602.04837
- **Gödel Agent** — treats own prompts/logic/decision rules as editable artifacts; candidate edits evaluated on held-out tasks before adoption.

## Curriculum + skill library
- **Voyager** — automatic curriculum (goals calibrated to current state, always pushing to unexplored), ever-growing skill library of EXECUTABLE code, iterative self-verification. Skill library transfers to new worlds. https://arxiv.org/abs/2305.16291 (already vendored in trading/brain/gui)

## Experience → instructions
- **Agent Workflow Memory (AWM)** — induces reusable workflows from successful web trajectories, online or offline; +51.1% relative web-task success. Direct blueprint for Binance/Upstox navigation → instruction neurons. https://arxiv.org/abs/2409.07429
- **ReUseIt** — synthesizing reusable AI agent workflows for web automation. https://arxiv.org/html/2510.14308v1
- **Managing Procedural Memory in LLM Agents** — control/adaptation/evaluation of the instruction store. https://arxiv.org/pdf/2606.23127

## Instruction mutation
- **GEPA** (ICLR 2026 oral) — reflective prompt mutation: LLM analyzes its own failure traces in natural language → targeted semantic mutations; Pareto pool of diverse working variants; genetic tree accumulates learning. Outperforms RL (GRPO) on sample efficiency. https://arxiv.org/pdf/2507.19457 · code: https://github.com/gepa-ai/gepa
- **PromptBreeder** — recursively evolves the mutation-prompts themselves (meta-mutation).

## Unified memory format
- **A-MEM** — Zettelkasten atomic notes; autonomous link generation; notes evolve content+links as new experiences arrive. Basis of the Neuron format. https://arxiv.org/abs/2502.12110 (already vendored: vendor/a_mem)
- **HippoRAG** — KG built at write time + Personalized PageRank at query time for multi-hop retrieval (already built in memory/associative.py).
- **NeuSymMS** — hybrid neuro-symbolic memory. https://arxiv.org/html/2605.17596v2

## Self-evaluation
- **Agentic time horizons** (2026 standard) — how long an agent runs autonomously before a critical error. https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide
- **EducationQ** — evaluating teaching via multi-agent teacher/student dialogue (useful for the Teacher module). https://arxiv.org/pdf/2504.14928

## Google's original Transformer / first-LLM source code (owner ask, 2026-07-12)
- **The original**: Google Brain's own training/eval code for "Attention Is All You Need" (Vaswani et al. 2017) lives in **tensor2tensor** — https://github.com/tensorflow/tensor2tensor — model file: `tensor2tensor/models/transformer.py`. Now deprecated in favor of **Trax** (google/trax), but t2t IS the historical first source.
- **Google's first big open LLM lineage**: **BERT** (2018) https://github.com/google-research/bert · **T5** https://github.com/google-research/text-to-text-transfer-transformer. (Meena/LaMDA were never open-sourced.)
- Readable community references: annotated PyTorch ports https://github.com/jadore801120/attention-is-all-you-need-pytorch, https://github.com/hyunwoongko/transformer.
- Use in this project: L3+ curriculum study material for the brain (how attention works, from the original authors' code) and reference for micro_llm (nanoGPT node already exports own weights). Vendor-clone t2t's transformer.py + BERT if/when the curriculum ingests them.
