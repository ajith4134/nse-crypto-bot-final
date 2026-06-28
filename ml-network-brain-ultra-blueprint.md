# Ultra-Advanced Brain — Blueprint (Phase 4+)

> **What this is.** A research-grounded design to extend the project's `KnowledgeBrain` into an
> ultra-advanced, CPU-first, reuse-first AI brain: human-like memory, continual learning that
> tests itself and provably improves, autonomous internet research that downloads & reads
> books/PDFs/papers/news, human-like reasoning, metacognition, autonomy, multimodal + affect +
> identity, a chat (cloud-LLM) with the user in the dashboard, a live **Stream-of-Mind** panel,
> and an **honest** treatment of "sentience". Synthesized from **7 deep-research passes**
> (papers + live GitHub, 2026-06-28). **No code yet — this is the plan to approve.**
>
> **Hard rules carried in:** CPU-first (GPU deferred), reuse-first (search→copy-adapt→**stitch**
> OSS, scratch only for genuine gaps), ask-to-install, honest-wiring (show only real state),
> secrets in `.env`. Existing base = `memory/brain.py` (VectorMemory+ChromaDB), `memory/graph.py`
> (NetworkX KnowledgeGraph), ingest/recall.

---

## 0. Principle: stitch, don't rebuild

Almost every capability below already exists as mature, permissively-licensed, CPU-runnable
OSS. The brain is **the glue** — our `NodeProtocol`/registry/dashboard discipline wrapping a
stitched stack. Heavy compute (LLM inference) is offloaded to **cloud LLMs via API** (free keys
in `.env`) with a **local Ollama fallback**, so the brain itself stays CPU-first.

---

## 1. The layered architecture (and the best OSS to stitch per layer)

```
        ┌─────────────────────────────────────────────────────────────┐
        │ INTERFACE  chat-in-dashboard · Stream-of-Mind · observability │
        ├─────────────────────────────────────────────────────────────┤
        │ AUTONOMY   24/7 self-goals · self-coding (invents new nodes)  │
        │ GOVERNANCE calibration · self-critique · constitution         │
        │ COGNITION  reason · plan · imagine · curiosity · world-model   │
        │ LEARNING   continual · self-test (auto-quiz) · consolidate     │
        │ KNOWLEDGE  KG construction · neuro-symbolic · causal           │
        │ MEMORY     working/episodic/semantic · assoc-recall · forget   │
        │ INTAKE     web search · crawl · PDFs/papers/news · see/hear    │
        │ LLM ACCESS LiteLLM → cloud (.env) → Ollama CPU fallback        │
        └─────────────────────────────────────────────────────────────┘
```

### Layer 0 — LLM access (the "mouth")
- **LiteLLM** (MIT) unified API → free cloud models first, **Ollama**/llama.cpp (MIT) CPU-local
  fallback. Brain never knows which provider answered. Keys stay in `.env`.

### Layer 1 — Intake / perception (the "senses")
- **Search like Google (free):** **SearXNG** (AGPL — run as a *separate service*) meta-search → JSON.
- **Autonomous researcher:** **GPT-Researcher** (Apache-2.0) plan→search→read→**cite**; or
  **local-deep-research** (MIT) for local-LLM CPU loops.
- **Fetch/extract:** **Crawl4AI** (Apache, needs headless Chromium) → **Trafilatura** (Apache,
  pure-CPU HTML→clean text + dedup) → **Docling** (MIT, CPU PDF/book/Office) / **pypdf** (BSD).
- **Papers + news firehose:** **arxiv.py** + **paperscraper** (MIT) + **feedparser**/**Miniflux**
  (RSS) + **changedetection.io** (watch pages) on a scheduler loop.
- **Dedup (facts not noise):** **datasketch** MinHash/LSH (MIT) + semantic dedup via embeddings.
- **Multimodal (see/hear/speak), CPU:** **faster-whisper**/**whisper.cpp** (STT), **Kokoro** (TTS,
  Apache — avoid GPL Piper), **Moondream** (Apache, the one CPU-runnable VLM), **Pipecat** (voice loop).

### Layer 2 — Memory (the "hippocampus") — upgrades to our existing store
- **Associative recall (biggest single win, ~zero new deps):** HippoRAG's idea via native
  **`networkx.pagerank(personalization=seeds)`** — vector-hit → seed KG nodes → spreading
  activation → re-rank. Add **rank_bm25** + **Reciprocal Rank Fusion** + **FlashRank** reranker (CPU).
