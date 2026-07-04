# Ultra-Network Data Plan — what to download, from where, and how

Date: 2026-07-03. Serves MASTER-REQUIREMENTS T2 (Data & timeframes) + T1 (market-mechanics
premises: order-book blocks/gaps) + CANON-05/06 (multi-market multi-TF ingestion),
CANON-42 (truly-unseen live validation). All sources below are free, scriptable, CPU/disk-light.

## 0. What we ALREADY have (verified on disk)

- `trading/crypto/freqtrade/user_data/data/binance/futures/`: **416 pairs × 1m/5m/15m/1h/4h/1d
  feather files, ~125 days deep** (BTC 1m: 179,527 rows, 2026-03-01 → today, 4.6 MB).
  1m set alone = 1.28 GB. `candle_updater.py` refreshes incrementally
  (`CANDLE_UPDATE_DAYS=120`, `CANDLE_UPDATE_TFS="1m 5m 15m 1h 4h 1d"`).
- KRF's requirement (~51,773 rows ≈ 35 days of BTC 1m) is **already exceeded 3.5×** — the
  short-TF lane can start training TODAY with zero downloads.
- Disk headroom: 131 GB free of 197 GB. Everything below fits in < 15 GB.

## 1. Crypto 1m candles (KRF lane — REQ KRF-13/KRF-05)

### How far back each venue's API allows (via freqtrade/ccxt REST)
| Venue | 1m depth via API | Notes |
|---|---|---|
| binance | **spot: Aug 2017; USD-M futures: Jan 2020** (full history) | best source, 1500 candles/req |
| bybit | ~full history for perps (2020+) | 1000/req |
| okx | **only ~recent 100-candle pages; mark candles ~3 months** | do NOT use okx for deep history |
| kucoin | ~1500-candle pages, deep history slow | data-pool only |

→ **Backfill from binance only.** The multi-venue pool stays for LIVE reads; historical bulk
comes from Binance (archive is a public CDN, zero rate-budget impact).

### Method A (preferred): freqtrade download-data (recent freqtrade versions fast-path
klines through data.binance.vision automatically for binance)

```bash
# Majors: FULL history since futures listing (Jan 2020) — deep-history lane
cd /home/karan18190164 && .venv/bin/freqtrade download-data \
  --config trading/crypto/freqtrade/config.json \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT \
  --timeframes 1m --timerange 20200101- --trading-mode futures

# Whole 416-pair whitelist: extend to ~400 days (pattern-learning breadth lane)
CANDLE_UPDATE_DAYS=400 .venv/bin/python trading/crypto/freqtrade/candle_updater.py  # one cycle
# then permanently set CANDLE_UPDATE_DAYS=400 in .env so the daemon maintains it
```

### Method B (bulk, if REST paging is too slow): Binance Vision public dumps
- Index: https://data.binance.vision/ • repo: https://github.com/binance/binance-public-data
- Monthly zips of 1m kline CSVs, checksummed:
  `https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2020-01.zip`
  (verified: futures um 1m starts **2020-01**; spot BTCUSDT 1m starts **2017-08**).
- Convert CSV→feather into the freqtrade datadir with
  `freqtrade convert-data` after dropping into `user_data/data/binance/futures/`.
- Also available there (free, same CDN): `metrics/` (open interest, long-short ratio, since
  ~2021) and `bookDepth/` (see §3) — both are feature gold for the KRF order-book premise.

### Volume estimate
- 1m feather ≈ 13.5 MB/pair/year (measured: BTC 125d = 4.6 MB).
- 5 majors × 6.5 yr ≈ **450 MB**; 416 pairs × 400 d ≈ **6 GB** (vs 1.28 GB now). Fine.

## 2. Long daily history — NSE equities/indices + global indices (NNM/LSTM lanes)

