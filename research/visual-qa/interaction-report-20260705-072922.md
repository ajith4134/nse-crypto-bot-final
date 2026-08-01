# Dashboard interaction QA — 2026-07-05 07:29

## main_brain  (5 controls · ok 3 · dead 1 · error 0 · skipped 1)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| ⟳ Refresh | button | - | heavy job — not clicked | skipped |
| ⚡ Think | button | click | 1 request(s) | ok |
| Message the brain… (Enter to send · Shift+Enter for newline | textarea | type | value set (controlled input) | ok |
| 🧠 Brain | span | click | 1 request(s) · re-render | ok |
| 📈 Trading | span | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |

## main_trading  (145 controls · ok 133 · dead 3 · error 0 · skipped 9)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| 🧪 NSE Auto Trading (OpenAlgo) | button | click | 1 request(s) | ok |
| ↗ Open Crypto Window | button | click | 5 request(s) | ok |
| Search coin | input | type | 12 request(s) | ok |
| Futures — live (Freqtrade, Binance) | button | click | 6 request(s) | ok |
| Spot — paper (one engine, Binance) | button | click | 15 request(s) | ok |
| Options — paper (one engine, Deribit) | button | click | 13 request(s) | ok |
| Prediction — paper (one engine, Polymarket) | button | click | 2 request(s) | ok |
| Select all 4 segments | button | click | 12 request(s) | ok |
| 7 | input/number | type | value set (controlled input) | ok |
| Set | button | click | 14 request(s) | ok |
| 7 | input/number | type | value set (controlled input) | ok |
| Set | button | click | 15 request(s) | ok |
| 7 | input/number | type | 4 request(s) | ok |
| Set | button | click | 2 request(s) | ok |
| 7 | input/number | type | 8 request(s) | ok |
| Set | button | click | 1 request(s) | ok |
| → Futures | button | click | no request / no DOM change | dead |
| → LIVE 💵 | button | click | 18 request(s) | ok |
| ETH/USDT | button | click | 13 request(s) | ok |
| BTC/USDT | button | click | 1 request(s) | ok |
| LAB/USDT | button | click | 2 request(s) | ok |
| SOL/USDT | button | click | 7 request(s) | ok |
| XRP/USDT | button | click | 1 request(s) | ok |
| HYPE/USDT | button | click | 18 request(s) | ok |
| HMSTR/USDT | button | click | 11 request(s) | ok |
| ZEC/USDT | button | click | 10 request(s) | ok |
| ADA/USDT | button | click | 1 request(s) | ok |
| VANRY/USDT | button | click | 12 request(s) | ok |
| TLM/USDT | button | click | 10 request(s) | ok |
| DOGE/USDT | button | click | 1 request(s) | ok |
| BNB/USDT | button | click | 1 request(s) | ok |
| VELVET/USDT | button | click | 1 request(s) | ok |
| WLD/USDT | button | click | 24 request(s) | ok |
| 1000PEPE/USDT | button | click | 4 request(s) | ok |
| NEAR/USDT | button | click | 1 request(s) | ok |
| SLX/USDT | button | click | 5 request(s) | ok |
| SUI/USDT | button | click | 13 request(s) | ok |
| RPL/USDT | button | click | 1 request(s) | ok |
| MAGMA/USDT | button | click | 1 request(s) | ok |
| XLM/USDT | button | click | 20 request(s) | ok |
| SYN/USDT | button | click | 13 request(s) | ok |
| O/USDT | button | click | 1 request(s) | ok |
| XAU/USDT | button | click | 5 request(s) | ok |
| BCH/USDT | button | click | 2 request(s) | ok |
| XAG/USDT | button | click | 4 request(s) | ok |
| OGN/USDT | button | click | 12 request(s) | ok |
| EPIC/USDT | button | click | DOM -79 | ok |
| ENA/USDT | button | click | 14 request(s) | ok |
| RE/USDT | button | click | 3 request(s) | ok |
| LINK/USDT | button | click | 26 request(s) | ok |
| MU/USDT | button | click | 2 request(s) | ok |
| MIRA/USDT | button | click | 1 request(s) | ok |
| AVAX/USDT | button | click | 1 request(s) | ok |
| 币安人生/USDT | button | click | 32 request(s) | ok |
| TAO/USDT | button | click | 5 request(s) | ok |
| ARX/USDT | button | click | 5 request(s) | ok |
| XPL/USDT | button | click | 2 request(s) | ok |
| SPCX/USDT | button | click | 12 request(s) | ok |
| AAVE/USDT | button | click | 1 request(s) | ok |
| TRUMP/USDT | button | click | 15 request(s) | ok |
| SOXL/USDT | button | click | 11 request(s) | ok |
| ETHFI/USDT | button | click | 5 request(s) | ok |
| SKHYNIX/USDT | button | click | 2 request(s) | ok |
| TAC/USDT | button | click | 4 request(s) | ok |
| 1000BONK/USDT | button | click | 1 request(s) | ok |
| LTC/USDT | button | click | 28 request(s) | ok |
| MSTR/USDT | button | click | 2 request(s) | ok |
| SNDK/USDT | button | click | 1 request(s) | ok |
| ONDO/USDT | button | click | 9 request(s) | ok |
| HEI/USDT | button | click | 13 request(s) | ok |
| ALLO/USDT | button | click | 1 request(s) | ok |
| DOGS/USDT | button | click | 13 request(s) | ok |
| ARPA/USDT | button | click | 2 request(s) | ok |
| BIRB/USDT | button | click | 17 request(s) | ok |
| BAS/USDT | button | click | 1 request(s) | ok |
| HOT/USDT | button | click | 6 request(s) | ok |
| VVV/USDT | button | click | 1 request(s) | ok |
| GWEI/USDT | button | click | 12 request(s) | ok |
| HBAR/USDT | button | click | 24 request(s) | ok |
| CL/USDT | button | click | 2 request(s) | ok |
| PUMP/USDT | button | click | 2 request(s) | ok |
| SKYAI/USDT | button | click | 10 request(s) | ok |
| DOT/USDT | button | click | 2 request(s) | ok |
| LIT/USDT | button | click | 3 request(s) | ok |
| BEAT/USDT | button | click | 14 request(s) | ok |
| 1000SHIB/USDT | button | click | 13 request(s) | ok |
| GRAM/USDT | button | click | 1 request(s) | ok |
| UNI/USDT | button | click | 1 request(s) | ok |
| FIL/USDT | button | click | 10 request(s) | ok |
| M/USDT | button | click | 13 request(s) | ok |
| H/USDT | button | click | 1 request(s) | ok |
| FET/USDT | button | click | 17 request(s) | ok |
| TRX/USDT | button | click | 4 request(s) | ok |
| CAP/USDT | button | click | 12 request(s) | ok |
| XMR/USDT | button | click | 6 request(s) | ok |
| JTO/USDT | button | click | 1 request(s) | ok |
| PLAY/USDT | button | click | 2 request(s) | ok |
| PENGU/USDT | button | click | 31 request(s) | ok |
| Permanently delete ALL closed trades (journal + Freqtrade) s | button | - | destructive — not clicked | skipped |
| filter all cells… | input | type | value set (controlled input) | ok |
| on | input/checkbox | click | 1 request(s) | ok |
| Columns ▾ | button | click | DOM +274 | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-27-56.csv) | ok |
| ✖ Close All | button | - | destructive — not clicked | skipped |
| filter all cells… | input | type | 4 request(s) | ok |
| on | input/checkbox | click | DOM +110 | ok |
| Columns ▾ | button | click | 20 request(s) | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-28-00.csv) | ok |
| AARTIIND ABCAPITAL ABFRL ADANIENT ADANIGAS ADANIPORTS AJANTP | select | select | 11 request(s) | ok |
| 1200 | input/number | type | 2 request(s) | ok |
| ▶ Practice | button | - | heavy job — not clicked | skipped |
| OOS Leaderboard | button | click | 8 request(s) | ok |
| Data-Gated Families | button | click | 1 request(s) | ok |
| Coverage | button | click | 1 request(s) | ok |
| all | button | click | 12 request(s) | ok |
| crypto_futures 52 | button | click | 12 request(s) | ok |
| crypto_options 4 | button | click | DOM -35 | ok |
| crypto_spot 10 | button | click | 4 request(s) | ok |
| mcx_commodities 5 | button | click | DOM -69 | ok |
| nse_cash 5 | button | click | 16 request(s) | ok |
| nse_futures 46 | button | click | 1 request(s) | ok |
| nse_intraday 5 | button | click | DOM -13 | ok |
| nse_options 52 | button | click | 1 request(s) | ok |
| teach the brain a topic (e.g. stochastic calculus) | input | type | 19 request(s) | ok |
| Learn | button | - | heavy job — not clicked | skipped |
| add to the continuous-learning queue | button | - | heavy job — not clicked | skipped |
| continuous learning: the brain picks a topic every interval  | button | - | heavy job — not clicked | skipped |
| note name | input | type | 11 request(s) | ok |
| the fact / lesson to remember | textarea | type | 1 request(s) | ok |
| remember | button | click | 1 request(s) | ok |
| e.g. bitcoin funding leverage | input | type | 6 request(s) | ok |
| recall | button | click | no request / no DOM change | dead |
| Discover ▸ | button | - | heavy job — not clicked | skipped |
| symbol | input | type | 3 request(s) | ok |
| LONG SHORT | select | select | 16 request(s) | ok |
| Run debate | button | - | heavy job — not clicked | skipped |
| recall: symbol or free text (e.g. BTC short funding)… | input | type | 13 request(s) | ok |
| Recall | button | click | 1 request(s) | ok |
| 👁 Observe | button | click | no request / no DOM change | dead |
| 🔬 Deep See (DOM+OCR) | button | click | 21 request(s) · re-render | ok |
| ▷ Step (dry) | button | click | 34 request(s) | ok |
| 🏋 Practice ×2 | button | - | heavy job — not clicked | skipped |
| 🔬 Experiment | button | click | 7 request(s) · re-render | ok |
| 🧠 Brain | span | click | 15 request(s) · re-render | ok |
| 📈 Trading | span | click | 28 request(s) · re-render | ok |