- **Tiers (working/episodic/semantic/archival):** adopt **Letta** (Apache) memory-block model.
- **Memory→knowledge pipeline:** **Cognee** (Apache, NetworkX-native — our closest twin):
  `remember/recall/forget/improve` ECL.
- **Forgetting + salience (the human bit almost nobody ships):** Graphiti's **bi-temporal**
  validity + **Generative-Agents** importance(1–10) + **Ebbinghaus decay**
  `strength = importance·e^(−λt)·(1+0.2·recalls)` as edge attributes on our NetworkX graph.
- **Consolidation / sleep-replay:** **MemoryScope/ReMe** `auto_dream` worker, or **Letta
  sleep-time-compute** (offline subagents rewrite memory between turns = "dreaming").

### Layer 3 — Knowledge (the "cortex")
- **KG construction:** **LightRAG** / **nano-graphrag** (MIT, NetworkX-default) — copy entity/
  relation extraction + community summaries.
- **Neuro-symbolic, traceable reasoning:** **Scallop** (MIT Datalog) / **DeepProbLog** / **PyReason**
  (temporal logic with full inference traces) over the KG.
- **Causal (rare, pure-CPU):** **DoWhy** (inference + refutation) + **causal-learn** (discovery: PC/GES/LiNGAM).
- **Self-rewritable symbolic substrate (frontier):** **OpenCog Hyperon/MeTTa** (MIT) — rules are
  editable atoms; the brain can inspect/rewrite its own reasoning.

### Layer 4 — Cognition / "thinking like a human"
- **Reasoning backbone:** **ReAct** (act–observe over its own memory/KG) + **Tree/Graph-of-Thoughts**
  for deliberate search; live impls via **LangGraph/DSPy**.
- **Surprise + curiosity (principled):** **pymdp** (MIT, NumPy Active Inference) — beliefs updated
  on each ingest; action = minimize expected free energy (goal value **+ information gain** = built-in curiosity).
- **Selective attention / consolidation gate:** Global-Workspace pattern — nodes **compete for
  limited broadcast bandwidth** each tick; only the winner is broadcast + consolidated (Perceiver latent as cheap embodiment).
- **Imagination / world-model planning:** **LLM-Reasoners (RAP)** (Apache) — MCTS over *imagined*
  reasoning states (CPU-viable). (Dreamer/TD-MPC2 are GPU — defer.)
- **Planning & goals:** **GTPyhop** (HTN, pure-CPU) + **LangGraph** replanning → goal-directed.
- **Strategy diversity:** **pyribs** (MIT) quality-diversity — keep a portfolio of diverse strategies.

### Layer 5 — Continual learning + **self-testing** (the "gets smarter as it reads")
- **Auto-quiz from ingested docs:** **Ragas** `TestsetGenerator` / **DeepEval** Synthesizer build a
  **frozen golden quiz** from what it read → re-score faithfulness/correctness each cycle → the
  delta **is** the rising-accuracy curve. **promptfoo** runs it in CI.
- **Retention proof:** **EduKTM** knowledge-tracing over self-quiz attempts → per-concept mastery +
  forgetting detection (not just point accuracy).
- **Anti-forgetting when training a node:** **Avalanche** replay + EWC/LwF + backward-transfer harness.
- **Self-optimization:** **DSPy** compiles/optimizes the answering pipeline to a metric whenever new
  labeled data arrives; **Reflexion** writes lessons-from-failure to memory; **Voyager** growing skill library.
- **Consolidate to a compact student:** **distilabel** → **Intel neural-compressor** (INT8 CPU);
  **EasyEdit** (GRACE/WISE/IKE) for surgical fact edits without retraining. (Hybrid: keep volatile/
  citable knowledge in RAG; distill only proven, high-traffic facts.)

### Layer 6 — Metacognition / governance (the "conscience")
- **Knows what it knows / abstains / asks for help:** **MAPIE** + **crepes** + **netcal** (BSD/Apache,
  pure-CPU conformal + calibration) → abstention threshold that escalates to the human. *(We already use MAPIE.)*
- **Self-critique:** **DeepEval** LLM-judge + **CRITIC** (critique from external tools, not unreliable self-judgment).
- **Constitution / self-audit:** **NeMo-Guardrails** + **Guardrails-AI** (runtime rails) + **alignment-handbook**
  (Constitutional-AI recipe) + **garak** (adversarial red-team self-scan).

