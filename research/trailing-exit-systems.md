# Trailing-Exit Systems — OSS Research (4 distinct needs)

Research date: 2026-06-29. No code changed. Goal: find battle-tested OSS for FOUR
separate trailing-exit needs, ranked, with a mapping onto our stack
(NSE via OpenAlgo, crypto via ccxt). User explicitly wants distinct software per
direction/purpose where it is honest to do so — and an honest verdict where the
ecosystem really uses one engine for both.

## The 4 needs (restated)

| # | Side | Purpose | Behaviour |
|---|------|---------|-----------|
| 1 | LONG / BUY  | PROFIT trail (trailing take-profit) | Arms only after +X% open profit, then trails a stop UP under price to lock gains. |
| 2 | LONG / BUY  | STOP-LOSS trail | Stop follows price UP (chandelier / ATR / Supertrend), exit on drop. |
| 3 | SHORT / PUT | PROFIT trail (trailing take-profit) | Arms after price falls X% in our favour, then trails a stop DOWN above price. |
| 4 | SHORT / PUT | LOSS trail | Stop follows price DOWN, exit on rise. |

### Honest framing up front (READ THIS FIRST)

In every mature OSS trading engine, a "trailing take-profit" is **not a separate
algorithm from a trailing stop** — it is *a trailing stop that is armed only after a
profit threshold (offset) is reached*. And long-vs-short is handled by a single
sign/direction abstraction, never two codebases. So the ecosystem does **not** ship
four separate libraries; it ships **one ratcheting trailing engine + a profit-offset
gate + a side flag**. That is exactly how vectorbt, freqtrade, backtrader,
nautilus_trader and Lean all do it — and it is exactly how our in-house
`trading/execution/trailing.py` already does it (`_ratchet`, `_is_long`,
`ProfitLockTrailing.lock_after_frac`).

Therefore the *useful* split the user wants is **4 configured components over 1–2
shared engines**, not 4 unrelated repos. Where genuinely specialized projects exist
(Supertrend/Chandelier indicator libs vs. order-execution engines), they are called
out. The recommendation section gives both: the honest minimal set, and a
"4 visibly-separate components" layout if separation is a hard product requirement.

---

## 1. Library survey (GitHub + PyPI), with SHORT support verdict

