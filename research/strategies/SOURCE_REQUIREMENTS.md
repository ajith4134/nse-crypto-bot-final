# Strategy Library — SOURCE REQUIREMENTS (pasted by user, this chat)

> This file preserves every strategy family, named strategy, and OSS repository the user
> pasted in this session. It is the **cross-check source of truth**: the Strategy Library
> (`trading/strategy/library/`) is not "done" until every item below is either implemented
> (executable signal) or catalogued as a data-gated spec with its OSS source + data needs.
> See the temporary rule `memory/strategy-implementation-mandate.md`.

---

## BLOCK 1 — Major strategy categories used by quant firms (15)

| Category | Goal | Holding time |
|---|---|---|
| Trend Following | capture large directional moves | minutes–months |
| Mean Reversion | bet prices return to average | seconds–days |
| Momentum | buy winners, sell losers | minutes–months |
| Statistical Arbitrage | exploit pricing inefficiencies | ms–days |
| Market Making | earn bid-ask spread | ms–minutes |
| High Frequency Trading | microstructure inefficiencies | µs–seconds |
| Event Driven | trade around news/events | minutes–weeks |
| Volatility Trading | trade vol not direction | hours–months |
| Relative Value | trade relationship between assets | days–months |
| Macro Trading | economies & global trends | days–months |
| Options Volatility Arbitrage | implied vs realized vol | hours–months |
| Machine Learning Trading | AI prediction / pattern extraction | seconds–months |
| Order Flow Trading | buying/selling pressure | ms–hours |
| Liquidity Strategies | liquidity imbalances | seconds–hours |
| Cross Asset Arbitrage | relationships across markets | seconds–days |

### 1. Trend Following
Moving Average Crossover · Dual Moving Average · Breakout Trading · Donchian Channel Breakout ·
Turtle Trading · Trend Strength Filters · SuperTrend Trend Following · Volatility Breakouts ·
Time-Series Momentum. Markets: Crypto Spot/Futures, NSE Cash/Futures, Commodities.

### 2. Mean Reversion
RSI Mean Reversion · Bollinger Band Reversion · VWAP Reversion · Z-score Reversion ·
Opening Gap Fade · Intraday Pullback · ATR Reversion · Overnight Mean Reversion.
Markets: NSE Intraday, Crypto Spot/Futures, Commodities.

### 3. Momentum
Relative Strength Ranking · Sector Rotation · Cross-Sectional Momentum · Earnings Momentum ·
Volume Momentum · Breakout Momentum · Relative Volume Momentum. Markets: NSE Cash, Crypto Spot, Futures.

### 4. Statistical Arbitrage
Pair Trading · Cointegration Trading · Basket Arbitrage · ETF Arbitrage · Index Arbitrage ·
Dispersion Trading · Factor Arbitrage · Correlation Arbitrage. Examples: Long Reliance/short ONGC;
long BTC/short ETH spread.

### 5. Market Making
Passive Bid-Ask MM · Inventory-Based MM · Avellaneda-Stoikov Model · Dynamic Spread Adjustment ·
Delta-Neutral MM · Options MM. Markets: Crypto Spot/Futures, NSE Options, Commodity Options.

### 6. High Frequency Trading
Latency Arbitrage · Queue Position Arbitrage · Order Book Imbalance · Quote Stuffing Detection ·
Tick Scalping · Market Microstructure Alpha · Order Anticipation.

### 7. Order Flow
Footprint Trading · Delta Volume Analysis · Aggressive Buyer Detection · Absorption Detection ·
Iceberg Detection · Stop Hunt Detection · Liquidity Sweep Trading.

### 8. Volatility Trading
Long Volatility · Short Volatility · Volatility Breakout · Volatility Carry · Variance Swap Trading ·
Implied Volatility Arbitrage.

### 9. Options
Directional: Long Call · Long Put · Covered Call · Protective Put.
Neutral: Short Straddle · Short Strangle · Iron Condor · Iron Butterfly.
Volatility: Long Straddle · Long Strangle · Calendar Spread · Diagonal Spread.
Advanced Quant: Gamma Scalping · Delta Neutral Arbitrage · Vega Trading · Volatility Surface Arbitrage ·
Skew Trading · Dispersion Trading · Volatility Cone Trading.

