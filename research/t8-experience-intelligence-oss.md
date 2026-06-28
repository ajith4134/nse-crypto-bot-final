# Agents That Get Smarter With Experience — Research Report for a CPU-First Trading Brain

> Deep-research finding (web search, June 2026). Saved verbatim to prevent loss.
> Context: "experience" = the 85-column trade journal of past trades + realized P&L; realized P&L = the learning signal.
> License info only (private project — do not filter). Stars approx/unverified unless noted.

**Reality check:** nearly all **LLM-native** self-improvement projects were built around large (GPT-4-class) LLMs, not CPU. The *patterns* are CPU-portable; the *reference implementations* mostly are not. Genuinely CPU-runnable building blocks = the classical-ML ones (continual learning / experience replay, MAML-style meta-init, case-based reasoning retrieval, DSPy/GEPA driving a small local model).

---

## 1. Experiential / lifelong / continual learning

### ExpeL — LLM Agents Are Experiential Learners
- paper https://arxiv.org/abs/2308.10144 · code https://github.com/LeapLabTHU/ExpeL · site https://andrewzh112.github.io/expel/
- Agent collects success+failure trajectories into an experience pool, **abstracts cross-task insights in natural language**, recalls similar past trajectories at decision time. (AAAI 2024)
- few-hundred stars (unverified). License: check repo. LLM-driven (insight extraction); insight DB + kNN recall is CPU-trivial.
- **Maps:** single closest blueprint. Journal rows = trajectories; insight extraction = mining rules from wins/losses ("breakouts after 2pm IST on low-volume NSE names lose"); recall = retrieve analogous past trades before deciding. Insight store rises in quality as trades accumulate.

### "Welcome to the Era of Experience" (Silver & Sutton, 2025)
- https://storage.googleapis.com/deepmind-media/Era-of-Experience%20/The%20Era%20of%20Experience%20Paper.pdf
- Position paper: agents should learn continually from their own streams of experience with environment-grounded reward. No code.
- **Maps:** the north star — realized P&L = the environment reward; trade stream = the experience stream. Framing, not implementation.

### Continual learning / experience replay (River, EWC, rehearsal)
- experience replay for CL https://papers.nips.cc/paper/8327-experience-replay-for-continual-learning · plasticity loss https://arxiv.org/pdf/2503.20018 · tabular CL (TRIL3) https://www.sciencedirect.com/science/article/pii/S095219762500908X · CL/EWC guide https://www.meta-intelligence.tech/en/insight-continual-learning
- Replay buffers, EWC regularization, parameter isolation to learn new regimes without forgetting. **CPU-native** (River, tabular replay).
- **Maps:** NodeProtocol nodes are tabular models. A replay buffer of past trade feature-vectors (sampled by recency + P&L magnitude) stops nodes forgetting prior regimes when retrained on fresh trades. Concrete catastrophic-forgetting defense.

---

## 2. Growing skill libraries

### Voyager — Open-Ended Embodied Agent
- paper https://arxiv.org/abs/2305.16291 · code https://github.com/MineDojo/Voyager (MIT)
- First LLM lifelong-learning agent with **ever-growing skill library of executable code**, automatic curriculum, iterative self-verification of skills; skills interpretable/compositional, compound abilities, alleviate forgetting.
- ~5k+ stars (approx). MIT. GPT-4 blackbox queries (LLM-heavy); skill-library store/retrieval is CPU-light.
- **Maps:** canonical "growing skill library." Each reusable strategy (parameterized entry/exit playbook validated on journal trades) = a stored retrievable "skill." New strategies written, back-tested against journal, admitted only if they raise realized P&L. Self-verification = commit a strategy only after a journal back-test gate.

### Generative Agents — memory stream + reflection
- synthesis https://lilianweng.github.io/posts/2023-06-23-agent/
- Episodic **memory stream** with importance + recency + relevance scoring, periodic **reflection** synthesizing higher-level insights. LLM for reflection; scored store CPU-native.
- **Maps:** retrieval scoring (recency × relevance × importance) = how to rank which *past trades* to surface; importance = |realized P&L| or surprise. Periodic reflection = nightly consolidation of the day's trades into durable lessons.

