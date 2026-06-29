"""Phase-T8: Position / capital sizing layer (NSE + crypto, long & short).

Decides *how much capital to deploy per trade* from
``{capital, entry, stop/ATR, win-rate/payoff, prob, volatility}``.

REUSE-FIRST: per-trade Kelly comes from the installed ``keeks`` library
(``KellyCriterion`` / ``FractionalKellyCriterion`` / ``DrawdownAdjustedKelly``);
the cross-asset capital split stays in
``trading/advintel/portfolio_risk.py`` (riskfolio-lib). The AI bet-sizing
("ai_meta") is the Lopez de Prado AFML Ch.10 "bet sizing from predicted
probabilities" algorithm, implemented directly here (mlfinlab/mlfinpy do not
build on this box -- numba fails -- so we ship the ~10-line equivalent).

CPU-only, fully offline, deterministic (``scipy.stats.norm`` for the CDF).
"""
from __future__ import annotations

from .position_sizer import (
    PositionSizer,
    afml_bet_size,
    build_demo_sizing,
)

__all__ = ["PositionSizer", "afml_bet_size", "build_demo_sizing"]
