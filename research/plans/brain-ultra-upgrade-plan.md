# PLAN — Brain Ultra-Upgrade (stitch/clone OSS)  ·  2026-07-02

Status: **PLAN ONLY — no code changes yet.** Awaiting your go + dep approvals.
Companion research: `research/brain-ultra-upgrade-2026.md`.
Branch: `feat/trading-t8` (uncommitted). Rules honored: reuse-first, ask-to-install, polyglot,
auto-index, enforced-interfaces, secrets-safe, dashboard-sync, never-skip.

Principle: **stitch/clone, don't rebuild.** The brain already has tiered/episodic/semantic memory,
world-model, self-improve, GUI computer-use. We only close the real gaps below.

---

## Phase A — Associative memory: "connect the dots / recall old topic when reading a related one"
Clone **HippoRAG 2** (KG + Personalized PageRank multi-hop recall) + **A-MEM** (dynamic note linking + evolution).
- Vendor: `git clone` → `vendor/hipporag`, `vendor/a_mem` (clone works; pip-git blocked).
- New module: `memory/associative.py` — `AssociativeMemory` wrapping HippoRAG PPR over existing `memory/graph.py`
  nodes; on `add(fact)` run A-MEM linking/evolution to re-tag related past notes.
- Interface (enforced): `class AssociativeMemory: def add(self, text, meta)->id; def recall(self, query, k)->list[Hit]`.
  Fuse into `memory/hybrid_memory.py` as a new tier alongside mem0/Letta/GA-stream.
- CPU: sentence-transformer embeddings on CPU; LLM extraction via `core/llm.py`. No graph DB.
- Test: `tests/test_associative_memory.py` — add 3 linked facts, query a related topic, assert multi-hop recall.

## Phase B — Durable file-memory like Claude's (bridges Axis 1 + Axis 5)
Give the trading brain Claude-style file memory: one-fact-per-file + index, indexed by Phase A for recall.
- New: `brain_memory/` dir + `memory/file_memory.py` (`FileMemory.write(fact)`, `.index()`, `.recall(q)`).
- Frontmatter per note (name/description/type) mirroring the Claude auto-memory format already in this repo.
- On brain decisions/lessons, write a note; `AssociativeMemory` ingests it → recallable next session.
- Test: write→reload→recall across a fresh process (persistence proven).

## Phase C — Own trainable micro-LLM: "how an LLM processes any data type", CPU
Clone **nanoGPT** (PyTorch, trainable) + **llama2.c** (pure-C micro-LLM, polyglot hot path).
- Vendor: `vendor/nanogpt`, `vendor/llama2_c`.
- New node (enforced NodeProtocol): `nodes/micro_transformer_node.py` — wraps nanoGPT as a brain node that
  tokenizes ANY stream (trade sequences, text, event logs) → embeddings → attention → next-token/next-event
  prediction. Registered in `core/registry.py`, auto-indexed via `gen-index`.
- C path: build `llama2_c` as an optional fast inference kernel behind the same node interface (polyglot rule).
- Extend, don't just run: add a data-adapter so the transformer ingests the brain's numeric/event streams,
  not only text — this is the "process any type of data" capability the user asked for.
- CPU-only; training tiny (~1–10M params) for smoke tests. `llama-cpp-python` NOT required for this phase.
- Test: train 50 steps on a toy sequence, assert loss decreases + node.predict returns valid shape.

## Phase D — Read any image/document (OCR/vision) + autonomous cited web research
- **Docling + Surya**: new `trading/brain/perception.py` — `read_any(path|url|bytes)->StructuredDoc` (PDF/office/
  image/screenshot → clean markdown+tables). Feeds output into Phase A memory. Complements vendored OmniParser
  (OmniParser=live UI screenshots for GUI agent; Docling=documents/reports).
- **GPT-Researcher**: upgrade `trading/brain/researcher.py` to run autonomous multi-source cited research,
  LLM via `core/llm.py`; results persisted to `research/` (persist-findings rule) + Phase A memory.
- Wire vendored **Reflexion** into the researcher loop for self-correction (already in `vendor/reflexion`).
- Test: `read_any` on a sample PDF returns non-empty structured text; researcher dry-run returns a cited stub offline.

## Phase E — Continual learning without forgetting (self-driving-car style)
- **Avalanche**: wrap `trading/brain/continual.py` with experience-replay + EWC so online nodes learn new regimes
  without catastrophic forgetting; expose forgetting/forward-transfer metrics to observability.
- Borrow **DreamerV3/CarDreamer** continual-world-model *pattern* (learn model → imagine → plan → update online)
  into existing `trading/brain/worldmodel.py`; do NOT pull CARLA/sim deps.
- Test: sequential-task smoke — learn task A, then B, assert task-A accuracy retained vs. no-replay baseline.

## Phase F — Dashboard + wiring (honest, no fake tiles)
- Extend `dashboard/web/src/trading/BrainLearningPanel.jsx` (or new `BrainMemoryPanel.jsx`) to show REAL
  associative-recall hits, file-memory notes, perception reads, continual-learning forgetting metrics.
- Add `/api/trading/brain/memory` + `/perception` endpoints in `dashboard/server.py`; rebuild web assets.
- Honest-wiring rule: panels show live counts/objects only, never decorative placeholders.

---

## Dependencies to install — **ASK BEFORE INSTALLING** (ask-to-install rule)
| Phase | Install | Method | Weight | GPU? |
|---|---|---|---|---|
| A | HippoRAG 2, A-MEM | `git clone`→vendor | Light–Med | No |
| C | nanoGPT, llama2.c | `git clone`→vendor | Light | No |
| D | `docling`, `surya-ocr`, `gpt-researcher` | pip | Medium (CPU model auto-DL first run) | No |
| E | `avalanche-lib` | pip (torch already present) | Medium | No |
| (opt) | `llama-cpp-python` | pip | Heavy | No |

None need GPU. All LLM calls reuse `core/llm.py`; embeddings/graph/vector all CPU. Secrets stay in `.env`.

## Sequencing / effort (rough)
A → B (memory core, highest leverage) · C (micro-LLM) · D (perception+research) · E (continual) · F (dashboard).
A+B are the biggest capability jump for the least code. Suggest starting there after you approve deps.

## Acceptance criteria
- Each phase ships a passing test (`run-tests`) + is honestly wired to the dashboard (`verify-live`).
- `gen-index` re-run after any new `.py` modules; `rebuild-frequi` only if FreqUI touched (it isn't here).
- No stubbing for missing data; if a dep is incompatible, ship the equivalent capability another way.

## Open decisions for you
1. Approve the dep list above (all / subset)?
2. Start order — begin with **Phase A+B (memory)** as recommended, or a different axis first?
3. Micro-LLM (Phase C): want both nanoGPT (Py) **and** llama2.c (C), or Python-only first?
