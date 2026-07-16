# Browser UI capture vs the in-RAM lake — measured 2026-07-16 12:55

**Question (owner):** is the Binance-app coin data actually working correctly, or should we turn off
web-browsing Binance/Upstox for DATA and take everything from the in-RAM lake?

**Verdict: the capture mechanism is CORRECT and honest. Its COVERAGE for deep per-symbol fields is
catastrophic — and it is an architectural ceiling, not a bug.** A browser can only look at a few
pages at a time; you cannot stream 400 order books through one screen.

---

## 1. The capture works, and it is honest about staleness

`ui_market.py` has a per-kind TTL (`_FRESH_S`, env-overridable `UI_MARKET_FRESH_<KIND>`) and `_get()`
serves a row **only** within TTL — a stale read returns `None` honestly (module docstring line 16).

**So the brain is NOT poisoned with day-old data.** It goes **blind** instead: the field is simply
absent. That is the right failure mode, and it explains every null in `orderflow_store`.

## 2. But the deep fields are stale far beyond their TTL

Snapshot `trading/state/ui_market.json` (4,000 keys, ~1.2 MB, written continuously):

| kind | n | median age | TTL | usable? |
|---|---|---|---|---|
| ticker | 2,469 | **0.2 h** | 60 s | breadth OK (1,427 fresh) |
| mark_price | 869 | **0.0 h** | 90 s | OK (822 fresh) |
| orderbook | 184 | **25.5 h** | 45 s | **~6 fresh of 184** |
| open_interest | 182 | **26.0 h** | 1200 s | **7 fresh of 182** |
| taker_volume | 49 | **44.3 h** | 1200 s | **3 fresh of 49** |
| long_short | 49 | **44.3 h** | 1200 s | **3 fresh of 49** |

Oldest entries are 3.7 days. Brokers in the snapshot: binance 3,936 · upstox 52 · web 12.

**Deep per-symbol data exists for ~3–7 coins at a time, out of a ~2,469-coin universe.**

## 3. The natural experiment (same rows, same moment, same 70 coins)

`orderflow_store.json`, 165 rows written after the 12:37 funnel restart. Some fields come from the
**WS mirror** (`binance_stream.py`), others from **browser capture** — in the *same row*:

| field | source | non-null |
|---|---|---|
| `of_funding` | **WS mirror** | **165/165 (100%)** |
| `of_liq_skew` | **WS mirror** | 78/165 (47%) |
| `of_oi` | browser UI | **0/165 (0%)** |
| `of_smart_long` | browser UI | 0/165 (0%) |
| `of_taker_ratio` | browser UI | 1/165 (0.6%) |
| `of_crowd_long` | browser UI | 1/165 (0.6%) |
| `of_gofi` | browser UI (book) | 1/165 (0.6%) |

**100% vs 0.6% coverage, same rows.** This is not a tuning gap; it is two different physics.

**Consequence for the direction quest:** `book_ofi` (the research's #1/#2 ranked drivers) produced 35
rows across 26 coins in ~20 min — because only ~6 order books are ever fresh. **The Input Hunt cannot
be run on browser-sourced book data.** The inputs the equation needs are gated by the browser's ceiling.

## 4. What each source is actually good for

**In-RAM lake (`binance_stream.py`) — ONE `wss://fstream.binance.com` combined connection:**
- `!markPrice@arr` → mark + **funding** + next-funding for **every perp** (~1–3 s)
- `!ticker@arr` → 24h %change/high/low/quote-volume/trade-count for **every symbol**
- `!forceOrder@arr` → **every liquidation** as it happens
- Push not poll → ~0 idle CPU, whole universe in RAM, microsecond reads, no network at decision time.
- Already has: auto-reconnect + backoff, REST snapshot backfill, per-field staleness flags, kill
  switch `BINANCE_STREAM=0`, holds **no keys** (all public).
- **Not covered by all-market streams:** per-symbol book depth (needs `<symbol>@depth` — combined
  streams reach hundreds of symbols, vs the browser's ~6), and OI / taker / long-short (REST-only:
  `openInterestHist`, `takerlongshortRatio`, `globalLongShortAccountRatio` — cheap for a shortlist).

**Browser — genuinely unique, cannot be replaced by any feed:**
- Binance's **own screener/filter presets + rankings** (the broker-picker candidate source; the
  filter TOP-N lane) — captured `screener: 1`, `option_chain: 10`.
- Login/account/position state not exposed by public API; the ⭐ Favorites mirror.
- App-school route learning (the brain learning the app's own endpoints from live traffic).

## 5. Recommendation (owner decision — flags NOT changed)

**Hybrid, with the default flipped: DATA from the lake, browser only for what is UI-only.**

- **Move to the lake:** book depth (`@depth` combined streams), OI / taker / long-short (targeted
  REST for the shortlist), plus mark/funding/ticker/liquidations already there.
- **Keep the browser for:** screener/filter presets + rankings, login/account/Favorites, app-school.
- **Do NOT turn browsing off wholesale** — it would kill the filter TOP-N lane and account visibility
  for zero data gain.

**Conflicts the owner must settle (flagged, not overridden):**
1. **THE MOTTO** names **WEB DATA** as a tenet and is owner-approved *verbatim, never change meaning*.
   This recommendation keeps web data for what only the web gives, but narrows its role for
   selection data. That is a motto-adjacent call and is the owner's, not mine.
2. **NSE memories already conflict with each other:** `nse-ui-only-data` (NSE_UI_ONLY=1 → ALL NSE
   trade-selection data from the Upstox UI scrape) vs `kite-inram-mirror` (owner **2026-07-14**: NSE
   selection data from the PAID Zerodha KiteTicker → RAM, *overrides* the Upstox UI scrape). The
   newer decision supersedes — so narrowing Upstox browsing for DATA **matches the owner's own
   7/14 call** rather than contradicting it. Upstox is only 52 of 4,000 captured rows.
3. `ui-only-auto-flip-standing-order` — the brain flips `UI_ONLY_DATA` itself (governor). Any flag
   change must account for that governor, or it will flip back.
