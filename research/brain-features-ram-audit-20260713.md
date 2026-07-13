# Brain features — RAM data-source + demo-data audit (2026-07-13)

P3 audit (owner: "audit first, then sweep"). REPORT-ONLY map of every brain/strategy feature: its
current data source, any demo/fake/placeholder data, and the RAM-wiring it needs. Reviewed before
any rewiring. RAM sources = binance_stream.get_mirror() (mark/funding/ticker/candles/ohlcv/book/
movers/liquidations), ui_market, ui_data (captured candles), app_signals (8 filter kinds),
micro_collect (oi/depth/taker/longshort/aggTrades → ui_market), journal (real outcomes).

## Executive summary
- ~200 modules audited (brain 73, direction 13, strategy/evolution+library ~60, screener 8,
  journal 9, broker_sense data layer ~12, freqtrade decider 6, 84 lib_ + ~25 catalog strategies).
- **Already on RAM**: app_signals (ui_market+mirror — reference impl), truth_ledger price labeling
  (get_mirror.price_at), trade_features/symbol_move_net (journal), brain_executor/percoin PRIMARY
  bars (ui_data captures), + this session's fusion/fast_candles RAM-first candles.
- **Partially on RAM (ccxt fallback still live)**: brain_executor/percoin `_ohlcv`, direction/pullback
  + micro_features, screener crypto source, autoresearch.
- **Demo/fake — HIGH (feeds trades): 1** — `screener/stubs.py` hardcoded lists reachable in the
  crypto trade path via `screener.py:488`.
- **Demo/fake — LOW/MED: 5** — coingecko synthetic 1h OHLC in the funnel; library/run.py synthetic
  dashboard OHLCV; build_demo_* dashboard builders; decision_memory random init seed.
- **Excluded as legitimate (~20+)**: RNG for GP evolution / RL / bandits / sampling, and the
  replay/sim/paper-fill synthetic engines — correct by design, NOT fake market data.
- Most brain cognition modules take ARG/journal/state (no direct market fetch → no wiring needed).
- lib_/catalog Freqtrade strategies have no fake data (pure indicators on Freqtrade's own feed);
  MlBridgeStrategy "placeholder" = intentional no-entry shell driven by brain_executor.

## DEMO / FAKE DATA HOTLIST (real, non-test paths)
HIGH = feeds a trading decision; LOW = cosmetic/dashboard/offline.
1. **HIGH** `trading/screener/stubs.py:12-72` (`_STUB`) + `screener/screener.py:488-489` — hardcoded
   RELIANCE/TCS/BTC/ETH/`BTC-100K-EOY` returned as `stub_candidates(...)` when a crypto/NSE live
   source yields nothing. Can seed the tradable watchlist with fake symbols. NSE already hard-abstains
   (l.485); the CRYPTO path does NOT → fake symbols can reach a live paper trade.
2. **MED** `trading/broker_sense/coingecko_feed.py:52,130-133` — synthetic 1h OHLC (no intra-hour H/L)
   injected into ui_data via a `fake_url` capture key; consumed by the funnel (run_funnel_loop.py:433-438).
   Real closes but fabricated H/L → weak candles can reach the ensemble.
3. **LOW** `trading/strategy/library/run.py:23-133` — seeded np.random synthetic OHLCV (l.40); dashboard
   snapshot only, already supports a real-ohlcv arg (l.80).
4. **LOW** dashboard demo builders (offline snapshots, not trade path): `exits/__init__.py:272`,
   `sizing/position_sizer.py:452`, `screener/screener.py:520`, `options/live_chain.py:15`, `advintel/stress.py:355`.
5. **LOW** `trading/brain/decision_memory.py:102` random init memory-importance seed (not market data).
Excluded legitimate RNG: strategy/evolve.py:81, operators.py:54-105, genome.py:117-191,
champion_bandit.py:98, generators/*, brain/{worldmodel,hypothesis,selfimprove,rl_exit,continual,school,rnd},
online/replay.py, simlab.py, sandbox/paper_sandbox.py (paper-fill engines).

## RAM-WIRING BACKLOG (ranked, trade-drivers first)
1. **[HIGH] Screener crypto stub removal.** screener.py:488-489 + sources.py LiveCryptoSource: source
   crypto candidates from get_mirror().movers()/futures_rows()/ticker(); make an empty crypto result a
   HARD ABSTAIN (mirror the NSE ui-abstain at l.485) so stubs.py never reaches a live trade.
2. **[HIGH] brain_executor / percoin OHLCV.** brain_executor.py:91-99: after ui_data miss, read
   get_mirror().ohlcv(symbol,"5m") as the RAM decision-bar fallback BEFORE ccxt fetch_ohlcv; keep ccxt
   last-resort only. Removes the last live ccxt read in the entry path.
3. **[MED] coingecko synthetic candles.** coingecko_feed.py / run_funnel_loop.py:433: prefer
   get_mirror().candles() (real 1m/5m/15m) over synthesized 1h; keep coingecko only for mirror-absent
   symbols and flag synthesized H/L so the ensemble down-weights.
4. **[MED] direction/micro_features + pullback.** micro_features.py:58,105 + pullback.py:59: replace
   exchange_pool/data_failsafe ccxt reads with get_mirror().book/mark/funding + candles for mirror symbols.
5. **[MED] strategy-library backtest data_sources.** library/data_sources/{crypto_deriv,orderflow,
   multi_asset}: back crypto fetchers with get_mirror().ohlcv/book/funding (cache to disk); ccxt only
   for history depth the mirror lacks — so evolution/foundry/autoresearch train on the live RAM feed.
6. **[MED] autoresearch feed.** autoresearch.py:124: swap data_failsafe.ohlcv primary for
   get_mirror().ohlcv() so evolved strategies fit on RAM bars.
7. **[LOW] library/run.py dashboard snapshot.** Pass real mirror-candle ohlcv instead of seeded synthetic
   frames for the live dashboard; keep synthetic only for the truly-offline demo.
8. **[LOW] cosmetic demo builders.** Ensure live dashboard routes call the real builders first;
   build_demo_* stays only as offline fallback.

## Notes
- The codebase is heavily annotated with "never faked/honest" guards (binance_orderflow.py:15,
  fast_candles.py:10, ui_market.py:414, funnel.py:689, truth_ledger.py:437) — most grep hits for
  demo/fake are these honesty comments, not actual fakes.
- Per-feature detailed table (source/demo/wiring for each module) is in the audit transcript; the
  actionable subset is the hotlist + backlog above.
