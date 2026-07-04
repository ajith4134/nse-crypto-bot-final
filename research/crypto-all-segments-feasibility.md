# Crypto all-segments (spot+futures+options+prediction) + few-trades — analysis & design (2026-07-02)

Analysis + design plan ONLY (no code changes this turn). Operator goal (2026-07-02):
> In the Freqtrade dashboard, beside the Start/Stop control panel, add **4 segment buttons**
> — **Futures · Spot · Options · Prediction**. Selecting them shows ALL those segments' open
> trades **with no symbol limit** — every symbol in futures/spot/options and ALL markets in
> prediction — all on ONE paper wallet, exactly like OpenAlgo does NSE all-segments-at-once.

---

## A. Why the brain opens FEW trades (root cause — CONFIRMED live)
Live now: **14 open / 50 cap**, dry-run, 300-pair whitelist. So it is NOT hitting the cap —
the brain is self-gating. It is a **cascading filter**, not one switch:

| Stage | Limit (file:line) | ~survivors |
|---|---|---|
| Whitelist | VolumePairList `number_assets=300` (config.json:33) | 300 |
| **Universe cap** | `brain_executor.py:161 _universe_cap()` → env `BRAIN_UNIVERSE` **default 150** | 150 |
| Min blended score | `percoin_decider.py:30 _MIN_FINAL_SCORE=0.5` (sharpe×brain_weight) | ~10–30 |
| Signal must fire NOW | `percoin_decider.py:154,180` `best.last==0 → FLAT` | ~5–15 |
| Min active bars | `percoin_decider.py:29 _MIN_ACTIVE_BARS=5` | — |
| Learner veto (rare) | `brain_executor.py:210,235 _entry_vetoed` bias≤−0.5 | ~4–14 |
| Freqtrade cap | `config.json:5 max_open_trades=50` | ≤50 |
| No re-entry if open | `brain_executor.py:215` | actual new opens 0–3/cycle |

Strategy itself has **no auto-entries** (`MlBridgeStrategy.populate_entry_trend → enter_long=0`);
ALL entries are brain `/forceenter` over REST. Loop every 60s (`BRAIN_LOOP_SEC`).

**Levers to open more (least→most noisy):** `BRAIN_UNIVERSE=300`; `_MIN_FINAL_SCORE 0.5→0.3`;
`max_open_trades 50→N`; `_MIN_ACTIVE_BARS 5→2`; learner veto off. Each trades selectivity for count.
The operator goal ("no limit") = make the universe cap + max_open_trades effectively unbounded
**per selected segment**, and give each segment its own open-trade budget.

---

## B. Can ONE Freqtrade instance do spot+futures+options+prediction? — NO (native)
- `freqtrade/enums/TradingMode` = **spot / margin / futures ONLY** — no options, no prediction.
- **One `trading_mode` per instance** (config.json:2 = `"futures"`), baked at startup — NOT
  switchable per-trade (`config.py:55`, `engine_client.py:97`). One process = one segment.
- The project already knows this: `trading/online/state.py:38` — crypto options stay on the ccxt
  path, OUTSIDE Freqtrade.
- **Binance "prediction market" reality (researched):** it is **Predict.fun** (an on-chain BNB-
  Smart-Chain dApp) surfaced inside Binance Wallet — buy/sell YES/NO shares $0.01–$0.99. There is
  **NO Binance REST/`eapi` trading endpoint** for it. Programmatic access = Predict.fun on-chain
  contracts or an aggregator/scrape path. So prediction can be **scanned & paper-simulated** now;
  real execution is an on-chain integration later. (Our env has only BINANCE_API_KEY/SECRET.)
- Binance **options** DO have a real REST API (`/eapi`, European options) → real dry-run possible
  via ccxt/Deribit, but NOT through Freqtrade.

**Conclusion:** Don't bend Freqtrade to 4 modes. Keep Freqtrade as the crypto **spot+futures**
execution venue (2 instances), put **options + prediction** on the ccxt/paper path — all unified
behind ONE segment-aware control plane + ONE paper wallet. Mirrors how our NSE side already runs
intraday+futures+options+commodities together (OpenAlgo model).

---

## C. Good news: most machinery ALREADY EXISTS (built for NSE)
- **Segment enum ready in 3 places** — just CRYPTO on the *dashboard* lags:
  - `trading/online/state.py:36 SEGMENTS["CRYPTO"] = ["options"]`  ← the one to widen
  - `trading/screener/screener.py:76 SEGMENTS["CRYPTO"] = ["spot","futures","options"]` (already!)
  - `trading/strategy/library/base.py:51` 8 segments incl. `crypto_spot/futures/options`
- **Segment toggle backend already wired:** `dashboard/server.py:2549 set_segments`, `:2551
  toggle_segment`; `MarketState.set_segments/toggle_segment/trades_segment` (state.py:77–94).
  Only SELECTED segments trade — exactly the "select buttons → trade those" behaviour requested.
