# Phase T8 — Stitch-Into-One Blueprint: Strategy-Evolution Engine + Ultra Brain

> Design doc (review before building). Synthesises the three saved research reports in
> [`research/`](research/README.md) into ONE Phase-T8 architecture for the ML Network Brain
> trading system. CPU-first; **license is NOT a selection filter** (private project); every
> external project is wrapped behind our own adapters so the brain stays the owner.
> Build sequencing + acceptance bars mirror T1–T7 (offline tests + demo runner + dashboard
> status + INDEX/blueprint sync). Live capital stays gated behind paper-trade + back-test acceptance.

---

## 0. Goal

Turn the system from "fixed hand-built strategies + static nodes" into a brain that:
1. **Invents, mutates and evolves** trading strategies for both crypto and NSE — automatically.
2. **Gets measurably smarter with experience** — every closed trade in the 85-column journal becomes training signal; an auto-quiz proves accuracy rises over time.
3. **Researches the world itself** — pulls news/filings/sentiment and folds them into decisions.
4. **Remembers** — episodic (past trades) + semantic (learned regime facts) memory.
5. **Stays honest + safe** — walk-forward / deflated-Sharpe guardrails, paper-first, kill-switch.

Single learning signal everywhere: **realized P&L from the journal** (sign = direction of improvement, magnitude = importance weight, risk-adjusted = Pareto objective).

---

## 1. How it fuses with the existing stack (T1–T7)

```
            ┌─────────────────────── ML NETWORK BRAIN (320 nodes, NodeProtocol) ───────────────────────┐
            │                                                                                            │
 NEWS/WEB ──┤  [T8-C] Autonomous Research  →  sentiment/event nodes ─┐                                   │
            │                                                         │                                  │
 OHLCV ─────┤  [T8-D] Pattern/Regime nodes (STUMPY/hmmlearn/TA) ─────┼─→ feature/context for…           │
            │                                                         │                                  │
            │  [T8-A] STRATEGY EVOLUTION ENGINE  ←── fitness ──┐      ↓                                  │
            │     genomes: GP rules / RL policy / NEAT net     │   [T8-B] EXPERIENCE→INTELLIGENCE LOOP   │
            │     mutate → crossover → select (DEAP/gplearn)   │     episodic memory + skill library +  │
            │     each survivor ⇒ a NodeProtocol strategy node │     continual learning + auto-quiz     │
            │                         │                        │            │                            │
            └─────────────────────────┼────────────────────────┼────────────┼────────────────────────────┘
                                       ↓                        │            ↓
                           [existing] Brain router/ensemble ────┘   recalibrates per-symbol confidence
                                       ↓                                     ↑
                        T3 Execution Engine (order SM, trailing, CB, kill)   │
                                       ↓                                     │
                        T5 Journal (85-col, realized P&L) ───────────────────┘  (THE fitness + reward + experience source)
                                       ↓
                        T7 Telegram alerts   ·   T6 Dark-Pro dashboard (+ T8 monitoring)
```

Key principle: **the T5 journal is the hub.** It is simultaneously (a) the *fitness function* for evolution, (b) the *reward* for RL/exit learning, and (c) the *experience bank* the brain learns from. Everything new reads/writes it.

---

## 2. Stitched components (the picks, all CPU-first)

| Subsystem | Stitched OSS (wrapped behind our adapters) | Role |
|---|---|---|
| **Evolution core** | DEAP | population, mutation/crossover, NSGA-II multi-objective, MAP-Elites |
| **Formula/alpha genomes** | gplearn (+ gpquant ts-operators grafted) | symbolic-regression strategy/feature genomes → NodeProtocol nodes |
| **Fast fitness** | vectorbt | vectorized backtest of a whole generation in one pass |
| **Policy genomes** | FinRL (small CPU agents) | RL strategy + adaptive exit/trailing-stop policy as a genome type |
| **Net genomes (optional)** | neat-python | neuroevolution genome diversity |
| **NSE research substrate** | Qlib (+ RD-Agent loop, LLM-gated) | alpha DSL, CPU GBDT ranking, backtest for equities/F&O |
| **LLM mutation (optional)** | OpenEvolve (Apache-2.0) / QuantaAlpha patterns | "intelligent" mutation of strategy source, LLM-gated |
| **Memory** | mem0 + LanceDB (embedded, CPU) ; Letta optional for self-editing core memory | episodic trades + semantic facts |
| **Continual learning** | River | online/incremental nodes + concept-drift detection |
| **Experience loop** | ExpeL/FinMem/CBR patterns + Generative-Agents scoring | episodic case bank, retrieval-weighted decisions |
| **Self-improvement** | Reflexion pattern + DSPy/GEPA (small local LLM, optional) | per-trade reflections + sample-efficient prompt/program evolution |
| **Meta-learning** | MAML-style init (small CPU models) | sample-efficiency for new symbols/regimes |
| **Pattern/regime** | STUMPY + hmmlearn + TA-Lib/pandas-ta-classic | motif/anomaly discovery, regime states, candlestick features |
| **Asset picking / signals** | Qlib ranker + Alphalens (IC gate) | which symbols to trade + factor validation |
| **Autonomous news** | GPT-Researcher (local LLM) + FinBERT (CPU) + scrapers | self-driven research → sentiment/event nodes |
| **Observability** | Langfuse (self-host) or Phoenix (offline) | trace the brain's reasoning → Stream-of-Mind |
| **Multi-agent (optional, later)** | LangGraph orchestration; TradingAgents debate blueprint | analyst→debate→trader→risk roles over the nodes |

