# Video Understanding — "Why AI Neural Networks Will Change Trading Forever & How to Build Yours in Minutes" (~21 min)

Source: `/home/karan18190164/research/video/nn-in-minutes/` (transcript.md + 80 frames). Every distinct technique, parameter, diagram and code element below is declared a REQUIREMENT by the user.

## Summary

The video (QuantProgram channel, 3rd in an ML series after regression and decision trees) teaches neural-network trading from first principles: it explains feed-forward NNs via a cat-classification example (input/hidden/output layers, random weight init, error term, back-propagation, epochs), then recurrent NNs with memory via the "I like to drink coffee" next-word table (hidden states h1–h4 carried across time steps t1–t5), maps that directly onto stock prediction (inputs = price + RSI per day, target = 5th-day return / +ve-or-−ve movement), covers RNN weaknesses (compute cost, vanishing gradient) and the LSTM forget-gate fix, then walks through a **hand-written NumPy RNN inside a QuantConnect QCAlgorithm** (no NN library; explicit Wxh/Whh/Why weights, tanh hidden states, BPTT with gradient clipping) trained on SPY 2000–2009 and tested 2010–2024. The strategy scores CAGR 9.089% vs max drawdown 18.3% → CAGR/MaxDD ratio 0.49, beating the S&P 500 buy-and-hold benchmark ratio of 10/55 ≈ 0.18, and the video closes comparing a whole family of models (regression 0.32, decision trees 0.45/0.49, SVM 0.44, RNN 0.49, LSTM, RNN+regression and RNN+SVM combos) plus LSTM-driven portfolio rebalancing over SPY/GLD/TLT/SHY.

---

## REQUIREMENTS

### A. Core concepts / pedagogy

- **REQ-NNM-01 — Feed-forward neural network (FNN) for classification.** Input layer → hidden layer(s) → output layer; initial weights random; wrong output (cat→"cheetah") produces an error term; weights everywhere are adjusted and the pass repeats until correct. [00:58–03:14]; frames f_0050_047–f_0230_057 (whiteboard: cat image → 2 grey input nodes → 5 blue hidden nodes → 1 orange output node labelled "Cat", annotated w (weights), E (error), o (output), h (hidden) with pink arrows showing error flowing backwards).
- **REQ-NNM-02 — Iterations = epochs.** The number of forward/backward repetitions is called iterations, i.e. epochs; a tunable training parameter. [02:55–03:04]; whiteboard list item "7. Epochs" (f_0050_047).
- **REQ-NNM-03 — Back-propagation & forward pass.** Error at output flows back adjusting hidden- and input-side weights, then a forward pass re-predicts; repeat. Reference diagram (stock image) shows Forward Pass vs Backpropagation columns: Input Units → Hidden Units H1 → Hidden Units H2 → Output Units, fully connected between adjacent layers, with backward arrows on the right copy. [04:03–04:42]; f_2026_044/f_2040_142 (diagram at right of full whiteboard), f_2110_145.
- **REQ-NNM-04 — RNN = FNN + memory via back-propagation through time (BPTT).** RNN keeps a hidden state per time step (sequential time steps), giving a memory advantage for sequence data (stock prices, sentences). [03:14–05:57]; whiteboard "Recurrent Neural Network" list (f_0320_062, f_0717_008): 1. Memory advantage, 2. Sequence data, 3. Back Propagation through time, 4. Sequential Time steps, 5. Hidden layers and Hidden States(time), 6. Memory Vectors(64,128..), 7. RNN Problems, Computational, LSTM.
- **REQ-NNM-05 — "I like to drink coffee" hidden-state table.** 5 time steps; each step consumes an input word plus the previous hidden state and emits a new hidden state; at t5 there is no input and the model predicts "coffee" from h4. Table exactly (f_0717_008/f_0732_010): columns = time step | input word | previous hidden state | current hidden state; rows = t1:"i"/none/h1; t2:"like"/h1/h2; t3:"to"/h2/h3; t4:"drink"/h3/h4; t5:none ("we predict here")/h4/predict "coffee". [05:02–06:01].
- **REQ-NNM-06 — Trading translation of the sequence model.** Same table with market data (f_1055_021/f_1500_032, "Trading example"): inputs per step = P1,RSI(1) … P4,RSI(4) (price + RSI per day), t5 = none / "we predict here", output = **Predict + or −ve Stock Movement**; whiteboard note "Eg for Stocks — Input: RSI, Volume, Price……  Target – 5th day Return". Inputs are freely choosable (price change, overnight gap, volume change, RSI…). [06:01–06:59, 13:25–13:43].
- **REQ-NNM-07 — RNN problem #1: computational cost.** NNs need much more compute than decision trees/regression; QuantConnect runs CPUs (no GPUs) — LSTM backtests take 15–30 min and can time out; keep models small enough for CPU. [06:59–07:42]. (Matches our CPU-first constraint.)
- **REQ-NNM-08 — RNN problem #2: vanishing gradient → LSTM forget gate.** RNN forgets distant past (Stephen King "The Stand" analogy) due to back-prop errors/weights; LSTM adds a forget gate alongside hidden units that keeps important past information. LSTM slide (f_0948_020/f_1120_024): 1. Problem with RNN – Vanishing Gradient Problems, 2. Forgets stuff, 3. Backpropogation errors- weights, 4. Special gate – Forget Gate. [10:00–10:53].
- **REQ-NNM-09 — Memory vector (hidden) size is a capacity dial.** Strategy uses 64 as the memory-vector size for speed; can scale 64 → 128 → 256 for more capacity at more compute. [07:47–07:59]; list "Memory Vectors(64,128..)".
- **REQ-NNM-10 — Hyper-parameter tuning set.** Explicit tunables (whiteboard "Hyper Parameter Tuning", f_1055_021): 1. Input features, 2. Epochs, 3. Hidden vector size, 4. Learning rate ..  — plus lookback and train/test windows elsewhere; the improvement path for the strategy is adjusting these. [08:05–08:24, 19:01–19:25].
- **REQ-NNM-11 — Three use cases of RNN/LSTM in trading** (whiteboard "Use case of RNN and LSTM", f_0948_020): 1. Entry or Exit trading condition, 2. Improve an existing strategy (reduce drawdowns), 3 (listed as "2."). Rebalance Portfolio. [09:45–11:54].

