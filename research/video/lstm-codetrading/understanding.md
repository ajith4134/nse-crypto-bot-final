# Understanding — "Recurrent Neural Networks LSTM Price Movement Predictions For Trading Algorithms" (CodeTrading, ~15 min)

Source: /home/karan18190164/research/video/lstm-codetrading/ (transcript.md + 80 frames).

## Summary

The video builds, in a single Jupyter notebook, a Keras/TensorFlow LSTM regressor that predicts the **next day's closing price** of the Russell 1000 index (`^RUI`, yfinance daily data 2012-03-11 → 2022-07-10). Features are OHL + Adj Close plus four pandas_ta indicators (RSI-15 and EMAs of length 20/100/150); three candidate targets are constructed (signed open→next-close distance, its 1/0 classification, and next-day Adj Close), with the regression target `TargetNextClose` used. All 11 columns are MinMax-scaled to [0,1] together, then a sliding window of `backcandles` (10, later 30) days over the first 8 feature columns forms a 3-D input tensor X of shape (2437, backcandles, 8) with y = the scaled last column reshaped to (n,1). After an 80/20 chronological split, a functional-API model Input(backcandles,8) → LSTM(150) → Dense(1) → Activation('linear') is trained with Adam/MSE, batch_size=15, epochs=30, shuffle=True, validation_split≈0.1. Evaluation is purely visual: y_pred vs y_test printed for 10 rows and plotted; predictions track the test curve closely (with a visible one-step lag), which the author flags as deceptive — the model "shouldn't be used as-is," with a follow-up video promised on its failures.

## REQUIREMENTS

Data & features

- **REQ-LSTM-01** [02:32–03:02, f_0232_004] Imports/stack: `numpy as np`, `matplotlib.pyplot as plt`, `pandas as pd`, `yfinance as yf`, `pandas_ta as ta`. Data acquisition: `data = yf.download(tickers='^RUI', start='2012-03-11', end='2022-07-10')` — Russell 1000 index, ~10 years, **daily timeframe** (chosen explicitly because it is "less noisy for our algorithm" [03:04]). Applicable to stocks or crypto [00:05].
- **REQ-LSTM-02** [03:09–03:21, f_0320_021] Raw DataFrame: Date index + Open, High, Low, Close, Adj Close, Volume. Volume is all zeros for ^RUI → treated as containing no valuable data and dropped later.
- **REQ-LSTM-03** [03:21–03:50, f_0330_022, f_1350_084] Technical indicators added via pandas_ta on Close:
  ```python
  data['RSI'] = ta.rsi(data.Close, length=15)
  data['EMAF'] = ta.ema(data.Close, length=20)    # fast
  data['EMAM'] = ta.ema(data.Close, length=100)   # medium
  data['EMAS'] = ta.ema(data.Close, length=150)   # slow
  ```
  (Frames clearly show `length=15` for RSI; the narration says "16" — trust the code.) Parameters and indicator set are explicitly meant to be user-tunable [03:45–03:56].