CPU-first split (from research): truly CPU-only = DEAP, gplearn, vectorbt, neat-python, River, STUMPY, hmmlearn, TA-Lib, LanceDB/FAISS/Qdrant, Alphalens, Qlib tree models, FinBERT (small), Langfuse/Phoenix. LLM-gated (use small local Ollama model, or hosted only at decision points) = OpenEvolve/QuantaAlpha, GPT-Researcher, Reflexion, DSPy/GEPA, Letta agent loop, LangGraph/TradingAgents reasoning.

---

## 3. Strategy representation (genome)

A **Strategy** is a typed, serialisable genome with a market tag (`NSE` | `CRYPTO`) and a uniform interface so any genome type plugs into the same evolution loop and becomes a NodeProtocol node:

```
Strategy:
  id, market, genome_type ∈ {gp_rule, rl_policy, neat_net, alpha_formula}
  representation:                      # type-specific
    gp_rule     -> expression tree of (indicators × operators × thresholds) → {LONG/SHORT/FLAT}
    alpha_formula -> gplearn SymbolicTransformer program → continuous signal
    rl_policy   -> serialized small policy net (obs=features, act=position/stop)
    neat_net    -> NEAT genome
  params:      sizing, stop/target template, session filter, instrument filter
  provenance:  parents[], mutations[], generation, created_ts
  -> to_node(): wraps as NodeProtocol predict_proba over the feature frame
  -> to_signal(bar): {action, size, stop, target}  (for backtest + live execution)
```

NSE vs CRYPTO differ only in the **feature set + constraints** they may use (e.g. NSE: SPAN margin, square-off, F&O ban list, India VIX; CRYPTO: funding, leverage, liquidation, 24/7). The genome carries its `market` so mutation only swaps in legal building blocks.

---

## 4. Evolution loop (DEAP-driven, journal-fitness)

```
population = seed(N)                       # seeded from existing strategies + random genomes
for generation in range(G):
    # 1) EVALUATE — fast vectorized backtest (vectorbt) on walk-forward windows
    for strat in population:
        bt = backtest_walkforward(strat, data[market])         # OOS folds only
        fitness = multi_objective(bt, journal_priors(strat))   # see §5
    # 2) SELECT — NSGA-II (Pareto over return / drawdown / turnover) or MAP-Elites cells
    parents = nsga2_select(population)
    # 3) VARY — mutation + crossover (+ optional LLM mutation overlay)
    offspring = crossover(parents) ; mutate(offspring)         # DEAP operators
    if llm_mutation_enabled: offspring += llm_mutate(elite)    # OpenEvolve/QuantaAlpha, gated
    # 4) GUARDRAIL — reject overfit (deflated Sharpe, PBO) before admission (§6)
    survivors = [s for s in offspring if passes_guardrails(s)]
    population = elitist_merge(population, survivors)
    # 5) PROMOTE — survivors become NodeProtocol nodes the brain can route/ensemble
    register_nodes(top_k(population))
```

Mutation operators: point-mutate threshold/indicator, subtree swap (GP), param jitter, indicator add/remove, regime-gate add. Crossover: subtree swap (GP), param blend, ensemble-merge of two rules.

---

## 5. Fitness = the journal + backtest (not a toy metric)

Fitness is **multi-objective** so we never optimise a single number into overfit oblivion:
- **Expectancy** = (win% × avg win) − (loss% × avg loss)  ← from T5 analytics
- **Profit factor** = gross win / gross loss
- **R-multiple distribution** mean & stability  ← T5 quality metrics
- **Deflated / probabilistic Sharpe** (penalises multiple-testing) — guardrail objective
- **Max drawdown** and **turnover/cost** (real charges from T5 `charges.py`)
- **Journal prior**: a strategy whose live/paper journal trades exist is scored on *realized* net P&L, not just backtest — closing the sim-to-real gap.

