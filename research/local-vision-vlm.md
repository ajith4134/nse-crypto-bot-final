# Local self-hosted vision VLM — permanent replacement for throttled free cloud vision (2026-07-11)

Owner ask: stop depending on rate-limited free CLOUD vision tiers; run a self-hosted, open-source,
CPU-only vision model as a PERMANENT no-throttle "eyes" for reading indicator charts → direction.

## Map-first (reuse — the wiring gap)
- **Ollama is ALREADY installed** (`/usr/local/bin/ollama`, serving `qwen2.5:3b` text) — and Ollama
  natively serves VISION models. `core/llm.py` already has a local TEXT lane (`allow_local`), but
  vision (`vision_chat`, VISION_PROVIDERS) has NO local entry → that's the gap to close.
- transformers 4.57 + torch 2.10 (CPU) present as a second serving path. Host: 12 cores, ~7GB free
  RAM (brain uses ~24GB) → the VLM must fit ≤~5GB → small models only.

## Phase-1 shortlist (cheap signals; CPU + Ollama-servable + chart quality)

| Model | Pull tag | Size (CPU) | Chart/doc quality | Fit | Verdict |
|---|---|---|---|---|---|
| **IBM Granite-3.2-Vision 2B** | `granite3.2-vision` | ~2.4GB | **Purpose-built for tables/CHARTS/diagrams/documents** | **10** | **PRIMARY** — chart-specialized, small, Ollama-ready, no-throttle |
| Qwen2.5-VL 3B | `qwen2.5vl:3b` | ~3.2GB | flagship small VLM, strong OCR/charts | 9 | **SECONDARY** — higher quality when RAM allows |
| moondream2 1.9B | `moondream` | ~1.7GB | fast, but weak on dense text/precise charts | 7 | **FAST FALLBACK** — speed floor |
| SmolVLM 2.2B | (HF/transformers) | ~2GB | efficient, general (not chart-tuned) | 6 | backup (transformers path) |
| PaliGemma 2 3B | (HF) | ~3GB | solid general VLM | 6 | backup |
| MiniCPM-V 4.5 8B | `minicpm-v` | ~6-8GB | best doc-OCR of the set | 5 | **too big** for our free RAM (skip) |
| Llama-3.2-Vision 11B | `llama3.2-vision` | ~8GB+ | strong general | 3 | too big |
| Chart-specialist research models (TinyChart, ChartLlama, chart-to-text) | HF | varies | chart-QA specialized but research-grade, not Ollama-packaged, older | 4 | granite-vision already folds chart understanding into a production servable model → not needed |

Sources: ollama.com/library (granite3.2-vision, qwen2.5vl, moondream, minicpm-v) · huggingface.co/blog/smolvlm ·
promptquorum local-vision-models-2026 · mljourney best-ollama-models-2026.

## Recommendation — STITCH: Ollama + Granite-Vision as the permanent local eyes
1. **Pull `granite3.2-vision:2b`** (IBM chart/table/document model) into the existing Ollama.
2. **Wire a LOCAL vision provider into `core/llm.py`** — extend `_candidates(VISION_PROVIDERS)` to
   append the Ollama vision model (OpenAI-compatible `/v1`, litellm `openai/…` + api_base). Put it
   FIRST (or as a guaranteed tail) so perception NEVER depends on a throttled free cloud tier.
3. Keep the CNN (Lane A) + cloud VLMs as complementary/failover; ChartScanAI YOLO stays a separate
   pattern lane. Optional: add `qwen2.5vl:3b` as a higher-quality local step when RAM is free.

Result: `chart_vlm.read_chart` / `vision_chat` get a permanent, rate-limit-free local backstop —
the free-tier throttling that blocked live reads today is eliminated.

## BUILT + operational finding (2026-07-11)
Wired: `core/llm.py` `_candidates(..., local_model)` + `_local_vision_model()` (env
`LOCAL_VISION_MODEL`, default `granite3.2-vision`); `vision_available`/`vision_chat`/`vision_order`
now pass `allow_local=True` so the Ollama VLM is the chain's guaranteed tail. `ollama pull
granite3.2-vision` done (2.4GB). `vision_order()` → [gemini, groq, openrouter×2, alibaba,
fireworks, **local**]. 13 vision tests green (incl. 2 new backstop tests).

**RAM was the whole problem (RESOLVED 2026-07-11):** at 31GB the brain held ~24GB → 0 free → the
VLM SWAPPED → a read took ~236s. Owner raised the box to **42GB**. With headroom the swap is gone.

**Benchmark (2026-07-11, 42GB, same indicator+VP chart, CPU):**
- **qwen2.5-vl:7b → 130s, clean parseable JSON, committed direction** (short, "failed auction above
  VAH"). ✅ **CHOSEN DEFAULT** (`LOCAL_VISION_MODEL`, default now `qwen2.5vl:7b`).
- granite-3.2-vision-2b → 196s, verbose nested JSON that truncated → parse FAIL. Kept as fallback.
- CPU (not RAM) is the per-read limit (~130s). More RAM keeps models resident; it does not speed
  CPU inference. So local vision is the **async deep-read + no-throttle backstop**, NOT the 30s path.

**Final architecture (BUILT):** cloud vision stays FIRST for the live 30s funnel (fast when a free
tier is up); the new **`trading/broker_sense/vision_worker.py`** reads charts ASYNCHRONOUSLY with a
220s budget (cloud-fast when available, local qwen7b when throttled — always completes), caches the
structured read per symbol|tf|bar, and `indicator_fusion.fuse()` folds the freshest deep read in as
its vision lens. Result: every decision gets a full indicator-chart reading, permanently, free, with
zero rate-limit dependence and zero funnel blocking. Run as its own process: `python -m
trading.broker_sense.vision_worker` (kill-switch VISION_WORKER=0).
