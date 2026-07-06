# Ultra-advanced indicator-fusion entry method (broker-sense)

Research + design note for the "use indicators to open trades" ask (2026-07-06).
Owner ask: the brain already *computes* MA/EMA/Bollinger/SAR/Supertrend/ADX/RSI from raw
candles (there is no URL for these — they are client-side in TradingView) and reads chart
*patterns* via vision. Design an **ultra-advanced way to USE them for entry**, not a naive
EMA cross.

## Why not a single indicator / single timeframe
A lone indicator is a coin-flip in the wrong regime: EMA-cross whipsaws in chop, RSI mean-
reversion gets run over in a trend. The edge is in **agreement across independent lenses and
across horizons**, gated by **regime**, then **filtered by a second model that decides whether
the primary signal is worth acting on**. That is the stack below.

## The stack (grounded in SOTA)

### 1. Full indicator suite per timeframe (raw candles → numbers)
Computed on 1m/5m/15m/1h/4h/1d from the same OHLCV the funnel already fetches:
- **Trend:** SMA/EMA ribbon (9/21/50/200), MACD, **Supertrend** (ATR 10 × 3.0), Parabolic SAR.
- **Regime/strength:** **ADX + DMI (+DI/−DI)** — the gate; ATR (volatility); Bollinger
  bandwidth (squeeze vs expansion).
- **Momentum/exhaustion:** RSI(14), Stochastic-RSI.
Each indicator emits a per-TF vote in {−1, 0, +1} plus a confidence.

### 2. Regime gate (ADX/DMI + Bollinger bandwidth) — trade only when the regime fits
- **Trending** (ADX > 25 and DMI agrees): take **trend-following** confluence (Supertrend/EMA/
  MACD). Mean-reversion signals are ignored.
- **Ranging** (ADX < 20, Bollinger squeeze): trend signals are down-weighted; only high-conviction
  reversion at band edges counts, or the symbol is **abstained**.
- Grounded in the SOTA "only signal when ADX>20 and DMI confirms" filter and the Trend-Quality-
  Index idea of a continuous 0..1 regime score modulating conviction.

### 3. Multi-timeframe confluence score (higher TF weighted more)
Weighted sum of per-TF votes with **horizon weighting** (1d/4h set the *bias*, 1m/5m set the
*timing*). Weights ≈ {1m:0.6, 5m:0.8, 15m:1.0, 1h:1.3, 4h:1.6, 1d:2.0}. The higher TF acts as a
**directional veto**: never take a long when the 1d Supertrend is red (the "daily bias" rule).
Output is a continuous confluence ∈ [−1, +1].

### 4. Vision pattern lens (independent of the numbers)
The multi-TF candlestick **screenshots** (chart_vision) are read by the CNN/VLM for
*pattern* direction. This is a genuinely independent signal (it sees engulfing/pin-bar/flag
shapes the scalar indicators don't encode). Fused with the numeric confluence as a separate lens
so the two must broadly agree for a high final score (disagreement → shrink conviction).

### 5. Meta-labeling (López de Prado, *Advances in Financial ML*)
The confluence+vision block is the **primary model**: it proposes the **side** (long/short).
A **secondary model decides whether to ACT** (take/skip + size) — trained on **triple-barrier**
outcomes of past entries from the trade journal. This is exactly what the project's existing
**UQ conformal gate** (`trading/uq`) and **TradeOutcomeNet** already provide, so meta-labeling is
*wiring*, not a new model: primary side from fusion → UQ/outcome gate abstains or sizes.
- Meta-labeling is shown to lift precision/F1 and cut false entries vs acting on every primary
  signal (Hudson & Thames; de Prado).

### 6. Triple-barrier entry/exit geometry (ATR-scaled)
From the winning side + current ATR, emit a concrete order plan:
- **entry** = mid (or a small pullback toward EMA for trend entries),
- **stop** = entry ∓ k_stop·ATR (k≈1.5),
- **target** = entry ± k_tp·ATR (k≈2.5 → ≥1.5R),
- **time barrier** = N bars of the trigger TF.
These barriers *are* the labels the meta-model learns from next time — the loop closes.

## Final decision object (attached to `decision_snapshot["app_signals"]["indicator_fusion"]`)
```
{ regime, adx, confluence,          # [-1..1] numeric multi-TF confluence
  vision_agree, p_up, direction,    # fused with the vision lens
  per_tf: {tf: {vote, supertrend, ema, macd, rsi, adx, ...}},
  entry, stop, target, rr, atr,     # triple-barrier geometry
  meta: {act, size_mult, reason} }  # meta-label decision (UQ/outcome gate)
```
Honest: every field derives from real candles + real vision; `unavailable` when data is missing,
never a fabricated number.

## Reuse map (project code, not from scratch)
- OHLCV fetch + parallelism: `fast_candles._ohlcv_fast` / `data_failsafe.ohlcv`.
- EMA/RSI primitives: `fast_candles._ema`, `_rsi` (extended with SMA/ATR/ADX/Supertrend/SAR/BB/MACD).
- Vision lens: `chart_vision.ChartVision.read` (extended to 1m,5m,15m,1h,4h,1d) + `cnn_direction`.
- Meta-label gate: `trading/uq` conformal gate + TradeOutcomeNet (already in the executor path).
- Merge point: `funnel` VERIFY stage → `app_signals` → `decision_snapshot`.

## Sources
- Marcos López de Prado, *Advances in Financial Machine Learning* — triple-barrier + meta-labeling.
- [Triple Barrier / meta-labeling — Quantreo](https://www.newsletter.quantreo.com/p/the-triple-barrier-labeling-of-marco)
- [Does Meta Labeling Add to Signal Efficacy? — Hudson & Thames](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/)
- [Algorithmic crypto trading: info-driven bars + triple barrier + DL — Financial Innovation (Springer, 2025)](https://link.springer.com/article/10.1186/s40854-025-00866-w)
- [Multi-TF AI SuperTrend with ADX — TradingView](https://www.tradingview.com/script/FeoUBe91-Multi-TF-AI-SuperTrend-with-ADX-Strategy-PresentTrading/)
- [Multi-Timeframe Adaptive Market Regime strategy — FMZQuant](https://medium.com/@FMZQuant/multi-timeframe-adaptive-market-regime-quantitative-trading-strategy-1b16309ddabb)
- [Adaptive SuperTrend + Trend Quality Index (4-layer confluence)](https://www.mql5.com/en/blogs/post/769330)
