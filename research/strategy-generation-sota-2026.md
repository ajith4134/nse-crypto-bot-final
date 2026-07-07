# Strategy-Generation SOTA vs our DEAP NSGA-II engine (2026-07-06)

Research scan triggered by connecting the evolution/mutation engine to the brain.
Question: is DEAP NSGA-II fixed-genome evolution top-grade, or are there better OSS
strategy creator / evolution / mutation approaches to adopt?

## Bottom line
- DEAP NSGA-II fixed-genome evolver = solid, standard baseline, **NOT the 2023-2026 frontier**.
- Core limit: **fixed genome** — only recombines/tunes a pre-specified rule template; cannot
  evolve the expression/structure itself.
- Our **evaluation/guardrail stack (CPCV + Deflated Sharpe + PBO) IS current SOTA** — keep it;
  make it the shared fitness oracle for every new generator.
- Recommended posture: **do NOT replace DEAP** — keep it as one generator + the param-tuning
  layer, and ADD 2-3 structurally stronger generators, all scored through our CPCV/DSR/PBO gate.

## Ranked shortlist (top 5)
1. **AlphaGen / AlphaForge** — formulaic-alpha mining (RL / GFlowNet). Discovers decorrelated
   SETS of novel formulaic alphas optimized for combined IC. github.com/RL-MLDM/alphagen ,
   github.com/DulyHao/AlphaForge (AAAI-2025, beats AlphaGen). HIGHEST priority. ADD.
2. **LLM-as-mutation-operator** (FunSearch/AlphaEvolve) via OpenEvolve /
   pwb-alphaevolve. Hypothesis-driven code edits from an LLM instead of blind bit-flips;
   evolves CODE not just genome params. We already have core/llm.py 12-provider failover.
   github.com/algorithmicsuperintelligence/openevolve , github.com/paperswithbacktest/pwb-alphaevolve.
   ADD — can even become NSGA-II's mutation operator (minimal-risk hybrid).
3. **PySR symbolic regression** — evolves the expression TREE itself (strictly more expressive
   than tuning a template); fast CPU-first Julia engine, built-in accuracy-vs-complexity
   multi-objective. github.com/MilesCranmer/PySR. ADD as factor-discovery generator.
   (Lighter pure-Python alt: gplearn.)
4. **pyribs — Quality-Diversity / MAP-Elites (MOME)** — returns an illuminated ARCHIVE of
   behaviorally-diverse high-performers (holding-period × turnover × regime) instead of a
   Pareto front that collapses to near-duplicates → far better, regime-robust skill library.
   github.com/icaros-usc/pyribs. ADD as archive/selection layer.
5. **Microsoft RD-Agent(Q) + Qlib** — autonomous multi-agent quant researcher; co-optimizes
   factors AND models (~2x ARR, 70% fewer factors reported). github.com/microsoft/RD-Agent ,
   github.com/microsoft/qlib. ADD as heavier optional tier when LLM budget allows.

## Per-family notes
- **GP / symbolic regression**: PySR (best) / gplearn (light). More expressive than fixed genome. ADD.
- **Formulaic-alpha mining**: AlphaGen/AlphaForge/AlphaSAGE/alpha-gfn/Alpha2; RD-Agent heavyweight. Biggest capability jump (decorrelated alpha SETS). ADD, top priority.
- **LLM-driven**: (a) multi-agent debate traders TradingAgents/FinRobot/QuantAgent — overlaps our brain-chat/boss. (b) LLM-as-mutation-operator OpenEvolve/pwb-alphaevolve/OpenELM/EvoPrompt — the one that beats fixed genome. ADD (b).
- **RL policy search**: FinRL + Stable-Baselines3 (best), TensorTrade (stale). Produces POLICIES (sizing/timing/execution) — complementary output type, lower priority, overfit-prone (CPCV essential).
- **AutoML / QD**: Optuna (NSGA-III/CMA-ES, near-drop-in for tuning sub-step); pyribs (QD/MAP-Elites — the architecturally interesting upgrade).
- **Overfitting eval**: we're at SOTA (CPCV+DSR+PBO, confirmed by 2024 study S0950705124011110). Optional adds: White's Reality Check + Hansen's SPA (family-wise error control across many generators) — mlfinlab OSS commits have PBO/CPCV/DSR reference code.

## Key sources
AlphaGen github.com/RL-MLDM/alphagen · AlphaForge github.com/DulyHao/AlphaForge ·
RD-Agent github.com/microsoft/RD-Agent · Qlib github.com/microsoft/qlib ·
OpenEvolve github.com/algorithmicsuperintelligence/openevolve · pwb-alphaevolve
github.com/paperswithbacktest/pwb-alphaevolve · PySR github.com/MilesCranmer/PySR ·
gplearn github.com/trevorstephens/gplearn · pyribs github.com/icaros-usc/pyribs ·
FinRL github.com/AI4Finance-Foundation/FinRL · SB3 github.com/DLR-RM/stable-baselines3 ·
Optuna github.com/optuna/optuna · mlfinlab github.com/hudson-and-thames/mlfinlab ·
Backtest-overfitting study (2024) ScienceDirect S0950705124011110 ·
Deflated Sharpe (Bailey & López de Prado) davidhbailey.com/dhbpapers/deflated-sharpe.pdf