### B. Strategy implementation (QuantConnect RNN, hand-written NumPy)

- **REQ-NNM-12 — No-library RNN: equations written by hand** with only NumPy + scikit-learn (StandardScaler); rationale: transparency and modifiability vs opaque libraries. Imports (f_1157_025): `from AlgorithmImports import *`, `import numpy as np`, `from sklearn.preprocessing import StandardScaler`. [11:54–12:32].
- **REQ-NNM-13 — Universe & data.** Single symbol SPY daily: `self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol`; backtest window `SetStartDate(2010,1,1)`, `SetEndDate(2024,9,1)`, `SetCash(100000)`. [12:37, 15:20–15:37]; f_1157_025/f_1306_028.
- **REQ-NNM-14 — Indicators + warm-up.** `self.rsiPeriod = 2`; `self.rsi = self.RSI(self.spy, self.rsiPeriod, Resolution.Daily)`; `self.ma9 = self.SMA(self.spy, 9, Resolution.Daily)`; `self.ma200 = self.SMA(self.spy, 200, Resolution.Daily)`; `self.SetWarmUp(200)` (warm up 200 days). Indicator readiness gates trading (see REQ-NNM-22). [12:37–13:14]; f_1306_028.
- **REQ-NNM-15 — RNN parameters block** (f_1306_028/f_1326_031/f_1920_138): `self.lookback = 10` (10 lookback periods, generalising the 5-step example); `self.feature_count = 2  # price_change, overnight_gap, volume_change` (exact 2 features kept course-private on purpose; comment lists candidates); `self.hidden_size = 64`; `self.learning_rate = 0.01`; `self.prediction = 0` (prediction sign drives long/short). [13:14–14:08].
- **REQ-NNM-16 — Feature scaling with StandardScaler.** `self.scaler = StandardScaler()`; features fit+transformed before training so large-magnitude features (e.g. volume ~100k) don't dominate small ones (RSI ~30). [14:08–14:44]; f_1306_028.
- **REQ-NNM-17 — Weight/bias initialization** (`InitializeRNN`, f_1511_033/f_1326_031): `np.random.seed(42)  # for reproducibility`; `self.Wxh = np.random.randn(self.hidden_size, self.feature_count) * 0.01`; `self.Whh = np.random.randn(self.hidden_size, self.hidden_size) * 0.01`; `self.Why = np.random.randn(1, self.hidden_size) * 0.01`; `self.bh = np.zeros((self.hidden_size, 1))`; `self.by = np.zeros((1, 1))`. Called from Initialize: `self.InitializeRNN()` then `self.TrainRNN()`. [14:44–15:16].
- **REQ-NNM-18 — Train/test split.** Training data = History(SPY, datetime(2000,1,1) → datetime(2009,12,31)); testing = the 2010–2024 backtest itself; user encouraged to shift windows (e.g. train 1990–2000). Training loop (`TrainRNN`, f_1511_033): `features=[]; targets=[]`; `for i in range(len(history) - self.lookback):` → `feature = self.GetFeaturesFromHistory(history.iloc[i:i+self.lookback+1])`; skip None; `target = (history['close'].iloc[i+self.lookback] - history['open'].iloc[i+self.lookback]) …` (rest off-screen). Features scaled/transformed, then epoch loop computes epoch losses. [15:16–16:25].
- **REQ-NNM-19 — Forward propagation.** Hidden states start as an empty array, are appended per time step using weights + biases; returns y and the hidden states (`return y, hidden_states`). (Exact forward equations largely off-screen; tanh implied by the backward pass derivative.) [16:25–17:01].
- **REQ-NNM-20 — Backward propagation (BPTT) — code transcribed** (`def backward(self, X, hidden_states, y, y_pred)`, f_1745_034/f_1934_036, lines 86–110):
  ```python
  dWxh, dWhh, dWhy = np.zeros_like(self.Wxh), np.zeros_like(self.Whh), np.zeros_like(self.Why)
  dbh, dby = np.zeros_like(self.bh), np.zeros_like(self.by)
  dhnext = np.zeros((self.hidden_size, 1))
  dy = y_pred - y
  dWhy += np.dot(dy, hidden_states[-1].T)
  dby += dy
  for t in reversed(range(len(X))):
      dh = np.dot(self.Why.T, dy) + dhnext
      dhraw = (1 - hidden_states[t] * hidden_states[t]) * dh     # tanh derivative
      dbh += dhraw
      dWxh += np.dot(dhraw, X[t].reshape(1, -1))
      dWhh += np.dot(dhraw, hidden_states[t-1].T) if t > 0 else np.zeros_like(self.Whh)
      dhnext = np.dot(self.Whh.T, dhraw)
  for dparam in [dWxh, dWhh, dWhy, dbh, dby]:
      np.clip(dparam, -5, 5, out=dparam)                          # gradient clipping ±5
  self.Wxh -= self.learning_rate * dWxh
  self.Whh -= self.learning_rate * dWhh
  self.Why -= self.learning_rate * dWhy
  self.bh  -= self.learning_rate * dbh
  self.by  -= self.learning_rate * dby
  ```
  [16:25–17:28].
