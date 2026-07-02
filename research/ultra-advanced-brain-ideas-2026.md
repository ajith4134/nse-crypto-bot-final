# Ultra-Advanced Brain Ideas — verified OSS menu (2026-07-02)

Deep research (5 parallel web-verified agents) for stitching cutting-edge, CPU-first,
free-cloud-LLM techniques into the ML Network Brain. Reuse-first: prefer pip/git-vendor,
CPU-runnable, LLM calls remote via the multi-provider failover (`core/llm.py`).
Companion file: `research/agentic-longterm-memory-2026.md`.

Legend — Impact × Feasibility (CPU + free-LLM tier), 1–5.

---

## 1) Autonomous research agents  → upgrades `trading/brain/researcher.py`
| Project | Repo | Maturity | Fit |
|---|---|---|---|
| **local-deep-researcher** | langchain-ai/local-deep-researcher (~9.2k★) | active 2025 | **Core pick** — reflect→gap→requery LangGraph loop; point at Groq/DeepSeek. Vendor the graph. Impact 5 / Feas 5 |
| **GPT-Researcher** | assafelovic/gpt-researcher (~28k★, Apache) | v3.5.1, very active | Citation + parallel-source quality; won DeepResearchGym. Impact 5 / Feas 4 |
| **STORM / Co-STORM** | stanford-oval/storm (~14k★) | active | Question-decomposition + Moderator "what am I missing?" self-verify. Impact 4 / Feas 4 |
| smolagents Open Deep Research | huggingface/smolagents | active | Code-acting tool-use agent (fetch on-chain page, parse CSV). Impact 4 / Feas 3 (sandboxing) |
| TradingAgents (also §5) | TauricResearch/TradingAgents | very active | Analyst→bull/bear debate → ledger-shaped hypotheses. Impact 5 / Feas 4 |
| Search-R1 | PeterGriffinJin/Search-R1 | active | **GPU-only training — idea only** (reason↔search interleave). Impact 3 / Feas 1 |

## 2) Self-improving / self-coding  → upgrades `trading/strategy/evolve.py`, self-coding sandbox
| Project | Repo | Maturity | Fit |
|---|---|---|---|
| **OpenEvolve** | algorithmicsuperintelligence/openevolve (~6.6k★) | v0.2.27 Mar'26, very active | **Top pick** — AlphaEvolve OSS: MAP-Elites + LLM program mutation + evaluator pool. Replace evolve loop; archive keyed on Sharpe/DD/turnover. Impact 5 / Feas 4 |
| **Darwin Gödel Machine** | jennyzzt/dgm (~2.2k★) | reference code | Self-rewriting agent + ancestor archive + empirical validation → improve the *proposer itself*. Impact 4 / Feas 3 |
| AI-Scientist-v2 | SakanaAI/AI-Scientist-v2 | mature | Agentic tree-search experiment manager → drive HypothesisLedger branch expand/prune. Impact 4 / Feas 3 |
| llmalpha | JiangZhihao123/llmalpha (~67★) | early | Factor→Signal→Strategy + walk-forward gate; copy-adapt blueprint. Impact 3 / Feas 4 |
| EvoPrompt | beeevita/EvoPrompt (~247★) | stale but small | Evolve the proposer's *prompts* (meta-layer). Impact 3 / Feas 5 |
| QuantEvolve | arXiv 2510.18569 | paper (no solid code) | Investor-preference MAP-Elites axes → configure OpenEvolve. Impact 4 / Feas 3 (reimpl) |

## 3) Reasoning + calibration + explainability  → upgrades `trading/brain/pipeline.py`
Current gap: scalar ±0.05 heuristics + home-rolled conformal, no verification/NL rationale.
| Project | Repo | Maturity | Fit |
|---|---|---|---|
| **MAPIE** | scikit-learn-contrib/MAPIE (1.6k★) | v1.4.1 Jun'26, solid | **Do first** — conformal w/ coverage guarantee + time-series (EnbPI). Replace home-rolled abstention. Impact 5 / Feas 5 |
| **LM-Polygraph** | IINemo/lm-polygraph (~483★) | v0.6.0, active | 40+ LLM uncertainty methods; black-box (no logprobs) → works on free endpoints. Real confidence vs ±0.05. Impact 5 / Feas 4 |
| Self-consistency + semantic entropy | Nature 2024; OATML/semantic-entropy-probes | technique | Sample N verdicts, abstain on high entropy. Cheapest verification win. Impact 4 / Feas 5 |
| crepes | henrikbostrom/crepes | active | Conformal predictive *CDF* → position-size off calibrated P(return>0). Impact 4 / Feas 4 |
| netcal | EFS-OpenSource/calibration-framework | stable | Temperature-scale the displayed confidence; log ECE as brain-health. Impact 3 / Feas 5 |
| DeepEval (G-Eval) | confident-ai/deepeval | very active | LLM-as-judge NL rationale + faithfulness → into trade journal. Impact 4 / Feas 4 |
| NeMo Guardrails | NVIDIA/NeMo-Guardrails (6.6k★) | v0.23 Jul'26 | Output rail: block trade if rationale not grounded in signals. Impact 4 / Feas 4 |

