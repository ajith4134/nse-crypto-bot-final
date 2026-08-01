# Dashboard interaction QA — 2026-07-05 07:24

## main_brain  (5 controls · ok 3 · dead 1 · error 0 · skipped 1)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| ⟳ Refresh | button | - | heavy job — not clicked | skipped |
| ⚡ Think | button | click | 1 request(s) | ok |
| Message the brain… (Enter to send · Shift+Enter for newline | textarea | type | 1 request(s) | ok |
| 🧠 Brain | span | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| 📈 Trading | span | click | 1 request(s) · re-render | ok |

## main_trading  (145 controls · ok 131 · dead 5 · error 0 · skipped 9)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| 🧪 NSE Auto Trading (OpenAlgo) | button | click | 11 request(s) | ok |
| ↗ Open Crypto Window | button | click | 4 request(s) | ok |
| Search coin | input | type | 1 request(s) | ok |
| Futures — live (Freqtrade, Binance) | button | click | 26 request(s) | ok |
| Spot — paper (one engine, Binance) | button | click | 2 request(s) | ok |
| Options — paper (one engine, Deribit) | button | click | 11 request(s) | ok |
| Prediction — paper (one engine, Polymarket) | button | click | 2 request(s) | ok |
| Select all 4 segments | button | click | 14 request(s) | ok |
| 10000 | input/number | type | 11 request(s) | ok |
| Set | button | click | 2 request(s) | ok |
| -1 | input/number | type | 4 request(s) | ok |
| Set | button | click | 1 request(s) | ok |
| 200 | input/number | type | 16 request(s) | ok |
| Set | button | click | 2 request(s) | ok |
| 5 | input/number | type | 1 request(s) | ok |
| Set | button | click | 2 request(s) | ok |
| → Futures | button | click | 17 request(s) | ok |
| → LIVE 💵 | button | click | 12 request(s) | ok |
| ETH/USDT | button | click | 3 request(s) | ok |
| BTC/USDT | button | click | 1 request(s) | ok |
| LAB/USDT | button | click | 6 request(s) | ok |
| SOL/USDT | button | click | 18 request(s) | ok |
| XRP/USDT | button | click | 2 request(s) | ok |
| HYPE/USDT | button | click | 20 request(s) | ok |
| HMSTR/USDT | button | click | 3 request(s) | ok |
| ZEC/USDT | button | click | 1 request(s) | ok |
| ADA/USDT | button | click | 11 request(s) | ok |
| VANRY/USDT | button | click | 9 request(s) | ok |
| TLM/USDT | button | click | 1 request(s) | ok |
| DOGE/USDT | button | click | 7 request(s) | ok |
| BNB/USDT | button | click | 20 request(s) | ok |
| VELVET/USDT | button | click | 4 request(s) | ok |
| WLD/USDT | button | click | 1 request(s) | ok |
| 1000PEPE/USDT | button | click | 5 request(s) | ok |
| NEAR/USDT | button | click | 1 request(s) | ok |
| SLX/USDT | button | click | DOM -79 | ok |
| SUI/USDT | button | click | 15 request(s) | ok |
| MAGMA/USDT | button | click | 20 request(s) | ok |
| RPL/USDT | button | click | 12 request(s) | ok |
| XLM/USDT | button | click | 2 request(s) | ok |
| SYN/USDT | button | click | 5 request(s) | ok |
| O/USDT | button | click | 1 request(s) | ok |
| XAU/USDT | button | click | 4 request(s) | ok |
| BCH/USDT | button | click | 14 request(s) | ok |
| XAG/USDT | button | click | 14 request(s) | ok |
| OGN/USDT | button | click | 1 request(s) | ok |
| EPIC/USDT | button | click | 1 request(s) | ok |
| ENA/USDT | button | click | 23 request(s) | ok |
| RE/USDT | button | click | 1 request(s) | ok |
| LINK/USDT | button | click | 2 request(s) | ok |
| MU/USDT | button | click | 25 request(s) | ok |
| MIRA/USDT | button | click | 9 request(s) | ok |
| AVAX/USDT | button | click | 1 request(s) | ok |
| 币安人生/USDT | button | click | 5 request(s) | ok |
| TAO/USDT | button | click | 1 request(s) | ok |
| ARX/USDT | button | click | 13 request(s) | ok |
| XPL/USDT | button | click | 17 request(s) | ok |
| SPCX/USDT | button | click | 1 request(s) | ok |
| AAVE/USDT | button | click | 13 request(s) | ok |
| TRUMP/USDT | button | click | 5 request(s) | ok |
| SOXL/USDT | button | click | 1 request(s) | ok |
| ETHFI/USDT | button | click | 4 request(s) | ok |
| TAC/USDT | button | click | 2 request(s) | ok |
| SKHYNIX/USDT | button | click | 28 request(s) | ok |
| 1000BONK/USDT | button | click | 2 request(s) | ok |
| LTC/USDT | button | click | 1 request(s) | ok |
| MSTR/USDT | button | click | 9 request(s) | ok |
| SNDK/USDT | button | click | 12 request(s) | ok |
| ONDO/USDT | button | click | 2 request(s) | ok |
| HEI/USDT | button | click | 14 request(s) | ok |
| ALLO/USDT | button | click | 1 request(s) | ok |
| ARPA/USDT | button | click | 18 request(s) | ok |
| DOGS/USDT | button | click | 5 request(s) | ok |
| BIRB/USDT | button | click | 1 request(s) | ok |
| BAS/USDT | button | click | 1 request(s) | ok |
| VVV/USDT | button | click | 13 request(s) | ok |
| GWEI/USDT | button | click | DOM -79 | ok |
| HBAR/USDT | button | click | 25 request(s) | ok |
| CL/USDT | button | click | 3 request(s) | ok |
| PUMP/USDT | button | click | 17 request(s) | ok |
| HOT/USDT | button | click | 4 request(s) | ok |
| SKYAI/USDT | button | click | 5 request(s) | ok |
| DOT/USDT | button | click | 17 request(s) | ok |
| LIT/USDT | button | click | 1 request(s) | ok |
| BEAT/USDT | button | click | 8 request(s) | ok |
| 1000SHIB/USDT | button | click | 1 request(s) | ok |
| GRAM/USDT | button | click | 12 request(s) | ok |
| UNI/USDT | button | click | 2 request(s) | ok |
| FIL/USDT | button | click | 16 request(s) | ok |
| M/USDT | button | click | 5 request(s) | ok |
| H/USDT | button | click | 12 request(s) | ok |
| FET/USDT | button | click | 6 request(s) | ok |
| TRX/USDT | button | click | 1 request(s) | ok |
| CAP/USDT | button | click | 2 request(s) | ok |
| XMR/USDT | button | click | 34 request(s) | ok |
| JTO/USDT | button | click | 1 request(s) | ok |
| PLAY/USDT | button | click | 1 request(s) | ok |
| PENGU/USDT | button | click | 5 request(s) | ok |
| Permanently delete ALL closed trades (journal + Freqtrade) s | button | - | destructive — not clicked | skipped |
| filter all cells… | input | type | 11 request(s) | ok |
| on | input/checkbox | click | 4 request(s) | ok |
| Columns ▾ | button | click | 1 request(s) | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-22-22.csv) | ok |
| ✖ Close All | button | - | destructive — not clicked | skipped |
| filter all cells… | input | type | 3 request(s) | ok |
| on | input/checkbox | click | 10 request(s) | ok |
| Columns ▾ | button | click | 8 request(s) | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-22-27.csv) | ok |
| AARTIIND ABCAPITAL ABFRL ADANIENT ADANIGAS ADANIPORTS AJANTP | select | select | no request / no DOM change | dead |
| 1200 | input/number | type | 6 request(s) | ok |
| ▶ Practice | button | - | heavy job — not clicked | skipped |
| OOS Leaderboard | button | click | 17 request(s) | ok |
| Data-Gated Families | button | click | DOM -327 | ok |
| Coverage | button | click | 3 request(s) | ok |
| all | button | click | 1 request(s) | ok |
| crypto_futures 52 | button | click | 16 request(s) | ok |
| crypto_options 4 | button | click | 1 request(s) | ok |
| crypto_spot 10 | button | click | DOM +42 | ok |
| mcx_commodities 5 | button | click | DOM -69 | ok |
| nse_cash 5 | button | click | no request / no DOM change | dead |
| nse_futures 46 | button | click | 32 request(s) | ok |
| nse_intraday 5 | button | click | 1 request(s) | ok |
| nse_options 52 | button | click | 2 request(s) | ok |
| teach the brain a topic (e.g. stochastic calculus) | input | type | 4 request(s) | ok |
| Learn | button | - | heavy job — not clicked | skipped |
| add to the continuous-learning queue | button | - | heavy job — not clicked | skipped |
| continuous learning: the brain picks a topic every interval  | button | - | heavy job — not clicked | skipped |
| note name | input | type | value set (controlled input) | ok |
| the fact / lesson to remember | textarea | type | 18 request(s) | ok |
| remember | button | click | 1 request(s) | ok |
| e.g. bitcoin funding leverage | input | type | 14 request(s) | ok |
| recall | button | click | 2 request(s) | ok |
| Discover ▸ | button | - | heavy job — not clicked | skipped |
| symbol | input | type | value set (controlled input) | ok |
| LONG SHORT | select | select | 11 request(s) | ok |
| Run debate | button | - | heavy job — not clicked | skipped |
| recall: symbol or free text (e.g. BTC short funding)… | input | type | 9 request(s) | ok |
| Recall | button | click | 1 request(s) | ok |
| 👁 Observe | button | click | 2 request(s) | ok |
| 🔬 Deep See (DOM+OCR) | button | click | 2 request(s) | ok |
| ▷ Step (dry) | button | click | 31 request(s) · re-render | ok |
| 🏋 Practice ×2 | button | - | heavy job — not clicked | skipped |
| 🔬 Experiment | button | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| 🧠 Brain | span | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |
| 📈 Trading | span | click | no effect; interaction raised (TimeoutError: Locator.click: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("[) | dead |

## crypto_window  (0 controls · ok 0 · dead 0 · error 0 · skipped 0)

| label | type | action | effect | verdict |
|---|---|---|---|---|

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
| FAQ | button | click | 7 request(s) | ok |
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
