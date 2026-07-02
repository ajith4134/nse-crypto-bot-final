"""catalog/market_making.py — liquidity-provision / market-making family (data-gated).

Earn the bid-ask spread while controlling inventory. Every MM model needs the order book
(L2 depth, queue) and ideally tick fills — not in a candle feed — so all are DATA_GATED with
their canonical OSS/model source. This is the highest-Sharpe institutional family (Jane
Street/Optiver/IMC), included for completeness and ready to wire to an L2 feed + the repo's
hftbacktest-style simulator.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy

_CRY = ("crypto_spot", "crypto_futures")
_L2 = (DataReq.ORDERBOOK_L2,)
_L2T = (DataReq.ORDERBOOK_L2, DataReq.TICKS)


def _g(name, family, logic, segments, data_req, oss, notes=""):
    return LibraryStrategy(name=name, category="market_making", family=family, logic=logic,
                           segments=segments, timeframe="ms–minutes", data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes=notes)


STRATEGIES = [
    _g("mm_passive_bid_ask", "passive",
       "Quote symmetric passive bid/ask around mid; capture the spread on fills.",
       _CRY, _L2, "Adamant-im/adamant-tradebot", notes="baseline two-sided quoting"),
    _g("mm_inventory_based", "inventory",
       "Skew quotes by current inventory to mean-revert position toward flat.",
       _CRY, _L2, "nkaz001/hftbacktest", notes="inventory skewing"),
    _g("mm_avellaneda_stoikov", "avellaneda_stoikov",
       "Avellaneda-Stoikov: reservation price + optimal spread from inventory, vol, risk-aversion.",
       _CRY + ("nse_options",), _L2,
       "fedecaccia/avellaneda-stoikov; Jungle-Sven/avellaneda_stoikov_mm; nkaz001/hftbacktest",
       notes="the canonical optimal-MM model"),
    _g("mm_gueant_lehalle", "gueant_lehalle",
       "Guéant-Lehalle-Fernandez-Tapia closed-form multi-asset MM with inventory limits.",
       _CRY + ("nse_options",), _L2, "Guéant-Lehalle-Fernandez-Tapia (arxiv 1907.12433)"),
    _g("mm_dynamic_spread", "dynamic_spread",
       "Widen/tighten quoted spread with realised volatility & book pressure.",
       _CRY, _L2, "dynamic spread adjustment"),
    _g("mm_microprice", "microprice",
       "Quote around the imbalance-weighted microprice rather than the mid.",
       _CRY, _L2, "Stoikov microprice; nkaz001/hftbacktest"),
    _g("mm_fill_probability", "fill_prob",
       "Model fill probability vs queue position to choose quote depth.",
       _CRY, _L2T, "fill-probability modelling"),
    _g("mm_delta_neutral", "delta_neutral",
       "Two-sided option/perp quoting kept delta-neutral by hedging the underlying.",
       ("nse_options", "crypto_options", "crypto_futures"), _L2,
       "delta-neutral market making"),
    _g("mm_options", "options_mm",
       "Quote an options surface; manage greeks (delta/gamma/vega) inventory.",
       ("nse_options", "crypto_options"), (DataReq.ORDERBOOK_L2, DataReq.IV_GREEKS, DataReq.OPTION_CHAIN),
       "u3ffrzi/options-market-maker-algorithm", notes="surface quoting + greek inventory"),
    _g("mm_reinforcement_learning", "rl_mm",
       "RL agent (PPO/SAC/A2C/DQN) learns quoting/skew policy from the book.",
       _CRY, _L2T, "ESkripichnikov/market-making", notes="RL market making"),
    _g("mm_stochastic_vol_inventory", "stoch_vol_inventory",
       "Stochastic-volatility inventory model for option MM (vol-aware reservation price).",
       ("crypto_options", "nse_options"), (DataReq.ORDERBOOK_L2, DataReq.IV_GREEKS),
       "stochastic-vol inventory models"),
]


# ── Wave 3: REAL market-making backtests (Avellaneda–Stoikov inventory sim on real prices).
# RL / options / IV-inventory / fill-probability MM stay gated (ticks/chain/RL → forward/GPU).
from trading.strategy.library.catalog import _impl_orderflow as _mmb  # noqa: E402
_MM_BT = {"mm_passive_bid_ask": _mmb.bt_passive_bid_ask, "mm_inventory_based": _mmb.bt_inventory_based,
          "mm_avellaneda_stoikov": _mmb.bt_avellaneda_stoikov, "mm_gueant_lehalle": _mmb.bt_gueant_lehalle,
          "mm_dynamic_spread": _mmb.bt_dynamic_spread, "mm_microprice": _mmb.bt_microprice,
          "mm_delta_neutral": _mmb.bt_inventory_based}
for _s in STRATEGIES:
    if _s.name in _MM_BT and any('crypto' in seg for seg in _s.segments):
        _s.backtest = _MM_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: A-S inventory MM sim").strip(" ·")
