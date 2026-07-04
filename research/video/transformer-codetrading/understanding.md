# Understanding: "How I Adapted ChatGPT's Transformer Networks for Trading Prediction" (CodeTrading, ~23:45)

> Source reconstruction from `transcript.md` + all 144 frames in `frames/`
> (frames f_0620_042 … f_1650_105 covering 06:20–16:50 were missing from the original
> extraction and were re-extracted from the source mp4 with ffmpeg for this document).

## Summary

The video adapts the GPT-style "predict the next token" idea to forex price forecasting: an
encoder-only PyTorch Transformer reads a sliding window of the last 30 (default 60) hourly
EURUSD candles — each timestep a 9-feature vector (OHLC + RSI + Bollinger high/low + MA20 +
MA20 slope), MinMax-scaled — and regresses the next candle's Close price. The pipeline is:
CSV load → technical indicators (`ta` library) → feature selection + MinMax scaling → a
windowed `ForexDataset` → `TimeSeriesTransformer` (input Linear 9→64, learnable positional
embedding, 2-layer/8-head TransformerEncoder with FF=256, last-timestep Linear 64→1) →
Adam+MSE training for 20 epochs on CPU → evaluation with inverse-scaled MSE/MAE and a
real-vs-predicted Close plot. The author's honest conclusion: the predictions look good but
are essentially a lagged copy of the most recent price change (persistence behavior), because
noisy market data makes the model fit noise, not signal; he closes with concrete improvement
directions (more indicators, volume, stocks, multi-step horizons, hyperparameter tuning).

---

## REQUIREMENTS

### A. Concept & framing

- **REQ-TFM-01 — Next-price-as-next-token objective.** Treat the price series exactly like an
  LLM prompt: given a sequence of timesteps, predict the most probable next value (next
  candle) instead of the next word. [00:02–00:36] (f_0020 "ChatGPT / Word 1, word 2, word 3, …?",
  f_0030 "TradeGPT").
- **REQ-TFM-02 — Attention as the core mechanism.** Use multi-head self-attention so each
  timestep learns to weight the importance of previous timesteps; each head is a parameter
  matrix tracking a different relationship in the sequence (in text: nouns↔verbs, pronoun
  reference; in prices: current price vs. particular past sub-sequences). [01:26–02:47]
  (f_0130/f_0140: sentence "The book is on the" with green per-token weight cells 0.01, 0.8,
  0.1, 0.03, 0.01 labeled "Attention Mechanism", arrows to candidate words Table/Floor/Car/
  Apple/Door).
- **REQ-TFM-03 — "Attention Is All You Need" reference architecture.** The video shows the
  original Vaswani encoder–decoder diagram (Input Embedding + Positional Encoding → N×
  [Multi-Head Attention → Add&Norm → Feed Forward → Add&Norm] → Linear → Softmax) with the
  attention blocks highlighted; the actual build uses only the **encoder** stack. [01:50–02:20,
  11:00–11:13] (f_0150–f_0220).
- **REQ-TFM-04 — TradeGPT windowing picture.** Conceptual diagram: a highlighted window of
  candles on a chart feeds the transformer block, which must answer "?" for the next candle.
  A neural-network graph (input col → hidden cols → single output) bridges candles→NN→Python.
  [02:16–03:50] (f_0240–f_0350).
- **REQ-TFM-05 — Claimed advantage.** Transformers capture long-term dependencies better than
  LSTMs / classic RNNs; that is the motivation for trying them on trading data. [03:23–03:39]

### B. Environment & data

- **REQ-TFM-06 — Stack.** Jupyter notebook, Python, PyTorch. `pip install torch pandas numpy
  scikit-learn` and `pip install ta` (video uses the `ta` library; pandas_ta mentioned as
  alternative). [03:52–04:05] (f_0040, f_0400).
- **REQ-TFM-07 — Imports.** `numpy as np`, `pandas as pd`, `torch`, `torch.nn as nn`,
  `from torch.utils.data import Dataset, DataLoader`, `from sklearn.preprocessing import
  MinMaxScaler`, `import ta`, `import matplotlib.pyplot as plt`. (f_0410, f_1340).
