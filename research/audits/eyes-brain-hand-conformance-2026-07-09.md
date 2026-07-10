# Eyes→Brain→Hand conformance audit — 2026-07-09

Owner's design (restated): the brain logs into the broker's OWN web app (Binance for crypto,
Upstox for NSE), selects candidates with the app's own built-in functions, mirrors its open
trades into the account watchlist (⭐ Favorites / "Brain-Open") — add on open, remove on close —
opens the symbol's own trade page, picks entry/direction, executes via API ONLY (paper and
live), trades every segment enabled on the dashboard, and navigates with eyes→brain→hand.

## Verdict per design element (all verified against running code/state this session)

| Design element | Status | Evidence |
|---|---|---|
| Candidates from the broker app's own functions | ✅ CONFORMS | every open trade's `decision_snapshot.app_signals.screener.lane` = `binance` (gainers/losers pages) or `broker_feature` (app preset pickers); direction = the app's own change% sign; 28/28 verified |
| UI-only data, API-only execution | ✅ CONFORMS | entries flow ONLY through `engine_client.place_order` (REST /forceenter); `human_ui` has an order-guard that BLOCKS any click matching order/buy/sell controls (guard verified in code + trail) |
| ⭐ Favorites mirror add-on-open / remove-on-close | 🟡 FIXED THIS SESSION | mirror ran in-funnel and DID add (login_ok=true) but removals starved forever (adds always ran first and ate the whole per-pass budget) and throughput (~2-3 star-toggles/cycle vs ~15 opens/cycle in explore mode) can't fully catch up. Fair interleave shipped (binance_watchlist.py + account_watchlist.py); backlog now drains both ways. Remaining honest gap: full catch-up during explore churn needs a batch star page (follow-up) |
| Trades ALL dashboard-enabled segments | 🟡 FIXED THIS SESSION | futures ✅; spot worker was DEAD at every boot (can_short ImportError — the base strategy was never overridden for spot; all "spot" API calls silently fell back to the futures bot) → fixed via `strategy: MlBridgeStrategySpot` override in config_template; options was enabled but had NO driver since the funnel replaced run_brain_loop → funnel now drives options/prediction cycles each loop |
| One Freqtrade framework for all segments | 🟡 PARTLY — now real | MultiWorker boots futures+spot+options (verified post-restart: per-segment counts distinct); phantom "entered" fixed (order result now checked); broker-app picks on delisted books (ADA/RUB, BSW/TRY) reroute to the coin's USDT book (verified live: cycle entered ADA/USDT:USDT, ALGO/USDT:USDT) |
| Eyes→brain→hand navigation | ✅ CONFORMS | sessions.page → free-eyes (DOM+OCR) → HumanUI locate/click/type with human glide + order guard; NEW: every action now feeds the owner-visible Brain Screen Mirror |
| Owner can WATCH the brain operate | ✅ NEW THIS SESSION | Brain Screen Mirror: throttled JPEG frames + action feed from inside the funnel processes → `/api/trading/mirror` → BrainMirrorPanel (Trading view). Verified: real frames of Binance futures pages the brain opened |
| Same pattern for NSE/Upstox | ✅ CONFORMS (hours-gated) | NSE funnel process runs the same pipeline against Upstox (QR login, market-hours gated); Upstox "Brain-Open" watchlist mirror shares the same (now-fixed) sync code |
| Learning from closed trades | 🟡 FIXED THIS SESSION | crypto ingest was gated on the registry's CRYPTO *trading* flag (off by design — funnel owns crypto) → journal starved since Jul 7. Gate removed (ingest is read-only learning); bulk backfill runs LLM-free and batched; dashboard poll path no longer runs LLM reflections in request threads |

## Answers to the owner's direct questions
- "Why don't I see symbols added/removed from my Binance Favorites?" — They WERE being
  added (slowly): ~2-3 per cycle vs ~15 opens per cycle in explore mode, and removals NEVER ran
  (queue starvation bug). Both fixed; expect adds AND removals every cycle now, converging over
  ~30–60 min of funnel cycles. Binance separates spot vs futures watchlists — the brain stars the
  FUTURES symbols (its trades are USDT-M perps), so look at the futures/overall Favorites tab.
- Paper AND live both execute via API after UI selection — confirmed; live additionally requires
  the explicit allow-live gate (never flipped implicitly).