### 10. Event Driven
Earnings Trading · Budget Trading · RBI Announcement Trading · Fed Announcement Trading ·
Election Trading · Merger Arbitrage · Dividend Arbitrage · Index Rebalancing.

### 11. Macro
Interest Rate Trading · Inflation Trading · Yield Curve Trading · Currency Carry Trade ·
Commodity Super Cycle Trading · Central Bank Divergence Trading.

### 12. Machine Learning
Models: Random Forest · XGBoost · LightGBM · CatBoost · LSTM · Transformer · Temporal Fusion
Transformer · Graph Neural Networks · Reinforcement Learning · Meta Learning · Multi-Agent RL.
Applications: Direction Prediction · Volatility Forecasting · Position Sizing · Regime Detection ·
Execution Optimization.

### Per-segment named strategies
- **Crypto Spot:** DCA · Trend Following · Swing Trading · Mean Reversion · Grid Trading · Market Making ·
  Funding Arbitrage · Carry Trading · Portfolio Rotation · Momentum Rotation.
- **Crypto Futures:** Perpetual Funding Arbitrage · Basis Trading · Cash-and-Carry Arbitrage ·
  Calendar Spread · Long-Short Market Neutral · Liquidation Hunting · Open-Interest Breakout ·
  Funding-Rate Momentum · Cross-Exchange Arbitrage.
- **Crypto Options:** Covered Call · Protective Put · Long Straddle · Short Straddle · Iron Condor ·
  Gamma Scalping · Vega Arbitrage · Skew Arbitrage · Volatility Surface Arbitrage.
- **NSE Intraday:** Opening Range Breakout · VWAP Strategy · CPR Breakout · Gap and Go ·
  Momentum Ignition · Pullback Continuation · Volume Breakout · Trend Day · Reversal Day · Index Leader.
- **NSE Cash Delivery:** Growth · Value · Quality · Factor · Sector Rotation · Momentum · Smart Beta · Dividend.
- **NSE Futures:** Trend Following · Spread Trading · Basis Arbitrage · Calendar Spread · Pair Trading ·
  Carry Trading · Volatility Trading.
- **NSE Options:** Long Call · Long Put · Bull Call Spread · Bear Put Spread · Iron Condor · Iron Butterfly ·
  Short Straddle · Short Strangle · Gamma Scalping · Volatility Arbitrage · Dispersion · Vega-Neutral Portfolios.
- **Commodities:** Crack Spread · Calendar Spread · Inventory Arbitrage · Gold-Silver Ratio ·
  Intermarket Arbitrage · Seasonal Trading · Harvest Cycle Trading · Weather Models.

### OSS repos (Block 1)
- stefan-jansen/machine-learning-for-trading
- je-suis-tm/quant-trading
- wangzhe3224/awesome-systematic-trading
- freqtrade/freqtrade · freqtrade/freqtrade-strategies · iterativv/NostalgiaForInfinity · Netanelshoshan/freqAI-LSTM
- 50shadesofgwei/funding-rate-arbitrage · aoki-h-jp/funding-rate-arbitrage
- dennislwy/binance-spot-futures-arbitrage-spread-monitor
- nkaz001/hftbacktest · Adamant-im/adamant-tradebot
- leanderdulac/crypto_vol_arb · alexanderkudryashov3/Crypto-Options
- pkjmesra/PKScreener · KalyanM45/MarketInsight
- VarunS2002/Python-NSE-Option-Chain-Analyzer
- sap215/StatArbPairsTrading · JerBouma/AlgorithmicTrading
- buzzsubash/algo_trading_strategies_india · srikar-kodakandla/fully-automated-nifty-options-trading
- mirajgodha/options · PyPatel/Options-Trading-Strategies-in-Python
- marketcalls/openalgo · AI4Finance-Foundation/FinRL · EarnHFT (arxiv 2309.12891)

---

## BLOCK 2 — Ultra-advanced (firm-internal) strategies

