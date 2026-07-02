"""run_strategy_library.py — run the curated institutional Strategy Library (active T8 feature).

Thin root launcher (mirrors run_strategy_t8.py) for `trading.strategy.library.run`. The
genetic creation/mutation/evolution engine is gated OFF for this phase
(trading.strategy.control); this backtests the fixed library of named institutional
strategies on seeded synthetic OHLCV and prints a ranked OOS leaderboard + the catalogued
data-gated families.

Usage:
    .venv/bin/python run_strategy_library.py
"""
from __future__ import annotations

import sys

from trading.strategy.library.run import main

if __name__ == "__main__":
    sys.exit(main())