- **REQ-NNM-21 — Epoch loss tracking.** Training loops over epochs, computing epoch loss each iteration via `self.backward(...)`; more epochs = better fit but more compute (QuantConnect may not handle too many). [16:06–16:25].
- **REQ-NNM-22 — OnData gating + entry/exit.** `def OnData(self, data: Slice):` → `if self.IsWarmingUp or not self.rsi.IsReady or not self.ma9.IsReady or not self.ma200.IsReady: return`. Entry/exit conditions and the exact input features are course-member-only (intentionally not shown); direction: prediction positive → long, negative → short (log line at f_2007_040: "Going long based on predicted returns"). [17:28–17:45, 14:00–14:08].
- **REQ-NNM-23 — Commissions included.** All results include commissions/fees (fees −$3,767.42 visible in the RNN backtest header). [17:52–17:57]; f_0019_006.

### C. Evaluation & benchmark

- **REQ-NNM-24 — Primary metric: CAGR ÷ Max Drawdown ratio.** Benchmark = S&P 500 buy-and-hold: CAGR 10 / MaxDD 55 (2008 crisis) = **0.18**; a strategy must beat 0.18 to be executed. RNN strategy: CAGR 9(.089)% / DD 18.3% = **0.491803278688525** (calculator shown, f_1840_134). [18:02–18:45].
- **REQ-NNM-25 — RNN backtest scorecard** (QuantConnect Overview, f_1900_136 + header f_0019_006): PSR 9.432%, Sharpe Ratio 0.553, Total Orders 879, Average Win 0.86%, Average Loss −1.04%, Compounding Annual Return 9.089%, Drawdown 18.300%, Expectancy 0.292, Start Equity 100000, End Equity 358388.00, Net Profit 258.388%, Sortino Ratio 0.407, Loss Rate 30%, Win Rate 70%; equity $358,381.88, holdings $358,500.48, unrealized $2,159.22. These are the fields a redesigned scorecard should reproduce.
- **REQ-NNM-26 — Leverage headroom argument.** Because 0.49 ≫ 0.18, ~2× leverage yields ~18% CAGR with ~36% DD, still below S&P's 55% max DD. [18:45–19:01].
- **REQ-NNM-27 — Model leaderboard (CAGR/MaxDD ratios)** (f_1941_039/f_1950_139/f_2000_140, blue/green table; S&P row yellow 0.18): Linear Regression Model 0.32; Decision Tree 1 0.45; Support Vector Machine 0.44; Recurrent Neural Network 0.49; Combine AI model 1: RNN + Linear Regression 0.39; Combined AI Model 2: RNN + Support Vector Machine 0.45; Decision Tree 2 0.49; Long Short Term Memory also shown as beating the benchmark (exact number not readable on screen). All strategies beat SPX 0.18. [19:38–20:30].
- **REQ-NNM-28 — Model combining (ensembles).** Combining models is a first-class technique: RNN+Regression (backtest header f_2020_141: equity $406,443.46, net profit $305,329.33, return 306.44%, PSR 4.283%) and RNN+SVM; presented as a way to get "a fundamentally better edge". [08:36–08:43, 20:18–20:30].
- **REQ-NNM-29 — Five-model curriculum.** The full model family discussed: regression, decision tree, support vector machine, recurrent neural network, long short-term memory — each with a strategy + quiz (quiz example f_0911_017: FNN-vs-RNN feedback-connections question; RNN good at sequence problems like stock prices/speech). A redesign should support all five model types. [08:56–09:30].
- **REQ-NNM-30 — Overfitting telemetry.** QuantConnect Research Guide panel shown repeatedly with "Likely Not Overfit" flags on backtest count / parameters detected / research time (e.g. "82 Backtests… Likely Not Overfit", "0 Parameters Detec… Likely Not Overfit") — i.e., track anti-overfit signals alongside results. Frames f_0019_006, f_1104_023.

