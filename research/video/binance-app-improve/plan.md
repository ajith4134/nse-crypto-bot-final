# Binance exploitation — full surface catalog + CPU-efficient architecture (2026-07-11)

Owner directive (from the video + answers): the 4 surfaces in the video are "a grain of sand" —
find EVERY exploitable Binance surface; and design for **fast / covers-more / low-CPU** by letting
**Binance's own scanners narrow the universe first, then hit the API only on the shortlist.**

Grounded in current state: brain already has a ccxt screener (vol/%change/funding + OI fetch,
`trading/screener/sources.py`+`screener.py`), order-book psychology (OBI/OFI/microprice/walls,
`trading/brain/psychology.py`), deribit options source, indicator_fusion, reflex R2 websocket lane.
132 deps / 737 modules. Standing rules: UI-only-data governor, CPU-solo, zero-cost-first.

## A. The efficiency architecture (answers the CPU concern) — 3 tiers

**The principle: Binance's servers do the universe-wide work; we only pay CPU for a bounded shortlist.**

```
TIER 0  UNIVERSE NARROWING  — Binance's compute, ~1 cheap call, near-zero CPU
  • ONE bulk call: GET /fapi/v1/ticker/24hr  → ALL ~400 perps in a single response.
    Locally derive movers / %change / quote-volume / amplitude(high-low) / trade-count.
    (This IS the Screener's raw columns — no per-symbol scanning.)
  • RARE, cached UI/curated reads (minutes–hours, not per tick):
    AI Select picks · Top Gainer/Top Volume/Hot · Token-Unlock calendar · new-listing
    announcements · sector categories.  ← Binance already ranked these for us (free).
  → OUTPUT: bounded SHORTLIST of N symbols (≈20–40) that pass coarse filters.

TIER 1  SHORTLIST DEEP-DIVE — targeted free API, ONLY the N shortlisted, cadenced+TTL-cached
  Per shortlisted symbol (≈5 tiny JSON calls, every 1–5 min, cached):
    topLongShortAccountRatio · topLongShortPositionRatio · globalLongShortAccountRatio
    · takerlongshortRatio · openInterestHist · funding+countdown · depth(→OBI/OFI, have)
  → bounded CPU/network; scales with N, not the universe.

TIER 2  STREAMING OVERLAY — websocket, event-driven, ZERO polling CPU
  • ONE all-market liquidation stream (!forceOrder@arr): pushes only when liqs happen.
  • bookTicker/aggTrade for the shortlist (reflex R2 already uses this).
  → CPU only on real events.

FUSION: everything lands in indicator_fusion → decision_snapshot as scored features, with
SWR/TTL caching (existing pattern) so repeat reads are free. Kill-switches per feed.
```
Net effect: **whole-universe coverage (Tier 0 sees all in 1 call) + deep signal only where it
matters (Tier 1/2 bounded)** → far less CPU than today's per-symbol scanning. This directly
implements the owner's "use Binance scanners to select, THEN API on the selected" idea.