- **One paper wallet, market-scoped (not segment-scoped):** `trading/online/wallet.py:124 PaperWallet`
  (crypto delegates to `paper_engine.py PaperEngine` — margin/leverage/liquidation), `:360
  PaperWalletBook` manages `(market, portfolio)`. All crypto positions (spot long, futures short,
  option leg, prediction YES) can coexist in ONE wallet/one margin pool. Only need a `segment` tag
  on Position/fill for per-segment reporting — no wallet redesign.
- **Per-segment screener/scan already the pattern:** `dashboard/server.py:937 live_markets(segment=…)`,
  `:2210 watchlist(m, segs, per_segment=…)` — "scan all markets" is a knob, not new code.
- **Strategy Foundry already segment-aware:** `foundry.py` seeds crypto_spot/futures/options ideas,
  `leaderboard(segment)`, `promote(segment)` — add crypto_prediction + wire per-segment brain loop.

So the 4-button + no-limit goal is mostly **wiring CRYPTO into the existing NSE-style pattern**,
not green-field. The real new build is options exec, prediction scan, and a 2nd Freqtrade (spot).

---

## D. Design — "mini-Binance" all-segments paper dashboard (one wallet)
```
   ┌───────────────────────  Dashboard control plane · ONE paper wallet  ──────────────────┐
   │ FreqtradeCryptoPanel:  [Start][Stop]   [Futures][Spot][Options][Prediction] ◄── 4 toggles │
   └──────────────┬───────────────────┬────────────────┬─────────────────┬──────────────────┘
                  │                   │                │                 │
           Freqtrade #1        Freqtrade #2       ccxt Deribit/     Predict.fun scan
           mode=futures        mode=spot          Binance /eapi     (BNB on-chain) →
           (dry-run)           (dry-run)          options (paper)   paper-sim now
                  └──── brain per-segment decider (PerCoin / Foundry, per-segment loop) ──────┘
                  all fills → ONE PaperEngine wallet · open trades merged in unified table
```
- **Per-segment budget** replaces the single 50 cap: each selected segment gets its own universe
  cap + max-open (default "unlimited" per operator ask); brain decides ALL symbols in each segment.
  Keep CPU sane with async batching, not a hard 150 cap.
- **Prediction segment** = read-only scan (Predict.fun/aggregators) + brain YES/NO → paper positions
  in PaperEngine; clearly flagged sim until on-chain exec exists.
- **Unified open-trades table** already merges loop+Freqtrade+OpenAlgo → add spot(FT#2), options
  (ccxt), prediction(paper) as extra sources into the same merge; one wallet/equity summary.

---

## E. Where each change lands (code map — for the BUILD phase, not done now)
| Change | File(s):line |
|---|---|
| Few-trades: per-segment universe/open budget (drop global 50) | `brain_executor.py:161`, `config.json:5`, `percoin_decider.py:30` |
| CRYPTO segments = spot+futures+options+prediction | `trading/online/state.py:40` (+ `_DEFAULT_SEGMENTS`); align `screener.py:76`, `library/base.py:51` |
| 4 buttons beside Start/Stop | `dashboard/web/src/trading/FreqtradeCryptoPanel.jsx` (reuse `toggle_segment` POST at server.py:2551) |
| 2nd Freqtrade (spot) instance | new `config.spot.json` (trading_mode=spot) + multi-instance `engine_client.py:36` |
| Crypto options exec (real greeks) | ccxt Deribit / Binance `/eapi` engine → PaperEngine; reuse Foundry `crypto_options` specs |
| Prediction scan + paper | new `trading/crypto/prediction/` (Predict.fun/aggregator scan) → PaperEngine sim |
| One wallet across segments | `paper_engine.py` (already single) + add `segment` tag on Position/fill (`wallet.py:200`) + unified merge (`dashboard/server.py`) |
| Per-segment brain routing | `brain_executor.py:129 run_once` (segment filter/loop), `percoin_decider.py:131`, `run_brain_loop.py:23` |

---

## F. Staged plan (paper-first, reuse-first)
1. **Few-trades quick win** — per-segment universe/open budgets; expose `BRAIN_UNIVERSE`+cap as
   dashboard knobs; default futures to "unlimited". (small, 1–2 files)
2. **CRYPTO segments + 4 buttons** — widen `SEGMENTS["CRYPTO"]`; render 4 buttons in
   FreqtradeCryptoPanel via the existing `toggle_segment` route. (small)
3. **Spot execution** — 2nd Freqtrade instance (mode=spot), fills → same PaperEngine. (med)
4. **Options execution** — ccxt Deribit/`/eapi` engine (real chain+greeks), paper-sim. (med, reuse
   Foundry `crypto_options_vol_eval`)
5. **Prediction** — Predict.fun/aggregator scan + brain YES/NO → PaperEngine; label sim-only;
   on-chain exec deferred. (med)
6. **Unified table + one wallet view** — merge all 4 sources into the existing unified table;
   single equity/wallet summary; per-segment tags. (med)

Reuse-first: Freqtrade (spot/futures), ccxt+Deribit (options), existing PaperEngine (wallet),
existing NSE segment-toggle machinery (buttons), Strategy Foundry (per-segment brain).

Sources: Freqtrade docs (one trading_mode per bot); Binance `/eapi` European options; Binance
prediction market = Predict.fun on-chain integration (no REST trade API).
