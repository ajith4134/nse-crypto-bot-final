# MASTER REQUIREMENTS — Ultra-Advanced Trading Neural-Network Redesign

Consolidated from 8 video requirement documents (211 requirements total). Every REQ id
appears exactly once in the theme groups below; the dedup table maps them to canonical
CANON ids that the design phase traces against.

Source key:
| Tag | Video | Path | REQs |
|---|---|---|---|
| NNM | "NN Trading in Minutes" (QuantProgram, ~21m) | nn-in-minutes/understanding.md | 32 |
| PNP | "Python NN Price Prediction" (~19m) | python-nn-price/understanding.md | 30 |
| LSTM | "LSTM Price Movement" (CodeTrading, ~15m) | lstm-codetrading/understanding.md | 22 |
| TFM | "Transformer for Trading" (CodeTrading, ~24m) | transformer-codetrading/understanding.md | 45 |
| KRF | "AI Learns Stock Patterns" (Krafer, ~16m) | krafer-patterns/understanding.md | 27 |
| GRC | "NN from Scratch" (Green Code, ~9m) | greencode-scratch/understanding.md | 29 |
| JKA | "NN that Trades Stocks" (Joshua Kyan Aalampour, 24s) | joshua-trades/understanding.md | 14 |
| RBT | "Neural Nets Robot Learning to Trade" (15s, silent) | robot-learning/understanding.md | 12 |

---

## 1. THEME GROUPS (all 211 REQs, each exactly once)

### T1. Market-mechanics premises & scope (5)

- **KRF-01** — Chart patterns are order-book/liquidity math, not trader psychology; model them mechanically. [KRF]
- **KRF-03** — Any pattern reduces to "blocks and gaps" in the order book; model gap-fill tendency explicitly. [KRF]
- **KRF-04** — More efficient/liquid markets show fewer patterns; pattern edge lives in short-horizon/less-liquid regimes. [KRF]
- **KRF-06** — Psychology-free order-matching market simulator as a training/test environment (still produces gaps/patterns). [KRF]
- **KRF-27** — Determinism study: statistically quantify chart/order-book predictability, independent of any model. [KRF]

### T2. Data & timeframes (6)

- **NNM-13** — Single-symbol SPY daily; train-history vs backtest windows (2000–2009 train, 2010–2024 test), $100k cash. [NNM]
- **PNP-07** — EUR/USD daily ASK candles 2003–2021 (~4734 rows, OHLCV CSV). [PNP]
- **LSTM-01** — yfinance ^RUI daily 2012–2022; daily chosen explicitly as "less noisy"; applies to stocks or crypto. [LSTM]
- **TFM-08** — EURUSD 1-hour Dukascopy-style CSV, 2020–2023. [TFM]
- **KRF-13** — Real BTC 1-minute data, ~51,773 rows (~35 days, ~17 MB). [KRF]
- **KRF-05** — Use ML prediction only on SHORT timeframes (1-minute); long horizons are macro/psychology-dominated. [KRF]
  - ⚠ **Tension:** KRF-05 (1m only, quant firms confirm short-TF-only AI) vs LSTM-01/NNM-13/PNP-07 (daily deliberately chosen as less noisy). Both must be supported; resolve empirically per segment.

### T3. Data hygiene, preprocessing, scaling & windowing (18)

