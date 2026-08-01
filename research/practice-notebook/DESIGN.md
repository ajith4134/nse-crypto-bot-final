# The Practice Notebook — ultra-advanced design

Owner ask (2026-07-21, verbatim intent): a new brain feature "like a practice note book or a
calculating paper we use to do all the calculation during an exam — experiment on the paper and
only write the correct answer in the answer sheet." After the brain picks entry-time + direction,
it must **practice / catch whether the symbol is actually moving as predicted**, and **only after
it double-confirms the direction** may it open a trade. If it goes the **opposite** way, **find
WHY and LEARN** so next time the direction call is better. **Practice on ALL 600+ symbols**, not
the top 60/80 — and only trades that are moving as predicted get opened.

This is a **prediction-grading + confirmation gate**, NOT a shadow/advisory trade lane
(honours the `no-shadow-on-paper` hard rule): practice attempts create **no positions** — they
record a prediction and grade it against realised price (same mechanism the D1 truth-ledger
already uses). Real paper trades open only for candidates we would trade anyway, once confirmed.

---

## The exam metaphor → real system

| Exam concept | System component |
|---|---|
| Rough / calculating paper | `PENDING` attempts scratchpad — predictions being watched, not yet traded |
| Doing every practice question | Universe-wide continuous prediction on ALL ~450–600 perps (in-RAM candles, zero extra network) |
| Double-check before writing the answer | N-of-M confirmation gate (default 2 confirmations) on realised price direction |
| Answer sheet | Real paper trades — only confirmed attempts are copied here |
| Reviewing the questions you got wrong | "Why did it go opposite" diagnostic post-mortem |
| Getting better each exam | Calibration + learned confirmation policy + auto-mined refusal rules |
| Skipping a question you can't solve | Abstention gate — low calibrated confidence → never even attempted |

---

## Layer 1 — Universe-wide practice (all 600+ "questions")
A continuous scanner over EVERY perp, driven off the **in-RAM candle mirror**
(`inram-candles-and-coverage-lane`) so it costs **zero extra Binance calls** (this is why we can
practise on all symbols without re-triggering the 418 ban that forced the 250 cap). Each candle,
for each symbol, it asks the existing brain (`brain_sources` / `BrainDecider` / `learned_direction`
/ `mom_ts` / `indicator_fusion`) for a **direction + magnitude + confidence** and writes a
**practice attempt** to the rough book: symbol, tf, predicted dir, predicted move %, confidence,
the full per-lens vote breakdown, regime, entry ref price, timestamp. No position is opened.

## Layer 2 — The confirmation gate (double-check before the answer)
For candidates the funnel actually intends to trade:
- **Pick** → written to rough book as `PENDING`, **not opened**.
- **Confirm** → over a short window (config `NOTEBOOK_CONFIRM_WINDOW_MIN`, default watch the next
  1–3 one-minute sub-bars) require **N-of-M confirmations** (default 2):
  1. realised price moved in the predicted direction beyond a noise floor (`> k·ATR` and
     `> round-trip cost`), and
  2. an independent second check still agrees — next favourable sub-bar AND the microstructure
     signal (OFI / book-state, `book-state-beats-order-flow`) hasn't flipped against us.
- **Write answer** → double-confirmed ⇒ open the real paper trade, tagged `via=notebook` with the
  measured confirmation latency stored on the journal row.
- **Reject + diagnose** → goes opposite, or window expires unconfirmed ⇒ **do NOT open**; run Layer 3.

Gate scope = **everything** (owner decision): Freqtrade `confirm_trade_entry()` asks the notebook
`is_confirmed(pair, side)` — no crypto entry opens on any lane unless the notebook says confirmed.

## Layer 3 — "Why did it go opposite" diagnostic + learning
When an attempt fails confirmation, a post-mortem runs and writes a **mistake note**:
- **Attribution** — which lenses/features voted the wrong way (reuse decision-memory SHAP +
  per-lens vote breakdown) → name the culprit signal(s).
