# Strategy Research Library — INDEX (7 segments)

Curated, proven strategy templates per market segment (research phase). Each segment file
documents every template with name · family · logic · entry/exit · indicators+params ·
timeframe · regime fit · OSS source · genome-mappable flag.

| # | Segment | File | Templates |
|---|---------|------|-----------|
| 1 | NSE intraday cash/equity | [nse-intraday-cash.md](nse-intraday-cash.md) | 122 |
| 2 | NSE futures (index + stock) | [nse-futures.md](nse-futures.md) | 143 |
| 3 | NSE options (incl. multi-leg) | [nse-options.md](nse-options.md) | 126 |
| 4 | MCX commodities | [nse-commodities-mcx.md](nse-commodities-mcx.md) | 124 |
| 5 | Crypto spot | [crypto-spot.md](crypto-spot.md) | 131 |
| 6 | Crypto futures / perp | [crypto-futures-perp.md](crypto-futures-perp.md) | 120 |
| 7 | Crypto options | [crypto-options.md](crypto-options.md) | 88 |
| | **TOTAL** | | **854** |

## Related files
- **[SOURCE_REQUIREMENTS.md](SOURCE_REQUIREMENTS.md)** — every strategy family / named strategy /
  OSS repo the user specified (Blocks 1–4: 15-category taxonomy, ultra-advanced firm-internal
  tier, highest-profitability tier, 11-level retail→institutional hierarchy).
- **[COVERAGE_CROSSCHECK.md](COVERAGE_CROSSCHECK.md)** — auto-generated map of every named
  strategy → its implemented catalog entry (executable or data-gated). 157/157 concepts covered.

## Implementation
The research above is realised in code as the **Strategy Library** (`trading/strategy/library/`):
- **239** concrete `LibraryStrategy` definitions across 15 institutional categories + 8 segments.
- **79 executable** — real `+1/-1/0` signals over an extended TA-Lib feature frame, scored
  out-of-sample through the existing T8 backtest (`run_strategy_library.py`).
- **160 data-gated** — full specs + OSS source + the exact data input (L2/ticks/IV-greeks/OI/
  funding/multi-asset/fundamentals) that unlocks them; never fabricated metrics.
- Genetic creation/mutation/evolution is **gated OFF** (`trading.strategy.control`) for this
  phase — the fixed library runs first so we can see how the known templates perform.
- Dashboard: `/api/trading/strategy/library` → "Strategy Library" panel (coverage, OOS
  leaderboard, data-gated families by need).

## Genome-mappable summary (research flags)
Across the segment files, templates are flagged `yes` (pure TA-feature rule), `partial` (needs
IV-rank/greeks/OI/funding overlays the repo can compute), or `no` (structurally vol/greek/OI/
orderflow-driven). The `yes`/`partial` set seeds the (currently gated-off) evolution engine; the
`no` set maps to the data-gated catalogue.
