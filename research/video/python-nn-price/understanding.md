# Video Understanding — "Algorithmic Trading and Price Prediction using Python Neural Network Models" (~19:27)

Note on sources: the shipped frame set had a gap between 06:50 and 12:50; the missing frames were re-extracted from the source mp4 as `frames/f_MMSS_gap.jpg` and are cited below alongside the original `f_MMSS_NNN.jpg` frames.

## Summary

The video builds a 3-class trend-direction classifier for EUR/USD daily data using scikit-learn's `MLPClassifier`, as a direct sequel/comparison to a previous XGBoost video (same data, same features, same target). Input features are RSI(16) plus a one-hot-encoded custom reversal signal (support/resistance levels + engulfing/shooting-star candlestick patterns), which is first validated standalone with backtesting.py (+126% return). The target labels each bar by whether price hits +250 pips or −250 pips within the next 30 bars (up / down / unclear). The author then trial-and-errors MLP hidden-layer topologies — (20,20,10,10), (2,2), (8,8,4), (20,20,50,30), (50,50,60,30,9) — showing via accuracy, confusion matrices and classification reports that small nets degenerate to predicting only the majority class (~33% test accuracy ≈ naive baseline), larger nets start predicting minority classes (downtrend precision up to 0.61 but recall only 0.13), and concludes MLP ≈ XGBoost on this problem, with the caveat that ML/NN works best in trend direction rather than trend reversal, and that TensorFlow/Keras would be the more advanced next step.

## REQUIREMENTS

### Concept & framing

- **REQ-PNP-01 — NN as drop-in replacement for XGBoost, same pipeline.** The whole pipeline (data, features, custom signal, target, split, metrics) is intentionally identical to the prior XGBoost video; only the model changes, to allow apples-to-apples model comparison. [00:06–00:29, 01:53–02:07; f_0000_001] Requirement: when swapping model families, hold every other pipeline stage fixed for comparability.
- **REQ-PNP-02 — Insight: ML predicts trend direction better than trend reversals.** A highlighted viewer comment ("ML works best in the direction of the trend. However, its not good in understanding trend reversals, therefore you have to implement risk and money management strategies when the ML model fails at predicting") is endorsed as true and worth correcting for in future models. [00:29–01:02; f_0040_005–f_0110_008] Requirement: prefer trend-following targets over reversal targets for ML/NN classifiers, and pair reversal models with risk/money management.
- **REQ-PNP-03 — Input-feature concept set.** Candidate NN inputs shown on the diagram: RSI, moving-average slope, parabolic-SAR slope, and any custom strategy signal; NNs can take arbitrarily many input features. [01:12–01:30; f_0120_009–f_0230_016] (Only RSI + custom signal are actually used in the code; MA slope / SAR slope are named as examples.)
- **REQ-PNP-04 — Custom reversal signal as an ML feature.** The custom signal (support/resistance + price action + candlestick patterns detecting trend reversals) is included as an input feature *because it earned positive returns as a standalone classic strategy* — validated profitability is the admission criterion for a feature. [01:38–02:34; f_0140_011]
- **REQ-PNP-05 — Classifier output framing.** The model is a classifier predicting trend category (up/down as 1/0 on the diagram; 3 classes 0/1/2 in code), not a price regressor. [02:41–02:54; f_0250_018–f_0300_019]
- **REQ-PNP-06 — Hidden topology is an open hyperparameter found by trial and error.** Stated bounds: 1 to ~100 hidden layers, ~1 to 10–100 nodes per layer; no clear rule exists; choose by trial-and-error plus expertise. [02:54–03:49; f_0310_020–f_0350_024, orange brace + "?" under hidden layers]

### Architecture diagram [01:07–03:55; f_0110_008–f_0350_024]

