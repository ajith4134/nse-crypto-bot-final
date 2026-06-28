# Strategy Creation / Mutation / Evolution Engines — OSS Landscape for Crypto + NSE

> Deep-research finding (web search, 2026-06-28). Saved verbatim to prevent loss.
> License reported for INFO ONLY — not a filter (private non-published project). CPU-first is the deciding lens.
> Star/license/last-push verified via GitHub API on 2026-06-28 by the research agent.

---

## 1. Genetic / Evolutionary (GP, GA, symbolic regression)

### gplearn — https://github.com/trevorstephens/gplearn
- Genetic programming with a scikit-learn API: `SymbolicRegressor`, `SymbolicClassifier`, `SymbolicTransformer` (feature/alpha synthesis via crossover+mutation of expression trees).
- ~1,866 stars. **BSD-3-Clause.** Maintained (pushed Jan 2026). **CPU-only** (NumPy/joblib, parallel via `n_jobs`).
- Integration: pure sklearn estimators — `fit/predict/transform`, custom function sets, custom fitness metrics. Trivial to wrap each evolved formula as a NodeProtocol prediction node and feed the trade journal's realized-PnL as the fitness metric.
- Maps to: 320-node brain — gplearn becomes the **alpha/feature-discovery node factory** (mutate indicator combos into new node candidates).

### DEAP — https://github.com/DEAP/deap
- General evolutionary-computation toolbox: GA, GP, ES, multi-objective (NSGA-II/III), CMA-ES. The substrate most trading-GP projects build on.
- ~6,411 stars. **LGPL-3.0.** Actively maintained (Apr 2026). **CPU-only**, parallelizable (multiprocessing/SCOOP).
- Integration: genome = ruleset/indicator tree, fitness = backtest Sharpe/PnL. Multi-objective key feature — evolve for Sharpe AND max-drawdown AND turnover simultaneously.
- Maps to: the **core evolution engine** for whole-strategy genomes; fitness calls existing execution/backtest + 85-col journal.

### gpquant — https://github.com/UePG-21/gpquant
- gplearn fork tuned for **financial time-series factor mining** (adds ts_rank, delta, decay, correlation operators).
- ~222 stars. **No license file** (unverified — treat as all-rights-reserved; fine for private use). **Stale** (last push Apr 2023). **CPU-only.**
- Maps to: reference implementation for time-series-aware GP operators to graft onto gplearn/DEAP.

### GeneTrader — https://github.com/imsatoshi/GeneTrader
- GA that evolves **Freqtrade strategy parameters** (genome = strategy hyperparams; fitness = backtest).
- ~197 stars. **MIT.** Maintained (Feb 2026). **CPU-only.**
- Maps to: concrete pattern for "GA on top of a backtester," relevant if adopting Freqtrade for crypto leg.

### mosquito — https://github.com/miro-ka/mosquito
- Crypto bot built around ML + genetic algorithms, modular. ~262 stars. **GPL-3.0.** **Stale** (Apr 2023). CPU. Historical/reference interest.

---

## 2. Reinforcement-Learning trading agents

### FinRL — https://github.com/AI4Finance-Foundation/FinRL
- De-facto OSS financial-RL framework: Gym-style market envs + DRL agents (PPO/A2C/DDPG/SAC/TD3) for stock/crypto/portfolio.
- ~15,540 stars. **MIT.** Actively maintained (May 2026). **CPU-runnable** for small/medium nets (SB3/ElegantRL); GPU only helps large nets/throughput.
- Companion: **FinRL-Meta** — https://github.com/AI4Finance-Foundation/FinRL-Meta — hundreds of near-real market environments + data engineering (plug NSE + ccxt data here).
- Integration: custom Gym env wrapping execution engine (order SM, trailing stops, circuit breaker) as the action space; reward = journal realized PnL net of costs. RL = "policy evolution" complementing GP.
- Maps to: an RL **node/agent** whose learned policy is another candidate strategy in the population.

---

## 3. AutoML / alpha-factor & feature discovery / symbolic regression

### Microsoft Qlib — https://github.com/microsoft/qlib
- Full AI-quant platform: data layer, alpha expression engine (Alpha158/360), model zoo, backtest, portfolio optimization, `qrun` YAML workflows.
- ~45,322 stars. **MIT.** Maintained (Apr 2026). **CPU-runnable** (LightGBM/XGBoost/CatBoost CPU-native; deep models optional).
- Integration: modular — use just data+alpha+backtest modules. Its **alpha expression DSL** is the strongest free scaffolding for the NSE equities leg.
- Maps to: the **research/backtest substrate** + alpha-expression vocabulary that GP/LLM mutation operates over.

