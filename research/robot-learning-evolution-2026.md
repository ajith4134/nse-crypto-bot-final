# How Robots Learn & Evolve → Trading-Brain Self-Evolution (research, 2026-07)

Current (2023–2026) open-source projects & techniques for how robots/embodied agents learn
and evolve, mapped onto our CPU-first self-evolving trading brain
(`trading/brain/self_evolve.py`, `worldmodel.py`, `hypothesis.py`, the Strategy Foundry,
the Voyager skill library). Stars/activity verified via GitHub API on 2026-07-02. Honest on
maturity — hype flagged inline.

Legend: **CPU** = runs on CPU without GPU · **GPU-pref** = works on CPU but slow / GPU intended ·
**GPU-only** = impractical without accelerator.

---

## (a) Lifelong / continual learning (avoid catastrophic forgetting)

### 1. Avalanche — ContinualAI
- Repo: https://github.com/ContinualAI/avalanche · ~2.06k★ · MIT · active (pushed 2025-03) · PyTorch-ecosystem.
- What: End-to-end continual-learning library. 5 modules (Benchmarks, Training, Evaluation,
  Models, Logging). Ships ready strategies against catastrophic forgetting: **EWC, Synaptic
  Intelligence, LwF, replay/rehearsal, GEM/A-GEM, GDumb**. Also `avalanche-rl` fork for
  continual RL.
- CPU/reuse: **CPU** — replay + regularizers on small MLPs/heads are cheap; pip-installable
  (`pip install avalanche-lib`). Mature, most-adopted CL framework. Solid reuse.
- Trading map: wrap `TradeOutcomeNet` / the online heads as an Avalanche `strategy` so the brain
  learns new market regimes as CL "experiences" without forgetting old ones — kills the
  fine-tune-forgets-last-regime problem in the self-evolve loop.

---

## (b) Open-ended / autotelic / curiosity-driven self-improvement

### 2. OMNI-EPIC — Faldor/Clune (ICLR 2025)
- Repo: https://github.com/maxencefaldor/omni-epic · ~78★ · Apache-2.0 · (research code, pushed 2024-12).
  Predecessor OMNI: https://github.com/jennyzzt/omni (~66★, MIT).
- What: **Open-endedness via Models of human notions of Interestingness, Environments Programmed
  in Code.** An LLM acts as a "model of interestingness" that *generates new tasks/environments
  as code*, keeping only tasks that are both *learnable AND interesting* (novel + worthwhile),
  then trains on them — an AI-generating-algorithm loop.
- CPU/reuse: LLM calls are API/CPU-side (fits our free-cloud-LLM setup); the RL training in the
  paper is sim/GPU-pref, but the **task-proposal + interestingness-filter** logic is the reusable,
  CPU-friendly part. Research-grade maturity, not a product.
- Trading map: this IS the blueprint for the Strategy Foundry's proposer — have the failover LLM
  *generate new strategy hypotheses as code* and gate them by a learnable-AND-interesting filter
  (novel vs. the hypothesis ledger, and showing learning progress) instead of raw backtest PnL.

### 3. MAGELLAN — Flowers/Inria (2025)
- Repo: https://github.com/flowersteam/MAGELLAN · ~14★ · MIT · (research code, pushed 2025-03).
- What: Metacognitive framework letting an **autotelic LLM agent predict its own competence and
  Learning Progress (LP) online**, using *semantic relationships between goals* to generalize LP
  estimates across a large goal space and prioritize what to practice next. Only method in the
  paper that fully masters a large, evolving goal space.
- CPU/reuse: **CPU** for the LP-prediction head + goal-embedding logic (the heavy part is the
  base LLM, which we already offload to free cloud). Small/new but the *idea* is directly liftable.
- Trading map: give `self_evolve.py` an LP predictor — pick which strategy/coin/regime to evolve
  next by *predicted learning progress* (semantic-neighbor generalization over the hypothesis
  ledger) rather than round-robin, so compute goes where the brain is actually improving.

### 4. Quality-Diversity: pyribs (+ QDax)
- pyribs: https://github.com/icaros-usc/pyribs · ~263★ · MIT · **actively maintained** (pushed 2026-06).
- QDax: https://github.com/adaptive-intelligent-robotics/QDax · ~357★ · MIT · active (pushed 2025-10).
- What: Quality-Diversity optimization — instead of one optimum, **illuminate a whole archive of
  diverse high-performing solutions** (MAP-Elites, CMA-ME, CMA-MAE). Robotics uses QD to breed
  behaviorally-diverse controllers (e.g. many gaits).
- CPU/reuse: **pyribs = CPU**, pure-Python/NumPy, no heavy deps, beginner-friendly, low-compute —
  ideal for us. **QDax = GPU-pref** (JAX+Brax, built for accelerators — flag it, prefer pyribs).
- Trading map: run the Strategy Foundry as a MAP-Elites archive — behavior descriptors =
  (holding-period, volatility bucket, market regime), objective = risk-adj return. Keeps a
  *diverse portfolio* of strategies (not one overfit champion), giving the brain robust fallbacks
  across regimes.

---

## (c) Self-improving embodied agents / skill acquisition

### 5. Eureka (+ DrEureka) — NVIDIA (ICLR 2024 / RSS 2024)
- Eureka: https://github.com/eureka-research/Eureka · ~3.17k★ · MIT · (pushed 2024-05).
- DrEureka: https://github.com/eureka-research/DrEureka · ~938★ · MIT · (pushed 2024-08).
- What: **LLM writes reward functions as code**, RL-trains on them, then reads back a "reward
  reflection" (training stats) and *self-edits the reward* — an evolutionary outer loop over reward
  code. Beat human-designed rewards on 83% of 29 tasks. DrEureka extends to sim-to-real
  (auto reward + domain-randomization for real robots).