### D. Portfolio application (LSTM)

- **REQ-NNM-31 — LSTM portfolio-optimization/rebalancing strategy.** Project "LSTM COVARIANCE MATRIX UPD…" (f_1104_023): use LSTM (with a covariance matrix) to allocate capital across a multi-asset portfolio — SPY, GLD, TLT, SHY (treemap "Assets Sales Volume" shows SHY/GLD/SPY/TLT; portfolio-margin chart tracks TLT/SPY/GLD) — for superior returns while minimizing drawdown. Backtest header: equity $439,155.16, fees $473.47, holdings $437,858.77, net profit $292,818.92, PSR 9.578%, return 339.16%, unrealized $46,318.64. Markowitz portfolio optimization also referenced as the classical baseline that AI upgrades. [09:41–11:54].
- **REQ-NNM-32 — NN as strategy-improver, not only signal-generator.** Apply the NN on top of an existing well-performing strategy to raise returns and cut drawdowns (the "improve an existing strategy" use case), and to rebalance value-investing portfolios. [09:45–10:00, 11:16–11:48].

### E. Architecture diagrams (redrawn)

**1. Title diagram — NN trading pipeline** (f_0009_004, f_2026_044):
```
  Stock (price series)          Neural network                Performance (equity curve)
 ┌─────────────┐        ┌──────────────────────────┐        ┌──────────────┐
 │  /\/\/\/\/  │ ──►    │  I1 ●──┐   H1 ●          │  ──►   │      _/‾     │
 │ noisy chart │        │        ├─► H2 ●  ─┐      │        │   _/‾ up-    │
 └─────────────┘        │  I2 ●──┘   H3 ●   ├─► O ●│        │ _/   trend   │
                        │            H4 ●  ─┘      │        └──────────────┘
                        │            H5 ●          │
                        └──────────────────────────┘
  2 input nodes (grey) → 5 hidden nodes (blue, fully connected) → 1 output node (orange)
```

