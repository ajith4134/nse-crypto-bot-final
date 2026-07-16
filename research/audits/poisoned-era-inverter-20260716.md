# ☣ POISONED ERA — the inverter that shorted everything (2026-07-16)

**Any analysis that reads trades in this window MUST exclude or era-control them. They were produced
by a KNOWN BUG, not by the brain's judgment. Treating them as evidence teaches the wrong lesson.**

## The window

| | |
|---|---|
| **Era opens** | **2026-07-16 ~17:40 UTC** — the futures segment was repaired (`CRYPTO_TRADING_MODE=spot→futures`), which UNMASKED a pre-existing inverter by allowing shorts at all |
| **Era closes** | **2026-07-16 ~18:09 UTC** — the inverter was killed (`learned_direction._signed_weight` no longer returns `invert=True` for unproven sources) |
| **Trades affected** | ~32 opened in-window; **15 force-closed 2026-07-16 ~18:30** on the owner's instruction |
| **Signature** | **31 SHORT vs 1 LONG**, **−112 P&L**, 25/32 red, coins that **ROSE +13% shorted** alongside coins that **FELL −13%** |
| **Markers** | `segment=futures`, `enter_tag` in {`learned_direction`, `filter:momentum`}, `is_short=True` |

## Why these rows are poison

`learned_direction._signed_weight` returned `weight 0.0` but **still `invert=True`** whenever a
source's Wilson CI straddled 0.5. Every live source sat in that band and all were underpowered
(river_online 0.4456, filter:momentum 0.4657, funnel_mtf_vote 0.4765, direction_model 0.4895; n≈260
→ ~12% power, ~540 needed for 80%). So **the brain flipped noise**, and in a long-leaning tape that
shorts everything. The direction on these rows is **the negation of a coin flip** — it carries no
information about what the brain believed, only about the defect.

It hid for months behind spot mode, which refuses shorts outright. Repairing futures is what exposed
it — the bug was always there; only its *expression* is new.

## How to exclude

- **Time window:** drop `entry_datetime` in `[2026-07-16T17:40Z, 2026-07-16T18:09Z]` for CRYPTO/futures.
- **Truth ledger:** any bucket whose labels fall in that window is contaminated for the `exit`
  horizon; the fixed-clock horizons (15m/1h/4h) resolve from price and are only contaminated in the
  SELECTION sense (which symbols/sides were sampled), not in the label itself.
- **Never** feed this window to TradeOutcomeNet, the direction model, the postmortem miner, or any
  win-rate/quality statistic without an era control.

## What is NOT poisoned

Trades after ~18:09 are honest: `learned_direction` now ABSTAINS when nothing is proven (correct per
CONVENTIONS §16) and the side falls through to the preset's own prior — momentum (`LONG if pct>=0
else SHORT`) or funding_extreme (`SHORT if funding>0`). Verified post-kill: **LONGs returned**
(TAC +11.7% → LONG, SKYAI +13.0% → LONG — SKYAI was SHORTED before the kill). The remaining
short skew is contrarian-by-construction (`funding_extreme` fades positive funding, and most coins
carry positive funding), plus momentum shorting a falling tape — **design, not defect**.

## Open question this era raises (CONVENTIONS §16b — do not leave at "it is what it is")

Momentum shorts coins that already fell 10-13%. Those entries went red — consistent with a **bounce
after exhaustion**, i.e. momentum-chasing at the wrong horizon. That is a REAL hypothesis worth
testing with the now-recorded `entry_vector`: is `pct_change` at entry a *contrarian* signal at our
holding period rather than a momentum one? Do not assume either sign — measure it.

See: `.claude/projects/-home-karan18190164/memory/direction-must-be-earned.md`,
`quality-gate-is-a-noop.md`, `direction-premises-falsified-20260716.md`.
