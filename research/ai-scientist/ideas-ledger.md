# AI-Scientist idea ledger (compounding — AgentRxiv style)

_Status legend: proposed · approved · done · rejected. Runs append here; nothing is re-proposed._

## Run 2026-07-04 — FULL CAPACITY, unconstrained (money-lens OFF by owner instruction)

Grounded in: state snapshot (132 deps · 31 vendored OSS · 538 files) + independent audit
(417 modules; `dashboard/server.py` 3777-line god-module; 24 unwired endpoints; unused
`DrawdownAdjustedKelly`; possibly-unwired `nodes/*`) + 2026 SOTA frontier scan.
★ = reuse candidate ALREADY vendored in `vendor/` (low integration cost).

| # | Idea | Type | Why it beats what we have | Reuse | Effort/Risk | Pillar | Status |
|---|---|---|---|---|---|---|---|
| 1 | **Node auto-loader** — pkgutil auto-discovers & registers every `nodes/*` module | wire-up | Audit found node capabilities (advanced_ml, automl, symbolic, quant_factor/signal, denoise, detect…) that may never reach the live pool. Free capability recovery. | stdlib pkgutil | S / Low | 7 | proposed |
| 2 | **Wire `DrawdownAdjustedKelly`** + vol-target blend into live sizing | replace | It's imported but unused today; the most capital-protective sizer sits idle. | keeks ★(installed) | S / Low | 4,22 | proposed |
| 3 | **Split `dashboard/server.py` (3777 L)** into `routes/<domain>.py` | refactor | The most-coupled file (51 deps); unblocks honest-wiring + kills silent endpoint drift. | — | M / Low | 12 | proposed |
| 4 | **"Brain Ops" panel** surfacing the 24 unwired endpoints (autonomy/boss/decisions/sizing/predictions) | new UI | Real brain capabilities you currently cannot see. | add-panel skill | M / Low | 3,12 | proposed |
| 5 | **TSFM ensemble upgrade** — add **Moirai-2.0 + TimesFM-2.5 + Time-MoE** to Chronos/TTM/TabPFN heads; ensemble + conformal; promote by CPCV | replace/upgrade | 2026 benchmarks: Moirai-2.0 & TimesFM-2.5 top financial return forecasting; you only run older heads. | uni2ts ★ · granite_tsfm ★ · lag_llama ★ + TimesFM/Time-MoE | M / Med | 7,17 | proposed |
| 6 | **LiT — Limit Order Book Transformer** for crypto short-horizon direction | new/replace | SOTA (Oct-2025), beats DL baselines on LOB, robust to regime shift; replaces hand-crafted microprice/OBI heuristics. | lob_deep_learning ★ + LiT | M / Med | 7,25 | proposed |
| 7 | **Regime-conditioned MoE router** over the node network (Time-MoE-style gating) | upgrade | Routes to the best model *per detected regime*, learned end-to-end — upgrades CORTEX routing. | Time-MoE + CORTEX | M-L / Med | 7,22,26 | proposed |
| 8 | **RL execution agent** (hierarchical RL order-slicing) | new | Learns to minimize slippage beyond closed-form Almgren-Chriss; execution cost is often the whole edge. | FinRL/ElegantRL + muzero ★ | L / Med-High | 21 | proposed |
| 9 | **GAN/VAE synthetic factor + scenario generator** | new | VAE latent factors avoid crowding; GAN synthetic regimes stress-test strategies & feed sleep-replay. | VAE/GAN + avalanche ★ | M-L / Med | 20,23 | proposed |
| 10 | **Intermarket Graph Neural Net** (PyG) over NSE↔crypto↔macro | new | Models lead-lag/contagion (BTC→NSE IT, funding→spot) as a graph, feeding the causal layer. | PyTorch-Geometric | L / Med | 15,19 | proposed |
| 11 | **On-chain whale + news-NLP alt-data lane** (live features) | new/wire | Free alt-data the goal says IS in scope; whale-flow repo already vendored. | crypto_whale_watching ★ | M / Low-Med | 2,15 | proposed |