---

## 3. Self-improving / self-reflective / self-modifying agents

### Reflexion — Verbal RL
- paper https://arxiv.org/abs/2303.11366 · code https://github.com/noahshinn/reflexion (NeurIPS 2023)
- Agent verbally reflects on feedback, stores reflective text in episodic memory to improve next trial — no weight updates. ~2k+ (approx). MIT (unverified). LLM-driven; buffer CPU-light.
- **Maps:** after each closed trade, generate a short reflection keyed to P&L ("exited too early; trailing stop too tight"); prepend relevant reflections to next decision. "Semantic gradient" = realized P&L sign/magnitude.

### STOP — Self-Taught Optimizer
- https://arxiv.org/abs/2310.02304 (Zelikman et al., MSR)
- Seed "improver" program uses an LM to improve solutions, then **improves itself** under a utility function (proposes beam search, genetic, SA). LM weights unchanged — scaffold self-improvement.
- **Maps:** utility = realized-P&L back-test score; improver rewrites strategy-selection / feature-engineering code, keeps versions beating the journal back-test.

### Gödel Agent — recursive self-improvement
- https://arxiv.org/abs/2410.04444 (ACL 2025)
- Self-referential framework that **dynamically modifies its own logic** guided only by high-level objectives. LLM-driven.
- **Maps:** aspirational ceiling — brain rewrites its own routing/decision policy toward "maximize risk-adjusted P&L." Risky on live capital; gate behind paper-trade + back-test acceptance.

### ADAS — Automated Design of Agentic Systems (Meta Agent Search)
- paper https://arxiv.org/abs/2408.08435 · code https://github.com/ShengranHu/ADAS (ICLR 2025)
- Meta agent iteratively **programs new agents in code** against a growing archive; invented agents transfer across domains. LLM-driven; archive CPU-light.
- **Maps:** archive-of-designs = versioned library of brain configurations (node ensembles, routing topologies); each candidate evaluated on journal back-tests, best retained. How the 320-node topology self-improves.

### DSPy optimizers (MIPROv2, COPRO, SIMBA, BootstrapFewShot)
- https://dspy.ai/api/optimizers/MIPROv2/ · https://github.com/stanfordnlp/dspy
- "Declarative Self-improving Python" — compiles LLM programs by auto-optimizing instructions + few-shot demos against a **metric** (Bayesian opt / bootstrapping). ~20k+ (approx). MIT (unverified). **Can run against a small local CPU LLM** (Ollama/llama.cpp).
- **Maps:** if any brain component uses a small local LLM to reason over trade context, DSPy lets it measurably self-improve as the journal grows, with realized P&L as the compile-time metric.

### GEPA — Reflective Prompt Evolution
- paper https://arxiv.org/abs/2507.19457 · code https://github.com/gepa-ai/gepa · `dspy.GEPA` (ICLR 2026 oral)
- Merges NL reflection with **multi-objective (genetic-Pareto) evolutionary search** over prompts; reflects on rollout trajectories. Beats GRPO ~6–20% with up to **35× fewer rollouts**; improves with ~10 examples. `pip install gepa`.
- Rollout-efficient — far cheaper than RL; viable with a local model on CPU (slow but feasible).
- **Maps:** **most sample-efficient** self-improvement optimizer here — crucial because trades accrue slowly. Evolve decision prompts against realized P&L with few examples; Pareto = return vs drawdown tradeoff.

### Promptbreeder — self-referential prompt evolution
- https://arxiv.org/abs/2309.16797 (DeepMind, ICML 2024). Evolves task-prompts AND mutation-prompts. No official code. LLM-driven.
- **Maps:** secondary to GEPA (less sample-efficient); same role.

---

## 4. Curriculum learning & open-endedness