## 4) Agentic / long-term memory  → upgrades `memory/*`, `trading/brain/experience.py`
Coverage already strong (mem0, Letta, GA stream, HippoRAG-style PPR vendored). Additions:
| Project | Repo | Maturity | Fit |
|---|---|---|---|
| **cognee** | topoteretes/cognee (~26.5k★) | v1.2.2 Jun'26 | **Recommended add** — embedded graph+vector (SQLite/LanceDB/Kuzu, no services); "memify" = tested consolidation for `dream()`. LanceDB already used. Impact 4 / Feas 5 |
| **A-MEM** | agiresearch/a-mem | NeurIPS'25 | Zettelkasten notes that self-link + evolve older memories. CPU sentence-transformers. Impact 4 / Feas 4 |
| Graphiti/Zep | getzep/graphiti | active | Temporal KG w/ edge-invalidation = principled forgetting; best for regime/event memory. **Needs Neo4j — defer.** Impact 4 / Feas 2 |
| HippoRAG 2 | OSU-NLP-Group/HippoRAG | NeurIPS'24 | Reference upgrade for KnowledgeBrain's PPR+RRF channel. Impact 3 / Feas 4 |
| CBR Revise/Retain | arXiv 2504.06943 | technique | ExperienceBank has Retrieve+Reuse; add auto Revise/Retain. Impact 3 / Feas 5 |

## 5) Advanced trading-AI brains  → span worldmodel/hypothesis/decider/strategy-lib
| Project | Repo | Maturity | Fit |
|---|---|---|---|
| **TradingAgents** | TauricResearch/TradingAgents (~90k★) | v0.3 Jun'26 | **Top pick** — analyst panel + bull/bear debate on LangGraph; native Groq/DeepSeek/Gemini. Debate layer → hypotheses + decider confidence. Impact 5 / Feas 4 |
| **FinRL** | AI4Finance/FinRL (~15.6k★) | v0.3.8 | RL exit/position policy (PPO/SAC via SB3, CPU-ok) to replace hand-tuned trailing/TP. Impact 4 / Feas 3 |
| **hmmlearn** | hmmlearn/hmmlearn (~3.2k★) | active | GaussianHMM bull/bear/neutral regime → regime-aware strategy routing. Impact 4 / Feas 5 |
| FinRobot | AI4Finance/FinRobot (~7.4k★) | v1.0 Mar'26 | AutoGen market-forecast/strategy agents → worldmodel feature + strat selector. Impact 3 / Feas 4 |
| FinMem | pipiku915/FinMem-LLM-StockTrading | research | Layered human-like memory driving decisions (ties to §4). Impact 3 / Feas 3 |
| muzero-general / UniZero | werner-duvaud/muzero-general; LightZero UniZero | reference | Harden `worldmodel.py` MCTS; UniZero = transformer latent for long horizon. **Keep nets tiny on CPU.** Impact 3 / Feas 3 |
| Time-Series-Library | thuml/Time-Series-Library (~8k★) | active | PatchTST/DLinear/TimeMixer CPU forecasters → world-model / regime features. Impact 3 / Feas 4 |
| Automate-Strategy-Finding | arXiv 2409.06289 | paper | Risk-aware multi-agent validation + ensemble strategy selection for the decider. Impact 4 / Feas 3 |

---

## Recommended "build-next" shortlist (highest impact × feasibility)
1. **Deep-research loop** — vendor local-deep-researcher's reflect→gap→requery + GPT-Researcher citations into `researcher.py` (the closed loop already calls it every cycle → instantly better hypotheses).
2. **Calibrated decisions** — MAPIE time-series conformal + LM-Polygraph/self-consistency + netcal into `pipeline.py`; replaces the ±0.05 heuristics with guaranteed abstention + honest confidence.
3. **Analyst-debate layer** — TradingAgents bull/bear panel feeding the HypothesisLedger + per-coin decider confidence.
4. **Real evolution** — OpenEvolve (MAP-Elites) as the engine behind `evolve.py`, axes per QuantEvolve (Sharpe/DD/turnover), library-first.
5. **Memory consolidation** — cognee (embedded) + A-MEM notes to give `dream()`/experience real tested consolidation.
6. **Regime routing** — hmmlearn regime label gating which strategy segment + world-model policy the decider uses.

GPU-only / defer: Search-R1 training, Graphiti (needs Neo4j), large FinRL/MuZero nets.
