# Direction Ceiling Research — raising crypto-perp SIGN accuracy above ~0.54

Horizon: 15 min – 4 h holds, ALL Binance USDⓈ-M perps, CPU-only, paper brain.
Date: 2026-07-17. Author: quant-microstructure research pass.

---

## 0. Bottom line up front

The literature and our own measured findings converge on one uncomfortable truth:
**at a 15 min–4 h horizon, microstructure/order-flow signals (OFI, CVD, book
imbalance) have already decayed to noise. The only signals with robust,
replicated out-of-sample edge at multi-hour holds are MOMENTUM/TREND and CARRY
(funding), plus a small lead from the OPTIONS market. The gains from "better
models" (boosting, deep LOB nets, TFT) are mostly overfit artifacts at this
signal-to-noise; the gains from better INPUTS, regime CONDITIONING, and honest
ABSTENTION are real.** So the ceiling is raised by (a) adding the two missing
high-edge inputs we can get free (options skew, a proper trend factor), (b)
conditioning on regime, and (c) abstaining hard when no edge exists — not by a
fancier estimator.

Key evidence anchors (full cites in §5):
- LOB imbalance predicts price, but only at **500 ms–5 s**; ternary sign
  accuracy peaks ~**0.54** at 500 ms and collapses at longer horizons
  (Better-Inputs paper, arXiv 2506.05764). That 0.54 is the SAME number we see
  at multi-hour — i.e. we are getting *coin-flip* because the input's real power
  lives 3-4 orders of magnitude below our hold time.
- On 5-min bars, a **parsimonious linear** model on microstructure gets +1.23%
  OOS R²; **LightGBM gets −10.94% OOS R²** (catastrophic overfit under purged
  walk-forward) despite 35.9% in-sample R² (Frontiers "Microstructure alpha",
  2026). Boosting on microstructure at our SNR is a trap.
- Cross-asset transfer of microstructure models is **block-diagonal**: models do
  NOT transfer across coins (asset-idiosyncratic) but DO transfer spot↔futures of
  the same asset (same paper). → keep PER-COIN models; that is correct.
- Crypto **time-series + cross-sectional momentum / trend factor**: Sharpe
  **1.2–1.28**, the strongest replicated multi-horizon directional edge
  (Trend-Factor paper, J. Financial & Quantitative Analysis 2024; TSMOM crypto).
- Funding rate as a **direct** return predictor is near-zero (R²≈0.003), but as a
  **carry factor + contrarian-at-extremes + OI-divergence conditioner** it has
  documented edge (Fulgur/BitMEX study; two-tiered funding-market paper 2026).
- **Options lead spot**: Deribit 25-delta risk-reversal/skew extremes precede
  spot moves; selling the risk-reversal is the best risk-adjusted options trade
  (Anchorage/Deribit Insights 2025). Deribit data is **free**.

---

## 1. Q1 — strongest published predictors at 15 min–4 h, ranked by OOS edge

Ranked by *reported out-of-sample edge at OUR horizon* (not at HFT horizons where
several of these look great and then vanish):

| # | Predictor | Reported OOS edge @ 15m–4h | Notes / decay |
|---|-----------|-----------------------------|---------------|
| 1 | **Time-series momentum / trend factor** (own past return, vol-scaled) | Sharpe **1.2–1.28**; trend factor is a priced, robust cross-section signal | The single most replicated multi-hour/daily crypto direction signal |
| 2 | **Cross-sectional momentum** (rank coins by past return, long winners) | weekly Sharpe **0.67–1.28** long-short | Works at hours→days; needs the universe (we have all perps) |
| 3 | **Funding-rate carry + OI-price divergence** | funding as *direct* predictor R²≈0.003 (weak); as **carry factor** + **contrarian at extremes** meaningful; OI↑+funding↑ = crowded-long reversal setup | CONDITIONER, not a standalone side |
| 4 | **Options-implied skew / 25Δ risk-reversal (Deribit)** | options "flash signals before spot"; skew extremes precede vol mean-reversion & directional turns | Leads spot by minutes–hours; free data; BTC/ETH only |
| 5 | **Realized-vol regime (HMM state)** | 4-state non-homogeneous HMM = best 1-step-ahead; regime-switch lowers strategy vol | A CONDITIONER that gates when momentum works |
| 6 | **Cross-exchange / cross-coin lead-lag** | BTC→alt lead 16–118 s; mid-tier venues lead Binance | Mostly too fast (seconds); BTC/ETH → alt lead at 1–5 min is the usable slice |
| 7 | **CVD / aggressive-flow imbalance** | "describes, does not predict"; divergence useful as context on 15m/1h/4h | Weak standalone; decays; use as confirmation only |
| 8 | **Order-book slope/curvature/imbalance (L2 book state)** | strong at 500 ms–5 s (binary acc ~0.71 @ 40 levels, 500 ms) | **Decays to ~coin-flip by 15 min**; keep for ENTRY TIMING/execution, not the multi-hour side |

