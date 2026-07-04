# Pillar 17 — Calibrated Uncertainty & Confidence-Aware Abstention (built 2026-07-03)

## What was built
`trading/uq/conformal.py` (`TradeUQ`, `get_uq()`, `self_uncertainty_from_votes()`):
every candidate entry now carries a calibrated `p_up` (P(trade nets > 0)) and a
coverage-guaranteed return interval, and ABSTENTION is a first-class, logged decision.
Sizing consumes calibration (`PositionSizer.size(uq=...)`).

## OSS candidates & choices (no new installs — all already in .venv)
| Library | Role | Why chosen |
|---|---|---|
| **crepes 0.9.1** (henrikbostrom/crepes) | PRIMARY: `WrapRegressor` + Conformal Predictive System on journal `net_pnl_pct` → calibrated CDF → `p_up = 1 − CDF(0)` + `predict_int` intervals | The blueprint's named "calibrated CDF → scalar p_up" tool; CPS is exactly that. Validated: 91% empirical coverage at 90% target on synthetic. |
| **MAPIE 1.4.1** | Auxiliary `SplitConformalRegressor` cross-check width (reported in status), plus it already powers `cognition.calibration.CalibratedAbstainer` (SplitConformalClassifier gate) | Pillar names MAPIE; its ACI/EnbPI classes are heavier — we implement ACI directly (below) over the crepes CPS instead of switching stacks. |
| **netcal 1.4.0** | ECE of p_up vs realized wins (nightly reliability metric) + LogisticCalibration inside CalibratedAbstainer | Already the project's calibration metric layer. |
| **ACI (Gibbs & Candès 2021)** — implemented (~10 lines, no packaged CPU impl fits our journal-replay shape) | Adaptive α_t replayed chronologically over the holdout; live intervals use the adapted α | Static split conformal under-covered badly on the non-stationary journal: **0.64** observed vs 0.90 target. ACI replay restores **0.86**. This is the pillar's "adaptive time-series conformal (EnbPI/ACI)" requirement. |
| uncertainty-toolbox | NOT stitched | netcal ECE + our reliability bins already cover the recalibration metrics; adding it duplicates capability. |
| TorchCP / Laplace | NOT stitched (this step) | Torch-node and MuZero-value-head UQ are a follow-up; the trade-level gate (this build) is the pillar's sizing-facing core. |

## Key empirical findings (real journal, 2,036 closed trades)
- Only **5/2036** rows carried `brain_confidence_entry` → the (confidence→win)
  CalibratedAbstainer stays in fallback until ≥30 pairs accumulate (it is wired and
  auto-engages). Primary calibration therefore targets the **return distribution**,
  which every row has.
- Calibrated `p_up ≈ 0.25` across the board — the journal's real win rate is ~40%
  and recent trades worse. **With the default gate θ=0.55 the brain abstains on
  nearly every entry.** That is the pillar working as designed ("abstention is the
  cheapest drawdown lever"), but it also stops paper-data collection; controls:
  - `UQ_P_UP_MIN` env → lower θ
  - `UQ_GATE=0` env → advisory mode (assess + log `would_abstain`, never block)
  - `UQ_WIDTH_CAP` env → override the adaptive width cap
- ACI-adapted intervals honestly widen (mean ≈ 62% at ±30% pnl clip) — per-trade
  outcomes are that dispersed; the adaptive width cap (1.25 × p90) scales with it.

## Wiring map
- Gate: `brain_executor.run_once` (crypto, after all confidence adjusters, before
  /forceenter) + `live_loop._open_trade` (first check). Abstentions →
  `trading/state/uq_abstentions.json` (rolling 300).
- Sizing: `live_loop._size_trade` → `PositionSizer.size(uq=...)`; `p_up` becomes the
  AFML bet-sizing prob when none supplied; `size_scale=0.5` on ensemble vote entropy
  ∈ [0.85, 0.97); entropy ≥ 0.97 abstains.
- Journal: new columns `p_up | interval_width | self_uncertainty | abstain_reason`
  (schema → auto in closed-table + CSV); filled by live_loop close path and
  freqtrade_ingest (via the `entry_meta` sidecar `uq` key).
- Recalibration: `learn_loop.run_once` → `get_uq().maybe_recalibrate(6h)` → summary
  persisted to `trading/state/uq_calibration.json` + activity-feed event.
- Dashboard: `GET /api/trading/brain/metacognition` (bg-snapshot, `?recalibrate=1`),
  `MetacognitionPanel` (reliability diagram SVG + gate stats + abstention log),
  open-table columns `p_up | Interval ± | Self-Unc`.

## Self-uncertainty (honest scope note)
The pillar's semantic-entropy-over-LLM-rationales is approximated by **normalized
vote entropy of the strategy ensemble** (longs/shorts from the library decider) —
CPU-free, per-decision, measures the same "brain disagrees with itself" quantity.
LLM semantic entropy can be layered on when debate (Pillar 18) lands.