Sources: TSFM finance benchmark (arxiv 2606.27100), 2026 TS toolkit (machinelearningmastery.com), LiT LOB transformer (frontiersin.org/…/frai.2025.1616485), latency-efficient LOB (arxiv 2606.25986), FinRL (arxiv 2111.09395), TradeR hierarchical RL execution (arxiv 2104.00620), AlphaEvolve (arxiv 2103.16196), Alpha-R1 (arxiv 2512.23515).

## COMPLETION — 2026-07-04 (all 11 ideas DONE)

Owner directive: complete every idea fully. Status of the Run 2026-07-04 table:

| # | Idea | Status | Delivery |
|---|------|--------|----------|
| 1 | Node auto-loader | ✅ done | `nodes/autoload.py` pkgutil sweep (162 families recovered) + `MLNB_AUTOLOAD_NODES=1` + `/api/network/autoload` |
| 2 | Wire DrawdownAdjustedKelly | ✅ done | `trading/sizing/position_sizer.py` (Wave 0) |
| 3 | Split `dashboard/server.py` | ✅ done | `dashboard/routes/{brain,trading,network,post}_ext.py`; server.py 3777→1524 |
| 4 | Brain-Ops panel | ✅ done | `dashboard/web/src/trading/BrainOpsPanel.jsx` (Wave 0) |
| 5 | TSFM ensemble | ✅ done | `foundation_nodes.TimeMoENode` + `nodes/tsfm_ensemble.py` (ensemble + isotonic conformal) |
| 6 | LiT order-book transformer | ✅ done | `nodes/lob_transformer.py` (torch TransformerEncoder, CLS readout) |
| 7 | Regime-conditioned MoE router | ✅ done | `nodes/regime_moe.py` (learned torch gate over frozen experts) |
| 8 | RL execution agent | ✅ done | `trading/execution/rl_exec_env.py` + `rl_execution.py` (SB3-PPO beats TWAP) |
| 9 | GAN/VAE factors | ✅ done | `nodes/vae_factor.py` (β-VAE latent factors + scenario generator) |
| 10 | Intermarket GNN | ✅ done | `nodes/intermarket_gnn.py` (PyG GCN over the cross-feature graph) |
| 11 | On-chain whale + news lane | ✅ done | news = `trading/brain/news.py`; on-chain = `trading/altdata/onchain.py` + `/api/trading/onchain` (live free sources) |

Each new node auto-registers into the live pool via idea #1's autoloader. New TSFM/LiT/GNN/MoE/VAE
nodes ship behind the existing opt-in pool flags to protect growth-pool fit time. All shipped with
tests (test_autoload, test_vae_factor, test_regime_moe, test_intermarket_gnn, test_lob_transformer,
test_tsfm_ensemble, test_rl_execution, test_onchain_altdata) and per-idea commits.

## Run 2026-07-05 — owner-invented: Broker-Sense Funnel (universe-scan compute fix)

Context: brain loop is WEDGED — run_once iterates 293 crypto (×153 strategies) single-thread, never
completes a cycle → 0 new trades, 5 stuck, only futures runs. Owner idea: offload the universe scan
to broker/3rd-party SCREENERS (open broker apps via computer-use, OTP via Brain Chat, use their
filters to rank), compute only on the shortlist, APIs only for execution. No single OSS does the full
vision → invent it. Full design: research/universe-scan-architecture.md.

| # | Idea | Type | Why it beats what we have | Reuse | Effort/Risk | Pillar | Status |
|---|---|---|---|---|---|---|---|
| 12 | **Broker-Sense Funnel** — 3-layer coarse→fine: Layer-1 PERCEIVE offloads the whole-universe screen to external screeners (tradingview-screener API for NSE+crypto; Chartink→OpenAlgo; GUI-fallback via browser-use w/ OTP-via-chat for API-less/blocked screens) → ~20-40 shortlist/segment/bar; Layer-2 REASON runs the 153-strategy brain+UQ ONLY on the shortlist (cycles complete in seconds); Layer-3 EXECUTE via OpenAlgo/Freqtrade | new/architecture | Removes the wedge (whole universe screened every bar for ~0 local compute vs never-completing 293×153 loop); finds MORE trades across all segments; NSE+crypto | tradingview-screener ★, Chartink→OpenAlgo ★(have OpenAlgo), browser_use_src ★, gui/agent.py ★, credentials.py vault ★ | M-L / Med | 7,21,25 | done — trading/broker_sense/funnel.py + run_funnel_loop crypto+nse; THE trade driver since 2026-07-06 |