The ordering deliberately demotes the microstructure family (7,8) that intuition
loves. Our own prior finding ("OFI power is contemporaneous, 3–5 s") is *exactly*
what the LOB papers show: the edge is real but lives far below our hold time.

---

## 2. Q2 — feasibility: HAVE / FREE / PAID

| Predictor | Data status | Where |
|-----------|-------------|-------|
| Time-series & cross-sectional momentum / trend factor | **HAVE** | in-RAM multi-TF OHLCV mirror (all perps) |
| Funding-rate carry + OI divergence | **HAVE** | funding/OI already ingested |
| Realized-vol regime (HMM) | **HAVE** | regime classifier + OHLCV; add an HMM head |
| Cross-coin lead-lag (BTC/ETH → alt) | **HAVE** | cross-symbol lead-lag module + RAM mirror |
| CVD / aggressive flow | **HAVE** | true OFI/GOFI + trades |
| Order-book slope/imbalance | **HAVE** | L2 depth |
| Liquidation clusters (contrarian at extremes) | **HAVE** | liquidations feed |
| **Options 25Δ skew / risk-reversal, IV term structure** | **FREE — NOT YET INGESTED** | Deribit public REST/WS (`/public/get_book_summary_by_currency`, ticker greeks); BTC & ETH only. **This is the single free winner we do not yet consume.** |
| On-chain / whale flows | FREE-ish (rate-limited) | Glassnode paid; free: block explorers, exchange-netflow via public endpoints — **low edge at 15m–4h, skip** |
| Cross-exchange (Bybit/OKX) order flow | **HAVE (partial)** | multi-venue data pool already round-robins venues |

**Free-data winners to add:** (1) **Deribit options skew/risk-reversal** for BTC
& ETH (and use it as a market-wide risk conditioner for alts). (2) A proper
**trend/momentum factor** and **cross-sectional momentum rank** computed from data
we already hold (zero new data — pure feature engineering, highest ROI).

---

## 3. Q3 — modeling advances: what WORKS vs what is overfit hype

### Works (evidence-backed at this SNR)
- **Parsimonious, regularized linear / ridge on well-chosen features.** Beat
  LightGBM OOS by >12 R² points on 5-min crypto microstructure (Frontiers 2026).
  At our SNR, model variance dominates; shrinkage wins.
- **Regime conditioning (HMM / regime-switching).** 4-state NHHMM = best
  one-step-ahead; lowers strategy volatility. Use regime as a GATE that turns
  momentum on/off, not as a direction source itself.
- **Meta-labeling done right (López de Prado).** Primary model = the SIDE
  (momentum); secondary ML model = *whether to act and how big* (the SIZE),
  trained on {take/skip}. Meta-labeling **cannot rescue a 0.49 primary** — it only
  improves precision/sizing on a primary that is already >0.5. So apply it on the
  momentum side (which clears 0.5), never on the coin-flip microstructure side.
- **Conformal-gated abstention / selective prediction.** "When Alpha Breaks"
  (arXiv 2603.13252) implements TWO-LEVEL abstention: a strategy-level regime-trust
  gate (deploy the ranker only on trusted dates) + a position-level gate (shrink
  the most-uncertain tail). This is the right shape for us: raise *conditional*
  accuracy on the trades we DO take by abstaining on the rest. It raises realized
  edge, not headline accuracy — which is exactly our bottleneck (payoff/exit).
- **Deflated Sharpe / purged-embargoed walk-forward (López de Prado, Bailey).**
  Mandatory eval discipline — the LightGBM overfit was invisible until purged CV.

### Overfit hype at 15m–4h crypto
- **Deep LOB nets (DeepLOB, CNN+LSTM, TFT).** Match or lose to logistic
  regression/XGBoost once inputs are cleaned; "adding a hidden layer" gives no
  real gain (Better-Inputs paper). And they only "work" at sub-second horizons.
