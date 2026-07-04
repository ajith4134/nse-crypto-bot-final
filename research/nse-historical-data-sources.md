# NSE historical data sources (for brain practice mode) — 2026-07-04

Goal: free NSE historical candles (intraday + EOD) usable from this GCP VM, to
let the brain practice-trade NSE exactly like crypto.

| Source | Access | Data | Verdict |
|---|---|---|---|
| **openchart** (github.com/marketcalls/openchart) | pip, NO auth (NSE charting backend) | 1m→monthly, IDX/EQ/FO | **PRIMARY** — test from cloud IP (NSE main site blocks GCP; charting API to verify empirically) |
| **Zerodha via OpenAlgo `.history()`** | already integrated (dashboard `_candles` uses it); needs user's daily Zerodha login | broker-grade intraday+EOD | **SECONDARY** — real broker data, auth-gated by login session |
| Upstox historical-candle v3 API | Bearer token required (developer account) | 1m (last 6 months), from 2022 | fallback if user adds an Upstox app key |
| NSE bhavcopy (`download_nse_bhavcopy`, built) | free, cloud-IP/WAF-blocked (cookie jar defeat) | EOD full-market | tier-3 EOD bulk |
| GitHub dumps: ShabbirHasan1/NSE-Data (1m Nifty50+indices 2017-2020), debaonline4u/NSE-Data (1m…daily) | git clone | bulk static history | tier-3 bulk backfill for practice |
| jugaad-data / nsepy / nsetools | NSE website scrapers | various | avoid — same cloud-IP block class as nselib |

Recommendation: stitch tier-1 (openchart) + tier-2 (OpenAlgo/Zerodha) into
`data/downloads.py::download_nse_history()` with per-source honest errors;
bulk-backfill practice data via openchart (fallback GitHub dumps if blocked).

Sources: [Upstox docs](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) ·
[openchart](https://github.com/marketcalls/openchart) ·
[ShabbirHasan1/NSE-Data](https://github.com/ShabbirHasan1/NSE-Data) ·
[debaonline4u/NSE-Data](https://github.com/debaonline4u/NSE-Data) ·
[jugaad-data](https://github.com/jugaad-py/jugaad-data)