## crypto_window  (9 controls · ok 7 · dead 0 · error 0 · skipped 2)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| 🛑 PANIC (halt all) | button | - | destructive — not clicked | skipped |
| ▶ Start trading | button | - | heavy job — not clicked | skipped |
| ⏹ Stop trading | button | click | 3 request(s) | ok |
| Switch to LIVE 💵 | button | click | 1 request(s) | ok |
| → Futures (short) | button | click | 4 request(s) | ok |
| filter all cells… | input | type | value set (controlled input) | ok |
| on | input/checkbox | click | DOM +110 | ok |
| Columns ▾ | button | click | DOM +274 | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-28-50.csv) | ok |

## frequi  (4 controls · ok 1 · dead 2 · error 0 · skipped 1)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| Toggle Night Mode | button/button | click | no request / no DOM change | dead |
| :BUTTON | button/button | click | no request / no DOM change | dead |
| Auto Refresh all bots now | button/button | - | heavy job — not clicked | skipped |
| Login | button/button | click | DOM +49 | ok |

## openalgo  (7 controls · ok 1 · dead 6 · error 0 · skipped 0)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| Home | button | click | no request / no DOM change | dead |
| FAQ | button | click | 6 request(s) | ok |
| Community | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| Roadmap | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| Docs | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| Download | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| Switch to dark mode | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