- **REQ-TFM-08 — Dataset.** EURUSD 1-hour candlestick CSV, 2020–2023 (Dukascopy-style name:
  `EURUSD_Candlestick_1_Hour_BID_01.07.2020-…2023.csv`), columns include `Gmt time`, Open,
  High, Low, Close. [15:29–15:44] (f_1540, f_1720).
- **REQ-TFM-09 — Loader `load_forex_data(csv_file)`.** Read CSV → parse/cast `Gmt time` with
  `pd.to_datetime(df['Gmt time'], format='%d.%m.%Y %H:%M:%S.%f')` → `df.sort_values('Gmt
  time', inplace=True)` ("just in case") → `df.reset_index(drop=True, inplace=True)` →
  return df. [04:09–04:29] (f_0410–f_0430).

### C. Feature engineering

- **REQ-TFM-10 — Technical indicators `add_technical_indicators(df)`.** Exactly (f_0440–f_0530,
  f_2200):
  - `df['rsi'] = ta.momentum.rsi(df['Close'], window=14)`
  - `bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)`
  - `df['bb_high'] = bollinger.bollinger_hband()`; `df['bb_low'] = bollinger.bollinger_lband()`
  - `df['ma_20'] = df['Close'].rolling(window=20).mean()`
  - `df['ma_20_slope'] = df['ma_20'].diff()` (difference between consecutive MA values) [04:36–04:49]
  - NaN handling: `df.fillna(method='bfill', inplace=True)` then `df.fillna(method='ffill',
    inplace=True)`; return df.
- **REQ-TFM-11 — Extension point.** The indicator function is the designated place to add more
  indicators (EMAs, other-length MAs, custom indicators) so the transformer "reads" them.
  [04:56–05:27]
- **REQ-TFM-12 — Feature list (9 features).** Default `feature_cols = ['Open','High','Low',
  'Close','rsi','bb_high','bb_low','ma_20','ma_20_slope']` (OHLC + 5 indicator columns).
  [05:39–07:15] (f_0540–f_0600).
- **REQ-TFM-13 — Scaling `select_and_scale_features(df, feature_cols=None)`.**
  `data = df[feature_cols].values` (shape `[num_samples, num_features]`); `scaler =
  MinMaxScaler()`; `data_scaled = scaler.fit_transform(data)`; return `(data_scaled, scaler,
  feature_cols)`. Rationale stated: bound every column to the same range so no feature
  dominates by magnitude; keep the scaler for inverse-transform later. [05:56–06:22]
  (f_0540, f_0600). Note: the video fits ONE scaler on the FULL dataset before the
  train/val/test split (see Open questions).

### D. Dataset windowing (supervised setup)

- **REQ-TFM-14 — `ForexDataset(Dataset)` signature.** `__init__(self, data, seq_length=60,
  prediction_length=1, feature_dim=4, target_column_idx=3)`; stores data, seq_length,
  pred_length, feature_size, target_column_idx. Docstring: data = numpy array
  `[num_samples, num_features]`; seq_length = how many timesteps in the input sequence;
  prediction_length = how many future steps to predict; feature_dim = total number of
  features (dimension check); target_column_idx = which column is the target ("e.g., close=3").
  [06:44–07:40] (f_0630–f_0800).
