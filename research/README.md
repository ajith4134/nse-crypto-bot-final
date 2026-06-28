# research/ — saved web-research findings (durable, never lose)

Token-expensive online research is saved here **verbatim and immediately** so no
information is lost across context windows or workflow failures. Always persist
research output to a file in this directory the moment an agent/workflow returns.

## T8 strategy + brain research (2026-06-28)
- [t8-strategy-evolution-oss.md](t8-strategy-evolution-oss.md) — OSS for strategy creation/mutation/evolution (genetic/GP, RL, AutoML/alpha, LLM-driven, NEAT, backtesters) for crypto + NSE; TOP PICKS TO STITCH (DEAP + gplearn + vectorbt + OpenEvolve/QuantaAlpha + FinRL + Qlib/RD-Agent).
- [t8-brain-ultra-features-oss.md](t8-brain-ultra-features-oss.md) — OSS brain capabilities: memory (mem0/Letta/Cognee + LanceDB/Qdrant), continual learning (River), autonomous news research (GPT-Researcher + FinBERT), pattern/regime (STUMPY/hmmlearn/TA-Lib), asset/entry/exit (Qlib/Alphalens/FinRL), dashboard observability (Langfuse/Phoenix), multi-agent (LangGraph/TradingAgents).
- [t8-experience-intelligence-oss.md](t8-experience-intelligence-oss.md) — agents that get smarter with experience: ExpeL, Voyager skill library, Reflexion, STOP/ADAS/Gödel/DGM, DSPy/GEPA, POET, FinMem, CBR, MAML; CPU-runnable experience→intelligence loop (Layers A–E).

## "Go online" research (2026-06-28) — live paper trading + toggles + editable paper money
- [online-nse-offhours-paper-trading.md](online-nse-offhours-paper-trading.md) — how OSS NSE bots paper-trade off-hours (calendar-gated LIVE↔REPLAY, candle/tick replay, synthetic ticks, OpenAlgo analyzer fed cached prices).
- [online-market-toggles-paper-real-switch.md](online-market-toggles-paper-real-switch.md) — per-market on/off + safe paper↔real switch (per-market state objects, mode=adapter, Nautilus ACTIVE/REDUCING/HALTED gate, confirmed transitions, mode-tagged IDs).
- [online-editable-paper-money-engine.md](online-editable-paper-money-engine.md) — editable per-market paper wallets (set/top-up/reset, pluggable fill/slippage/fee/margin reality models, persistence + isolation, leaderboard).
- [online-alwayson-loop-and-features.md](online-alwayson-loop-and-features.md) — always-on loop (crypto 24/7 WS + NSE scheduler-gated replay) + prioritized feature list (protections, two-way Telegram, hot-reload, APScheduler).

## Provenance / cost note
- Source: 3 parallel web-research agents (real WebSearch/WebFetch), after the deep-research
  Workflow harness repeatedly failed on a structured-output retry cap (>1M tokens wasted on
  failed runs). Direct agents are the reliable path; these reports are the recovered output.
- Stars/licenses verified or marked approx/unverified per the source files; **license is NOT a
  selection filter** (private non-published project — see memory `no-license-filter`).

## Synthesis → T8 blueprint
These three feed **[`t8-stitch-blueprint.md`](../t8-stitch-blueprint.md)** (repo root) — the
stitch-into-one Phase-T8 architecture (strategy-evolution engine + ultra-brain upgrades),
with module layout, the DEAP/journal-fitness evolution loop, overfitting guardrails
(walk-forward / deflated Sharpe / PBO), the experience→intelligence loop, crypto-vs-NSE
handling, a 9-step build plan, and dependency list. Review before building.
