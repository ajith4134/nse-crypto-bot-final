# MEASURED: `pct_change` is CONTRARIAN at our horizon — the momentum preset is backwards

**Date:** 2026-07-16. **Trigger:** owner — *"don't assume the sign — measure it"* (CONVENTIONS §16b:
a coin flip is a trigger, not an answer).

## The measurement

n = **2,469** closed trades carrying `pct_change` at entry (`decision_snapshot.brain.filter`):

| | |
|---|---|
| **corr(pct_change at entry, forward move)** | **−0.0689** |
| standard error (1/√n) | ≈ 0.020 |
| **significance** | **≈ −3.4 σ** |
| rose at entry (n=1084) | forward move **−0.133%** mean / −0.043% median |
| fell at entry (n=1385) | forward move **+0.067%** mean / −0.027% median |

Negative correlation = **contrarian**: big movers MEAN-REVERT over our holding period. Both subgroups
point the same way independently.

**This is NOT the underpowered case.** The gate's −0.031 on n=260 gave ~12% power and was correctly
called unresolved. This is n=2,469 at ~3.4σ — it clears the §16 bar that says *never invert without
proof*. Here there IS proof.

## What it indicts

`brain_executor._filter_side()` for the momentum preset:

```python
if pct is not None:
    return "LONG" if float(pct) >= 0 else "SHORT"     # "continue the move"
```

It **buys what just rose and shorts what just fell** — the exact opposite of the measured effect. It
is the fallthrough side whenever `learned_direction` abstains, which (correctly, post-inverter-kill)
is most of the time. So it is currently a primary direction driver.

Live corroboration: coins shorted after falling 10–13% went red — the "bounce after exhaustion" the
owner named before the measurement confirmed it.

## Caveats — state them or the number is a lie

1. **Selection bias.** These are trades we CHOSE to open, not a random sample of the universe. The
   effect is measured on our own picks; it may be weaker/absent on coins we never touched.
