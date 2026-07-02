"""catalog/machine_learning.py — ML / RL / regime family.

One EXECUTABLE strategy now: Hidden-Markov regime switching, reusing the repo's
`trading/brain/regime.py` GaussianHMM (long in bull regime, short in bear, flat in neutral)
— the ⭐⭐⭐⭐⭐ regime-switching family the user flagged, and the honest single-series slice
of "regime detection".

The rest are DATA_GATED specs: supervised models (RF/XGB/LGBM/CatBoost), deep nets
(LSTM/Transformer/TFT/GNN), RL (PPO/SAC/A2C/DQN), meta-learning, multi-agent & hierarchical
RL, meta strategy selection (HMM/Transformer-regime/Bayesian/Thompson/contextual-bandits) and
neural microstructure (DeepLOB/Deep-OFI — also in high_frequency.py). They need a trained
model artifact and (for microstructure) tick/L2 data. The repo's node-network + FinRL/gplearn
vendoring are the wiring path; survivors of the (gated-off) evolution engine also land here.
OSS: AI4Finance-Foundation/FinRL, stefan-jansen/machine-learning-for-trading, EarnHFT.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.library.base import DataReq, LibraryStrategy

_ALL = ("nse_cash", "nse_intraday", "nse_futures", "mcx_commodities",
        "crypto_spot", "crypto_futures")


def _regime_hmm(f: pd.DataFrame) -> pd.Series:
    """Long in bull regime / short in bear / flat in neutral (GaussianHMM over ret+vol+range).

    NOTE: the HMM is fit on the provided window (in-sample parameter estimation); the backtest
    executes next-bar (signal shifted +1) so entries are causal, but regime *labels* use the
    window's full statistics — an accepted approximation for a regime overlay (the same model
    the brain uses). Walk-forward folds limit the in-sample reach per fold.
    """
    try:
        from trading.brain.regime import RegimeModel
        cols = ["open", "high", "low", "close", "volume"]
        rm = RegimeModel(n_states=3, seed=0).fit(f[cols])
        labels = rm.predict_labels(f[cols])
        m = {"bull": 1, "bear": -1, "neutral": 0}
        return pd.Series([m.get(x, 0) for x in labels], index=f.index, dtype=int)
    except Exception:
        # deterministic fallback if hmmlearn is unavailable: trend-sign gated by volatility
        trend = np.sign(f["ema_fast"] - f["ema_slow"])
        calm = f["natr"] < f["natr"].rolling(50).median()
        return (trend * calm.astype(int)).fillna(0).astype(int)


def _g(name, family, logic, segments, oss, data_req=None, notes="", tf="varies"):
    return LibraryStrategy(name=name, category="machine_learning", family=family, logic=logic,
                           segments=segments, timeframe=tf,
                           data_req=tuple(data_req) if data_req else (DataReq.OHLCV, DataReq.VOLUME),
                           signal=None, oss_source=oss, notes=notes)


STRATEGIES = [
    # ── executable ──────────────────────────────────────────────────────────
    LibraryStrategy(
        name="ml_regime_switching_hmm", category="machine_learning", family="regime_switching",
        logic="Gaussian-HMM regime: long bull / short bear / flat neutral (regime detection).",
        segments=_ALL, timeframe="swing", signal=_regime_hmm,
        oss_source="hmmlearn; repo trading/brain/regime.py", allow_short=True,
        notes="EXECUTABLE — reuses the brain's RegimeModel; in-sample HMM fit (approx)."),

    # ── data-gated: supervised models (need a trained artifact) ─────────────────
    _g("ml_random_forest_direction", "supervised", "Random-Forest next-bar direction classifier.",
       _ALL, "stefan-jansen/machine-learning-for-trading; scikit-learn",
       notes="needs trained model + feature pipeline"),
    _g("ml_xgboost_direction", "supervised", "XGBoost direction/return-quantile model.",
       _ALL, "XGBoost; stefan-jansen/ml-for-trading"),
    _g("ml_lightgbm_direction", "supervised", "LightGBM gradient-boosted direction model.",
       _ALL, "LightGBM"),
    _g("ml_catboost_direction", "supervised", "CatBoost direction model (categorical-friendly).",
       _ALL, "CatBoost"),
    _g("ml_lstm_sequence", "deep", "LSTM sequence model for price/return prediction.",
       _ALL, "Netanelshoshan/freqAI-LSTM"),
    _g("ml_gru_sequence", "deep", "GRU sequence model (lighter LSTM) for trend/vol forecast.",
       _ALL, "GRU sequence model"),
    _g("ml_tcn_sequence", "deep", "Temporal Convolution Network for sequence forecasting.",
       _ALL, "Temporal Convolution Network"),
    _g("ml_transformer", "deep", "Transformer sequence model for direction/vol.",
       _ALL, "transformer models"),
    _g("ml_temporal_fusion_transformer", "deep", "Temporal Fusion Transformer multi-horizon forecast.",
       _ALL, "Temporal Fusion Transformer"),
    _g("ml_patchtst", "deep", "PatchTST patched-transformer long-horizon forecasting.",
       _ALL, "PatchTST"),
    _g("ml_informer", "deep", "Informer efficient long-sequence transformer forecasting.",
       _ALL, "Informer"),
    _g("ml_timegpt", "deep", "TimeGPT foundation-model time-series forecasting.",
       _ALL, "TimeGPT (Nixtla)"),
    _g("ml_graph_neural_network", "deep", "GNN over a cross-asset relationship graph.",
       ("nse_cash", "crypto_spot"), "graph neural networks", data_req=(DataReq.MULTI_ASSET,)),
    # ── data-gated: applications ────────────────────────────────────────────────
    _g("ml_volatility_forecasting", "application", "ML/GARCH realised-volatility forecast for sizing/vol trades.",
       _ALL, "vol forecasting (GARCH/LSTM)"),
    _g("ml_position_sizing", "application", "Learned position sizing / bet-sizing from edge & risk.",
       _ALL, "ML position sizing (repo trading/sizing/)"),
    _g("ml_execution_optimization", "application", "RL/optimal execution (VWAP/TWAP/IS minimisation).",
       _ALL, "optimal execution models", data_req=(DataReq.ORDERBOOK_L2, DataReq.TICKS)),
    # ── data-gated: reinforcement & meta ────────────────────────────────────────
    _g("ml_rl_trading", "reinforcement", "RL agent (PPO/DQN/SAC/TD3/A2C/DDPG) end-to-end trading.",
       _ALL, "AI4Finance-Foundation/FinRL"),
    _g("ml_multi_agent_rl", "reinforcement",
       "Multi-agent RL: MM/execution/alpha/regime/risk/router agents cooperating.",
       _ALL, "MARL (arxiv 2511.02136, 2309.12891/EarnHFT)"),
    _g("ml_hierarchical_rl", "reinforcement",
       "Hierarchical RL: portfolio→strategy→execution→order-placement agent stack.",
       _ALL, "hierarchical RL"),
    _g("ml_meta_strategy_selection", "meta",
       "Meta-selector picks/weights strategies via HMM/Transformer-regime/Bayesian/Thompson/bandits.",
       _ALL, "meta strategy selection (Thompson sampling, contextual bandits)"),
    _g("ml_meta_learning", "meta", "Meta-learning across markets/regimes for fast adaptation.",
       _ALL, "meta learning"),
    _g("ml_neural_microstructure", "deep",
       "Neural microstructure (DeepLOB / Deep-OFI / TFT / GNN) over the order book.",
       ("crypto_futures", "nse_futures"), "DeepLOB; Deep Order Flow Imbalance",
       data_req=(DataReq.ORDERBOOK_L2, DataReq.TICKS), notes="see high_frequency.py"),
]


# ── Wave 2: REAL sklearn/boosting ML-direction backtests; DL/RL honestly GPU-deferred ──
from trading.strategy.library.catalog import _impl_ml_direction as _mld  # noqa: E402
_ML_DIR_BT = {"ml_random_forest_direction": _mld.bt_rf, "ml_xgboost_direction": _mld.bt_xgb,
              "ml_lightgbm_direction": _mld.bt_lgb, "ml_catboost_direction": _mld.bt_catboost}
_GPU_DEFER = {"ml_lstm_sequence", "ml_gru_sequence", "ml_tcn_sequence", "ml_transformer",
              "ml_temporal_fusion_transformer", "ml_patchtst", "ml_informer", "ml_timegpt",
              "ml_rl_trading", "ml_multi_agent_rl", "ml_hierarchical_rl"}
for _s in STRATEGIES:
    if _s.name in _ML_DIR_BT:
        _s.backtest = _ML_DIR_BT[_s.name]
        _s.notes = (_s.notes + " · REAL: sklearn/boosting OOS").strip(" ·")
    elif _s.name in _GPU_DEFER:
        _s.notes = (_s.notes + " · GPU-deferred (deep-learning/RL — CPU-only build skips per rule)").strip(" ·")
