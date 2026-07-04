# Multi-venue crypto market-data pool (ban-proofing) — 2026-07-03

Trigger: Binance IP-banned the VM (418/-1003) from `fetch_l2_order_book` REST storms
(300-pair whitelist × order-book pricing + psychology polling). Binance's ban message
itself says: "use the websocket for live updates to avoid bans."

User decision (AskUserQuestion): FULL MULTI-VENUE POOL for market DATA (round-robin
Binance/Bybit/OKX/KuCoin public endpoints with per-venue rate budgets); NO API keys
(paper/public only). LIVE EXECUTION stays on Binance (or Bybit) for all segments —
the pool is data-plane only.

## Candidates (Phase-1 cheap signals)

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| ccxt (already installed) | github.com/ccxt/ccxt | 100+ exchanges unified REST; FREE merged ccxt.pro websockets (`watch_order_book`, `watch_order_book_for_symbols` ≥4.0.90); per-instance rate limiter | extremely active | 10/10 — already the project's crypto client everywhere, sync REST fits our 5s-tick loop | **WINNER for the pool engine** |
| cryptofeed | github.com/bmoscon/cryptofeed | 2.9k★, v2.4.1 (Feb 2025); 40+ exchanges incl. Binance/Bybit/OKX/KuCoin; normalized L2_BOOK websocket streams; REST fallback; backend sinks | active | 8/10 — best-in-class continuous L2 streaming, but asyncio feed-handler architecture ≠ our sync loop | **Stitch later as optional L2 streaming sidecar for DeepLOB/psychology recording** |
| BitcoinExchangeFH | github.com/BitcoinExchangeFH | order-book/trade recorder to DBs | stale | 3/10 | reject |

## Design (implemented in trading/crypto/exchange_pool.py)
- `ExchangePool`: ordered venues `[binance, bybit, okx, kucoin]` (public ccxt, no keys),
  one shared instance per venue (ccxt guidance: reuse instance = shared rate limiter).
- Per-venue token-bucket budget (default ~60 req/min each, far under every venue's
  public limit) — the pool REFUSES to exceed a venue's budget by construction: hard
  cap = ban-proof.
- Round-robin selection per call; skip venues that are out of budget, cooling down
  (429/418/-1003 → exponential cooldown), or missing the market; failover to next.
- Symbol normalization per venue via ccxt unified symbols (BTC/USDT:USDT works across
  binance/bybit/okx swap markets).
- Wired into `ExchangeClient.order_book()/ticker()` (which psychology + screeners +
  loop marks already use), so ALL crypto data reads spread across 4 venues.
- Freqtrade engine itself stays single-venue (its architecture) but its REST pressure
  was removed separately (ticker pricing, not order-book — config_template.py).

Sources:
- https://github.com/ccxt/ccxt/issues/19208 (free ws methods)
- https://docs.ccxt.com/docs/examples/py/binance-watch-orderbook-watch-balance
- https://github.com/bmoscon/cryptofeed
- https://norman-lm-fung.medium.com/fetching-orderbooks-via-ccxt-pro-websockets-library-300b21f02052