| Library | What it gives you | pip | License | CPU-only | Backtested | Long | SHORT trail | Notes |
|---|---|---|---|---|---|---|---|---|
| **vectorbt** (polakowo) | `Portfolio.from_signals(sl_stop=, sl_trail=True, tp_stop=, tsl_stop=, tsl_th=, short_entries=, short_exits=)` — vectorized SL / trailing-SL / TP / trailing-TP exits | `pip install vectorbt` (PyPI 0.27.x) | Apache-2.0 (core; some extras GPL) | ✅ numpy/numba | ✅ this IS a backtester | ✅ | ✅ explicit `short_entries`/`short_exits`; short trail uses `max_high*(1-stop)` mirror | **Best for backtest/validation of all 4.** `tsl_th` = trailing threshold = the profit-offset that arms a trailing-TP. ~4k★ |
| **freqtrade** | `trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`, `trailing_only_offset_is_reached`, `custom_stoploss()` callback | `pip install freqtrade` (or repo) | GPL-3.0 | ✅ | ✅ + live | ✅ | ✅ via `can_short=True` (futures); custom_stoploss returns *risk* not price, so YOU sign it per direction + leverage | `offset` ⇒ trailing-TP; `custom_stoploss` ⇒ ATR/chandelier trail. ~30k★. GPL = keep as separate process, don't link into our code. |
| **backtrader** | `Order.StopTrail` / `StopTrailLimit` with `trailamount` or `trailpercent` | `pip install backtrader` | GPL-3.0 | ✅ | ✅ | ✅ `sell(...StopTrail)` | ✅ `buy(exectype=StopTrail)` trails DOWN — clean symmetric API | Cleanest textbook trailing-order API for both sides. Unmaintained-ish but stable. |
| **nautilus_trader** | `TrailingStopMarketOrder` / `TrailingStopLimitOrder`, `trailing_offset`, `activation_price`, OCO for SL+TP | `pip install nautilus_trader` | LGPL-3.0 | ✅ (Rust core) | ✅ + live | ✅ | ✅ "applies equally to short and long"; offset in bps/ticks | Production-grade, live ccxt-class venues (incl. Binance Futures perps). Heavy. |
| **jesse** | `update_position()`, exit lists, trailing via strategy callbacks; multi take-profit tuples | `pip install jesse` | MIT | ✅ | ✅ + live (crypto) | ✅ | ✅ `self.sell` short entry + symmetric SL/TP | Crypto-native (perps). MIT = friendliest license. Trailing is DIY in callback (no built-in primitive). |
| **QuantConnect / Lean** | `trailing_stop_order(sym, qty, trail, trailing_as_pct)` native order | Lean engine (Docker / `lean` CLI), not a pip indicator | Apache-2.0 | ✅ | ✅ + live | ✅ | ✅ short = negative qty, trail starts *above* price | Native broker-style trailing-stop order. Big infra footprint; reference impl. |
| **pandas-ta / pandas-ta-classic** | `supertrend()`, `chandelier exit (ce)`, `atr()`, `psar()` indicators | `pip install pandas-ta` (classic: `pandas-ta-classic`, 250+ indics, optional numba 6–230× speedup) | MIT | ✅ | indicator only | ✅ both dir cols | ✅ Supertrend & CE emit explicit long/short stop columns | **Indicator source, not an exit engine.** Feeds the stop level; you ratchet+execute. |
| **TA-Lib** | `ATR`, `SAR` (`SAREXT`) C library | `pip install TA-Lib` (needs C lib) | BSD | ✅ | indicator only | n/a | n/a (raw indicator) | Fast ATR/SAR primitive. No chandelier/supertrend built-in. C dep is the friction. |
| **NJiHin/TA_Chandelier** | PineScript→Python Chandelier Exit (long+short stop) | clone/vendor | (repo) | ✅ | indicator only | ✅ | ✅ explicit CE_S short stop | Tiny single-purpose chandelier repo if you want a vetted reference vs our impl. |

Notes verified: vectorbt PyPI Apache-2.0, `short_entries`/`short_exits` + `tsl_stop`/`tsl_th`
real params; freqtrade `can_short`/`trailing_stop_positive_offset` real; backtrader StopTrail
trails down on `buy`; nautilus `TrailingStopMarketOrder` + `activation_price` (Binance: must use
`activation_price`, NOT `trigger_price`); Lean `trailing_stop_order(..., -1, 0.05, True)` short.

---

## 2. Per-direction specialization — does it really exist?

- **Genuinely specialized projects exist only at the INDICATOR layer**, not the exit-engine
  layer: pandas-ta `supertrend`/`ce` and TA_Chandelier emit *separate long and short stop
  columns* (e.g. `SUPERTl`/`SUPERTs`, `CE_L`/`CE_S`). So "different software per direction"
  is real for *computing the stop level*.
- **At the execution/order layer, no engine ships separate long vs short libraries** — all use
  one ratchet + a side sign. Claiming otherwise would be dishonest. backtrader is the most
  symmetric (`sell StopTrail` vs `buy StopTrail`); nautilus/Lean take a signed qty.
- **Trailing-TP vs trailing-SL is a config, not a library**: it is the *same* trailing engine
  with a profit-offset gate (`tsl_th` in vectorbt, `trailing_stop_positive_offset` /
  `trailing_only_offset_is_reached` in freqtrade, our `ProfitLockTrailing.lock_after_frac`).

**Conclusion:** to honour the "4 separate" requirement, split by **configuration into 4
named components over a shared engine**, and optionally back each with a *direction-specific
indicator source*. Recommended 4-component split in §5.

---

## 3. Advanced / adaptive trailing

- **Volatility-scaled (ATR multiple):** pandas-ta `atr` + ratchet; our `ATRTrailingStop` already
  does `close ∓ mult·ATR`. backtrader `trailpercent`, nautilus `trailing_offset` (bps).
- **Supertrend:** pandas-ta `supertrend(length, multiplier)` — trend-flip trailing stop, long
  and short columns. Strong, widely-backtested; good as a *regime/flip* exit.
