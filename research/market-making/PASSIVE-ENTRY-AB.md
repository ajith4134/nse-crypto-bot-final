# Passive (maker) ENTRY A/B — build + pre-experiment findings
2026-07-18. Follow-on to `FINDINGS.md` (market-making verdict). Mode: PAPER (money-lens: PROCEED).

The ask: A/B passive vs taker ENTRY on the crypto lane. Cutting round-trip cost
0.10% → 0.04% matters because fees are 31% of our losses.

**The experiment is BUILT and VALIDATED but NOT YET RUNNING** — it needs one process
restart (see "To start it" below). Everything measured here came from data that already
existed, before the A/B produces its first row.

---

## 1. It was already half-built — and already running unrandomized
`trading/execution/exec_choice.py` (E7, 2026-07-17) already chooses limit-at-touch vs
market per entry, logs every choice, and grades slippage. **Enabled by default.**
1,748 real decisions over 2026-07-17/18.

Its reported result looked excellent:

| order type | n | mean slippage vs decision mid |
|---|---|---|
| limit | 163 | **−2.905 bps** (better than mid) |
| market | 215 | **+3.845 bps** (worse than mid) |

**6.75 bps in favour of maker — and it is not trustworthy.** Three compounding defects:

1. **Selection.** `choose()` picks limit exactly when drift is `coming_to_us` — price
   already moving toward our resting price. That is the condition under which a passive
   order fills well. The sample is chosen by the outcome's own cause.
2. **Survivorship.** `grade_fills()` iterates over TRADES. A limit order that never became
   a trade is invisible to it. The −2.905 bps is conditional on fill.
3. **Fuzzy join.** It matches any log row for the same symbol within **±300 s**,
   nearest-wins. At ~1,000 trades/day that can cross-attribute a market order to a limit
   decision.

Neither 1 nor 2 is fixable by analysis. They need randomization — which is what was built.

## 2. What the existing data DOES support (and it is not encouraging)
Joining the 1,748 decisions to the trades DB:

| reason | type | n | mean P&L% |
|---|---|---|---|
| tight_spread | market | 260 | **−0.388** |
| no_book | market | 921 | −0.727 |
| wide_spread | limit | 91 | −1.365 |
| coming_to_us | limit | 257 | **−1.537** |
| running_away | market | 219 | **−1.791** |

Overall: limit entries **−1.490%** vs market **−0.834%**. Passive entries did WORSE, and
the two drift-conditioned buckets (`coming_to_us`, `running_away`) are the two worst cells
while the drift-agnostic `tight_spread` is the best. Confounded, but it is the direction
the markout study predicted: a passive fill happens *because* price came to you.

Also: **53% of all entries hit `no_book`** — the RAM mirror had no fresh book, so E7
silently degraded to market. Half the lane was never eligible for the feature at all.

## 3. Paper CANNOT settle maker fill rate — the blocking validity limit
Measured on 1,144 limit ENTRY orders in the Freqtrade DB:

```
fill rate 99.9%   median wait 27 s   p90 634 s   MAX 124,709 s  (34.6 HOURS)
```

Cause: `unfilledtimeout` was `null`, so Freqtrade never expired an unfilled limit
(`interface.py:1734` skips the check when None). The order simply waits until price
eventually crosses it — which, given unbounded time, it essentially always does.
An entry filling 34 hours after its signal is not that signal's trade.

Deeper and unfixable: `_dry_is_price_crossed` (`exchange.py:1288`) is a single price
comparison. **No queue position, no depth ahead, no partial fills — the order's own size
is never read.** Real maker fills require the queue at your level to clear. Meanwhile
market orders DO get an honest book-walk (`get_dry_market_fill_price`), and maker fees are
applied correctly. So paper gives the taker arm a realistic cost and the maker arm a
fantasy fill rate — the worst combination, because it looks rigorous.

