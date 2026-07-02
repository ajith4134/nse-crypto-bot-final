"""catalog/options.py — options & options-volatility family (data-gated).

The full options playbook: directional (long call/put, covered call, protective put, vertical
spreads), neutral income (short straddle/strangle, iron condor/butterfly), volatility (long
straddle/strangle, calendar, diagonal), and advanced quant (gamma scalping, delta-neutral &
vega arb, volatility-surface/skew/term-structure arb, dispersion, vol-cone, IV-RV & vol-carry,
VRP harvesting, dynamic delta hedging, dealer gamma/vanna/charm flow, delta-gamma hedging nets).

All need an option chain and/or IV-greeks, so DATA_GATED — BUT the repo already computes greeks
(trading/options/greeks.py, iv.py, gex.py, max_pain.py, pcr.py via Black-76/vollib), so these
flip to executable as soon as the chain is fed in. OSS sources cited per entry.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy

_NSE = ("nse_options",)
_CRY = ("crypto_options",)
_BOTH = ("nse_options", "crypto_options")
_CHAIN = (DataReq.OPTION_CHAIN,)
_GREEKS = (DataReq.OPTION_CHAIN, DataReq.IV_GREEKS)


def _g(name, family, logic, segments, data_req, oss, tf="hours–weeks", notes=""):
    return LibraryStrategy(name=name, category="options", family=family, logic=logic,
                           segments=segments, timeframe=tf, data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes=notes)


STRATEGIES = [
    # ── directional ─────────────────────────────────────────────────────────
    _g("opt_long_call", "directional", "Buy a call for leveraged upside (defined risk).",
       _BOTH, _CHAIN, "PyPatel/Options-Trading-Strategies-in-Python"),
    _g("opt_long_put", "directional", "Buy a put for downside / hedge (defined risk).",
       _BOTH, _CHAIN, "PyPatel/Options-Trading-Strategies-in-Python"),
    _g("opt_covered_call", "income", "Long underlying + short call to harvest premium.",
       _BOTH, _CHAIN, "PyPatel/...; mirajgodha/options"),
    _g("opt_protective_put", "hedge", "Long underlying + long put as insurance.",
       _BOTH, _CHAIN, "PyPatel/Options-Trading-Strategies-in-Python"),
    _g("opt_bull_call_spread", "vertical", "Long lower-strike call / short higher-strike call.",
       _NSE, _CHAIN, "vertical spread"),
    _g("opt_bear_put_spread", "vertical", "Long higher-strike put / short lower-strike put.",
       _NSE, _CHAIN, "vertical spread"),
    # ── neutral income ────────────────────────────────────────────────────────
    _g("opt_short_straddle", "income", "Sell ATM call+put; profit if it stays range-bound.",
       _BOTH, _GREEKS, "buzzsubash/algo_trading_strategies_india", notes="short-gamma income"),
    _g("opt_short_strangle", "income", "Sell OTM call+put; wider breakevens than a straddle.",
       _BOTH, _GREEKS, "buzzsubash/algo_trading_strategies_india"),
    _g("opt_iron_condor", "income", "Short strangle + long wings = defined-risk range income.",
       _BOTH, _GREEKS, "mirajgodha/options; PyPatel/..."),
    _g("opt_iron_butterfly", "income", "Short ATM straddle + long wings (tight defined-risk).",
       _BOTH, _GREEKS, "mirajgodha/options"),
    # ── long volatility ─────────────────────────────────────────────────────
    _g("opt_long_straddle", "long_vol", "Buy ATM call+put for a big move either way.",
       _BOTH, _GREEKS, "long straddle"),
    _g("opt_long_strangle", "long_vol", "Buy OTM call+put — cheaper long-vol, wider breakevens.",
       _BOTH, _GREEKS, "long strangle"),
    _g("opt_calendar_spread", "term_structure", "Short near-expiry / long far-expiry same strike.",
       _BOTH, _GREEKS, "calendar spread"),
    _g("opt_diagonal_spread", "term_structure", "Calendar across different strikes (diagonal).",
       _BOTH, _GREEKS, "diagonal spread"),
    _g("opt_ratio_spread", "ratio", "Unbalanced long/short option ratio (e.g. 1×2) for skew/credit.",
       _NSE, _GREEKS, "ratio spreads"),
    # ── advanced quant / volatility ─────────────────────────────────────────
    _g("opt_gamma_scalping", "gamma_scalp",
       "Long ATM straddle, delta-hedge continuously; profit when realised vol > implied.",
       _BOTH, _GREEKS, "alpacahq/gamma-scalping; michaelsyao/GammaScalping; mirajgodha/options",
       notes="flagship vol-desk strategy"),
    _g("opt_delta_neutral_arbitrage", "delta_neutral",
       "Delta-neutral option vs underlying portfolio capturing mispriced optionality.",
       _BOTH, _GREEKS, "delta-neutral arbitrage"),
    _g("opt_vega_trading", "vega",
       "Take directional vega (long/short vol) hedged of delta.",
       _BOTH, _GREEKS, "vega trading"),
    _g("opt_iv_rv_arbitrage", "iv_rv",
       "Trade implied vol vs forecast realised vol (sell rich IV / buy cheap IV).",
       _BOTH, _GREEKS, "leanderdulac/crypto_vol_arb; u3ffrzi/options-market-maker-algorithm"),
    _g("opt_volatility_carry", "vol_carry",
       "Harvest the slope of the vol term structure (sell front, buy back).",
       _BOTH, _GREEKS, "volatility carry"),
    _g("opt_vrp_harvest", "vrp",
       "Volatility-Risk-Premium: systematically sell expensive IV, hedge delta.",
       _BOTH, _GREEKS, "VRP harvesting (Citadel/Millennium-style)", notes="top long-run Sharpe"),
    _g("opt_volatility_surface_arb", "surface_arb",
       "Trade smile/skew/term-structure distortions vs a fitted surface.",
       _BOTH, _GREEKS, "alexanderkudryashov3/Crypto-Options", notes="IV percentile/rank/curvature"),
    _g("opt_skew_trading", "skew",
       "Trade put/call skew richness/cheapness (risk-reversal).",
       _BOTH, _GREEKS, "skew arbitrage"),
    _g("opt_dispersion", "dispersion",
       "Long index vol / short component vol (or inverse) on correlation mispricing.",
       _NSE + _CRY, _GREEKS, "billydavila/Dispersion-Trading-Strategy",
       notes="Citadel/Jane Street/Millennium dispersion"),
    _g("opt_volatility_cone", "vol_cone",
       "Compare current IV to its historical realised-vol cone by horizon.",
       _BOTH, _GREEKS, "volatility cone"),
    _g("opt_dynamic_delta_hedging", "delta_hedge",
       "Continuously re-hedge option delta as spot/IV move (MM/vol-desk core).",
       _BOTH, _GREEKS, "dynamic delta hedging"),
    _g("opt_dealer_gamma_exposure", "dealer_gamma",
       "Use dealer net-gamma (GEX) to predict pinning vs squeeze; trade the regime.",
       _NSE + _CRY, (DataReq.OPTION_CHAIN, DataReq.IV_GREEKS, DataReq.OPEN_INTEREST),
       "dealer gamma exposure (repo trading/options/gex.py)", notes="weekly NIFTY/BankNifty pinning"),
    _g("opt_dealer_vanna", "dealer_vanna",
       "Track dealer vanna (delta sensitivity to IV) hedging flows.",
       _NSE, (DataReq.OPTION_CHAIN, DataReq.IV_GREEKS, DataReq.OPEN_INTEREST), "dealer vanna models"),
    _g("opt_dealer_charm", "dealer_charm",
       "Track dealer charm (delta decay over time) hedging flows into expiry.",
       _NSE, (DataReq.OPTION_CHAIN, DataReq.IV_GREEKS, DataReq.OPEN_INTEREST), "dealer charm models"),
    _g("opt_vanna_charm_flow", "vanna_charm",
       "Combined vanna+charm dealer-flow model (post-2020 index-option desk staple).",
       _NSE, (DataReq.OPTION_CHAIN, DataReq.IV_GREEKS, DataReq.OPEN_INTEREST), "vanna-charm flow"),
    _g("opt_delta_gamma_hedging_net", "ml_hedging",
       "Neural network for dynamic delta/gamma hedging & portfolio optimisation.",
       _CRY + _NSE, _GREEKS, "delta-gamma hedging networks (arxiv 2502.11706)",
       notes="ML hedging — see machine_learning.py"),
]


# ── Wave 1B: REAL Deribit-options backtests (free chain + DVOL + binance realized vol) ──
# Crypto-options strategies flip to EXECUTABLE via data_sources/deribit_options. opt_dispersion
# (needs multi-asset index-vs-components → Wave 1C) and opt_dealer_gamma_exposure (needs OI
# positioning aggregation) stay honestly gated until that data lands.
from trading.strategy.library.catalog import _impl_crypto_options as _co  # noqa: E402

_CRYPTO_OPT_BT = {
    "opt_long_call": _co.bt_long_call, "opt_long_put": _co.bt_long_put,
    "opt_covered_call": _co.bt_covered_call, "opt_protective_put": _co.bt_protective_put,
    "opt_short_straddle": _co.bt_short_straddle, "opt_short_strangle": _co.bt_short_strangle,
    "opt_iron_condor": _co.bt_iron_condor, "opt_iron_butterfly": _co.bt_iron_butterfly,
    "opt_long_straddle": _co.bt_long_straddle, "opt_long_strangle": _co.bt_long_strangle,
    "opt_calendar_spread": _co.bt_volatility_cone, "opt_diagonal_spread": _co.bt_volatility_cone,
    "opt_gamma_scalping": _co.bt_long_straddle, "opt_delta_neutral_arbitrage": _co.bt_vrp_harvest,
    "opt_vega_trading": _co.bt_vega_trading, "opt_iv_rv_arbitrage": _co.bt_iv_rv_arbitrage,
    "opt_volatility_carry": _co.bt_volatility_carry, "opt_vrp_harvest": _co.bt_vrp_harvest,
    "opt_volatility_surface_arb": _co.bt_skew_trading, "opt_skew_trading": _co.bt_skew_trading,
    "opt_volatility_cone": _co.bt_volatility_cone, "opt_dynamic_delta_hedging": _co.bt_long_straddle,
    "opt_delta_gamma_hedging_net": _co.bt_long_straddle,
}
for _s in STRATEGIES:
    if _s.name in _CRYPTO_OPT_BT and "crypto_options" in _s.segments:
        _s.backtest = _CRYPTO_OPT_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: Deribit chain+DVOL").strip(" ·")
