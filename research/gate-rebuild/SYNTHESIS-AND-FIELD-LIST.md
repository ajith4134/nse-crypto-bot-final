# Gate rebuild — research synthesis + the exact entry field list (2026-07-16)

> **UPDATE after reading ALL 217 claims (the first pass grepped ~40 by topic).** The full corpus
> **corrects this document and my report to the owner**. Read §0 first — it overturns two things I
> told the owner, adds a contradiction I had missed, and names fields the field list below omits.

---

## §0 — WHAT THE FULL READ CHANGED

### 0.1 I OVERCLAIMED "the gate has zero predictive power" — n=260 cannot support that
> **[32|primary]** *"with 34 out-of-sample folds and an observed effect size d=0.17, the study attains
> only 12% power, and ~540 independent test periods would be needed for 80% power. This transfers
> directly to our n=260 gate-vs-profit correlation — at realistic trading effect sizes, a few hundred
> observations cannot distinguish a real edge from zero, so our measured −0.031 correlation is
> consistent with both 'no edge' and 'small edge we cannot resolve'."*

My phrasing "Not 'weak' — *zero*" was wrong. The honest claim: **underpowered; −0.031 is consistent
with no edge OR a small unresolvable edge.** What survives untouched is the **NO-OP** finding
(threshold 0.25 vs observed scores 9.74–340) — that is deterministic arithmetic, not statistics.

### 0.2 …BUT the inversion I measured is exactly what theory PREDICTS (this strengthens the verdict)
> **[95|primary]** *"Under backtest overfitting the in-sample-to-out-of-sample relationship is
> NEGATIVE, not merely zero: the regression slope of SR_OOS on SR_IS is negative in most practical
> cases, so ranking strategies by IS Sharpe actively selects the worst OOS performers. This directly
> predicts the observed −0.031 correlation and 'highest-score quartile is the WORST' pattern."*
> **[106|primary]** *"…in the presence of memory effects it systematically produces NEGATIVE
> out-of-sample performance, i.e. loss maximization… the selection gate is not noise, it is INVERTED."*
> **[105|primary]** E[max SR] over N trials inflates with zero true skill; at N≈142 the null threshold
> is ~2.5σ of cross-trial SR dispersion. **[96]** On a pure random walk, IS Sharpe 1–2.2 with 100%
> positive IS, yet ~53% of OOS negative, PBO 55%. **[71]** measured 58.6% PBO even WITH strict t+1
> and realistic costs. **[97]** overfitting is unavoidable once >1 config is tried; **[108]** holdout
> and vanilla K-fold cannot assess it at all.

So: the point estimate is underpowered, but the **Q4-is-worst pattern is the published signature of an
overfit selector**. The gate is not merely uninformative — theory says it is *inverted by construction*.

### 0.3 A CONTRADICTION inside the research I must not paper over: how deep is the book worth?
> **[110|primary]** Integrated multi-level OFI (PCA of top-10 levels, depth-scaled) **massively**
> beats top-of-book: IS R² 87.1% vs 71.2%, OOS 83.8% vs 64.6%. **[125][126]** multi-level adds real
> power. **[92]** impact β ∝ 1/depth, so depth must be recorded to normalize.
> **[87|primary]** *"A deliberately SHALLOW feature set is used and deep book levels are explicitly
> rejected as noise"* — named schema: mid, spread, L1 bid/ask volumes, signed order flow,
> buy-VWAP−mid and sell-VWAP−mid. **[121]** CatBoost on top-of-book + trade flow was **sufficient**;
> deep levels omitted as redundant; no DeepLOB/transformer needed.

**Unresolved.** Our top-20 recording is defensible (it is a superset — we can always ablate down), but
"20 levels is right" is NOT settled. Record depth, ablate later on OUR data.

### 0.4 The OFI construction we use may be the WRONG one
> **[117|primary]** *"Multi-level ORDER FLOW (per-level bid and ask flows concatenated, OF ∈ R^20 over
> 10 levels) outperforms multi-level ORDER FLOW IMBALANCE (bid minus ask, OFI ∈ R^10) — **the
> subtraction that defines OFI destroys information** the network can otherwise use… snapshot
> per-level signed bid-OF and ask-OF SEPARATELY rather than only their difference."*
> **[113]** the 10 level-OFIs are ~89% one principal component (collinear) → PCA-integrate, don't dump raw.
> **[115]** differencing the LOB into **stationary** order-flow inputs beats raw levels; *stationarity,
> not model complexity*, dominates OOS accuracy — simple LSTM matches DeepLOB once inputs are flow.

