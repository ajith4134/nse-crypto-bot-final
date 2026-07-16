# The Input Hunt — session findings (2026-07-16, Fable-5 Prompt 1)

Ran after the measurement rebuild (`research/audits/measurement-rebuild-20260716.md`) so every
number here scores against honest labels.

## 1. "Inputs are the ceiling" — CONFIRMED by my own measurement

LightGBM (300 trees, chrono 70/30 split — no shuffling, no leakage) trained on the M1 stacking
features the ledger stores at decision time (5,500 rows: `f_confluence, f_p_up, f_orderflow,
f_sectors, f_ai, f_vp, f_yolo, f_direq, f_onchain, f_vision, m_momentum, m_funding,
m_liquidations, f_cortex_*`), predicting the realized up/down move:

> **OOS AUC = 0.497** — chance. Top importances (momentum, funding, liquidations, VP) are the
> model shuffling noise. This independently reproduces the documented 0.477–0.523 range.

**Verdict:** the diagnosis is right. No model change can help; every feature currently reaching a
decision is directionally information-free out-of-sample at these horizons.

## 2. Coverage vs REQUIREMENTS.md (delta from COVERAGE-AUDIT)

| Force | Status 2026-07-16 |
|---|---|
| Order flow (true L2 OFI/GOFI) | **CAPTURE BUILT THIS SESSION** (see §3) — was the #1/#2 ranked driver, never computed |
| Order flow (taker/positioning/OI/funding/liq) | live lens ✅; per-bar store was a DEAD PIPE — **fixed this session** (§4) |
| Liquidity/microstructure (OBI, microprice, spread, depth) | point-in-time psych features existed; **per-bar history now captured** (§3) |
| On-chain | live lens ✅; per-bar history still ⬜ (real API-integration task) |
| Macro / sentiment | partial (catalysts, AI-select); no per-bar history ⬜ |
| Positioning history, funding history | accumulates via the un-gated orderflow_store now |

## 3. Built: TRUE L2-book OFI/GOFI capture — `trading/broker_sense/book_ofi.py`

- **Source (motto-compliant):** the web app's own `@depthN` partial-book stream, already parsed by
  `ui_market._parse_orderbook`. New hook at the ingest store-point feeds every book snapshot to
  `book_ofi.on_book()`. Zero new API calls, zero new browser work.
- **Math:** per-level Cont–Kukanov–Stoikov OFI increments between consecutive snapshots (L1 `ofi`
  + depth-normalized `ofi_n`), multi-level exp-weighted depth-normalized **GOFI**, time-mean OBI,
  microprice deviation (bp), spread (bp), visible depth. Gap >120s resets the diff state (no
  fabricated increments); a 30s sweep closes bars for symbols whose stream went quiet.
- **Persistence:** one row per 60s bar per symbol, append-only JSONL under
  `trading/state/orderflow/<SYM>.jsonl` (atomic appends, size-rotated). `series(symbol, bar_s=300)`
  resamples to the equation's 5m bars.
- **Splice:** `orderflow_store.join_features()` now merges BOTH stores' columns
  (`of_taker_ratio…of_gofi` + `of_ofi, of_ofi_n, of_gofi_book, of_obi, of_microdev_bp,
  of_spread_bp, of_book_n`) onto any timestamped feature frame — and `direction_equation.
  features_bus()` already calls it, so the SR generators pick the new variables up with **no
  further wiring**. Bars before the store began carry NaN, never fakes.
- **Tests:** `tests/test_book_ofi.py` — 6 tests, hand-computed OFI/GOFI/OBI expectations,
  stale-gap reset, kill-switch (`BOOK_OFI=0`), 5m resampling, join splice, store feat-param.
  All green; the 4 neighboring suites (ui_market_motto, orderflow_store, binance_orderflow,
  indicator_fusion) green — 56/56.

## 4. Fixed: `orderflow_store.snapshot()` was a dead pipe

It was wired in `indicator_fusion.fuse()` behind `if not _cheap` — but the default
`CRYPTO_UNLIMITED_OPENS=1` makes `_cheap` always True, so **the store had never written a single
row** (`trading/state/orderflow_store.json` did not exist). Fixed: snapshot always runs, reusing
the already-fetched feature dict (no extra REST). Its "gofi" proxy stays but the true book GOFI
now exists alongside it.

## 5. Also fixed: pre-existing test pollution

`tests/test_binance_orderflow.py` failed standalone because `ui_market` hydrates REAL captured app
data from the live snapshot file into any test process — the suite predates the UI-first change.
Now isolates the capture store. (This was failing before this session's edits; verified via stash.)

## 6. What must happen next (the honest sequence)

1. **Restart the two funnel processes** (owner authorization required — this session was
   permission-blocked). The funnels host the browser stream pump, so book_ofi accumulation,
   the un-gated orderflow_store, AND `MIRROR_GATE=0` all activate on that restart.
2. **Let it accumulate.** Coverage = the symbols whose tabs stream depth (favorites/watchlist).
   1m bars → ~1.4k rows/symbol/day.
3. **After ~3–5 days**, re-run the equation search (`direction_equation.discover()` /
   `reevolve_all()` — Fable-5 Prompt 7) — the generators will now see true order-flow variables.
   Score with purged CPCV, Rank-IC by horizon, on truth-ledger labels (now unfrozen).
4. If OFI/GOFI also fail OOS at 15m–4h horizons, the honest next hypothesis is that the horizon is
   wrong (book OFI's documented predictive power is strongest at seconds-to-minutes) — the input
   set and the holding period must be chosen together.

## Negative result, stated plainly

Every input the system currently trades on is exhausted: 0.497 OOS AUC on 5,500 labeled decisions.
The named missing information is now being collected instead of proxied. Until it accumulates, no
amount of equation search over the existing bus can honestly beat coin-flip — three prior sessions
demonstrated that, and this session's measurement agrees.
