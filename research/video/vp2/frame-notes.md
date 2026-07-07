# vp2 (videoplayback (2).mp4, 19:52) — frame observations (pre-transcript)

Different channel from vp0/vp1: "CodeTrading"-style coding tutorial (VS Code, path
F:\CodeTrading\Code_trading_2025\Videos\09_A_Reinforcement_Trading_SingleBar\Code).
Title card: **"Reinforcement Learning Strategy"** — RL (PPO, stable-baselines3) trading
agent on EURUSD hourly (H1) forex data, Python. "<CODE> download link in the description".

## RL concept slides [00:40–02:20]
- Agent → Action → Environment → Reward → back to Agent loop over a candlestick chart.
- **Policy**: the agent's strategy or mapping from states to actions.
- **model-free RL**: the agent learns directly from experience in the environment
  (dog-training cartoon analogy).

## Project structure (VS Code explorer)
- `data/` — EURUSD_Candlestick_1_Hour_BID_01.07.2020-15.07.2023.csv (TRAIN)
  and test_EURUSD_Candlestick_1_Hour_BID_20.02.2023-22.02.2025.csv (TEST, out-of-sample)
- `indicators.py` — load_and_preprocess_data(csv_path): read csv (GMT time, OHLC, Volume),
  sort by date, add pandas_ta indicators: rsi_14 (RSI len 14), ma_20 (SMA 20), ma_50
  (SMA 50), atr (ATR 14), ma_20_slope = ma_20.diff(); dropna. Comment: "could add more
  features: slopes, candlestick patterns, etc."
- `trading_env.py` — class **ForexTradingEnv(gym.Env)**: "custom trading environment for
  EUR/USD that at each step: observes a window of data (OHLC + indicators); takes an
  action: choose among NO TRADE or combos of (direction, SL, TP); computes reward based
  on PnL from that decision." __init__(df, window_size=30, sl_options=None,
  tp_options=None); defaults sl_options=[60,90,120] pips, tp_options=[60,90,120]
  (example comment [10,20,30]); action space = discrete: action 0 = No-Trade, then for
  direction in [0=short, 1=long] × each (sl, tp) combo → action_map list; total actions
  = 1 + 2*len(sl)*len(tp) (=19); observation = 2D window (window_size × num_features,
  num_features = df.shape[1]).
- `train_agent.py` — df=load_and_preprocess_data(train csv) → env=ForexTradingEnv(df,
  window_size=30, sl_options=[30,60,80], tp_options=[30,60,80]) → DummyVecEnv →
  model=PPO("MlpPolicy", vec_env, verbose=1, tensorboard_log="./tensorboard_log/") →
  model.learn(total_timesteps=10000..50000) → model.save("model_eurusd") → evaluation
  loop: model.predict(obs, deterministic=True), step, current_equity =
  vec_env.get_attr("equity")[0], equity_curve.append → plot "Equity Curve during
  Evaluation".
- `test_agent.py` — load TEST csv (or same train csv for sanity), rebuild the SAME env
  (must match window_size, sl_options, tp_options), DummyVecEnv, PPO.load("model_eurusd"),
  predict deterministic, log equity_curve + trade_history (trade_id…) → save
  trade_history_output.csv → plot "Equity Curve — Single-Bar RL Environment Test".
- `model_eurusd.zip`, `tensorboard_log/`, `trade_history_output.csv` artifacts.

## Results shown
- TRAIN-data evaluation: near-straight-line equity 10,000 → 32,000–35,000 over ~17,500
  steps (in-sample; looks amazing).
- TEST-data (out-of-sample 2023–2025): equity oscillates 9,000–10,200, spikes at the end,
  ends ~flat/negative — classic overfitting demonstration; PPO metrics table (clip_range
  0.2, explained_variance ≈ −0.0008, learning_rate 0.0003, n_updates 240, value_loss
  2.27e+03) and a UserWarning about OpenAI Gym→Gymnasium compatibility visible.

## Concepts to carry into the plan
1. Gym-style trading env where the ACTION is a full trade spec (direction, SL, TP) or
   no-trade; reward = PnL of that decision; single-bar decision framing.
2. Discretized SL/TP menu in pips as the action space (risk parameters are LEARNED, not
   fixed).
3. Strict train/test split with identical env params; equity-curve + trade-history CSV as
   the evaluation artifacts; in-sample vs out-of-sample contrast (overfitting caveat).
4. TensorBoard for training telemetry.
