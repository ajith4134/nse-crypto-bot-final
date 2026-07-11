# SOTA research: short-horizon direction prediction (agent sweep, 2026-07-10)

Companion to PLAN.md. Key findings (full citations inline):

## 1. Meta-labeling (López de Prado) — BUILD FIRST
Secondary classifier predicts "will this signal be right?"; triple-barrier labels.
Canonical study (Hudson & Thames, S&P E-mini): mean-reversion primary 17%→63% accuracy
OOS; trend primary 48%→55%. Not a silver bullet — needs a primary with *some* structure
(ours has strong ANTI-structure, which qualifies). 2025 crypto study confirms
(Financial Innovation, s40854-025-00866-w). OSS: mlfinpy (pip), mchiuminatto/triple_barrier,
old Apache mlfinlab labeling.py. CPU-trivial (LightGBM/RF seconds).
- https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/
- https://link.springer.com/article/10.1186/s40854-025-00866-w
- https://github.com/mchiuminatto/triple_barrier

## 2. Order-flow imbalance — upgrade existing OFI to multi-level + rolling linear fit
Cont-Kukanov-Stoikov: short-horizon price change ≈ linear in OFI (arXiv:1011.6402).
DeepLOB-class 74-84% numbers are tick-horizon, cost-free, OOD-fragile — SKIP deep LOB
models; keep the linear/logistic per-coin fit (CPU-friendly). MLOFI > best-level OFI
(arXiv:1907.06230); 2025: OFI-derived features beat raw-LOB deep models (arXiv:2507.22712).

## 3. Cross-exchange lead-lag — BUILD as feature
Binance futures leads; laggard venues follow. Practitioner validation: moves ≥0.10% show
~90.7% follow-through, ~300ms median (leadedge.dev/blog/validation — we play 1s-60s, not
the ms race). Asset-dependent leadership (arXiv:2506.08718). OSS: pip `lead_lag`
(philipperemy, Hayashi-Yoshida estimator, crypto case study included).

## 4. Regime-conditional — wire vendored BOCD + hmmlearn 3-state HMM
Regime-switching beats single-regime for crypto (Digital Finance 2024, s42521-024-00123-2).
Mean-reversion works ONLY in ranging regimes → regime = a switch between OPPOSITE signals.
Expect +1-3pts raw accuracy but large risk-adjusted gain from not trading wrong-regime.

## 5. Inverse-signal / anti-edge — bucketed, never blanket
Crypto intraday: short-term contrarian effect dominates at intraday horizons
(S1062940822000833). CRITICAL caveat: inverting a wrong signal only works if its errors are
STABLE — the statistically-supported form is meta-labeling (learn WHEN it's wrong).
→ Mirror Gate (D2) stays bucketed per source×regime×horizon with Wilson-CI gates and is
subsumed by D6 once trained. Regime-gated 5m-1h z-score reversal + funding/long-short-ratio
extreme fade = supported new strategies (Binance ratio API is free).

## 6. Foundation models 2025-2026
- **TabPFN-v2 / tabpfn-time-series** (arXiv:2501.02945): zero-shot, CPU-explicit, beats
  Chronos-Large and tuned GBMs on small tabular data (<10k rows — our journal size).
  → challenger secondary model in D6 (we already have _TabPFNWrap!).
- **Kronos** (shiyu-coder/Kronos, AAAI 2026, MIT): OHLCV-native foundation model,
  -mini/-small CPU-inferable → optional extra forecast node later.
- Sober counterweight (arXiv:2511.18578): off-the-shelf TSFMs UNDERPERFORM in finance
  without fine-tuning; Chronos ≈ XGBoost on RMSE. Do NOT replace the GBM stack.

## 7. Honest ceiling (sets our acceptance bars)
918-experiment 2026 study: mean directional accuracy of DL on hourly data = 50.08%
(arXiv:2603.16886). Credible results cluster 53-57% at 1h-1d. Even 60% can lose after
costs at 5m (MDPI Algorithms 2025, 10.3390/a18120758). Exploitable exceptions are
CONDITIONAL: lead-lag follow-through 90%+ after a trigger; meta-labeled SELECTED trades
63%. → 80% only as precision-on-accepted-trades. Optimize precision-at-coverage +
after-cost expectancy, never blanket accuracy.

## Priority stack (mirrors PLAN.md execution order)
1. Meta-labeling on unified journal (LightGBM + TabPFN-v2 challenger)
2. Regime gate (vendored BOCD + hmmlearn)
3. Multi-level OFI rolling linear predictor
4. Cross-venue lead-lag via pip lead_lag
5. Regime-gated reversal + positioning-fade strategies
6. Honest-target copy on the dashboard panel