Data-source split (owner's Q2 = "1 but also 2, you decide"): **free public API for the
quantitative feeds** (Tier 0 bulk, Tier 1 shortlist, Tier 2 stream — reliable, zero-cost), and
**UI-read only for the curated lists with no API** (AI Select, Token Unlock, Screener presets),
read rarely + cached. Best of both, honors UI-only-data governor for the UI parts.

## A2. ULTRA "no-lag" migration (owner 2026-07-11: option 2 everything-Binance, drawbacks engineered away)

Mandate: migrate ALL Binance-computable work off local CPU; local CPU is reserved for ML/brain only.
The drawbacks of naive option 2 (poll-per-decision) are lag + rate-limits + scrape-brittleness. Fix:

**WEBSOCKET-FIRST IN-RAM MIRROR** (confirmed feasible; `websocket`/`websockets`/`ccxt` already installed):
- ONE futures WS connection (`wss://fstream.binance.com`, ≤1024 streams) subscribes to the
  **all-market push streams** → keeps a live in-RAM snapshot of the WHOLE universe, updated BY Binance:
    `!markPrice@arr` (funding + mark, whole universe) · `!ticker@arr` (24h %chg/vol/amplitude, whole
    universe) · `!forceOrder@arr` (every liquidation).
- Per-SHORTLIST symbol WS: `@aggTrade` (taker buy/sell via maker flag) · `@depth` (OBI/OFI).
- REST only for the few non-streamed, slow-changing feeds (`/futures/data` long/short + taker ratio,
  `openInterestHist`) — polled per-shortlist every few min, cached.
- The brain reads from the **in-RAM mirror in microseconds** → NO network call at decision time, NO
  local recompute (Binance pushes computed values), ~0 idle CPU (push, not poll), no rate-limit polling.
- Robustness (kills the brittleness drawback): auto-reconnect + heartbeat, REST snapshot on (re)connect
  to backfill, per-field **staleness flag + last-update ts** (honest-wiring: a stale field is marked
  stale, never silently old), and a local fallback when a feed is cold.
- UI-only items with no API (AI Select, Token Unlock, Screener presets): slow background poller
  (minutes–hours) → state file cache; never on the decision hot path, so never a lag source.

Result: whole-universe coverage + deep shortlist signal, all pushed by Binance, **local CPU freed
entirely for ML/brain** (TabPFN, UQ, direction thesis, world-model) — making the brain smarter, not busier.

## B. Full exploitable-surface catalog (25, beyond the video's 4)

Legend: ✅ have · 🟡 partial · 🆕 new · [API]=free public REST · [WS]=websocket · [UI]=app-read

### Order-flow & positioning  (free /futures/data — highest signal-per-effort)
1. 🆕[API] **Taker buy/sell volume ratio** (`takerlongshortRatio`) — aggressor flow.
2. 🆕[API] **Global long/short account ratio** — retail crowd positioning.
3. 🆕[API] **Top-trader long/short ACCOUNT ratio** — smart-money accounts.
4. 🆕[API] **Top-trader long/short POSITION ratio** — smart-money size.
5. 🟡[API] **Open Interest + history** (`openInterestHist`) — OI↑+price↑=conviction, OI+funding=squeeze.
6. 🟡[API] **Funding rate + countdown + history** — crowding/carry (extend the 32 existing refs).
7. 🆕[API] **Basis / premium** (`premiumIndex`: mark−index) — contango/backwardation regime.
8. 🆕[WS] **Liquidation stream** (`!forceOrder@arr`) — forced flow, squeeze/capitulation, reflex trigger.
9. ✅ Order-book imbalance / walls / microprice (psychology.py).

### Market structure / universe  (mostly 1 bulk call)
10. 🟡[API] **Bulk ticker/24hr** — %change/volume/amplitude/trade-count = Screener columns in ONE call.
11. 🆕[UI] **Native Screener w/ indicator filters** (RSI/MA/StochRSI/KDJ/MACD/STOCH/Candle, multi-TF) — offload TA to Binance across the whole universe.
12. 🆕[UI] **Top Gainer / Top Volume / Hot** — curated movers as candidate source.
13. 🆕[UI] **AI Select** — Binance's own AI-ranked picks as a feature/candidate.
14. 🆕[UI/API] **Sector/category taxonomy** (AI, MEME, RWA, L1/L2, DePIN, Gaming) — sector rotation & correlation grouping.

### Catalyst / event  (UI or 3rd-party, low-freq, asymmetric)
15. 🆕[UI] **Token Unlock calendar** — supply cliffs → avoid/short/size-down. HIGH asymmetry.
16. 🆕[UI] **New-listing announcements** — listing pump; fast catalyst.
17. 🆕[UI] **Launchpool / Megadrop / HODLer** — farming + volatility events.
18. 🆕[UI] **Binance Square** — social/news/narrative sentiment (fits autonomous-web-brain).
19. 🆕[UI] **Delisting / leverage-tier / margin changes** — risk events.

### Derivatives-advanced  (eapi options, free)
20. 🆕[API] **Options mark IV / greeks** (eapi) — IV term-structure & skew → regime/risk.
21. 🆕[API] **Options OI / max-pain / put-call ratio** — positioning magnets.
22. 🆕[API] Options exercise history (low).

### Price/vol derived  (from klines, cheap)
23. ✅ Multi-TF klines (candle infra) → indicator_fusion.
24. 🟡 Realized vol / ATR / amplitude percentile — regime.
25. 🆕 **Beta/correlation to BTC** (Screener's Beta col) — market-neutral/hedge sizing.

## C. Ranked build phases (impact × confidence ÷ effort)

**Phase 1 — the efficiency backbone + order-flow (do first; establishes Tier 0/1/2):**
- Tier-0 universe narrower from ONE bulk ticker/24hr call (movers/amplitude/volume/txn) → shortlist.
- Order-flow & positioning pack (#1–5,7) as one `binance_orderflow.py` feeding indicator_fusion.
- Liquidation websocket (#8) — event-driven, feeds fusion + reflex.
- Funding extremes+countdown upgrade (#6).

**Phase 2 — catalysts (asymmetric edges):** Token Unlock (#15), new-listing/announcements (#16),
Launchpool/Megadrop (#17). UI-read + cached; gate entries around events.

**Phase 3 — curated selectors as candidate sources:** AI Select (#13), Top movers (#12), native
Screener presets (#11), sector rotation (#14, #25) into the funnel.

**Phase 4 — options & advanced:** Binance options IV/skew/max-pain (#20–21), Square sentiment (#18).

Every feed: TTL-cached, kill-switchable, bounded to the shortlist, honors CPU-solo & UI-only-data.

## D. Compute-MIGRATION map (owner mandate 2026-07-11: "move every feature to Binance if available")

Standing rule: for anything the brain computes on local CPU, if Binance already computes it, READ
Binance's result and DROP the local calc. Keep local ONLY what Binance can't provide (the edge).

| Local compute today | Binance equivalent | Action |
|---|---|---|
| **Universe-wide scan/rank** (screener.py over ~400 symbols) | Screener / AI Select / Top movers / bulk ticker/24hr | **MIGRATE** — biggest CPU win: stop scanning all locally; read Binance's ranked shortlist |
| RSI, MA/EMA, MACD, StochRSI, STOCH, KDJ (indicator_fusion, features_ta, feature_bus) | Binance **Screener** computes these multi-TF across the universe | **MIGRATE** (read on shortlist) |
| Candlestick patterns (patterns.py / talib) | Screener **Candle** filter | **MIGRATE** |
| Movers / volume / amplitude / txn ranking | Binance Hot / Top Gainer / Top Volume | **MIGRATE** |
| Funding / OI | Binance API | ✅ already offloaded (extend) |
| Long/short, taker, basis, liquidations | Binance API/WS | **ADD** (offloaded by definition) |
| Supertrend, Parabolic SAR, ADX/DMI, ATR, Bollinger bandwidth | *not exposed by Screener* | **KEEP local** (cheap; needed for regime gate + triple-barrier) |
| Order-book OBI/OFI/microprice/walls (psychology.py) | *not precomputed by Binance* | **KEEP local** |
| Brain ML: TabPFN, conformal UQ, direction thesis, meta-labeler, world-model, regime fusion | *none — this is the edge* | **KEEP local** (irreducible) |

Honest tradeoff to flag: classic TA (RSI/MACD) is cheap locally; the REAL CPU win is migrating the
**universe-wide scan** to Binance (compute on 400 symbols → read a shortlist). Migrating per-symbol
RSI/MACD too honors the mandate but adds network dependency + (for UI-only items) scrape brittleness
— so we cache aggressively and keep a local fallback when a Binance feed is cold.