- **Gradient boosting on raw microstructure.** Catastrophic OOS collapse
  (−10.94% R²). Only safe if features are pre-aggregated, few, and shrunk.
- **Time-series foundation models** for crypto direction — no demonstrated edge
  over simple baselines (Re-Visiting TS Foundation Models in Finance, 2025).

**Net modeling stance:** primary side = momentum (linear/ridge, per-coin) →
regime gate (HMM) → conformal/meta-label abstention+sizing. No boosting/deep nets
on the direction side.

---

## 4. Q4 — what profitable systematic crypto desks actually use for multi-hour DIRECTION

Per practitioner sources (Quantt 2026 crypto-quant survey; Unravel cross-sectional
factors; Citadel Securities systematic-crypto role; TSMOM/trend literature):

- **Direction at multi-hour+ = momentum (time-series + cross-sectional) and
  carry (funding), plus value/trend factors.** These are the "systematic premia"
  desks actually run at hours-to-days. Cross-sectional alpha factors reportedly
  reach **>2 Sharpe without overfitting** when built as ranks across the universe.
- **Microstructure/order-flow is used for EXECUTION and market-making
  (seconds), not for the multi-hour side.** Colocation, order-slicing, stat-arb —
  latency-sensitive. This matches our finding that OFI's power is contemporaneous.
- **Basis/funding is harvested as CARRY** (long spot / short perp), and funding
  extremes are used as a **contrarian/risk conditioner**, not a primary side.
- Options desks note the **options market leads spot** — skew/term-structure is a
  read on direction/risk that spot-only systems miss.

**The single most important insight:** *stop trying to extract multi-hour
direction from microstructure. Build the side from momentum + carry, condition it
on regime + options skew, and abstain when the regime says "no edge."* Our 0.523
is what momentum-free, microstructure-driven direction is supposed to look like.

---

## 5. Ranked, implementable plan (edge × feasibility)

Each item: {name · expected edge · data · CPU · impl sketch as truth-ledger
source or conditioner · pre-registered success metric}. All fit CPU + RAM mirror.

### R1 — Per-coin Time-Series Momentum direction source (vol-scaled) ★ #1
- **Expected edge:** highest of the set — TSMOM crypto Sharpe 1.2+; realistically
  a per-coin sign accuracy **0.54→0.57+** on trades taken, and (more important) a
  positive realized edge because side aligns with continuation, not noise.
- **Data:** HAVE (multi-TF OHLCV). No new data.
- **CPU:** trivial (rolling returns + vol scaling).
- **Sketch — new truth-ledger source `mom_ts`:** for each coin, side = sign of
  vol-scaled blended past return over lookbacks matched to hold (e.g. 1h/4h/12h
  EWMA returns / EWMA realized vol). Emit side + confidence = |z|. Register as a
  first-class truth-ledger source so its realized edge is measured per coin.
- **Pre-registered metric:** on n≥200 closed trades/coin, sign accuracy on
  taken-trades ≥ **0.55** AND binomial p<0.05 vs 0.50 AND truth-ledger realized
  edge > 0; else demote. Compare against current side as control (honor
  DIRECTION-MUST-BE-EARNED: never invert; abstain if underpowered).

### R2 — Cross-sectional Momentum rank conditioner
- **Edge:** weekly long-short Sharpe 0.67–1.28; complements R1 (low correlation).
- **Data:** HAVE (whole perp universe in RAM).
- **CPU:** cheap (rank across ~200 coins each bar).
- **Sketch — conditioner `mom_xs`:** each bar, rank all perps by past return;
  boost long-confidence for top-decile, short for bottom-decile; neutral middle.
  Feeds the sizing/abstention layer, not a standalone side.
- **Metric:** among trades where mom_xs agrees with side, win-rate ≥ +3pp vs
  disagree, n≥200; else drop.

### R3 — Deribit options skew / risk-reversal conditioner (FREE new data) ★
- **Edge:** options lead spot; skew extremes precede directional turns. BTC/ETH
  direct; market-wide risk read for alts.
