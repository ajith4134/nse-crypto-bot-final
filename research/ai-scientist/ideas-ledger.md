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

## 2026-07-07 — Ultra-brain + eyes/hand round 2 (proposed; post-autoresearch/wide-funnel state)
Grounded in state-20260707-165922 (673 modules) + today's shipped work (live autoresearch,
explore-wide funnel, Binance/Upstox Brain-Open mirrors, ui_candles cross-process store).

1. **Local grounded eyes (REPLACE cloud-vision clicks)** — drive human_ui clicks/reads with
   the VENDORED OmniParser (v2 icon+box detector) + a local caption head: coordinates come
   from local parsing, the cloud LLM is consulted only on ambiguity. Rate-limit-proof,
   ~10x faster per action, $0. Modules: trading/brain/vision/human_ui.py + vendor/omniparser.
2. **Hand skill-cache (Voyager-for-UI)** — record every SUCCESSFUL explore() action trajectory
   (goal + layout-hash → steps) into ocular layout memory and REPLAY it next time; fall back
   to explore + re-record on failure; per-skill trust via W7 track_record rule-of-three.
   Cuts vision calls ~90% on repeat tasks (watchlist add/remove, tab nav). vendor/voyager.
3. **Champion bandit allocator** — allocate paper capital across the autoresearch library's
   champions with a contextual bandit (regime features → Thompson sampling) instead of
   single-best-per-market; learning allocation IS the edge compounding. reuse: mabwiser.