**⇒ Treat any paper maker fill rate as an UPPER BOUND. The one paper number that can be
trusted is slippage conditional on fill, against a real recorded mid.**

## 4. A live data-integrity bug, fixed
`freqtrade_ingest.py` hardcoded `entry_order_type="MARKET", exit_order_type="MARKET"`.
**1,142 limit entries were recorded as MARKET.** Any maker-vs-taker study reading the
journal would have compared MARKET against MARKET and correctly found nothing.

Fixed: `_leg_order_type()` reads Freqtrade's own order rows, preferring the authoritative
`ft_is_entry` flag (survives DCA/partials) over side inference. Verified across 7,824
closed trades: 6,681 MARKET/MARKET, 829 LIMIT/LIMIT, 313 LIMIT/MARKET, 1 MARKET/LIMIT.

This also makes visible Freqtrade's silent limit→market conversion when an order crosses
the spread by >1% (`exchange.py:1188`) — previously undetectable.

## 5. Why the A/B must NOT be judged on P&L
σ of `net_pnl_pct` ≈ **8.4%** per trade. The effect is ~4–7 bps of entry cost.

```
n per arm ≈ 16σ²/Δ²  →  ~9,800 per arm  →  ~18 days at 1,100 closes/day
```

A P&L-only readout would show noise for two and a half weeks and invite a false "no
difference" conclusion. **Endpoints in descending power: (1) fill rate, binomial, tight at
n≈400/arm; (2) slippage vs mid, low variance, the direct causal channel; (3) ITT P&L,
reported with a CI so it reads as unresolved rather than null.**

## 6. What was built
- **`exec_choice.py`** — `ab_enabled()` + `_ab_arm()`: deterministic fair coin over
  (symbol, side, minute), sha256 not `hash()` (PYTHONHASHSEED randomizes str hashing per
  process; the arm must be reproducible offline and across restarts). Minute-keyed so a
  retried signal cannot re-roll into the other arm and count twice. `EXEC_AB_FRAC` gates
  participation. Verified: 1967/2033 split over 4,000 symbols, stable within a minute.
  Randomization is placed AFTER the book checks — so every randomized decision is one where
  BOTH arms were feasible (a `no_book` entry cannot be a maker order at all).
- **`config_template.py`** — `unfilledtimeout {entry:120, exit:600, seconds}`. Put in the
  TEMPLATE, not config.json: `launch.py` regenerates config.json via `write_config()` and
  would have silently wiped a direct edit. Verified to survive regeneration.
- **`freqtrade_ingest.py`** — the order-type fix above.
- **`research/market-making/entry_ab_report.py`** — ITT readout. Joins to the ORDERS table,
  not trades, so cancelled maker orders are counted as the misses they are.
- **`.env`** — `EXEC_AB=1`, `EXEC_AB_FRAC=1.0`.

Tests: 21 passed (`-k "exec_choice or ingest or freqtrade_ingest"`).

## To start it
The running processes predate the `.env` change and Python has no hot-reload, so they must
be respawned. Kill by PID (never `pkill` inline — the pattern matches the invoking shell
and kills it, exit 144), then let the guarded launcher respawn:

```bash
kill <run_funnel_loop crypto pid> <run_live_loop pid> <freqtrade trade pid>
bash start_all.sh          # pgrep-guarded; run in background, can exceed 120s
```
Verify with `ps -o lstart= -p <new pids>` that they started after the change, then:
```bash
.venv/bin/python research/market-making/entry_ab_report.py
```
First rows take one funnel cycle (2–15 min). Fill rate and slippage should be readable
within a few hours; ITT P&L will not resolve for ~18 days and should not be forced.

## Standing caveat
Even a clean result here says what passive entry does **on paper, with no queue model**.
It can tell us the slippage channel is real and size it. It cannot tell us the true fill
rate — that needs live maker orders, and the markout study (`FINDINGS.md`) is the reason
to expect real fills to be worse than paper's.