`trading/journal/analytics.py` + `charges.py` already compute most of this; the fitness adapter just calls them on a strategy's trade set.

---

## 6. Overfitting guardrails (mandatory gate before any strategy is trusted)

Every candidate must pass before promotion to a live-eligible node:
1. **Walk-forward / anchored OOS** — fitness only ever measured on out-of-sample folds; in-sample fit is discarded.
2. **Deflated Sharpe Ratio (DSR)** — adjust for the number of trials in the generation (we test thousands; naive Sharpe is meaningless without this).
3. **PBO (Probability of Backtest Overfitting)** via CSCV — combinatorially-symmetric cross-validation flags strategies whose in-sample rank doesn't survive OOS.
4. **Alphalens IC gate** — for alpha-formula/asset-picking genomes, require a real Information Coefficient before trust; IC feeds per-symbol Bayesian confidence (T5).
5. **Paper-trade burn-in** — promoted strategies trade in T2/T3 paper mode first; only journal-verified ones become live-eligible.
6. **Regime stress** (optional, Layer E) — POET-style synthetic harder regimes; reject strategies that collapse out-of-regime.

This is the most important section: it's what separates "evolving real edges" from "curve-fitting noise."

---

## 7. Brain upgrades (the experience→intelligence loop)

Built in layers (research Layer A→E), each CPU-runnable, each reading the journal:

- **A. Episodic experience bank** — every journal row indexed as a "case" (embedding) in **LanceDB** via **mem0**; before any decision retrieve k analogous past setups (recency × relevance × importance, importance=|realized P&L|) and bias the decision (Case-Based Reasoning). *Lowest risk, highest immediate value — build first.*
- **B. Growing skill/strategy library** — Voyager-pattern: each guardrail-passing strategy stored as a retrievable, parameterised "skill"; an AutoManual-style "trading manual" of rules mined + online-corrected from outcomes.
- **C. Self-evaluation + self-improvement (auto-quiz)** — nightly: (1) Reflexion note per closed trade keyed to P&L; (2) **auto-quiz**: replay held-out recent setups, predict, score vs realized outcomes, **log accuracy-vs-trade-count to prove the curve rises** (P4.4 "proves accuracy rises"); (3) optional GEPA/DSPy evolves any small-LLM reasoning component against the P&L metric (35× fewer rollouts → viable on CPU).
- **D. Continual learning + meta-learning** — **River** online nodes with concept-drift detection; experience-replay buffer (P&L-weighted) when retraining NodeProtocol nodes (anti-forgetting); MAML-style init so a new symbol/regime adapts from a handful of trades.
- **E. (Later) Open-ended + topology evolution** — POET curriculum of harder regimes; DGM-style archive evolving the 320-node topology itself — gated hard behind paper + back-test acceptance.

Plus cross-cutting:
- **Autonomous news research** — GPT-Researcher (local model) pulls catalysts; FinBERT (CPU) scores headlines → sentiment/event NodeProtocol nodes + Telegram surfacing + Stream-of-Mind.
- **Pattern/regime** — STUMPY motifs/anomalies + hmmlearn regime state → context nodes that gate which strategies are active.
- **Asset picking + entry/exit** — Qlib cross-sectional ranker chooses *which* NSE symbols; FinRL/trading-rl learns adaptive exits feeding T3's trailing engine.

---

## 8. Crypto vs NSE handling

One engine, two market profiles (config-driven, mirrors existing `trading/` split):
- **Shared:** evolution loop, fitness, guardrails, journal, memory, brain, dashboard.
- **NSE profile:** Qlib data + alpha DSL, OpenAlgo execution, SPAN/margin + square-off + F&O-ban constraints in genome legality, India VIX/FII-DII context nodes, options (T4 GEX/IV) as features.
- **CRYPTO profile:** ccxt data, funding/liquidation/leverage in genome + fitness (funding P&L from T5), 24/7 sessions, Fear&Greed context node.
- Strategies are tagged by `market`; the population can be split (separate Pareto fronts) or shared with market-legal masking. Default: **separate populations, shared brain + memory** (cross-market insight transfer via the experience bank).

---

## 9. Proposed module layout

