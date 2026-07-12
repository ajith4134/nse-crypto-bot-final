# Whole-System Performance Audit — "use 100% of the hardware"
Date: 2026-07-12 · Box: AMD EPYC 7B12, **12 vCPU (6 physical cores)**, **41 GB RAM**, **no GPU**, **no swap**, disk 110 GB free.

## The reframe (measured, not assumed)
The machine is **NOT small or maxed out.** At audit time: **load average 3.3 / 12**, ~21 GB RAM free.
The problem is not *too little* hardware — it is that **the work is serialized onto one core at a time while 8+ cores sit idle.**

Two root diseases, many sites:

### Disease A — serial `for sym in universe:` loops under one GIL
Every evaluation cycle walks the universe **one symbol at a time in a single Python thread**, bounded by a
wall-clock `deadline` so it just `break`s when it runs out of time. With 420 spot / 626 futures symbols and
~0.5–1 s per symbol (OHLCV fetch + indicator fusion + ensemble + vision + ocular), the loop either takes
**300–400 s** or finishes only a fraction and defers the rest. Meanwhile 8+ cores idle.

Confirmed sites:
| Site | Loop | Cost |
|---|---|---|
| `trading/crypto/freqtrade/brain_executor.py:301` | `for i, sym in enumerate(syms)` — full whitelist scan | **the 300–400 s spot/futures scan** |
| `brain_executor.py:799` `_run_options_cycle` (`:802/:815/:861`) | serial option-chain build | futures/options slow |
| `brain_executor.py:893` `_run_prediction_cycle` (`:898`) | serial per-outcome | prediction slow |
| `trading/broker_sense/funnel.py:324` | `for s in candidates:` VERIFY (book+checklist+fusion+ocular+preview each) | funnel "only scans some" |
| `trading/online/live_loop.py:926/952/962/1020/1701/1748` | serial `for market, syms` sweeps | live loop lag |
| `trading/brain/learn_loop.py:101` | serial row learn | learning lag |

Partial parallelism already exists **inside sub-stages** (`fast_candles.py:114` ThreadPool-12,
`broker_features.py:318` ThreadPool, `indicator_fusion.py:346` ThreadPool over 6 timeframes) — but the
**outer per-symbol loop is serial**, so those pools spin up & tear down *per symbol* (pure overhead) instead
of one big pool over all symbol×timeframe jobs.

### Disease B — the dashboard is a compute hog in the trade path
`dashboard/server.py` (PID 1690) measured at **101% CPU + 9.9 GB RAM**. It runs the live P-trade loop
in-process (`server.py:1740` `if NO_LOOP != "1"`), a markets-writer thread, SWR prewarm, and outcome-net
builds — all in the same GIL as the web server. This both starves the web UI and holds ~10 GB.
(Matches memory note *dashboard-524-wedge-rootcause*: GIL starvation, run with `NO_LOOP=1`.)

## LIVE EVIDENCE (verified in person, real running data, 2026-07-12 ~08:40)
Not code-reading — measured from the loops running now on real Binance/Upstox data:
```
futures] 08:07:43  shortlist=144  non_neutral=55  entered=[]  took=422.76s
futures] 08:39:30  shortlist=144  non_neutral=51  entered=[]  took=538.37s   <- the 400s+ scan
options] universe=100  entered=[] exited=[] skipped=3         (serial scan of 100)
NSE funnel] cycle 5=97.7s  6=148.4s  9=135.0s  10=62.3s   (only 84-88 symbols tested)
```
Two proofs at once: (a) a futures cycle costs **422–538 s** serial; (b) after all that time it
**opens ZERO trades** (`entered=[]`) — hundreds of seconds burned, nothing to show — while load is 3.3/12.
That is the "takes 300–400s / dormant / waiting" symptom, reproduced live.

## MEASURED per-symbol profile (verified live, corrected — "check again" paid off)
Probed the real `decider.decide()` on live data. First read looked I/O-bound (ThreadPool 4.84×) but that was a
**cache artifact** — the repeat run reused symbols and hit both the 20s OHLCV cache AND the TabPFN brain-weight
TTL cache. With **distinct** symbols (no cache reuse):
```
serial          6.33 s/sym
ThreadPool(8)   4.56 s/sym  (1.39x)     <- threads barely help
ThreadPool(12)  4.65 s/sym  (1.36x)     <- plateaus at 8: GIL-bound
isolated network fetch  = 0.18 s/sym    <- only ~3% of decide()
disk feather read       = 0.005 s/sym   <- 36x faster than even a warm network call
```
**Conclusion: `decide()` is CPU/GIL-bound (~97% CPU: ~219 strategies × per-coin backtest + a TabPFN transformer
forward pass per symbol), NOT I/O-bound.** So the fix is NOT "more threads" (GIL caps it at ~1.4×). The real levers:
1. **Memoize per 5m bar** — candles change every 5m but cycles run every ~1–2 min, so 3–5 consecutive cycles
   recompute an identical decision. Cache `decide()` by `(symbol, last_candle_ts)` → repeat cycles ≈ free.