### Crypto Spot
- Cross-Exchange Arbitrage (Binance↔Bybit, Coinbase↔Binance, Hyperliquid↔Binance) — hummingbot/hummingbot
- Triangular Arbitrage (USDT→BTC→ETH→USDT) — hummingbot/hummingbot
- DEX-CEX Arbitrage (Uniswap vs Binance, Hyperliquid vs Binance) — hummingbot/hummingbot
- Cross-Chain Arbitrage (ETH↔SOL, ARB↔Base, BSC↔ETH) — topics/trading-bot-bsc-solana

### Crypto Futures
- Funding Rate Arbitrage — 50shadesofgwei/…, aoki-h-jp/…
- Basis Arbitrage — dennislwy/binance-spot-futures-arbitrage-spread-monitor
- Market Making (Avellaneda-Stoikov, inventory skew, dynamic spread, queue position, microprice, fill-prob) — nkaz001/hftbacktest
- Order Book Alpha (OB imbalance, queue imbalance, cumulative delta, microprice deviation, spoofing, iceberg) — nkaz001/hftbacktest, zozoheir/hftpy
- Latency Arbitrage — hello2all/gamma-ray, ayan-goel/crypto_bot

### Crypto Options
- Volatility Arbitrage — u3ffrzi/options-market-maker-algorithm
- Volatility Surface Arbitrage (skew, smile, surface anomalies) — alexanderkudryashov3/Crypto-Options
- Gamma Scalping (long gamma, continuous delta hedge)
- Dispersion Trading (long index vol, short component vol)
- Volatility Carry (sell overpriced IV / buy underpriced IV)

### NSE Intraday Cash
- Opening Auction Imbalance · Relative Volume Shock Models · VWAP Execution Alpha ·
  Sector Rotation Intraday · Leader-Laggard Models · Statistical Arbitrage (sap215, je-suis-tm)

### NSE Futures
- Calendar Spread Arbitrage · Basis Trading · Index Basket Arbitrage · Correlation Breakdown ·
  Regime Switching (HMM / Bayesian / Kalman)

### NSE Options
- Volatility Surface Arbitrage · Dynamic Delta Hedging · Gamma Scalping (mirajgodha/options) ·
  Volatility Risk Premium Capture · Dispersion · Dealer Gamma Exposure · Dealer Vanna · Dealer Charm

### Commodities
- Crack Spread (crude↔gasoline↔diesel) · Spark Spread (natgas↔electricity) ·
  Crush Spread (soybean↔oil↔meal) · Gold-Silver Ratio · Storage Arbitrage · Convenience Yield Arbitrage

### Ultra-advanced AI
- Multi-Agent RL (MM/execution/alpha/regime/risk/router agents) — arxiv 2511.02136, 2309.12891
- Hierarchical RL (portfolio→strategy→execution→order agents)
- Meta Strategy Selection (HMM, Transformer regime, Bayesian nets, Thompson sampling, contextual bandits)
- Neural Microstructure (Transformer OB, DeepLOB, Deep OFI, Temporal Fusion Transformer, GNN)

---

## BLOCK 3 — Highest-profitability institutional tier (+ repos)

### NSE Futures
- Index Basket Arbitrage · StatArb Pairs (arnavkohli/statistical-arbitrage-pairs-trading, sap215/StatArbPairsTrading) ·
  Calendar Spread Arbitrage · Correlation Breakdown · Hidden Markov Regime Switching (HMM/Bayesian/Markov-Switching GARCH)

### NSE Options
- Gamma Scalping (alpacahq/gamma-scalping, michaelsyao/GammaScalping) · Dispersion (billydavila/Dispersion-Trading-Strategy) ·
  Volatility Surface Arbitrage (IV percentile/rank/curvature) · Dealer Gamma Exposure (pinning/squeeze) ·
  Vanna-Charm Flow · Volatility Risk Premium Harvesting

### Crypto Futures
- Funding Rate Arbitrage (50shadesofgwei, aoki-h-jp) · Cross Exchange Arbitrage ·
  Avellaneda-Stoikov MM (fedecaccia/avellaneda-stoikov, Jungle-Sven/avellaneda_stoikov_mm) ·
  RL Market Making (ESkripichnikov/market-making; PPO/SAC/A2C/DQN) · Queue Position Prediction · Liquidation Sniping (hummingbot.org)