```
INPUTS (4)                 HIDDEN (3)        OUTPUT (2)
RSI              (blue) ──┐
MA slope         (red)  ──┤   ● ● ●   ──►   1 (red)  = UP   ▲
SAR slope        (blue) ──┤  (fully          0 (blue) = DOWN ▼
Custom Strategy  (red)  ──┘  connected)
Signal
                └──────── how many layers / nodes? ────────┘
                     (orange brace + "?" annotation)
```
Fully connected 4 → 3 → 2 toy MLP; output nodes labeled 1 (up-arrow) and 0 (down-arrow); the brace + question mark marks the hidden-layer count and width as the unknown to tune.

### Data & preprocessing

- **REQ-PNP-07 — Dataset.** `EURUSD_Candlestick_1_D_ASK_05.05.2003-30.06.2021.csv` — EUR/USD daily ASK candles, 2003–2021, ~4734 rows, columns: Local time, open, high, low, close, volume. [03:55–04:17; f_0355_000, f_0410_025]
- **REQ-PNP-08 — Cleaning.** Drop zero-volume rows (weekend/holiday bars), reset index, verify no NAs:
  ```python
  import pandas as pd
  df = pd.read_csv("EURUSD_Candlestick_1_D_ASK_05.05.2003-30.06.2021.csv")
  df = df[df['volume'] != 0]
  df.reset_index(drop=True, inplace=True)
  df.isna().sum(); df.tail()
  ```
  [04:17–04:21; f_0355_000] Later, after RSI/Target add NaNs at the head/tail, `df.dropna(inplace=True); df.reset_index(drop=True, inplace=True); print(df.describe())` → 4686 rows remain. [07:53–08:29; f_0830_gap]
- **REQ-PNP-09 — Column rename.** `df.columns = ['Local time','Open','High','Low','Close','Volume','signal']` (capitalized OHLCV for backtesting.py compatibility). [~05:10; f_0510_031]

### Support/resistance & candlestick-pattern signal

- **REQ-PNP-10 — Fractal support/resistance detection.** [04:21–04:33; f_0420_026–f_0430_027]
  ```python
  def support(df1, l, n1, n2):   # n1 n2 before and after candle l
      for i in range(l-n1+1, l+1):
          if df1.low[i] > df1.low[i-1]: return 0
      for i in range(l+1, l+n2+1):
          if df1.low[i] < df1.low[i-1]: return 0
      return 1

  def resistance(df1, l, n1, n2):  # n1 n2 before and after candle l
      for i in range(l-n1+1, l+1):
          if df1.high[i] < df1.high[i-1]: return 0
      for i in range(l+1, l+n2+1):
          if df1.high[i] > df1.high[i-1]: return 0
      return 1
  ```
  A level is support if lows monotonically decrease into candle l for n1 bars and increase after it for n2 bars (mirror logic for resistance).
- **REQ-PNP-11 — Candlestick pattern detectors** (engulfing + star/rejection; isStar transcribed from f_0440_028, [04:33–04:41]):
  ```python
  def isStar(l):
      bodydiffmin = 0.0020
      row = l
      highdiff[row] = high[row] - max(open[row], close[row])
      lowdiff[row]  = min(open[row], close[row]) - low[row]
      bodydiff[row] = abs(open[row] - close[row])
      if bodydiff[row] < 0.000001: bodydiff[row] = 0.000001
      ratio1[row] = highdiff[row] / bodydiff[row]
      ratio2[row] = lowdiff[row] / bodydiff[row]
      if (ratio1[row] > 1 and lowdiff[row] < 0.2*highdiff[row]
              and bodydiff[row] > bodydiffmin):   return 1   # shooting star (bearish)
      elif (ratio2[row] > 1 and highdiff[row] < 0.2*lowdiff[row]
              and bodydiff[row] > bodydiffmin):   return 2   # hammer/rejection (bullish)
      else: return 0
  ```
  An `isEngulfing(row)` detector (returns 1 bearish / 2 bullish / 0) is also used (visible in the signal cell, defined in a previous video).