2. **Process-level parallelism** for the cold (new-bar) scan — real cores, not GIL-blocked threads.
3. **Local candle store** where fresh (futures 5m store = 519 symbols on disk; spot 5m store stale/sparse — 2
   files, needs the updater or the WS mirror to feed it) so the fetch is a 5 ms disk read, not a network call.

## THE ACTUAL ROOT CAUSE (found by verifying live — bigger than "serial loops")
The system is ALREADY designed for speed: the heavy 142-strategy tournament is meant to run
**off-cycle** (nice-10 `run_micro_distill` daemon) → populate a per-coin winner table + a LightGBM
student (`micro_policy.py`) → the live funnel does **ms table lookups** (`brain_executor.py:404-419`).
But the distiller has **NEVER once succeeded**: `micro_policy.json` = `{"coins": {}, ...}`, and the daemon
log shows every attempt failing identically —
```
Connection error - could not connect to 127.0.0.1:8080.
{'symbols': 0, 'coins': 0, ... 'took_s': 1.2}   (08:52, 17:15, 19:15, 06:46 … then sleeps 24h)
```
The distiller pulled its symbol list from a single `whitelist(futures)` call that returned [] when the
engine API was down at boot, wrote an empty table, and slept 24h. So the ms fast-path table is EMPTY →
`MicroPolicy.decide()` returns None for every symbol → **all ~600 symbols fall through to the 7.5s
teacher every cycle = the 422–538s scan.** The serial loop is real, but the *empty fast-path* is why it
never keeps up.

### W1 SHIPPED (2026-07-12)
1. **Per-5m-bar tournament memo** (`percoin_decider.tournament`) — repeat-in-bar cycles → ~0. Verified: 7.5s→0.000s. `SCAN_MEMO=0` off.
2. **Distiller repaired + parallelized** (`micro_policy.distill_once`, `run_micro_distill`):
   - robust engine-independent universe (`_resolve_universe` → futures/spot whitelist → config → **ccxt active USDT markets**; options filtered) — verified 454 real coins even with an options-only whitelist;
   - **process pool across cores** (`MICRO_DISTILL_WORKERS`, default ≤5, per-worker decider built once) — off-cycle, safe, uses the idle hardware;
   - **non-destructive save** (an empty distill never clobbers a good table);
   - **fast retry** (daemon retries in minutes on an empty distill, not 24h; skips dream/challenger until the fast-path exists).
   - Verified machinery: 6 real coins → coins=6, student trained (521 rows, agreement 1.0).
3. Dashboard `NO_LOOP=1` restart (frees the 9.9GB/101%-CPU in-process loop).
Effect: once the daemon populates the table (minutes), the live scan becomes ms table lookups → seconds, and the
heavy compute lives off-cycle on the idle cores — exactly "use 100% of the hardware."

## The broader "compute fabric" (remaining W2–W4, proposed)
1. **Parallel lanes (transistors switching in parallel).** Replace every serial `for sym in universe` with a
   **persistent process pool** (`ProcessPoolExecutor`, 10 of 12 cores) that fans the whole universe across all
   cores at once. Persistent = pay fork/import cost once, not per cycle. → the GIL stops being the ceiling.
2. **Shared in-RAM market bus (the power rail).** ONE process owns the **WS in-RAM mirror** of all Binance
   OHLCV/book (already the APPROVED plan: `research/video/binance-app-improve/plan.md`). Workers read the rail
   from shared memory instead of re-fetching OHLCV per symbol — kills the single biggest per-symbol cost.
3. **Pipelining (the instruction pipeline).** screen→look→verify→decide run as overlapping stages: while
   VERIFY chews batch N, LOOK already fetches N+1. No stage idles.
4. **Capacitors (memoize).** Cache indicator-fusion + OHLCV features keyed by `(symbol, tf, last_candle_ts)`;
   an unchanged symbol costs ~0 next cycle.
5. **Diode (one-way cull gate).** A fast **vectorized** numeric pre-score lets only forward-biased symbols
   through to the expensive lanes — expensive work flows only where it can pay off.
6. **ASIC (compiled hot path).** Vectorize the indicator math (EMA/Boll/ATR/Supertrend/ADX) with numpy/numba
   over the **whole universe at once** instead of per-symbol Python (hot-path skill; measured >2× gate).
7. **Core allocation.** Dashboard `NO_LOOP=1` (frees ~10 GB + a core); loops in their own niced processes;
   pin the compute pool, keep browser/UI responsive.

## Expected outcome
300–400 s universe scan → **single-digit seconds**; every core busy during a cycle; no dormant multi-minute
waits; dashboard light and responsive. No paid hardware — pure architecture (zero-cost-first).

## Rollout (quick wins first)
- **W1 (hours, low risk):** dashboard `NO_LOOP=1` split + persistent ProcessPool for `brain_executor.run_once`
  symbol scan + memoize indicator fusion. Biggest single win (the 300–400 s scan).
- **W2:** funnel VERIFY loop → same pool; one universe-wide thread pool for OHLCV instead of per-symbol pools.
- **W3:** WS in-RAM market bus as the shared data rail (offload fetch to Binance, reserve CPU for ML).
- **W4:** vectorized/numba indicator ASIC + pipelined stages + diode pre-cull.
