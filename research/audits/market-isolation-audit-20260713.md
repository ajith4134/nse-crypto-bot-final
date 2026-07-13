# Multi-Market Isolation Audit — Indian (Upstox/OpenAlgo/Kite) vs Crypto (Freqtrade/Binance)

Date: 2026-07-13 · Scope: find every seam where the two markets leak into each other.
Method: runtime routing trace by hand (static import graph hides routing-logic leaks — see
independent-audit learnings). Confirmed symptom from owner: **an NSE options/OpenAlgo path is
trying to open a CRYPTO symbol on Kite**, and the **screen mirror only shows Binance, never Upstox.**

## Verdict
Isolation is **mostly correct by market-tag convention, but NOT structurally enforced.** Every
execution seam trusts an upstream `market` string; there is **no validator that a symbol's SHAPE
matches its market at the API door.** One wrong tag (or a wrong-market symbol slipping into a
per-market list) ships a crypto ticker to Zerodha. Plus one real brain-learning crossover.

---

## AXIS 1 — Execution routing  ⚠️ CONFIRMED STRUCTURAL HOLE

- **`trading/broker_sense/exec_adapter.py:52-53`** — `ExecAdapter.place()` routes with
  `if market == "crypto"` (lowercase, exact) → **else falls through to the NSE OpenAlgo door.**
  A crypto order tagged `market="CRYPTO"` (uppercase — the form used across the codebase:
  truth_ledger, brain_executor, live_loop all use `"CRYPTO"`) or `""`/`None` would route into
  Kite/OpenAlgo. No symbol-shape check. **This is the most likely source of the reported bug.**
- **`trading/online/live_loop.py:1391`** — `_open_trade` submits an NSE order when
  `not is_crypto` where `is_crypto = market.upper()=="CRYPTO"`. Correct *iff* the market tag is
  right, but there is **no guard that `symbol` is actually an NSE instrument.** A crypto symbol
  in `self.symbols["NSE"]` → `_submit_nse_order(symbol="BTC/USDT:USDT".split("/")[0]="BTC")` → Kite.
- Upstream universe (`live_loop._refresh_watchlist` → `Screener.watchlist`) IS market-scoped
  (screener dispatch `screener.py:375-402` and stub fallback `stubs.py` are keyed by market) — so
  the *normal* path is clean. The hole is the **absence of a last-line structural guard** at the
  two API doors for when a bad tag/symbol arrives from any source (manual action, account
  watchlist, a future caller).

**Fix:** add a `market_matches_symbol(market, symbol)` guard and enforce it in BOTH
`ExecAdapter.place()` and `live_loop._submit_nse_order` / `_route_crypto_engine`. Crypto symbols
carry `/`, `:`, or a `USDT`/`USDC`/`BTC` quote; NSE symbols do not. Reject + log on mismatch.
Also normalize the market compare to `.upper()` in `exec_adapter.place`.

## AXIS 2 — Shared state / config bleed  ✅ MOSTLY CLEAN

- Wallets isolated: `trading/online/wallet.py` → `paper_wallet_<MARKET>_<portfolio>.json`.
- Loop open-positions keyed `"MARKET:symbol"` (`live_loop._open`, `flush_market`). Clean.
- Registry is per-market; Freqtrade whitelist is crypto-only, OpenAlgo is NSE-only. Clean.
- (Verify) any GLOBAL singleton that both funnels share — the browser profile lock is per-broker
  (`live_browser.py:105` `browser_profiles/<broker>`), fine.

## AXIS 3 — Brain / decision crossover  ⚠️ REAL LEAK

- **`trading/direction/truth_ledger.py:249`** — `_bucket_key(source, regime, horizon)` has **NO
  market component.** So the same `source` name (e.g. `indicator_fusion`, `meanrev_stochrsi`,
  `funnel_mtf_vote`) that fires in BOTH crypto and NSE **pools its hit-rate into one bucket.**
- **`source_reliability()` (truth_ledger.py:510)** sums those buckets with an optional regime/
  horizon filter but **no market filter.** `learned_direction.decide()`/`correct_direction()`
  read this → **an NSE direction decision is weighted by crypto outcomes, and vice-versa.**
- `meta_labeler.py` DOES carry `market` as a category feature (`_CATS`, line 37) → the model can
  separate; acceptable. The leak is specifically the **per-source reliability buckets** the Hedge
  decider trusts.

**Fix:** add market to the bucket key (`source|market|regime|horizon`) and a `market=` filter to
`source_reliability()`; pass `market` through `learned_direction.decide/correct_direction`.
Migration: existing aggregate is rebuildable from the train JSONL / journal backfill.

## AXIS 4 — Dashboard / UI + screen mirror  ⚠️ BINANCE-ONLY BY CONSTRUCTION

- **"Mirror shows only Binance":** `run_funnel_loop.py:92` starts `get_mirror()` =
  `binance_stream.get_mirror()` — a **Binance-specific WS/RAM mirror.** There is **no Upstox/NSE
  equivalent** wired into the same mirror surface. `LiveBrowser` (`live_browser.py`) can host a
  per-broker browser (incl. upstox) but no NSE browser is streamed to the dashboard mirror.
- Unified open/closed trade table is intentionally cross-market (memory: unified-trading-ui) but
  should be clearly market-labeled/filterable so it doesn't read as "mixed."

**Fix:** either (a) start a per-broker LiveBrowser mirror for the active NSE broker alongside the
Binance stream and expose an Upstox tab, or (b) at minimum label the mirror as Binance-WS and add
the Upstox headed browser to the mirror route. Confirm the unified table tags each row's market.

---

## Ranked fix plan
1. **[Axis 1, highest] Structural market/symbol guard at the two API doors** — makes the confirmed
   crypto-into-Kite bug impossible regardless of upstream source. Small, high-leverage, tests.
2. **[Axis 3] Market-scope the truth-ledger buckets + source_reliability + learned_direction** —
   stops crypto/NSE learning pollution.
3. **[Axis 4] NSE/Upstox mirror parity** — add the Upstox browser to the mirror surface.
4. **[Axis 2] Add regression tests** asserting no wrong-market symbol can reach either door.
