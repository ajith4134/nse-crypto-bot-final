# Understanding — "I Made an AI Learn Stock Market Patterns" (Krafer, ~16:25)

Source: `/home/karan18190164/research/video/krafer-patterns/` (transcript.md + frames/ 000–169).
NOTE: the original extraction skipped 03:00–09:29; those frames were re-extracted into `frames-gap/` (gap_001–077, timestamps noted below) and are fully incorporated here.

## Summary

Krafer argues that chart patterns are a mathematical artifact of order-book mechanics (liquidity gaps that price fills), not trader psychology, so short-timeframe price is partially predictable. He first hooks a population of neural-net bots to his own psychology-free market simulation using a genetic algorithm (inputs: last ~150 bars + order book; outputs: buy/sell/hold) — it fails because the fitness tracked only *realized* PnL, so bots learned to hide losses by never closing losers, and GA evolution is far too sample-inefficient. He then switches to supervised learning in Python (Keras/TensorFlow, Jupyter) on ~51,773 minutes (~35 days) of real 1-minute BTC data, training the "KAT/CAT 1.3" model to predict the close of exactly the next candle; a GPT-style autoregressive loop (feed each prediction back in) yields multi-candle forecasts (CAT 2.x, ~200k neurons; CAT 1.4 at 33M neurons), which visually track never-seen live BTC test data. The models are deployed in a venv on a server behind an API and served live at krafercrypto.com (confidence score + buy/sell recommendation), with a diffusion-based predictor named as untried future work.

## REQUIREMENTS

### A. Market-mechanics premise (what the network should exploit)

