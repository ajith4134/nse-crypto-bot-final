# Direction-Equation Quest — coverage audit (2026-07-11, post-P4)

Honest cross-check of REQUIREMENTS.md + SYNTHESIS-AND-PLAN.md + related research docs against what is
actually BUILT, so nothing is silently skipped. Legend: ✅ done · ◑ partial · ⬜ gap.

## Requirements (REQUIREMENTS.md, the 8 verbatim asks)
| # | Ask | Status | Where / gap |
|---|-----|--------|-------------|
| 1 | Research online, hard, the direction-driving data + equation | ✅ | deep-research-raw.json (109 agents) → SYNTHESIS-AND-PLAN.md |
| 2 | Equation-generator (symbolic regression): discover from X→y, deploy to predict | ✅ | direction_equation.py discover() + direction_equation_deploy.predict() |
| 3 | Find ALL data/forces that drive price | ◑ | order-flow/positioning/funding/OI/liquidations/microstructure/VP/vision ✅; **on-chain ⬜ (stubbed), macro/sentiment partial, GOFI ⬜** |
| 4 | Try ALL combinations/theories/equations | ✅ | gplearn + Operon + PySR + alphagen + DEAP evolution + QD/Optuna portfolio |
| 5 | Read/reuse ALL related projects | ◑ | gplearn/Operon/PySR/ChartScanAI/candlestick_cnn reused; **SINDy installed-but-unwired, AI-Feynman not installed** |
| 6 | ADD our existing features | ◑ | fusion consumes them; **the EQUATION's own feature bus is TA-only (see GAP-A)** |
| 7 | Mutate + evolve, self-improving, keep-best | ✅ | DEAP evolve.py + reevolve_all() daemon + CPCV keep-best gate |
| 8 | Save the meaning first | ✅ | REQUIREMENTS.md |

## GAPS found (nothing hidden)
- **GAP-A (most important — the quest's core thesis): the discovered equation is over STANDARD TA
  FEATURES ONLY.** The symbolic-regression generators fit on `features.compute_features` →
  `market_features` → `FEATURE_NAMES` = {ret, sma_fast/slow, ema, rsi, atr, atr_pct, mom, …}. The
  order-flow (OFI/CVD/OBI/funding/OI/liquidations), Volume-Profile (POC/VAH/VAL), and vision
  (CNN/VLM/YOLO) signals are consumed by `indicator_fusion.fuse()` as bounded LENSES, and the equation
  is ALSO a lens — but they are NOT variables the equation can be BUILT from. So today's equation is a
  "TA equation fused with order-flow," not the "order-flow-FIRST equation" the research ranked #1.
  - Two sub-parts: (a) cheap — point the generators at the richer `compute_features_ext` (has vp_* +
    EMA/SAR/supertrend/vwap); (b) real work — materialize per-bar order-flow columns (OFI/GOFI/CVD from
    historical book/aggTrade) so they enter the equation's variable set.
- **GAP-B: GOFI** (generalized/stationarized OFI — plan's #2 driver, OOS R²≈84% at 30s) is computed
  nowhere. OFI/CVD/OBI/microprice exist as point-in-time fusion signals; GOFI does not.
- **GAP-C: on-chain data** — COINGECKO/ETHERSCAN/COINALYZE keys present but stubbed; not in any feature
  path. Macro + sentiment are only lightly present (Binance AI-Select, catalysts).
- **GAP-D: SR engines** — gplearn/Operon/PySR wired; **pysindy INSTALLED but not wired as a generator**;
  AI-Feynman not installed. Both are named candidates in the glossary.
- **GAP-E (from champions-chart plan): real Binance-UI screenshot with indicators toggled ON** — the
  local matplotlib render is currently the indicator source; the live broker-app capture path is plain
  candles. chart_yolo needs the real screenshot (distribution-sensitive).

## What IS solid (built + tested + committed)
P1 feature bus + 3-lane vision cascade (CNN/VLM/YOLO); permanent local vision (qwen2.5-vl:7b + async
worker); Volume-Profile auction engine; P2 discover (gplearn/Operon/PySR) → horizon-conditioned OOS
Rank-IC; P3 purged-CPCV + triple-barrier + PBO gate; P4 live deploy → Truth-Ledger measured +
Mirror-Gate self-correcting + reevolve daemon. ~45 tests. Commits 750bb82/6058d1a/b355cf5/8b7e3b0.

## CLOSED 2026-07-11 (this pass)
- **GAP-A(a) ✅** — the equation now discovers over the RICH bus (81 vars): `direction_equation.features_bus`
  = `compute_features_ext(with_vp=False)`; `symbolic._feature_matrix` now derives its variable set from
  the PASSED frame's numeric columns (so the quest gets EMA/SAR/supertrend/VWAP/MACD/ADX/Bollinger/
  Keltner/Donchian/OBV/… while the DEAP foundry path is untouched — market_features left as base).
- **GAP-A(b) / GAP-B (proxy) ✅** — order-flow columns added to `features_ext`: `buy_press, signed_vol,
  cvd, cvd_roll, tick_ofi, cvd_slope` (OHLCV-derived money-flow / tick-rule OFI / CVD). Verified the
  equation actually builds from them. **Remaining (data-plumbing, honestly deferred):** *true* L2-book
  OFI / **GOFI** need the order-book/aggTrade history feed materialized per-bar — binance_orderflow.py
  computes them LIVE but there's no stored historical series yet. Scoped, not faked.
- **GAP-D ✅** — `SindyGenerator` (pysindy STLSQ sparse polynomial, scale-free standardized fit, degree
  auto-capped by feature count) wired into the portfolio + the equation generator set + tested.

## Still open (honest — external-data / live-UI infra, NOT faked)
- **GAP-B/A(b) true book-OFI/GOFI** — needs a per-bar historical order-flow series (L2 book / aggTrade).
- **GAP-C on-chain** — CoinGecko/Etherscan/Coinalyze → per-bar aligned history is a real API-integration
  task (free tiers give limited history); point-in-time on-chain could ride as a fusion lens sooner.
- **GAP-E real-UI indicator screenshot** — toggling Binance's chart indicators via Playwright then
  capturing needs a live logged-in session to develop+test; the annotated RENDER is the indicator
  source meanwhile (the VLM reads the full set off it).

## Recommended close-out order (highest value first)
1. **GAP-A(a)** — repoint the SR generators to `compute_features_ext` (immediate: gives the equation
   the VP + richer TA variables). Small change to _feature_matrix / market_features.
2. **GAP-D** — wire a `SindyGenerator` (pysindy installed) into the portfolio (fast win).
3. **GAP-A(b) + GAP-B** — materialize per-bar OFI/GOFI/CVD columns from historical book/aggTrade so the
   equation is genuinely order-flow-first (the biggest lift, biggest payoff).
4. **GAP-C** — wire on-chain (Etherscan/CoinGecko/Coinalyze) as feature columns.
5. **GAP-E** — capture the real Binance-UI chart with indicators ON for chart_yolo/VLM.