- **REQ-PNP-12 — Combined signal: pattern near S/R level.** Signal fires only when a bullish pattern occurs close to support (or bearish near resistance), with a proximity tolerance visible as `closeSupport(row, ss, 150e-…)` (~150e-4 = 150 pips window; exact value truncated). Visible tail of the cell [04:41–05:02; f_0450_029]:
  ```python
  elif ((isEngulfing(row)==2 or isStar(row)==2) and closeSupport(row, ss, 150e-...)):
      signal[row] = 2      # buy/reversal-up signal
  else:
      signal[row] = 0
  ```
  `df['signal'] = signal`; category-1 (sell) signals occur 91 times in the dataset (`df[df['signal']==1].count()` → 91). [f_0450_029, f_0500_030]

### Standalone strategy validation (backtesting.py)

- **REQ-PNP-13 — Verify the signal with a classic backtest before feeding it to ML.** [05:18–05:54; f_0520_032–f_0550_035]
  ```python
  def SIGNAL(): return df.signal

  from backtesting import Strategy
  class MyCandlesStrat(Strategy):
      def init(self):
          super().init()
          self.signal1 = self.I(SIGNAL)
      def next(self):
          super().next()
          if self.signal1 == 2:
              sl1 = self.data.Close[-1] - 600e-4
              tp1 = self.data.Close[-1] + 450e-4
              self.buy(sl=sl1, tp=tp1)
          elif self.signal1 == 1:
              sl1 = self.data.Close[-1] + 600e-4
              tp1 = self.data.Close[-1] - 450e-4
              self.sell(sl=sl1, tp=tp1)
  ```
  Fixed SL = 60 pips, TP = 45 pips on both sides. Results (f_0540_034): Return 126.525528%, Buy&Hold 5.128364%, Equity Final $22,652.55 / Peak $23,157.25, Exposure 72.33%, Max Drawdown −18.93% (avg −1.85%, max DD duration 1242), # Trades 94, Win Rate 75.53%. Equity curve plotted with `bt.plot()` (Peak 232%, Final 227% shown). Acceptance gate: the signal must show a rising equity curve / positive return before use as an ML feature.

### Target engineering

- **REQ-PNP-14 — Barrier-style 3-class trend target `mytarget(barsupfront, df1)`.** [05:54–06:57; f_0600_036–f_0640_040, f_0750_gap]
  ```python
  pipdiff = 250*1e-4      # 250 pips → TP distance
  SLTPRatio = 1           # pipdiff/Ratio gives SL distance
  def mytarget(barsupfront, df1):
      length = len(df1)
      high = list(df1['High']); low = list(df1['Low'])
      close = list(df1['Close']); open = list(df1['Open'])
      trendcat = [None] * length
      for line in range(0, length-barsupfront-2):
          valueOpenLow = 0; valueOpenHigh = 0
          for i in range(1, barsupfront+2):
              value1 = open[line+1] - low[line+i]
              value2 = open[line+1] - high[line+i]
              valueOpenLow  = max(value1, valueOpenLow)
              valueOpenHigh = min(value2, valueOpenHigh)
          if (valueOpenLow >= pipdiff) and (-valueOpenHigh <= (pipdiff/SLTPRatio)):
              trendcat[line] = 1   # downtrend
              break-equivalent (break)
          elif (valueOpenLow <= (pipdiff/SLTPRatio)) and (-valueOpenHigh >= pipdiff):
              trendcat[line] = 2   # uptrend
              break
          else:
              trendcat[line] = 0   # no clear trend
      return trendcat
  ```
  Semantics: looking `barsupfront` bars ahead from next bar's open — touch −250 pips first (without +250 breach) → class 1 downtrend; touch +250 pips first → class 2 uptrend; touch both or neither → class 0 unclear. Commented-out variants in the cell show a richer 6-class scheme (2 both-limits, 3 downtrend, 1 uptrend, 0 no trend, 5 light trend down, 4 light trend up) that was collapsed to 3 classes. Symmetric barriers (SLTPRatio=1) mean random accuracy ≈ 33%; a useful model needs ≳45–50%. [12:41–13:13]
