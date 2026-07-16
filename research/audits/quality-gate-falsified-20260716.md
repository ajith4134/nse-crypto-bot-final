# The quality gate (CRYPTO_MIN_SCORE / CRYPTO_MIN_PSR) — measured 2026-07-16

**Owner's question:** how are these calculated, are they giving profitable trades, and is there a
more solid/advanced way using all the new data?

**Verdict: the gate has NO measurable predictive power over profit — and at its current value it is
a NO-OP that filters nothing. Do not tune it. Replace it, but only after the new inputs are proven.**

---

## 1. How they are calculated today (`trading/crypto/freqtrade/percoin_decider.py`)

**`final_score = sharpe × brain_weight`**, gated by `CRYPTO_MIN_SCORE`:
- `sharpe` (`_backtest_stats`, line ~194): vectorized backtest of each of ~142 library strategies on
  **that coin's last ~500 5-minute bars (~42 h)**. Position at bar *i* from the signal known at *i*,
  earns the *i→i+1* return (strictly causal, no lookahead). Then
  `sharpe = mean(strat_ret)/std(strat_ret) × √105120` (annualized: 12/h × 24 × 365).
- `brain_weight`: TradeOutcomeNet confidence multiplier (trained on the closed journal).
- The tournament ranks all ~142 candidates and keeps the single best.

