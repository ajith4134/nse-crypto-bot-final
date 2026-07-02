# Brain Activation Map (audit 2026-06-30, branch feat/trading-t8)

Goal: connect every NN/brain feature live + to the dashboard; load all strategies to Freqtrade.
Key fact: almost NOTHING is dep-blocked — torch, scipy, deslib, mapie, playwright+chromium,
paddleocr, deap, river, langgraph all installed in `.venv`. "Demo" = wiring (snapshot vs loop) +
data (synthetic vs real journal/OHLCV), not missing capability. Only OmniParser (GPU) + TabPFN
(token) genuinely unavailable.

## Three subsystems
1. **NN core/routing** (core/, nodes/) — real code, SNAPSHOT-driven: run_*.py write state.json/
   phase3.json; /api/state serves last snapshot. No loop. phase3.json (Hellsemble L2/L3, DESlib,
   conformal, Caruana, deep-cascade, DGMG gate/bus/structure-search) computed but NO endpoint.
2. **Brain-ultra/cognition** (P4.1-4.8) — built; /api/brain/{agent,memory,hybrid,librarian,quiz,
   thinking,stream,autonomy}/status all serve build_demo_*. Chat/agent/thinking LLM-gated.
3. **Trading brain T8** (trading/brain/*) — experience/continual/metalearn/selfeval/patterns/regime/
   picking/news/skills/researcher/rl_exit/pipeline = OFFLINE DEMO via run_brain_t8.build_demo_*,
   NOT in any live loop. Live crypto driver (run_brain_loop→percoin_decider) imports none of them.
   Only TradeOutcomeNet (trade_features.py) is live. BrainTradingPipeline gated BRAIN_LOOP=1 (off),
   stripped (regime/news/experience/strategy=None) even when on.

## Live now ✅
brain loop trading (PID varies; per-coin best strategy→enter_tag /forceenter); TradeOutcomeNet NN;
crypto trades/markets/predictions/watchlist/opentrades/online/candles; computer-use GUI (DOM+OCR
live, disarmed); worldmodel+hypothesis CODE (on synthetic data).

## Gated-off by design 🔒
self-evolve (STRATEGY_EVOLUTION_ENABLED=1; control.py _DEFAULT_ENABLED=False); computer-use arm_live
(paper-first 2-step); LLM (core/llm.py active_model()=None w/o key); GPT-Researcher/DSPy/mem0/Langfuse.

## Data-gated 📡 (86 of 239 strategies)
multi_asset×23, orderbook_l2×23, news×17, ticks×16, fundamentals×9, option_chain×9, iv_greeks×8,
basis×6, open_interest×5. context FII/DII no free feed.

## Strategies→Freqtrade
239 total / 153 executable / 86 data-gated. 80 OHLCV crypto reachable via brain-as-signal (best per
coin→enter_tag). 80 native lib_*.py exist but FT single-strategy (runs no-op MlBridgeStrategy).
ml_decider.py ML models built but PerCoinBrainDecider is the active decider.

## Activation batches (user picked ALL 4)
1. Wire demo→live: flip 8 BrainPanel endpoints + worldmodel/hypothesis to real journal/OHLCV;
   expose phase3.json (routing); ingest freqtrade journal.
2. Live brain loop: BRAIN_LOOP=1 + inject real T8 modules into BrainTradingPipeline; periodic NN re-run.
3. Arm gated-off: STRATEGY_EVOLUTION_ENABLED=1; LLM key wiring (needs user key).
4. Data feeds: wire free feeds (on-chain SOPR/MVRV, fear&greed, RSS news) ; list paid ones.

See [[ml-network-brain]] [[brain-stitch-worldmodel]] [[strategy-library-feature]] [[crypto-trades-need-brain-loop]].
