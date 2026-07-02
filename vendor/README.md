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
