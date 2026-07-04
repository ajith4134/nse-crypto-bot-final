# Understanding — "I built a neural network that trades stocks" (Joshua Kyan Aalampour)

Source: 24.07 s vertical short (720p, dated 10/24/2025), 4 extracted frames + full speech transcript.
Files: `transcript.md`, `frames/f_0001_000.jpg` (t=1.94s), `frames/f_0013_001.jpg` (t=13.6s), `frames/f_0016_002.jpg` (t=16.75s), `frames/f_0021_003.jpg` (t=21.43s).

## Summary

A 24-second talking-head short in which the creator claims he built a neural network that trades stocks and was "consistently profitable for the last five years, even when the market was bleeding in 2022." He describes the pipeline in one breath: on every bar, a 64x12 feature window is fed through a causal temporal convolutional network (TCN); the resulting embedding is converted into a next-bar (up) probability; and position sizing comes from a "proprietary risk map" consisting of (a) a neutral-zone dead band around the probability, (b) signal scaled inversely with forecast volatility, and (c) a hard exposure cap. He closes with "I still have a lot to learn, but I'm pretty happy with this so far." Visually the clip contains almost nothing technical: one stylized graphic of a fully-connected MLP-style network (Inputs → HL 1 → HL 2 → Outputs, ~8 input nodes, two tall hidden columns, 1 output node) above a "2022 Backtest Curve" stats block that is entirely ZEROED OUT (SHARPE 0.00, TRADES 0, MAX DD "--", CAGR 0.00%, EQUITY $1,000,000 (+$0), LAST PNL $0.00) with the disclaimer "Not financial advice. Research preview only."; two selfie frames of the speaker; and one near-black frame with only an empty box and a truncated "Ra·" glyph visible (illegible). No code, no equations, no real equity curve, and no non-zero performance numbers are ever shown — the profitability claim is spoken only and is directly contradicted by the all-zero on-screen backtest panel.

## Exact on-screen content

- Frame f_0001_000.jpg [00:01.9]: network diagram labeled `Inputs`, `HL 1`, `HL 2`, `Outputs` (dot columns; ~8 inputs, 2 tall hidden layers, 1 output). Text block:
  - `2022 Backtest Curve`
  - `SHARPE 0.00` | `TRADES 0` | `MAX DD --`
  - `CAGR 0.00%` | `EQUITY $1,000,000 (+$0)` | `LAST PNL $0.00`
  - `Not financial advice. Research preview only.`
- Frame f_0013_001.jpg [00:13.6]: selfie, speaker talking indoors. No technical content.
- Frame f_0016_002.jpg [00:16.8]: almost entirely black; a thin empty rectangular box near the top and faint serif text starting `Ra` (rest illegible). No recoverable technical content.
- Frame f_0021_003.jpg [00:21.4]: selfie, speaker talking. No technical content.
- No code, formulas, architecture hyperparameters, tickers, data sources, or broker/exec details appear anywhere in the video.

## REQUIREMENTS (every distinct claim/technique/element)

- REQ-JKA-01 [00:00] — Core claim: a neural network that trades stocks end-to-end (signal → sizing → trades). (audio only)
- REQ-JKA-02 [00:00–00:04] — Performance claim: consistently profitable over the last five years, including the 2022 bear market. Unverified — the only shown backtest panel (frame f_0001_000) is all zeros.
- REQ-JKA-03 [00:04–00:07] — Per-bar inference: the model runs on EVERY bar (bar-driven event loop, not periodic/portfolio-batch).
- REQ-JKA-04 [00:07] — Input representation: a 64x12 feature window per decision, i.e., 64 lookback bars x 12 features per bar. (Feature identities never disclosed.)
- REQ-JKA-05 [00:07] — Model architecture: a CAUSAL Temporal Convolutional Network (dilated causal 1-D convolutions; no future leakage) producing an embedding of the window.
- REQ-JKA-06 [00:11] — Prediction head: the TCN embedding is mapped to a next-bar probability (binary directional probability for the next bar).
- REQ-JKA-07 [00:11–00:15] — A "proprietary risk map" layer sits between the probability and the order — the claimed "real secret sauce" is the sizing/risk overlay, not the predictor.
- REQ-JKA-08 [00:15] — Risk map component 1: neutral-zone dead band — when the probability is within a no-trade band around neutral (~0.5), take no position (abstain).
- REQ-JKA-09 [00:15–00:19] — Risk map component 2: position size scaled inversely with FORECAST volatility (a volatility forecast is an explicit model input to sizing; vol-targeting style size ∝ signal / σ̂).
- REQ-JKA-10 [00:19] — Risk map component 3: capped exposure — a hard maximum position/leverage cap after scaling.
- REQ-JKA-11 [frame f_0001_000, 00:01.9] — Visual architecture shown is a plain fully-connected MLP graphic (Inputs → HL 1 → HL 2 → Outputs, single output node), which does NOT match the spoken TCN claim; treat as decorative.
- REQ-JKA-12 [frame f_0001_000, 00:01.9] — Backtest presentation elements: a named-year backtest panel ("2022 Backtest Curve") with metrics SHARPE, TRADES, MAX DD, CAGR, EQUITY (start $1,000,000 with delta), LAST PNL — a compact metric set worth mirroring in any redesign's reporting UI. All values shown are zero/blank.
- REQ-JKA-13 [frame f_0001_000, 00:01.9] — Disclaimer framing: "Not financial advice. Research preview only." (paper/research mode, not live-money claims).
- REQ-JKA-14 [00:19–00:22] — Author's own caveat: "I still have a lot to learn" — the system is presented as an early-stage personal project, not a validated product.

## Open questions (not answered by the video)

1. Which 12 features per bar, and what bar timeframe (minutes? daily?) — completely unspecified.
2. TCN hyperparameters (layers, dilation schedule, channels, receptive field vs the 64-bar window), training objective (BCE on next-bar direction?), and train/test split.
3. What produces the "forecast volatility" (GARCH? another head of the network? realized-vol EWMA?).
4. Dead-band thresholds, exposure cap value, long-only vs long/short.
5. Universe (which stocks?), costs/slippage assumptions, and any actual evidence for the 5-year profitability claim — the only metrics ever shown are all zeros ("research preview"), so the claim is entirely unsubstantiated on screen.
6. What frame f_0016_002 was meant to show (a black card with an empty box and truncated "Ra·" text — likely a title/quote card lost to keyframe timing).