### yfinance from a GCP VM: use as *backup only*
yfinance scrapes Yahoo endpoints; since 2025 Yahoo aggressively 429-blocks datacenter IPs
(GCP/AWS/Streamlit reports: yfinance issues #2422/#2411/#2480). One-off decade downloads of a
handful of tickers *usually* work with retries + latest yfinance (curl_cffi impersonation) +
long sleeps, but it must not be a scheduled dependency from this VM.

### Primary sources
1. **NSE bhavcopy archives** (official, free, one file per day covers ALL listed equities =
   every NIFTY constituent at once):
   - UDiFF format since Jul-2024; classic bhavcopy CSVs back to the 1990s at
     `nsearchives.nseindia.com`. Full-bhavcopy (with delivery %) removed for pre-2020 dates.
   - Scriptable via `jugaad-data` (`bhavcopy_save(date, dir)`) or the `nse`/`bhavcopy` PyPI
     packages (they set the required NSE cookies/headers). NSE blocks bare requests — always
     go through one of these libs. We already talk to NSE via OpenAlgo/Zerodha for live; this
     is history-only.
   - Plan: **2014-01-01 → today (~2,900 trading days), ~1–2 MB/day zipped → ≈ 3 GB**, stored
     as-is + a one-time consolidation into per-symbol parquet for the ~200 symbols we trade.
   - Index levels (NIFTY 50/BANKNIFTY, 10+ yr): niftyindices.com "historical data" CSV
     download (scriptable POST), backup `yfinance ^NSEI` one-shot.
2. **Stooq** (`https://stooq.com/q/d/l/?s=<sym>&i=d`) — free full-history daily OHLC CSV, no
   key; per-IP daily hit limit (~a few hundred) which is irrelevant for our handful of
   symbols. Covers `spy.us` (SPY 1993→), `^spx`, `gld.us`, `tlt.us`, `shy.us` (NNM-31
   portfolio set), `eurusd` (1971→). Does NOT carry ^RUI (Russell 1000) — substitute `^spx`,
   or pull ^RUI once via yfinance/manual CSV; LSTM-01 explicitly says the recipe applies to
   any liquid daily series.

```bash
mkdir -p /home/karan18190164/data/daily
for s in spy.us ^spx gld.us tlt.us shy.us eurusd; do
  curl -s "https://stooq.com/q/d/l/?s=$s&i=d" -o "data/daily/${s//[^a-z0-9]/_}.csv"; sleep 3
done   # ≈ 300 KB–1 MB each; total < 5 MB
```

## 3. Order-book snapshots (KRF blocks/gaps features — T1)

### Record L2 ourselves (yes — within budget)
- **Binance: WEBSOCKET depth streams only** (`watch_order_book` via ccxt.pro, bundled free in
  modern ccxt). WS market-data streams don't consume REST weight → sidesteps our documented
  Binance L2 REST ban. Bybit/okx/kucoin REST `fetch_order_book` calls fit the existing
  `exchange_client` per-venue budgets for spot-checks, but WS is preferred everywhere.
- Best practice: subscribe depth@100ms→maintain local book→**sample top-25 snapshot every
  5 s** per pair; append to daily zstd-parquet (`date, ts, symbol, bid_px[25], bid_qty[25],
  ask_px[25], ask_qty[25]`); rotate daily; derive OBI/OFI/microprice/walls offline (we
  already compute these live in the psychology signal — this adds the *historical* archive
  it never had).
- **Storage**: ~100 floats/row ≈ 200–300 B in parquet+zstd → 17,280 rows/day/pair ≈
  **4 MB/day/pair → 20 pairs ≈ 80 MB/day ≈ 2.4 GB/month**. Cap: record top-20-volume pairs +
  auto-prune > 90 days (~7 GB steady state). Store: `data/orderbook/{yyyy-mm-dd}/{pair}.parquet`.

### Free historical L2 (backfill before our recorder existed)
1. **Binance Vision `bookDepth`** (futures um, verified available **since 2023-01-01**,
   daily zips per symbol): per-minute depth-at-±%-levels — perfect for gap/wall features at
   1m resolution and it's the SAME CDN as klines (no auth, no budget).
   `https://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip`
   BTC+ETH 2023→now ≈ ~1–2 GB. Do majors only.
2. **Tardis.dev free slice** — documented: "Historical datasets for the first day of each
   month are available to download without API key" (docs.tardis.dev/downloadable-csv-files/api).
   Dataset types incl. `book_snapshot_25`, `book_snapshot_5`, `incremental_book_L2`, across
   binance-futures/bybit/okx. → script pulls the 1st of every month 2021→now for BTC/ETH:
   ~65 sample days of true tick-level L2, ideal for the KRF determinism study (KRF-27) and
   for validating our own recorder's feature math. A few GB; keep compressed.

## 4. Live-unseen validation feed (KRF-20 / CANON-42)

No new download needed — `candle_updater.py` IS the feed. Protocol (hold-out-by-time):
1. At training time write a manifest `data/holdout_manifest.json`:
   `{model_id, train_cutoff_utc, pairs, tf, embargo_minutes}`. Trainers MUST filter
   `df[df.date < train_cutoff]` (candle feathers are append-only, so cutoff filtering is exact).
2. Embargo ≥ 1 day (KRF: "pulled days ago, cannot be in training") to kill boundary leakage
   for windowed models: eval only on `date ≥ cutoff + embargo`.
3. A rolling-accuracy job (KRF-17) re-reads the same feathers daily, scores every model on
   candles newer than its manifest cutoff, and appends to `data/rolling_accuracy.jsonl` — the
   candle_updater's incremental append makes each day's new rows automatically "live-unseen".
4. Never retrain and evaluate in the same run against the same cutoff; a retrain issues a new
   manifest with a new cutoff.

## 5. Remaining T2 requirements

- **EURUSD daily 2003–2021, ASK candles (PNP-07)**: Stooq `eurusd` gives daily mid OHLC
  1971→ (1 CSV, ~400 KB) — good default. PNP specifically used ASK candles → exact
  replication via **dukascopy-node** (free, no key):
  `npx dukascopy-node -i eurusd -from 2003-05-01 -to 2021-12-31 -t d1 -p ask -f csv`
  (Dukascopy EURUSD history starts 2003; ~5k rows, < 1 MB).
- **EURUSD 1h 2020–2023 (TFM-08, Dukascopy-style)**: same tool, `-t h1` → ~25k rows, ~2 MB.
- **SPY daily 2000–2024 (NNM-13)** + GLD/TLT/SHY (NNM-31 rebalancer): Stooq (above).
- **^RUI daily 2012–2022 (LSTM-01)**: one-shot yfinance with retries, else ^SPX substitute.
- **Open interest / long-short-ratio (futures metrics)**: Binance Vision `metrics/` daily
  zips per symbol — cheap, feature-rich; majors 2021→ ≈ 200 MB. Optional but recommended.

## 6. Consolidated download plan (order of execution, sizes, destinations)

| # | What | Source / command | Est. size | Destination |
|---|---|---|---|---|
| 1 | 1m majors full history (BTC,ETH,SOL,BNB,XRP; 2020→) | `freqtrade download-data --timerange 20200101- --timeframes 1m` (auto Binance-Vision fastpath) | ~450 MB | `trading/crypto/freqtrade/user_data/data/binance/futures/` |
| 2 | whitelist 1m/5m/…: deepen 120→400 days | `CANDLE_UPDATE_DAYS=400` in .env + one candle_updater cycle | +5 GB | same |
| 3 | NSE bhavcopy 2014→today | `jugaad-data` bhavcopy_save loop (or `nse` pkg) | ~3 GB | `data/nse/bhavcopy/` + per-symbol parquet in `data/nse/eod/` |
| 4 | NIFTY/BANKNIFTY index levels 10y | niftyindices.com CSV (backup: yfinance ^NSEI once) | < 5 MB | `data/daily/` |
| 5 | SPY/^SPX/GLD/TLT/SHY/EURUSD daily full | Stooq `q/d/l` CSVs (curl loop above) | < 5 MB | `data/daily/` |
| 6 | EURUSD d1 ASK 2003-21 + h1 2020-23 | `npx dukascopy-node` | < 3 MB | `data/daily/` |
| 7 | L2 recorder (live, ongoing) | ccxt.pro `watch_order_book` sidecar, top-25 @ 5s, top-20 pairs, 90-day prune | ~2.4 GB/mo, 7 GB cap | `data/orderbook/` |
| 8 | Historical depth backfill (majors) | Binance Vision `bookDepth/` daily zips 2023→ | ~1–2 GB | `data/orderbook/binance_bookdepth/` |
| 9 | Tick-L2 samples for determinism study | Tardis free 1st-of-month `book_snapshot_25` (no key) | ~2–3 GB | `data/orderbook/tardis_samples/` |
| 10 | Futures metrics (OI, long-short) majors | Binance Vision `metrics/` | ~200 MB | `data/metrics/` |
| — | Hold-out manifest + rolling accuracy | §4 protocol (code, not download) | — | `data/holdout_manifest.json` |

**Total new disk: ~12–14 GB** (131 GB free). Nothing touches live-venue rate budgets except
the WS recorder (weight-free) — all bulk history rides Binance Vision CDN, NSE archives,
Stooq, Dukascopy, and Tardis's free slice.

## Sources
- https://github.com/binance/binance-public-data • https://data.binance.vision/ (S3 listing verified: futures-um 1m from 2020-01, spot 1m from 2017-08, bookDepth from 2023-01-01, metrics/bookTicker/trades/aggTrades present)
- https://www.freqtrade.io/en/stable/data-download/ • https://www.freqtrade.io/en/stable/exchanges/ (OKX 100-candle pages, ~3-month mark candles)
- yfinance cloud-IP 429s: https://github.com/ranaroussi/yfinance/issues/2422 · /2411 · /2480
- https://stooq.com/db/h/ • https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data/
- https://docs.tardis.dev/downloadable-csv-files/api ("first day of each month … without API key") • https://docs.tardis.dev/historical-data-details/bybit
- https://github.com/Leo4815162342/dukascopy-node (EURUSD tick→d1 from 2003, free CLI)
- NSE: https://pypi.org/project/bhavcopy/ • jugaad-data bhavcopy_save • https://pypi.org/project/nse/
