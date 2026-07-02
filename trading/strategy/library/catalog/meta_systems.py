"""catalog/meta_systems.py — Level-11 meta-strategy systems (data-gated portfolio layers).

How modern multi-strategy funds (Millennium / Point72 / Citadel) actually operate: a regime
layer, a strategy-allocation layer over many sub-strategies, a risk layer, and an execution
layer. These are PORTFOLIO-LEVEL meta-strategies — they consume the OUTPUT of many of the
library's strategies + the brain's regime/risk nodes — so they're catalogued as data-gated
orchestration specs (executable once the live multi-strategy book + execution venue are wired;
the gated-off evolution engine and the regime HMM already exist to feed them).
OSS: repo trading/brain/regime.py, sizing/, execution/, advintel/portfolio_risk.py.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy

_ALL = ("nse_cash", "nse_intraday", "nse_futures", "nse_options", "mcx_commodities",
        "crypto_spot", "crypto_futures", "crypto_options")


def _g(name, family, logic, data_req, oss, notes=""):
    return LibraryStrategy(name=name, category="machine_learning", family=family, logic=logic,
                           segments=_ALL, timeframe="continuous", data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes="meta-system layer — " + notes)


STRATEGIES = [
    _g("meta_regime_detection_layer", "regime_layer",
       "Classify bull/bear/sideways/vol-expansion/panic regimes to gate sub-strategies.",
       (DataReq.MULTI_ASSET,), "repo trading/brain/regime.py (HMM); Bayesian-switching; Transformer",
       notes="HMM single-series version IS executable: ml_regime_switching_hmm"),
    _g("meta_strategy_allocation_layer", "allocation_layer",
       "Dynamically allocate capital across trend/vol/arb/MM strategies by regime & performance.",
       (DataReq.MULTI_ASSET,), "meta strategy selection; repo node-network router",
       notes="consumes the library leaderboard + regime"),
    _g("meta_risk_layer", "risk_layer",
       "Portfolio risk controls: gross/net, correlation, tail (VaR/ES) and liquidity limits.",
       (DataReq.MULTI_ASSET,), "repo advintel/portfolio_risk.py, stress.py",
       notes="overlay across the whole book"),
    _g("meta_execution_layer", "execution_layer",
       "Choose order type per child slice: market/limit/TWAP/VWAP/POV to minimise impact.",
       (DataReq.ORDERBOOK_L2, DataReq.TICKS), "optimal execution; repo execution/engine.py",
       notes="TWAP/VWAP/POV scheduling"),
]