- **Regime** — which regime were we in; is this lens historically wrong in that regime?
- **Microstructure** — was there an OFI/book-state signal contradicting the pick that we ignored?
- **Cross-symbol / beta** — was the whole market moving the other way?
- Update **truth-ledger** per-(lens, regime) trust weights: the lens wrong here loses weight *in
  that regime*. Over time the notebook learns **which signals to trust WHEN**.
- Emit an FSRS/continuous-learning card + a hypothesis-ledger reflection so the wrong call trains
  the next prediction (owner's "learn so next time it predicts correct direction").

## Layer 4 — Calibration & self-improvement (get better each exam)
Because we grade thousands of predictions fast (all symbols, every candle):
- **Calibrated P(direction correct | features, regime, tf)** via conformal UQ (Pillar 17 / crepes).
- **Learned confirmation policy** — a small bandit over (window length, threshold, N-of-M) that
  maximises *confirmed-and-right* while minimising *confirmed-and-wrong* and *rejected-would-have-won*.
- **Abstention gate** — calibrated confidence below threshold ⇒ skip the question, never attempt.
- **Refusal-rule mining** — pysubgroup (`trade-postmortem-engine`) mines "conditions where confirmed
  trades still lose" ⇒ auto-proposes new refusal rules to the hypothesis ledger.

## Layer 5 — Honest dashboard surface ("the notebook you can look at")
Panel **Practice Notebook**, all state-file-backed (atomic tmp+rename, route reads state only):
- **Rough page** — live `PENDING` attempts with a confirmation meter (predicted dir, current move
  vs threshold, confirm count).
- **Answer sheet** — confirmed → opened, with confirmation latency.
- **Mistakes book** — rejected attempts grouped by diagnosed cause (culprit lens/regime).
- **Report card** — rolling direction hit-rate overall + per-lens + per-regime, calibration curve,
  and the measured P&L lift of the gate (confirmed trades vs rejected attempts' realised outcomes).

---

## How this resolves the momentum vs mean-reversion tension
The notebook is **direction-agnostic**. Whether a pick is a momentum-LONG or a dip-reversion-LONG,
it must confirm the same way. Universe-wide practice then reveals **empirically, per regime**, which
of the two the brain should trust — the data decides, not an opinion. (Owner approved building all
three: momentum-LONG lane + dip-reversion lane + this gate.)

## Real integration points (honest wiring)
- Data: in-RAM candle store (`inram-candles-and-coverage-lane`).
- Prediction: `brain_sources`, `BrainDecider` (`trading/online/live_loop.py`), `learned_direction`,
  `mom_ts`, `indicator_fusion`.
- Gate hooks: `trading/broker_sense/run_funnel_loop.py` (propose) + Freqtrade
  `MlBridgeStrategy.confirm_trade_entry()` (open-or-not).
- Learning: decision-memory (FinMem + reflections), truth-ledger, hypothesis ledger, FSRS,
  trade-postmortem (pysubgroup).
- UQ: crepes conformal (Pillar 17).
- State/config: `trading.state` STATE_DIR + atomic writes; `.env` knobs, config-driven.

## Hot-path note
Universe-wide prediction every candle is a hot loop. Reuse cached feature vectors from the in-RAM
store; vectorise. Measure; if Python is >2× too slow, numba the inner loop (`hot-path`), Python stays
the oracle.

## New `.env` knobs (config-driven, defaults shown)
- `NOTEBOOK_ENABLED=1`
- `NOTEBOOK_CONFIRM_WINDOW_MIN=3`
- `NOTEBOOK_CONFIRMATIONS_REQUIRED=2`
- `NOTEBOOK_NOISE_ATR_K=0.5`
- `NOTEBOOK_ABSTAIN_BELOW=0.52`
- `NOTEBOOK_PRACTICE_ALL_SYMBOLS=1`