- **Data:** FREE — Deribit public API (not yet ingested). BTC & ETH only.
- **CPU:** trivial (poll 25Δ RR + IV term slope every few min into RAM).
- **Sketch — conditioner `opt_skew`:** compute 25-delta risk-reversal and ATM IV
  term-structure slope; extreme put-skew = downside-protection demand (risk-off
  conditioner) / mean-reversion setup; use as a market-regime gate for alts and a
  direct lean for BTC/ETH. Store in RAM mirror like funding/OI.
- **Metric:** as a gate, trades taken when opt_skew regime ≠ "stressed-off" show
  win-rate ≥ +2pp vs ungated, n≥150; as BTC/ETH lean, sign accuracy > 0.52 p<0.05.

### R4 — HMM regime gate (turns momentum on/off)
- **Edge:** 4-state NHHMM best 1-step-ahead; lowers vol; momentum only pays in
  trending/normal-vol regimes.
- **Data:** HAVE. **CPU:** hmmlearn on returns+RV, cheap; refit hourly.
- **Sketch — conditioner `regime_hmm`:** latent states {trend-up, trend-down,
  chop, high-vol}. Gate: allow R1/R2 sides only in trend/normal states; abstain in
  chop/high-vol. Feeds abstention layer.
- **Metric:** trades in "allowed" states beat "blocked" states win-rate by ≥5pp,
  n≥200; else the gate is noise → drop.

### R5 — Conformal / meta-label abstention + sizing layer (raise conditional acc)
- **Edge:** does not lift headline accuracy but lifts accuracy AND realized edge
  ON TRADES TAKEN by abstaining on low-confidence — directly attacks the 0.523
  "we trade coin-flips" problem. This is the highest-leverage MODELING change.
- **Data:** HAVE (uses R1–R4 outputs + realized outcomes).
- **CPU:** conformal calibration is O(n) sort; trivial. Meta-label = small
  logistic on {take/skip}.
- **Sketch:** two-level gate à la "When Alpha Breaks": (1) regime-trust gate
  (R4) decides deploy-or-abstain per bar; (2) position gate = conformal
  nonconformity on the momentum confidence → trade only if predicted-correct set
  excludes the wrong side at target risk α; size ∝ meta-label prob. Meta-label
  trained only on the momentum primary (which clears 0.5), NEVER on microstructure.
- **Metric:** on taken subset, sign accuracy ≥ **0.57** and realized edge/trade >
  baseline (−0.213%), with abstention rate reported; coverage guarantee held
  within ±3% of target α on rolling window.

### R6 — Funding-carry + OI-divergence contrarian conditioner
- **Edge:** modest; contrarian at extremes; crowded-long detection.
- **Data:** HAVE. **CPU:** trivial.
- **Sketch — conditioner `carry_oi`:** flag {funding percentile extreme} ×
  {OI rising with price} = crowded → dampen/への contrarian lean; fold into R5
  sizing. Not a standalone side.
- **Metric:** trades opened AGAINST an extreme-crowded flag win-rate ≥ +3pp vs
  with-crowd, n≥150.

### R7 — BTC/ETH → alt lead-lag micro-conditioner (1–5 min slice only)
- **Edge:** small; only the 1–5 min lead is usable at our horizon (second-scale
  leads are for HFT).
- **Data:** HAVE. **CPU:** cheap rolling cross-corr.
- **Sketch — conditioner `leadlag`:** when BTC/ETH made a clean 1–5 min move,
  lean pending alt entries in the same direction for a short window; decays fast.
- **Metric:** alt trades opened within the lead window in BTC's direction beat
  others by ≥3pp, n≥150; else drop.

### Explicitly DE-PRIORITIZED (evidence says low ROI at our horizon)
- LightGBM/XGBoost/deep-LOB/TFT on microstructure for the SIDE — overfit trap.
- CVD/OFI/book-imbalance as a multi-hour SIDE — contemporaneous only; keep for
  entry-timing/execution micro-optimization at most.
- On-chain/whale flows — signal lives at days–weeks, not 15m–4h; free data thin.

---

## 6. Top-5 by (edge × feasibility) + #1 first experiment

1. **R1 Per-coin time-series momentum side** — HAVE data, trivial CPU, highest
   replicated multi-hour edge. THE side generator.
2. **R5 Conformal/meta-label abstention+sizing** — turns a 0.54 side into a
   high-conditional-accuracy traded subset; directly fixes "we trade coin-flips."
3. **R4 HMM regime gate** — cheap, well-evidenced, makes momentum pay only when
   it should.
