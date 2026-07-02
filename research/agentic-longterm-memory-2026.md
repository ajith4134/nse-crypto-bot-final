# Agentic / long-term memory OSS for a CPU-first trading brain (research, 2026-07)

Reuse-first survey of current (2024–2026) agentic + human-like long-term memory systems the
trading brain can pip-install or git-vendor. Free cloud LLMs power extraction/importance/
synthesis; embeddings + graph + vector store all run on CPU. Maturity is stated honestly.

Existing brain memory this maps onto:
- `memory/human_memory.py` — Ebbinghaus decay, Letta-style core/recall/archival tiers, `dream()` forget/consolidate.
- `memory/hybrid_memory.py` — already fuses vendored Stanford GA memory-stream + Letta (pip) + mem0 (pip, gated) + KnowledgeBrain PPR/RRF.
- `trading/brain/experience.py` — `ExperienceBank`: episodic case base over closed trades, CBR recall (relevance×recency×importance) → decision bias, LanceDB/numpy.

---

## 1. mem0 — universal memory layer for agents
- Repo: https://github.com/mem0ai/mem0 · ~59.6k★ (Jun 2026), 14M downloads, VC-funded, production-mature.
- What: extraction-based memory layer — LLM distills conversations/events into facts, stored across vector DB (semantic) + graph (relations) + key-value (fast facts); add/search API.
- CPU + free-LLM: embeddings run on CPU; LLM is remote (OpenAI-compatible, so free cloud keys work). Default store is local (Qdrant/Chroma embeddable); no mandatory external DB.
- Maps to brain: ALREADY wired as the gated external semantic store in `hybrid_memory._init_mem0`; keep as the "facts about markets/symbols" tier, powered by core.llm keys.

## 2. Letta (formerly MemGPT) — self-editing tiered memory (LLM-as-OS)
- Repo: https://github.com/letta-ai/letta · paper https://arxiv.org/abs/2310.08560 · large/active, company-backed.
- What: agent edits its own memory via tool calls. Three tiers — Core (in-context RAM), Recall (searchable history), Archival (cold store). "Sleeptime" background agents do memory management (a consolidation analogue).
- CPU + free-LLM: runs embedded/offline without the server; LLM remote. Postgres optional (SQLite embedded works).
- Maps to brain: `human_memory.py` already borrows the core/recall/archival tier model; `hybrid_memory._init_letta` uses real Letta `ChatMemory`. Letta's "sleeptime" ≈ our `dream()`.

## 3. A-MEM — agentic memory, Zettelkasten-style (NeurIPS'25)
- Repo: https://github.com/agiresearch/a-mem (also WujiangXu/A-mem) · paper https://arxiv.org/abs/2502.12110 · research-grade, smaller but real code.
- What: each new memory becomes a structured note (context, keywords, tags) that DYNAMICALLY links to related notes AND triggers "memory evolution" — updating attributes of older linked memories. Emergent knowledge network, no fixed schema.
- CPU + free-LLM: sentence-transformer embeddings on CPU; LLM remote for note generation. No external DB required.
- Maps to brain: the evolution/linking layer over `KnowledgeBrain`'s graph — when a new trade insight arrives, re-tag and re-link analogous past insights (richer than static ingest_text).

## 4. Zep / Graphiti — temporal knowledge-graph memory
- Repo: https://github.com/getzep/graphiti · paper https://arxiv.org/abs/2501.13956 · active, company-backed; beats MemGPT on DMR (94.8% vs 93.4%).
- What: `add_episode` routes text through an LLM to extract entities+edges into a temporal graph with validity intervals; edge INVALIDATION = principled forgetting; can fuse unstructured chat + structured business data.
- CPU + free-LLM: embeddings CPU; LLM remote. BUT requires an external graph DB (Neo4j / FalkorDB) — heavier infra than the others; honest downside for CPU-first single-box.
- Maps to brain: strongest fit for MARKET REGIME / EVENT memory — bi-temporal edges (fact valid-time vs observed-time) model "this correlation held during Q1 regime, invalidated after." Layer over episodic trade memory when a graph DB is acceptable.

## 5. cognee — self-hosted graph+vector memory engine
- Repo: https://github.com/topoteretes/cognee · ~26.5k★, Apache-2.0, v1.2.2 (Jun 2026), very active.
- What: ingest any data → "cognify" builds a knowledge graph (entities/relations/summaries + embeddings); "memify" post-processing PRUNES stale nodes, strengthens frequent edges, reweights by usage — an explicit consolidation/decay pipeline.
- CPU + free-LLM: fully embedded by default — SQLite + LanceDB + Kuzu, ZERO extra services (unlike Zep). Embeddings CPU; LLM remote via OpenAI-compatible key. `pip install cognee`.
- Maps to brain: closest infra match (LanceDB already used in `experience.py`). "memify" prune/reweight ≈ our `dream()`; could replace the hand-rolled consolidate with a tested pipeline.

## 6. HippoRAG — neurobiologically-inspired long-term memory (NeurIPS'24)
- Repo: https://github.com/OSU-NLP-Group/HippoRAG · ~1.3k★, research-grade but usable, HippoRAG 2 released.
- What: hippocampal-indexing theory → LLM+KG+Personalized PageRank for single-shot multi-hop associative recall; +up to 20% multi-hop QA, 10–30× cheaper/6–13× faster than iterative retrieval.
- CPU + free-LLM: PPR + embeddings CPU-friendly; LLM remote for graph construction. No heavy external DB.
- Maps to brain: `KnowledgeBrain` ALREADY does "PPR + RRF associative recall" (per `human_memory.py` docstring) — HippoRAG is the canonical reference/upgrade path for that channel (adopt HippoRAG 2's improvements).

---

## Market-specific techniques (from the trading-agent literature)
- Episodic memory of regimes/events + layered short/medium/long memory with recency×relevance×importance and self-reflection is now standard in LLM trading agents — e.g. survey https://arxiv.org/html/2408.06361v2 ; memory-controlled benchmark https://arxiv.org/html/2605.28359v1 . Brain already implements this scoring in BOTH `experience.py` (trades) and GA stream (text).
- Case-based reasoning (Retrieve→Reuse→Revise→Retain) for LLM agents: review https://arxiv.org/pdf/2504.06943 . `ExperienceBank.recall()` IS the Retrieve+Reuse+bias; the missing loop steps are Revise (adjust after outcome) and explicit Retain (auto add_trade on close) — cheap to add.
- Memory decay / "dreaming" consolidation: Stanford Generative Agents scoring (recency 0.995 decay × importance × relevance) https://arxiv.org/abs/2304.03442 — already vendored; cognee "memify" and Graphiti edge-invalidation are production analogues of `human_memory.dream()`.

## Honest recommendation for CPU-first single box
Already-integrated (mem0, Letta, GA-stream, PPR≈HippoRAG) cover most needs. Two concrete adds:
1. **cognee** — best infra fit (embedded LanceDB/Kuzu, no server), gives a tested prune/reweight consolidation to back `dream()`.
2. **A-MEM** — lightweight memory-evolution/linking layer to make trade-insight notes self-organize.
Defer **Graphiti/Zep** until a Neo4j/FalkorDB dependency is acceptable — it's the best regime-graph model but the heaviest infra.
