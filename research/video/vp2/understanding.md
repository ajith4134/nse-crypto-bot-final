# vp2 — "Reinforcement Learning Trading Strategy (PPO, EURUSD H1)" (videoplayback (2).mp4, 19:52)

## One-paragraph summary
A CodeTrading-style educational video (different creator from vp0/vp1; code download in
description) that builds a **model-free RL (PPO / stable-baselines3) trading agent** on
EURUSD hourly candles in 4 Python files: `indicators.py` (pandas_ta features),
`trading_env.py` (custom `ForexTradingEnv(gym.Env)` whose discrete action space is
NO-TRADE or a full trade spec (direction × SL × TP menu in pips) and whose reward is the
trade's PnL), `train_agent.py` (PPO MlpPolicy, 10k–50k timesteps, TensorBoard, save
model), `test_agent.py` (reload model, identical env params, out-of-sample 2023–2025 data,
equity curve + trade_history_output.csv). Training equity looks great (10k→~32k) but
out-of-sample is flat/negative — an explicit overfitting lesson with concrete improvement
levers (more/custom indicators, denser SL/TP menu, fewer timesteps, different algorithms).

## Every distinct idea (timestamp + frame refs)
1. **RL-as-trader framing** [00:00–02:22, f_0100–f_0140]: agent/environment/action/
   reward/policy; model-free = learn directly from trial-and-error experience (dog-training
   analogy); agent maximizes coded reward; "learns like a human trader would".
2. **4-file project layout** [02:39–03:35, f_0240]: data/ (train CSV 2020–07.2023, test
   CSV 02.2023–02.2025, EURUSD H1 BID), indicators.py, trading_env.py, train_agent.py,
   test_agent.py + model_eurusd.zip + tensorboard_log/ + trade_history_output.csv.
3. **Feature pipeline** [03:35–04:50, f_0340]: `load_and_preprocess_data(csv)` — read CSV
   (GMT time, OHLCV), sort index, add rsi_14, ma_20, ma_50, atr(14), ma_20_slope =
   ma_20.diff() (he notes it's a naive diff, not a regression slope), dropna. Explicit
   extension point for custom indicators.
4. **Environment design** [04:50–10:25, f_0240/f_0500–f_0610]: `ForexTradingEnv(gym.Env)`:
   - observation = 2D numpy window (window_size=30 rows × ALL df features incl.
     indicators), with edge-case handling at data start;
   - action space = Discrete(1 + 2×len(sl_options)×len(tp_options)): action 0 = skip
     candle; else (direction short/long, SL, TP) tuple from a pip menu (60/90/120 default;
     train used 30/60/80); menu chosen arbitrarily; bigger menus = more compute;
   - reward = PnL × 10,000 (pip-adjusted), negative for losses, proportional to size;
   - **conservative ambiguity rule**: if one candle touches both SL and TP (no tick data,
     unknowable order), count it as a LOSS — "so we don't cheat our way around";
   - internal state: current_step, equity $10,000 start, slippage 0, positions list,
     equity-curve log, last-trade info; reset() restarts backtest; render() plots equity.
5. **Training** [10:25–14:49, f_1740]: PPO("MlpPolicy", DummyVecEnv, verbose=1,
   tensorboard_log) — PPO chosen as well-suited for noisy continuous market data;
   model.learn(50,000 timesteps), model.save; then deterministic evaluation loop
   (model.predict(obs, deterministic=True)) collecting equity via
   vec_env.get_attr("equity") and plotting the curve. Training equity rises ~linearly
   10k→32k (f_1423) — "the agent learned to follow positive-reward actions".
6. **Honest out-of-sample test** [14:49–16:09, f_1510–f_1555]: test_agent.py loads UNSEEN
   2023–2025 data, must recreate the env with IDENTICAL window/SL/TP params, loads the
   saved model, no further fitting; result: oscillating flat-to-down equity (f_1555) —
   "not what we expected… this is on new and unseen data".
7. **Improvement levers** [16:09–18:23]: (a) richer/custom indicators that actually carry
   signal; (b) denser SL/TP menu (e.g. 5-pip increments 30→100); (c) reduce training
   timesteps to fight overfitting — retraining at 10,000 steps instead of 50,000 gave a
   partly-positive out-of-sample equity [17:32–18:23, f_1823]; (d) try algorithms other
   than PPO for education.
8. **Closing caveat** [18:57–19:30]: RL is powerful for trading but hard to fine-tune —
   market data is mostly noise and the model struggles to find the true signal.

## Open questions
- None; self-contained tutorial. (The step() internals scrolled past quickly, but the
  docstring + narration fully specify behavior.)
