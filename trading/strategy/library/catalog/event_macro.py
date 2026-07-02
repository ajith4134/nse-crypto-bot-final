"""catalog/event_macro.py — event-driven, macro, fundamental-factor & seasonal families (data-gated).

Edges driven by scheduled events, macro state, fundamentals or seasonality rather than the
price bar: earnings/budget/RBI/Fed/election trades, merger & dividend arb, index rebalancing,
opening-auction imbalance; macro rate/inflation/yield-curve/carry/super-cycle/CB-divergence;
NSE cash factor styles (growth/value/quality/factor/smart-beta/dividend); commodity seasonal/
harvest/weather. DATA_GATED on a news/event calendar, fundamentals, macro series or auction
data. The repo's advintel/ (nse_announcements, fii_dii) + news pipeline feed several.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy

_EV = (DataReq.NEWS_EVENTS,)
_FU = (DataReq.FUNDAMENTALS,)


def _g(name, category, family, logic, segments, data_req, oss, tf="event–weeks", notes=""):
    return LibraryStrategy(name=name, category=category, family=family, logic=logic,
                           segments=segments, timeframe=tf, data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes=notes)


STRATEGIES = [
    # ── event-driven ─────────────────────────────────────────────────────────
    _g("event_earnings", "event_driven", "earnings",
       "Trade the earnings event (drift/surprise/IV-crush around results).",
       ("nse_cash", "nse_options"), _EV + (DataReq.FUNDAMENTALS,), "earnings trading"),
    _g("event_budget", "event_driven", "budget",
       "Position around the Union Budget volatility & sector impact.",
       ("nse_cash", "nse_futures", "nse_options"), _EV, "budget-day trading"),
    _g("event_rbi_announcement", "event_driven", "central_bank",
       "Trade RBI policy announcements (rates/liquidity) impact on banks & rupee.",
       ("nse_futures", "nse_options"), _EV, "RBI announcement trading"),
    _g("event_fed_announcement", "event_driven", "central_bank",
       "Trade FOMC/Fed announcements impact on risk assets & crypto.",
       ("crypto_spot", "crypto_futures", "nse_futures"), _EV, "Fed announcement trading"),
    _g("event_election", "event_driven", "political",
       "Position around election results volatility.",
       ("nse_cash", "nse_futures"), _EV, "election trading"),
    _g("event_merger_arbitrage", "event_driven", "merger_arb",
       "Long target / short acquirer to capture the deal spread (risk arb).",
       ("nse_cash",), _EV + _FU, "merger arbitrage"),
    _g("event_dividend_arbitrage", "event_driven", "dividend_arb",
       "Capture dividend vs option/forward pricing around ex-dates.",
       ("nse_cash", "nse_options"), _EV + _FU, "dividend arbitrage"),
    _g("event_index_rebalancing", "event_driven", "rebalance",
       "Front-run index add/drop flows around rebalancing dates.",
       ("nse_cash", "nse_futures"), _EV, "index rebalancing"),
    _g("event_opening_auction_imbalance", "event_driven", "auction",
       "Trade pre-open auction imbalance / order concentration / institutional positioning.",
       ("nse_intraday",), (DataReq.NEWS_EVENTS, DataReq.ORDERBOOK_L2),
       "opening-auction imbalance", tf="intraday"),
    # ── macro ───────────────────────────────────────────────────────────────
    _g("macro_interest_rate", "macro", "rates", "Trade duration/rates on policy & data.",
       ("nse_futures",), (DataReq.NEWS_EVENTS, DataReq.MULTI_ASSET), "interest-rate trading", tf="weeks"),
    _g("macro_inflation", "macro", "inflation", "Position for inflation prints/regime.",
       ("mcx_commodities", "nse_futures"), _EV, "inflation trading", tf="weeks"),
    _g("macro_yield_curve", "macro", "curve", "Trade steepeners/flatteners on the yield curve.",
       ("nse_futures",), (DataReq.MULTI_ASSET,), "yield-curve trading", tf="weeks"),
    _g("macro_currency_carry", "macro", "carry", "Long high-yield / short low-yield currencies.",
       ("nse_futures",), (DataReq.MULTI_ASSET,), "currency carry trade", tf="weeks"),
    _g("macro_commodity_supercycle", "macro", "supercycle",
       "Position for multi-year commodity super-cycles.",
       ("mcx_commodities",), (DataReq.MULTI_ASSET, DataReq.FUNDAMENTALS), "commodity super-cycle", tf="months"),
    _g("macro_cb_divergence", "macro", "cb_divergence",
       "Trade divergence between central-bank policy paths (rate differentials).",
       ("nse_futures",), (DataReq.NEWS_EVENTS, DataReq.MULTI_ASSET), "central-bank divergence", tf="weeks"),
    # ── NSE cash delivery factor styles ────────────────────────────────────────
    _g("factor_growth", "machine_learning", "growth", "Growth investing (high earnings growth).",
       ("nse_cash",), _FU, "growth investing", tf="positional"),
    _g("factor_value", "machine_learning", "value", "Value investing (low P/E, P/B).",
       ("nse_cash",), _FU, "value investing", tf="positional"),
    _g("factor_quality", "machine_learning", "quality", "Quality (high ROE/low leverage).",
       ("nse_cash",), _FU, "quality investing", tf="positional"),
    _g("factor_investing", "machine_learning", "multifactor",
       "Multi-factor model (value/momentum/quality/size/low-vol).",
       ("nse_cash",), _FU + (DataReq.MULTI_ASSET,), "AQR factor investing", tf="positional"),
    _g("factor_smart_beta", "machine_learning", "smart_beta", "Rules-based smart-beta tilts.",
       ("nse_cash",), _FU + (DataReq.MULTI_ASSET,), "smart beta", tf="positional"),
    _g("factor_dividend", "machine_learning", "dividend", "Dividend / income investing.",
       ("nse_cash",), _FU, "dividend investing", tf="positional"),
    _g("factor_low_volatility", "machine_learning", "low_vol",
       "Low-volatility factor: tilt to low-realised-vol names (defensive premium).",
       ("nse_cash",), (DataReq.MULTI_ASSET,), "low-volatility factor", tf="positional"),
    _g("factor_carry", "machine_learning", "carry",
       "Carry factor: long high-carry / short low-carry across the universe.",
       ("nse_cash", "nse_futures"), (DataReq.MULTI_ASSET, DataReq.BASIS), "carry factor", tf="positional"),
    # ── commodity seasonality ───────────────────────────────────────────────
    _g("cmd_seasonal", "macro", "seasonal", "Seasonal commodity patterns (calendar effects).",
       ("mcx_commodities",), (DataReq.MULTI_TF,), "seasonal trading", tf="weeks"),
    _g("cmd_harvest_cycle", "macro", "harvest", "Agriculture harvest-cycle supply patterns.",
       ("mcx_commodities",), (DataReq.FUNDAMENTALS,), "harvest-cycle trading", tf="weeks"),
    _g("cmd_weather_models", "macro", "weather", "Weather-driven supply shocks (energy/agri).",
       ("mcx_commodities",), (DataReq.NEWS_EVENTS, DataReq.FUNDAMENTALS), "weather models", tf="weeks"),
]


# ── Wave 2: REAL NSE factor backtests (free yfinance fundamentals + price panel) ──
from trading.strategy.library.catalog import _impl_nse_factor as _nf  # noqa: E402
_FACTOR_BT = {"factor_value": _nf.bt_factor_value, "factor_growth": _nf.bt_factor_growth,
              "factor_quality": _nf.bt_factor_quality, "factor_dividend": _nf.bt_factor_dividend,
              "factor_low_volatility": _nf.bt_factor_low_volatility,
              "factor_investing": _nf.bt_factor_multifactor, "factor_smart_beta": _nf.bt_factor_multifactor}
for _s in STRATEGIES:
    if _s.name in _FACTOR_BT:
        _s.backtest = _FACTOR_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: yfinance NSE factor L/S").strip(" ·")