```
trading/strategy/                # T8-A evolution engine
  genome.py        # Strategy genome + types (gp_rule/alpha_formula/rl_policy/neat_net) + to_node/to_signal
  operators.py     # mutation + crossover (DEAP), market-legal building-block sets
  fitness.py       # journal+backtest multi-objective fitness (reuses journal/analytics+charges)
  guardrails.py    # walk-forward, deflated Sharpe, PBO/CSCV, Alphalens IC gate
  backtest.py      # vectorbt adapter (fast generation eval) + walk-forward folds
  evolve.py        # DEAP NSGA-II / MAP-Elites loop; registers survivors as nodes
  registry.py      # promote strategy → NodeProtocol node; paper burn-in tracking
brain/                           # T8-B brain upgrades (or extend core/ + memory/)
  memory_bank.py   # mem0 + LanceDB episodic/semantic store over the journal
  experience.py    # CBR retrieval + recency/relevance/importance scoring
  skills.py        # growing skill/strategy library + trading-manual rules
  selfeval.py      # Reflexion notes + AUTO-QUIZ (accuracy-vs-trades proof) + (opt) GEPA/DSPy
  continual.py     # River online nodes + experience-replay retrain + MAML init
  research_agent.py# GPT-Researcher + FinBERT news/sentiment → nodes (LLM-gated)
  patterns.py      # STUMPY + hmmlearn + TA-Lib feature/context nodes
  picking.py       # Qlib ranker (NSE) + entry/exit learning (FinRL/trading-rl)
  observability.py # Langfuse/Phoenix trace hooks → Stream-of-Mind
run_strategy_t8.py / run_brain_t8.py   # offline deterministic demos (like T1–T7)
tests/test_strategy_t8.py / test_brain_t8.py
dashboard: /api/trading/strategy/status, /api/trading/brain/status  +  UI panels
```

---

## 10. Phased build plan (each: offline tests + demo runner + dashboard status + INDEX/blueprint sync)

| Sub-phase | Deliverable | Acceptance |
|---|---|---|
| **T8.1** | Genome + operators + fast backtest (vectorbt) | evolve toy GP rules on synthetic data, green tests |
| **T8.2** | Journal-driven multi-objective fitness + guardrails (WF, DSR, PBO) | a known-overfit strategy is rejected; a real edge passes |
| **T8.3** | DEAP NSGA-II evolution loop → survivors registered as NodeProtocol nodes | population improves OOS fitness over generations (logged) |
| **T8.4** | Episodic experience bank (mem0+LanceDB) + CBR retrieval (Layer A) | retrieve analogous past trades; decision bias demoed |
| **T8.5** | Continual learning (River) + experience-replay retrain + auto-quiz (Layer C/D) | auto-quiz logs rising held-out accuracy vs trade count |
| **T8.6** | Pattern/regime + asset-picking + entry/exit nodes | regime-gated strategy activation; Qlib ranker on NSE universe |
| **T8.7** | Autonomous news research + sentiment nodes (LLM-gated) | GPT-Researcher pull + FinBERT score → node + Telegram + Stream-of-Mind |
| **T8.8** | Skill library + self-improvement (GEPA/DSPy, optional) + observability | growing skill store; Langfuse traces in dashboard |
| **T8.9** | Crypto+NSE end-to-end + Dark-Pro T8 panels + safety review | paper-trade burn-in; kill-switch + guardrails verified |

RL / LLM-gated / topology-evolution (FinRL policies, OpenEvolve, DGM, POET) slot in as optional later steps once the CPU core is proven.

---

## 11. Dependencies to install (CPU wheels; ask-to-install honored)

Core (CPU, no LLM): `deap`, `gplearn`, `vectorbt` (or `vectorbtpro` if licensed — vectorbt OSS fine), `river`, `stumpy`, `hmmlearn`, `TA-Lib` (or `pandas-ta-classic` to avoid the C build), `alphalens-reloaded`, `lancedb`, `mem0ai`, `pyqlib`.
Optional / LLM-gated (small local Ollama or hosted at decision points): `neat-python`, `finrl`, `gpt-researcher`, `transformers`+`finbert`, `dspy`/`gepa`, `langfuse` (or `arize-phoenix`), `openevolve`, `langgraph`.

I'll ask before each install and prefer pure-pip wheels.

---

## 12. Risks & safety (non-negotiable)

- **Overfitting** is the #1 risk → §6 guardrails are mandatory; no strategy goes live without OOS + DSR + PBO + paper burn-in.
- **Self-modifying agents** (DGM/Gödel/STOP editing live logic) are highest-risk → confined to evolving *candidate* code that must pass the same guardrails; never auto-promoted to live capital.
- **LLM components** stay optional + gated; the system must run fully on the CPU core with no LLM.
- **Live capital** always behind the T3 kill-switch, circuit breaker, and master toggle; T8 changes nothing about that.
- **Tokens/research** persisted to `research/` (rule: [[persist-research-findings]]).

---

## 13. Recommended first build

**T8.1 → T8.4** form the minimum coherent vertical slice: evolve real (guardrail-passed) strategies into NodeProtocol nodes, with an episodic experience bank making the brain reuse what worked. That alone delivers "creates + evolves strategies" and "gets smarter with experience" on the CPU core, fully offline-testable — then layer news/patterns/self-improvement on top.