2. **Exit timing is ours.** "Forward move" is entry→exit, and the exit is our own smart-exit/stop —
   not a fixed horizon. So this measures *our realized path*, not a clean h-bar forward return.
   A clean test needs fixed-horizon labels (the truth ledger's 15m/1h/4h buckets).
3. **No era control.** ~30 min of the inverter era (2026-07-16 17:40–18:09) is inside this sample —
   negligible against 2,469 rows, but the era is documented in `poisoned-era-inverter-20260716.md`.
4. **Regime.** The whole sample is recent crypto. The research is explicit that signal edge is
   regime-conditional; this may be a property of THIS tape, not a law.

## Recommended next step (NOT done — owner decision)

Do **not** blind-flip the preset. Confirm on a CLEAN target first: re-run the same correlation using
the truth ledger's fixed-horizon (15m/1h/4h) labels instead of our own exit, and split by
`liquidity_regime` + `clock_phase` — the two conditioners the research says flow-type signals swing
~10× across, now recorded in `entry_vector`. If the sign holds there, flipping the momentum preset
(or better: replacing it with the measured, regime-conditioned relationship) is evidence-backed and
satisfies §16.

**If it holds, this is the first statistically real directional edge measured in this project.**
Everything else (direction 0.4922, the gate −0.031) has been noise. That makes it worth doing
properly rather than quickly.

---

# ✅ CONFIRMED ON CLEAN FIXED-HORIZON LABELS (same day, after backfilling candles)

The confound is GONE. These are forward returns read from 5m candle feathers at FIXED horizons —
not our own smart-exit. Candles backfilled via Binance's PUBLIC BULK ARCHIVE (data.binance.vision,
freqtrade's `_can_use_data_download_fast`): 765 sets, **zero rate-limit/ban hits** — static ZIPs, no
API weight, no key, cannot trigger the 418 that wedged the stack on 2026-07-12.

**n = 2,205 trades** (resolved 2213; 30 no-feather, 247 out-of-range):

| horizon | n | corr | sigma | verdict |
|---|---|---|---|---|
| **15m** | 2205 | **−0.0739** | **−3.5σ** | **CONTRARIAN — significant** |
| **1h** | 2172 | **−0.0530** | **−2.5σ** | **CONTRARIAN — significant** |
| **4h** | 2129 | **+0.0529** | **+2.4σ** | **MOMENTUM — significant** |

**THE SIGN FLIPS WITH HORIZON.** Big movers mean-revert at 15m–1h, then trend at 4h. Three
independent horizon points forming a coherent decay-and-flip — structure, not noise. Reads as
overreaction bouncing first, the underlying trend reasserting later. It also matches the deep
research's core claim that microstructure-type signals are strongest at short horizons and decay.

**What it indicts:** `brain_executor._filter_side()` does `LONG if pct>=0 else SHORT` (momentum). That
is **WRONG at 15m–1h and RIGHT at 4h**. The fix is therefore NOT "flip the preset" — it is that **the
correct side depends on the HOLDING HORIZON**, which no current code path knows. A trade opened on a
momentum prior and exited in <15m is systematically on the wrong side of a measured effect.

**Remaining caveats (state them or the number lies):**
1. **Selection bias** — measured on trades we CHOSE to open, not the full universe. The effect may be
   weaker/absent on coins never picked.
2. **One regime** — recent crypto only. The research is explicit that signal edge is
   regime-conditional; the 4h momentum leg especially could be a bull-tape artifact.
3. **Not conditioned** — `liquidity_regime` and `clock_phase` (now recorded in `entry_vector`) are the
   conditioners the research says such signals swing ~10x across. Splitting by them is the next test
   and could sharpen or dissolve this.

**This is the FIRST statistically real directional signal measured in this project** (direction 0.4922
and the gate's −0.031 were both noise). That makes it worth building on — carefully, conditioned, and
out-of-sample — rather than flipping a preset today.

**Method note for the next session:** the candle data was ALWAYS THERE (521 5m futures feathers) — it
was merely STALE (didn't cover the trade dates), and `ls | head -5` hid it because `15m`/`1d`/`1h`
sort before `5m`. If `truth_ledger` reads those same stale feathers, ITS labels may be under-resolving
too — check that.

---

# 📊 MEASUREMENT QUALITY + CLOCK-PHASE CONDITIONING (same day, after the candle backfill)

## 1. The ledger's "coin flip" is PARTLY a measurement artifact

The ledger resolves labels from a MIX and never recorded which method produced which label
(`methods` was a global COUNT only — no outcome). Of 174,279 labels: **only ~15% from real candle
feathers**; **36% from `mirror:markprice`** (a funding-anchored INDEX, not the traded price);
**44% from timing-sensitive PROBES** (`probe:ui:capture` 31% + `probe:api:ccxt-binance` 13%) that read
the price when the resolver tick fires, NOT at the horizon.

Re-resolving the journal from FEATHERS ONLY (clean 5m closes, n≈6,300/horizon):

| horizon | feather-clean | ledger (mixed) | gap |
|---|---|---|---|
| 15m | 0.4918 (−1.3σ) | 0.4887 | ~none |
| **1h** | **0.5149 (+2.4σ)** | **0.4952** | **+2.0 pp** |
| 4h | 0.5107 (+1.7σ) | 0.5092 | ~none |

**At 1h the ledger reports a coin flip while the clean measurement is significantly ABOVE chance.**
The noisy probe/markprice labels dragged a small real signal down to 0.5. FIXED: `_fold()` now writes
`method_acc[f"{method}|{horizon}"] = {n, correct}` so measurement quality is auditable going forward.
The bucket key stays `source|market|regime|horizon` (readers parse it; a 5th field would break them
and explode cardinality). Pinned by `tests/test_truth_ledger.py::TestMethodAccuracyIsAuditable`.

## 2. The 1h edge CONCENTRATES by clock phase — conditioning SHARPENS it

1h accuracy, feather-clean, by seconds-since-the-quarter-hour mark:

| phase | n | acc | σ |
|---|---|---|---|
| 0–3m past the mark | 1040 | 0.5019 | +0.1 |
| 3–7m | 1658 | 0.5109 | +0.9 |
| 7–11m | 2028 | 0.5079 | +0.7 |
| **11–15m (approaching the next mark)** | **1611** | **0.5363** | **+2.9** |

A **3.4-point spread** across phases of the same clock. The pooled 0.5149 HIDES this. Matches the
research: *"order imbalance is strongest at quarter-hour marks and monotonically weaker at finer
marks"* and *"unconditional pooling across clock phases mixes structurally different regimes."*
**First time in this project an edge SHARPENED under conditioning instead of dissolving.**

## 3. Live state after the day's fixes

Futures entry flow is HEALTHY and the direction bias is GONE: **14 open, SHORT 5 / LONG 9** (was 31
SHORT vs 1 LONG), entries landing every cycle, `learned_direction` DECIDING (not abstaining into
silence — the risk flagged when the inverter was killed did not materialise).
Cadence UNFIXED: 18:37→18:53→19:08→19:25 = 16/15/17 min. The budget cut (BROKER_SENSE_BUDGET 120→60,
FILTER_LANE_BUDGET_MULT 1.5→1.0) did NOT work — `took` even rose to 360s (a suspiciously round number
= a cap being hit). Three attempts (crawl, tournament, lane budget), three wrong levers. **The
un-run measurement is a stage-by-stage profile of ONE loop iteration from start to next start** —
attribute the 16 min instead of guessing at it.

## Caveats on 1 & 2 (state them or the numbers lie)
- Selection bias: our own picks, not the universe.
- Multiple comparisons: 3 horizons and 4 phase buckets tested; +2.4σ and +2.9σ survive Bonferroni
  only marginally (p≈0.05 and ≈0.015).
- One regime (recent crypto).
- **53.6% is a SIGNAL, not yet an EDGE**: the research's own benchmark is a 53% hit ratio →
  Sharpe 0.12, untradeable after costs. Net-of-fee viability is unproven.
