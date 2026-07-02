"""catalog/order_flow.py — tick-level order-flow family (data-gated).

The trade-by-trade slice of flow: footprint/CVD, aggressor & absorption detection, iceberg &
spoofing detection, stop-hunt & liquidity-sweep, plus the crypto-derivatives flow signals
(OI breakout, liquidation hunting/sniping). These need tick/aggressor data, L2 depth, open
interest or the liquidation feed — so DATA_GATED. (Bar-level volume/flow that DOES run on
candles lives in catalog/volume_flow.py.) The repo's advintel/liquidations.py + ccxt OI feed
unlock several of these.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy
from trading.strategy.library.catalog import _impl_crypto_deriv as cd

_CRY = ("crypto_futures", "crypto_spot")
_NSE = ("nse_futures", "nse_options")
_TICK = (DataReq.TICKS,)
_TICKL2 = (DataReq.TICKS, DataReq.ORDERBOOK_L2)


def _g(name, family, logic, segments, data_req, oss, notes="", backtest=None):
    return LibraryStrategy(name=name, category="order_flow", family=family, logic=logic,
                           segments=segments, timeframe="ms–hours", data_req=tuple(data_req),
                           signal=None, backtest=backtest, oss_source=oss, notes=notes)


STRATEGIES = [
    _g("of_footprint", "footprint",
       "Footprint/bid-ask volume per price level to read intrabar buying vs selling.",
       _CRY + _NSE, _TICK, "footprint charts", notes="needs per-trade aggressor side"),
    _g("of_cumulative_delta", "cvd",
       "Cumulative volume delta (aggressor buys − sells); trade CVD/price divergence.",
       _CRY + _NSE, _TICK, "delta-volume / CVD analysis"),
    _g("of_aggressive_buyer", "aggressor",
       "Detect persistent aggressive market-buy/sell pressure and follow it.",
       _CRY + _NSE, _TICK, "aggressive-buyer detection"),
    _g("of_absorption", "absorption",
       "Large resting orders absorbing aggressive flow → reversal as flow exhausts.",
       _CRY + _NSE, _TICKL2, "absorption detection"),
    _g("of_iceberg", "iceberg",
       "Detect hidden iceberg orders from repeated refills at a level.",
       _CRY + _NSE, _TICKL2, "iceberg detection"),
    _g("of_spoofing", "spoofing",
       "Detect spoofed depth (placed then pulled) and fade the fake pressure.",
       _CRY + _NSE, _TICKL2, "spoofing detection"),
    _g("of_stop_hunt", "stop_hunt",
       "Anticipate stop-run sweeps beyond obvious levels, then fade the snapback.",
       _CRY + _NSE, _TICKL2, "stop-hunt detection"),
    _g("of_liquidity_sweep", "liquidity_sweep",
       "Trade liquidity-sweep / liquidity-grab reversals at swept highs/lows.",
       _CRY + _NSE, _TICKL2, "liquidity-sweep trading"),
    # ── crypto derivatives flow ──────────────────────────────────────────────
    _g("of_oi_breakout", "oi_breakout",
       "Open-interest expansion confirming a price breakout (real positioning).",
       ("crypto_futures", "nse_futures", "nse_options"), (DataReq.OPEN_INTEREST,),
       "open-interest breakout", notes="REAL: ccxt OI history + perp breakout",
       backtest=cd.bt_oi_breakout),
    _g("of_liquidation_hunting", "liquidation",
       "Position ahead of cascading forced liquidations near key leverage zones.",
       ("crypto_futures",), (DataReq.TICKS, DataReq.OPEN_INTEREST),
       "hummingbot.org liquidation guides; repo advintel/liquidations.py",
       notes="needs liquidation feed / OI clustering"),
]


# ── Wave 3: REAL order-flow backtests (binance taker-volume CVD). L2-microstructure
# (iceberg/spoofing/stop_hunt/liquidation) stays gated for the forward L2/tick collector.
from trading.strategy.library.catalog import _impl_orderflow as _ofb  # noqa: E402
_OF_BT = {"of_footprint": _ofb.bt_footprint, "of_cumulative_delta": _ofb.bt_cumulative_delta,
          "of_aggressive_buyer": _ofb.bt_aggressive_buyer, "of_absorption": _ofb.bt_absorption,
          "of_liquidity_sweep": _ofb.bt_absorption}
for _s in STRATEGIES:
    if _s.name in _OF_BT and any('crypto' in seg for seg in _s.segments):
        _s.backtest = _OF_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: taker-volume CVD").strip(" ·")