### 0.5 Even a REAL, OOS-stable OFI signal is NOT tradeable — and contemporaneous fit is a trap
> **[80]** top-of-book OFI explains ~40% of CONTEMPORANEOUS return variance but only **~3% of
> next-bucket** — ~92% of its apparent power is same-bar contamination (~13× inflated R²).
> **[81]** the correctly-lagged OFI signal IS real OOS (t=49.3, OOS R² 0.0305, almost no decay)…
> **[82]** …yet yields only a **53.0% hit ratio and Sharpe 0.12 — not tradeable after costs.**
> **[111]** for 1-minute-AHEAD returns, EVERY model tested (best-level, integrated, cross-asset,
> AR) had **NEGATIVE** mean OOS R² (−0.37 to −0.10) — worse than predicting zero.
> **[84]** OFI's recommended use is an **overlay on execution/market-making, not a standalone
> directional entry signal**. **[90]** the 65% R² is explicitly a contemporaneous impact regression.
> **[94]** much of it is mechanical/tautological (OFI contains price-changing events); excluding them
> drops R² to 35–60%, and the concave "square-root" impact of volume is partly an aggregation artifact.

### 0.6 Horizon must be in EVENT time, normalized PER COIN — not clock time
> **[116|primary]** *"the effective forecast horizon is approximately two (to three) average price
> changes… information flows at different rates for different stocks and so horizon cannot be constant
> in time across stocks."* **[29]** event/volume clocks, not 5m time bars, are the correct sampling basis.

**This reframes our whole horizon problem.** "15m–4h" may be meaningless as a fixed clock horizon; the
right unit is *this coin's own price-change rate*. → record a per-coin update/price-change rate at entry.

### 0.7 Findings that contradict our existing brain
- **[103|primary]** In crypto, **Kyle's lambda carries essentially NO feature importance** (near-zero
  MDA); the **Roll measure is the single most important** own feature, and **VPIN is frequently
  important**. We compute Kyle's lambda (`psych_kyle_lambda`) and neither Roll nor VPIN.
- **[91|primary]** OFI **strictly dominates** trade-sign/volume imbalance (R² 65% vs 32%); with both
  in the model TI's t-stat falls 4× — *"taker-flow imbalance adds nothing once book-event OFI is
  recorded."* ⚠ This **contradicts** my plan to add `trade_sign_imbalance`… but **[54]** says trade-sign
  autocorrelation is power-law/long-memory and **[53]** says impact depends on the *lagged sign* of net
  taker flow. Resolution: record **lagged signed net taker flow** (for the cost/impact model), and do
  not expect raw TI to add directional alpha on top of OFI.
- **[42|primary]** **Classification accuracy is NOT a valid proxy for P&L** — ternary selective
  classifiers hit the HIGHEST accuracy (63%) yet produced WORSE Sharpe than binary ones (~56.5%).
  Tuning on an accuracy-like metric instead of realized net P&L is *"the same failure mode as ranking
  strategies by a score uncorrelated with realized profit."* ⚠ **This indicts our entire
  direction-accuracy program (the 0.4922 number) as the wrong target.**
- **[122]** Label design beats architecture: a direction-aware loss (GMADL) is what makes forecasts
  tradable. **[121]** a CPU-friendly GBM (CatBoost) on shallow features sufficed — no GPU/DeepLOB.
- **[137]** order-flow edge does NOT generalize across assets (ETH clears, BTC does not) —
  **cross-sectional pooling can manufacture a false edge that is really one asset.**
- **[128]** cross-asset OFI (BTC/ETH) adds nothing contemporaneously but **DOES help forecasting** →
  record BTC/ETH OFI alongside each coin. **[129]** the structure is sparse — LASSO, don't dump 200 coins.

### 0.8 Execution assumption can FLIP the sign of the result
> **[89|primary]** Same signal, taker vs maker: taker positive on ETC/ENJ/ROSE (p<0.05); **maker loses
> and took catastrophic adverse-selection losses in the 2025-10-10 flash crash.** **[124]** all maker
> strategies were statistically insignificant. → **record best bid, best ask, and intended fill side.**
> **[47][130]** passive fills need queue position + BOTH feed and order latency modeled.
> **[19]** ⚠ estimating slippage by **walking the L2 book UNDER-predicts** impact — the naive method our
> 20-level snapshot invites. **[52]** use the fitted square-root law instead: on Binance BTC/USD perps
> **δ = 0.59** (not 0.5), I = k·σ_T·(Q/V_T)^δ → needs **Q (intended size), σ_T (trailing 1h vol),
> V_T (trailing 1h weighted volume)**. **[18]** δ is regime-dependent (collapses without order-splitting
> / market-making — i.e. thin alt books, liquidation cascades).