- **REQ-PNP-15 — Apply with 30-bar horizon and inspect class balance.** `df['Target'] = mytarget(30, df)`; `df['Target'].hist()` → class 0 ≈ 800, class 1 (down) ≈ 1800, class 2 (up) ≈ 2080. Cell is titled `#!!! pitfall one category high frequency`: always check the class histogram to interpret accuracy against the majority-class baseline (~34–35% by always predicting class 2). [06:39–07:31, 13:13–13:44; f_0640_040, f_0700_gap, f_1310_079]

### Features & encoding

- **REQ-PNP-16 — RSI feature via pandas_ta.** `import pandas_ta as pa; df["RSI"] = pa.rsi(df.Close, length=16)` — RSI length 16 (first 16 bars become NaN; dropped by REQ-PNP-08's dropna, as are the last 30 bars where Target is NaN). [07:31–08:29; f_0740_gap, f_0810_gap]
- **REQ-PNP-17 — One-hot encode the categorical signal.** `dfDummies = pd.get_dummies(df_model['signal'], prefix='signalcategory')`; drop raw `signal`; `df_model = pd.concat([df_model, dfDummies], axis=1)` → final model frame 4686 rows × 5 cols: RSI, Target, signalcategory_0, signalcategory_1, signalcategory_2. [08:42–09:20; f_0850_gap, f_0900_gap]

### Models

- **REQ-PNP-18 — XGBoost reference model (kept in the same notebook for comparison).** `from xgboost import XGBClassifier; from sklearn.metrics import accuracy_score, log_loss`; attributes = ['RSI','signalcategory_0','signalcategory_1','signalcategory_2']; X=df_model[attributes], y=df_model['Target']; chronological 70/30 split (`train_pct_index = int(0.7*len(X))`, slice-based, no shuffle); `model = XGBClassifier(); model.fit(X_train,y_train)`. Results: Train 57.0732%, Test 32.3613%. Confusion matrices — train [[0,39,212],[0,416,853],[0,161,1273]], test [[0,73,364],[0,69,317],[0,101,342]] — both non-majority classes get predictions (unlike small MLPs). Also `print(model.get_booster().feature_names)` and an F-score feature-importance plot (signalcategory_2 visible). Comment lines `#choices = [2, 0, -1, +1]`, `##choices = [2, 0, 3, +1]`. [09:06–09:25, 18:24–18:56; f_0910_gap, f_0920_gap, f_1840_112, f_1850_113, f_1900_114, f_1830_111]
- **REQ-PNP-19 — MLP classifier, exact construction.** [09:25–11:28; f_0930_gap–f_1130_gap]
  ```python
  from sklearn.neural_network import MLPClassifier
  attributes = ['RSI', 'signalcategory_0', 'signalcategory_1', 'signalcategory_2']
  X = df_model[attributes]
  y = df_model['Target']

  train_pct_index = int(0.6 * len(X))                       # 60/40 chronological split
  X_train, X_test = X[:train_pct_index], X[train_pct_index:]
  y_train, y_test = y[:train_pct_index], y[train_pct_index:]

  NN = MLPClassifier(hidden_layer_sizes=(20, 20, 10, 10), random_state=10,
                     verbose=0, max_iter=1000, activation='relu')
  NN.fit(X_train, y_train)
  pred_train = NN.predict(X_train)
  pred_test  = NN.predict(X_test)
  acc_train = accuracy_score(y_train, pred_train)
  acc_test  = accuracy_score(y_test, pred_test)
  print("="*20)
  print('****Train Results****'); print("Accuracy: {:.4%}".format(acc_train))
  print('****Test Results****');  print("Accuracy: {:.4%}".format(acc_test))
  ```
  Notes: split is time-ordered slicing (no shuffling/leakage); `random_state` is later changed to 100 (stated to be an arbitrary seed); `verbose=0`; `max_iter=1000`; `activation='relu'` (default, said not to matter much here).
- **REQ-PNP-20 — Evaluation harness.** Always report BOTH train and test accuracy, plus confusion matrices and classification reports for both sets:
  ```python
  from sklearn.metrics import confusion_matrix, classification_report
  matrix_train = confusion_matrix(y_train, pred_train)
  matrix_test  = confusion_matrix(y_test, pred_test)
  print(matrix_train); print(matrix_test)
  report_train = classification_report(y_train, pred_train)
  report_test  = classification_report(y_test, pred_test)
  print(report_train); print(report_test)
  ```
  [09:20, 13:44–13:57, 14:45; f_0920_gap, f_1450_089]

### Topology experiments (trial-and-error protocol) — all with same data/split/metrics

- **REQ-PNP-21 — Experiment 1: hidden_layer_sizes=(20,20,10,10).** Train 52.6859%, Test 33.1733%. [10:22–12:26; f_1040_gap, f_1220_gap]
- **REQ-PNP-22 — Experiment 2: (2,2).** Train 51.8677%, Test 32.8533% — nearly identical global accuracy to Exp 1. Confusion matrices show single-class collapse: train [[0,0,189],[0,0,1164],[0,0,1458]], test [[0,0,621],[0,0,638],[0,0,616]] — everything predicted class 2; precision/recall = 0 for classes 0 & 1; class 2 test precision 0.33 / recall 1.00 / f1 0.49; test accuracy 0.33 = majority baseline. Lesson: global accuracy alone cannot detect a degenerate/naive model; the confusion matrix can. [10:38–15:17; f_1050_gap, f_1100_gap, f_1240_gap, f_1350_083, f_1500_090, f_1510_091]
- **REQ-PNP-23 — Naive-baseline rule.** With 3 classes and the majority class ≈34–35% of samples, a model always predicting "uptrend" scores ~33–35% accuracy; require materially more (~45–50%+ stated) before trusting the model for trading. [12:41–13:44]
- **REQ-PNP-24 — Experiment 3: width ≥ input count.** Heuristic stated: with 4 input features, use at least 4 — better double (8) — nodes per layer; try (8,8,4) narrowing toward the 3 output classes. Result: essentially unchanged (Train ~51.8%, Test ~32.8%), still one-class collapse. [14:07–14:56; f_1420_086–f_1440_088]
- **REQ-PNP-25 — Experiment 4: (20,20,50,30).** Train 52.7926%, Test 34.9867%. Model starts predicting class 1 sometimes: confusion train [[0,2,187],[0,47,1117],[0,21,1437]], test [[0,16,605],[0,29,609],[0,19,597]]; train class-1 precision 0.67 / recall 0.04; test class-1 precision 0.45 / recall 0.05 (i.e., missing ~95% of downtrends); test class-2 0.33/0.97. More layers/nodes = more compute/fit time (acceptable on this small dataset). [15:17–16:36; f_1530_093–f_1640_100, f_1600_096–f_1630_099]
- **REQ-PNP-26 — Experiment 5: (50,50,60,30,9).** Adding a 9-node bottleneck layer before output. Train 52.8637%, Test 34.9867%. Confusion train [[0,6,183],[0,76,1088],[0,48,1410]], test [[0,10,611],[0,82,556],[0,42,574]]. Test class-1 (downtrend) precision 0.61 / recall 0.13 (improving), class-2 precision 0.33 / recall 0.93. Global accuracy barely moves while minority-class behavior improves → track per-class precision/recall, not just accuracy. [16:36–17:30; f_1650_101–f_1740_106, f_1750_107, f_1800_108–f_1820_110]
- **REQ-PNP-27 — Tuning protocol.** Hidden-layer count/widths are tuned purely by iterative trial-and-error re-runs of the same cell, observing accuracy + confusion matrix each time; results are highly sensitive to these hyperparameters; no automated search is used (explicit open call for better methods/books). [17:30–18:24]

### Conclusions / forward pointers

- **REQ-PNP-28 — Model comparison verdict.** XGBoost is judged better *from the confusion-matrix perspective* (both non-majority categories represented in train and test predictions), but global train/test accuracies are almost the same for XGBoost (57.07%/32.36%) and MLP (~52.9%/~35.0%) — for this application classical ML ≈ simple NN. [18:24–19:03; f_1840_112–f_1900_114]
- **REQ-PNP-29 — Upgrade path.** sklearn's MLPClassifier is "a relatively simple neural network model"; more advanced models should use TensorFlow with Keras as the interface. [19:03–19:16]
- **REQ-PNP-30 — Reproducibility/packaging.** Everything lives in a single downloadable Jupyter notebook ("Neural Networks For Market Trading") that contains both the XGBoost and NN models, the signal backtest, and all cells in execution order. [03:49–04:04; f_0355_000]

## Condensed notebook flow

```
read CSV → drop volume==0 → S/R functions → candlestick detectors → signal (0/1/2)
→ rename columns → backtesting.py sanity backtest (126.5% return, 94 trades, 75.5% WR)
→ mytarget(30, df) with pipdiff=250e-4, SLTPRatio=1 → Target hist (800/1800/2080)
→ RSI(16) via pandas_ta → dropna (4686 rows)
→ one-hot signal → df_model[RSI, Target, signalcategory_0/1/2]
→ [XGBClassifier, 70/30 chrono split]  (reference)
→ MLPClassifier(hidden_layer_sizes=…, random_state=100, verbose=0, max_iter=1000,
                activation='relu'), 60/40 chrono split
→ predict train+test → accuracy_score → confusion_matrix + classification_report
→ iterate topologies: (20,20,10,10) → (2,2) → (8,8,4) → (20,20,50,30) → (50,50,60,30,9)
```

## Open questions (ambiguous / unreadable — not invented)

1. `closeSupport(row, ss, 150e-…)` third argument is cut off at the right edge in every frame (f_0450_029); likely 150e-4 but the exponent is not fully visible. The full signal-cell body (bearish branch, `ss`/`rr` level lists, closeResistance call) is never fully on screen.
2. `isEngulfing()` implementation is never shown (referenced from a previous video).
3. The right edge of the MLPClassifier line is clipped in most frames; `max_iter=1000` and `activation='relu'` are confirmed only via the horizontally-scrolled frame f_1110_gap. Any parameters beyond `activation` (if present) are unverifiable.
4. `mytarget` inner loop uses `open[line+1] - low[line+i]` / `open[line+1] - high[line+i]` — index base `line+1` appears constant while `i` advances (as transcribed); whether the notebook intends `open[line+1]` or `open[line+i]` in `value1/value2` cannot be double-checked beyond the visible frames (all frames consistently show `line+1` for open).
5. The commented-out 6-category variant of `mytarget` (categories 3, 4, 5 "light trend") has its condition lines truncated at the right margin (f_0630_039, f_0750_gap); full thresholds unknown.
6. Transcript says the histogram shows category 1 (downtrend) ≈ "1750" and support counts in classification reports imply train-set class ratios 189/1164/1458; the exact total per class in the full dataset is read from the histogram only approximately (≈800/≈1800/≈2080).
7. Transcript [06:10–06:21] first describes the target with "10 days in the future" as an example before fixing 30; only 30 is used in code.
8. The XGBoost cell's `#choices = [2, 0, -1, +1]` / `##choices = [2, 0, 3, +1]` comments (f_1850_113) are legacy remap notes from the previous video; their exact purpose is not explained here.