4. **R3 Deribit options skew** — the one FREE new input with genuine lead on
   spot; BTC/ETH direct + market risk gate for alts.
5. **R2 Cross-sectional momentum rank** — free feature-engineering, complements
   R1 at low correlation.

**#1 recommended first experiment (do this before anything else):**
Stand up **R1 as a new truth-ledger source `mom_ts`** (per-coin, vol-scaled
blended momentum side) running in SHADOW against the current side, then
immediately wrap it with **R5's abstention gate**. Pre-register: on n≥200 taken
trades/coin, `mom_ts` must show sign accuracy ≥0.55 (binomial p<0.05) and
positive realized edge vs the −0.213% baseline; if the abstention-gated subset
reaches ≥0.57 with positive edge/trade, promote from shadow to live paper.
Honor the hard rules: never invert an unproven source, abstain when underpowered,
and let the truth-ledger — not intuition — decide promotion.

---

## 7. Sources
- Better inputs > deeper nets (LOB horizon decay; 0.54 ternary @500ms): https://arxiv.org/html/2506.05764v2
- Microstructure alpha, LightGBM OOS collapse, block-diagonal transfer: https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1811716/full
- Explainable patterns in crypto microstructure (cross-asset feature importance): https://arxiv.org/html/2602.00776v1
- Order-book liquidity/shape (slope, resilience): https://www.mdpi.com/1911-8074/18/3/124
- Order flow & crypto returns (order-flow raises Sharpe): https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2025-Greece/papers/OrderFlowpaper.pdf
- Trend factor, cross-section of crypto returns (JFQA 2024): https://www.cambridge.org/core/services/aop-cambridge-core/content/view/4C1509ACBA33D5DCAF0AC24379148178/S0022109024000747a.pdf/trend_factor_for_the_cross_section_of_cryptocurrency_returns.pdf
- TS & cross-sectional momentum in crypto (Sharpe): https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
- Cryptocurrency factor momentum (weekly Sharpe): https://open.icm.edu.pl/server/api/core/bitstreams/86a51c47-8cd3-4201-88ee-42f44fb89227/content
- Cross-sectional alpha factors, >2 Sharpe (practitioner): https://blog.unravel.finance/p/cross-sectional-alpha-factors-in
- Bitcoin intraday time-series momentum: https://centaur.reading.ac.uk/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf
- Funding rate weak direct predictor (R²≈0.003), mean-reversion at extremes: https://medium.com/@fulgur.ventures/bitcoin-funding-rates-and-price-predictability-27ce95535af1
- Two-tiered funding-rate market structure (2026): https://www.mdpi.com/2227-7390/14/2/346
- Funding+OI+liquidation combined signals (practitioner): https://metamask.io/news/monitoring-perps-funding-rate-trends-signals
- Deribit 25Δ skew / risk-reversal leads spot; selling RR best risk-adjusted: https://www.anchorage.com/research/the-anchorage-digital-prime-signal-what-skew-wings-and-the-term-structure-are-telling-us-about-bitcoin-and-its-adjacent-markets
- Deribit skew/BF live + interpretation: https://insights.deribit.com/industry/bitcoin-options-finding-edge-in-four-years-of-volatility-regimes/
- HMM/regime-switching crypto (4-state NHHMM best 1-step): https://link.springer.com/article/10.1007/s42521-024-00123-2
- Regime-adaptive HMM+RF trading (practitioner impl): https://blog.quantinsti.com/regime-adaptive-trading-python/
- Cross-exchange / cross-coin lead-lag (15–118 s; mid-tier leads Binance): https://www.mdpi.com/2227-7072/14/5/103
- BTC→altcoin causality & trading strategies: https://www.researchgate.net/publication/394315102_Bitcoin_and_Main_Altcoins_Causality_and_Trading_Strategies
- CVD "describes not predicts"; 15m/1h/4h context: https://markettrace.ai/blog/cumulative-volume-delta
- Conformal two-level abstention "When Alpha Breaks": https://arxiv.org/html/2603.13252v1
- Conformal predictive portfolio selection: https://arxiv.org/html/2410.16333v2
- TS foundation models no edge in finance: https://arxiv.org/pdf/2511.18578
- Crypto quant strategies survey (practitioner, what desks run): https://www.quantt.co.uk/resources/crypto-quant-strategies-2026