- **REQ-TFM-15 — Window count.** `__len__`: "the maximum starting index is total_length −
  seq_length − prediction_length" → `return len(self.data) - self.seq_length -
  self.pred_length + 1`. (f_0740).
- **REQ-TFM-16 — Sample construction `__getitem__(idx)`.**
  - Input: `x = self.data[idx : idx + self.seq_length]` — full 9-feature rows of the last
    `seq_length` candles.
  - Label: `y = self.data[idx + self.seq_length : idx + self.seq_length + self.pred_length,
    self.target_column_idx]` — the NEXT candle's (scaled) Close.
  - `return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)` —
    torch tensors, not numpy, because they feed the transformer. Explicitly framed as
    supervised learning: labels y are shown during training; at test time the model must
    guess. [07:46–08:46] (f_0800–f_0850).
- **REQ-TFM-17 — Target definition.** Predict the closing price of the very next candle:
  `target_col_idx = feature_cols.index('Close')` (= 3), `pred_length = 1`. Multi-step (3–5
  candles ahead) is possible by raising prediction_length but harder to evaluate. [07:22,
  16:15–16:45] (f_1600–f_1640).

### E. Model architecture

- **REQ-TFM-18 — `TimeSeriesTransformer(nn.Module)` hyperparameters.** Defaults:
  `feature_size=9, num_layers=2, d_model=64, nhead=8, dim_feedforward=256, dropout=0.1,
  seq_length=30, prediction_length=1`. [08:55–10:17] (f_0900–f_1040, f_1500).
- **REQ-TFM-19 — Sizing rule of thumb.** nhead(8) × 8 = d_model(64); dim_feedforward = 4 ×
  d_model = 256; all powers of two. No strict theory — practitioner convention; if you grow
  one, grow the others proportionally (recommended, not mandatory). [09:16–09:59]
- **REQ-TFM-20 — Dropout for regularization.** `dropout=0.1` explicitly to avoid overfitting.
  [09:59]
- **REQ-TFM-21 — Sequence length choice.** seq_length shortened from 60 → 30 to speed up CPU
  training/inference; both are valid (evaluation mentions "30 or 60 rows depending on how the
  model was trained"). [10:05–10:11, 14:19–14:27]
- **REQ-TFM-22 — Input projection.** `self.input_fc = nn.Linear(feature_size, d_model)` —
  "embed each feature vector (feature_size) into a d_model-sized vector" (the numeric
  analogue of token embedding). (f_0900).
- **REQ-TFM-23 — Learnable positional encoding.** `self.pos_embedding =
  nn.Parameter(torch.zeros(1, seq_length, d_model))` — comment in code: "Positional Encoding
  (simple learnable or sinusoidal). We'll do a learnable here". Added to the projected input
  in forward. (f_0900, f_1140).
- **REQ-TFM-24 — Encoder-only transformer.**
  `encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead,
  dim_feedforward=dim_feedforward, dropout=dropout, activation="relu")`;
  `self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)`.
  8 attention heads, each focusing on a relationship between the current price and a certain
  sub-sequence of previous prices. [10:42–11:31] (f_0900, f_1050–f_1130).
- **REQ-TFM-25 — Output head.** `self.fc_out = nn.Linear(d_model, prediction_length)` —
  code comment: "Final output: we want to forecast `prediction_length` steps for 1 dimension
  (Close price). If you want multi-step and multi-dimensional, adjust accordingly." (f_0900).
- **REQ-TFM-26 — Forward pass.** (f_1050–f_1150, f_1330)
  1. `src` shape `[batch_size, seq_length, feature_size]`; `batch_size, seq_len, _ = src.shape`.
  2. Project: `x = self.input_fc(src)` → `[batch, seq_length, d_model]`.
  3. Add positional embedding (reshape/prepare step the author skims: "what comes before is
     basically reshaping the data and preparing the input of the model").
  4. Encode: `encoded = self.transformer_encoder(...)`.
  5. **Last-timestep pooling:** "We only want the output of the last time step for
     forecasting the future": `last_step = encoded[:, -1, :]` → `(batch_size, d_model)`.
  6. `out = self.fc_out(last_step)` → `(batch_size, prediction_length)`; return out.
- **REQ-TFM-27 — Architecture summary comment (in-code block above the class).** (f_1150)
  ```
  # [Input Linear: 9 -> 64]
  # [+ Positional Embedding (1, 30, 64)]
  # [Transformer Encoder]  (2 Layers, 8 Heads, FF=256)
  # [Output Linear: 64 -> 1]
  # [Prediction: (B, 1)]
  ```

### F. Training

- **REQ-TFM-28 — `train_transformer_model(model, train_loader, val_loader=None, lr=1e-3,
  epochs=20, device='cpu')`.** [12:00–13:25] (f_1200–f_1330):
  - `criterion = nn.MSELoss()` — comment "For regression on price".
  - `optimizer = torch.optim.Adam(model.parameters(), lr=lr)`.
  - `model.to(device)`; for each epoch: `model.train()`, loop `x_batch, y_batch` in
    train_loader → `.to(device)` → `optimizer.zero_grad()` → `output = model(x_batch)`
    (comment: output shape `[batch_size, prediction_length]`) → `loss = criterion(output,
    y_batch)` → `loss.backward()` → `optimizer.step()` → collect `loss.item()`;
    `mean_train_loss = np.mean(train_losses)`.
  - If `val_loader is not None`: `model.eval()`, `with torch.no_grad():` loop val batches,
    accumulate val losses, mean; print per epoch `Epoch [i/epochs], Train Loss: …, Val Loss: …`
    (else print train loss only). Return the trained model.
- **REQ-TFM-29 — Device policy.** Trains fine on CPU; `device = 'cuda' if
  torch.cuda.is_available() else 'cpu'` — switch to GPU if present. [13:05–13:19, 19:31–19:44]
  (f_1900, f_1930).
- **REQ-TFM-30 — Observed training run.** 20 epochs; log shows e.g. `Epoch [1/20] Train Loss:
  0.01116, Val Loss: 0.00006…` descending to ~`Train Loss: 0.00009, Val Loss: 0.00001` —
  losses in scaled space. (f_1900–f_2010). Author stopped/kept it short for the recording.

### G. Splitting & loaders

- **REQ-TFM-31 — Sequential (chronological) 80/10/10 split — MANDATORY.**
  `train_size = int(len(dataset) * 0.8)`; `val_size = int(len(dataset) * 0.1)`;
  `test_size = len(dataset) - train_size - val_size`;
  `train_dataset = torch.utils.data.Subset(dataset, range(0, train_size))`;
  `val_dataset = Subset(dataset, range(train_size, train_size + val_size))`;
  `test_dataset = Subset(dataset, range(train_size + val_size, len(dataset)))` —
  "Perform sequential splitting (without shuffling)". [17:02–18:36] (f_1750–f_1830).
- **REQ-TFM-32 — Anti-pattern left in on purpose.** A commented-out
  `torch.utils.data.random_split(dataset, [train_size, val_size, test_size])` line with the
  warning "don't do this": random splitting is the ML default but WRONG for time series —
  order matters, mixing points from different times biases results / leaks information.
  [17:48–18:56] (f_1820).
- **REQ-TFM-33 — DataLoaders.** `batch_size = 32`;
  `train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False)` (shuffle
  off, consistent with sequential regime — see Open questions); `val_loader` and
  `test_loader` likewise `shuffle=False`. [18:57–19:09] (f_1850, f_2310).
- **REQ-TFM-34 — Model instantiation in the driver cell.**
  `model = TimeSeriesTransformer(feature_size=len(feature_cols), num_layers=2, d_model=64,
  nhead=8, dim_feedforward=256, dropout=0.1, seq_length=seq_length,
  prediction_length=pred_length)`; then `trained_model = train_transformer_model(model,
  train_loader, val_loader, lr=1e-3, epochs=20, device=device)`. [19:09–19:57] (f_1810–f_1950).

### H. Evaluation

- **REQ-TFM-35 — `evaluate_model(model, test_loader, scaler, feature_cols, target_col_idx,
  window_width=10, start_index=0, pred_length=1, device='cpu')`.** Docstring: evaluates on
  test data, compares predictions with actual prices, plots real vs. predicted within a given
  window width and start index; params spell out that scaler is used "to inverse transform
  predictions and real values" and window_width = "number of points to plot for real vs.
  predicted prices". [13:31–14:45] (f_1340–f_1430).
- **REQ-TFM-36 — Inference loop.** `model.eval()`; `real_prices = []; predicted_prices = []`;
  `with torch.no_grad():` for each test batch: `predictions =
  model(x_batch).cpu().numpy()` (shape `[batch_size, pred_length]`), `y_batch =
  y_batch.cpu().numpy()`. (f_1440, f_2334).
- **REQ-TFM-37 — Dummy-row inverse-scaling trick.** For each sample i (f_1440, f_2334):
  ```python
  dummy_pred = np.zeros((pred_length, len(feature_cols)))
  dummy_pred[:, target_col_idx] = predictions[i]   # assign predicted future prices
  dummy_real = np.zeros((pred_length, len(feature_cols)))
  dummy_real[:, target_col_idx] = y_batch[i]       # assign real future prices
  pred_inversed = scaler.inverse_transform(dummy_pred)[:, target_col_idx]
  real_inversed = scaler.inverse_transform(dummy_real)[:, target_col_idx]
  predicted_prices.extend(pred_inversed); real_prices.extend(real_inversed)
  ```
  (MinMaxScaler inverse-transform needs full feature width, so zeros fill the other columns.)
- **REQ-TFM-38 — Metrics.** Flatten arrays; `mse = np.mean((real_prices - predicted_prices)**2)`;
  `mae = np.mean(np.abs(real_prices - predicted_prices))`; print
  `Model Evaluation: - Mean Squared Error (MSE) - Mean Absolute Error (MAE)`. Observed run:
  MSE ≈ 0.0000, MAE ≈ 0.0009 (EURUSD price units). (f_1450, f_2020).
- **REQ-TFM-39 — Plot spec.** Guard start_index bounds (warn + reset to 0);
  `end_index = min(start_index + window_width * pred_length, len(real_prices))` ("adjust for
  multi-step forecasts"); `plt.figure(figsize=(12, 6))`; real Close = dashed line with 'o'
  markers (blue), predicted Close = solid line with 'x' markers (orange); title
  `"Real vs. Predicted Close Prices (From Index {start_index}, {window_width} Windows,
  {pred_length} Steps Each)"`; xlabel "Time Steps", ylabel "Close Price", legend, show.
  (f_1450, f_1520).
