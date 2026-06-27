# PROJECT BRIEF — Vision, Goal, and Captured Plans

> This is the durable record of **what we are building and why**, so no step is
> taken blindly. It captures the user's own words/plans. Secrets are NOT stored
> here (see `.env.example` / `config.py`).

## The Goal (one paragraph)
Build a **CPU-first "network of prediction models with a brain"**: hundreds of
ML/DL/quant models wired as **graph "nodes"** (each a full model with its own
golden dataset), trained supervised-style — known input→output first to raise
accuracy, then predicting unknown outputs. An outside **"brain" agent** has
access to all nodes and the full data flow, **reads books/PDFs/news into
memory**, learns, grows, and learns *how to wire/route the nodes*. Primary domain
is trading/quant, but nodes generalize to any data. Reuse mature open-source
first; invent only where nothing exists. GPU is off for now, switchable later.

## Scope of "nodes" / domains
Advanced ML models, deep learning, transformers, AI agents, ML algorithms;
mathematics, physics, quantum finance, quantitative methods; probability,
statistics; **noise finding, chaos finding, finding patterns in chaos/noise,
learning patterns, and prediction**. PhD-level concepts welcomed.

## Hard constraints / preferences
- **CPU-only first**, GPU path deferred and flag-switchable.
- **Reuse-first**: edit/adapt existing OSS; build from scratch only if nothing matches.
- **Self-documenting + indexed + interface-enforced** codebase (see `CONVENTIONS.md`).
- **Dashboard-sync**: every node/feature/intelligence capability appears on an
  ultra-visual animated dashboard (**React + D3/Three.js**), auto-reflecting new additions.
- **Secrets-safe**: keys only in gitignored `.env`.
- Free cloud-LLM API keys provided (stored in `.env`, rotate-later) + local LLM fallback.

## Captured prompts / plans (chronological summary)
1. **Brain-like AI memory** — wants agents that store/recall like a human brain,
   ingest books/PDFs. (Researched: Mem0, Graphiti, Cognee, agentmemory,
   neo4j-agent-memory, Awesome-GraphMemory.)
2. **True intelligence/consciousness** — explored OpenCog Hyperon, LIDA (Global
   Workspace Theory), Darwin Gödel Machine, W3C CogAI. Conclusion: functional
   intelligence is tractable; "consciousness" is unsolved/philosophical.
3. **AI that grows as it learns** — reads web/books/news → vector/graph DB →
   gets smarter. (LLM-Wiki/Karpathy pattern, RAGFlow, DeepTutor, Crawl4AI,
   ScrapeGraphAI, OpenAgent, R2R.)
4. **AI that creates & tests new equations** — Symbolic Regression: PySR, LLM-SR,
   AI Feynman, DSR, SymbolicRegressionToolkit.
5. **AI creating new ML models from equations** — NAS (DARTS, NNI, AutoGluon) and
   algorithm discovery (FunSearch, AlphaEvolve, OpenEvolve, AI-Scientist).
6. **500–1000 ML models as neuron-nodes in a giant network** — MoE (Mixtral,
   OLMoE, Switch Transformer), model merging (MergeKit, FusionBench), Sakana Fugu.
7. **"Not LLaMA but predictions"** — deep stacked ensembles / model-graph networks:
   AutoGluon, H2O AutoML, FLAML, TPOT. Confirmed: 500–1000 full-model routed graph
   doesn't exist yet — this is the novel contribution.
8. **Coding-discipline rules** — self-documenting names, an auto index of files/
   functions/imports/exports/IO/summaries, to stop agents writing code that
   doesn't fit. → Formalized in `CONVENTIONS.md`.
9. **This turn** — do the conventions, show rules banner each message, dashboard
   for all nodes/features, save all plans (this file), provided API keys.

## Related project artifacts
- `ml-network-research.md` — best-practices research (cited).
- `ml-network-related-topics.md` — adjacent fields & CPU-first OSS (cited).
- `ml-network-master-plan.md` — unified architecture + phased roadmap.
- `CONVENTIONS.md` — standing coding rules.
- `.env.example` / `config.py` — secrets pattern.

## Data decision (development vs real)
**Development/test data = synthetic dynamical-system benchmarks with known generating
processes** (default: **Mackey-Glass** chaos; also logistic map, noisy-XOR) — chosen
because they have real, measurable signal + tunable chaos/noise, so the growing
network's accuracy provably rises as it learns (crypto daily-direction is ~random
and useless for development). Verified: MG baseline 52% → ensemble 96.4%, reservoir
node 97.1%. **Real data (crypto via CoinGecko/Coinalyze/Etherscan — already wired)
gets swapped in after the full project is built.** Runners: `run_dev.py` (synthetic,
default), `run_crypto.py` (real). Live nodes: logreg, knn, stump, mlp, reservoir,
gaussnb → stacking_ensemble.

## Status & next step
Planning complete. **Next: scaffold Phase 0 + Phase 1** — repo skeleton, data/eval
plane with golden datasets, `NodeProtocol` + registry + auto-`INDEX.md`, and a
small CPU-only AutoGluon/H2O stacked ensemble proving the known-I/O → accuracy →
unknown-prediction loop. Dashboard (React + D3/Three.js) stood up alongside.
