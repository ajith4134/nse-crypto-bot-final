# Brain Ultra-Upgrade — OSS survey (research, 2026-07-02)

Reuse-first Phase-1 SELECT (README/signal-level only; no cloning yet). Goal: ultra-upgrade the
brain across 4 user-requested axes and stitch/clone OSS to extend how the brain *processes any
type of data*:

1. **Human-like memory** — store / recall / connect-the-dots + associative recall on a related topic.
2. **CPU LLMs — CLONE & EXTEND the code** (not download a model): learn how an LLM processes any
   data type and graft that processing capability into the brain.
3. **Coding-agent capabilities** — read data in images (OCR/vision), autonomous online research, web access.
4. **Self-driving-car style continual / online learning + world models.**

## What the brain ALREADY has (baseline — avoid duplicating)
- `memory/` package: `human_memory.py` (Ebbinghaus decay, Letta-style core/recall/archival tiers,
  `dream()` consolidate/forget), `hybrid_memory.py` (fuses vendored Stanford Generative-Agents
  memory-stream + Letta + mem0 + KnowledgeBrain PPR/RRF), `graph.py`, `knowledge_tracing.py`,
  `librarian.py`, `self_quiz.py`, `store.py`, `brain.py`.
- `trading/brain/`: `experience.py` (episodic CBR case base over closed trades, LanceDB kNN),
  `semantic.py` (mem0 free-text lessons), `worldmodel.py` (MuZero imagination), `hypothesis.py`,
  `continual.py`, `selfimprove.py`, `researcher.py`, `metalearn.py`, `regime.py`, `gui/` (computer-use).
- `vendor/`: `generative_agents_memory`, `reflexion`, `voyager`, `muzero_general`, `omniparser`,
  `browser_use_src`, `gplearn`.
- `core/llm.py`: 12-provider cloud-LLM failover (LiteLLM).

So the brain is already strong. Below = the **gaps** and the best OSS to close them.

---

## AXIS 1 — Human-like memory: store / recall / connect-the-dots

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **HippoRAG 2** | github.com/OSU-NLP-Group/HippoRAG | Hippocampus-indexing memory: KG + **Personalized PageRank** for multi-hop *associative* recall ("recall old memory when reading a related topic"). NeurIPS'24. | Active, research-grade | **HIGH** — this is exactly the "connect the dots / associative recall" ask; PPR over a KG runs on CPU | **CLONE/VENDOR** — the missing associative-retrieval layer over existing `memory/graph.py` |
| **A-MEM** | github.com/agiresearch/a-mem | Zettelkasten notes: each new memory auto-links to related notes AND triggers *memory evolution* (re-tags/updates older linked notes). | Research-grade, real code | **HIGH** — dynamic linking + evolution = "future knowledge reshapes old knowledge" | **CLONE/VENDOR** — layer over KnowledgeBrain graph |
| **Graphiti (Zep)** | github.com/getzep/graphiti | Temporal KG, bi-temporal edges, edge *invalidation* = principled forgetting; 63.8% LongMemEval. | Active, company-backed | MED — best for regime/event memory but needs Neo4j/FalkorDB (heavier infra) | Optional later (graph DB dependency) |
| **Letta / Mem0** | letta-ai/letta · mem0ai/mem0 | Tiered self-editing memory / extraction memory layer | Mature | Already integrated in `hybrid_memory` | Keep as-is |
| **Cognee** | github.com/topoteretes/cognee | Ingest any data → "cognify" KG → "memify" prunes stale, strengthens frequent edges (consolidation/decay). | 26k★, Apache-2.0, active | MED — explicit consolidation pipeline | Optional; overlaps `dream()` |

**Winner:** stitch **HippoRAG 2 (associative PPR recall) + A-MEM (dynamic linking/evolution)** on top of the
existing `memory/graph.py` / KnowledgeBrain. Both CPU-friendly (embeddings on CPU, LLM remote via `core/llm.py`).

---

## AXIS 2 — CPU LLMs: CLONE the code and extend data-processing (NOT download a model)

