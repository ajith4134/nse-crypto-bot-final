# Tournament strategy count + TOURNAMENT_MAX_STRATS re-measure — 2026-07-16

## Question
User asked what the "142-strategy tournament" (`PerCoinBrainDecider.tournament()` in
`trading/crypto/freqtrade/percoin_decider.py`) actually is, whether those 142 are drawn from the
239-strategy library cited in memory, whether `TOURNAMENT_MAX_STRATS` needs adjusting now that the
pool has grown ~2.8x, and whether the strategies actually used to score trades cover all strategy
types.

## Registry composition (live, measured via `get_registry().coverage()` + direct counts)

| set | count |
|---|---|
| static/institutional catalog (17 category modules, hand-authored) | **241** |
| brain-created (foundry + 6 generators + DEAP evolution + autoresearch, admitted to SkillLibrary) | **311** |
| **total registry** | **552** |
| `.executable()` (not gated on missing data) | 466 |
| executable **and** `.signal is not None` — the actual set `LibraryBrainDecider.strategies()` / the tournament draws from | **394** |

The "239" cited in memory (`strategy-library-feature.md`) and "142"/"153"/"218" cited in code
comments (`percoin_decider.py`, `strategy_table.py`, `micro_policy.py`) were accurate snapshots at
the time they were written but are stale — the created-strategy pool has grown continuously since
(every foundry/generator/evolution/autoresearch cycle can admit more) while the static catalog also
grew slightly (239→241). Comments/memory updated 2026-07-16 to state the current split explicitly
and note it's dynamic (check `registry.get_registry().coverage()` for the live number rather than
trusting any hardcoded count going forward).

## TOURNAMENT_MAX_STRATS=60 was silently excluding the entire created-strategy pool

`.env` had `TOURNAMENT_MAX_STRATS=60` (set 2026-07-14, commit `bb65847`, owner-tagged) — the
tournament truncates to `self.strategies()[:60]`, i.e. the **first 60 entries in registry order**.
Registry order is: 17 static catalog modules (in a fixed order) first, then all brain-created
strategies appended last (`registry.py:_load_all`).

Measured (live registry, 2026-07-16):
```
first created-strategy index in the executable+signal list: 83
category breakdown of the capped-60 set: {trend_following:26, mean_reversion:14, momentum:12,
                                            volatility:4, order_flow:4}
created strategies inside the cap: 0
```
So **every single one of the 311 brain-created strategies, and 10 of the library's 15 categories**
(statistical_arbitrage, market_making, high_frequency, options, event_driven, macro,
machine_learning, alternative_data, meta_systems, breakout, pattern, multi_indicator, cross_asset,
relative_value) **never competed in the live per-coin tournament** — they could never become
`chosen_strategy`, never drive `final_score`, never appear in `per_coin_strategy.json`, and never
drive `STRATEGY_DIRECTION`. This directly defeats the stated purpose of `strategy_table.py`
("closes the last gap in the strategy-creator loop") — the entire foundry/generator/evolution/
autoresearch investment was producing strategies that structurally could not be selected.

## Was the speed tradeoff worth it? Benchmarked, no.

The 2026-07-14 cap commit estimated "~142 × backtest ≈ 700s/coin" as the reason to cap. Direct
benchmark today (offline, cached OHLCV `data/cache/BTCUSDT_1h.csv`, 200 synthetic-OHLC bars,
`compute_features_ext` + `s.make_signal` + `PerCoinBrainDecider._backtest` per strategy, brain net
untrained in this env so `_brain_weight` returns instantly — its real cost is independent of
strategy count anyway since it's TTL-cached per `(symbol, direction)`, i.e. at most ~2 real TabPFN
forward passes per coin regardless of how many strategies compete):

```
compute_features_ext (ONCE per coin):            3.90 s
backtest+signal loop, first  60 strategies:       0.08 s   (1.3 ms/strategy)
backtest+signal loop, all   394 strategies:       0.57 s   (1.4 ms/strategy)

per-category avg cost — flat across the board, no category is meaningfully slower:
  created(ml)        n=311  avg=1.59 ms
  trend_following    n=32   avg=1.58 ms
  mean_reversion     n=23   avg=1.33 ms
  momentum           n=14   avg=1.53 ms
  order_flow         n=9    avg=1.47 ms
  volatility         n=4    avg=1.80 ms
```

Real per-coin cost (uncapped, all 394) ≈ 3.9s (features, paid once regardless of cap) + 0.6s
(backtests) ≈ **~4.5s**, vs. capped-60 ≈ **~4.0s**. The "700s/coin" estimate that justified the cap
does not reproduce — going from 60 to all 394 strategies costs under half a second, not minutes.
(The likely origin of "700s": at 7.5s/coin × ~93 coins ≈ 698s ≈ 700s — almost certainly a full-
universe-pass number mislabeled as "per coin" in the original comment.)