**2. FNN cat-training loop** (f_0050_047 → f_0230_057, hand annotations):
```
 cat image → [inputs ●●] → [hidden ●●●●●, weights w] → [output ● ] → "Cheetah"?? 
                     ▲                                        │
                     │        error term E (output wrong)      │
                     └───── back-propagation: adjust ALL w ◄───┘
        repeat forward/backward for N epochs until output = "Cat"
   annotations on canvas: w = weights (top + bottom of hidden column),
   E = error, o = output, h = hidden; pink arrows loop output→hidden→input
```

**3. RNN unrolled through time (word + trading versions)** (f_0717_008, f_1500_032): see REQ-NNM-05/06 tables; connectivity is `h(t) = f(input(t), h(t-1))`, prediction made from last hidden state h4 at t5.

**4. Forward-pass / back-propagation reference image** (right side of f_2040_142):
```
 Forward Pass:                    Backpropagation:
 Input Units (row of ●)           same 4-layer stack, arrows reversed
   │ (full fan-out)               Output error → Hidden Units H2
 Hidden Units H1                  → Hidden Units H1 → input weights
   │
 Hidden Units H2
   │
 Output Units
```

Mermaid (strategy dataflow):
```mermaid
flowchart LR
  A[SPY daily bars 2000-2009 History] --> B[GetFeaturesFromHistory\nlookback=10, 2 features\n(candidates: price_change, overnight_gap, volume_change, RSI)]
  B --> C[StandardScaler fit/transform]
  C --> D[RNN train: epochs loop\nforward pass -> hidden_states, y\nbackward BPTT + clip ±5\nSGD lr=0.01]
  D --> E[Live OnData 2010-2024\nwarmup 200d + RSI2/SMA9/SMA200 ready]
  E --> F{prediction sign}
  F -->|+| G[Go long SPY]
  F -->|-| H[Go short SPY]
  G & H --> I[Scorecard: CAGR/MaxDD >= beat 0.18 SPX;\nSharpe, Sortino, PSR, win rate, expectancy]
```

### F. Condensed faithful code (as shown on screen)

