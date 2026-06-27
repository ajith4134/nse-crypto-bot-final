# Master Plan — A CPU-First "Network of Prediction Models with a Brain"

> **What this is.** A single, unified architecture + phased build roadmap for your vision: hundreds of ML/DL prediction models wired as **graph "nodes"**, trained supervised-style (known input→output first, then predicting unknown outputs), with an outside **"brain" agent** that has access to all nodes + data flow, reads books/news/PDFs into memory, learns, and grows.
>
> **Grounding.** Synthesized from your stated plan + two cited deep-research passes:
> - `ml-network-research.md` — best practices for large network-of-projects ML systems.
> - `ml-network-related-topics.md` — adjacent fields & OSS projects (CPU-first).
>
> **Hard constraints (your choices).** CPU-only first (GPU path deferred and switchable). Reuse mature open-source first; build from scratch only where nothing fits. Solo-buildable.

---

## 0. The Core Idea, Stated Precisely

You are building a **deep, multi-layer "prediction graph network"** where each node is a *full ML model* (not a single neuron), plus a **learning meta-controller ("brain")** that decides how nodes connect and route. The research confirms this maps onto two mature, CPU-friendly fields:

1. **Deep stacked / multi-layer ensembles with routing** — the direct analog of "models as nodes." Base models' predictions become the next layer's inputs; a meta-learner (or a *learned router*) combines them. Validated by AutoGluon, H2O, Hellsemble, Ensemble².
2. **The "brain" = a continual-learning orchestrator** with graph+vector memory that ingests documents and informs routing/feature generation.