Honest design note (baked in): raw candles/order-book via API (exact, fast) — GUI-reading only for
data with NO API (some NSE); the compute problem was the backtest, not the fetch. Prior art = pieces
only (tradingview-screener, Chartink→OpenAlgo, browser-use, TradingAgents); the autonomous
broker-app-driven screener+perception funnel is the invention.

## 2026-07-06 — Broker-app "full-feature" exploitation (proposed)
Context: bot can now click broker UI (App Driving School), 31GB RAM / 12 cores, crawl is serial.
1. [DONE] Screener-Feature Catalog+Use engine — discover EVERY built-in picker on Upstox
   (momentum gainers 1m/3m/5m, trending, trending<500, top gainers/losers, Algovers, Chart360,
   Scalper, News, OI-analysis) + Binance (Top Movers, Gainers/Losers, New Listings, Funding-rate
   board, Long/Short leaderboard, Liquidation heatmap, Options movers) → register each as a named
   candidate SOURCE the funnel reads directly (broker did the compute → we just read the list).
2. [DONE] Parallel exploration pool — one Playwright context PER broker-feature, crawled
   concurrently (12-core / 31GB), so all pickers refresh every bar instead of one-at-a-time.
3. [DONE] Feature→signal fusion — treat each broker picker as a weak labeler; brain learns
   per-feature hit-rate and weights them (stacking), so "appears in 3+ bullish pickers" = strong.
4. [DONE] Live UI reflex — read the app's own real-time movers stream (no polling) → act in
   ms; broker's ranking replaces our universe scan (saves CPU + latency).
5. [DONE] News/OI/sentiment columns from the apps' own News + OI-analysis tabs → trade cols.
6. [DONE] Self-expanding screener presets — brain invents new filter combos IN the app's
   screener UI (Voyager-style) and keeps the ones that backtest well.

## 2026-07-06 — Broker-feature follow-ons (all DONE)
1. [DONE] Self-growing columns — trade_columns.propose→accept API+TradeColumnsPanel (6 real cols)
2. [DONE] Order-preview gate — funnel VERIFY reads broker margin/liq-price (BROKER_ORDER_PREVIEW=1)
3. [DONE] Segment-focus CPU save — fully-off market does ZERO funnel work
4. [DONE] Momentum-ignition — new_entries→mind_events + fuse() 1.25x boost for fresh igniters
5. [DONE] Regime-aware weights — FeaturePerf per-regime buckets, blended by current_regime()
6. [DONE] Self-healing wiring watchdog — connectivity_monitor (baseline+regression), non-blocking
   scan_async (fixed 14s→2.9s load), learn-loop piggyback, ConnectivityPanel

## 2026-07-06 — Strategy-generation SOTA upgrades (proposed; DEAP evolution now wired+ON)
Context: connected the DEAP NSGA-II evolution/mutation engine to the brain pipeline
(evolved_link.py) and turned it ON in paper. Research (research/strategy-generation-sota-2026.md)
says DEAP fixed-genome is a solid baseline but NOT the frontier; our CPCV+DSR+PBO guardrail IS
SOTA. Posture: keep DEAP as one generator, ADD stronger generators through the same gate.
1. [PROPOSED] Formulaic-alpha mining generator — AlphaGen/AlphaForge (RL/GFlowNet); discovers
   decorrelated SETS of novel alphas (combined-IC), feeds genome + CPCV gate. Highest impact.
2. [PROPOSED] LLM-as-mutation-operator — OpenEvolve/pwb-alphaevolve; replace DEAP's blind
   mutation with hypothesis-driven LLM code edits (reuse core/llm.py). Minimal-risk hybrid.
3. [PROPOSED] PySR symbolic-regression generator — evolves the expression tree itself
   (more expressive than a fixed genome); CPU-first. (gplearn = lighter fallback.)
4. [PROPOSED] Quality-Diversity archive — pyribs MAP-Elites/MOME; illuminated archive of
   behaviorally-diverse strategies (holding-period×turnover×regime) vs Pareto collapse.