### alphagen — https://github.com/ICT-FinD-Lab/alphagen (older mirror: RL-MLDM/alphagen)
- KDD'23 "synergistic formulaic alpha collections via RL." Generates **sets** of formulaic alphas (RL over expression trees) + gplearn-GP and DSO baselines + an `alphagen_llm` module.
- ~1,135 stars. **No license file** (unverified). Maintained (Jun 2026). **CPU-runnable** (small policy nets; runs on Qlib data).
- Maps to: drop-in **alpha-generation engine** targeting Qlib — produces formulaic alphas registerable as nodes.

### AlphaForge — https://github.com/DulyHao/AlphaForge
- AAAI'25. Two-stage: generative-predictive net mines factors, then **dynamically combines** them with time-varying weights.
- ~385 stars. **No license file** (unverified). **Stale-ish** (Sep 2024). CPU-runnable.
- Maps to: the **factor-combination/weighting layer** — dynamic reweighting of node ensemble vs static stacking.

### Microsoft RD-Agent (R&D-Agent-Quant) — https://github.com/microsoft/RD-Agent
- LLM multi-agent that **automates the quant R&D loop**: proposes factors+models, codes them, backtests on Qlib, reads results, iterates. Reported ~2x ARR with 70% fewer factors at <$10/run.
- ~13,690 stars. **MIT.** Very active (Jun 2026). Orchestration **CPU-runnable**; heavy lift = LLM API calls (external).
- Maps to: the **closed-loop autonomous researcher** on top of Qlib — closest off-the-shelf "self-improving strategy loop" for NSE leg.

---

## 4. LLM-driven idea generation / code synthesis / self-improving loops

### QuantaAlpha — https://github.com/QuantaAlpha/QuantaAlpha
- Evolutionary framework for **LLM-driven alpha mining**: each mining run = a trajectory; **trajectory-level mutation + crossover**, localizes weak steps for targeted LLM revision, recombines high-reward segments.
- ~1,178 stars. **No license file** (unverified). Active (Jun 2026). Orchestration CPU; relies on external LLM.
- Maps to: most direct template for **LLM-as-mutation-operator over strategy/alpha genomes**; pairs with DEAP/gplearn population.

### OpenEvolve — https://github.com/algorithmicsuperintelligence/openevolve
- Open implementation of DeepMind AlphaEvolve: evolutionary coding agent (program database + MAP-Elites-style selection + LLM ensemble mutation) evolving whole **code** against an evaluator.
- ~6,614 stars. **Apache-2.0.** Maintained (Mar 2026). Orchestration CPU; LLM calls external.
- Integration: evaluator = backtest+journal; evolve strategy **source code** (Python rules). Supply the trading evaluator.
- Maps to: the **general code-evolution engine** — evolve actual strategy `.py` files with execution engine as fitness sandbox.

### QuantEvolve (paper; repo unconfirmed) — https://arxiv.org/abs/2510.18569
- Multi-agent evolutionary framework with **quality-diversity feature map** (Sharpe, drawdown, turnover, strategy-category cells) + hypothesis-driven LLM reproduction. No verified public repo — use as **design blueprint** (its QD-map argues for DEAP NSGA-II / MAP-Elites).

### LLM bot references (lower priority, idea-mining)
- LLM-TradeBot (multi-provider, reflection agent) — https://github.com/EthanAlgoX/LLM-TradeBot
- FinMem (layered-memory self-evolving agent) — https://github.com/pipiku915/FinMem-LLM-StockTrading
- Agent demos, not evolution engines — mine for prompt/reflection patterns only.

---

## 5. Backtesting frameworks with optimization (the fitness-eval layer)

### vectorbt — https://github.com/polakowo/vectorbt
- Vectorized (Numba) backtester for **massive parameter sweeps** (10k+ combos one pass) — ideal fitness evaluator for GA/GP populations.
- ~8,072 stars. **License NOASSERTION** (custom/Apache-derived — verify; open-core, PRO paid). Active (Jun 2026). **CPU-only**, fast.
- Maps to: the **high-throughput fitness engine** — score an entire evolved population per generation cheaply.

### Freqtrade (+ FreqAI + Hyperopt) — https://github.com/freqtrade/freqtrade
- Mature crypto bot: backtest, **Hyperopt (Optuna)**, FreqAI adaptive-ML, Telegram control, many exchanges (ccxt).
- ~51,912 stars. **GPL-3.0.** Extremely active. **CPU-runnable** (FreqAI uses CPU GBDTs by default).
- Maps to: ready-made **crypto execution+optimization leg**; Hyperopt+FreqAI + Telegram reusable. GeneTrader shows GA-on-top pattern.

### backtesting.py — https://github.com/kernc/backtesting.py
- Lightweight single-asset backtester with built-in optimization (grid + SAMBO/scikit-optimize).
- ~8,577 stars. **AGPL-3.0.** Maintained (Dec 2025). **CPU-only.**
- Maps to: simple fitness harness for quick GP/GA rule evaluation when vectorbt is overkill.