User intent: don't fetch a `.gguf` binary — clone an LLM's *source* and graft how it processes any data.

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **karpathy/nanoGPT** | github.com/karpathy/nanoGPT | ~600-line PyTorch GPT: tokenizer → embeddings → attention → training loop. Cleanest reference for *how an LLM processes tokens*. | Iconic, stable | **HIGH** — clone & extend to a brain "micro-transformer" node that processes any tokenized data stream (trades, text, events) on CPU | **CLONE/VENDOR** as a trainable node |
| **karpathy/llama2.c** | github.com/karpathy/llama2.c | Full Llama-2 inference in one file of pure C (RoPE, SwiGLU, RMSNorm). Trains/finetunes ~100M micro-LLMs, runs on CPU/edge. | Iconic | **HIGH** — polyglot hot-path (C) micro-LLM the brain owns end-to-end; matches "clone & extend, CPU" | **CLONE/VENDOR** (C node) |
| **karpathy/llm.c** | github.com/karpathy/llm.c | GPT-2/3 training in raw C/CUDA. | Active | MED — CUDA-leaning; CPU path exists | Reference only |
| **llama.cpp** | github.com/ggml-org/llama.cpp | SOTA CPU inference engine + Python bindings; GGUF; 1.5–8-bit quant; 3–8× faster than PyTorch on CPU. | Huge, active | HIGH *as an engine* if we ever want to *run* a model — but that's "download", which user deprioritized | Keep as optional runtime, not the clone target |

**Winner:** **CLONE nanoGPT (Python, trainable node) + llama2.c (C micro-LLM, polyglot hot path)**. These give the
brain its *own* transformer it can train on any data stream and extend — the "how an LLM processes any data type"
capability, owned in-repo, CPU-first. llama.cpp stays as an optional inference runtime only.

---

## AXIS 3 — Coding-agent capabilities: read images (OCR/vision) + autonomous web research

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **Docling (IBM)** | github.com/DS4SD/docling | Any doc (PDF/office/images) → clean structured Markdown; layout, tables, formulas; feeds LLM pipelines. | Active, IBM | **HIGH** — "read data in any file/image" as structured text the brain can reason over | **VENDOR/pip** |
| **Surya** | github.com/VikParuchuri/surya | SOTA multilingual OCR + layout + table + LaTeX, 90+ langs; pairs with Docling. | Active | **HIGH** — the OCR engine under Docling for scanned/screenshot input | **pip** (pairs w/ Docling) |
| **MarkItDown (MS)** | github.com/microsoft/markitdown | 12+ formats → Markdown, 100pg/12s, no GPU; optional LLM-vision OCR plugin. | Active, MS | MED — lighter, no-GPU fast path | Optional light complement |
| **OmniParser** (vendored) | microsoft/OmniParser | Screenshot → structured UI elements for GUI agents. | vendored | Already in `vendor/omniparser` + `trading/brain/gui` | Keep; Docling complements (docs vs UI) |
| **GPT-Researcher** | github.com/assafelovic/gpt-researcher | Autonomous multi-source web research → cited report; local-LLM capable. | 15k★+, active | **HIGH** — upgrades `trading/brain/researcher.py` to autonomous cited deep-research | **VENDOR/pip** |
| **Reflexion** (vendored) | noahshinn/reflexion | Verbal self-reflection learning loop. | vendored | Already in `vendor/reflexion` | Keep; wire into researcher |

**Winner:** **Docling+Surya** (universal "read any data in an image/file" → structured text) + **GPT-Researcher**
(autonomous cited web research), both feeding the memory layer. OmniParser/Reflexion already cover GUI+self-reflect.

---