### 0.9 Concrete data-capture mandates the first pass missed
- **[107|primary]** DSR needs **seven** quantities, five beyond Sharpe — including **V[{SR_n}] across
  ALL trials (including rejected ones)** and **N independent trials**. → **log every rejected trial's
  Sharpe**, not just the winner's. **[109]** effective N from cross-strategy correlation:
  N̂ = ρ̂ + (1−ρ̂)·M → store per-trial return series. **[73]** trials must count window and
  cost-scenario re-evaluations (360–3240), not just optimizer trials.
- **[36][37][39]** sample-uniqueness weights need, per event, the **entry timestamp AND the eventual
  barrier-touch timestamp t1**; overlapping labels get down-weighted (non-IID).
- **[14]** barriers = rolling **std of log returns × multiple** → record point-in-time volatility, the
  multiples, the resulting **upper/lower price levels**, and the **vertical-barrier timestamp**.
- **[48]** record **exchange timestamp AND local receipt timestamp** separately (feed vs order latency).
- **[69]** **trade-size roundness** is a cheap recordable proxy for algo participation.
- **[120]** dominant SHAP features, stable across BTC and long-tail coins: **OFI, spread, book depth,
  and VWAP-to-mid deviation** — we do not record VWAP-to-mid.
- **[88]** predictive effects are **conditional on spread** (wider → attenuated, adverse selection) →
  spread is both a feature and a natural abstention variable.
