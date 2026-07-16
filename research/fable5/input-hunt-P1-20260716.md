# P1 — THE INPUT HUNT, first session (2026-07-16, late night)

**Status: the hunt's #1 concrete lead is CLOSED — true L2-book OFI/GOFI (+ the book-STATE
metrics the deep research ranked above flow) are captured, persisted per-bar, verified
accumulating across the whole streamed universe, and verified consumed by the direction-equation
feature bus. First preliminary ICs measured (hours of data — labeled as such). Prompt 0's
remaining doc-correction half was also completed this session.**

## 1. Capture: verified live end-to-end (the "named, ranked, uncollected input" is collected)

- `trading/broker_sense/book_ofi.py` (built earlier today, verified tonight): true
  Cont–Kukanov–Stoikov L1 OFI + depth-normalized multi-level GOFI + book-state metrics
  (obi, microprice deviation, spread, multi-level depth imbalance `dobi`, L1 concentration
  `d1s`), one JSONL row per bar per symbol under `trading/state/orderflow/`.
- Measured tonight: **236 symbols, 98,236 stored bars, newest row 31s old** — fed by the WS
  in-RAM mirror's 20-level depth stream (motto-pure: the app's own data, zero extra API).
- Consumption chain verified (B2's "wired ≠ read" lesson applied):
  `book_ofi.series` → `orderflow_store.join_features` (merge_asof on bar timestamps) →
  `direction_equation.features_bus` — the equation's discover/evolve pool sees the new columns.
- **Added tonight:** `of_mid` (bar-close mid) rides in every row, so forward-return labels come
  straight from the series — future IC/CPCV studies need no candle join (the join proved the
  fragile part: ui_candles covers only ~45 favorites and goes hours-stale; static feathers
  filtered out exactly the depth-watched movers). 10/10 tests green; funnel reloaded, accruing.

## 2. First ICs (PRELIMINARY — ~10 hours of bars, read nothing as final)

Spearman IC of stored features vs forward mid returns, pooled across joined symbols:

| feature | IC@5m | IC@15m | IC@60m | n |
|---|---|---|---|---|
| of_ofi_n (true L1 OFI, depth-normalized) | +0.008 | −0.023 | +0.018 | ~2,900 |
| of_gofi_book (multi-level GOFI) | +0.012 | −0.024 | +0.020 | ~2,900 |
| of_obi | +0.026 | +0.016 | +0.027 | ~2,900 |
| of_microdev_bp | **+0.037 (p=0.048)** | +0.013 | +0.029 | ~2,900 |
| of_dobi (book-state headline) | +0.013 | −0.089 (p=0.15) | n too small | **310/264/93** |
| of_spread_bp | −0.002 | −0.005 | −0.024 | ~2,900 |

Honest readings:
1. **Flow (OFI/GOFI) is flat at 5m–60m — exactly what the deep research predicted** (flow's
   R² lives at 3–5 *seconds*; we hold 15m–4h). The point of collecting it anyway: conditioning
   (stressed-liquidity regimes, clock-phase) and seconds-scale execution timing, not naked alpha.
2. **microdev_bp is the only marginally significant 5m signal** (+0.037, p=0.048) — microprice
   pressure, consistent with the literature; worth watching as n grows.
3. **dobi (the research's headline book-STATE predictor) is starved, not falsified**: only
   top-N movers get 20-level depth streams, so it has n=310 vs flow's 2,900. Its −0.09 at 15m
   is direction-suggestive and underpowered. **The cheapest coverage win: widen the depth-watch
   list** (binance_stream `_depth_watch`) if socket budget allows.
4. An earlier pass over a different symbol set showed spread_bp IC −0.11@60m (p≈1e-7); it did
   not replicate on the favorites universe — likely a cross-sectional level artifact (illiquid
   coins drifted down today). Needs per-symbol demeaning before any claim. Filed, not believed.

## 3. Power math (when this becomes a real answer)

At the current accrual (~236 symbols × ~250 5m bars/day ≈ 45–60k feature-bars/day after joins),
detecting IC = 0.03 at p<0.01 needs ~15k obs (< 1 day); a *stable regime-conditioned* verdict
with purged CPCV across regimes needs **1–2 weeks**. For dobi specifically, at today's depth
coverage it accrues ~600–800 obs/day → ~1 week to power, or days if the depth-watch widens.
Re-run this study then — the script pattern is in the session transcript; labels come from
`of_mid` directly now.

## 4. Coverage audit vs REQUIREMENTS (item 2 of the prompt — what's still missing)

Per `COVERAGE-AUDIT.md` cross-checked tonight: GAP-A (rich bus) ✅, GAP-B (true GOFI) ✅ **closed
today**, GAP-D (SINDy) ✅. Still open: **GAP-C on-chain** (keys present, stubbed — no on-chain
series in any feature dict), **GAP-E indicator-screenshot lane**, and from the force list:
macro calendar and cross-venue basis remain proxy-only. Positioning (funding/OI/long-short/
liquidations/taker) exists via orderflow_store's 5m aggregates. These are the next capture
targets after the book-state series matures.

## 5. Prompt 0 closure (same session)

The three invalidated docs named by Prompt 0 all carry dated corrections: the 2026-07-11
diagnosis and ideas-ledger already had morning banners; SYNTHESIS-AND-PLAN.md received tonight's
evening addendum (Mirror Gate retired with the B1 negation proof; B4's backtest short-return
inversion voiding pre-fix trade-return validations; direction_equation's +3.6σ standing intact).