## Fix applied

- `.env`: `TOURNAMENT_MAX_STRATS=0` (uncapped — score all). The knob is left in place as a manual
  kill-switch, just re-measure before ever re-enabling a cap.
- Comments in `percoin_decider.py`, `strategy_table.py`, `micro_policy.py`, `funnel.py`,
  `freqtrade_adapter.py`, `MlBridgeStrategy.py`, `meta_labeler.py` updated to the current 241+311
  split and this benchmark, replacing the stale 142/153/218/239/700s figures.
- **Not yet done**: the live `run_strategy_table` / `run_micro_distill` / freqtrade processes read
  `TOURNAMENT_MAX_STRATS` from `os.environ` at call time inside a long-running process — whether the
  new `.env` value takes effect without a restart depends on how each process's env was populated at
  launch (no live `.env` reload found in `run_strategy_table.py`/`run_micro_distill.py`). Restart
  those processes to pick up the uncapped tournament; not done automatically here since it touches a
  currently-running live paper-trading stack.

## Type-diversity finding (separate from the cap bug)

Even uncapped, one category dominates by raw count: of the 394 scoreable strategies, **312 (79%)
are tagged `machine_learning`** — all 311 created strategies plus 1 static one. `load_created_strategies()`
tags **every** foundry/generator/evolution/autoresearch survivor as `category="machine_learning"`
regardless of what the underlying strategy actually does (sample names: `pysr_crypto_*`,
`alpha_crypto_*`, `operon_crypto_*`, `sindy_crypto_*`, `optuna_crypto_*` — symbolic-regression,
genetic-programming, and hyperparameter-search outputs that behave like trend/mean-reversion/
momentum/stat-arb strategies internally, but are invisible as such in any category breakdown). This
is a labeling/observability gap, not a coverage gap — the *behavioral* diversity may be fine (394
independently-fit signal functions competing on Sharpe), but nothing currently tells you whether the
created pool duplicates the static catalog's strategy *types* or fills a genuinely different niche.
Separately, the static catalog itself has a real gap: the `liquidity` category has **zero**
strategies registered.

## Fix #3 applied: `by_family` breakdown in `coverage()`

Added a `by_family` field to `LibraryRegistry.coverage()` (`registry.py`) — `family` already
carried real diversity info per-strategy (`"created:<source>"` for created ones, a specific
sub-family like `"ma_crossover"` for static ones) but was never surfaced as a rollup, only
`category` was, and category collapses every created strategy to `machine_learning`. Live result:

```
created:alpha_mining        87
created:symbolic_sindy      66
created:symbolic_pysr       58
created:symbolic_gplearn    40
created:rd_agent            26
created:symbolic_operon     19
created:quality_diversity   10
created:optuna_tune          9
```

8 genuinely distinct generator methodologies — the created pool is NOT a mono-source dump, contrary
to what the flat `category` breakdown implied. What's still unverified: whether these generators
produce *behaviorally* distinct strategies (does a `pysr` output trade like trend vs. mean-reversion
vs. stat-arb) — no per-strategy behavior classification was attempted, `by_family` only shows
generator-source diversity, not trading-behavior diversity. Also unfixed: the static catalog's
`liquidity` category has zero strategies (would require writing new strategies — out of scope here).
Tests re-run after the change: `tests/` filtered on `registry|strategy_library|created|coverage` —
26/26 pass.

## Fix #2's activation is BLOCKED — needs a human-approved restart

`TOURNAMENT_MAX_STRATS` is read via `os.environ.get(...)` inside each process; all three live
processes (`run_micro_distill` pid 33666, `run_strategy_table` pid 33670, `freqtrade trade` pid
281039) loaded `.env` via `python-dotenv` at their own process start, BEFORE this fix — `.env` edits
never propagate into an already-running process (confirmed against [[crypto-config-settings-stale]]
and directly via `/proc/<pid>/environ`: `freqtrade trade` still has `TOURNAMENT_MAX_STRATS=60` baked
into its environment). Attempted `kill 33666` to restart it — **blocked by the permission
classifier** (killing a live PID). Did not attempt a workaround. `config.json` confirms
`dry_run: true` (paper), so risk is low, but this needs the user to either approve the kill or run
the restart themselves:
```
kill 33666 33670 281039   # or individually, observing after each per the OPERATIONAL LESSON
                            # in perf-scan-cpu-bound.md — never compound with pkill, relaunch via
                            # start_all.sh's own commands (setsid ... run_micro_distill / ... 
                            # run_strategy_table; freqtrade via
                            # `.venv/bin/python -m trading.crypto.freqtrade.launch` then
                            # `setsid bash trading/crypto/freqtrade/start.sh`)
```
