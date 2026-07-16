# Gate rebuild — research synthesis + the exact entry field list (2026-07-16)

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
