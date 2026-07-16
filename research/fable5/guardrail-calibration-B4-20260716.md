# B4 — THE GUARDRAIL: calibrated or wall? Answer: A WALL, with a named mechanism — now repaired (2026-07-16, night)

**Verdict: the anti-overfit gate was structurally impassable — not because the thresholds were
strict, but because the per-trade return series fed to the deflated-Sharpe test was corrupted:
SHORT-trade winners were recorded as losers. Every one of the ~5,600 candidates across 100
evolution runs was judged on that corrupted series. PROMOTED=0 measured the bug, not the
candidates. The bug is fixed at root; the gate re-calibrates to "strict but passable"; the
thresholds themselves were NOT touched.**

## 1. The candidate record (what the 100 runs actually show)

`self_evolve.json`: 100 runs × ~56 candidates ≈ 5,600 evaluated, **promoted 0, admitted 0**.
In-sample best_score median 1.05, max 12.79; PBO median 0.50 (the textbook noise-mining
signature — half of in-sample winners degrade OOS). On its face this reads "honest gate,
garbage candidates". The calibration probe says otherwise.

## 2. The calibration probe (known truth through the exact production gate)

Method (the literature-correct way — never tune until something passes; plant known truth and
measure both error rates): duck-typed strategies through the *same* `passes_guardrails`
(evolve defaults: n_trials=56, dsr_min=0.6, min_trades=10) on 20,000 real BTC/USDT 5-minute
bars, 1-hour holds, real fee model (3 bps round-trip-leg).

| probe | truth | pass rate BEFORE fix | pass rate AFTER fix |
|---|---|---|---|
| 25 null strategies (random persistent positions) | no skill | 0/25 ✅ | 0/25 ✅ |
| 10 oracles @ 52% bar accuracy | tiny real edge | 0/10 | 0/10 (correct: fees eat it — OOS returns mostly negative) |
| 10 oracles @ 55% | solid edge | 0/10 | 0/10 (borderline-strict; OOS returns positive but small) |
| 10 oracles @ **60%** | **enormous edge** (OOS returns up to **+100%**, ~4,500 trades) | **0/10 — THE WALL** | **4/10 — passable** |

A gate that fails a 60%-accurate oracle earning +100% out of sample on 4,500 trades is not
strict; it is broken.

## 3. The mechanism (root cause, file:line)

`trading/strategy/backtest.py` built portfolios with
`vbt.Portfolio.from_orders(size_type="targetpercent")` and then read per-trade returns from
`pf.trades.records_readable["Return"]`. With target-percent rebalancing orders those records
are order-pairing cash-flow artifacts, not directional round-trip returns — **short winners
come out negative**. Direct falsification: a short-only 60% oracle showed equity **+5.35%**
while only **41.5%** of its recorded trade returns were positive (a 60% oracle should win
~60%). The B4 symptom in the wild: 60%-oracle probes with +29% to +100% OOS equity showed
*negative mean per-trade return* (SR −0.07 to −0.12) → DSR 0.000 → automatic fail, forever.

**Fix (applied):** per-trade returns are now derived from the signal segments themselves —
each maximal run of a constant nonzero target position is one round trip,
`ret = side × (exit/entry − 1) − 2×cost` (`_segment_trades`, backtest.py). The pandas
fallback path already did this correctly; only the vectorbt path was wrong. Equity/drawdown/
Sharpe metrics were always computed from the portfolio and were never affected — only the
per-trade series the DSR/PBO/win-rate consumed.

**Deliberately NOT changed:** `dsr_min=0.6`, `min_trades=10`, drawdown limit, n_trials
deflation — the bright line ("never loosen the gate to manufacture flow") was respected. The
post-fix calibration shows the thresholds are defensible: nulls all fail, marginal edges fail,
big edges pass.

## 4. Consequences beyond the gate (blast radius, stated honestly)

Every consumer of `backtest_signal(...).trades` judged short trades on inverted returns:
- **self_evolve / evolve / foundry promotion** — the headline (100 runs void as evidence).
- **fitness() expectancy/profit-factor objectives** — evolution has been *selecting against*
  good short genes and favoring bad ones for as long as this code path existed.
- **per-coin strategy tournament (strategy_table)** — short-strategy rankings biased; the
  daemon was restarted on the fixed code (per-coin table will re-rank over its next cycles).
- Win-rate/expectancy numbers in any historical foundry/tournament report that came from
  vectorbt-path trades: treat as suspect for short-heavy strategies.

Regression tests: `tests/test_backtest.py` (short winner positive, segment splitting,
end-to-end sign consistency) + guardrails/evolve/self_evolve/strategy_table/percoin suites —
54 tests green. Verified by re-running the full calibration probe through the repaired gate.

## 5. What to do with the answer (recommendation, owner decides)

1. The generator-vs-gate question is now genuinely open again — the old "candidates are all
   garbage" conclusion was unmeasurable. Let evolution run on the fixed fitness for ~a week of
   cycles before judging the generators.
2. If promotions stay at 0 *after* clean re-runs, THEN the generator is the problem (B4's
   original alternative) — revisit with the same probe method, not threshold tuning.
3. Historical strategy_table rankings will self-correct as the daemon re-scores; no manual
   surgery needed (scores are recomputed per cycle).

## Method / reproduction

Probe script: session scratchpad `b4_gate_calibration.py` (deterministic seeds; BTC 5m feather;
oracles = forward-sign diluted to target accuracy, 12-bar holds; nulls = persistent random).
Raw results: `b4_results.json` (pre-fix run). Post-fix pass rates measured with the identical
script. All numbers re-derivable; nothing in production state was touched by the probes.
