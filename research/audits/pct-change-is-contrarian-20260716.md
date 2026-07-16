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
