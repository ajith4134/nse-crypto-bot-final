"""trading/uq — calibrated uncertainty for trade decisions (Pillar 17).

Conformal prediction (crepes CPS + MAPIE aux + netcal) over the closed-trades
journal → every candidate entry carries a calibrated ``p_up`` and a
coverage-guaranteed return interval, and ABSTENTION is a first-class action.
"""
from trading.uq.conformal import TradeUQ, get_uq, self_uncertainty_from_votes

__all__ = ["TradeUQ", "get_uq", "self_uncertainty_from_votes"]
