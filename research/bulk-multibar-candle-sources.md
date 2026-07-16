# Bulk multi-bar candle sources (web-navigable) — 2026-07-12

Question: since Binance's web exposes only ~1 bar/symbol in bulk, does any OTHER service expose
a MULTI-BAR price series for MANY symbols in ONE web-navigable request?

| Service | Bulk multi-bar? | Shape | Login-free | Verdict |
|---|---|---|---|---|
| **CoinGecko** `/coins/markets?sparkline=true` | ✅ **YES** | **168 hourly points × up to 250 coins/page** (~42k points/request) | yes (free) | **WINNER for breadth** — hourly resolution |
| **CoinMarketCap** listings (7d sparkline) | ✅ yes | 7d sparkline × many coins | yes | similar to CoinGecko |
| **TradingView** scanner (scanner.tradingview.com) | ⚠️ partial | thousands of symbols but CURRENT values / computed columns, not a per-symbol series | yes | breadth SCREEN (current), not a series |
| **Binance** get-product-dynamic | ⚠️ 1 bar | O/H/L/C/V per symbol × 1014 | yes | already captured (our bulk screen door) |
| **Bybit / OKX / KuCoin** web markets | ⚠️ 1 bar | bulk ticker; klines are per-symbol | yes | no bulk multi-bar |
| **Coinbase** Advanced Trade candles | ❌ per-symbol only | GET products/{id}/candles — one product/request | yes | no bulk |

## Findings
- The ONLY true bulk multi-bar web source is **CoinGecko / CoinMarketCap sparklines** — hundreds of
  coins' *hourly* series in one web request.
- Every exchange (Binance/Bybit/OKX/KuCoin/Coinbase) gives either bulk single-bar OR per-symbol
  klines — no bulk multi-bar. TradingView's scanner is bulk-CURRENT, not a series.

## Caveats / recommendation
1. **Resolution:** CoinGecko's bulk series is HOURLY (7d/168pts), not 5m/15m. So it's a broad
   HOURLY direction + regime screen for the whole market in one visit — NOT the fine 5m entry
   candles (those stay with the rolling parked tabs).
2. **Motto:** CoinGecko/CMC are third-party DATA aggregators, not the owner's Binance/Upstox
   ACCOUNT. Using them for candle breadth is a data-source diversification (execution stays on
   Binance). It's web-navigable + free but not "pure account web app" — a pragmatic extension.
3. **Best use:** wire a CoinGecko bulk-candle door → captures 250 coins' hourly series/visit →
   feeds a broad HOURLY direction + regime SCREEN (which symbols + trend), then the rolling
   parked tabs read the fine 5m/15m entry candles only for the top screened symbols. Two-tier:
   CoinGecko = hourly breadth, Binance parked tabs = 5m depth.