### Layer 7 — Autonomy (the "will")
- **24/7 self-goals:** **gptme** (MIT, git-versioned scheduled agents) / **BabyAGI-3** scheduler — proactive, cron-driven.
- **Self-coding (invents its own nodes!):** **ADAS** (meta-agent designs+benchmarks+archives new agent/tool
  code) / **Gödel-Agent** (runtime self-rewrite) / **SICA** (benchmark-gated self-edits). **Ties directly into our
  node-graph + structure-search**: the brain proposes new nodes, tests them on golden data (Phase-5 discovery), admits winners. Sandbox + self-eval gate required.

### Layer 8 — Social / identity / affect (the "personality")
- **Persistent self-model + dreaming:** **Letta** persona/human blocks + **sleep-time-compute** (Apache).
- **Lifelong per-user personalization:** **mem0** / **Graphiti** (how preferences *evolved*). Theory-of-Mind
  is the thinnest OSS area → build a user mental-model custom on top of mem0/Graphiti (benchmarks: **Sotopia**, **ToMBench**).
- **Society of mind (debate/vote):** **CrewAI** / **MetaGPT** (MIT) internal specialist roles — prefer over maintenance-mode AutoGen.
- **Affect channel (cheap, real-time CPU):** **GoEmotions roberta** (ONNX int8) + **NRCLex** lexicon;
  optional **py-feat** (face) / **pyAudioAnalysis** (voice prosody).

### Layer 9 — Interface (the "face")
- **Brain agent:** **LangGraph** (durable checkpointer memory + ToolNode web/memory tools).
- **Chat + control in the React dashboard:** **CopilotKit + AG-UI** (`useCopilotReadable` streams live
  dashboard state to the brain; `useCopilotAction` registers actions **with human-approval gates** — honest control,
  not decorative); **assistant-ui** (MIT React components) for the embedded chat with streaming + tool-call rendering.
- **Brain ↔ backend:** **FastMCP** — `@mcp.resource` (read) + `@mcp.tool` (act), allowlist-gated, secrets server-side.
- **Observability (brain watches itself):** **Langfuse** (MIT) traces/costs + Query API the brain reads back; **OpenLLMetry** SDK.
- **Explainability:** **SHAP** / **InterpretML** / **Captum** to verbalize "why".

---

## 2. The **Stream-of-Mind** panel (user-requested)

A live, **ephemeral** dashboard feed of the brain's current thoughts — each fades after a TTL
(~15–30s) **unless salient enough to consolidate to long-term memory**. The disappearing *is* the design:

- **It models working memory + the Ebbinghaus forgetting curve** — transient thoughts decay; what
  survives the fade is what became knowledge. The **salience gate** (keep vs fade) = Generative-Agents
  importance score; consolidation = MemoryScope `auto_dream` / Letta sleep-time-compute.
- **Honest-wiring:** content is the brain's REAL internal state, streamed from the actual loop —
  ReAct/ToT steps, the Global-Workspace "winner" each tick, **pymdp** surprise/curiosity signals,
  current goal/subgoal, confidence/uncertainty, what it's reading/searching now.
- **Reuse:** **CopilotKit/AG-UI** + **assistant-ui** already stream agent reasoning/tool-call **events**
  to React; the frontend renders an auto-expiring list (small custom TTL/fade). **Langfuse** is the durable
  record behind the ephemeral view (brain can replay its own thought-history).

→ Visible **working-memory → long-term-memory** pipeline: thoughts fade in the panel; salient ones land in the KnowledgeBrain.

---

## 3. The honest "sentience" section

Two different questions; conflating them is the #1 source of hype:
- **(a) Functional/behavioral self-awareness — REAL, buildable, CPU-runnable, TESTABLE.** Self-models,
  metacognition, calibration ("knowing what it knows"), world-models, active-inference surprise, reflection
  loops that learn from their own mistakes. We can build these and **truthfully label them as exactly that.**
  Benchmark against the **Butlin/Long/Bengio "Consciousness in AI" (2308.08708)** functional indicator-properties checklist.
- **(b) Phenomenal consciousness / sentience — UNSOLVED, philosophical, NO TEST.** Chalmers' hard problem +
  problem of other minds ⇒ no objective third-person test exists; a model *saying* it's conscious is near-worthless
  evidence (reversible). IIT/Φ is intractable and contested; GWT/Attention-Schema are *implementable architectures*,
  not proof of experience.