**`deflated_psr`**, gated by `CRYPTO_MIN_PSR` (Pillar-20 anti-overfit):
`probabilistic_sharpe_ratio(best.sharpe, n_active, sr_benchmark=expected_max_sharpe(var_sr, n_trials))`
— the winner must beat the *expected maximum* Sharpe of that many trials (López de Prado's DSR).

## 2. THE GATE IS A NO-OP AT ITS CURRENT VALUE

`CRYPTO_MIN_SCORE=0.25`. The **observed** `final_score` on real trades ranges **9.74 → 340.08**.
The lowest score ever recorded is ~39× the threshold. **Nothing is ever filtered.** The gate is
switched on, produces a number, and rejects nothing — the selectivity is imaginary. (Same shape for
`CRYPTO_MIN_PSR=0.10`.) This alone explains "it is not giving profitable trades": it is not choosing.

## 3. AND THE SCORE DOES NOT PREDICT PROFIT ANYWAY

n=260 closed trades that carry their own gate scores (`decision_snapshot.brain`). Realized:
**win rate 29.2%, mean −0.213%, median −0.112%.**

Pearson correlation of each gate input with the trade's realized return:

| gate input | n | corr with realized return |
|---|---|---|
| `final_score` | 260 | **−0.0311** |
| `sharpe` | 260 | **−0.0312** |
| `deflated_psr` | 245 | +0.0286 |
| `p_win` | 252 | +0.0032 |
| `brain_weight` | 259 | +0.0038 |
| backtest `win_rate` | 259 | **−0.1083** |

With n=260 the standard error is ≈0.062, so everything except `win_rate` is **statistically
indistinguishable from zero**. Not "weak" — *zero*. `win_rate` at −0.108 (~1.7 se) is the only hint
of structure and it points the **wrong way**: strategies with better backtest win rates did *worse* live.

**Win rate + mean return by score quartile — the gate is non-monotonic and the top quartile is the worst:**

| quartile | n | score range | win rate | mean return |
|---|---|---|---|---|
| Q1 (lowest) | 65 | 9.74–17.02 | 26.2% | −0.433% |
| Q2 | 65 | 17.05–22.16 | 33.8% | −0.055% |
| Q3 | 65 | 22.40–37.25 | 33.8% | −0.020% |
| **Q4 (highest)** | 65 | 38.09–340.08 | **23.1%** | **−0.345%** |

**Every quartile loses money, and the highest-scoring trades are the worst of all.** A higher score
is not evidence of a better trade. Raising the threshold would not help — it would select Q4.

## 4. WHY it fails (structural, from the code — not speculation)

1. **Annualizing 42 hours of 5m bars by √105120 amplifies noise ~324×.** A Sharpe estimated from
   ~500 bars is dominated by sampling error; the ×√periods scaling makes tiny mean differences look
   like huge "annualized" numbers (hence scores of 340). It is a noise statistic wearing a units label.
2. **In-sample selection over ~142 candidates on the SAME window.** The winner is the *luckiest*
   strategy on those 42 hours, not the best one. DSR is a partial correction, but it is fed
   `n_active` (bars *held*) as the sample size, which overstates the number of independent
   observations, and `var_sr` from the candidate pool understates the true trial multiplicity.
3. **No out-of-sample validation at all.** The pick is fitted and scored on one window; nothing
   checks it on unseen data. The repo already has purged/embargoed CV + PBO in
   `trading/strategy/guardrails.py` — the gate does not use them.
4. **It is a BACKTEST statistic, not a forecast.** "Did well in the last 42 h" ≠ "will do well in the
   next hour". The −0.108 `win_rate` correlation is consistent with **mean-reversion of strategy
   performance**: the strategy that just won tends to lose next. If that holds up, the current gate
   is selecting precisely the wrong strategies.
5. **It uses NONE of the new data.** The gate is pure OHLCV backtest × brain weight. Zero
   microstructure: no OFI/GOFI, no book imbalance, no microprice, no spread, no taker flow, no OI,
   no funding, no liquidations.

## 5. The better way — and the honest order to build it

The pieces already exist in this repo: the truth ledger (111k labels), `direction_model` /
`learned_direction`, conformal UQ with abstention (Pillar 17, crepes CPS+ACI), and purged-CV/PBO/DSR
guardrails. As of today the **inputs** exist too: true L2 OFI/GOFI/OBI/microprice/spread/depth on
213 coins at ~109 book events/bar, plus taker flow, OI, crowd/smart long-short, funding, liquidations.

**The right gate is a direct, calibrated forecast of the trade's outcome — not a backtest statistic.**
Concretely: predict `E[return]` (or `P(win)`) for *this coin, this direction, right now* from the
microstructure feature vector; fit it on the truth ledger + journal outcomes with **purged, embargoed
CV**; gate on **calibrated predicted edge net of fees**, with conformal abstention when the interval
straddles zero. That replaces "this strategy looked good for 42 h" with "this trade has a measured
edge", and it is the only version that can be honestly validated.

**But the order matters, and this is the part not to skip.** Today's measurements say the direction
inputs are the ceiling: overall accuracy 0.4922 across 111k labels, exit horizon 0.4427. The new
microstructure inputs have **never been tested for signal** — they started flowing today. Building an
"advanced" gate on unvalidated inputs would just be a more sophisticated way to be wrong, and it
would look convincing while doing it.

**So:**
1. **Now — capture the evidence.** Record the full microstructure feature vector *at entry* for every
   trade, alongside the realized outcome. Only 260 of 7,526 closed trades carry any gate score today,
   and none carry the new inputs. Without this, the replacement cannot be fitted or validated.
2. **Days — test the inputs** (the Input Hunt, `research/fable5/PROMPTS-BRAIN.md` B1/Prompt 1): do
   OFI/GOFI/taker/OI carry signal at the horizons we actually trade? Purged CV, honest OOS.
3. **Then — fit the gate** on whatever survived, gate on calibrated edge + conformal abstention, and
   promote it only if it beats the measured **29.2% / −0.213%** baseline out-of-sample.

**Meanwhile, on paper, do NOT tighten the gate.** Paper is the lab (CONVENTIONS §15) and the goal is
data. The current gate rejects nothing, which — for *gathering* data — is accidentally the right
behavior. The bug is that it is **reported** as a quality gate while doing nothing. Its real cost is
the ~7.5 s/coin tournament of 142 strategies it spends to produce a number with no predictive power
(`perf-scan-cpu-bound`: 97% of scan CPU) — that CPU is the thing worth reclaiming first.
