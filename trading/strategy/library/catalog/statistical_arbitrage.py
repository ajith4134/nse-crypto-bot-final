"""catalog/statistical_arbitrage.py — stat-arb / relative-value / cross-asset arbitrage.

These monetise *relationships between instruments*, so they need >1 price series, a futures
curve / basis, funding, or open interest — none of which a single-symbol OHLCV bar carries.
They are therefore DATA_GATED: full spec + OSS source + the exact data input that unlocks
them. The repo already has the pieces to feed several (ccxt multi-symbol + funding, OpenAlgo
NSE chains, advintel/arbitrage.py, advintel/liquidations.py) — wiring those in is the next
step and flips these to executable.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy
from trading.strategy.library.catalog import _impl_crypto_deriv as cd

_NSE = ("nse_cash", "nse_futures")
_CRY = ("crypto_spot", "crypto_futures")


def _g(name, category, family, logic, segments, data_req, oss, tf="varies", notes="",
       backtest=None):
    return LibraryStrategy(name=name, category=category, family=family, logic=logic,
                           segments=segments, timeframe=tf, data_req=tuple(data_req),
                           signal=None, backtest=backtest, oss_source=oss, notes=notes)


STRATEGIES = [
    # ── classic statistical arbitrage ──────────────────────────────────────────
    _g("statarb_pairs_trading", "statistical_arbitrage", "pairs",
       "Trade the mean-reverting spread of two cointegrated names (HDFC↔ICICI, BTC↔ETH).",
       _NSE + _CRY, [DataReq.MULTI_ASSET],
       "arnavkohli/statistical-arbitrage-pairs-trading; sap215/StatArbPairsTrading",
       notes="needs 2 aligned price series + cointegration/z-score of spread"),
    _g("statarb_cointegration", "statistical_arbitrage", "cointegration",
       "Engle-Granger / Johansen cointegration with dynamic hedge ratio (Kalman).",
       _NSE + _CRY, [DataReq.MULTI_ASSET],
       "je-suis-tm/quant-trading (cointegration); statsmodels",
       notes="needs multi-asset + Kalman-filtered hedge ratio"),
    _g("statarb_basket", "statistical_arbitrage", "basket",
       "Trade a name vs a weighted basket of correlated peers (residual reversion).",
       _NSE, [DataReq.MULTI_ASSET], "factor basket arb"),
    _g("statarb_etf_arbitrage", "statistical_arbitrage", "etf_arb",
       "ETF price vs its NAV/creation-basket; arb the premium/discount.",
       ("nse_cash",), [DataReq.MULTI_ASSET, DataReq.BASIS], "ETF arbitrage (Jane Street style)"),
    _g("statarb_index_arbitrage", "statistical_arbitrage", "index_arb",
       "Index futures vs the cash basket of constituents (program trading).",
       ("nse_futures",), [DataReq.MULTI_ASSET, DataReq.BASIS], "index arbitrage desks"),
    _g("statarb_index_basket_arb", "statistical_arbitrage", "index_basket",
       "Buy NIFTY50 components / short NIFTY future when premium is excessive.",
       ("nse_futures",), [DataReq.MULTI_ASSET, DataReq.BASIS],
       "index-basket arb (HFT/ETF MM)", notes="low return/trade, very high Sharpe, scalable"),
    _g("statarb_factor", "statistical_arbitrage", "factor_arb",
       "Long/short on residuals after neutralising common factors.",
       ("nse_cash",), [DataReq.MULTI_ASSET, DataReq.FUNDAMENTALS], "AQR factor arbitrage"),
    _g("statarb_correlation", "statistical_arbitrage", "correlation_arb",
       "Trade deviations in the realised correlation between two assets.",
       _NSE + _CRY, [DataReq.MULTI_ASSET], "correlation arbitrage"),
    _g("statarb_correlation_breakdown", "relative_value", "correlation_breakdown",
       "BankNifty↔Nifty corr drops 0.85→0.40 → trade convergence back to normal.",
       ("nse_futures",), [DataReq.MULTI_ASSET], "multi-asset/RV desks",
       notes="rolling correlation regime + convergence"),
    _g("statarb_leader_laggard", "statistical_arbitrage", "lead_lag",
       "Bank-Nifty leads → trade laggard constituents (Axis/Kotak/AU) on the lag.",
       ("nse_intraday", "nse_futures"), [DataReq.MULTI_ASSET], "leader-laggard models", tf="intraday"),
    _g("statarb_sector_rotation_intraday", "momentum", "sector_rotation",
       "If banking leaders (HDFC/ICICI/SBI) rise together → long Bank-Nifty future.",
       ("nse_intraday", "nse_futures"), [DataReq.MULTI_ASSET], "intraday sector rotation", tf="intraday"),
    _g("statarb_cross_sectional_momentum", "momentum", "cross_sectional",
       "Rank a universe by trailing return; long top decile / short bottom.",
       ("nse_cash", "crypto_spot"), [DataReq.MULTI_ASSET], "cross-sectional momentum"),
    _g("statarb_relative_strength_ranking", "momentum", "rs_ranking",
       "Relative-strength rank rotation across a universe (momentum rotation).",
       ("nse_cash", "crypto_spot"), [DataReq.MULTI_ASSET], "RS ranking / momentum rotation"),
    _g("statarb_long_short_market_neutral", "statistical_arbitrage", "market_neutral",
       "Beta-neutral long-short book (longs vs shorts sized to net ~0 beta).",
       _NSE + _CRY, [DataReq.MULTI_ASSET], "market-neutral L/S"),
    _g("statarb_cross_sectional_mean_reversion", "statistical_arbitrage", "cross_sectional_mr",
       "Short recent cross-sectional winners / long losers (universe MR).",
       ("nse_cash", "crypto_spot"), [DataReq.MULTI_ASSET], "cross-sectional mean reversion"),
    _g("statarb_dollar_neutral", "statistical_arbitrage", "dollar_neutral",
       "Equal long/short notional (dollar-neutral) residual portfolio.",
       ("nse_cash",), [DataReq.MULTI_ASSET], "dollar-neutral portfolio"),
    _g("statarb_beta_neutral", "statistical_arbitrage", "beta_neutral",
       "Hedge net beta to ~0 against the index (beta-neutral portfolio).",
       ("nse_cash", "nse_futures"), [DataReq.MULTI_ASSET], "beta-neutral portfolio"),
    _g("statarb_sector_neutral", "statistical_arbitrage", "sector_neutral",
       "Neutralise net exposure within each sector (sector-neutral portfolio).",
       ("nse_cash",), [DataReq.MULTI_ASSET, DataReq.FUNDAMENTALS], "sector-neutral portfolio"),
    _g("statarb_factor_neutral", "statistical_arbitrage", "factor_neutral",
       "Residualise common factor exposures; trade idiosyncratic alpha only.",
       ("nse_cash",), [DataReq.MULTI_ASSET, DataReq.FUNDAMENTALS], "factor-neutral portfolio"),

    # ── futures term-structure / basis (relative value) ─────────────────────────
    _g("rv_calendar_spread", "relative_value", "calendar_spread",
       "Long near-month / short far-month future on carry & roll-yield anomalies.",
       ("nse_futures", "crypto_futures", "mcx_commodities"),
       [DataReq.BASIS, DataReq.MULTI_TF], "calendar spread arbitrage",
       notes="REAL: ccxt basis term-structure (perp-vs-spot proxy)", backtest=cd.bt_calendar_spread),
    _g("rv_basis_trading", "relative_value", "basis",
       "Trade spot's deviation from futures fair value (cost-of-carry).",
       ("nse_futures", "crypto_futures", "mcx_commodities"), [DataReq.BASIS], "basis trading",
       notes="REAL: ccxt spot+perp basis fade", backtest=cd.bt_basis_trading),
    _g("rv_cash_and_carry", "relative_value", "cash_carry",
       "Long spot + short future to lock the basis (cash-and-carry arbitrage).",
       ("crypto_futures", "mcx_commodities"), [DataReq.BASIS], "cash-and-carry arb",
       notes="REAL: ccxt spot+perp basis lock", backtest=cd.bt_cash_carry),
    _g("rv_roll_yield_harvesting", "relative_value", "roll_yield",
       "Harvest roll yield along the futures curve (contango/backwardation carry).",
       ("crypto_futures", "mcx_commodities", "nse_futures"), [DataReq.BASIS, DataReq.MULTI_TF],
       "roll-yield harvesting", notes="REAL: ccxt funding/basis carry",
       backtest=cd.bt_roll_yield_harvesting),

    # ── crypto derivatives carry / arbitrage ────────────────────────────────────
    _g("cry_funding_rate_arbitrage", "relative_value", "funding_arb",
       "Long spot + short perpetual to harvest positive funding (delta-neutral).",
       ("crypto_futures",), [DataReq.FUNDING, DataReq.MULTI_ASSET],
       "50shadesofgwei/funding-rate-arbitrage; aoki-h-jp/funding-rate-arbitrage",
       notes="REAL: ccxt funding-rate history, delta-neutral carry P&L", backtest=cd.bt_funding_arb),
    _g("cry_basis_arbitrage", "relative_value", "basis_arb",
       "Trade the perp/quarterly premium against spot (spread monitor).",
       ("crypto_futures",), [DataReq.BASIS], "dennislwy/binance-spot-futures-arbitrage-spread-monitor",
       notes="REAL: ccxt spot+perp basis convergence", backtest=cd.bt_basis_arb),
    _g("cry_funding_momentum", "momentum", "funding_momentum",
       "Funding-rate sign/trend as a directional momentum signal on the perp.",
       ("crypto_futures",), [DataReq.FUNDING], "funding-rate momentum",
       notes="REAL: ccxt funding trend → perp direction", backtest=cd.bt_funding_momentum),

    # ── commodity spreads (relative value) ──────────────────────────────────────
    _g("cmd_crack_spread", "relative_value", "crack_spread",
       "Crude vs refined products (gasoline/diesel) refining-margin spread.",
       ("mcx_commodities",), [DataReq.MULTI_ASSET], "crack spread"),
    _g("cmd_spark_spread", "relative_value", "spark_spread",
       "Natural gas vs electricity generation-margin spread.",
       ("mcx_commodities",), [DataReq.MULTI_ASSET], "spark spread"),
    _g("cmd_crush_spread", "relative_value", "crush_spread",
       "Soybean vs soybean-oil + soybean-meal processing spread.",
       ("mcx_commodities",), [DataReq.MULTI_ASSET], "crush spread"),
    _g("cmd_gold_silver_ratio", "relative_value", "ratio",
       "Trade deviations in the gold/silver ratio (mean-reverting metal ratio).",
       ("mcx_commodities",), [DataReq.MULTI_ASSET], "gold-silver ratio"),
    _g("cmd_intermarket_arbitrage", "cross_asset", "intermarket",
       "Trade lead-lag/relationships across related commodity markets.",
       ("mcx_commodities",), [DataReq.MULTI_ASSET], "intermarket arbitrage"),
    _g("cmd_storage_arbitrage", "relative_value", "storage",
       "Inventory/storage-cost vs futures curve (contango carry).",
       ("mcx_commodities",), [DataReq.BASIS, DataReq.FUNDAMENTALS], "storage arbitrage"),
    _g("cmd_convenience_yield", "relative_value", "convenience_yield",
       "Trade convenience-yield distortions in the commodity term structure.",
       ("mcx_commodities",), [DataReq.BASIS], "convenience-yield arb"),

    # ── cross-venue / cross-chain arbitrage ─────────────────────────────────────
    _g("cross_exchange_arbitrage", "cross_asset", "cross_exchange",
       "Buy on one exchange / sell on another simultaneously (Binance↔Bybit, etc.).",
       ("crypto_spot", "crypto_futures"), [DataReq.MULTI_ASSET, DataReq.ORDERBOOK_L2],
       "hummingbot/hummingbot", notes="needs synchronised multi-venue books + low-latency exec"),
    _g("triangular_arbitrage", "cross_asset", "triangular",
       "Cycle USDT→BTC→ETH→USDT to capture cross-rate mispricing.",
       ("crypto_spot",), [DataReq.MULTI_ASSET, DataReq.ORDERBOOK_L2], "hummingbot/hummingbot"),
    _g("dex_cex_arbitrage", "cross_asset", "dex_cex",
       "Arb a DEX pool price against a CEX quote (Uniswap vs Binance).",
       ("crypto_spot",), [DataReq.MULTI_ASSET, DataReq.ORDERBOOK_L2], "hummingbot/hummingbot"),
    _g("cross_chain_arbitrage", "cross_asset", "cross_chain",
       "Arb the same asset across chains (ETH↔SOL, ARB↔Base, BSC↔ETH).",
       ("crypto_spot",), [DataReq.MULTI_ASSET], "topics/trading-bot-bsc-solana"),
]


# ── Wave 1C: REAL multi-asset crypto stat-arb backtests (free ccxt price panel) ──
# The crypto-applicable pure-multi_asset strategies flip to EXECUTABLE. Cross-exchange/triangular
# arb (need orderbook_l2 → Wave 3), commodity spreads + factor/sector (fundamentals/NSE → Wave 2)
# stay honestly gated until that data lands.
from trading.strategy.library.catalog import _impl_multi_asset as _ma  # noqa: E402

_CRYPTO_MA_BT = {
    "statarb_pairs_trading": _ma.bt_pairs_trading,
    "statarb_cointegration": _ma.bt_cointegration,
    "statarb_correlation": _ma.bt_correlation,
    "statarb_cross_sectional_momentum": _ma.bt_cross_sectional_momentum,
    "statarb_cross_sectional_mean_reversion": _ma.bt_cross_sectional_mean_reversion,
    "statarb_relative_strength_ranking": _ma.bt_relative_strength_ranking,
    "statarb_long_short_market_neutral": _ma.bt_long_short_market_neutral,
}
for _s in STRATEGIES:
    if _s.name in _CRYPTO_MA_BT and any("crypto" in seg for seg in _s.segments):
        _s.backtest = _CRYPTO_MA_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: ccxt multi-asset panel").strip(" ·")


# ── Wave 2: REAL NSE factor-neutral stat-arb (yfinance) ──
from trading.strategy.library.catalog import _impl_nse_factor as _nf2  # noqa: E402
_SA_FACTOR_BT = {"statarb_factor": _nf2.bt_statarb_factor,
                 "statarb_sector_neutral": _nf2.bt_factor_multifactor,
                 "statarb_factor_neutral": _nf2.bt_factor_multifactor}
for _s in STRATEGIES:
    if _s.name in _SA_FACTOR_BT:
        _s.backtest = _SA_FACTOR_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: yfinance factor-neutral").strip(" ·")


# ── Wave 2: REAL NSE multi-asset stat-arb (free yfinance large-cap panel) ──
from trading.strategy.library.catalog import _impl_multi_asset as _ma3  # noqa: E402
_NSE_MA_BT = {"statarb_basket": _ma3.bt_nse_basket,
              "statarb_correlation_breakdown": _ma3.bt_nse_correlation_breakdown,
              "statarb_leader_laggard": _ma3.bt_nse_leader_laggard,
              "statarb_sector_rotation_intraday": _ma3.bt_nse_sector_rotation,
              "statarb_dollar_neutral": _ma3.bt_nse_dollar_neutral,
              "statarb_beta_neutral": _ma3.bt_nse_beta_neutral}
for _s in STRATEGIES:
    if _s.name in _NSE_MA_BT:
        _s.backtest = _NSE_MA_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: yfinance NSE panel").strip(" ·")
