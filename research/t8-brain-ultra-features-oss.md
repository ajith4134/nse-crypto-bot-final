# Ultra-Advanced OSS "Brain" / Autonomous-Agent Capabilities for a CPU-First Trading AI (Crypto + NSE)

> Deep-research finding (web search, June 2026). Saved verbatim to prevent loss.
> Star/license figures approximate; marked "approx"/"unverified" where not directly confirmed.
> License informational only (private/non-published project — copyleft is not a blocker).

---

## 1. Long-Term Memory Frameworks

Persistent episodic (past trades/decisions) + semantic (learned facts/regimes) memory across restarts. All CPU-runnable for storage/retrieval; the extraction/summarization step optionally calls an LLM (can be small/local).

| Project | What it does | Stars/maturity | License | CPU vs GPU | Map onto stack |
|---|---|---|---|---|---|
| **Letta (ex-MemGPT)** — https://github.com/letta-ai/letta | "OS for stateful agents": context window as RAM, external store as disk, pages memory via tools; self-improving memory blocks | ~23.6k (verified) | Apache-2.0 | Storage CPU; agent loop needs LLM (can be local/small) | Best fit for the **learning brain** itself — editable "core memory" blocks (per-symbol playbook) it rewrites over time. Heavier than a plain memory service. |
| **mem0** — https://github.com/mem0ai/mem0 | Universal memory layer: hybrid vector+graph+KV, auto-extracts salient facts, multi-level (user/session/agent) | ~59.6k (verified) | Apache-2.0 | CPU store/retrieve; LLM only for fact-extraction (pluggable/local) | Lightest "call from your app" option — log each trade/decision; query "what did I learn about BTC in high-vol." Pairs with 85-col journal. |
| **Zep / Graphiti** — https://github.com/getzep/graphiti | Temporal knowledge graph tracking fact-validity windows; ~63.8% LongMemEval vs mem0 ~49% on temporal retrieval | ~15k+ (unverified) | Apache-2.0 (unverified) | CPU store; LLM for graph extraction | Strongest where **time-validity matters** — "thesis true until earnings/halving." Good for regime/news facts that expire. |
| **Cognee** — https://github.com/topoteretes/cognee | Self-hosted KG memory ("GraphRAG"), 100%-local capable (Ollama) | ~14.2k (approx) | Apache-2.0 | Fully local (CPU + small local LLM) | Best **fully-offline** memory; KG linking symbols ↔ news ↔ outcomes. |
| **LlamaIndex (memory + GraphRAG)** — https://github.com/run-llama/llama_index | Data framework: chat memory buffers, vector/graph stores, retrievers; integrates Cognee | ~40k+ (unverified) | MIT | CPU index/retrieval | Glue layer for one retrieval API across journal + news + docs. |

**Vector stores (storage substrate):**
- **FAISS** — https://github.com/facebookresearch/faiss — fastest ANN; no real-time updates, manual sharding. MIT. CPU build available (GPU optional).
- **Qdrant** — https://github.com/qdrant/qdrant — full-featured, best **metadata filtering** (ideal for financial AI). Apache-2.0. CPU-first (Rust).
- **Chroma** — https://github.com/chroma-core/chroma — easiest, embedded, lightweight. Apache-2.0. CPU.
- **LanceDB** — https://github.com/lancedb/lancedb — embedded-first, edge/offline, zero-server. Apache-2.0. CPU.

Guidance: **Chroma/LanceDB for embedded local; Qdrant for rich filtering at scale; FAISS for raw speed.** For CPU-first single box → **LanceDB or Qdrant-embedded**.

---

## 2. Continual / Online / Self-Improving Learning + Self-Evaluation

| Project | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|
| **River** — https://github.com/online-ml/river | Online/incremental ML on streams; classification/regression/anomaly + **concept-drift adaptation** (creme + scikit-multiflow merger) | ~5.5k (unverified) | BSD-3 | **Pure CPU**, tiny, no retrain | Flagship **continual learning** pick. Wrap as NodeProtocol nodes updating tick-by-tick; native drift detection = automatic regime-shift response. |
| **Reflexion** — https://github.com/noahshinn/reflexion (NeurIPS 2023) | Verbal RL: agent reflects on failures in text, stores reflections, improves next trial w/o weight updates | ~3k+ (unverified) | MIT | Needs LLM (small OK) | Pattern: after each closed trade, brain writes self-critique into memory, retrieved before next similar setup. Pairs with mem0/Letta + Stream-of-Mind. |
| **awesome-online-machine-learning** — https://github.com/online-ml/awesome-online-machine-learning | Curated incremental-learning resources | n/a | — | CPU | Source list for more drift/meta-learning algos. |

