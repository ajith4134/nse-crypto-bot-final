# vendor/ — in-tree vendored OSS source (vendor-first rule)

Per the project's **vendor-first** rule: reuse real project code by copying its source
into this directory and making only minor edits to fit our flow — heavy logic comes from
the original project, our code is the glue. License is no obstacle (private, non-published).

**The practical boundary (honest):**
- **Vendored here** = pure-Python projects we can run + edit in-tree.
- **pip-installed instead** = compiled / JIT / framework libs that cannot be vendored sanely:
  TA-Lib (C), STUMPY & vectorbt (Numba), hmmlearn/scikit-learn (Cython), River, DEAP,
  LanceDB, mem0, (PyTorch/FinRL, Qlib — Qlib also has no py3.13 wheel). These are documented
  in `trading-execution-blueprint.md` as "pip — compiled, not vendorable".

## Contents
- **gplearn/** — genetic-programming symbolic regression (pure-Python, MIT), vendored from
  the upstream package. Used by `trading/brain/picking.py` (GPLearnFactorMiner) to *learn* a
  symbolic asset-ranking factor from features→forward-returns. Minor edits: removed the
  upstream `tests/` and `__pycache__`; imports are relative so it runs unchanged from here.
  Import as `from vendor.gplearn.genetic import SymbolicRegressor`.

## Computer-use / GUI-agent stack (research/brain-advanced-features-chat.md)
Source the brain's **computer-use agent** (`trading/brain/gui/`) reuses. The agent SEES
dashboards, presses their buttons, experiments, reflects and grows a skill library — composing
these real projects rather than reimplementing them. The agent's reliable path (read the same
JSON the panels draw + drive the in-process control surface) needs **no** new dependency; the
projects below are the perception/automation **upgrade layers** it adapts.

- **browser_use_src/** — [browser-use](https://github.com/browser-use/browser-use). Its
  `dom/`, `controller/`, `tools/`, `browser/` give Playwright-based DOM reading + clicking.
  `trading/brain/gui/actions.py::dom_click` and `perception.py` (DOM read) adapt this as the
  **pixel-true click** path. Activates when `playwright` + a chromium binary are installed.
- **voyager/** — [Voyager](https://github.com/MineDojo/Voyager). Its `agents/skill.py`
  `SkillManager` is the model for `trading/brain/gui/skills.py::GuiSkillLibrary` — a growing,
  validated library of reusable macros. We adapted OFF its langchain/OpenAI/Chroma deps to a
  file-based, embedding-free (CPU) implementation.
- **reflexion/** — [Reflexion](https://github.com/noahshinn/reflexion). The try→fail→reflect→
  store-lesson loop behind `trading/brain/gui/reflection.py::GuiReflector`. (Contains broken
  human-eval *fixtures* on purpose — `tools/gen_index.py` skips `vendor/` so they can't break
  the index.)
- **omniparser/** — [OmniParser](https://github.com/microsoft/OmniParser). Screenshot→structured-
  UI parsing. Its model is **GPU-only**, so it is a documented **upgrade slot** for the pixel-OCR
  perception layer; the CPU path uses PaddleOCR + the DOM/API read instead.
- **ChartScanAI/** — [ChartScanAI](https://github.com/Omar-Karimov/ChartScanAI) @ 58f7120. YOLOv8
  detector trained to spot Buy/Sell pattern regions on candlestick charts (`weights/custom_yolov8.pt`,
  50MB, classes {Buy, Sell}). Powers **Lane C** of the vision cascade (trading/broker_sense/chart_yolo.py)
  — CPU sub-second inference via the pip-installed `ultralytics`. Trained on real chart screenshots, so
  it detects on the eyes' broker-app captures (conf≈0.10), not our synthetic renders. The weights live
  here locally (not committed — 50MB blob); a fresh checkout without them → chart_yolo degrades honestly.

**GPU-only upgrade slots (not vendored as runnable here, CPU-first project):** UI-TARS,
Florence-2, SAM2, GroundingDINO — the vision-language perception models from the chat. The
agent's `perception.capabilities()` reports them as honest off-flags; install on a GPU box to
light them up. The equivalent CPU capability (read panels via API + parse controls + chart
reading + optional PaddleOCR) ships and works today.

## Strategy Foundry reuse (2026-07-02) — build-from-oss for ultra-advanced strategies
Vendored to copy-adapt into trading/strategy/ LibraryStrategy signals + the Strategy Foundry
(trading/strategy/foundry.py). Each foundry spec references its source; performance tracked by
unique id in trading/state/strategy_foundry.json.
- **funding-rate-arbitrage** @ cca3531 — github.com/aoki-h-jp/funding-rate-arbitrage — ccxt
  funding-rate fetch + cross/single-exchange divergence → crypto_futures "Funding Rate Arb".
- **statistical-arbitrage-pairs-trading** @ 6a5ac2a — github.com/arnavkohli/statistical-arbitrage-pairs-trading
  — cointegration + z-score signal (objects/signalprocessor.py, pairsbacktester.py) → nse_futures
  "StatArb Pairs" + "Correlation Breakdown".
- **gamma-scalping** @ c80b5e3 — github.com/alpacahq/gamma-scalping — options greeks + delta-hedge
  engine (engine/delta_engine.py) → nse_options "Gamma Scalping".
- **hmmlearn** (pip 0.3.3) — github.com/hmmlearn/hmmlearn — GaussianHMM regimes → "HMM Regime Switching".

## Brain ultra-upgrade donors (2026-07-02)
- `hipporag/` — https://github.com/OSU-NLP-Group/HippoRAG @ ef2f14c — KG + Personalized PageRank associative retrieval (neurobiological memory).
- `a_mem/` — https://github.com/agiresearch/A-mem @ ceffb86 — Zettelkasten agentic memory: dynamic note linking + memory evolution.
- `nanogpt/` — https://github.com/karpathy/nanoGPT @ 3adf61e — minimal trainable GPT (tokens→embeddings→attention); basis of micro_transformer_node.
- `llama2_c/` — https://github.com/karpathy/llama2.c @ 350e04f — pure-C Llama-2 micro-LLM inference (polyglot hot path).

## Trader-psychology donors (2026-07-02, research/trader-psychology-stitch-map.md)
- `lob_regime_scanner/` — https://github.com/CameronScarpati/lob-regime-scanner @ 5658da5 — L2 microstructure feature library (multi-level OFI, book imbalance, spread bps, Kyle λ, flowrisk VPIN); src/features.py loaded by path in trading/brain/psychology.py.
- `microprice/` — https://github.com/sstoikov/microprice @ 4e5f29a — Stoikov's canonical microprice estimator notebook; ported to the online StoikovMicroprice class.
- `crypto_whale_watching/` — https://github.com/pmaji/crypto-whale-watching-app @ 304959b — whale buy/sell-wall + ladder detection over REST depth snapshots; adapted as detect_walls().
- `lob_deep_learning/` — https://github.com/Jeonghwan-Cheon/lob-deep-learning @ 91b8d2e — PyTorch DeepLOB (lighten=5-level) price-direction model; wrapped by trading/brain/psych_deeplob.py.

## freqtrade
- origin: https://github.com/freqtrade/freqtrade
- tag: 2026.6 (matches installed pip version)
- commit: b604e2fd70539f7f73d3c62c16ce0b155bbab319
- purpose: deep fork — single-process multi-segment engine (futures/spot/options/prediction) behind one URL; local divergences carry '# mlnb:' comments

## Decision-memory donors (2026-07-03, research/decision-memory-stitch-map.md)
- `finmem/` — https://github.com/pipiku915/FinMem-LLM-StockTrading @ be814aa — layered episodic memory (shallow/intermediate/deep) with importance + recency decay and P&L feedback re-weighting; layer/decay/feedback semantics adapted into trading/brain/decision_memory.py.
- `tradingagents/` — https://github.com/TauricResearch/TradingAgents @ 85946c2 — decision log resolved with realized returns + reflection injected into future prompts; outcome-closure + reflection prompt shape adapted into decision_memory.resolve().
- **shap** (pip 0.48.0) — github.com/shap/shap — per-decision feature attribution engine → trading/brain/attribution.py.

## Time-series foundation models (git-vendored 2026-07-03)

Three heavy TS foundation models that are NOT cleanly pip-installable on this Python 3.13
CPU env (they force pandas 3.0 / a CUDA torch, or fail metadata-generation). Git-cloned and
imported via sys.path insertion (nodes/foundation_nodes.py `_add_vendor_path`). Wrapped as
gated foundation nodes (TinyTimeMixerNode / MoiraiNode / LagLlamaNode).

| dir | repo | commit | node | local patches |
|---|---|---|---|---|
| granite_tsfm | ibm-granite/granite-tsfm | f87e8bf | TinyTimeMixerNode | none (imports clean from vendored path) |
| uni2ts | SalesforceAIResearch/uni2ts | cfd46d4 | MoiraiNode | none (needs pip: hydra-core, einops, jaxtyping) |
| lag_llama | time-series-foundation-models/lag-llama | df7531a | LagLlamaNode | (1) `_gluonts_compat.py` shim re-implements the removed `gluonts.torch.modules.loss.{DistributionLoss,NegativeLogLikelihood}`; (2) two import lines repointed to it; (3) `data/`→`ll_data/` rename + import fix to avoid collision with the project's own `data/` package; (4) node aliases the shim into `sys.modules['gluonts.torch.modules.loss']` so the published checkpoint unpickles. |

All three verified end-to-end (real checkpoints, CPU): TTM ~9s, Moirai ~11s, Lag-Llama ~6s.

## CORTEX B3 single-file vendors (2026-07-04, research/cortex-stitch-map.md rows 21-22)
- `efficient_kan/kan.py` — https://github.com/Blealtan/efficient-kan (src/efficient_kan/kan.py, MIT).
  KANLinear/KAN: memory-efficient Kolmogorov-Arnold layers. Used as an OPT-IN drop-in for the
  gate's nn.Linear in nodes/gated_node.py (`use_kan=True`; graceful fallback to Linear).
  Unmodified upstream source (header comment added).
- `bocd/bocd.py` — https://github.com/gwgundersen/bocd (bocd.py, Gregory Gundersen).
  Bayesian Online Changepoint Detection (Adams & MacKay 2007), Gaussian unknown-mean model.
  core/trust.py runs its recursion ONLINE (message-passing form of the vendored batch `bocd()`)
  to reset the TrustLedger on run-length collapse. Local edit: matplotlib imports moved inside
  `plot_posterior()` (headless server).
