"""MlBridgeStrategy — minimal placeholder Freqtrade strategy (T-split B).

A VALID, runnable IStrategy that emits no automatic entries by default, so a fresh Freqtrade
bot stands up cleanly in dry-run and waits for orders driven via the REST API
(`CryptoEngineClient.place_order` → /forceenter). The real signal logic arrives in Phase C, when
the 239-strategy library is translated into Freqtrade strategies by an adapter.

This file is loaded by the Freqtrade process (not by this repo's package), so importing
`freqtrade`/`pandas` here is fine — those are Freqtrade's own runtime deps.
"""
from __future__ import annotations

from pandas import DataFrame
from freqtrade.strategy import IStrategy


class MlBridgeStrategy(IStrategy):
    """No-auto-entry baseline. Exits are managed by stoploss + REST /forceexit."""

    INTERFACE_VERSION = 3
    timeframe = "5m"

    # Wide, permissive risk frame — real per-trade exits come from the library adapter (Phase C).
    minimal_roi = {"0": 0.10}        # take 10% if it ever gets there
    stoploss = -0.10                 # 10% hard stop (placeholder)
    # MARKET orders (owner's preference): guaranteed immediate fill on entry AND exit — the brain
    # already picks the entry timing, so it wants the fill now, not a resting limit that may miss.
    # /forceenter passes order_type=market too; this keeps exits + stoploss consistent.
    order_types = {"entry": "market", "exit": "market", "stoploss": "market",
                   "stoploss_on_exchange": False}
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count = 30
    can_short = True                 # futures: allow SHORTs so the brain can trade down-movers
                                     # (most account-first movers are falling — long-only skipped them)

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs):
        """Operator-set leverage from config (futures only); clamp to the exchange max."""
        lev = float(self.config.get("ml_leverage", 1.0) or 1.0)
        return max(1.0, min(lev, max_leverage))

    def informative_pairs(self):
        """Make extra timeframes available to the LIVE chart (/pair_candles) for every whitelist pair.

        GATED OFF by default: with a 300-pair VolumePairList this loads 300×N extra dataframes every
        loop (network + rate-limit heavy) and can slow live trading. The dashboard chart already falls
        back to /pair_history (disk) for non-strategy timeframes, so this is rarely needed. Enable by
        setting "ml_chart_informatives": ["15m","1h","4h"] (or true → a sane default set) in config.json.
        """
        cfg = self.config.get("ml_chart_informatives")
        if not cfg:
            return []
        tfs = cfg if isinstance(cfg, list) else ["15m", "1h", "4h"]
        tfs = [tf for tf in tfs if tf and tf != self.timeframe]
        try:
            pairs = self.dp.current_whitelist()
        except Exception:
            return []
        return [(pair, tf) for pair in pairs for tf in tfs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No automatic entries — entries come via REST /forceenter for now.
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