4. **Distilled entry micro-policy (REPLACE per-cycle backtests)** — nightly distill the
   153-strategy + fusion decision surface into a per-coin GBDT policy; decide() drops from
   seconds to ~ms, releasing the funnel budget that throttled breadth (today's root cause).
   Modules: percoin_decider + TradeOutcomeNet + lightgbm (installed).
5. **Concurrent free-eyes fusion** — run the DOM / local-OCR / network-interception
   perception lanes CONCURRENTLY per page and fuse (they run serially today); 32 GB
   headroom standing order. Module: broker_sense free-eyes ladder.
6. **Off-policy funnel-weight evaluation** — upgrade picker/lane hit-rate learning to
   doubly-robust off-policy evaluation over the journal's decision_snapshot columns, so
   lane weights learn from EVERY logged decision, not just taken ones. Module: funnel-learn.

## 2026-07-10 — Brain de-stagnation round (1-5 DONE same day + Dream-Trainer + fast_nav shipped; 6-8 proposed; grounded in research/brain-audit-2026-07-10.md)
1. [done 2026-07-10] Loop Keeper — runtime self-heal for the 3 loop processes + learn daemon: systemd user units (Restart=on-failure) or a 5-min keeper cron running pgrep-guarded start_all.sh; dead-loop banner on the dashboard. Ends "silent mid-day death" (today's #1 root cause).
2. [done 2026-07-10] LLM Budget Governor + local floor — per-provider token-bucket RPM caps honoring free tiers, prompt dedupe/cache, circuit breaker on reload_at, and a LOCAL fallback model (ollama qwen/llama or distilled micro_llm) so brain features degrade to local instead of 429-dying (95% of 4.5k calls/day are failures).
3. [done 2026-07-10] Calibration truth loop — per-symbol Brier/ECE computed at close-learn (root-cause ETH brier 0.0), reliability panel, auto re-fit of conformal UQ + confidence recalibration from realized outcomes.
4. [done 2026-07-10] Learning that visibly improves — FSRS param re-fit from quiz outcomes; error-driven topic picker (learn what the brain got WRONG last week, not a fixed topic list); learning-curve panel (retention, OOF-acc, rolling win-rate deltas) so improvement is visible.
5. [done 2026-07-10] Demo→LIVE panel wiring (8 panels) — memory/hybrid/librarian/quiz/thinking/stream/self-coding → real get_brain() HippoRAG/A-MEM, knowledge_main, FSRS log, mind_events.json, self_evolve state; options chain → real OpenAlgo NFO chain already fetched by the options segment.
6. [done 2026-07-10] TradeOutcomeNet SOTA replacement scan — trading/brain/challenger.py (champion/challenger on the same OOF protocol) + _TabPFNWrap in trade_features.py; tests/test_challenger.py.
7. [done 2026-07-10] Off-policy gate tuning — trading/brain/gate_tuner.py (counterfactual θ sweeps over the explore-open-all journal lanes) + learn-loop tick + /api/trading/gate_tuning; tests/test_gate_tuner.py.
8. [done 2026-07-10] Knowledge gathering upgrade — trading/brain/news_ingest.py (free public RSS → symbol-linked news_memory.json, 15-min internal rate limit, zero-cost-first) + learn-loop tick; tests/test_news_ingest.py.

9. [done 2026-07-10] Dream-Trainer counterfactual regret decomposition (trading/brain/dreamer.py) — owner 'entirely different' ask; phase 2 worldmodel imagination replay = imagine_replay() [done 2026-07-10, tests/test_dream_replay.py].
10. [done 2026-07-10, wiring landed same day] fast_nav planner (trading/brain/vision/fast_nav.py) — skill→goto→explore ranked nav plans + 2-strikes accuracy loop. WIRED: HumanUI.navigate() (honest landing check — goto only counts when the target's words appear on the landed page) + boss tool navigate_app ("open holdings on Upstox" from Brain Chat) + fast_nav block in /api/trading/ocular; tests/test_fast_nav_wiring.py.

## 2026-07-10 — Brain-native FreqUI + engine redesign (owner-initiated)
| id | idea | type | status |
|----|------|------|--------|
| BN-E1 | In-engine tailgate/lock enforcement at engine tick (~5-15s) | replace (funnel-cadence exits) | done 2026-07-10 — MlBridgeStrategy.custom_exit (`tailgate_lock`), kill-switch mlnb_tailgate_enforce |
| BN-E2 | Native brain fields in engine /api/v1 (kill cross-origin overlay) + segment-routed /status | replace | done 2026-07-10 — mlnb_sidecar enrich (tg_* + strategy_label/brain_pred) + /api/v1/mlnb/{feed,funnel,tailgate,xray} + header-scoped /status |
| BN-E3 | decisions.jsonl push inbox: funnel writes, engine executes (replaces forceenter polling) | replace | done 2026-07-10 — mlnb_inbox.py + freqtradebot hook + engine_client CRYPTO_DECISION_INBOX=1 (OFF by default) |
| BN-E4 | Fill-time journal stamping in engine (entry context at fill, not ingest reconstruction) | replace | done 2026-07-10 — mlnb_fills.py at _notify_enter/_notify_exit fill branches → mlnb_fills.jsonl |
| BN-E5 | Fork hygiene: disable FreqAI/hyperopt surfaces, FORK.md divergence doc | new | done 2026-07-10 — vendor/freqtrade/FORK.md divergence index + unused-surfaces policy |
| BN-U1 | FreqUI "Brain Cockpit" trading view (segment rails + decision feed + X-Ray drawer) | new | done 2026-07-10 — BrainSegmentsRail/BrainFeed/BrainXray in TradingView.vue; built+deployed |
| BN-U2 | FreqUI "Mission Control" (dashboard brain panels as native tabs) | new | done 2026-07-10 (owner go-ahead) — MissionControlView.vue (/mission): Brain feed + Funnel tiles same-origin, School + Sandbox via mlnbDash composable; live-verified all tabs |
| BN-U3 | FreqUI "Pro Terminal" (chart-first, brain markers + ratchet lines) | new | done 2026-07-10 (owner go-ahead) — ProTerminalView.vue (/terminal): full-height chart, real entry/exit markers w/ reason, ≈LOCK/≈PEAK ratchet price lines, trades+brain docks; swap-pool candles fix for futures-only symbols; BASE_URL overlay fix (4 files had silent site-root fetch) |
Details: research/brain-native-frequi-engine-redesign-2026-07-10.md

## 2026-07-10 — evening code-review round (8 CONFIRMED findings, all fixed same day)
1. Inbox queued≠entered — brain_executor books queued decisions separately ("queued" report field), engine flag mlnb_decision_inbox=true added to config.json so CRYPTO_DECISION_INBOX=1 is end-to-end.
2. /api/trading/options/status now cache-keys per ?underlying (server _QUERY_KEYED_CACHE) — was serving one index's analytics for all.
3. Options tile falls back honestly on {"available": false} cached-chain errors (was a permanent error box).
4. state.update_json (flock merge) ends cross-process broker_sense_status.json tile clobbering (funnel.py + run_funnel_loop.py); tests/test_state_update_json.py.
5. dreamer.dream_once preserves the imagination section (was wholesale-overwriting nightly replay results).
6. Inbox exits carry trade_id ("all" closes every open trade on the pair; specific id closes exactly that one).
7. challenger duel masks TRADE_NET_ENGINE for the champion side + labels the engine that actually trained; duel() wired into run_micro_distill (CHALLENGER_DUEL=1 nightly).
8. _pool_ohlcv falls to perp candles ONLY on BadSymbol for /USDT pairs (transient spot errors no longer silently chart perp prices); FreqUI candle fallback now sends the full pair.
Also: gate_tuner reads live UQ_P_UP_MIN / CRYPTO_MIN_SCORE envs instead of a hardcoded copy.
Deferred (ledgered, not done): consolidate 4 legacy mlnb_status.json fetch sites onto the useMlnbDash composable; extract shared chart composable for BrainControlView/ProTerminal; GateTuning dashboard panel; screen_mirror O(1) action append + cheap n_actions.
Fork-tracking gap (found at commit time): only 3 vendor files were ever git-tracked while FORK.md names ~20 diverged ones — this commit adds the brain-native layer (mlnb_* + E2 api_server files + BN-U sources); the OLDER segment-fork divergences (persistence/segment_context, deps.py, rpc.py, exchange/deribit.py, worker plumbing…) remain untracked [proposed: vendor-update-style sweep to land them].
2026-07-10 update: BN-E1..E5 + BN-U1 (Brain Cockpit) APPROVED by owner and BUILT same day.
E1 verified live (engine tailgate_lock exits incl. gap-through-lock at -2.9%); E2 verified
(native tg_*/strategy_label on /status+/trades, header-scoped /status, /mlnb/* endpoints);
E4 verified (mlnb_fills.jsonl filling with real entry/exit fills); E3 built+tested, OFF by
default pending soak; E5 FORK.md landed. BN-U2/U3 remain proposed (owner picked A).

## 2026-07-10 — DIRECTION ACCURACY PROGRAM (owner order: "correct direction every time or close"; plan research/direction-accuracy-program/PLAN.md)
Ground truth: 1,665 closed crypto trades = 40.3% direction-correct (conf≈1.0 bucket: 29%) → systematic ANTI-signal, exploitable by inversion.
> **⚠️ CORRECTED 2026-07-16:** the "ANTI-signal exploitable by inversion" reading is FALSIFIED
> (evidence: `research/audits/measurement-rebuild-20260716.md`). Predictors are coin-flips
> (0.488 on 100k labels), not anti-signals; the 40.3% was era-bound (crypto realized since 7/11
> = 0.523, n=3,282); paired analysis shows inversion flips reverted winners (implied raw-on-gate-samples
> 0.64–0.67, persistence corr −0.214); conf≈1.0 bucket is now 0.498, not 29% (still miscalibrated:
> low-conf 0.568 beats high-conf). D2 Mirror Gate RETIRED (MIRROR_GATE=0, 2026-07-16). D3–D6 remain
> valid ideas but must not cite inversion or the 4h edge as justification.
| id | idea | type | status |
|----|------|------|--------|
| DA-D1 | Direction Truth Ledger — fixed-horizon direction outcomes for every decision (taken + skipped), per source×regime×horizon hit-rates w/ Wilson CI; backfill 1,665 trades | new | done 2026-07-10 — truth_ledger.py, 11,067 labels/127 buckets, panel + API live; found SHORTs 63%@4h destroyed by exits |
| DA-D2 | Mirror Gate — invert reliably-wrong (CI<45%) direction buckets, abstain 45-55%; turns measured 29-40% buckets into 60-71% with zero new data | new | **RETIRED 2026-07-16** — paired experiment falsified the premise (inversion flips reverted winners; persistence corr −0.214); MIRROR_GATE=0. Was: done 2026-07-10, wired at 3 entry sites |
| DA-D3 | Pullback entry — require k×ATR retrace after verdict before entry (<15m holds are 34.9% correct = entries at local extremes) | replace (immediate market entry) | proposed |
| DA-D4 | Microstructure direction features — cross-venue lead-lag gap (multi-venue pool), OFI/microprice, funding snap, multi-TF agreement | new | proposed |
| DA-D5 | Regime-conditional direction — momentum sign only in trend regime, reversion sign in chop, abstain at transitions (BOCD/HMM exist) | replace (regime-blind decide) | proposed |
| DA-D6 | Direction meta-labeler — lightgbm P(side correct) on D4+snapshot features, triple-barrier labels, isotonic + conformal abstention = the 80%-on-taken dial | new | proposed |
| DA-D7 | Direction Colosseum — shadow league: every source predicts every candidate, truth-scored at horizon, live weight only after >55% CI in shadow | new | proposed |
| DA-D8 | Validate+Size stages — pre-trade audit veto (local LLM + rules) + fractional-Kelly from calibrated P + enforced target≥2×stop (vidup1 math: 52%×3.92 R/R) | new | proposed |
| DA-D9 | NSE call/put on the same oracle — CE/PE from calibrated verdicts, ends options no_direction starvation | new | proposed |
| DA-W | Watchlist Study Funnel — save shortlist to app watchlist → open each symbol → eyes-read multi-TF/indicators/depth → StudyReport → oracle → API trade → remove on close | new | proposed |
| DA-M | Live Screen Mirror — ffmpeg x11grab MJPEG stream per brain display, viewer-demand start/stop; replaces per-action JPEGs | replace (frame polling) | proposed |
Fixed same session (pre-plan): funnel LLM-wedge (no crypto trades) + tailgate displayed-lock vs exit-line divergence (live_loop) — both verified live.

## 2026-07-11 — Direction program D3-D9 + W + M ALL SHIPPED (owner "continue with d3 and all next steps")
DA-D3 done (pullback.py arm→sweep + live_price feather fallback for UI-only mode; 8 tests; 3 executor sites).
DA-D4 done (micro_features.py: venue_leadlag/psych_ofi/funding_extreme/mtf_agree shadow lanes; 8 tests; funnel-cycle claims).
DA-D5 done (regime.py Kaufman-ER trend/chop/transition, 60s shared cache; 8 tests; default regime for all crypto claims + gates).
DA-D6 done (meta_labeler.py LightGBM+isotonic, time-ordered holdout, honesty guard; 6 tests; trained on 7,676 real examples → AUC 0.509 → ADVISORY until features accrue; 6-hourly retrain; executor gate + Kelly sizing).
DA-D7 done by composition (6+ measured claim sources per cycle; Truth panel = league table).
DA-D8 done (regime-transition block + fractional-Kelly stake from calibrated p, proven-model-only).
DA-D9 done (live_loop NSE/options entries record + mirror-gate; NSE regime = cross-broker label).
DA-W done (watchlist_study.py: study set → BOTH app watchlists, StudyReport fusion, app_study claims, auto-drop; 8 tests).
DA-M done (live_mirror.py ffmpeg x11grab MJPEG + /api/trading/mirror/stream + panel LIVE toggle w/ honest 503 fallback).
Also fixed: DecisionMemoryPanel null-outcome crash (e.outcome?.r_multiple) that unmounted the whole Trading view.
Deferred (ledgered): /code-review high-effort pass over the full direction diff; meta-labeler TabPFN challenger; lead_lag pip HY-estimator upgrade of venue lane; Direction panel sections for pullback/study/meta.

## 2026-07-11 — Reflex fast lane (signal→order in seconds) [proposed]
Grounded in TODAY's measured bottlenecks (py-spy on live funnel): cycle time is
network I/O (broker feature reads, candle fetches, budgeted LLM lanes) + model
compute (TabPFN, now TTL-cached) — NOT Python loops. A compiled-language rewrite
would not move latency; RAM (24/31GB used) is a stability lever, not a speed one.
Design (extends existing modules, no net-new subsystems):
- R1 Verdict cache: DirectionOracle verdict per shortlist symbol (mirror gate +
  regime + meta-p + pullback distance) PRECOMPUTED each cycle into state
  (direction_verdicts.json) — the slow thinking happens off the hot path.
- R2 Tick trigger: the pullback-sweeper thread (already ticking 45s) upgraded to a
  websocket bookTicker listener (reuse multi-venue pool / freqtrade ws) → on tick
  crossing an armed retrace or a fresh verdict threshold → place order via the
  existing sweep_pullbacks path. Signal→order target: <5s.
- R3 CPU-solo auto: pause SIGSTOP-able batch jobs (cpu-solo skill logic) whenever
  R2 fires a burst, resume after — decision latency protected from batch load.
- R4 (optional, Pillar 9) numba-jit the retrace/ATR check if profiling ever shows
  it hot (unlikely — it's ~microseconds today).
Effort: R1+R2 ~1 day; risk: low (paper-first, reuses order path + levers).
Pillar: 27 (Direction Supremacy) + 9 (hot paths). STATUS: R1+R2 DONE 2026-07-11 (commit; 2.75s latency measured); R3 deferred until latency data demands it.

## 2026-07-11 · Binance surface exploitation (compute-offload architecture) — PROPOSED
Source: research/video/binance-app-improve/plan.md (owner video + "migrate compute to Binance account").
Principle: Binance's servers do universe-wide compute (Screener TA, AI Select, /futures/data,
movers); we READ results + deep-dive API only the shortlist → low CPU. 3-tier funnel (Tier0 bulk
narrow · Tier1 shortlist API · Tier2 liq websocket) → indicator_fusion/decision_snapshot.
25-surface catalog beyond the video's 4. Phases:
- P1 (proposed): Tier-0 narrower + order-flow pack (taker/long-short/OI/basis) + liquidation WS + funding upgrade.
- P2: Token Unlock + listing/launchpool catalysts.
- P3: AI Select + movers + native Screener + sector rotation as candidate sources.
- P4: options IV/skew/max-pain + Square sentiment.
Status: awaiting owner approval on phase(s) to build.

## 2026-07-11 · P2 catalysts — SHIPPED (listings) + Token-Unlock DEFERRED
Binance-native listing catalysts shipped: binance_catalysts.py (free announcements API catalogId 48
+ mirror universe-diff for just-listed perps) → fuse() `catalyst` block + screener new-listing
discovery boost (+0.15). Token-Unlock catalyst DEFERRED: DefiLlama emissions API now paywalled
(402), no free Binance endpoint — zero-cost-first forbids a pay item. Do NOT fabricate. Revisit
when a free unlock source is found (Binance bapi token-unlock path, or a free mirror of the data).

## 2026-07-11 · Binance compute-offload roadmap — COMPLETE (P1–P4 + panel)
All shipped + live + committed: P1 WS mirror + order-flow + universe migration · P2 listing
catalysts · P3 sector rotation · P4 options IV/skew regime · Binance Edge dashboard panel.
Brain reads funding/movers/order-flow/long-short/liquidations/catalysts/sectors/options-regime
ALL from Binance (local CPU reserved for ML). Deferred (no free source): AI Select (UI-only),
Token Unlock (DefiLlama paywalled). ~9 commits, ~100 new tests.

## 2026-07-11 · AI Select — SHIPPED (was deferred). Real endpoint discovered via UI interception:
GET bapi/apex/v1/friendly/apex/web/opportunity/recommended-assets?type=<sentiment|technical>
binance_ai_select.py reads Binance's built-in recommender directly (reliable, not DOM scrape) →
fusion ai_select block + screener +0.12 discovery boost + snapshot/panel. Only Token Unlock remains
deferred (DefiLlama paywalled). Verified: the new fusion signals (order_flow/sectors/catalyst/
options/ai_select) are USED — they move confluence (Δ measured) AND land in real journaled trades.

## 2026-07-12 — MOTTO level-up: web-nav + local-vision + RAM, seconds-fast data (proposed)
Motto: CPU=ML only · API=exec only · DATA=Binance/Upstox web-nav + qwen2.5-vl vision + RAM. Goal: per-cycle data in SECONDS.
1. [proposed] WS in-RAM mirror via BROWSER WS-tap (keystone) — CDP-intercept the Binance web app's OWN wss klines/depth/ticker frames → RAM ring buffer. Extends ocular interception + WS-mirror. Kills per-symbol fetch → RAM microseconds.
2. [proposed] Screener-as-universe — scrape Binance's built-in movers/screener as the universe+ranking. Replaces freqtrade VolumePairList (the #1 418 ban source) + local ranking. Extends broker_features.
3. [proposed] Shared-memory market bus — mirror in multiprocessing.shared_memory/Arrow; freqtrade+funnel+live_loop read ONE mirror. Kills duplicate cross-process fetching.
4. [proposed] Per-bar vision indicator cache — qwen2.5-vl reads the app's rendered indicators once/bar → RAM-served. Extends today's ocular per-bar memo.
5. [proposed] Frame-diff-gated + batched VLM — perceptual-hash skip unchanged charts; batch screenshots per VLM call. Cuts vision 5-10×. Extends vision_worker.
6. [proposed] freqtrade VolumePairList → StaticPairList fed by the mirror (migration). Kills ban burst.
7. [proposed] Predictive/speculative navigation — nav_brain pre-opens next-cycle shortlist charts so data is warm in RAM. Extends nav_brain.
8. [proposed] Faster local VLM scan — evaluate MiniCPM-V 2.6 / InternVL2 / Moondream2 vs qwen2.5-vl:7b for chart-read speed. Migration: core/llm local vision provider.
9. [proposed] Event-driven reflex from the mirror — mirror emits price/book events; brain reacts (reflex lane) instead of polling. Seconds→ms reaction.

## 2026-07-12 (session: motto web-data) — candle coverage + exit logic

### Candle coverage (broad+deep web-nav)
- [proposed] BULK-CANDLE DOOR: navigate the Binance markets/movers page → interception captures the app's
  OWN single bulk request that returns hundreds of symbols' recent candles/sparklines at once (the
  ticker-door trick applied to candles). Breadth for SCREEN; deep parked tabs only for the VERIFY shortlist.
  Reuse: interception + ui_market. Impact: HIGH (10→hundreds of screenable symbols, ~0 extra tabs).
- [proposed] TWO-TIER: bulk sparklines = direction screen for the universe; deep multi-TF parked tabs =
  fusion/strategy decision on the top-K only. Mirrors the funnel SCREEN(breadth)/VERIFY(depth) split.

### Exit logic (better than fixed net<=-2 + 3% tailgate)
- [proposed] ATR/VOL-SCALED BARRIERS: use fusion's already-computed ATR triple-barrier (entry/stop/target)
  for the exit instead of fixed %. High-vol coin = wider, low-vol = tighter. HIGH impact, LOW effort (wire
  existing fusion.barriers to the exit path). LdP meta-labeling exit.
- [proposed] REGIME-AWARE EXIT: trend regime → loose trailing (ride); chop regime → tight target (grab).
  fusion already computes `regime`; the tailgate's stated "tighter in chop, looser in trends" made real.
- [proposed] PARTIAL/SCALE-OUT: exit 1/3 at target, trail the rest. Locks profit + lets winners run.
- [proposed] VISION-READ EXIT (motto-native, novel): local qwen2.5-vl reads the open position's real app
  chart for exhaustion/reversal → exit signal. CPU=brain intelligence reading the web chart. vision_worker
  already reads charts; add a per-position exit read. HIGH novelty.
- [proposed] META-LABELER EXIT: mid-trade, if D6 meta P(direction correct) drops below threshold → exit.
- [APPROVED 2026-07-12, owner idea] BINANCE-FILTER TOP-N LANE (breadth engine, motto-pure UI data):
  open Binance segment market page → read the FULL sorted market table via the app's own filters/sort
  (24h%, volume, funding, OI, long/short, taker — all ALREADY captured by ui_market: ticker()/funding()/
  open_interest()/long_short()/taker()/movers()) → a LEARNED combo-selector (truth_ledger-scored per regime;
  reuse autoresearch.py "breed strategies over Binance filter data" + PresetStore rotation) picks the best
  filter combination → take adaptive TOP-N (start 20, grow to 50/100 as the edge holds) → learned_direction
  sets each side → executor opens until wallet/min-score gate. Fixes the 40-vs-10 breadth collapse the
  UI-only way (hundreds of pre-ranked candidates per page read vs ~37 screened/cycle). ROLLOUT: NEW PARALLEL
  LANE (kill-switchable), not a replacement. Stages: (1) ranker over ui_market filters + top-N open on a
  default preset; (2) learned combo-selector; (3) per-pick learned direction + regime rotation. Reuses
  ~80%; new = binance_filter_lane.py ranker + combo-selector. [[direction-driver-replaces-vote]]