### Crypto Options
- Volatility Surface Arbitrage · Gamma Scalping (alpacahq/gamma-scalping) ·
  Delta-Gamma Hedging Networks (arxiv 2502.11706) · Option Market Making (Avellaneda-Stoikov, Guéant-Lehalle-Fernandez-Tapia, arxiv 1907.12433)

### Institutional profitability ranking
1 Market Making · 2 Volatility Risk Premium · 3 Statistical Arbitrage · 4 Gamma Scalping ·
5 Dispersion · 6 Funding Arbitrage · 7 Cross-Exchange Arbitrage · 8 Order Book Alpha ·
9 Vanna-Charm · 10 Regime Switching

---

## BLOCK 4 — 11-level retail→institutional hierarchy (final set)

- **L1 Classical Retail:** Trend (EMA/SMA cross, SuperTrend, MACD, Donchian, Turtle) ·
  Mean-Reversion (RSI, Bollinger, VWAP, Z-score) · Breakout (ORB, CPR, Volume, Gap) ·
  Momentum (relative strength, sector momentum, relative-volume).
- **L2 Prop:** Relative Value (pair, cointegration, basket, spread) · Futures (calendar spreads,
  basis arb, carry, **roll-yield harvesting**) · Options (iron condor/butterfly, short
  strangle/straddle, **ratio spreads**).
- **L3 Institutional Quant:** StatArb (**cross-sectional mean reversion**, **factor-neutral**,
  **sector-neutral**, **dollar-neutral**, **beta-neutral**) · Factor Investing (momentum, value,
  quality, **low-volatility**, **carry**) · **Alternative-Data Alpha** (news sentiment, social
  sentiment, search trends, blockchain-flow, satellite imagery, supply-chain tracking). Users: AQR, Two Sigma.
- **L4 Microstructure:** order-book imbalance, queue-position (fill/jump/cancel prob), microprice
  prediction, trade classification (aggressive buyer/seller, hidden liquidity). Users: HRT, Tower, Jump.
- **L5 Market Making:** fixed / adaptive / inventory / Avellaneda-Stoikov / queue-aware / multi-asset MM;
  Guéant-Lehalle-Fernandez-Tapia; RL-MM. Users: Optiver, IMC.
- **L6 Options Volatility:** VRP (short straddle/strangle/IC, delta-hedged shorts) · gamma scalping ·
  vol-surface arb (skew/smile/term) · dispersion · vanna · charm · dealer-gamma (pinning/squeeze). Users: Citadel Sec, Jane Street, Optiver.
- **L7 Arbitrage:** statarb · futures basis arb · calendar-spread arb · cross-exchange arb · ETF arb ·
  triangular arb · cross-asset arb (gold/silver, NIFTY/BankNifty, BTC/ETH). Users: Jane Street, Jump, DRW.
- **L8 HFT:** latency arb · queue-position arb · microprice prediction · order-flow-imbalance ·
  hidden-liquidity detection · liquidity-sweep detection. Users: HRT, Tower, Jump.
- **L9 Machine Learning:** GBM (XGBoost/LightGBM/CatBoost) · sequence (LSTM, **GRU**, **TCN**) ·
  transformers (TFT, **PatchTST**, **Informer**, **TimeGPT**) · GNN · meta-learning. Users: Two Sigma, WorldQuant, AQR.
- **L10 Reinforcement Learning:** execution agents · market-making agents · portfolio agents ·
  hierarchical RL · multi-agent RL.
- **L11 Meta Strategy Systems:** **regime-detection layer** (HMM/Bayesian-switching/Transformer) ·
  **strategy-allocation layer** (dynamic capital across trend/vol/arb/MM) · **risk layer**
  (portfolio/correlation/tail/liquidity risk) · **execution layer** (market/limit/TWAP/VWAP/POV).
  Users: Millennium, Point72, Citadel.

### Profitability ranking (capacity / competition / typical Sharpe)
1 Market Making (3–10) · 2 Statistical Arbitrage (2–5) · 3 Volatility Arbitrage (2–5) ·
4 Dispersion (2–4) · 5 Funding Arbitrage (1.5–4) · 6 Volatility Risk Premium (1.5–3) ·
7 Trend Following (1–2) · 8 Momentum (1–2) · 9 Mean Reversion (1–2) · 10 Directional Prediction (0.5–1.5).