## AXIS 4 — Self-driving-car style continual / online learning + world models

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **Avalanche (ContinualAI)** | github.com/ContinualAI/avalanche | PyTorch continual-learning: experience replay, EWC, benchmarks, forgetting metrics — beats catastrophic forgetting. MIT. | Active, PyTorch-ecosystem | **HIGH** — principled continual learning for the online nodes; the "car learns without forgetting" ask | **VENDOR/pip** — wrap `trading/brain/continual.py` |
| **CarDreamer** | github.com/ucd-dare/CarDreamer | Open-source world-model RL platform for autonomous driving (DreamerV3-style learn-and-imagine). | Active | MED — self-driving world-model reference; heavy (CARLA sim) | Reference/architecture only; feed ideas into `worldmodel.py` |
| **DreamerV3 / muzero_general** (vendored) | danijar/dreamerv3 · vendored muzero | Learn a world model, imagine rollouts, plan. | active / vendored | Already have `vendor/muzero_general` + `worldmodel.py` | Keep; borrow Dreamer's continual-RL online update pattern |
| **River** | github.com/online-ml/river | Online/streaming ML (incremental learn-one/predict-one), pure-Python CPU. | Mature | MED — likely already used by `trading/online`; good for always-on incremental nodes | Confirm/keep |

**Winner:** **Avalanche** (replay/EWC to stop forgetting) wrapping `continual.py`; borrow **CarDreamer/DreamerV3**
continual-world-model *patterns* into the existing `worldmodel.py` (don't pull CARLA).

---

## AXIS 5 (bonus) — How Claude persists project memory to a file (the mechanism you asked about)
- **Mechanism:** two file-based layers loaded at session start — (a) `CLAUDE.md` (hierarchical: global
  `~/.claude`, project, sub-dir), authoritative human-written instructions; (b) **Auto memory** — a
  persistent directory where the agent itself writes one-fact-per-file notes (frontmatter + body,
  indexed by a `MEMORY.md`) based on corrections/insights, and recalls relevant ones by description.
  Files persist across sessions; conversation history does not. Long sessions are **summarized** and the
  summary + unsummarized tail carry into the next context window.
- **This repo already mirrors that exact pattern** at
  `.claude/projects/-home-karan18190164/memory/` (MEMORY.md index + per-fact `.md` files). ✅
- **Actionable upgrade:** give the *trading brain* the same file-memory discipline — a durable
  `brain_memory/` (per-fact notes + index) that HippoRAG/A-MEM index for associative recall, so the
  brain "remembers projects/decisions in files" the way Claude does. This is the bridge that unifies
  Axis 1 + Axis 5.

---

## Deps that would need installing (ASK FIRST — per ask-to-install rule)
| Dep | Axis | Weight | Why |
|---|---|---|---|
| `docling` + `surya-ocr` | 3 | Medium (CPU models auto-download on first OCR) | Read images/PDF/screenshots → structured text |
| `gpt-researcher` (pip) | 3 | Light | Autonomous cited web research |
| `avalanche-lib` | 4 | Medium (pulls torch, already present) | Continual learning w/o forgetting |
| clone `nanoGPT`, `llama2.c` (git clone → `vendor/`) | 2 | Light (clone works; no pip) | Own trainable micro-LLM, CPU |
| `hipporag` / clone A-MEM | 1 | Light–Med (embeddings CPU) | Associative PPR recall + note evolution |
| (optional) `llama-cpp-python` | 2 | Heavy | Only if we later want to RUN a quantized model |

No GPU required for any winner (GPU-only paths explicitly avoided per never-skip-for-data rule). All LLM calls
route through the existing `core/llm.py` cloud failover; all embeddings/graph/vector run CPU-side.

## Recommendation (one paragraph)
Stitch, don't rebuild. The brain already has tiered/episodic/semantic memory — the true gaps are:
(1) **associative multi-hop recall** → clone **HippoRAG 2 + A-MEM** over `memory/graph.py`;
(2) **its own trainable LLM to process any data type** → clone **nanoGPT (Py) + llama2.c (C)** as brain nodes;
(3) **reading any image/document + autonomous cited web research** → **Docling+Surya + GPT-Researcher**;
(4) **continual learning without forgetting** → **Avalanche** wrapping `continual.py`, with DreamerV3/CarDreamer
world-model patterns folded into `worldmodel.py`; and
(5) **file-based project memory like Claude's** → a durable `brain_memory/` that Axis-1 indexes for recall.
Full sequencing, integration points, and interfaces are in the plan file.