```python
from AlgorithmImports import *
import numpy as np
from sklearn.preprocessing import StandardScaler

class ImprovedCasualBrownGiraffe(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2010, 1, 1); self.SetEndDate(2024, 9, 1); self.SetCash(100000)
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.rsiPeriod = 2
        self.rsi = self.RSI(self.spy, self.rsiPeriod, Resolution.Daily)
        self.ma9 = self.SMA(self.spy, 9, Resolution.Daily)
        self.ma200 = self.SMA(self.spy, 200, Resolution.Daily)
        self.SetWarmUp(200)
        # RNN parameters
        self.lookback = 10
        self.feature_count = 2   # price_change, overnight_gap, volume_change
        self.hidden_size = 64
        self.learning_rate = 0.01
        self.prediction = 0
        self.scaler = StandardScaler()
        self.InitializeRNN()
        self.TrainRNN()

    def InitializeRNN(self):
        np.random.seed(42)  # for reproducibility
        self.Wxh = np.random.randn(self.hidden_size, self.feature_count) * 0.01
        self.Whh = np.random.randn(self.hidden_size, self.hidden_size) * 0.01
        self.Why = np.random.randn(1, self.hidden_size) * 0.01
        self.bh = np.zeros((self.hidden_size, 1))
        self.by = np.zeros((1, 1))

    def TrainRNN(self):
        history = self.History(self.spy, datetime(2000,1,1), datetime(2009,12,31), Resolution.Daily)
        features, targets = [], []
        for i in range(len(history) - self.lookback):
            feature = self.GetFeaturesFromHistory(history.iloc[i:i+self.lookback+1])
            if feature is not None:
                features.append(feature)
            target = (history['close'].iloc[i+self.lookback] - history['open'].iloc[i+self.lookback])  # trailing part off-screen
            # ... scale features, then epoch loop: forward -> loss -> self.backward(...)

    # forward(): builds hidden_states list step by step with Wxh/Whh/bh, output via Why/by
    #            returns y, hidden_states           (exact lines partially off-screen)

    def backward(self, X, hidden_states, y, y_pred):
        dWxh, dWhh, dWhy = np.zeros_like(self.Wxh), np.zeros_like(self.Whh), np.zeros_like(self.Why)
        dbh, dby = np.zeros_like(self.bh), np.zeros_like(self.by)
        dhnext = np.zeros((self.hidden_size, 1))
        dy = y_pred - y
        dWhy += np.dot(dy, hidden_states[-1].T); dby += dy
        for t in reversed(range(len(X))):
            dh = np.dot(self.Why.T, dy) + dhnext
            dhraw = (1 - hidden_states[t] * hidden_states[t]) * dh   # tanh'
            dbh += dhraw
            dWxh += np.dot(dhraw, X[t].reshape(1, -1))
            dWhh += np.dot(dhraw, hidden_states[t-1].T) if t > 0 else np.zeros_like(self.Whh)
            dhnext = np.dot(self.Whh.T, dhraw)
        for dparam in [dWxh, dWhh, dWhy, dbh, dby]:
            np.clip(dparam, -5, 5, out=dparam)
        self.Wxh -= self.learning_rate * dWxh
        self.Whh -= self.learning_rate * dWhh
        self.Why -= self.learning_rate * dWhy
        self.bh  -= self.learning_rate * dbh
        self.by  -= self.learning_rate * dby

    def OnData(self, data: Slice):
        if self.IsWarmingUp or not self.rsi.IsReady or not self.ma9.IsReady or not self.ma200.IsReady:
            return
        # entry/exit conditions + exact input features intentionally not shown in video
```

---

## Open questions (honest gaps — do not invent)

1. **Exact 2 input features and entry/exit rules** are deliberately withheld ("available for our members"); only the candidate list (price change, overnight gap, volume change, RSI) and feature_count=2 are known. [13:39–13:47, 17:28–17:45].
2. **Forward-propagation equations** are described verbally (empty hidden-state array, append per step, weights+biases, `return y, hidden_states`) but the exact code lines were never fully legible on screen; tanh activation is inferred from the backward derivative `(1 − h²)`.
3. **TrainRNN target line** is cut off mid-expression after `(history['close'].iloc[i+self.lookback] - history['open'].iloc[i+self.lookback]`; the divisor/normalisation (if any) and the epoch count value are not visible.
4. **LSTM strategy internals** (covariance-matrix usage, gate equations, rebalance cadence, allocation rule across SPY/GLD/TLT/SHY) are never shown — only project name, asset set and results.
5. **LSTM leaderboard number** — the narrator scrolls to it ("that also has done spectacularly well") but the exact CAGR/MaxDD value for LSTM (and RNN+Regression / RNN+SVM rows beyond those listed) is not readable in captured frames.
6. **Transcript garbles** (p=0.78 ASR): "LSDF" ≈ LSTM [07:15]; "recurring neural network" = recurrent; "hidden exercise" ≈ hidden size; "decision 3" = decision tree; "SSY / SBIR / CLC" ≈ SHY / (likely SPY) / (unclear — treemap shows GLD, TLT); "The Stunt" = The Stand; "possessorial" ≈ course tutorial; "depth on data" = def OnData. Values cross-checked against frames where possible; "CLC" has no frame confirmation.
7. Combined-model wiring (how RNN and regression/SVM votes are merged) is not explained anywhere in the video.
