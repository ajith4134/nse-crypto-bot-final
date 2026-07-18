# Market making / fill toxicity — MEASURED verdict
2026-07-18. Follow-on to `research/direction-brain-mission/HFT-feasibility.md`.

Prior session ended: *"this is the first strategy family where the gross economics work
— worth a cheap test. Measure fill toxicity before committing to a quoting engine."*
This is that test. **Answer: no. Do not build the quoting engine.**

Everything below is measured on this VM on 2026-07-18, not argued from theory.

---

## Method — no quoting engine needed
Every Binance trade carries `m` = "was the BUYER the maker", which identifies the passive
side of every trade. That is the exact population our quotes would live in, so fill
toxicity is measurable off the public wire without placing a single order.

Collected 12 minutes of `@trade` + `@bookTicker` on 7 symbols: **31,823 trades /
206,489 book updates** (`markout-raw-1784401334.jsonl`, 32 MB, kept for re-analysis).

Markout decomposition, in bps: `net = half_spread + drift(h) - 2bps maker fee`
where `drift = side * (mid(t+h) - mid(t)) / mid(t)` is the adverse selection.

**TRAP — `@aggTrade` is dead on the futures host from this VM.** Measured 0 messages in
12s on BTCUSDT while REST reported ~770 trades/min. `@trade` works and is strictly better
(per-trade, not aggregated, same `m` flag). Spot's `stream.binance.com` serves @aggTrade
fine; `fstream.binance.com` does not. This would have silently produced an empty study.

---

## Result 1 — the universe scan (714 symbols, live)
Spread must beat the **0.04% round-trip maker fee** (VIP0 maker 0.02% x2 legs).

| symbol | spread | verdict |
|---|---|---|
| BTCUSDT | 0.0002% | far below fee |
| SOLUSDT | 0.0133% | below fee |
| ENAUSDT | 0.0124% | below fee |
| **median of all 714** | **0.0436%** | ~zero net edge |
| widest (INTW/APP/GWEI/SNOW) | 0.22–0.37% | tokenized-equity + microcap perps, 0.5–14 trades/min |

393 of 713 symbols clear the fee. Upper-bound revenue assuming **5% flow capture and
ZERO adverse selection**: **$16,430/day across the entire universe**, best single symbol
$2,258/day. That ceiling — before any toxicity — was the first warning.

The wide spreads sit exactly where nothing trades. That is not bad luck, it is the market
being efficient: spread is wide precisely where quoting is dangerous.

## Result 2 — markout (the toxicity test itself)

| symbol | fills | half-spread | drift +10s | net +10s | net +30s |
|---|---|---|---|---|---|
| BTCUSDT | 7911 | 0.088 | -0.441 | **-2.35** | -2.02 |
| SOLUSDT | 3636 | 0.702 | -0.498 | **-1.80** | -1.30 |
| SYNUSDT | 11020 | 4.136 | -2.181 | **-0.04** | -2.23 |
| HOMEUSDT | 3689 | 7.699 | -4.202 | **+1.50** | +1.07 |
| BULLAUSDT | 2483 | 13.431 | -7.763 | **+3.68** | +3.76 |
| FWDIUSDT | 2221 | 16.143 | -9.573 | **+4.61** | **-8.27** |
| GWEIUSDT | 833 | 17.701 | -3.064 | **+12.64** | +11.59 |

- **Controls pass.** BTC/SOL land at -2.35/-1.80 bps, which the spread-vs-fee arithmetic
  demands. The measurement is sound.
- **Adverse selection is universal.** Drift is negative on every symbol. On FWDI it eats
  59% of the spread at 10s and *all* of it by 30s.
- **Sample size mattered enormously.** A 4-minute partial run showed BULLA drift +0.03 and
  FWDI +0.85; the full run gave -7.76 and -9.57. Never call this on a short sample.
- **The edge decays with holding time** — exactly the regime where we are weakest.

## Result 3 — latency (the decisive one)

