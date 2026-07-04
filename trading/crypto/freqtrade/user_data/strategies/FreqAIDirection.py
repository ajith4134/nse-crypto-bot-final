"""FreqAIDirection — FreqAI directional ML strategy (Wave: crypto ML strategies → Freqtrade).

This single FreqAI strategy is the Freqtrade-native home for the library's ML-direction family
(ml_random_forest_direction / ml_xgboost_direction / ml_lightgbm_direction / ml_catboost_* …):
FreqAI trains a per-pair model on engineered OHLCV features and predicts the next-window return;
the MODEL is chosen at launch via `--freqaimodel` (LightGBMRegressor | XGBoostRegressor |
CatboostRegressor | ...), so all those library variants map onto one strategy + a model flag.

Run (needs `pip install datasieve` for the FreqAI pipeline):
    freqtrade trade --config config.json --strategy FreqAIDirection --freqaimodel LightGBMRegressor
The config must carry a `freqai` block — config_template.build_config(freqai=True) adds it.

Loaded by the Freqtrade process; freqtrade/pandas/numpy are its runtime deps.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame
from technical import qtpylib
from freqtrade.strategy import IStrategy


class FreqAIDirection(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = False                     # spot default; futures mode flips via config
    minimal_roi = {"0": 0.05}
    stoploss = -0.05
    process_only_new_candles = True
    startup_candle_count = 40
    # entries gated on the model's confidence in an UP move
    entry_threshold = 0.002               # predicted return must exceed this to enter
    use_exit_signal = True

    # ── FreqAI feature engineering ─────────────────────────────────────────────
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-rsi-period"] = qtpylib.rsi(dataframe["close"], period)
        dataframe["%-atr-period"] = (
            (dataframe["high"] - dataframe["low"]).rolling(period).mean() / dataframe["close"])
        dataframe["%-roc-period"] = dataframe["close"].pct_change(period)
        dataframe["%-relvol-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean())
        sma = dataframe["close"].rolling(period).mean()
        dataframe["%-close_over_sma-period"] = dataframe["close"] / sma - 1.0
        dataframe["%-std-period"] = dataframe["close"].pct_change().rolling(period).std()
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict,
                                         **kwargs) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_close"] = dataframe["close"]
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: dict,
                                     **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        # target = forward return over the FreqAI label horizon (regression)
        horizon = self.freqai_info["feature_parameters"]["label_period_candles"]
        dataframe["&-s_close"] = (
            dataframe["close"].shift(-horizon).rolling(horizon).mean()
            / dataframe["close"] - 1.0)
        return dataframe

    # ── prediction → indicators → entries/exits ────────────────────────────────
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return self.freqai.start(dataframe, metadata, self)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        pred, ok = df.get("&-s_close"), df.get("do_predict")
        if pred is None or ok is None:
            return df
        enter = (ok == 1) & (pred > self.entry_threshold)
        df.loc[enter, ["enter_long", "enter_tag"]] = (1, "freqai_up")
        if self.can_short:
            short = (ok == 1) & (pred < -self.entry_threshold)
            df.loc[short, ["enter_short", "enter_tag"]] = (1, "freqai_down")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        pred, ok = df.get("&-s_close"), df.get("do_predict")
        if pred is None or ok is None:
            return df
        df.loc[(ok == 1) & (pred < 0), "exit_long"] = 1
        if self.can_short:
            df.loc[(ok == 1) & (pred > 0), "exit_short"] = 1
        return df