**The honest novelty (where you'd actually invent):** nobody has built 500–1000 full prediction models wired as a routed graph with a *learning* brain choosing the wiring. The pieces exist; the **routing/meta-learner-selection at depth (L2/L3+) is an explicitly open research problem** ([src](https://arxiv.org/html/2511.15350)). That gap is your project's real contribution — everything below it is assembly of existing OSS.

---

## 1. Unified Architecture (CPU-first, layered)

```
                         ┌──────────────────────────────────────────────┐
                         │  BRAIN AGENT (outside the network)            │
                         │  • reads books/PDF/news → memory              │
                         │  • sees all nodes + full data flow            │
                         │  • LEARNS how to wire/route nodes             │
                         │  • triggers equation/model discovery          │
                         └───────────────┬──────────────────────────────┘
                                         │ observes + controls
   ┌─────────────────────────────────────────────────────────────────────┐
   │ ORCHESTRATION / ROUTING LAYER                                        │
   │  learned router assigns inputs → node-families (Hellsemble-style);   │
   │  meta-learners stack node outputs into higher layers (H2O SuperLrnr) │
   └───────────────┬───────────────────────────────────┬─────────────────┘
                   │                                     │
   ┌───────────────▼──────────────┐      ┌───────────────▼─────────────────┐
   │ NODE LAYER (models as nodes)  │      │ MEMORY / STATE LAYER            │
   │  • tabular/boosting nodes     │      │  • vector DB (Qdrant/Chroma)    │
   │  • reservoir/ESN nodes (chaos)│      │  • temporal graph (Graphiti/    │
   │  • regime/change-point nodes  │      │    Neo4j) for relationships     │
   │  • symbolic-regression nodes  │      │  • agent memory (Mem0/Cognee)   │
   │  each: own golden dataset     │      │  • checkpoints, versioned       │
   └───────────────┬──────────────┘      └─────────────────────────────────┘
                   │
   ┌───────────────▼──────────────────────────────────────────────────────┐
   │ DATA + EVAL/CI PLANE                                                  │
   │  feature/data bus · golden input→output sets · CI gates on accuracy  │
   │  (node graduates known→unknown inputs only after passing)            │
   └──────────────────────────────────────────────────────────────────────┘
```

**Layer responsibilities**
- **Node layer** — each node is a CPU-friendly model with a defined interface and its own *golden dataset* (known input→output pairs). Node families below.
- **Memory/state layer** — the brain's long/short-term memory; documents become graph nodes + vectors; versioned as artifacts.
- **Orchestration/routing** — static stacking first (proven), then a *learned* router (the research frontier).
- **Brain agent** — sits outside, reads everything, learns the wiring, and proposes new nodes/equations.
- **Data + Eval/CI plane** — the discipline that makes "increase accuracy on known I/O, then predict unknown" real and testable.

---

## 2. Node Families (all CPU-friendly, all OSS)

| Node family | Purpose | Best OSS | CPU? |
|---|---|---|---|
| **Boosting / tabular** | Core predictors; stacking base learners | AutoGluon-Tabular, H2O, XGBoost/LightGBM/CatBoost | ✅ strong |
| **Reservoir / Echo-State** | Chaotic & noisy time-series prediction | **ReservoirPy** (ESN/NVAR) | ✅ *faster than LSTM on CPU by 1–3 orders of magnitude* ([src](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) |
| **Chaos / noise measures** | Lyapunov, entropy, signal-in-noise | **nolds** (NumPy-only) | ✅ |
| **Recurrence / pattern** | RQA, recurrence networks | **pyunicorn** | ✅ |
| **Regime / change-point** | Detect market/state shifts in noisy series | **ruptures**, hmmlearn, Merlion, Kats | ✅ |
| **Symbolic-regression** | Invent & test new equations from data | **PySR** | ✅ feasible |
| **Pipelines-as-nodes** | Whole AutoML systems as ensemble members | Ensemble² pattern | ✅ |

Reservoir computing is the standout: it's the **CPU-first answer to your "chaos/noise/pattern prediction"** goal and avoids backprop-through-time entirely.

---

## 3. Sequenced Build Roadmap (justified by dependency + risk)

**Sequencing principle:** each phase ships something that works, maximizes OSS reuse, and *defers the hardest/novel research (deep routing, self-improvement) until the substrate exists*. Build the skeleton that everything plugs into first.

### Phase 0 — Foundations (the substrate)
- Hybrid repo: **monorepo** for core AI logic (node code, routing, golden data) for atomic cross-node changes; separate repos for peripheral services (bounds blast radius — Uber found single monorepo commits can hit 1000+ services).
- Data/feature bus + experiment tracking; **version everything** (code, data, models, configs).
- **Eval/CI harness with golden datasets** wired to fail builds on accuracy regression (multi-metric, not single noisy metric).
- **Code discipline (see `CONVENTIONS.md`):** self-documenting names, auto-generated `INDEX.md` (`make index` + pre-commit, never hand-edited), enforced `NodeProtocol` + typed I/O schemas + node registry, and `vulture`/import-graph CI to block orphans/dead code. This is what makes the codebase safe for an agent to extend.
- **Secrets pattern:** gitignored `.env` (+ `.env.example`) loaded via `config.py`; never commit/echo keys.
- **Dashboard substrate (React + D3/Three.js):** stand up the dashboard app + a registry it reads, so **every node/feature/learning capability auto-appears** with live visuals/animation as it's added (dashboard-sync rule).
- *Why first:* every later phase plugs into this; cheapest to get right early.

### Phase 1 — MVP: a small prediction-node ensemble *(start here)*
- Use **AutoGluon/H2O stacking** on both trading and non-trading tabular/time-series data.
- Prove the supervised loop: known input→output → measure accuracy → only then predict unknown.
- *Why first node work:* highest OSS reuse, lowest risk, and it *is* the "models-as-nodes" core in miniature. Everything else connects to it.

### Phase 2 — Specialized node families
- Add **reservoir/ESN** nodes (chaotic series), **nolds/pyunicorn** (chaos/noise/pattern), **ruptures/hmmlearn** (regime).
- Each new node type ships with its own golden dataset + CI gate.
- *Why here:* diversifies the node pool (diversity is what makes routing pay off later).

### Phase 3 — Learned routing (the research frontier)
- Replace the static metalearner with a **learned router** (Hellsemble-style "circles of difficulty": misclassified/hard instances routed to specialist nodes).
- This is where the **open L2/L3 routing gap** lives — your genuine contribution.
- *Why after Phase 2:* routing only helps once you have diverse nodes to route between.

### Phase 4 — Brain / memory layer
- Stand up **Mem0 + Graphiti (temporal graph) + Cognee**, fed by **Crawl4AI** ingestion (books/PDF/news → vector+graph memory).
- Brain uses accumulated knowledge to inform routing decisions & feature generation; add **Avalanche** for continual learning / catastrophic-forgetting mitigation.
- *Why after routing:* the brain's first real job is to *improve the wiring* — it needs Phase 3 to act on.

### Phase 5 — Equation / model discovery (self-improvement)
- **PySR** (+ optionally OpenEvolve / AI-Scientist loop) lets the brain *invent new node models/equations*, test them against golden data, and admit winners into the graph.
- *Why last (pre-scale):* self-improvement is highest-risk; only safe once eval/CI + node substrate are solid.

### Phase 6 — Scale-out & GPU path
- Grow toward hundreds of nodes; flip the **GPU switch** only where it pays (deep models, MoE-style routing). Until then everything stays CPU-first.

---

## 4. Reuse-First Policy — Build Only the Gaps

| Capability | Reuse this OSS | Build from scratch? |
|---|---|---|
| Stacking / ensembling | AutoGluon, H2O | No — reuse |
| Chaotic time-series | ReservoirPy | No — reuse |
| Chaos/noise/recurrence measures | nolds, pyunicorn | No — reuse |
| Regime/change-point | ruptures, hmmlearn, Merlion | No — reuse |
| Symbolic regression | PySR | No — reuse |
| Agent memory / graph | Mem0, Graphiti, Cognee, Neo4j | No — reuse |
| Web/doc ingestion | Crawl4AI, RAGFlow | No — reuse |
| Continual learning | Avalanche | No — reuse |
| **Node-graph orchestration substrate** | (partial: LangGraph/Ray) | **Yes — the glue is yours** |
| **Learned router at depth (L2/L3)** | Hellsemble as starting point | **Yes — the research frontier** |
| **Unified node interface + data bus** | — | **Yes — thin custom layer** |

> Net: ~80% assembly of mature OSS; the ~20% you invent is the **node-graph substrate, the deep learned router, and the brain's wiring policy** — which is exactly the part nobody has built.

---

## 5. Recommended Tech Stack (CPU-first)

- **Language/runtime:** Python. Models on CPU via **gradient boosting (XGBoost/LightGBM/CatBoost)**, **AutoGluon/H2O**, **ReservoirPy**, **scikit-learn**.
- **PyTorch present but CPU-mode / GPU off** (flag-switchable) for any deep nodes — research lands in PyTorch first, so keep the door open.
- **Serving/inference:** ONNX Runtime (CPU) for fast portable inference; quantization when needed.
- **Memory:** Qdrant/Chroma (vectors) + Graphiti/Neo4j (temporal graph) + Mem0/Cognee (agent memory).
- **Orchestration:** LangGraph (agent control flow) + Ray (scale-out when ready).
- **Eval:** DeepEval-style golden datasets in CI.

---

## 6. Key Risks & Open Questions (from the research)

1. **Routing at depth is unsolved** — meta-learner selection at L2/L3 is an open problem; dynamic selection currently *underperforms* static stacking on standard benchmarks. Your bet: hundreds of diverse nodes + a learning brain *reverse* that. Validate early on small scale.
2. **No proven 500–1000 full-model graph exists** — compute & coordination are the reason. CPU-first means starting at tens of nodes and proving the routing pays before scaling.
3. **Continual learning at scale, CPU-feasible?** — Avalanche works for small models; unverified at hundreds of coordinated nodes.
4. **MoE/model-merging are not CPU-first** — treat as GPU-phase ideas, not Phase 1–5.
5. **Eval discipline is load-bearing** — "increase accuracy on known I/O then predict unknown" only means something with golden datasets + honest CI gates; weak eval silently invalidates the whole stack.

---

## 7. Immediate Next Step

Build **Phase 0 + Phase 1**: scaffold the monorepo, the data/eval plane, and a small AutoGluon/H2O stacked ensemble on a real dataset (trading + one non-trading) — proving the known-I/O → accuracy → unknown-prediction loop end-to-end on CPU. Say the word and I'll start scaffolding it.

---

*Sources: see `ml-network-research.md` and `ml-network-related-topics.md` for full citations and confidence levels. Highest-confidence findings: stacking/ensembles and reservoir computing (multiple primary sources). Medium/low: continual learning, MoE, symbolic-regression CPU specifics.*
