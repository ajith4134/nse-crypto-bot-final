---
title: Brain Stitch Gap-Map — chat projects vs. our brain, reuse-first plan
source: research/brain-features-chat.md compared against live code (trading/brain, memory, core, cognition, vendor)
date: 2026-06-29
method: two recon passes — (A) live-code inventory, (B) prior blueprint/OSS docs (t8-*.md, ml-network-*.md)
rule: reuse-first (clone+adapt real code; write own only where nothing exists), CPU-first, NodeProtocol+dashboard+test
---

# Brain Stitch Gap-Map

Comparison of every project/idea in `research/brain-features-chat.md` against what our
brain already implements, with a reuse-first plan for each gap. Status legend:

- **HAVE** — already implemented in our code (file named).
- **PARTIAL** — a piece exists; needs extension to match the chat's intent.
- **MISSING** — nothing in our code does this yet.

The headline finding: our brain already covers ~20 of the chat's capabilities. The
**only genuinely MISSING** capabilities are **world-model / imagination** and
**MuZero-style planning**. Everything else is HAVE or PARTIAL.

---

## 1. Capability-level map (the important table)

| Chat capability | Status | Where it lives / plan |
|---|---|---|
| Episodic memory | **HAVE** | `trading/brain/experience.py` (LanceDB case recall), `memory/human_memory.py` (Ebbinghaus decay) |
| Semantic memory | **HAVE** | `memory/brain.py` (vector+graph PPR/RRF), `trading/brain/semantic.py` (mem0) |
| Procedural memory / skill library | **HAVE** | `trading/brain/skills.py` (quality-gated `SkillLibrary`) — Voyager pattern |
| Reflection / Reflexion | **HAVE** | `trading/brain/selfeval.py` (`AutoQuiz` + `reflect`) |
| Experience replay | **HAVE** | `trading/brain/continual.py` (`ReplayBuffer`, P&L-weighted retrain) |
| Self-improvement | **HAVE** | `trading/brain/selfimprove.py` (hill-climb + DSPy gate) |
| Meta-learning (MAML) | **HAVE** | `trading/brain/metalearn.py` (warm-start per symbol/regime) |
| RL exit / dynamic stoploss | **HAVE** | `trading/brain/rl_exit.py` (tabular Q), `entryexit.py` (regime/anomaly gates) |
| Trailing / tail-gating profits | **HAVE** | `research/trailing-exit-systems.md` + `rl_exit.py` + strategy trailing |
| Regime detection | **HAVE** | `trading/brain/regime.py` (GaussianHMM) |
| Entry / direction learning | **HAVE** | `continual.py` (OnlineNode drift-aware) + `metalearn.py` |
| Pattern / motif / anomaly | **HAVE** | `trading/brain/patterns.py` (STUMPY matrix profile + TA-Lib) |
| Research / notes (autonomous) | **HAVE** | `trading/brain/researcher.py`, `news.py`, `sentiment.py` |
| Reasoning search (Tree/Graph of Thoughts) | **HAVE** | `cognition/reasoning.py` (ReAct + ToT over memory) |
| Multi-agent debate | **HAVE** | `cognition/society.py` (bull/bear/risk roles + judge) |
| Surprise + curiosity (active inference) | **HAVE** | `cognition/active_inference.py` (Bayesian KL, info-gain) |
| Global workspace / stream-of-mind | **HAVE** | `cognition/stream_of_mind.py` |
| Identity / affect / mood | **HAVE** | `cognition/identity.py`, `cognition/affect.py` |
| Neuro-symbolic + causal | **HAVE** | `cognition/neuro_symbolic.py` (Datalog + DoWhy) |
| Self-evolving strategies | **PARTIAL** | `skills.py` grows; full DEAP/gplearn/OpenEvolve loop planned in `t8-stitch-blueprint.md` |
| Hypothesis → experiment → update loop | **PARTIAL** | `selfimprove.py` optimizes params; no formal hypothesis ledger (RD-Agent style) |
| **World-model / imagination** | **MISSING** | **← THIS PASS.** Dreamer/World-Models were deferred as "GPU-only". Build CPU forward-model. |
| **Planning (MCTS / MuZero)** | **MISSING** | **← THIS PASS.** Never evaluated. Adapt `muzero-general` MCTS + learned dynamics. |
| Hierarchical RL / options framework | MISSING | Not in chat priority core; defer. |