### POET / Enhanced POET
- POET https://arxiv.org/abs/1901.01753 · Enhanced POET https://arxiv.org/abs/2003.08536 (Uber AI)
- Co-evolves **environments (challenges) and their solutions** with stepping-stone transfer — endless auto-generated curriculum. Classic neuroevolution — **CPU-feasible** at small scale (no LLM).
- **Maps:** generate an expanding curriculum of synthetic/historical market scenarios (regimes, vol bands, NSE vs crypto sessions) of rising difficulty; strategies solving harder regimes transfer back. CPU-native open-endedness for robustness.

### AutoManual — instruction manuals via interactive learning
- https://arxiv.org/abs/2405.16247 (NeurIPS 2024)
- Planner/Builder/Formulator agents distill interaction into an **online-updated rule set / manual**, verified against new episodes. LLM-driven; rule store CPU-light.
- **Maps:** living "trading manual" — rules mined + online-corrected from journal outcomes (Builder updates a rule when a trade contradicts it). Auditable growing rulebook keyed to P&L.

---

## 5. Memory-of-experience driving better decisions

### FinMem & FinAgent — LLM trading agents with layered memory
- FinMem paper https://arxiv.org/abs/2311.13743 · code https://github.com/pipiku915/FinMem-LLM-StockTrading · survey https://arxiv.org/html/2408.06361v2
- Profiling + layered Memory (short/mid/long, scored by recency/relevance/importance) + Decision modules. FinAgent adds multimodal + layered reflection. LLM decisions; **layered memory + retrieval design is the reusable CPU-light artifact**.
- **Maps:** closest finance-specific template. Adopt layered-memory + recency/relevance/importance retrieval for the 85-col journal; importance = realized P&L magnitude. Related: TradingAgents (https://arxiv.org/html/2412.20138v1), TradingGroup w/ self-reflection + data-synthesis (https://arxiv.org/pdf/2508.17565).

### Case-Based Reasoning for LLM agents
- review https://arxiv.org/abs/2504.06943 · CBR-LLM https://www.emergentmind.com/topics/case-based-reasoning-augmented-large-language-model-cbr-llm
- Retrieve the most **analogous past case + its outcome**, adapt to the new situation; strong explainability. **CPU-native** retrieval (embeddings/kNN); LLM optional for adaptation.
- **Maps:** each journal trade = a "case" (features → action → P&L). Before a new entry, retrieve k most-similar historical setups, weight decision by their realized outcomes. Pure CPU, auditable; accuracy rises mechanically as the case base grows — **strong low-risk first build.**

### Retrieval-Augmented Memory / RARL for online learning
- https://arxiv.org/pdf/2512.02333 · https://arxiv.org/pdf/2202.08417
- Augment a small policy/model with a retrieval buffer of past experiences at decision time — data efficiency w/o retraining. **CPU-feasible.**
- **Maps:** lets a small CPU model "remember" rare past trades it wasn't retrained on.

---

## 6. Meta-learning / learning-to-learn (sample efficiency)

### MAML & meta-learning for financial time series
- zero-shot financial forecasting https://arxiv.org/abs/2504.09664 · few-shot TS https://dl.acm.org/doi/abs/10.3233/JIFS-212228 · MAML survey https://dl.acm.org/doi/10.1145/3659943
- Learn an **initialization that adapts to a new task in a few steps** — built for limited-data regimes; recent work targets turbulent/zero-shot financial series. Small models **CPU-feasible**.
- **Maps:** each ticker/regime/session = a "task." Meta-learn an init across the journal so a node adapts to a *new* symbol or fresh regime from a handful of recent trades — directly raising sample-efficiency. Principled answer to "few trades per symbol."

---

## 7. Other "gets smarter with experience" paradigms

### Darwin Gödel Machine (DGM)
- paper https://arxiv.org/abs/2505.22954 · code https://github.com/jennyzzt/dgm (Sakana AI, 2025)
- Self-modifying coding agent maintaining an **archive of generated agents**; samples one, uses a foundation model to produce an improved variant, empirically validates it — open-ended (Darwinian) self-improvement. LLM-heavy.
- **Maps:** archive + empirical-validation loop = template for evolving brain code: population of brain variants, mutate via LLM, accept only those beating journal back-tests. (Project's own MEMORY references a "DGMG / trainable-network" design — DGM is the closest published analog.)

### AlphaEvolve
- overview https://www.alphaxiv.org/overview/2505.22954v2 · DeepMind (May 2025)
- Gemini-powered **evolutionary coder**; rediscovered 75% / improved 20% of SOTA on tested problems. Large-LLM + heavy eval — **not CPU**.
- **Maps:** reference for evolve-and-empirically-verify; open analog = OpenEvolve (community reimpl).

---

## TOP PICKS TO STITCH — a CPU-runnable experience → intelligence loop

Goal: brain measurably improves stock/entry/exit decisions the more it trades; realized P&L = single learning signal; an auto-quiz proves accuracy rises over time. Build order:

**Layer A — Episodic Experience Bank (build first; pure CPU)**
- **Case-Based Reasoning** (https://arxiv.org/abs/2504.06943) + **FinMem layered memory** (https://github.com/pipiku915/FinMem-LLM-StockTrading) + **Generative-Agents retrieval scoring** (recency × relevance × importance).
- Index every journal row (85 cols) as a "case" w/ embedding; importance = |realized P&L|/surprise. Before any decision, retrieve k analogous historical setups and bias the decision by their outcomes. Accuracy grows mechanically; fully auditable. **Lowest risk, highest immediate value.**

**Layer B — Growing Skill/Strategy Library (Voyager pattern, CPU store)**
- **Voyager skill library** (https://github.com/MineDojo/Voyager) + **AutoManual online rules** (https://arxiv.org/abs/2405.16247) + **ExpeL insight extraction** (https://github.com/LeapLabTHU/ExpeL).
- Each validated strategy = a stored parameterized retrievable "skill"; a Builder mines/updates rules from journal outcomes; admission gate = must improve back-tested P&L.

**Layer C — Self-Evaluation + Self-Improvement Cycle (the auto-quiz)**
- **Reflexion** (https://github.com/noahshinn/reflexion) per-trade reflections + **GEPA** (https://github.com/gepa-ai/gepa, ~35× fewer rollouts) sample-efficient optimizer + **STOP/ADAS archive** idea (https://github.com/ShengranHu/ADAS).
- Nightly: (1) Reflexion notes keyed to each closed trade's P&L; (2) **auto-quiz** — replay held-out recent setups, predict, score vs realized outcomes, log accuracy-over-time to prove the curve rises; (3) GEPA evolves decision prompts/program against P&L with few examples.

**Layer D — Continual Learning guard + Meta-learning (CPU)**
- **Experience replay / River** (https://arxiv.org/pdf/2503.20018, https://papers.nips.cc/paper/8327-experience-replay-for-continual-learning) + **MAML meta-init for financial series** (https://arxiv.org/abs/2504.09664).
- Retrain NodeProtocol nodes on fresh trades while replaying a P&L-weighted buffer of old regimes (anti-forgetting); meta-learn an init across tickers/regimes so a new symbol/regime adapts from a handful of trades.

**Optional Layer E — Open-ended robustness & topology evolution (later)**
- **POET/Enhanced POET** (https://arxiv.org/abs/2003.08536, CPU neuroevolution) for a curriculum of harder synthetic/historical regimes; **DGM archive loop** (https://github.com/jennyzzt/dgm) to evolve the 320-node topology — both gated behind paper-trade + back-test acceptance before live capital.

**Single learning signal across all layers:** realized P&L (sign = improvement direction, magnitude = importance weight, risk-adjusted variant for Pareto optimizers). **Proof-of-improvement:** the Layer-C auto-quiz logging held-out predictive accuracy + back-tested P&L vs trade count over time.

### Caveats
- Stars/several licenses **approx/unverified** — confirm per repo.
- AlphaEvolve and (largely) DGM/ADAS/STOP/Promptbreeder used large/proprietary LLMs — **pattern sources**, not CPU drop-ins. CPU-native core = Layers A, B (storage), D, E-POET, plus DSPy/GEPA driving a small local model for Layer C.
- "Self-modifying" agents editing live trading logic are high-risk; always gate behind back-test + paper-trade acceptance.
