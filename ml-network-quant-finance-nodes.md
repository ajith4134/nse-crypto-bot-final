# Quant-Firm / Trader / Finance-ML Node Catalog (2026)

> Signature techniques of top quant firms + famous quant authors, mapped to
> CPU-wrappable NodeProtocol nodes. From 3 parallel GitHub/PyPI research passes.
> We ALREADY have: GARCH, cointegration/stat-arb, EVT tails, order-book/microstructure,
> fractional differentiation, Kalman, regime/HMM-ish, matrix profile, wavelets/EMD,
> TA-Lib, tsfresh, gplearn, LightGBM/XGBoost/CatBoost.

## ⚠️ Architecture note — single-series vs cross-sectional
Our nodes train per-instrument (one series → X→y). Two buckets:
- **(A) Single-series** — fit the current design now (rolling factors, momentum, mean-reversion, labeling, risk features).
- **(B) Cross-sectional / panel** — need a multi-asset universe at each timestamp (WorldQuant 101 rank-alphas, HRP/portfolio allocation, cross-sectional z-scoring). These need a future **panel mode**; flagged, not skipped.

## BUILD BATCH — single-series, CPU, permissive, on-theme
| # | Node | Source | License | Type | Notes |
|---|---|---|---|---|---|
| 1 | **qlib Alpha158 factors** | lift expression strings from microsoft/qlib + small operator engine (Ref/Mean/Std/Corr/Rank…) OR **KunQuant** | MIT / Apache-2.0 | feature | 158 battle-tested per-series rolling factors; NO pyqlib install needed (expr engine is pure pandas) — biggest single add |
| 2 | **Meta-labeling** | mlfinpy (MIT) | MIT | predictor | López de Prado's signature: primary signal → secondary ML filter on {act/skip}. NOT mlfinlab (commercial) |
| 3 | **Triple-barrier labeling** | mlfinpy (MIT) | MIT | target/feature | proper path-dependent financial labels (profit-take/stop/time) |
| 4 | **Time-series momentum (TSMOM)** | self-implement (AQR; ref repos no-license) | — | signal | 12-mo vol-scaled trend; Moskowitz/Ooi/Pedersen |
| 5 | **Mean-reversion suite (Ernie Chan / RenTec)** | self-implement | — | signal | Bollinger-Z, OU half-life (−ln2/β), z-score reversion — trivial, single-series |
| 6 | **empyrical risk features** | empyrical-reloaded (Apache) | Apache-2.0 | feature | rolling Sharpe/Sortino/Calmar/VaR/maxDD as features |
| 7 | **WorldQuant time-series alphas (subset)** | KunQuant (Apache) / STHSF/alpha101 (MIT) | Apache/MIT | signal | the per-series alphas (the cross-sectional ones → bucket B) |
| 8 | **Fama-French factor data** | getFamaFrenchFactors (MIT) | MIT | feature/data | FF 3/5-factor + momentum (downloads Ken French data) |

## BUCKET B — panel/cross-sectional (needs panel mode; high value, deferred)
- **WorldQuant 101 Alphas (cross-sectional)** — KunQuant / STHSF (MIT). Rank-across-universe alphas.
- **HRP / Hierarchical Risk Parity + Black-Litterman + CVaR** — **skfolio** (BSD-3, sklearn-native, best) / Riskfolio-Lib / PyPortfolioOpt → allocation-weight node.
- **Cross-sectional z-scoring** (qlib CSRankNorm/CSZScoreNorm).
- **CombinatorialPurgedCV** (skfolio) — purged/embargoed CV for honest backtests (evaluation, not a node).
- **alphalens-reloaded** (Apache) — IC / rank-IC factor scorer (grades any factor node).

## FLAGGED — exclude
- **mlfinlab** (hudson-and-thames) — ⚠️ proprietary all-rights-reserved (commercial license), frozen since 2023. Use **mlfinpy (MIT)** for the same AFML algorithms.
- **GPU/LLM**: FinRL/FinRL-Meta, FinGPT, FinBERT, deep-TSMOM (momentum-transformer), GluonTS, transformer forecasters (PatchTST/TFT).
- **Restrictive license**: vectorbt (Commons Clause, no resale), backtrader (GPL), pycatch22 (GPL — but we already have catch22 via aeon).
- **No-license repos** (port logic, don't vendor): yli188 alpha101, rkohli3/TSMOM, BAB/Alpha191/Avellaneda-Stoikov forks.
- **Concept-only (not predictors)**: Avellaneda-Stoikov market making, latency arbitrage.
- **Dedup**: arbitragelab (overlaps our Kalman+cointegration), stumpy (have matrix profile).

## Integration via the registry
Single-series predictor/feature nodes (Alpha158 features, meta-labeling, empyrical) wrap cleanly — meta-labeling fits the registry's sklearn-estimator path; Alpha158/TSMOM/mean-reversion/alphas are feature/signal nodes on the `_WindowFeat`/`_HeadBase` pattern. Panel nodes (bucket B) wait for a cross-sectional data mode in run_multi.

## Recommended next build
Single-series batch (1–8 above): **Alpha158 factor node + meta-labeling + triple-barrier + TSMOM + mean-reversion(OU/Bollinger) + empyrical risk features + WorldQuant TS-alpha subset + Fama-French**. Then design panel mode for bucket B (101 cross-sectional alphas + HRP).