- **REQ-LSTM-04** [03:56–04:31, f_0400_025..f_0430_028] Three target constructions:
  ```python
  data['Target'] = data['Adj Close'] - data.Open      # distance current open → close
  data['Target'] = data['Target'].shift(-1)           # ...of the NEXT candle
  data['TargetClass'] = [1 if data.Target[i]>0 else 0 for i in range(len(data))]  # up/down classification option
  data['TargetNextClose'] = data['Adj Close'].shift(-1)  # regression target USED in the video
  ```
  A commented-out alternative classification block also exists [05:56, f_0610_038]: `#y = [1 if data.Open[i]>data.Close[i] else 0 ...]`, `#yi = [data.Open[i]-data.Close[i] ...]`. The video uses only `TargetNextClose` (predict tomorrow's closing price [00:56]).
- **REQ-LSTM-05** [04:39–04:53, f_0440_029, f_0450_030] Cleaning:
  ```python
  data.dropna(inplace=True)
  data.reset_index(inplace=True)
  data.drop(['Volume', 'Close', 'Date'], axis=1, inplace=True)
  ```
  Close is dropped (Adj Close kept); Date/Volume dropped. Resulting columns [04:53–05:12, f_0500_031, f_0510_032]: `Open, High, Low, Adj Close, RSI, EMAF, EMAM, EMAS, Target, TargetClass, TargetNextClose` (11 columns). Sanity check shown [05:18–05:31, f_0520_033]: row-0 TargetNextClose 787.179993 equals row-1 Adj Close.
- **REQ-LSTM-06** [f_0450_030] Materialize model matrix: `data_set = data.iloc[:, 0:11]  #.values` and `pd.set_option('display.max_columns', None)`; inspect with `data_set.head(20)`.

Preprocessing

- **REQ-LSTM-07** [05:31–06:15, f_0540_035] Scale ALL 11 columns together to [0,1] because a neural network is used:
  ```python
  from sklearn.preprocessing import MinMaxScaler
  sc = MinMaxScaler(feature_range=(0,1))
  data_set_scaled = sc.fit_transform(data_set)   # returns 2-D NumPy array; column order must be tracked manually [06:15–06:28]
  ```
- **REQ-LSTM-08** [06:31–07:11] Input/target column split: the **first 8 columns** (Open, High, Low, Adj Close, RSI, EMAF, EMAM, EMAS) are the model inputs; the last 3 columns (Target, TargetClass, TargetNextClose) are excluded from input, and the **last column (index -1, TargetNextClose)** is the prediction target. ("Choose -1 for last column, classification else -2..." comment [f_0910_056] indicates -2 would select TargetClass instead.)
- **REQ-LSTM-09** [07:13–07:41, 08:50, f_0850_054, f_1300_079, f_1310_080] Lookback hyperparameter `backcandles` = number of past days fed to the model. Video starts conceptually with 4 [01:23], mentions trying 6 [02:01], codes **10**, then re-runs with **30** [12:55–13:22, f_1310_080/f_1320_081 show `backcandles = 30`]. Requirement: lookback must be an easily-changed experiment knob.
- **REQ-LSTM-10** [08:50, f_0850_054] Sliding-window tensor construction (exact code):
  ```python
  X = []
  backcandles = 10   # later 30
  print(data_set_scaled.shape[0])
  for j in range(8):                     # 8 feature columns; 2 (3) trailing cols are target not X
      X.append([])
      for i in range(backcandles, data_set_scaled.shape[0]):
          X[j].append(data_set_scaled[i-backcandles:i, j])
  X = np.moveaxis(X, [0], [2])           # move feature axis from 0 to position 2
  # Choose -1 for last column, classification else -2...
  X, yi = np.array(X), np.array(data_set_scaled[backcandles:, -1])
  y = np.reshape(yi, (len(yi), 1))
  ```
  Also shown commented: a one-line list-comprehension equivalent [08:15, f_0940_059]: `#X = np.array([data_set_scaled[i-backcandles:i, :4].copy() for i in range(backcan...)` (kept for coding-style reference only, truncated in frame).
- **REQ-LSTM-11** [08:32–09:57, f_0910_056, f_0920_057, f_0930_058, f_0940_059] Shape verification is mandatory ("if you feed the LSTM model with the wrong dimensions it's not going to work" [09:10]). Printed shapes with backcandles=10: total scaled rows 2447; `X.shape == (2437, 10, 8)` (samples, backcandles, features); `y.shape == (2437, 1)` — y must be 2-D with one value per element [09:42–09:47]. Rows = 2447 − backcandles.
- **REQ-LSTM-12** [09:57–10:10, f_1000_061, f_1010_062] Chronological (non-shuffled) 80/20 train/test split:
  ```python
  splitlimit = int(len(X)*0.8)
  X_train, X_test = X[:splitlimit], X[splitlimit:]
  y_train, y_test = y[:splitlimit], y[splitlimit:]
  ```
  With backcandles=30: splitlimit=1933; shapes (1933,30,8), (484,30,8), (1933,1), (484,1) [f_1000_061].

Model & training

- **REQ-LSTM-13** [10:10–10:29, f_1020_063] Framework imports (some acknowledged redundant):
  `from keras.models import Sequential, Model`; `from keras.layers import LSTM, Dropout, Dense, TimeDistributed, Input, Activation, concatenate`; `import tensorflow as tf; import keras; from keras import optimizers; from keras.callbacks import History; import numpy as np`. Optional reproducibility seeds present but commented: `#tf.random.set_seed(20)`, `#np.random.seed(10)`.
- **REQ-LSTM-14** [10:29–11:16, f_1030_064..f_1110_068] Model architecture (Keras functional API), exact code:
  ```python
  lstm_input = Input(shape=(backcandles, 8), name='lstm_input')   # 2-D input shape (timesteps, features)
  inputs = LSTM(150, name='first_layer')(lstm_input)              # single LSTM layer, 150 nodes
  inputs = Dense(1, name='dense_layer')(inputs)                   # one dense node
  output = Activation('linear', name='output')(inputs)            # linear output for regression
  model = Model(inputs=lstm_input, outputs=output)
  adam = optimizers.Adam()
  model.compile(optimizer=adam, loss='mse')
  ```
  Deliberately small/simple so training is fast [11:34–11:40]; layers/nodes are meant to be increased in experiments [13:31–13:40].
- **REQ-LSTM-15** [11:16–11:32, f_1120_069, f_1130_070] Training call:
  ```python
  model.fit(x=X_train, y=y_train, batch_size=15, epochs=30, shuffle=True, validation_split=...)  # line truncated at right edge
  ```
  batch_size=15, epochs=30, shuffle=True, plus a validation split — logs show "Train on 1754 samples, validate on 195 samples" (and, for the 10-backcandle run, 1739/194), i.e. ≈10% validation. Observed losses: epoch 1 loss 0.0023 / val_loss 0.0016, decaying to ~7.55e-05 / 7.55e-04 by epoch 30 [f_1130_070, f_1150_072, f_1200_073].

Evaluation

- **REQ-LSTM-16** [11:42–12:26, f_1200_073, f_1220_075] Predict on held-out test set only (data the model never saw):
  ```python
  y_pred = model.predict(X_test)
  #y_pred = np.where(y_pred > 0.43, 1, 0)   # commented threshold for classification variant
  for i in range(10):
      print(y_pred[i], y_test[i])
  ```
  Sample pairs (scaled): [0.53974944]/[0.55227039], [0.54552203]/[0.55846903], … [f_1220_075].
- **REQ-LSTM-17** [12:26–12:38, f_1240_077, f_1430_088] Visual evaluation plot:
  ```python
  plt.figure(figsize=(16,8))
  plt.plot(y_test, color='black', label='Test')
  plt.plot(y_pred, color='green', label='pred')
  plt.legend(); plt.show()
  ```
  Result: predicted curve closely shadows the real test curve in scaled [0,1] space (intro frames f_0018_000/f_0030_007 show the same Test/pred overlay). Note the visible small lag of pred behind Test.
- **REQ-LSTM-18** [12:51–13:29, f_1300_079..f_1330_082] Experiment protocol: rerun the whole pipeline with `backcandles = 30` (model reads last 30 days, predicts tomorrow's close); the 30-candle predictions look even closer to real prices. Lookback sensitivity is part of the study.
- **REQ-LSTM-19** [13:31–14:16] Listed extension experiments (requirements for future iterations): add layers/nodes; add more technical indicators beyond the 4 used (RSI + 3 EMAs); add **slope of moving averages** (positive/negative, up/down direction) as features; add a **momentum column**; add other custom indicators believed useful [00:35–00:44 also names "custom indicators" as valid inputs].
- **REQ-LSTM-20** [00:18–00:30, 14:16–14:36] Skepticism requirement: the similar-looking prediction curve is "very tempting" but there is a "small clap" (catch) in these results; the model is failing in ways shown in a follow-up video and **must not be used as-is to predict the market**; improvements/corrections come only after understanding the failure mode. Any redesign must include honest failure analysis (e.g. lag/persistence check), not just an overlay plot.

Conceptual diagram requirements

- **REQ-LSTM-21** [00:35–01:04, f_0035_001, f_0050_008, f_0100_009] Network sketch: 4 input arrows → multi-layer dense-drawn net → output node(s) highlighted. Inputs = price values + technical + custom indicators; output = price movement trend, concretely next candle's closing price.
- **REQ-LSTM-22** [01:09–02:21, f_0109_002, f_0120_010..f_0228_003] Sliding-window training illustration on the OHLC table: an orange box over 4 consecutive rows (e.g. 2012-03-12..03-15) is the input window; the dotted red box on the NEXT row's Adj Close (777.130005) is the label; the window slides down one day at a time until the end of the training set. Caption on f_0228_003: "**2 Dim Input / 3 Dim training data**" — each sample is a 2-D matrix (backcandles × features); the stacked training set is 3-D [02:11–02:21].

```
window t-backcandles..t-1 (8 cols: O,H,L,AdjC,RSI,EMAF,EMAM,EMAS)  ──►  [ LSTM(150) ] ──► [ Dense(1) ] ──► linear ──► ŷ = scaled TargetNextClose(t)
X: (N, backcandles, 8)   y: (N, 1)   N = rows − backcandles;  split 80/20 chronological
```

## Open questions (not shown/audible in the video)

1. Exact `validation_split` value in `model.fit` — the argument is cut off at the frame's right edge; logs imply ≈0.1 but the literal value is unverified.
2. Frames for 07:00–08:40 are missing from frames/ (index gap f_0650_042 → f_0850_054); the X/y-building cell narrated there is fully visible in later frames, but any transient on-screen content in that window is unconfirmed.
3. The truncated one-line list-comprehension for X (`...:4].copy() ...`) — its full text (and why it slices `:4` vs 8 columns) is not fully visible.
4. No inverse-transform of predictions back to price units is shown; plotting stays in scaled space. Whether the source notebook contains an inverse step is unknown.
5. No quantitative metric (RMSE/MAE/directional accuracy) is computed — evaluation is visual only; the promised failure analysis is in a separate next video not included here.
6. Whether `shuffle=True` in fit (shuffling training windows) vs the chronological split was a deliberate choice is not discussed.