- **REQ-KRF-01 — Patterns are order-book math, not psychology.** Treat classical chart patterns as reducible to simple support/resistance lines caused by order-book structure; do NOT model them as self-fulfilling psychological artifacts. [00:14–00:54] (f_0020_006 shows a consolidation rectangle drawn on candles; f_0031_008 shows pattern break through a falling resistance line).
- **REQ-KRF-02 — Full classical pattern taxonomy as reference.** The taxonomy shown [00:28] (f_0028_007) that "reduces to resistance lines": Reversal = Double Top, Head & Shoulders, Rising Wedge, Double Bottom, Inverse H&S, Falling Wedge; Continuation = Falling Wedge, Bullish Rectangle, Bullish Pennant, Rising Wedge, Bearish Rectangle, Bearish Pennant; Bilateral = Ascending / Descending / Symmetrical Triangle. Each drawn with entry / stop / target levels — any pattern feature-generator should emit these three levels.
- **REQ-KRF-03 — Blocks-and-gaps reduction.** Any trading pattern must be reducible to "blocks and gaps" in the order book: large gaps between bid/ask levels get filled by price ("Gap Up" → "Filled the Gap Down", f_0140_016 [01:37]). Model the gap-fill tendency explicitly. [01:12–01:49]
- **REQ-KRF-04 — Efficiency ↔ pattern frequency.** The more efficient/liquid the market, the fewer patterns appear; patterns are a *short-term liquidity* phenomenon. Prefer less-liquid/shorter-horizon regimes for pattern-based edge. [01:49–02:00]
- **REQ-KRF-05 — Short timeframes only.** Use ML prediction only on short timeframes (1-minute here); long horizons are psychology/macro-dominated (quant firms confirmed: "they only use AI on the shorter time frames"). [02:15–03:10]
- **REQ-KRF-06 — Psychology-free simulator as training/test environment.** A market simulation that generates charts purely from order-matching math (no agents' psychology) which still produces gaps and patterns; used as the RL/GA training ground. Sim UI (f_0154_017 [01:54], gap_003 @03:40, gap_028 @04:54, gap_031 @05:08): panel with `Position`, `Last Price $`, `Floating`, `Total PnL`, `Buy`/`Sell`/`>>` buttons and a "Show/Hide Order Bars" toggle that renders resting order-book levels as horizontal colored bars overlaid on candles + volume.

### B. Attempt 1 — Genetic algorithm (built, failed; lessons are requirements)

- **REQ-KRF-07 — GA design (baseline to compare against).** Spawn a population (~200) of NN copies with slight weight mutations in the simulator; each cycle keep top-10 performers, "breed" them (crossover) to form the next generation, kill the rest; repeat. [04:56–05:22] (gap_030 @05:01 many bot icons; gap_056 @07:53 grid of bots in the sim; gap_052 @07:28 DNA imagery).
- **REQ-KRF-08 — Network I/O spec.** Input layer = entire chart for the past ~150 bars + the order book; output = single ternary action: +1 buy, −1 sell, 0 do nothing. [05:27–06:03] (gap_017 @04:06 shows the layer diagram: binary inputs 1/0/1 → hidden circles labeled 0.384 / 0.971 / 0.129 / 0.493 → further layers → output).
- **REQ-KRF-09 — Per-generation PnL tracking graph.** A graph tracking every bot's PnL throughout the cycle, one line per bot, per generation. [06:07–06:31] (gap_047 @07:15 multicolor PnL-line spaghetti per bot; gap_046 @07:09 rising PnL lines after ~100 generations).
- **REQ-KRF-10 — Fitness MUST use total (realized + unrealized/mark-to-market) PnL.** The observed failure: tracking only *realized* PnL let bots amass open losing positions that never showed, so the population "learned to hide their losses" and looked profitable. Any fitness/reward/eval metric must mark open positions to market and penalize unrealized losses. [06:31–07:22] (gap_048 @07:17 "PnL Dashboard — Realized 0.00 | Unrealized 6.00" with Close Trade button).
- **REQ-KRF-11 — Reject GA for this problem class.** GA updates once per generation, wastes ~200 discarded agents per round, and is only appropriate when there is *no known correct answer* (walking, game playing). Price prediction has a ground-truth label (the covered-up right side of the chart), so use supervised gradient learning instead. [07:27–08:07, 09:38–10:23] (gap_058 @08:00 "Genetic Algo" comic; gap_075 @09:18 Unity 999+ errors "this is fine" — Unity also rejected as an ML environment [09:16–09:23]).

### C. Attempt 2 — Supervised Keras model (KAT/CAT series) — the adopted design

- **REQ-KRF-12 — Stack.** Python + Jupyter Notebook + Keras/TensorFlow ("the toolbox that lets you design any sort of AI"). [08:07–08:19, 09:28–09:33] (f_0929_130 & gap_077 TF+Keras logos).
- **REQ-KRF-13 — Dataset.** Real Bitcoin data, past ~4 months, 1-minute timeframe, ~50,000 rows; the trained CAT 1.3 used 51,773 minutes ≈ 35 complete days of 1-minute candles, ~17 MB. [08:19–08:25, 08:55–09:04, 10:47]
- **REQ-KRF-14 — Label / task.** The model predicts exactly ONE number: the close of the next single candle. (One prediction per forward pass — same as an LLM predicting one token.) [09:04–09:13, 10:38–10:47]
- **REQ-KRF-15 — Keras model pattern (as shown on screen, illustrative).** [09:34] (f_0934_131):
  ```python
  model = tf.keras.Sequential([
      tf.keras.layers.Flatten(input_shape=(28, 28)),
      tf.keras.layers.Dense(128, activation='relu'),
  ])
  ```
  (Snippet shown is the generic Keras Sequential/Flatten/Dense-relu template; the actual KAT layer sizes were not shown.)
- **REQ-KRF-16 — Training = gradient descent ("fine-tuning a radio with a million knobs", "hyper-dimensional calculus"), hours-long runs on one model** — one AI + one "textbook" (dataset) beats 200 random GA agents. [09:38–10:38] (gap_072 @08:38 gradient/steepest-ascent math imagery; gap_019 @04:22 playground-style loss curves "Test loss 0.351 / Training loss 0.208").
- **REQ-KRF-17 — Accuracy-over-time evaluation script.** Write a script that checks how accurate the model is over time (rolling accuracy vs. ground truth), and use it to drive iterative improvement of the model. [08:31–08:36]
- **REQ-KRF-18 — GPT-style autoregressive multi-candle generation (CAT 2.x).** Like ChatGPT feeding the whole conversation back for the next token: feed the model's own predicted candle back into the input window to predict the next, iterated to generate "as many future candles as we want". Emergent pattern-reasoning is expected to arise from training if patterns really exist. [11:12–12:27]
- **REQ-KRF-19 — Model scale.** CAT 2.x series ≈ 200,000 neurons (deliberately small vs GPT-3's quoted 70B — must run on a consumer machine); CAT 1.4 = 33 million neurons (noted as too big for cheap web serving). [12:22–12:31, 14:26–14:37]
- **REQ-KRF-20 — Out-of-sample test on truly unseen live data.** Evaluate on live BTC data pulled from just days ago (impossible to be in training set); judge via freeze-frame overlay comparisons of predicted vs actual future candles — "these predictions are not far off". [12:31–12:58]
- **REQ-KRF-21 — KAT 1.4 behavior spec (from website docs, f_1402_150 [14:02]):** "KAT (Krafer Agent Trader) is a neural network model trained on Bitcoin price action… KAT 1.4 focuses on predicting large, lengthy moves in the future. Predictions are often slower and take longer to play out… Remember to adapt appropriately when trading and to always use caution." I.e., a variant tuned for larger/longer forward moves rather than the next tick.
- **REQ-KRF-22 — Roadmap: multi-candle-at-once model.** Milestones (f_1441_156 [14:41]): Launch KAT (Jun 30 2025); Raise Funds — models go private/subscription (Jul 21 2025); **Launch KAT 3 (TBD): "high level of accuracy, focusing on predicting multiple candles at once"** — i.e., a direct multi-step (vector) output head, not only autoregressive rollout.
- **REQ-KRF-23 — Diffusion-model alternative (declared future work, NOT built).** A second neural prediction paradigm: refine the same guess over and over until "crystal clear" — a diffusion model for candle sequences. [13:22–13:45]

### D. Serving / product requirements

- **REQ-KRF-24 — Deployment.** Run the model from a Python virtual environment on a server, exposed via an API consumed by a website; predictions stream in live "like ChatGPT generations roll in". Model file size is a real constraint (GitHub 50 MiB file limit shown, f_1430_154 [14:30]; big models can't be hosted cheaply). [08:36–08:47, 14:07–14:30] (f_1420_152 client–internet–server diagram).
- **REQ-KRF-25 — Prediction UI (krafercrypto.com, f_1408_151 [14:08]).** Dashboard shows: Market Summary (Total Market Cap $3.77T, 24h Volume $188.5B, BTC Dominance 60.0%, Fear & Greed "Greed (55)"), live BTC price chart with the model's predicted path overlaid, and a "Trade Analysis" card: **Confidence Score 61%** (progress bar), **BUY OR SELL recommendation button**, "Price raw predicted minimum ($117,336), but future direction unclear due to timeline", plus a Research-Purposes-Only disclaimer block. Market-news sidebar alongside.
- **REQ-KRF-26 — Honest research disclaimer.** All predictions labeled experimental/educational: "No Financial Advice… No Accuracy Guarantee: past performance and displayed accuracy metrics do not guarantee future results… consult with qualified financial advisors" (f_1408_151 footer).

### E. Follow-on research thread

- **REQ-KRF-27 — Determinism study.** Companion analysis: measure whether probabilities of future direction can be extracted purely from charts + the order book ("spoiler: I did find some results") — i.e., quantify chart/order-book predictability statistically, separate from any model. [15:07–15:22]

## Diagrams

Genetic-algorithm loop (Attempt 1):
```
        market simulator (math-only, has gaps/patterns)
                      │  state: last ~150 bars + order book
                      ▼
   ┌── population of ~200 NN bots ── each outputs {+1 buy, -1 sell, 0 hold}
   │            │
   │            ▼
   │   per-generation PnL graph (MUST be realized+unrealized)   ← failure was realized-only
   │            │
   │   top-10 survive ──► crossover/mutate ──► new population
   └───────────── repeat ~100+ generations (rejected: too slow) ─┘
```

NN layer sketch shown on screen (gap_017):
```
inputs        hidden          hidden   output
 [1] ─┐      (0.384)
 [0] ─┼──►   (0.971)  ──►  ( ) ( )  ──► ( )   → prediction
 [1] ─┘      (0.129)
             (0.493)
```

Adopted supervised pipeline (KAT/CAT):
```
BTC 1m candles (4 months, ~51,773 rows, 17MB)
      │ window: past N candles
      ▼
Keras Sequential (Flatten → Dense(relu) → … )  ~200k neurons (KAT2.x) / 33M (KAT1.4)
      │ trains hours, gradient descent, accuracy-over-time script drives iteration
      ▼
predict close of NEXT 1 candle ──feed back──► autoregressive rollout = k future candles
      │
      ▼
venv on server → API → website UI (confidence %, buy/sell rec, disclaimer)
```

## Open questions (not stated in the video)

1. Exact KAT architecture: layer counts/sizes, activation beyond the generic `Dense(128, relu)` snippet, whether recurrent/attention layers are used ("a chat gpt of my own" suggests transformer-like, but never confirmed).
2. Exact input window length and feature set for KAT (OHLCV only? order book included as in the GA version?), and normalization scheme.
3. Loss function and optimizer (only "hyper-dimensional calculus"/knob-tuning metaphors given).
4. Quantitative accuracy numbers for CAT 1.3/1.4/2.x — only visual freeze-frame comparisons and a website "61% confidence" are shown.
5. How the website Confidence Score is computed.
6. Train/validation split details and whether any walk-forward protocol was used beyond "test on live data from a couple days ago".
7. GA hyperparameters (population size beyond "~200", mutation rate, crossover method).
8. What differentiates CAT 1.3 vs 1.4 in training/data (besides 1.4 = 33M neurons and "large, lengthy moves" focus) and what 2.x/3.x change.