| symbol | median quote life | % lives < 162 ms | pick-off % |
|---|---|---|---|
| BTCUSDT | **1 ms** | 91.9% | 26.5% |
| BULLAUSDT | **2 ms** | 98.0% | 5.0% |
| FWDIUSDT | **2 ms** | 97.6% | 7.5% |
| GWEIUSDT | **1 ms** | 83.7% | 1.2% |
| HOMEUSDT | **1 ms** | 72.2% | 6.8% |
| SOLUSDT | 681 ms | 46.5% | 8.1% |
| SYNUSDT | **2 ms** | 81.8% | 25.4% |

Median top-of-book lifetime is **1–2 ms** against our **162 ms** round trip. On GWEI —
the only robustly profitable name — **83.7% of quotes die before we could acknowledge
them.** We would never hold a current quote on any of these symbols, ever.

## Result 4 — capacity (order book depth, live)

| symbol | top-of-book notional |
|---|---|
| BULLAUSDT | **$79** |
| FWDIUSDT | **$411** |
| SYNUSDT | $724 |
| GWEIUSDT | $7,028 |
| HOMEUSDT | $9,071 |
| SOLUSDT | $417,573 |

The profitable names hold $79–$9,000 at top of book. The deep name is structurally
unprofitable. **The edge and the capacity are disjoint.**

## Result 5 — stale-fill split: MIS-SPECIFIED, reported honestly
Intent: split fills by whether the book re-priced in the prior 162 ms, to measure our
fill quality vs the average maker's. Result came out **backwards** (stale fills looked
*better*: BULLA +17.8 bps "latency cost").

That is a broken test, not a finding. With median quote life at 2 ms, essentially every
fill is "stale" by a 162 ms definition (BULLA: 2318 stale vs 159 fresh), so "fresh" is not
a control — it is a rare subsample where a hyperactive book happened to freeze. The split
degenerates because the market is faster than the measurement window. Would need
queue-position simulation, not a time window. **Not used in the verdict.**

---

## VERDICT
The edge is REAL and the net economics DO work on GWEIUSDT: **+12.6 bps per fill after
fees**, robust across horizons. What is absent is **capacity**:

- entire maker-side flow on GWEI: **$30,617 per 12 min** (~$10M/day)
- capture 100% of every maker fill (i.e. be the only MM in the symbol): **~$12,600/day**
- realistic 1–5% share: **$126–$630/day**
- ...while warehousing inventory in a microcap we cannot exit, at 162 ms, in a book that
  re-prices every 1 ms.

**Capacity is the one constraint better code cannot fix.** The prior session's instinct
that "the gross economics work" was correct — and irrelevant, because the pool the edge
lives in is too small to matter and too fast for us to reach.

Same conclusion as the HFT study, reached from the opposite direction: the binding
constraint is not our prediction quality, it is physics and inventory.

## What this does NOT close
Making trades **cheaper** is still the live, large win, and is independent of all the
above: we are taker on every leg (0.10% round trip) and fees are 31% of our losses.
Passive *entry* on our existing minutes-to-hours directional lanes cuts that to 0.04%.
That is not market making — no two-sided quoting, no inventory book, no cancel-replace —
and the adverse-selection numbers here are the reason it must be A/B'd rather than
assumed: passive fills are systematically worse than the mid you aimed at.

## Reusable artifacts
- `collect_markout.py` — WS recorder (`@trade` + `@bookTicker`) -> jsonl
- `analyze_markout.py` — markout / adverse-selection decomposition
- `latency_test.py` — quote lifetime + pick-off exposure vs our latency
- `stale_quote_markout.py` — mis-specified, kept as a record of the failed cut
- `markout-raw-1784401334.jsonl` — 32 MB raw tape, re-analysable

Note: this is the ONLY sub-second market data in the project. `binance_stream.py` captures
500 ms depth and event-level trades but folds everything into 60 s bars before persisting;
finest thing otherwise on disk is 60 s.