5. [PROPOSED] RD-Agent(Q)+Qlib autonomous quant-researcher tier (heavier, LLM-budget gated).
6. [PROPOSED] Family-wise error control — White's Reality Check + Hansen's SPA (mlfinlab OSS)
   now that many generators produce far more candidates. Optuna (NSGA-III/CMA-ES) for tuning.

## 2026-07-06 — Strategy-generator portfolio (ALL DONE, user approved "add all 6 + 5th")
Built trading/strategy/generators/ — DEAP + 6 SOTA generators through ONE CPCV+DSR+family-wise gate.
1. [DONE] Formulaic-alpha mining — alpha_mining.py (reuses vendor/alphagen operator vocabulary, IC-filtered)
2. [DONE] LLM-as-mutation-operator — llm_mutation.py (LLM edits GP-DSL, reuse core.llm)
3. [DONE] Symbolic regression — symbolic.py BOTH gplearn + PySR (Julia)
4. [DONE] Quality-Diversity — quality_diversity.py (pyribs CMA-ME MAP-Elites)
5. [DONE] RD-Agent(Q) researcher — rd_agent.py (research→develop→feedback loop, persisted Trace, reuse core.llm + alpha_ops; vendor/RD-Agent ref)
6. [DONE] Family-wise error control — stats_gate.py (Hansen StepM via arch) in the gate + Optuna tuner (optuna_tune.py)
Scaffold: base.py (Candidate/evaluate_and_admit/rebuild) + expression.py + alpha_ops.py + portfolio.py. Tests: tests/test_generators.py. Verified: 63+24 tests green, integrated breed admits across all generators.

## 2026-07-07 — Invent-beyond (eyes-brain-UI + next-gen self-evolve) [proposed]
Grounded in state-20260707-140924.md + audit-20260707 + the 8 videos. Owner NAMED
several of these in the goal message → treated as pre-approved (marked ★).

1. ★ [DONE `baac5e1` — broker_sense/curiosity.py + /api route + 7 tests] **Curiosity-driven feature discovery on app screens** (new) — a scout that scores
   NEW numeric fields appearing on the broker pages by novelty and auto-proposes them as
   trade columns. Extends trade_columns.py discovery with a curiosity signal. Serves the
   owner's "each and every data on the trading account web page." Effort LOW, risk LOW.
2. ★ [DONE `baac5e1` — ui_crawl._expected_info_gain; live scores visible in ui_crawl_cursor.json] **Active-inference page exploration** (replace ui_crawl round-robin) — the crawl
   visits the page that maximizes expected information gain about coverage gaps (min
   expected free energy) instead of round-robin. Upgrades ui_crawl.py. Effort MED.
3. ★ **Self-supervised UI world-model** (new) — the eyes predict the next screen's key
   features before acting; prediction surprise = where to look + a learned "this layout
   changed" signal. Reuse trading/brain/worldmodel.py retargeted to UI feature vectors.
   Effort MED-HIGH, impact HIGH for the eyes.
4. ★ **Sleep-replay / dreaming of episodic UI memory** (new) — during idle, replay
   captured page episodes to consolidate layout memory + surface recurring
   pre-move patterns (vp1/self-improving-agent "dreaming"). Reuse decision_memory +
   brain sleep. Effort MED.
5. [DONE `41086f2` — run_autoresearch daemon + Researcher section in StrategyGeneratorsPanel;
   live: 175 tested / 6 admitted / 8 tripwire rejections on day one] **Autoresearch champion
   loop, live** (activate) — run the strategy-generator portfolio
   in continuous auto-research mode; the leak-tripwire + champion lineage (W5) already
   exist — needs only a driver loop + Trading-Researcher panel. Effort LOW (pieces built).
6. **Recurrent-PPO / decision-transformer exec** (replace W6 PPO) — handle partial
   observability in the exec policy (audit upgrade candidate). Effort MED.
7. **Cross-app information arbitrage** (new) — when Binance vs Upstox/TradingView disagree
   on a cross-listed or correlated signal, that gap is an edge; a scout comparing the two
   eyes. Effort MED, needs both crawls warm.
8. **advintel activation** (activate) — the parked insider-style intel subsystem feeds the
   NSE-side scouts once the UI crawl reaches those broker pages. Effort MED.