- **PNP-08** — Drop zero-volume rows, reset index, verify no NAs; dropna after indicator/target NaNs. [PNP]
- **PNP-09** — Column rename to capitalized OHLCV for backtesting.py compatibility. [PNP]
- **LSTM-02** — Inspect raw frame; drop all-zero Volume column as valueless. [LSTM]
- **LSTM-05** — dropna, reset_index, drop Volume/Close/Date (keep Adj Close). [LSTM]
- **LSTM-06** — Materialize explicit model matrix (`data_set = data.iloc[:, 0:11]`) and inspect it. [LSTM]
- **TFM-09** — Loader: parse timestamps with explicit format, sort by time, reset index. [TFM]
- **NNM-16** — StandardScaler fit+transform of features so large-magnitude features don't dominate. [NNM]
- **LSTM-07** — MinMax-scale ALL columns to [0,1] together for the NN (column order tracked manually). [LSTM]
- **TFM-13** — `select_and_scale_features`: MinMaxScaler on feature matrix, keep the scaler for inverse transform. [TFM]
  - ⚠ **Tension:** LSTM-07/TFM-13 fit the scaler on the FULL dataset before the split (leakage, flagged in both docs' open questions) vs proper train-only fitting. Redesign fits on train only.
- **PNP-17** — One-hot encode categorical signal features (pd.get_dummies). [PNP]
- **LSTM-08** — Explicit input/target column split (first 8 cols input, last col target; -1/-2 selects regression/classification). [LSTM]
- **LSTM-10** — Sliding-window 3-D tensor construction (loop + np.moveaxis), lookback windows over feature columns. [LSTM]
- **LSTM-11** — Mandatory shape verification: X=(N, backcandles, features), y=(N,1); wrong dims break the LSTM. [LSTM]
- **TFM-14** — Windowed `ForexDataset` with seq_length, prediction_length, feature_dim, target_column_idx params. [TFM]
- **TFM-15** — Correct window count: `len(data) − seq_length − pred_length + 1`. [TFM]
- **TFM-16** — `__getitem__`: x = seq_length full-feature rows; y = next pred_length scaled Closes; float32 torch tensors. [TFM]
- **JKA-04** — 64×12 feature window per decision (64 lookback bars × 12 features). [JKA]
- **GRC-23** — Input flattening for dense nets (28×28 → 784 vector). [GRC]

### T4. Model architectures (46)

#### From-scratch NumPy core (19)
- **GRC-01** — From-scratch constraint: numpy + Python only, no ML frameworks. [GRC]
- **GRC-02** — Build progression: neuron → layers → network → real tasks. [GRC]
- **GRC-03** — Neuron = Σ(input·weight) + bias. [GRC]
- **GRC-04** — Learning = tweaking weights & bias until output is right. [GRC]
- **GRC-06** — Layer value propagation: each neuron = weighted sum of ALL previous-layer neurons + bias. [GRC]
- **GRC-07** — Vectorize the whole layer as one `np.dot(layers[-1], W[i]) + b[i]`. [GRC]
- **GRC-08** — Seeded small random init (`0.01 * randn`), zero biases; untrained softmax ≈ uniform. [GRC]
- **GRC-09** — Stacked linear layers collapse to one line — non-linearity is mandatory. [GRC]
- **GRC-10** — ReLU on every hidden layer (`max(0,x)`). [GRC]
- **GRC-11** — Numerically-stable softmax output layer (subtract row max). [GRC]
- **GRC-12** — Full forward pass keeping every intermediate activation + layer-type tags for backprop. [GRC]
- **GRC-16** — Backprop = per-weight partial derivatives computed backwards through the network. [GRC]
- **GRC-17** — Credit assignment intuition ("team of chefs"): update each weight ∝ its contribution to the error. [GRC]
- **GRC-14** — Categorical cross-entropy loss as the classification error signal. [GRC]
- **NNM-12** — No-library RNN: equations hand-written with NumPy + StandardScaler, for transparency/modifiability. [NNM]
- **NNM-03** — Back-propagation & forward pass mechanics (error flows back through H2→H1→input weights). [NNM]
- **NNM-17** — Seeded weight/bias init: `randn*0.01` for Wxh/Whh/Why, zero bh/by. [NNM]
- **NNM-19** — RNN forward propagation: hidden states appended per time step; returns y + hidden_states. [NNM]
- **NNM-20** — Full BPTT backward pass with tanh derivative and gradient clipping ±5, SGD update. [NNM]

#### From-scratch validation tasks (5)
- **GRC-13** — Validate forward pass with externally (PyTorch)-trained weights before writing backprop (97.53%). [GRC]
- **GRC-22** — MNIST spec: 60k 28×28 images, 10 classes — the known-answer validation task. [GRC]
- **GRC-25** — Interactive inference on hand-drawn inputs with full probability vector + argmax printed. [GRC]
- **GRC-28** — Dataset-agnostic implementation: same code retrained on Fashion-MNIST → 87%. [GRC]
- **GRC-29** — Fashion inference demos + True/Pred misclassification grid re-run on the new dataset. [GRC]

#### RNN / LSTM (7)
- **NNM-01** — Feed-forward NN concept: input→hidden→output, random init, error term, repeat until correct. [NNM]
- **NNM-04** — RNN = FNN + memory via BPTT; hidden state per time step for sequence data. [NNM]
- **NNM-05** — "I like to drink coffee" hidden-state table: h(t) = f(input(t), h(t−1)); predict at t5 from h4. [NNM]
- **NNM-08** — RNN vanishing gradient → LSTM forget gate keeps important distant past. [NNM]
- **NNM-15** — RNN parameter block: lookback=10, feature_count=2, hidden_size=64, lr=0.01, prediction sign drives direction. [NNM]
- **LSTM-13** — Keras/TF import stack (Sequential/Model, LSTM/Dense/Input/Activation, Adam; optional seeds). [LSTM]
- **LSTM-14** — Functional-API model: Input(backcandles,8) → LSTM(150) → Dense(1) → Activation('linear'), Adam+MSE. [LSTM]

#### Transformer (11)
- **TFM-02** — Multi-head self-attention as core mechanism; each head tracks a different sequence relationship. [TFM]
- **TFM-03** — "Attention Is All You Need" reference; build uses encoder stack only. [TFM]
- **TFM-05** — Motivation: transformers capture long-term dependencies better than LSTM/RNN. [TFM]
- **TFM-18** — TimeSeriesTransformer defaults: feature_size=9, layers=2, d_model=64, nhead=8, ff=256, dropout=0.1, seq=30. [TFM]
- **TFM-19** — Sizing convention: nhead×8=d_model; ff=4×d_model; powers of two; grow proportionally. [TFM]
- **TFM-22** — Input projection Linear(feature_size→d_model) — numeric token embedding. [TFM]
- **TFM-23** — Learnable positional embedding Parameter(1, seq_length, d_model). [TFM]
- **TFM-24** — Encoder-only nn.TransformerEncoder (relu activation, 8 heads, N layers). [TFM]
- **TFM-25** — Output head Linear(d_model → prediction_length). [TFM]
- **TFM-26** — Forward pass: project → +pos → encode → last-timestep pooling `encoded[:, -1, :]` → fc_out. [TFM]
- **TFM-27** — In-code architecture summary comment block (9→64, +pos(1,30,64), encoder 2L/8H/FF256, 64→1). [TFM]

#### MLP / Keras (2)
- **PNP-19** — sklearn MLPClassifier exact construction (hidden_layer_sizes tuple, relu, max_iter=1000, seed, chrono split). [PNP]
- **KRF-15** — Keras Sequential Flatten→Dense(relu) template as the supervised model pattern. [KRF]

#### TCN / NEAT / future (4)
- **JKA-05** — Causal Temporal Convolutional Network (dilated causal 1-D convs, no future leakage) producing window embedding. [JKA]
- **RBT-05** — NEAT-style variable, evolvable topology; node count grows over evolution; complexity is a displayed scalar. [RBT]
- **KRF-23** — Diffusion-model candle-sequence predictor (iteratively refine the same guess) — declared future work. [KRF]
- **NNM-29** — Support the full five-model family: regression, decision tree, SVM, RNN, LSTM. [NNM]

### T5. Feature engineering & indicators (13)

- **NNM-14** — Indicators + warm-up: RSI(2), SMA(9), SMA(200), SetWarmUp(200); readiness gates trading. [NNM]
- **PNP-03** — Candidate input concept set: RSI, MA slope, parabolic-SAR slope, any custom strategy signal. [PNP]
- **PNP-04** — Custom reversal signal admitted as feature BECAUSE it was independently profitable standalone. [PNP]
- **PNP-10** — Fractal support/resistance detectors (n1 bars into / n2 bars out of candle l, low/high monotonicity). [PNP]
- **PNP-11** — Candlestick pattern detectors: isStar (shooting star / hammer via wick-body ratios), isEngulfing. [PNP]
- **PNP-12** — Combined signal: bullish pattern near support / bearish near resistance within pip tolerance. [PNP]
- **PNP-16** — RSI(16) via pandas_ta as the numeric ML feature. [PNP]
- **LSTM-03** — pandas_ta indicators: RSI(15) + EMA fast/medium/slow (20/100/150); explicitly user-tunable. [LSTM]
- **LSTM-19** — Extension features: more indicators, MA slope direction, momentum column, custom indicators. [LSTM]
- **TFM-10** — `add_technical_indicators`: rsi(14), Bollinger high/low (20,2), ma_20, ma_20_slope; bfill+ffill. [TFM]
- **TFM-11** — Indicator function is the designated extension point for arbitrary new features. [TFM]
- **TFM-12** — 9-feature default vector per timestep: OHLC + rsi + bb_high + bb_low + ma_20 + ma_20_slope. [TFM]
- **KRF-02** — Classical pattern taxonomy (reversal/continuation/bilateral) as a feature-generator emitting entry/stop/target levels. [KRF]

### T6. Targets & labeling (10)

- **NNM-06** — Sequence-to-trading mapping: inputs per step = price+RSI (freely choosable), target = 5th-day return / ± movement. [NNM]
- **PNP-02** — Prefer trend-DIRECTION targets over trend-REVERSAL targets; pair reversal models with risk management. [PNP]
- **PNP-05** — Classifier framing: predict trend category (3 classes), not price regression. [PNP]
- **PNP-14** — Barrier-style 3-class target: ±250 pips within N bars → up/down/unclear (SLTPRatio-parameterized). [PNP]
- **PNP-15** — 30-bar horizon + MANDATORY class-balance histogram check (majority-class pitfall). [PNP]
- **LSTM-04** — Three target constructions: next-candle open→close distance, its 1/0 class, next-day Adj Close (regression used). [LSTM]
- **TFM-01** — Next-price-as-next-token objective: treat the series like an LLM prompt, predict the next candle. [TFM]
- **TFM-17** — Target = next candle's Close (pred_length=1); multi-step possible but harder to evaluate. [TFM]
- **KRF-14** — Model predicts exactly ONE number per forward pass: next 1-minute candle close (like one token). [KRF]
- **JKA-06** — Embedding mapped to next-bar directional (up) probability. [JKA]
  - ⚠ **Tension:** regression-on-price targets (LSTM-04/TFM-17/KRF-14) vs classification/probability targets (PNP-05/NNM-06/JKA-06). Both lanes are required; direction-probability is what sizing consumes (JKA), price-path is what autoregressive rollout consumes (KRF).

### T7. Training discipline (32)

#### Chronological splits (6)
- **NNM-18** — Train on 2000–2009 history, test = 2010–2024 backtest itself; shiftable windows. [NNM]
- **LSTM-12** — Chronological (non-shuffled) 80/20 slice split. [LSTM]
- **TFM-31** — Sequential 80/10/10 train/val/test split via ordered Subsets — MANDATORY. [TFM]
- **TFM-32** — Anti-pattern documented in-code: `random_split` is WRONG for time series (leaks/biases). [TFM]
- **TFM-33** — DataLoaders with shuffle=False everywhere, batch_size=32. [TFM]
- **LSTM-15** — Training call: batch_size=15, epochs=30, shuffle=True, ~10% validation_split. [LSTM]
  - ⚠ **Tension:** LSTM-15 shuffles training windows (after a chronological split) while TFM-33 forbids shuffle entirely. Shuffling *within train* after chrono split is defensible; the design must decide and document.

#### Loop, losses, optimizers (10)
- **NNM-02** — Iterations = epochs; a tunable training parameter. [NNM]
- **NNM-21** — Track epoch loss every iteration; more epochs = better fit but more compute. [NNM]
- **GRC-15** — Canonical cycle: forward → loss → backward → update, repeated. [GRC]
- **GRC-18** — Learning rate semantics: too high stumbles; want big-then-small steps. [GRC]
- **GRC-19** — Plain SGD chosen; momentum/AdaGrad/RMSProp consciously skipped. [GRC]
  - ⚠ **Tension:** GRC-19 (plain SGD suffices) vs TFM-28/LSTM-14 (Adam default). Design default: Adam; SGD retained in the from-scratch core.
- **GRC-24** — Mini-batch training loop (batch slicing, periodic accuracy/loss logging) lifted 40–50% → 97.42%. [GRC]
- **TFM-20** — dropout=0.1 explicitly for overfitting control. [TFM]
- **TFM-28** — train function: MSELoss + Adam(lr=1e-3), epochs=20, per-epoch val loop with printed Train/Val loss. [TFM]
- **TFM-30** — Observed loss trajectory logging in scaled space (train + val per epoch). [TFM]
- **KRF-16** — Gradient descent on ONE model + one dataset beats 200 random GA agents; hours-long runs acceptable. [KRF]

#### Hyperparameter search & topology experiments (13)
- **NNM-09** — Memory-vector size 64 as capacity dial (64→128→256 = capacity vs compute). [NNM]
- **NNM-10** — Explicit tunable set: input features, epochs, hidden size, learning rate, lookback, train/test windows. [NNM]
- **PNP-06** — Hidden topology is an open hyperparameter found by trial-and-error; no clean rule exists. [PNP]
- **PNP-21** — Experiment 1: (20,20,10,10) → Train 52.7% / Test 33.2%. [PNP]
- **PNP-22** — Experiment 2: (2,2) → single-class collapse; global accuracy cannot detect degeneracy, confusion matrix can. [PNP]
- **PNP-24** — Heuristic: nodes-per-layer ≥ input count (better 2×); (8,8,4) narrowing toward output classes. [PNP]
- **PNP-25** — Experiment 4: (20,20,50,30) → minority class starts being predicted (precision 0.45, recall 0.05). [PNP]
- **PNP-26** — Experiment 5: (50,50,60,30,9) bottleneck → track per-class precision/recall, not just accuracy. [PNP]
- **PNP-27** — Tuning protocol: iterative reruns of the same cell observing accuracy+confusion each time. [PNP]
- **LSTM-09** — Lookback (`backcandles`) must be an easily-changed experiment knob (4→6→10→30). [LSTM]
- **LSTM-18** — Rerun full pipeline with backcandles=30; lookback sensitivity is part of the study. [LSTM]
- **TFM-21** — seq_length 60→30 tradeoff for CPU speed; both valid. [TFM]
- **GRC-27** — Notebook "Notes" cell logging experiment settings/results per run. [GRC]

#### Debugging & validation practice (3)
- **GRC-20** — The backwards(y)-vs-backwards(output) bug: backward pass must receive the forward OUTPUT. [GRC]
- **GRC-21** — Diagnose training with loss/accuracy-vs-step plots; sanity-check on small data BEFORE real datasets. [GRC]
- **KRF-16 is above; GRC-13 in T4.** —

### T8. Evaluation & honesty gates (26)

#### Baselines & anti-delusion (5)
- **TFM-41** — Persistence/lag diagnosis: predictions that copy the last delta look great by MSE but have zero predictive power; ALWAYS test vs naive-persistence baseline. [TFM]
- **LSTM-20** — Skepticism requirement: tracking-looking overlay is deceptive; model must NOT be used as-is; failure analysis first. [LSTM]
- **PNP-23** — Naive-baseline rule: 3-class majority ≈33–35%; require ~45–50%+ before trusting for trading. [PNP]
- **PNP-13** — Feature admission gate: validate any custom signal with a classic backtest (rising equity, +126%) before feeding it to ML. [PNP]
- **NNM-30** — Overfitting telemetry: track anti-overfit signals (backtest count, parameter count) alongside results. [NNM]

#### Classification evaluation (2)
- **PNP-20** — Always report train AND test accuracy + confusion matrices + classification reports for both. [PNP]
- **GRC-26** — Misclassification gallery (True/Pred tiles) to confirm errors are understandable. [GRC]

#### Regression evaluation (6)
- **LSTM-16** — Predict on the held-out test set only (data the model never saw). [LSTM]
- **TFM-35** — evaluate_model harness: test-set comparison with plot window params, inverse transform via kept scaler. [TFM]
- **TFM-36** — Inference loop: eval mode, no_grad, batch predictions to numpy. [TFM]
- **TFM-37** — Dummy-row inverse-MinMax trick to recover price units for target column only. [TFM]
- **TFM-38** — Metrics: MSE + MAE on inverse-scaled real vs predicted prices. [TFM]
- **TFM-40** — Concrete evaluation call convention (window_width, start_index, pred_length). [TFM]

#### Trading-grade scorecards & gates (9)
- **NNM-23** — All results include commissions/fees. [NNM]
- **NNM-24** — Primary gate: CAGR ÷ MaxDD must beat buy-and-hold benchmark (SPX 10/55 = 0.18) before execution. [NNM]
- **NNM-25** — Full scorecard fields: PSR, Sharpe, Sortino, orders, avg win/loss, CAGR, DD, expectancy, win/loss rate, equity. [NNM]
- **JKA-12** — Compact backtest panel: SHARPE, TRADES, MAX DD, CAGR, EQUITY(+delta), LAST PNL, named year. [JKA]
- **RBT-08** — Headline trade-quality line: win-rate %, win/loss counts, avg-win/avg-loss ratio, avg win vs avg loss values. [RBT]
- **RBT-10** — Always-visible per-trade economics: round-trip count + average $ per round-trip. [RBT]
- **KRF-10** — Fitness/eval MUST use total (realized + unrealized, mark-to-market) PnL — realized-only lets agents hide losses. [KRF]
- **RBT-03** — Named fitness: profit-per-trade × minimize-underwater (drawdown-aware), not raw total profit. [RBT]
- **RBT-12** — Learning direction: improve trade QUALITY even at cost of fewer trades ($/trade up, losses shrink). [RBT]

#### Out-of-sample & live honesty (4)
- **KRF-17** — Rolling accuracy-over-time script drives iterative model improvement. [KRF]
- **KRF-20** — Test on truly unseen LIVE data (pulled days ago, cannot be in training). [KRF]
- **JKA-02** — Spoken performance claims without on-screen evidence are unverified — never trust or emit such claims. [JKA]
- **JKA-14** — Label system maturity honestly ("still a lot to learn" / early-stage). [JKA]

### T9. Autoregressive & multi-step forecasting (3)

- **KRF-18** — GPT-style autoregressive rollout: feed predicted candle back into the window to generate k future candles. [KRF]
- **KRF-21** — Long-horizon variant (KAT 1.4): tuned for large, lengthy moves rather than the next tick. [KRF]
- **KRF-22** — Roadmap: direct multi-candle-at-once vector output head (KAT 3), not only autoregressive rollout. [KRF]

### T10. Risk overlay & sizing (5)

- **JKA-07** — A dedicated risk-map layer between probability and order is the "real secret sauce" (not the predictor). [JKA]
- **JKA-08** — Neutral-zone dead band: abstain when probability is near 0.5. [JKA]
- **JKA-09** — Position size ∝ signal / forecast volatility (vol-targeting; explicit vol forecast input). [JKA]
- **JKA-10** — Hard exposure/leverage cap applied after scaling. [JKA]
- **NNM-26** — Leverage headroom logic: CAGR/MaxDD ≫ benchmark permits ~2× leverage while staying under benchmark DD. [NNM]

### T11. Strategy integration & execution (7)

- **NNM-11** — Three NN use cases: entry/exit condition, improve existing strategy (cut drawdowns), rebalance portfolio. [NNM]
- **NNM-22** — Live loop gating: skip bars until warm-up done and all indicators ready; prediction sign → long/short. [NNM]
- **NNM-31** — LSTM + covariance-matrix portfolio optimization/rebalancing across SPY/GLD/TLT/SHY (Markowitz baseline). [NNM]
- **NNM-32** — NN as strategy-improver on top of an existing strategy, not only a raw signal generator. [NNM]
- **JKA-01** — End-to-end pipeline: signal → sizing → trades (one system owns the whole chain). [JKA]
- **JKA-03** — Per-bar inference: model runs on EVERY bar (bar-driven event loop). [JKA]
- **RBT-04** — Strategy identity bound to venue/instrument ("Strategy_MM BITMEX" — per-segment naming). [RBT]

### T12. Serving / API / UI (4)

- **KRF-24** — Deployment: venv on a server behind an API consumed by a website; model file size is a real constraint. [KRF]
- **KRF-25** — Prediction UI: live chart with predicted path overlay, Confidence Score %, BUY/SELL recommendation, market summary. [KRF]
- **KRF-26** — Honest research disclaimer on all predictions (no financial advice, no accuracy guarantee). [KRF]
- **JKA-13** — "Not financial advice. Research preview only." framing — paper/research mode labeling. [JKA]

### T13. Visualization conventions (12)

- **LSTM-17** — Test-vs-pred overlay plot (black test line, green pred line, legend, large figure). [LSTM]
- **LSTM-21** — Network sketch convention: inputs (price + indicators + custom) → net → output = next-candle close. [LSTM]
- **LSTM-22** — Sliding-window illustration: orange input-window box + dotted label box; "2-D input / 3-D training data". [LSTM]
- **TFM-04** — TradeGPT windowing picture: highlighted candle window → transformer → "?" next candle. [TFM]
- **TFM-39** — Plot spec: real = dashed+o, predicted = solid+x, bounded window, parameterized title/labels/legend. [TFM]
- **KRF-09** — Per-generation PnL graph: one line per bot per generation. [KRF]
- **GRC-05** — Fully-connected column drawing convention (labels rotated, hidden columns taller, labeled output nodes). [GRC]
- **JKA-11** — Anti-requirement: decorative diagrams that don't match the real architecture (MLP graphic vs spoken TCN) — diagrams must reflect the actual model. [JKA]
- **RBT-06** — Equity-curve chart with per-period detail underlay. [RBT]
- **RBT-07** — Train/test split shown honestly ON the chart (shaded "← Train →" band; OOS continues beyond it). [RBT]
- **RBT-09** — Per-trade P&L strip (green/red bars for every trade) to eyeball loss clusters/tails. [RBT]
- **RBT-11** — P&L distribution histogram inset (red left tail, green right) alongside the equity curve. [RBT]

### T14. Meta / ensembling & leaderboards (5)

- **PNP-01** — Model-swap protocol: hold every other pipeline stage fixed when comparing model families. [PNP]
- **PNP-18** — Keep the reference model (XGBoost) in the same pipeline as the comparison baseline + feature importance. [PNP]
- **PNP-28** — Comparison verdict discipline: judge by confusion-matrix structure, not just global accuracy (XGB ≈ MLP here). [PNP]
- **NNM-27** — Model leaderboard scored by CAGR/MaxDD (regression 0.32 … RNN 0.49, all vs SPX 0.18). [NNM]
- **NNM-28** — Model combining/ensembles as a first-class technique (RNN+Regression, RNN+SVM). [NNM]

### T15. Evolutionary & continual learning (5)

- **KRF-07** — GA design baseline: population ~200 mutated NN copies; keep top-10, crossover, repeat. [KRF]
- **KRF-08** — GA network I/O: last ~150 bars + order book in; ternary action out (+1/−1/0). [KRF]
- **KRF-11** — Reject GA for label-available problems (sample-inefficient); use supervised gradients when ground truth exists. [KRF]
- **RBT-01** — Continuous evolve/train loop with live-updating metrics between iterations. [RBT]
- **RBT-02** — Rich neuro-evolution operator set: asexual mutation, sexual crossover, interspecies (speciation), random injection, input-switch — with per-operator counters. [RBT]
  - ⚠ **Tension:** KRF-11 rejects GA outright, while RBT-01/02/05 show a NEAT-style GA visibly working (62%+ win rate, improving $/trade). Resolution: supervised gradients for prediction (labels exist); evolution reserved for topology/strategy search where no differentiable label exists — both lanes kept.

### T16. Documented failure modes & improvement roadmap (3)

- **TFM-42** — Root cause of NN failure on markets: expressive models fit noise, not signal → denoising/regularization/simplicity bias required. [TFM]
- **TFM-43** — Input insufficiency: OHLC + 3 indicator families is "not enough"; richer inputs are a prerequisite for real edge. [TFM]
- **TFM-44** — Explicit improvement roadmap: more/custom indicators, seq-length changes, hyperparameter tuning, other asset classes, volume data, multi-step horizons. [TFM]

(Additional failure modes distributed to their owning themes: KRF-10 hidden-loss fitness → T8; TFM-32 random-split leakage → T7; TFM-41/LSTM-20 persistence delusion → T8; PNP-22 degenerate collapse → T7; GRC-20 backprop-arg bug → T7; JKA-02/11 unverified claims / decorative diagrams → T8/T13.)

### T17. Tooling, compute & reproducibility (11)

- **NNM-07** — CPU-first constraint: no GPUs on the platform; keep models small enough that backtests don't time out. [NNM]
- **TFM-29** — Device policy: train fine on CPU; `cuda if available` switch. [TFM]
- **KRF-19** — Model-scale budget: ~200k-neuron models run on consumer machines; 33M-neuron model too big for cheap serving. [KRF]
- **TFM-06** — Stack: Jupyter + Python + PyTorch (+ ta library; pandas_ta as alternative). [TFM]
- **TFM-07** — Standard imports: numpy/pandas/torch/nn/Dataset/DataLoader/MinMaxScaler/ta/matplotlib. [TFM]
- **KRF-12** — Stack: Python + Jupyter + Keras/TensorFlow as the general model toolbox. [KRF]
- **PNP-29** — Upgrade path: sklearn MLP is simple; advanced models should use TensorFlow/Keras. [PNP]
- **PNP-30** — Single reproducible notebook containing both models, the signal backtest, all cells in execution order. [PNP]
- **TFM-34** — Single driver cell instantiating model + training with all parameters overridable in one place. [TFM]
- **TFM-45** — Copy-paste-runnable function pipeline (load → indicators → scale → dataset → model → train → evaluate). [TFM]
- **GRC-28 is in T4 validation; NNM-12/GRC-01 from-scratch philosophy in T4.** —

**Theme totals:** T1=5, T2=6, T3=18, T4=46, T5=13, T6=10, T7=32, T8=26, T9=3, T10=5, T11=7, T12=4, T13=12, T14=5, T15=5, T16=3, T17=11 → **211** ✓

---

## 2. DEDUP TABLE — canonical requirements (CANON ids)

Every REQ belongs to exactly one CANON. 63 canonical requirements.

| CANON | Canonical requirement (one sentence) | Member REQs |
|---|---|---|
| CANON-01 | Model chart patterns as order-book/liquidity mechanics (gap-fill tendency; edge decays with market efficiency). | KRF-01, KRF-03, KRF-04 |
| CANON-02 | Pattern-taxonomy feature generator that emits entry/stop/target levels for the full classical pattern set. | KRF-02 |
| CANON-03 | Psychology-free order-matching market simulator as a training/eval environment. | KRF-06 |
| CANON-04 | Standalone statistical predictability (determinism) study of charts + order book. | KRF-27 |
| CANON-05 | Multi-market, multi-timeframe data ingestion (equities daily, forex daily/1H, index daily, crypto 1m) from CSV/API sources. | NNM-13, PNP-07, LSTM-01, TFM-08, KRF-13 |
| CANON-06 | Timeframe policy: support and empirically arbitrate short-TF-only vs daily-is-less-noisy doctrines per segment. | KRF-05 |
| CANON-07 | Data hygiene pipeline: parse/sort timestamps, drop dead rows/columns, dropna, reset index, standard column names. | PNP-08, PNP-09, LSTM-02, LSTM-05, LSTM-06, TFM-09 |
| CANON-08 | Feature scaling (Standard/MinMax) with scaler persisted for inverse transform and fitted on TRAIN ONLY (fixing the videos' full-data leak). | NNM-16, LSTM-07, TFM-13 |
| CANON-09 | Categorical feature one-hot encoding. | PNP-17 |
| CANON-10 | Sliding-window supervised tensor builder (N, lookback, features) with correct window count, explicit target-column selection, and mandatory shape verification. | LSTM-08, LSTM-10, LSTM-11, TFM-14, TFM-15, TFM-16, JKA-04, GRC-23 |
| CANON-11 | From-scratch NumPy NN core: neuron → vectorized dense layers → full forward pass with cached activations. | GRC-01, GRC-02, GRC-03, GRC-04, GRC-06, GRC-07, GRC-12, NNM-12 |
| CANON-12 | Seeded small-random weight init, zero biases, reproducible. | NNM-17, GRC-08 |
| CANON-13 | Activation policy: ReLU hidden, stable softmax (classification) / linear (regression) heads; non-linearity is mandatory. | GRC-09, GRC-10, GRC-11 |
| CANON-14 | Backpropagation from first principles (per-weight partial derivatives, credit assignment). | NNM-03, GRC-16, GRC-17 |
| CANON-15 | Hand-written NumPy RNN: Wxh/Whh/Why + tanh hidden states, full BPTT with ±5 gradient clipping, lookback/hidden/lr parameter block. | NNM-04, NNM-05, NNM-15, NNM-19, NNM-20 |
| CANON-16 | Feed-forward/MLP baseline models (sklearn MLPClassifier + Keras Dense template). | NNM-01, PNP-19, KRF-15 |
| CANON-17 | LSTM model lane: forget-gate motivation + Keras LSTM(150)→Dense(1) linear-regression head. | NNM-08, LSTM-13, LSTM-14 |
| CANON-18 | Encoder-only time-series Transformer: Linear input projection, learnable positional embedding, N×(MHA+FF), last-step pooling, linear head, with the nhead/d_model/ff sizing convention. | TFM-02, TFM-03, TFM-05, TFM-18, TFM-19, TFM-22, TFM-23, TFM-24, TFM-25, TFM-26, TFM-27 |
| CANON-19 | Causal TCN encoder over the feature window (no future leakage). | JKA-05 |
| CANON-20 | NEAT-style evolvable-topology network with measured/displayed complexity. | RBT-05 |
| CANON-21 | Diffusion-based candle-sequence forecaster (future-work lane). | KRF-23 |
| CANON-22 | Multi-model family support (regression/tree/SVM/RNN/LSTM) with framework upgrade path (sklearn → Keras/TF/PyTorch). | NNM-29, PNP-29 |
| CANON-23 | Correctness validation on known-answer tasks: PyTorch-weight forward-pass check, MNIST/Fashion-MNIST runs, dataset-agnostic code, demo inference. | GRC-13, GRC-22, GRC-25, GRC-28, GRC-29 |
| CANON-24 | Technical-indicator feature library (RSI/EMA/SMA/Bollinger/MA-slope, tunable lengths) with warm-up gating and a designated extension point. | NNM-14, PNP-16, LSTM-03, TFM-10, TFM-11, TFM-12, LSTM-19 |
| CANON-25 | Validated custom signals as features: fractal S/R + candlestick detectors combined into a proximity signal; profitability is the admission criterion. | PNP-03, PNP-04, PNP-10, PNP-11, PNP-12 |
| CANON-26 | Next-bar close regression target (price-as-next-token). | LSTM-04, TFM-01, TFM-17, KRF-14 |
| CANON-27 | Directional classification / next-bar up-probability target. | NNM-06, PNP-05, JKA-06 |
| CANON-28 | Barrier-style labeling (±pip barriers within horizon) with mandatory class-balance histogram check. | PNP-14, PNP-15 |
| CANON-29 | Target-selection doctrine: trend-direction targets over reversal targets; reversal models require risk overlay. | PNP-02 |
| CANON-30 | Chronological splits only — ordered train/val/test slices, random_split forbidden, shuffle policy explicit. | NNM-18, LSTM-12, TFM-31, TFM-32, TFM-33, LSTM-15 |
| CANON-31 | Standard training loop discipline: epochs, LR, mini-batches, per-epoch train+val loss logging, appropriate losses (CE/MSE), gradient-descent-over-GA. | NNM-02, NNM-21, GRC-14, GRC-15, GRC-18, GRC-24, TFM-28, TFM-30, KRF-16 |
| CANON-32 | Optimizer policy (SGD baseline; Adam default in framework lanes). | GRC-19 |
| CANON-33 | Regularization / simplicity bias (dropout etc.). | TFM-20 |
| CANON-34 | Hyperparameter/topology/lookback search protocol with logged experiments and per-class-metric observation (not accuracy alone). | NNM-09, NNM-10, PNP-06, PNP-21, PNP-22, PNP-24, PNP-25, PNP-26, PNP-27, LSTM-09, LSTM-18, TFM-21, GRC-27 |
| CANON-35 | Training-debug practice: loss/accuracy-vs-step plots, small-data sanity runs, backward-pass argument correctness. | GRC-20, GRC-21 |
| CANON-36 | Naive-baseline honesty gate: beat persistence (regression) and majority-class (classification) baselines before any trust. | TFM-41, LSTM-20, PNP-23 |
| CANON-37 | Classification evaluation: train+test accuracy, confusion matrices, per-class reports, misclassification galleries. | PNP-20, GRC-26 |
| CANON-38 | Execution gate: CAGR/MaxDD must beat the buy-and-hold benchmark ratio. | NNM-24 |
| CANON-39 | Trading scorecard: Sharpe/Sortino/PSR/CAGR/DD/expectancy/win-loss stats + per-trade economics headline ($/round-trip). | NNM-25, JKA-12, RBT-08, RBT-10 |
| CANON-40 | Cost-aware results: commissions/fees included in every reported number. | NNM-23 |
| CANON-41 | Mark-to-market, drawdown-aware fitness: realized+unrealized PnL, profit-per-trade × underwater-minimization, quality over trade count. | KRF-10, RBT-03, RBT-12 |
| CANON-42 | Out-of-sample & live validation: held-out-only prediction, truly-unseen live-data tests, rolling accuracy-over-time tracking. | LSTM-16, KRF-17, KRF-20 |
| CANON-43 | Anti-overfit telemetry (backtest count, parameter count, research-time flags). | NNM-30 |
| CANON-44 | Regression evaluation harness: inverse-scaled MSE/MAE with dummy-row inverse transform and parameterized comparison windows. | TFM-35, TFM-36, TFM-37, TFM-38, TFM-40 |
| CANON-45 | Honest-claims policy: research-preview disclaimers, no unverified performance claims, explicit maturity labeling. | JKA-02, JKA-13, JKA-14, KRF-26 |
| CANON-46 | Feature admission gate: standalone classic backtest must be profitable before a signal becomes an ML feature. | PNP-13 |
| CANON-47 | Autoregressive multi-candle rollout (feed predictions back into the window). | KRF-18 |
| CANON-48 | Multi-horizon heads: long-move-tuned variants + direct multi-candle vector output. | KRF-21, KRF-22 |
| CANON-49 | Risk-map overlay: dead-band abstention, inverse-forecast-vol sizing, hard exposure cap, benchmark-relative leverage headroom. | JKA-07, JKA-08, JKA-09, JKA-10, NNM-26 |
| CANON-50 | NN as strategy-improver & portfolio rebalancer (entry/exit, drawdown reduction, LSTM+covariance allocation). | NNM-11, NNM-31, NNM-32 |
| CANON-51 | Per-bar end-to-end live loop (signal→sizing→trade) with warm-up/indicator readiness gating. | JKA-01, JKA-03, NNM-22 |
| CANON-52 | Per-venue/instrument strategy identity. | RBT-04 |
| CANON-53 | Model serving: venv + API behind a web front-end with model-size budgets. | KRF-24 |
| CANON-54 | Prediction UI: live chart + predicted-path overlay, confidence score, buy/sell recommendation, market summary. | KRF-25 |
| CANON-55 | Pred-vs-real overlay plot conventions (styles, markers, windows, legends). | LSTM-17, TFM-39 |
| CANON-56 | Trading run visualization suite: equity curve, on-chart Train band, per-trade P&L strip, P&L distribution histogram, per-agent PnL lines. | RBT-06, RBT-07, RBT-09, RBT-11, KRF-09 |
| CANON-57 | Honest architecture/window diagrams that match the real model (no decorative mismatches). | GRC-05, LSTM-21, LSTM-22, TFM-04, JKA-11 |
| CANON-58 | Model-comparison protocol: frozen pipeline, in-notebook reference model, confusion-structure verdicts, CAGR/MaxDD leaderboard, ensembles. | PNP-01, PNP-18, PNP-28, NNM-27, NNM-28 |
| CANON-59 | Evolutionary lane: GA/NEAT continuous-learning loop with rich operators — used only where no supervised label exists (KRF-11 boundary). | KRF-07, KRF-08, KRF-11, RBT-01, RBT-02 |
| CANON-60 | Failure-mode catalog + improvement roadmap: noise-fitting root cause, input insufficiency, enumerated upgrade directions. | TFM-42, TFM-43, TFM-44 |
| CANON-61 | CPU-first compute budget: model sizes and seq lengths sized to CPU training/serving. | NNM-07, TFM-29, KRF-19 |
| CANON-62 | Standard stack: Python/Jupyter, PyTorch and Keras/TF lanes, ta/pandas_ta, sklearn preprocessing. | TFM-06, TFM-07, KRF-12 |
| CANON-63 | Reproducible packaging: single notebook / driver cell / copy-paste-runnable function pipeline with all knobs in one place. | PNP-30, TFM-34, TFM-45 |

---

## 3. COVERAGE MATRIX SKELETON (design phase fills "Implemented by")

| CANON | Member REQs | Implemented by |
|---|---|---|
| CANON-01 | KRF-01, KRF-03, KRF-04 | |
| CANON-02 | KRF-02 | |
| CANON-03 | KRF-06 | |
| CANON-04 | KRF-27 | |
| CANON-05 | NNM-13, PNP-07, LSTM-01, TFM-08, KRF-13 | |
| CANON-06 | KRF-05 | |
| CANON-07 | PNP-08, PNP-09, LSTM-02, LSTM-05, LSTM-06, TFM-09 | |
| CANON-08 | NNM-16, LSTM-07, TFM-13 | |
| CANON-09 | PNP-17 | |
| CANON-10 | LSTM-08, LSTM-10, LSTM-11, TFM-14, TFM-15, TFM-16, JKA-04, GRC-23 | |
| CANON-11 | GRC-01, GRC-02, GRC-03, GRC-04, GRC-06, GRC-07, GRC-12, NNM-12 | |
| CANON-12 | NNM-17, GRC-08 | |
| CANON-13 | GRC-09, GRC-10, GRC-11 | |
| CANON-14 | NNM-03, GRC-16, GRC-17 | |
| CANON-15 | NNM-04, NNM-05, NNM-15, NNM-19, NNM-20 | |
| CANON-16 | NNM-01, PNP-19, KRF-15 | |
| CANON-17 | NNM-08, LSTM-13, LSTM-14 | |
| CANON-18 | TFM-02, TFM-03, TFM-05, TFM-18, TFM-19, TFM-22, TFM-23, TFM-24, TFM-25, TFM-26, TFM-27 | |
| CANON-19 | JKA-05 | |
| CANON-20 | RBT-05 | |
| CANON-21 | KRF-23 | |
| CANON-22 | NNM-29, PNP-29 | |
| CANON-23 | GRC-13, GRC-22, GRC-25, GRC-28, GRC-29 | |
| CANON-24 | NNM-14, PNP-16, LSTM-03, TFM-10, TFM-11, TFM-12, LSTM-19 | |
| CANON-25 | PNP-03, PNP-04, PNP-10, PNP-11, PNP-12 | |
| CANON-26 | LSTM-04, TFM-01, TFM-17, KRF-14 | |
| CANON-27 | NNM-06, PNP-05, JKA-06 | |
| CANON-28 | PNP-14, PNP-15 | |
| CANON-29 | PNP-02 | |
| CANON-30 | NNM-18, LSTM-12, TFM-31, TFM-32, TFM-33, LSTM-15 | |
| CANON-31 | NNM-02, NNM-21, GRC-14, GRC-15, GRC-18, GRC-24, TFM-28, TFM-30, KRF-16 | |
| CANON-32 | GRC-19 | |
| CANON-33 | TFM-20 | |
| CANON-34 | NNM-09, NNM-10, PNP-06, PNP-21, PNP-22, PNP-24, PNP-25, PNP-26, PNP-27, LSTM-09, LSTM-18, TFM-21, GRC-27 | |
| CANON-35 | GRC-20, GRC-21 | |
| CANON-36 | TFM-41, LSTM-20, PNP-23 | |
| CANON-37 | PNP-20, GRC-26 | |
| CANON-38 | NNM-24 | |
| CANON-39 | NNM-25, JKA-12, RBT-08, RBT-10 | |
| CANON-40 | NNM-23 | |
| CANON-41 | KRF-10, RBT-03, RBT-12 | |
| CANON-42 | LSTM-16, KRF-17, KRF-20 | |
| CANON-43 | NNM-30 | |
| CANON-44 | TFM-35, TFM-36, TFM-37, TFM-38, TFM-40 | |
| CANON-45 | JKA-02, JKA-13, JKA-14, KRF-26 | |
| CANON-46 | PNP-13 | |
| CANON-47 | KRF-18 | |
| CANON-48 | KRF-21, KRF-22 | |
| CANON-49 | JKA-07, JKA-08, JKA-09, JKA-10, NNM-26 | |
| CANON-50 | NNM-11, NNM-31, NNM-32 | |
| CANON-51 | JKA-01, JKA-03, NNM-22 | |
| CANON-52 | RBT-04 | |
| CANON-53 | KRF-24 | |
| CANON-54 | KRF-25 | |
| CANON-55 | LSTM-17, TFM-39 | |
| CANON-56 | RBT-06, RBT-07, RBT-09, RBT-11, KRF-09 | |
| CANON-57 | GRC-05, LSTM-21, LSTM-22, TFM-04, JKA-11 | |
| CANON-58 | PNP-01, PNP-18, PNP-28, NNM-27, NNM-28 | |
| CANON-59 | KRF-07, KRF-08, KRF-11, RBT-01, RBT-02 | |
| CANON-60 | TFM-42, TFM-43, TFM-44 | |
| CANON-61 | NNM-07, TFM-29, KRF-19 | |
| CANON-62 | TFM-06, TFM-07, KRF-12 | |
| CANON-63 | PNP-30, TFM-34, TFM-45 | |

(63 CANON rows; member counts sum to 211.)

---

## 4. RESEARCH QUESTIONS (open items to confirm/upgrade before design freeze)

1. **NNM private features & rules** — the exact 2 RNN input features and entry/exit conditions are course-private; candidates are price change / overnight gap / volume change / RSI. Research + ablate to pick our own 2+ (or supersede with a larger validated set).
2. **NNM off-screen math** — forward-pass equations (tanh inferred) and the TrainRNN target normalization/epoch count are cut off; reconstruct a correct reference RNN and verify against the reported 0.49 CAGR/MaxDD behavior class.
3. **Scaler-leakage repair** — LSTM/TFM fit MinMax on the full dataset (and LSTM scales the target jointly). Confirm the correct pattern: per-fold train-only fitting, separate target scaler or return-space targets.
4. **TFM tensor plumbing** — batch_first vs permute, and absence of a causal mask (bidirectional attention within window): decide whether last-step regression needs causal masking; benchmark both.
5. **Persistence-gate metrics** — define quantitative persistence tests (lag-1 correlation of predictions vs shifted truth, Diebold–Mariano vs naive, directional accuracy net of baseline) beyond visual diagnosis.
6. **KAT unknowns** — KRF never reveals architecture, loss, normalization, window length, or how the 61% Confidence Score is computed; research best practice for calibrated confidence (conformal — ties to our Pillar-17 crepes gate).
7. **Best CPU-class architectures** — TCN (JKA) vs small Transformer (TFM) vs LSTM vs modern CPU-friendly options (xLSTM, KAN, TS foundation models per research/model-catalog): benchmark under the CANON-61 compute budget.
8. **Volatility forecaster for sizing** — JKA's inverse-vol sizing needs a σ̂ source: EWMA realized vol vs GARCH vs a second NN head. Research and pick.
9. **Dead-band & cap calibration** — thresholds for JKA-08/10 are undisclosed; derive from expected-value-after-costs analysis on our journal data.
10. **Underwater fitness math** — exact form of `FITNESS_PROFIT_PER_TRADE_TIMES_MINIMIZE_UNDERWATER` (RBT-03) is unknown; formalize (e.g., $/trade × 1/(1+avg underwater) ) and test variants.
11. **NEAT lane feasibility** — reconcile KRF-11 (GA rejected) with RBT success: evaluate neat-python (or vendored NEAT OSS) for topology/strategy search on mark-to-market fitness, gated by CANON-41.
12. **Barrier-label details** — PNP's `mytarget` uses `open[line+1]` with constant index (possible bug) and a truncated 6-class variant; validate against proper triple-barrier labeling (López de Prado) and choose.
13. **Missing detector code** — `isEngulfing` and `closeSupport` tolerance argument were never shown; reimplement from OSS pattern libraries rather than guessing.
14. **Multi-step evaluation methodology** — TFM-44/KRF-22 want 3–5-candle horizons; research proper multi-step metrics (per-horizon error curves, path-space evaluation) since the videos admit it is "harder to evaluate".
15. **Autoregressive drift** — KRF-18 rollout compounds errors; research scheduled sampling / direct multi-output vs recursive strategies for stability.
16. **Order-book features for our venues** — KRF's gap/blocks premise needs live L2 data; confirm what our multi-venue crypto pool + OpenAlgo can supply within rate budgets (Binance L2 ban gotcha already documented).
17. **Diffusion forecaster** — untried in KRF; scan OSS (e.g., time-series diffusion repos) for a CPU-viable candidate before committing.
18. **LSTM portfolio internals** — NNM-31's LSTM+covariance rebalancer internals are never shown; research LSTM-forecast + Markowitz/Riskfolio pipelines to build the equivalent.
19. **Ensemble wiring** — NNM-28 combined models' vote-merging is unexplained; design our own (stacking vs gating — ties to existing Hellsemble/column-network work).
20. **Shuffle policy** — LSTM-15 (shuffle=True within train) vs TFM-33 (no shuffle): confirm the accepted practice (shuffling windows within the training partition after chronological split is safe for non-stateful models) and encode it as a rule.

---

## 5. COUNTS

- **Total REQs: 211** (each listed exactly once in themes; each in exactly one CANON)
- **Total CANONs: 63**
- Per video: NNM 32, PNP 30, LSTM 22, TFM 45, KRF 27, GRC 29, JKA 14, RBT 12
- Per theme: T1 Market premises 5 · T2 Data & timeframes 6 · T3 Hygiene/preprocessing/windowing 18 · T4 Model architectures 46 · T5 Features & indicators 13 · T6 Targets & labeling 10 · T7 Training discipline 32 · T8 Evaluation & honesty gates 26 · T9 Autoregressive/multi-step 3 · T10 Risk overlay & sizing 5 · T11 Strategy integration & execution 7 · T12 Serving/API/UI 4 · T13 Visualization 12 · T14 Meta/ensembling 5 · T15 Evolutionary learning 5 · T16 Failure modes & roadmap 3 · T17 Tooling/compute/reproducibility 11