- **Chandelier Exit:** pandas-ta `ce` / NJiHin/TA_Chandelier — `extreme_since_entry ∓ mult·ATR`;
  matches our `ChandelierExit`.
- **Parabolic SAR:** TA-Lib `SAR`/`SAREXT`, pandas-ta `psar`; matches our `ParabolicSAR` (it flips).
- **Time-based / R-multiple trailing:** no dedicated mainstream lib; freqtrade `custom_stoploss`
  (gets trade duration + current profit) and jesse callbacks are the standard place to code
  "tighten after N bars" or "trail by R". Our `ProfitLockTrailing` is the R-multiple/breakeven gate.
- **ML / adaptive trailing-stop repos:** no production-grade, well-starred OSS exists — only
  small experimental Binance scripts (LUCIT trailing-stop-loss CLI, gabroliveros binance
  dynamic-amplitude trailing, Yskaa91 Bittrex). Treat these as references, **not** dependencies.
  The credible "adaptive" path is ATR-scaled + Supertrend regime, not an ML repo.

---

## 4. Mapping table — each need → library → wiring (long/short, OpenAlgo/ccxt)

| Need | Recommended lib(s) | Stop level source | Live wiring on OpenAlgo (NSE long/short/options) | Live wiring on ccxt (crypto long/short perps/options) |
|---|---|---|---|---|
| **1. LONG profit-trail (TTP)** | vectorbt `tsl_stop`+`tsl_th` (backtest) → our `ProfitLockTrailing(side="long", lock_after_frac=X)` (live) | peak-since-entry ratchet, armed after +X% | Tick loop (`tick_cache`/WS) updates stop; on breach place SELL MARKET via `openalgo_client` | ccxt: same tick loop; reduce-only SELL to close long; or native `TRAILING_STOP_MARKET` on Binance Futures |
| **2. LONG loss-trail** | pandas-ta `supertrend`/`ce` OR our `ATRTrailingStop`/`ChandelierExit(side="long")` | `high_since_entry − mult·ATR` | Same tick loop; breach ⇒ SELL MARKET. Optional: mirror as resting OpenAlgo stop where broker supports it | ccxt reduce-only SELL, or exchange-native trailing stop (nautilus `TrailingStopMarketOrder`) |
| **3. SHORT profit-trail (TTP)** | vectorbt `short_entries`+`tsl_stop`+`tsl_th` (backtest) → our `ProfitLockTrailing(side="short", lock_after_frac=X)` (live) | trough-since-entry ratchet, armed after −X% | Breach ⇒ BUY MARKET to cover short (futures/options leg) via `openalgo_client` | ccxt reduce-only BUY to close short perp; or Binance `TRAILING_STOP_MARKET` with `activation_price` above |
| **4. SHORT loss-trail** | pandas-ta `supertrend`/`ce` short col OR our `ATRTrailingStop`/`ChandelierExit(side="short")` | `low_since_entry + mult·ATR` | Breach ⇒ BUY MARKET to cover | ccxt reduce-only BUY; or nautilus `TrailingStopMarketOrder` (buy, trails down) |

Wiring constants:
- **OpenAlgo has no native exponential/ATR trailing order** → all 4 must run **client-side** in
  our WS tick loop (exactly what `trailing.py` header documents), emitting a plain MARKET/SL order
  on breach. This is already our architecture; OSS here is for the *stop-level math + validation*.
- **ccxt**: prefer **reduce-only** market close on breach for portability; only use
  exchange-native `TRAILING_STOP_MARKET` (Binance) when you want server-side resilience —
  nautilus_trader is the cleanest OSS that already speaks that order type. On Binance Futures use
  `activation_price`, never `trigger_price`.
- **Options (NSE puts / crypto options)**: trail on the **option premium** (or underlying, your
  choice) with the same engine; exit leg is BUY-to-close for short premium, SELL-to-close for long
  premium. Side flag = direction of the *option position*, not the underlying.

---

## 5. RECOMMENDED set

### Honest minimal set (what I actually recommend)
**Two engines, four configured components, one indicator library** — not four repos:

1. **vectorbt** (Apache-2.0, pip, CPU) — *offline validation* of all 4 needs. Use
   `from_signals` with `sl_stop`/`sl_trail` (needs 2&4), `tsl_stop`+`tsl_th` and
   `tp_stop` (needs 1&3), and `short_entries`/`short_exits` for the short side. This is how we
   prove our live trailing matches a battle-tested engine before risking capital.
2. **pandas-ta** (MIT, pip, CPU) — *stop-level source* for the adaptive variants: `supertrend`,
   `ce` (chandelier), `atr`, `psar`, each with explicit long & short columns. Lets us back our
   in-house `ATRTrailingStop`/`ChandelierExit`/`ParabolicSAR` with a vetted reference and gives a
   ready Supertrend regime-flip exit we don't have yet.
3. **Keep + extend our `trading/execution/trailing.py`** as the *live* engine — it already has the
   ratchet, `_is_long` side abstraction, ATR/Chandelier/SAR/Exponential, and `ProfitLockTrailing`
   (the profit-offset gate = trailing-TP). It is the correct client-side design for OpenAlgo.

Why not add a 4th heavy dep: freqtrade (GPL) / nautilus (LGPL) / Lean (Docker) are full engines,
not drop-in trailing libs; pulling them in to "have a separate lib per need" buys little over
vectorbt-for-backtest + pandas-ta-for-levels, and GPL would force process-isolation anyway.

### If "4 visibly separate components" is a hard requirement
Create 4 thin, separately-named wrapper components over the shared engine — honest, testable,
and what the ecosystem effectively does:

| Component (new) | Wraps | Config |
|---|---|---|
| `LongProfitTrail` | `ProfitLockTrailing` | `side="long"`, `lock_after_frac` armed, inner=`ExponentialTrailingStop` |
| `LongStopTrail` | `ChandelierExit`/`ATRTrailingStop` | `side="long"`, `mult`, ATR period |
| `ShortProfitTrail` | `ProfitLockTrailing` | `side="short"`, `lock_after_frac` armed |
| `ShortStopTrail` | `ChandelierExit`/`ATRTrailingStop` | `side="short"`, `mult` |

Each validated independently against the matching vectorbt configuration (long/short ×
sl_trail/tsl) and optionally fed by pandas-ta Supertrend/Chandelier columns.

### Optional heavyweight (only if we move to exchange-native server-side trailing on crypto)
**nautilus_trader** (LGPL, pip, CPU) for ccxt-class venues — it natively emits
`TrailingStopMarketOrder` with `activation_price`, surviving our process going down. Adopt only
when server-side resilience on Binance/Bybit perps becomes a requirement.

---

## Sources
- vectorbt: https://vectorbt.dev/getting-started/features/ · https://github.com/polakowo/vectorbt/issues/291 · https://deepwiki.com/polakowo/vectorbt/4.2-stop-based-exit-signals · https://pypi.org/project/vectorbt/
- freqtrade: https://www.freqtrade.io/en/stable/stoploss/ · https://www.freqtrade.io/en/stable/leverage/ · https://github.com/freqtrade/freqtrade/blob/develop/docs/stoploss.md
- backtrader: https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/ · https://www.backtrader.com/blog/posts/2017-03-22-stoptrail/stoptrail/ · https://community.backtrader.com/topic/2398/close-a-short-position-with-trailing-stop
- nautilus_trader: https://nautilustrader.io/docs/latest/concepts/orders/ · https://pypi.org/project/nautilus_trader/
- jesse: https://docs.jesse.trade/docs/strategies/entering-and-exiting.html · https://jesse.trade/help/faq/does-jesse-support-trailing-stop-loss-or-some-kind-of-break-even-functionality · https://github.com/jesse-ai/jesse
- Lean/QuantConnect: https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-types/trailing-stop-orders
- pandas-ta: https://github.com/xgboosted/pandas-ta-classic · https://github.com/NJiHin/TA_Chandelier
- trailing-stop topic/refs: https://github.com/topics/trailing-stoploss · https://capitalise.ai/trailing-take-profit-manage-your-risk-while-locking-the-profits/
