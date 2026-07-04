# Stitch map — Brain ultra-upgrade (2026-07-02)

Feature × donor matrix. Per-feature best-of-breed; donors vendored with commit in `vendor/README.md`.

| Feature | Donor → module | Lands in | Glue needed |
|---|---|---|---|
| Associative multi-hop recall (PPR over KG) | HippoRAG @ef2f14c → `src/hipporag/HippoRAG.py` retrieve/run_ppr/add_fact_edges pattern | `memory/associative.py` | Reuse OUR `memory/graph.py` `personalized_ranks` (already networkx PPR); LLM triple-extraction via `core/llm.chat`; deterministic offline fallback |
| Note linking + memory evolution | A-MEM @ceffb86 → `agentic_memory/memory_system.py` (MemoryNote, analyze_content + evolution prompt) | `memory/associative.py` (`_analyze`, `_evolve`) | Swap LLMController→`core/llm.chat`; ChromaRetriever→our graph + keyword/embedding sim; JSON persistence in state dir |
| Durable file memory (Claude-style) | pattern from Claude Code memory docs (no code donor — from-scratch glue, stated) | `memory/file_memory.py` + `brain_memory/` | Frontmatter notes + MEMORY.md index; ingest into AssociativeMemory |
| Trainable micro-transformer over any stream | nanoGPT @3adf61e → `model.py` (GPT, Block, CausalSelfAttention) | `nodes/micro_transformer_node.py` | NodeProtocol wrapper; data-adapter tokenizing numeric/event streams; tiny CPU config |
| C micro-LLM hot path | llama2.c @350e04f → `run.c` + `Makefile` | `vendor/llama2_c` built binary, invoked from node (optional) | `make run` build; subprocess adapter; graceful skip if toolchain missing → Python path still full-capability |
| Read any doc/image → structured text | docling + surya-ocr (pip) | `trading/brain/perception.py` | `read_any()`; enabled-when-installed pattern w/ functional text/CSV/JSON fallback reader; output → memory |
| Autonomous cited web research | gpt-researcher (pip) | `trading/brain/researcher.py` upgrade | conduct→write report via GPTResearcher when configured; existing researcher fallback; persist to research/ + memory |
| Self-reflection loop | vendor/reflexion (already vendored) | researcher glue | reuse existing pattern |
| Continual learning w/o forgetting | avalanche-lib (pip) → Replay/EWC plugins | `trading/brain/continual.py` extension | wrap existing learner; if avalanche incompatible w/ py3.13 → implement replay-buffer+EWC directly IN continual.py (equivalent capability, no drop) |
| Continual world-model online update | DreamerV3/CarDreamer PATTERN (no heavy dep) | `trading/brain/worldmodel.py` | learn→imagine→plan→update-online loop hook |
| Dashboard | — glue | `dashboard/server.py` + `BrainMemoryPanel.jsx` | real data endpoints only |

Overlaps: mem0/Letta (already in hybrid_memory) vs A-MEM — keep both: mem0=fact extraction, A-MEM=linking/evolution (different roles). OmniParser (UI screenshots) vs Docling (documents) — complementary, keep both.
Gaps (from-scratch, search came up empty for exact fit): file_memory.py Claude-pattern glue; stream tokenizer-adapter for micro-transformer. Both are glue-class, allowed.
