# Strategy-Creator → Brain: real trade-selection architecture map + gap

Resumed from the interrupted "strategy creator feature to brain" session (2026-07-06). The two
background agents that died were **"Research SOTA strategy generation OSS"** and **"Map real
trade-selection architecture."** Both jobs are done here — and the conclusion flips the framing.

## TL;DR — it's a WIRING gap, not a capability gap
The project already has a SOTA strategy-**creation** stack. What's missing is the wire that lets a
brain-**created** strategy actually enter the set the live executor picks from. Don't build another
generator — **close the loop.**

## The real crypto trade path (what actually opens trades)
```
broker-sense funnel  (THE trade driver — trade-driver-is-funnel memory)
  → shortlist candidates: broker-native ranked pickers (fusion) + indicator_fusion + MTF vote
  → BrainExecutor (trading/crypto/freqtrade/brain_executor.py)
      → PerCoinBrainDecider (percoin_decider.py): backtest × brain, best strategy PER COIN
          → strategy universe = LibraryBrainDecider.strategies()
              = trading.strategy.library.registry.get_registry().executable()   ← STATIC LIBRARY
```
Journal evidence: `strategy_name` ∈ {MlBridgeStrategy, momentum, meanrev_stochrsi, force_entry,
mom_trix, mom_stochastic} — all pre-existing library strategies. No foundry/generated ids appear.

## The strategy-CREATION stack (rich, but off to the side)
- `trading/strategy/foundry.py` (+ `foundry_advanced.py`) — seed catalog + online research
  (`research_segment` via AutonomousResearcher) + performance ledger (`strategy_foundry.json`).
- `trading/strategy/generators/` — 6 SOTA generators: symbolic (gplearn/PySR), alpha_mining,
  llm_mutation, quality_diversity (pyribs), optuna_tune, rd_agent + stats_gate (CPCV/DSR).
- `trading/strategy/evolve.py` (DEAP NSGA-II) + `self_evolve.py` — genetic evolution → admits
  guardrail-passed survivors into the **SkillLibrary**.
- Bridges that EXIST but target the wrong decider:
  - `evolved_link.py` → sets `BrainTradingPipeline.evolved_strategy` (NOT percoin_decider).
  - `registry.py` → promotes an evolved Strategy to a NodeProtocol `StrategyNode` (for the ML
    network / dashboard), NOT into `library.registry.executable()`.

## THE GAP (root finding)
The live executor reads **`trading.strategy.library.registry`**. Created strategies land in a
**different** store (`SkillLibrary` / `StrategyRegistry` / `BrainTradingPipeline`). The two are not
the same object, so **brain-created strategies never compete for real trades.** The brain "creates"
strategies that can only ever appear on the dashboard + ledger.

## Recommendation — close the loop (one wire, high value)
When the foundry / 6 generators / genetic evolution produce a strategy that **passes the existing
CPCV + DSR + guardrail gate**, register it INTO `trading.strategy.library.registry` as an
`executable()` strategy (with its unique foundry id as `enter_tag`), so:
1. `percoin_decider` immediately includes it in the per-coin backtest×brain ranking, and
2. it can win live entries and be tracked by outcome — the ledger `promote()`/prune loop then
   keeps only the genuinely profitable created strategies (ties into the profitability-based
   explore graduation just shipped).

This is a glue/adapter task (`freqtrade_adapter.py` + `library/registry.py` already model the
executable-strategy interface), NOT new generator research.

## SOTA-OSS research verdict
We have 6 modern generators already (symbolic regression, QD, LLM-mutation, alpha-mining,
Bayesian-tune, RD-Agent) + DEAP evolution + CPCV/DSR gating — this is at/above current OSS SOTA for
CPU-first strategy synthesis. Adding another generator library would be low-value until the wiring
loop is closed. Revisit OSS (e.g. new alpha-factor libs) only after created strategies are proven to
reach and win real trades.

## Status
Report only — no code changed for this feature (PROPOSE→APPROVE). Awaiting owner decision on
building the closing wire.