---

## 2. Project-by-project (the chat's 25 named repos + tiers)

### Memory / learning lists (chat §1, Tier 3)
- **Awesome-Memory-for-Agents, Awesome-Agent-Memory** → episodic/semantic/procedural. **HAVE** (experience/semantic/human_memory). No action.
- **AgentMemory (rohitg00)** → persistent semantic recall. **HAVE** via mem0/LanceDB. No action.
- **MindForge** → layered human memory. **HAVE** (human_memory tiers + dream consolidation). No action.

### Thinking / reasoning (chat §2, §10)
- **Reflexion (noahshinn)** → fail→reflect→store→retry. **HAVE** (`selfeval.py`). No action.
- **Tree-of-Thoughts / Graph-of-Thoughts** → branch→score→select. **HAVE** (`cognition/reasoning.py`). No action.
- **Generative Agents (joonspk)** → memory stream + reflection. **HAVE** (`vendor/generative_agents_memory/memory_stream.py`). No action.
- **CAMEL / MetaGPT / AutoGPT / BabyAGI** → multi-agent/autonomy. **PARTIAL** (`society.py` debate). Keep as reference; deeper orchestration deferred (CrewAI rejected on deps).

### Trading RL (chat §4–§9)
- **FinRL / FinRL-Trading / TradeMaster / RLTrader / RL-agent-trader / PPO crypto** → entry/direction/SL/TP via RL. **HAVE/PARTIAL**: `rl_exit.py` (Q-learning exit) + `continual.py` (entry/direction). Full FinRL policy genomes planned in `t8-strategy-evolution-oss.md`. No new action this pass.
- **machine-learning-for-trading (stefan-jansen)** → reference ecosystem. Reference only.

### World models / planning (Tier 1, Tier 6) — THE GAP
- **World Models (ctallec, worldmodels.github.io)** → observe→build simulator→imagine→act. **MISSING**.
- **DreamerV3 (danijar)** → latent dynamics, train-in-imagination. **MISSING** (was "GPU defer"; we do a CPU-light RSSM-style value/dynamics).
- **MuZero (werner-duvaud/muzero-general)** → learned dynamics + MCTS planning without rules. **MISSING**.
- **PLAN (this pass):** clone `muzero-general` (done → `vendor/muzero_general/`), adapt its **MCTS** (pure-Python `Node`/`MinMaxStats`/`ucb_score`/`backpropagate`) + **MuZeroFullyConnectedNetwork** (representation/dynamics/prediction) into a CPU-first `trading/brain/worldmodel.py`:
  - `MarketWorldModel` — learned latent market dynamics. **torch backend** (faithful MuZero-FC, scalar value/reward simplification for CPU speed) + **numpy fallback** (ridge transition+reward) so it never blocks (never-skip).
  - `ImaginationPlanner` — MCTS over a trade action set {HOLD, ENTER_LONG, ENTER_SHORT, EXIT, TIGHTEN_STOP, SCALE_OUT}; rolls the model forward to score entry/SL/TP/trailing *before acting*; returns best action + imagined trajectory + predicted R distribution.
  - `WorldModelNode(BaseNode)` — NodeProtocol face: `predict_proba` = P(positive-R) from the value head; self-registers in `core/registry.py`.
  - Stitch into `trading/brain/pipeline.py` `decide()` as a what-if imagination gate; dashboard panel `BrainWorldModel.jsx` + `/api/brain/worldmodel` endpoint; smoke test in `tests/` with isolated `STATE_DIR`.