Self-eval pattern (no single lib): per-trade Reflexion critiques + per-symbol Bayesian confidence + River drift alarms = closed self-testing loop. Auto-eval can reuse §8 observability (Langfuse/Phoenix run evals as scored datasets on the brain's own decisions).

---

## 3/4/5. Exit Learning, Asset Picking, Entry Timing

| Project | Area | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|---|
| **Microsoft Qlib** — https://github.com/microsoft/qlib | Asset pick + entry/exit | Full AI quant platform: supervised + market-dynamics + RL; cross-sectional ranking, backtests; RD-Agent automation | ~37k (approx) | MIT | **CPU** (LightGBM/linear/CatBoost); deep optional GPU | The big one for **cross-sectional stock ranking on NSE** — factors → ranked symbol list + entry signals; reuse its backtest. Meta-ranker over 320 nodes. |
| **FinRL** — https://github.com/AI4Finance-Foundation/FinRL | Exit/entry RL | DRL (PPO/SAC/DDPG/TD3/A2C/DQN) for automated trading; reward shaping | ~10k+ (unverified) | MIT | small state-space agents train on **CPU** | Learn **adaptive exit/trailing-stop policies** (stop/target as policy outputs conditioned on vol). "exit-policy node." |
| **trading-rl (Price Trailing, ICASSP'19)** — https://github.com/Kostis-S-Z/trading-rl | Exit | Trail-Environment RL for **price-trailing exit** | <1k (unverified) | unverified | CPU-feasible (small) | Direct reference impl for a learned trailing-stop. |
| **Alphalens** — https://github.com/quantopian/alphalens | Asset pick (eval) | Evaluates alpha factors: quantile returns, **Information Coefficient**, turnover, sector | ~3k (unverified); Quantopian-era, community forks active | Apache-2.0 | Pure CPU | Validate a factor/node-score actually ranks the universe before trading. IC = node-quality gate feeding Bayesian confidence. |

Entry timing: Qlib signal models + the pattern/regime tools in §7 are the practical CPU path.

---

## 6. Autonomous Web Research + Finance News / Sentiment

| Project | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|
| **GPT-Researcher** — https://github.com/assafelovic/gpt-researcher | Autonomous deep-research agent: planner + execution agents search web/local docs → cited reports | ~27k (approx) | Apache-2.0 | **Needs LLM** (API or local); search/scrape itself CPU | Drop-in **autonomous news/filings researcher** — "research catalysts for RELIANCE/BTC today," feed summary+citations into memory + Stream-of-Mind. |
| **FinRobot** — https://github.com/AI4Finance-Foundation/FinRobot | Multi-agent financial-analysis platform (analysts + RL + quant) on LLMs | ~7.4k (verified) | Apache-2.0 | LLM-dependent | Reference architecture for a finance multi-agent layer over nodes. |
| **FinGPT** — https://github.com/AI4Finance-Foundation/FinGPT | Open financial LLMs + **FinNLP** data pipelines for sentiment/forecasting | ~15k+ (unverified) | MIT (code) | Models want GPU; **FinNLP scrapers CPU** | Use FinNLP data feeds; LLMs GPU-heavy (skip CPU-first, or distilled). |
| **finvizfinance** — https://github.com/lit26/finvizfinance | Scrapes Finviz: screener, fundamentals, technicals, insider, news | ~0.6k (unverified) | MIT | Pure CPU | Lightweight CPU news/screener (US-centric; for NSE pair with NSE/Moneycontrol scrapers). |
| **FinBERT (ProsusAI)** — https://github.com/ProsusAI/finbert | BERT fine-tuned for **financial sentiment** (pos/neg/neutral) | ~1.5k (unverified) | Apache-2.0 | **Runs on CPU** (~110M) | Score every scraped headline → sentiment feature node + alert filter. Practical CPU sentiment engine. |
| **xai-finnews-sentiment** — https://github.com/MaraAlexandru/xai-finnews-sentiment | Explainable pipeline: TF-IDF+LR, FinBERT, LM lexicon, VADER, SHAP, regime-shift | small | MIT (code) | CPU | Blueprint for an explainable sentiment node with SHAP attributions for dashboard. |

---

## 7. Pattern Discovery + Regime Detection

| Project | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|
| **STUMPY** — https://github.com/stumpy-dev/stumpy | Scalable **matrix profile**: motif discovery, discords (anomalies), AB-joins, multidim | ~3.7k (unverified) | BSD-3 | **CPU** (Numba); optional GPU/distributed | Unsupervised **chart-pattern + anomaly discovery** node — recurring setups + outlier moves across OHLCV, no labels. |
| **hmmlearn** — https://github.com/hmmlearn/hmmlearn | Gaussian/discrete **HMMs**; standard for bull/bear/neutral **regime detection** | ~3k (unverified) | BSD-3 | Pure CPU | Regime-state node ("high-vol bear") to gate strategy/exit policies. |
| **TA-Lib** — https://github.com/TA-Lib/ta-lib-python | 150+ indicators + **61 candlestick patterns** (+100/-100) | ~10k (unverified) | BSD | CPU (Cython) | Cheap deterministic candlestick/indicator features for entry nodes. |
| **pandas-ta-classic** — https://github.com/xgboosted/pandas-ta-classic | 250+ indicators, **62 native candlestick patterns, no TA-Lib C dep** | small | MIT | CPU, pure Python | Pure-pip alternative avoiding the TA-Lib C build. |

---

## 8. Dashboard Monitoring / Observability ("thoughts"/trace visualization)

| Project | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|
| **Langfuse** — https://github.com/langfuse/langfuse | OSS LLM-eng platform: hierarchical **traces** (LLM/tool/retrieval calls), evals, prompt mgmt, scores, sessions; OTel-native; self-host free | ~10k+ (unverified) | MIT (core) | CPU (Docker), self-hostable | Best to **trace the brain's reasoning** + decisions; traces/scores map onto Stream-of-Mind; run auto-evals (§2) here. |
| **Arize Phoenix** — https://github.com/Arize-ai/phoenix | AI observability + eval; runs **locally/Jupyter/Docker, zero external deps**; OpenInference/OTel; LangGraph/CrewAI/Claude SDK support | ~5k+ (unverified) | Elastic License v2 (info only) | Fully local, CPU | Strong **offline-first** tracing/eval; embedding-drift views for node feature drift. |
| **AgentOps** — https://github.com/AgentOps-AI/agentops | Agent telemetry: session replay, **time-travel debugging**, 400+ LLMs | ~4k (unverified) | MIT (unverified) | CPU SDK | Best for **multi-agent debugging** if adopting a multi-agent layer (§9). |

---

## 9. Other Autonomous-Agent Capabilities (multi-agent, planning, tool-use)

| Project | What it does | Stars | License | CPU vs GPU | Map |
|---|---|---|---|---|---|
| **TradingAgents** — https://github.com/TauricResearch/TradingAgents | LLM **multi-agent trading firm**: analysts → research **debate** → trader → risk → fund manager; on LangGraph; multi-provider incl. local Ollama | ~10k+ (unverified) | Apache-2.0 (unverified) | LLM-driven (Ollama-local CPU-feasible w/ small models) | Closest existing blueprint — a debate/role structure to wire over 320 nodes + journal; research-only disclaimer. |
| **LangGraph** — https://github.com/langchain-ai/langgraph | Graph-based agent orchestration with state, checkpoints, **audit trails/rollback** | ~15k+ (unverified) | MIT | CPU orchestration | Best **production-grade orchestration** for the brain's control flow (deterministic, resumable). |
| **AutoGen** — https://github.com/microsoft/autogen | Multi-agent **conversation** framework | ~40k (approx) | MIT | CPU orchestration; LLM calls | Conversational **debate** (bull vs bear). |
| **CrewAI** — https://github.com/crewAIInc/crewAI | Role/goal/backstory agent crews | ~35k (approx) | MIT | CPU orchestration | Simplest role-based abstraction for a small analyst crew. |

All multi-agent frameworks need an LLM behind the agents. On CPU-first hardware: drive with small local models (Ollama) or gate expensive reasoning to a hosted LLM only at decision points.

---

## TOP PICKS TO STITCH (best CPU-runnable, by subsystem)

- **Memory (episodic trades + semantic facts):** **mem0** + **LanceDB or Qdrant-embedded** CPU vector store. Add **Letta** for self-editable "core memory" playbooks; add **Cognee/Graphiti** for a fully-local KG with time-valid facts.
- **Continual learning + self-eval:** **River** (online nodes + drift detection, 100% CPU) + the **Reflexion** pattern writing per-trade self-critiques into mem0, scored/tracked in Langfuse.
- **Autonomous news research + sentiment:** **GPT-Researcher** (point its LLM at local Ollama) + **FinBERT** (CPU sentiment) + **finvizfinance**/FinNLP scrapers for the raw feed.
- **Pattern + regime:** **STUMPY** + **hmmlearn** + **TA-Lib / pandas-ta-classic**. All pure CPU.
- **Asset-picking + entry/exit:** **Qlib** (CPU cross-sectional ranker / entry signals) + **Alphalens** (factor IC gate) + **FinRL** (or **trading-rl**) for a learned adaptive exit/trailing-stop node.
- **Dashboard / observability:** **Langfuse** (self-hosted, MIT, OTel) feeding Stream-of-Mind; **Phoenix** for a fully-offline alternative.
- **Orchestration / multi-agent (optional, LLM-gated):** **LangGraph** for deterministic resumable control flow; study **TradingAgents** as the analyst→debate→trader→risk→manager blueprint; drive with local Ollama to stay CPU-first.

### CPU-first caveats
- **Need LLM/GPU (use small local models or gate to hosted API):** Letta agent loop, Reflexion, GPT-Researcher, FinRobot, FinGPT models, TradingAgents, AutoGen/CrewAI/LangGraph reasoning.
- **Truly CPU-only, no LLM:** River, FAISS/Qdrant/Chroma/LanceDB (storage), STUMPY, hmmlearn, TA-Lib, pandas-ta, Alphalens, FinBERT (small CPU inference), Qlib tree models, finvizfinance, Langfuse/Phoenix backends.

All stars/licenses except Letta, mem0, FinRobot (directly verified) are approximate/unverified — confirm at integration time.