- **[21][23]** the guarantee shape a gate needs is **conditional on acceptance** ("of the trades I take,
  error ≤ α") — standard marginal conformal does NOT give it; only **SCRC-I** (calibration-only) is
  deployable live, and it is the weaker PAC/DKW guarantee. **[24]** none of it survives non-exchangeable
  data without ACI/weighted conformal.
- **[56][57][58][59][60]** calibration measurement itself is a trap: fixed-bin ECE **underestimates**
  and is a lower bound; use **quantile/KDE** estimators + the de-biased form; Brier/NLL conflate
  accuracy with calibration; any single ECE number is an artifact of bin count.
- **[41][44]** abstention improved accuracy in **every** configuration tested, and its value **rises
  with transaction costs** — worth more in a high-fee venue like perps, not less.
- **[65]** a concrete null protocol to copy: rolling monthly OOS folds, event-clustered validation, and
  **permutation nulls with feature shuffling blocked by month, symbol, and pre-event state**.
- **[45]** ⚠ contrarian: richer feature sets did NOT help (taker-flow-augmented FS4 lost to minimal FS2;
  RF degraded on richer sets) — at a 30-min bar horizon. Weak evidence, but a caution against
  feature-dumping.

---

**Source:** two deep-research runs (`wf_1b9d76ec-ac6` formulas/labeling/validation/calibration/costs,
`wf_57b21e69-3a8` broad sweep: features/data/architectures/targets/failure-modes). Stopped by the
owner before the synthesis phase, so this file IS the synthesis. Evidence base: **197 unique claims,
189 from primary sources**, each extracted with a supporting quote; ~33 went through adversarial
3-vote verification. Raw claims + verdicts are in this directory's `*-journal.json`.

**Bottom line: the research contradicts the premise we built on today, and that is the most valuable
thing in it.** Read §1 before writing any code.

---

## 1. THE FOUR FINDINGS THAT CHANGE THE PLAN

### 1.1 Book STATE beats order FLOW — by 3-4× — at exactly our horizons
> *"The pre-event L2 liquidity state (spread, top-20 depth, top-20 imbalance) is a stronger predictor
> than order flow, improving over the marginal baseline by +0.034 (1m) and +0.045 (5m) — roughly
> 3-4x the order-flow increment."* (primary)
> *"Order flow adds only marginal predictive value over a pure L2 book-shape baseline for 1m/5m state
> transitions in BTC/ETH perps: pooled overlay improvement was +0.010 vs a flow-shuffle null 95th
> percentile."* (primary)

We spent today wiring OFI/GOFI as "the research's #1/#2 ranked drivers". At 1m/5m horizons the
**static book shape is 3-4× more predictive than the flow**. And we already capture spread, OBI and
depth. **Do not drop OFI — but stop treating it as the headline; the book state is.**

### 1.2 OFI's famous R²=65% is CONTEMPORANEOUS, not predictive
> *"OFI ... explains contemporaneous mid-price changes linearly with an average R^2 of 65%."*
> *"order-flow market impact is large and positive only at the contemporaneous 5-second bucket and
> turns slightly negative for all subsequent lags."*
> *"The paper's entire empirical edge estimate lives at a 3-second horizon."*

OFI **explains** the move happening now; it does not **forecast** the next one. Its documented power
lives at **3-5 seconds**. We trade at 15m-4h. This is the single biggest reason to expect OFI alone
to fail for us — and it independently confirms the hypothesis already written in
`research/fable5/PROMPTS-BRAIN.md`: *if OFI/GOFI fail at our horizons, the horizon itself is wrong.*

### 1.3 Order-flow power is STATE-DEPENDENT and CLOCK-PHASED (both are conditioners we don't record)
> *"for ETH the 1-minute overlay increment rises monotonically from +0.004 (calm) to +0.020 (mixed)
> to +0.038 (stressed)"* → flow only works in **stressed liquidity**; ~10× difference.
> *"Order imbalance measured at quarter-hour clock openings forecasts crypto perpetual-futures returns
> at a 4-to-12-hour horizon"*, *"strongest at quarter-hour marks and monotonically weaker at one- and
> five-minute marks"*, *"Binance perpetual contracts exhibit periodic bursts in volatility and volume
> at one-, five-, and quarter-hour marks, so unconditional pooling of order-flow features across
> clock phases mixes structurally different regimes."*

**So a flat, pooled model is structurally wrong.** Liquidity regime and clock phase must be recorded
at entry as conditioning variables — otherwise the signal averages to zero across regimes, which is
*exactly the 0.4922 we measure*. This is the most actionable finding in the whole corpus.

### 1.4 Meta-labeling CANNOT rescue our primary
> *"Meta-labeling cannot rescue a bad primary signal — it requires a primary model with genuine
> (high-recall) predictive power; against a bad primary it only limits the downside rather than
> creating edge."*
> *"OOS precision rose only 0.17 -> 0.2x"* — the gains are on filtering false positives, not raw precision.

Our primary direction is **0.4922** (a coin flip). Bolting meta-labeling onto it is not a fix. The
primary must earn real recall first, or the gate is lipstick.

---

## 2. WHAT THE RESEARCH ENDORSES (for when we do build)

- **Labels: triple-barrier + CUSUM event sampling.** *"produced positive trading performance net of
  transaction costs, and outperformed both fixed-interval time bars and next-bar prediction."*
  Pipeline: *"CUSUM event filter thresholded on point-in-time volatility -> triple-barrier labels
  whose horizontal barriers are set as the rolling standard deviation of log returns times a
  user-defined multiplier."* → **the barriers are volatility-scaled, so entry-time volatility must be
  recorded or labels are irreproducible.**
- **Validation: CPCV.** *"endorses Combinatorial Purged Cross-Validation as the best-performing
  anti-overfitting validator, with walk-forward retained for realistic simulation."* Note the
  research also repeatedly caught *papers themselves* skipping purged CV despite overlapping labels —
  a warning, not a licence.
- **Costs: fees-only is a lie.** *"a fee-only cost model inflates annualized return from 2.726 to
  4.308 (+58%) and Sharpe from 2.049 to 2.506 versus a fully costed run including slippage."*
  → **slippage and funding carry must be in the net-edge target, not bolted on later.**
  For passive/limit entries, *"net-edge estimation must model order queue position at fill time."*
- **Trade-sign imbalance has long memory.** *"Trade-sign autocorrelation in BTC/USD perps decays as a
  clean power law, empirically confirming metaorder splitting"* → persistent structure worth a feature.
- **Regime-conditionality is general.** *"the same signals produced +0.60% quarterly in
  high-volatility 2020-2024 but -0.16% in stable 2015-2019."*

### ⚠ Conformal abstention: our intended gate may be statistically invalid
> *"Naive selection/abstention BREAKS the exchangeability that conformal validity depends on;
> validity is only restored if the selection rule is symmetric across calibration and test points."*
> *"guarantees rest entirely on exchangeability ... no treatment of distribution shift, temporal
> dependence, or non-exchangeable data."*

Pillar 17 already gates trades on conformal abstention. **A threshold gate is exactly the "naive
selection" that voids the guarantee**, and crypto perps are non-exchangeable (temporal dependence,
regime drift). The fix is a symmetric selection rule (SCRC-T computes the threshold jointly over
calibration and test). **Flagged, not fixed — this deserves its own investigation.**