### Embodied / self-improving / cognitive arch (Tier 4, 5; chat §20–25)
- **CARLA / CarDreamer / Procgen / Voyager** → embodied skill growth. Voyager skill-library pattern **HAVE** (`skills.py`); embodied sim out of trading scope.
- **OpenCog Hyperon / NARS / SOAR / ACT-R / Sigma / JEPA** → cognitive architectures / world-rep learning. **PARTIAL** (`neuro_symbolic.py`, `active_inference.py`, `thinker.py` cover the functional slices we need). Full AGI archs deferred — capability already approximated.
- **AI-Scientist (sakana) / AI-Researcher (hkuds) / RD-Agent** → hypothesis→experiment→paper loop. **PARTIAL** (`selfimprove.py` + `researcher.py`). Next-pass candidate: a formal **HypothesisLedger** (propose→backtest→measure→update belief), reusing RD-Agent's loop shape over our vectorbt fitness. (Not this pass.)
- **SWE-agent / OpenDevin / RepoMaster** → self-coding. **PARTIAL** (P4.7 NodeProposer plan). Deferred.

---

## 3. Build order (this pass + next passes)

1. **THIS PASS — World-Model + Imagination + MuZero planning** (the only true MISSING core). End-to-end: node + planner + pipeline stitch + dashboard + test.
2. Next — **HypothesisLedger** (AI-Scientist/RD-Agent formal hypothesis tracking) to upgrade the PARTIAL hypothesis→experiment loop.
3. Next — **Self-evolving strategy loop** (DEAP+gplearn+OpenEvolve over vectorbt fitness) per `t8-strategy-evolution-oss.md`, feeding `skills.py`.

Everything else in the chat is already HAVE — no rebuild (reuse-first / no-orphans).

---

## 4. Audit (grep-grounded cross-check) — residual PARTIALs after the 3 builds

The four frontier gaps are BUILT + tested (31 brain tests green): world-model/imagination,
MuZero planning (`worldmodel.py`), hypothesis loop (`hypothesis.py`), self-evolving loop
(`self_evolve.py`). A rigorous item-by-item pass against the chat surfaces residual PARTIALs
that the "fully closed" summary glossed over — recorded here honestly:

- **§6 rich observation for DIRECTION** — funding/OI are *fetched* (`screener/sources.py`) and
  funding is one feature in `experience.py`, but orderbook / order-flow / volume-profile /
  correlations / social-sentiment are **not wired into the brain decision or the world-model's
  8-feature observation**. Highest-value follow-up (it's the user's original ask).
- **§9 tail-gating exits** — world-model *imagines* TIGHTEN_STOP/SCALE_OUT and the wallet supports
  partial reduce, but there is **no live laddered exit engine** (breakeven @+1R, ATR-trail @+2R,
  structure-trail @+4R, scale-out 25/25/50). `research/trailing-exit-systems.md` is the plan.
- **§4 deep-RL policies** — `rl_exit.py` tries stable_baselines3/finrl then falls back to tabular
  Q (numpy); PPO/SAC/TD3/DDPG not active. Entry/direction = online-logistic + MCTS.
- **multi-agent societies** (CAMEL/MetaGPT/AutoGPT/BabyAGI) — only internal debate
  (`cognition/society.py`); no role-team orchestration / autonomous task-decomposition.
- **cognitive architectures** (OpenCog Hyperon/NARS/SOAR/ACT-R/Sigma/JEPA) — functions
  approximated (`neuro_symbolic.py`, `active_inference.py`, `thinker.py`); frameworks not integrated.
- CORRECTLY OUT OF SCOPE: embodied AI (CARLA/CarDreamer), quantum/physics AI-scientists.
- CONFIRMED HAVE (doubted, then verified): recursive self-improvement / self-coding —
  `cognition/self_coding.py` + `cognition/_sandbox_worker.py` + `run_self_coding_p47.py`.

**Recommended next build (highest value, = user's original ask):** wire the rich observation
features (funding/OI/orderbook from the screener) into the world-model observation + decision,
then implement the live R-laddered tail-gating exit engine.