- **REQ-TFM-40 — Evaluation call used.** `evaluate_model(trained_model, test_loader, scaler,
  feature_cols, target_col_idx, window_width=45, start_index=70, pred_length=1,
  device=device)` → plot "(From Index 70, 45 Windows, 1 Steps Each)", EURUSD range ≈
  1.076–1.092. [20:11–20:22] (f_2020–f_2130).

### I. Findings, failure modes & improvement roadmap (requirements for any redesign)

- **REQ-TFM-41 — Persistence/lag failure diagnosis.** Visual inspection shows predictions
  ≈ copy of the most recent real change shifted one step: each predicted move replicates the
  previous real move (rise→predicted rise next step, drop→predicted drop next step). Looks
  accurate by MSE/MAE but has no genuine predictive power. Any serious evaluation MUST test
  against this naive-persistence baseline / lag artifact. [20:23–21:49] (f_2030–f_2250 zooms).
- **REQ-TFM-42 — Noise-vs-signal root cause.** Trading data is jumpy and non-repetitive; a
  model expressive enough to capture detail captures noise ("trying to fit noise more than
  signal") — the stated main reason neural networks fail at this task, and why simpler models
  often perform better in trading. Redesigns must include denoising / regularization /
  simplicity bias. [22:07–22:45]
- **REQ-TFM-43 — Input insufficiency.** Only 3 indicator families + OHLC were provided —
  acknowledged as "not enough to actually come up with a prediction"; richer inputs are a
  prerequisite for real predictive power. [21:49–22:07]
- **REQ-TFM-44 — Improvement roadmap (explicit list).** (a) add more/custom technical
  indicators; (b) change sequence length; (c) tune model hyperparameters (layers, heads,
  d_model, ff, dropout, lr, epochs); (d) try stocks data instead of forex; (e) add volume /
  centralized volume data; (f) extend prediction_length to 3–5 future candles (with the
  caveat that multi-step evaluation is harder). [16:29–16:45, 22:45–23:18]
- **REQ-TFM-45 — Reproducibility.** Full notebook code is distributed via download link; the
  design goal is copy-paste-runnable functions (load → indicators → scale → dataset → model
  → train → evaluate) with a single driver cell where all parameters are overridden/tuned.
  [00:58–01:07, 15:19–15:29] (f_0100 "<CODE> Download Link In Description").

---

## Architecture diagram (as built in the video)

```
CSV (EURUSD 1H, 2020-2023)
   │  load_forex_data: parse 'Gmt time', sort, reset_index
   ▼
add_technical_indicators: rsi(14), bb_high/bb_low(20,2), ma_20, ma_20_slope, bfill+ffill
   ▼
select_and_scale_features: 9 cols [O,H,L,C,rsi,bb_high,bb_low,ma_20,ma_20_slope]
   │  MinMaxScaler.fit_transform  → data_scaled [N, 9], scaler kept
   ▼
ForexDataset (seq_length=30, pred_length=1, target=Close idx 3)
   │  x: [30, 9] window   y: [1] next scaled Close     (float32 tensors)
   ▼  sequential Subset split 80/10/10 → DataLoaders (batch 32, no shuffle)
┌──────────────────────────────────────────────────────────────┐
│ TimeSeriesTransformer                                        │
│  src [B, 30, 9]                                              │
│   ├─ input_fc: Linear(9 → 64)                 [B, 30, 64]    │
│   ├─ + pos_embedding: Parameter(1, 30, 64)  (learnable)      │
│   ├─ TransformerEncoder × 2 layers                           │
│   │    └─ EncoderLayer(d_model=64, nhead=8,                  │
│   │         dim_feedforward=256, dropout=0.1, act=relu)      │
│   ├─ take last timestep  encoded[:, -1, :]    [B, 64]        │
│   └─ fc_out: Linear(64 → 1)                   [B, 1]         │
└──────────────────────────────────────────────────────────────┘
   ▼
train: MSELoss + Adam(lr=1e-3), 20 epochs, CPU (cuda if available), val loop each epoch
   ▼
evaluate: predictions → dummy-row inverse MinMax → MSE / MAE +
          plot real (dashed·o) vs predicted (solid·x) Close, window_width=45, start_index=70
   ▼
finding: near-persistence output (copies last delta) → noise-fitting, needs richer
         inputs / baselines / regularization
```

## Condensed faithful code transcription

```python
# pip install torch pandas numpy scikit-learn ; pip install ta
import numpy as np, pandas as pd, torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
import ta
import matplotlib.pyplot as plt

def load_forex_data(csv_file):
    df = pd.read_csv(csv_file)
    df['Gmt time'] = pd.to_datetime(df['Gmt time'], format='%d.%m.%Y %H:%M:%S.%f')
    df.sort_values('Gmt time', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def add_technical_indicators(df):
    df['rsi'] = ta.momentum.rsi(df['Close'], window=14)
    bollinger = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['bb_high'] = bollinger.bollinger_hband()
    df['bb_low']  = bollinger.bollinger_lband()
    df['ma_20'] = df['Close'].rolling(window=20).mean()
    df['ma_20_slope'] = df['ma_20'].diff()
    df.fillna(method='bfill', inplace=True)
    df.fillna(method='ffill', inplace=True)
    return df

def select_and_scale_features(df, feature_cols=None):
    if feature_cols is None:   # default: O,H,L,C and indicators
        feature_cols = ['Open','High','Low','Close',
                        'rsi','bb_high','bb_low','ma_20','ma_20_slope']
    data = df[feature_cols].values            # [num_samples, num_features]
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data)
    return data_scaled, scaler, feature_cols

class ForexDataset(Dataset):
    def __init__(self, data, seq_length=60, prediction_length=1,
                 feature_dim=4, target_column_idx=3):
        self.data = data
        self.seq_length = seq_length
        self.pred_length = prediction_length
        self.feature_dim = feature_dim
        self.target_column_idx = target_column_idx
    def __len__(self):
        return len(self.data) - self.seq_length - self.pred_length + 1
    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_length]
        y = self.data[idx + self.seq_length : idx + self.seq_length + self.pred_length,
                      self.target_column_idx]
        return (torch.tensor(x, dtype=torch.float32),
                torch.tensor(y, dtype=torch.float32))

class TimeSeriesTransformer(nn.Module):
    def __init__(self, feature_size=9, num_layers=2, d_model=64, nhead=8,
                 dim_feedforward=256, dropout=0.1, seq_length=30, prediction_length=1):
        super().__init__()
        self.input_fc = nn.Linear(feature_size, d_model)
        # learnable positional encoding (not sinusoidal)
        self.pos_embedding = nn.Parameter(torch.zeros(1, seq_length, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=dropout, activation="relu")
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer,
                                                         num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, prediction_length)
    def forward(self, src):                    # [B, seq_length, feature_size]
        x = self.input_fc(src)                 # -> [B, seq, d_model]
        x = x + self.pos_embedding             # (+ reshape/prep, skimmed in video)
        encoded = self.transformer_encoder(x)
        last_step = encoded[:, -1, :]          # (B, d_model)  last time step only
        return self.fc_out(last_step)          # (B, prediction_length)

def train_transformer_model(model, train_loader, val_loader=None,
                            lr=1e-3, epochs=20, device='cpu'):
    criterion = nn.MSELoss()                   # regression on price
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.to(device)
    for epoch in range(epochs):
        model.train(); train_losses = []
        for x_batch, y_batch in train_loader:
            x_batch, y_batch = x_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            output = model(x_batch)            # [B, prediction_length]
            loss = criterion(output, y_batch)
            loss.backward(); optimizer.step()
            train_losses.append(loss.item())
        mean_train_loss = np.mean(train_losses)
        if val_loader is not None:
            model.eval(); val_losses = []
            with torch.no_grad():
                for x_val, y_val in val_loader:
                    x_val, y_val = x_val.to(device), y_val.to(device)
                    val_losses.append(criterion(model(x_val), y_val).item())
            print(f"Epoch [{epoch+1}/{epochs}] Train Loss: {mean_train_loss:.6f} "
                  f"Val Loss: {np.mean(val_losses):.6f}")
    return model

def evaluate_model(model, test_loader, scaler, feature_cols, target_col_idx,
                   window_width=10, start_index=0, pred_length=1, device='cpu'):
    model.eval(); real_prices, predicted_prices = [], []
    with torch.no_grad():
        for x_batch, y_batch in test_loader:
            x_batch = x_batch.to(device)
            predictions = model(x_batch).cpu().numpy()   # [B, pred_length]
            y_batch = y_batch.cpu().numpy()
            for i in range(len(predictions)):
                dummy_pred = np.zeros((pred_length, len(feature_cols)))
                dummy_pred[:, target_col_idx] = predictions[i]
                dummy_real = np.zeros((pred_length, len(feature_cols)))
                dummy_real[:, target_col_idx] = y_batch[i]
                pred_inv = scaler.inverse_transform(dummy_pred)[:, target_col_idx]
                real_inv = scaler.inverse_transform(dummy_real)[:, target_col_idx]
                predicted_prices.extend(pred_inv); real_prices.extend(real_inv)
    real_prices = np.array(real_prices).flatten()
    predicted_prices = np.array(predicted_prices).flatten()
    mse = np.mean((real_prices - predicted_prices) ** 2)
    mae = np.mean(np.abs(real_prices - predicted_prices))
    print(f"Model Evaluation:\n - Mean Squared Error (MSE): {mse:.4f}")
    print(f" - Mean Absolute Error (MAE): {mae:.4f}")
    if start_index < 0 or start_index >= len(real_prices):
        print(f"Warning: start_index {start_index} is out of bounds. Using 0 instead.")
        start_index = 0
    end_index = min(start_index + window_width * pred_length, len(real_prices))
    plt.figure(figsize=(12, 6))
    plt.plot(range(start_index, end_index), real_prices[start_index:end_index],
             label="Real Close Prices", linestyle="dashed", marker="o")
    plt.plot(range(start_index, end_index), predicted_prices[start_index:end_index],
             label="Predicted Close Prices", linestyle="-", marker="x")
    plt.title(f"Real vs. Predicted Close Prices (From Index {start_index}, "
              f"{window_width} Windows, {pred_length} Steps Each)")
    plt.xlabel("Time Steps"); plt.ylabel("Close Price"); plt.legend(); plt.show()

# ---------------- driver cell ----------------
csv_file = "EURUSD_Candlestick_1_Hour_BID_01.07.2020-…2023.csv"
df = load_forex_data(csv_file)
df = add_technical_indicators(df)
data_scaled, scaler, feature_cols = select_and_scale_features(df)
target_col_idx = feature_cols.index('Close')

seq_length = 30
pred_length = 1        # forecast next 1 candle (adjust to 3 or 5 if needed)
dataset = ForexDataset(data_scaled, seq_length, pred_length,
                       len(feature_cols), target_col_idx)

# Train/Validation/Test Split (80% train, 10% val, 10% test)
train_size = int(len(dataset) * 0.8)
val_size   = int(len(dataset) * 0.1)
test_size  = len(dataset) - train_size - val_size
# !!! don't use this !!!  (random split leaks/biases time series)
# train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
#     dataset, [train_size, val_size, test_size])
# Perform sequential splitting (without shuffling)
train_dataset = torch.utils.data.Subset(dataset, range(0, train_size))
val_dataset   = torch.utils.data.Subset(dataset, range(train_size, train_size + val_size))
test_dataset  = torch.utils.data.Subset(dataset, range(train_size + val_size, len(dataset)))

batch_size = 32
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False)
val_loader   = DataLoader(val_dataset,   batch_size=batch_size, shuffle=False)
test_loader  = DataLoader(test_dataset,  batch_size=batch_size, shuffle=False)

model = TimeSeriesTransformer(
    feature_size=len(feature_cols), num_layers=2, d_model=64, nhead=8,
    dim_feedforward=256, dropout=0.1,
    seq_length=seq_length, prediction_length=pred_length)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
trained_model = train_transformer_model(model, train_loader, val_loader,
                                        lr=1e-3, epochs=20, device=device)
evaluate_model(trained_model, test_loader, scaler, feature_cols, target_col_idx,
               window_width=45, start_index=70, pred_length=1, device=device)
```

## Open questions (not invented — genuinely unresolved from the 240p source)

1. **Exact CSV end date** in the filename (`…01.07.2020-??.07.2023.csv`) is unreadable at
   240p; transcript only says "between 2020 and 2023".
2. **Scaler leakage:** `MinMaxScaler.fit_transform` is applied to the FULL dataset before the
   80/10/10 split (visible in code order). The video never discusses this; unclear if
   intentional. A redesign should fit the scaler on train only.
3. **`batch_first` handling:** whether `nn.TransformerEncoderLayer(batch_first=True)` is set
   or the forward permutes to `[seq, batch, d_model]` is in the skimmed "reshaping" lines the
   author explicitly did not walk through; the exact tensor-prep lines are not fully legible.
4. **Causal masking:** no attention mask is visible/mentioned — the encoder appears to attend
   bidirectionally within the 30-step window (fine for last-step regression, but unstated).
5. **`train_loader` shuffle flag:** rendered as `shuffle=False` at 240p (consistent with the
   "sequential, no shuffling" narrative) but the token is at the edge of legibility.
6. **Early stopping / stopping the run:** the author says he "had to stop it a bit quickly"
   for the recording — unclear whether the shown metrics come from all 20 epochs or a
   truncated run.
7. **`feature_dim=4` default vs 9 features:** the ForexDataset default (4, i.e. OHLC-only)
   vs the driver passing `len(feature_cols)=9` — the default's origin story (an earlier
   OHLC-only iteration?) is never explained.
8. **Exact MSE decimals:** printed MSE displays as `0.0000` at 4 decimal places (true value
   below print precision); exact value not recoverable.