### backtrader — https://github.com/mementum/backtrader
- Event-driven backtester+live, realistic fills, broker integrations. ~22,158 stars. **GPL-3.0.** **Effectively unmaintained** (Aug 2024). **CPU-only.**
- Maps to: realistic event-driven validation AFTER fast vectorbt screening; note staleness.

### Jesse — https://github.com/jesse-ai/jesse
- Crypto framework with Optuna **Optimize Mode** + cross-validation + JesseGPT. ~8,115 stars. **MIT.** Very active. **CPU-runnable.**
- Maps to: MIT alternative to Freqtrade for crypto leg with built-in optimization.

### OctoBot — https://github.com/Drakkar-Software/OctoBot
- Crypto bot (Grid/DCA/TradingView/AI), built-in backtest+optimize, 15+ exchanges. ~6,159 stars. **GPL-3.0.** Active. More end-user product.

---

## 6. Neuroevolution / NEAT

### neat-python — https://github.com/CodeReclaimers/neat-python
- Pure-Python NEAT (evolves NN topology+weights). Used in trading (e.g. ChadBowman/neatrader for options).
- ~1,570 stars. **BSD-3-Clause.** Maintained (May 2026). **CPU-only.**
- Maps to: a **neuroevolution node** — evolve small NN policies over indicator inputs; fitness = backtest. Complements GP.

---

## NSE-specific glue (India data/exec layer, not evolution engines)
- **OpenEngine** — https://github.com/marketcalls/openengine — event-driven backtest+live for Indian markets, integrates **OpenAlgo PlaceOrder** (already used). ~15 stars, AGPL-3.0, last push Feb 2025.
- algo_trading_strategies_india (NIFTY/BANKNIFTY option-selling templates) and aaryansinha16/AI-trader (NSE F&O ML, TimescaleDB) — strategy/idea references.

---

## TOP PICKS TO STITCH — one CPU-first strategy creation/mutation/evolution engine

Architecture: **GP/GA core → fast vectorized fitness → LLM mutation overlay → RL/NEAT as alternative genome types → execution+journal as ground-truth fitness.**

1. **DEAP** (LGPL, ~6.4k★, active) — evolution **core**. Genome = strategy/ruleset; NSGA-II multi-objective (Sharpe + drawdown + turnover); optional MAP-Elites quality-diversity grid. CPU, parallel.
2. **gplearn** (BSD, ~1.9k★, active) — **alpha/feature-discovery factory**. Sklearn-native → each evolved `SymbolicTransformer` formula drops in as a NodeProtocol node. Graft gpquant's time-series operators.
3. **vectorbt** (open-core, ~8k★, active) — **high-throughput fitness engine**. Numba-vectorized; scores an entire generation in one pass → makes CPU-only evolution tractable.
4. **QuantaAlpha** *or* **OpenEvolve** — **LLM mutation/crossover overlay**. QuantaAlpha = trajectory-level mutate/crossover (no-license → reproduce patterns); OpenEvolve = Apache-2.0, evolve whole strategy source files with backtest as evaluator. OpenEvolve = safer license + more generic.
5. **FinRL** (MIT, ~15.5k★) — **policy-evolution genomes**: RL agent (custom Gym env over order SM/trailing stops/circuit breaker, reward = journal net PnL) = another candidate strategy type. CPU-fine for modest nets.
6. **Microsoft RD-Agent on Qlib** (both MIT, very active) — **autonomous closed-loop researcher for NSE equities/F&O**. Qlib = alpha DSL + CPU GBDT + backtest; RD-Agent = propose→code→backtest→reflect loop (heavy lift = external LLM).
7. *(Optional)* **neat-python** (BSD, active) — cheap **neuroevolution genome type** to diversify the population.

Why: DEAP+gplearn+vectorbt = fully-CPU, fully-owned evolutionary core where **the 85-column journal's realized PnL + per-symbol Bayesian confidence become the fitness function**. LLM layer = "intelligent mutation," FinRL adds learned-policy candidates, Qlib+RD-Agent = NSE autonomous research loop — each output normalized into a NodeProtocol node. Freqtrade/Jesse = crypto execution+Hyperopt leg; OpenEngine/OpenAlgo = NSE execution leg; both feed the same fitness journal.

**Caveats:** gpquant, AlphaForge, mosquito are stale; alphagen/AlphaForge/QuantaAlpha/gpquant have **no license file** (fine to reference/reproduce privately, riskier to vendor verbatim); backtrader effectively unmaintained; QuantEvolve has no confirmed repo (design blueprint only). vectorbt is open-core (PRO paid). Stars/licenses verified via GitHub API 2026-06-28.