- CPU/reuse: RL inner loop is IsaacGym/**GPU-only** (flag it) — but the reusable gold is the
  **reward-code-generation + reward-reflection self-improvement loop**, which is CPU/LLM-side.
- Trading map: the brain already self-codes; adopt Eureka's *reflection* step — after each
  backtest, feed key stats back to the LLM to auto-rewrite the strategy's *scoring/exit reward*
  code, iterating in `self_evolve.py` toward rewards that beat hand-tuned ones.

### 6. DreamerV3 — danijar (Nature 2025)
- Repo: https://github.com/danijar/dreamerv3 · ~3.48k★ · MIT · **active** (pushed 2026-05) · pip `dreamerv3`.
- What: General world-model agent — learns a latent world model, then **trains an actor-critic
  purely inside imagined ("dreamed") trajectories**, fixed hyperparameters across 150+ tasks;
  first to mine diamonds in Minecraft from scratch. This is the mature cousin of our MuZero worldmodel.
- CPU/reuse: JAX, **GPU-pref** but explicitly supports `--jax.platform cpu` (small models train on
  CPU, slowly — flag it). Very mature, single-file-ish, well documented.
- Trading map: upgrade `worldmodel.py` — learn a latent market world model and let the brain
  *train/evaluate strategies inside imagined rollouts* before risking paper/live capital; port
  Dreamer's actor-critic-in-imagination as the planning core (we already have the MuZero scaffold).

### Voyager — MineDojo (already vendored; baseline reference)
- Repo: https://github.com/MineDojo/Voyager · ~7.0k★ · MIT · (pushed 2024-04).
- What: LLM lifelong agent = automatic curriculum + **ever-growing skill library of executable
  code** + iterative self-verification prompting. Already the model for our Voyager skill library.
- Trading map: keep as-is; combine with MAGELLAN (curriculum by learning progress) + OMNI-EPIC
  (interestingness filter) to make the curriculum smarter than "next unlocked skill".

---

## (d) Evolutionary robotics / neuroevolution

### 7. EvoTorch — NNAISENSE
- Repo: https://github.com/nnaisense/evotorch · ~1.14k★ · Apache-2.0 · **active** (pushed 2026-06) · PyTorch+Ray.
- What: Scalable evolutionary computation — GA, CMA-ES, PGPE, CEM, distributed via Ray. Neuroevolve
  policies / optimize black-box params without gradients.
- CPU/reuse: **CPU** first-class (PyTorch CPU + Ray for multi-core parallelism) — good fit for our
  CPU-first, no-gradient strategy params. pip-installable, production-quality (NNAISENSE).
- Trading map: replace/augment `trading/strategy/evolve.py` — use EvoTorch CMA-ES/PGPE to evolve
  strategy hyperparameters (thresholds, trailing-stop %, sizing) as a gradient-free population,
  parallelized across CPU cores.

### 8. evosax — Robert Lange
- Repo: https://github.com/RobertTLange/evosax · ~771★ · Apache-2.0 · **active** (pushed 2026-04) · JAX.
- What: 30+ evolution strategies in JAX (CMA-ES, OpenAI-ES, Diffusion Evolution, PGPE, …), clean
  ask/tell API. Companion to neuroevobench benchmark.
- CPU/reuse: JAX runs on **CPU** (jit-compiled, fine for small param vectors) — **GPU-pref** only
  at scale. More ES variety than EvoTorch but adds a JAX dep; pick per the "dep weight by
  capability" rule. (Note: google/evojax is now **archived** — prefer evosax/EvoTorch instead.)
- Trading map: alternative ES engine for the Foundry when we want exotic strategies (Diffusion
  Evolution / novelty search) beyond CMA-ES; same ask/tell loop as EvoTorch.

---

## Maturity / hype honesty
- **Production-grade, safe to vendor now:** Avalanche, pyribs, EvoTorch, DreamerV3, Eureka
  (all >250★, active, permissive licenses).
- **Research code / lift the idea not the whole repo:** OMNI-EPIC (~78★), MAGELLAN (~14★) — small,
  new, papers-first; reuse their *mechanisms* (interestingness filter, learning-progress predictor).
- **Avoid / deprioritize:** google/evojax is **archived**; QDax and Dreamer's RL inner loops are
  GPU-preferred — take the CPU-friendly pieces (pyribs for QD; imagination/reward-reflection logic
  for the LLM loops).
- Recurring, CPU-friendly pattern across all of them and the highest-value adoption for us:
  **generate-as-code → evaluate → reflect/score-by-learning-progress-&-diversity → keep-diverse →
  repeat**, which is exactly the self_evolve + Strategy Foundry + hypothesis-ledger loop.

## Sources
- Avalanche — https://github.com/ContinualAI/avalanche · https://github.com/ContinualAI/avalanche-rl
- OMNI-EPIC — https://github.com/maxencefaldor/omni-epic · OMNI — https://github.com/jennyzzt/omni · https://arxiv.org/abs/2306.01711
- MAGELLAN — https://github.com/flowersteam/MAGELLAN · https://arxiv.org/abs/2502.07709
- pyribs — https://github.com/icaros-usc/pyribs · QDax — https://github.com/adaptive-intelligent-robotics/QDax
- Eureka — https://github.com/eureka-research/Eureka · DrEureka — https://github.com/eureka-research/DrEureka · https://eureka-research.github.io/
- DreamerV3 — https://github.com/danijar/dreamerv3 · https://arxiv.org/abs/2301.04104
- EvoTorch — https://github.com/nnaisense/evotorch
- evosax — https://github.com/RobertTLange/evosax · evojax (archived) — https://github.com/google/evojax
- Voyager — https://github.com/MineDojo/Voyager · https://arxiv.org/abs/2305.16291