---

## 3. THE ENTRY FIELD LIST (what to snapshot)

Legend: **[HAVE]** already in `decision_snapshot`, **[NEW]** must add, **[FIX]** present but null/broken.

### Tier 1 — the conditioners (highest value; without these the model is structurally wrong, §1.3)
| field | why | status |
|---|---|---|
| `liquidity_regime` (calm/mixed/stressed) + the percentile it came from | flow power varies ~10× across it | **[NEW]** |
| `clock_phase_s` — seconds since the 1m / 5m / 15m mark | power is strongest at quarter-hour marks; pooling mixes regimes | **[NEW]** |
| `vol_regime` + `sigma_logret` (rolling std of log returns) | regime-conditional edge; ALSO sets triple-barrier widths | **[NEW]** |

### Tier 2 — book STATE (the strongest predictor per §1.1)
| field | status |
|---|---|
| `spread_bps` | **[HAVE]** `psych_spread_bps` |
| top-20 **depth** each side (`depth_bid_20`, `depth_ask_20`) | **[HAVE-ish]** `depth_q`/`psych_depth_slope_bias` — verify it's top-20, not top-5 |
| top-20 **imbalance** (`obi_20`) | **[HAVE]** `psych_obi` (levels=5 today → **widen to 20**) |
| `obi_l1`, book slope/curvature, `gap_map`, walls | **[HAVE]** |
| `microprice_drift_bps`, `kyle_lambda` | **[HAVE]** |

### Tier 3 — order flow (keep, but demoted; §1.1/1.2)
| field | status |
|---|---|
| `ofi` multi-level, `ofi_n` (normalized), `gofi` | **[HAVE]** `psych_ofi`/`psych_ofi_z`; **[NEW]** the book_ofi normalized + GOFI |
| `trade_sign_imbalance` (long-memory, §2) | **[NEW]** |
| `taker_buy_sell_ratio`, `taker_imbalance` | **[NEW]** (RAM, live today) |
| `book_n` (events in bar — sample-size honesty) | **[NEW]** |

### Tier 4 — positioning / carry
| field | status |
|---|---|
| `funding_rate`, `next_funding_in_s` | **[FIX]** `funding_rate_entry` is **None** despite 100% RAM coverage |
| `open_interest_usd`, `oi_change_pct` | **[NEW]** (RAM, live today) |
| `crowd_long_pct`, `smart_long_pct` | **[NEW]** (RAM, live today) |
| `liq_skew`, liquidation notional by side | **[NEW]** |

### Tier 5 — label + cost reproducibility (without these the row is unusable for fitting)
| field | why | status |
|---|---|---|
| `pt_barrier`, `sl_barrier`, `vertical_barrier_s` | triple-barrier labels must be reproducible | **[HAVE-ish]** `initial_sl`/`initial_target` — record as vol multiples |
| `fees_bps`, `expected_slippage_bps`, `participation_rate` | fee-only overstates by ~58% (§2) | **[NEW]** |
| `entry_type` (maker/taker), `queue_position` if passive | required for passive net-edge | **[NEW]** |
| `mid`, `atr`, `btc_price`, `fear_greed` | context | **[HAVE]** |
| `feature_ts` + `decision_ts` (staleness of every input) | leakage/staleness audit | **[NEW]** |

---

## 4. THE HONEST ORDER (unchanged, but now evidence-backed)

1. **Record the vector** (§3) — cheap, reversible, and the prerequisite for everything.
2. **Test the conditioners first, not the flow.** The highest-value experiment is no longer "does OFI
   predict?" but **"does book STATE, conditioned on liquidity regime and clock phase, predict at the
   horizon we actually trade?"** §1.1+§1.3 say that is where the signal is — and it reframes the
   Input Hunt in `research/fable5/PROMPTS-BRAIN.md`.
3. **Confront the horizon.** OFI's power is at 3-5s; we hold 15m-4h. Either the inputs or the holding
   period must change. The research cannot tell us which — only our own purged OOS test can.
4. **Do not add meta-labeling** until the primary has real recall (§1.4).
5. Any replacement must beat the measured baseline: **29.2% win / −0.213% mean**
   (`research/audits/quality-gate-falsified-20260716.md`).

**What this research CANNOT tell us:** whether any of it holds *in our market, at our horizons, on
our coins*. Every number above is someone else's dataset. It tells us where to look and what to
record — not what is true for us. Only a purged, embargoed out-of-sample test on our own data settles
that, which is precisely why step 1 is a recorder and not a model.