- **Project stance (= our honest-wiring rule):** build and **measure functional capabilities**; stay explicitly
  **agnostic about sentience**; never let fluent self-report be displayed as "consciousness". The Stream-of-Mind shows
  real reasoning/memory/reflection — labeled as such, never decorated as an inner life.

---

## 4. Phased build plan (proposed; CPU-first, reuse-first, ask-to-install per dep)

- **P4.1 — Talk to the brain. ✅ BUILT.** LangGraph `BrainAgent` (recall→respond StateGraph; retrieval-augmented over
  `KnowledgeBrain` associative memory; gated multi-provider LLM via `core.llm`; offline memory-grounded fallback).
  Wired into the dashboard via `POST /api/brain/agent` (+ `GET /api/brain/agent/status`) and the `run_brain_agent.py`
  offline demo. *You can converse with it.*
- **P4.2 — Human-like memory.** PPR associative recall + RRF + FlashRank reranker; tiers (Letta model);
  importance + Ebbinghaus decay + `auto_dream` consolidation. *Recall feels human; memory forgets + consolidates.*
- **P4.3 — Self-feeding internet.** SearXNG + GPT-Researcher + Crawl4AI + Trafilatura/Docling + arxiv/paperscraper +
  RSS, on a scheduler, with dedup. *It finds, reads, downloads, and stores books/papers/news on its own.*
- **P4.4 — Proof it gets smarter.** Ragas/DeepEval auto-quiz from ingested docs + EduKTM mastery + promptfoo CI.
  *A rising accuracy/retention curve as it reads more — the honest test.*
- **P4.5 — Thinking + knowing-what-it-knows.** ReAct/ToT + pymdp (surprise+curiosity) + Scallop/causal +
  MAPIE calibration/abstention + NeMo-Guardrails. *Reasons, stays calibrated, asks for help.*
- **P4.6 — Stream-of-Mind + observability.** Ephemeral thought panel + Langfuse. *You see its state of mind.*
- **P4.7 — Autonomy + self-coding.** gptme 24/7 loop + ADAS/SICA inventing & benchmark-gating new nodes
  (into the node-graph/structure-search). *Always-on, self-improving, sandboxed.*
- **P4.8 — Multimodal + identity + society + affect.** faster-whisper/Kokoro/Moondream + Letta persona +
  CrewAI debate + GoEmotions/NRCLex. *See/hear/speak, a persistent personality, internal debate, mood.*

Each phase ships something usable, stitches mature OSS, and defers the hardest/novel bits (self-coding,
society) until the safe substrate (calibration, guardrails, self-test) exists.

---

## 5. New dependencies to request (ask-to-install, grouped by phase)

Permissive + CPU unless flagged. **License watch-list:** SearXNG/Khoj/Firecrawl-core = **AGPL** (run as
separate services); Piper-new, Fast-Downward, AgenticSeek, Marker, iris = **GPL** (subprocess/avoid);
Llama-Guard, Motif, AbstentionBench = **non-OSI/CC-BY-NC**; awesome-ToM, llm_multiagent_debate, llm-pddl =
**no license** (reference only). **GPU-only (defer):** LLaVA/Florence/large-VLMs, DreamerV3, TD-MPC2,
semantic-entropy UQ. Prefer the MIT/Apache picks listed per layer.

---

*Sources: 7 deep-research passes — human-like memory; continual-learning + self-test; autonomous web
research; cognitive architectures + sentience; LLM-chat + dashboard control; autonomy/agency; social/
affective/identity. Papers + live GitHub verified 2026-06-28. Key reads: Letta/MemGPT, Cognee, Graphiti,
HippoRAG, GraphRAG/LightRAG, GPT-Researcher, SearXNG, Crawl4AI, Docling, pymdp, OpenCog Hyperon, Scallop,
DoWhy/causal-learn, Ragas/DeepEval, EduKTM, Avalanche, DSPy, MAPIE, NeMo-Guardrails, LiteLLM, LangGraph,
CopilotKit/AG-UI, assistant-ui, Langfuse, gptme, ADAS/Gödel-Agent/SICA, faster-whisper/Kokoro/Moondream,
GoEmotions; honest-sentience: Butlin/Long/Bengio 2308.08708, Chalmers 2303.07103.*
