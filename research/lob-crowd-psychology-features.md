# LOB "crowd psychology" features — formulas + OSS candidates (2026-07-02)

README-level survey: canonical order-book microstructure formulas that quantify trader/crowd sentiment, plus OSS implementing them.

## Formula reference

| Feature | Formula | Predictive interpretation (literature) | Citation |
|---|---|---|---|
| Order Book Imbalance (OBI) | `(V_bid − V_ask)/(V_bid + V_ask)` at best (or top-k) levels, in [−1,1] | Positive OBI (bid-heavy book = buying eagerness) predicts short-horizon upward mid-price moves; strongest signal near ±1. Standard HFT alpha (hftbacktest example, Alpaca example-hftish). | Cartea/Jaimungal; used across HFT practice |
| Weighted mid / Microprice | Weighted mid: `P_wm = I·P_ask + (1−I)·P_bid`, I = bid-size fraction. Stoikov microprice: `P_micro = mid + g(I, spread)` — Markov-chain adjustment making it a martingale estimate of future mid | Better short-term (ms–s) predictor of future mid than mid or weighted mid; deviation microprice−mid signals imminent drift direction | Stoikov 2017, "The Micro-Price" (SSRN 2970694) |
| Order Flow Imbalance (OFI) | `OFI_t = Σ (signed changes in best-bid queue) − (signed changes in best-ask queue)` over interval (event-level: +ΔbidVol on adds, −on cancels; mirrored for ask) | Price change ≈ linear in OFI, slope ∝ 1/market-depth: `ΔP ≈ OFI / (2·AvgDepth)`. More robust than volume; multi-level OFI (MLOFI) extends deeper | Cont, Kukanov & Stoikov 2014, "The Price Impact of Order Book Events", J. Fin. Econometrics (arXiv 1011.6402) |
| Depth slope / liquidity shape | Regression slope of cumulative depth vs price distance from mid (per side); shallow slope = thin book | Thin/asymmetric depth ⇒ larger impact per order ⇒ higher volatility; steepening on one side signals crowd defending/pressuring a level | Næs & Skjeltorp 2006 (order book slope); SPDE LOB models (lobpy) |
| Kyle's lambda | `λ` from `ΔP_t = λ · S_t + ε` (S = signed order flow / net volume); Amihud `|r|/dollar-vol`, Hasbrouck variants | λ = price impact per unit flow = adverse-selection/informed-trading intensity; rising λ = market fears informed flow, moves amplify | Kyle 1985; mlfinlab implements Kyle/Amihud/Hasbrouck lambdas |
| Bid-ask spread (fear proxy) | `spread = P_ask − P_bid` (or relative `spread/mid`); estimators from OHLC: Roll, Corwin-Schultz | Spread widening = MM uncertainty/adverse-selection fear; precedes/accompanies volatility spikes; narrow spread = confident two-sided crowd | Glosten-Milgrom 1985; Roll 1984; Corwin-Schultz 2012 (in mlfinlab) |
| (bonus) VPIN / PIN | Volume-synchronized probability of informed trading | High VPIN = toxic flow, precedes liquidity crashes (flash-crash literature) | Easley, López de Prado, O'Hara 2012 (in mlfinlab) |

## OSS candidates

| Project | Repo URL | Stars | Last activity | Key features | Reusability |
|---|---|---|---|---|---|
| mlfinlab | https://github.com/hudson-and-thames/mlfinlab | 4,854 | 2023-10 (archived-ish; open core) | Kyle/Amihud/Hasbrouck lambdas, Roll & Corwin-Schultz spread, VPIN, entropy features, bar-indexed feature matrices | HIGH — real pip-able library, `microstructural_features` module lifts straight in (bar/tick data, not raw LOB) |
| hftbacktest | https://github.com/nkaz001/hftbacktest | 4,242 | 2025-12 (very active) | L2/L3 tick backtester; example notebooks implement OBI market-making alpha; infra, not a feature lib | MEDIUM — copy the OBI notebook math; engine itself is Rust+Numba infra |
| sstoikov/microprice | https://github.com/sstoikov/microprice | 463 | 2021-01 | Author's reference microprice implementation (Jupyter, Python), sample data | HIGH for the one formula — canonical code, small, easy port |
| LOB-feature-analysis | https://github.com/nicolezattarin/LOB-feature-analysis | 272 | 2022-04 | OFI + multi-level OFI, PIN (MLE), realized vol, order-size distribution | MEDIUM — notebooks not a library, but OFI/MLOFI code is directly portable |
| fastlob | https://github.com/mrochk/fastlob | ~low | active | Pure-Python LOB with built-in feature extraction: spread, midprice, volume, imbalance; on PyPI | HIGH — pip install, feed depth snapshots, read features |
| crobat | https://github.com/orderbooktools/crobat | 55 | 2026-05 | Records live LOB (Coinbase), OFI + trade-flow-imbalance model for BTC-USD | MEDIUM — crypto-native OFI recorder; niche but active |

Rejected/context: mansoor-mamnoon/limit-order-book (69★, C++/PySDK, imbalance+impact analytics but young), bigfatwhale/orderbook (168★, LOBSTER parser), lob-deep-learning (DeepLOB models, heavier than needed), lobpy (SPDE depth models). Awesome-lists: awesome-systematic-trading (wangzhe3224, paperswithbacktest), awesome-high-frequency-trading, awesome-institutional-trading.

**Recommendation:** stitch — mlfinlab `microstructural_features` (lambdas/spread/VPIN) + fastlob or own snapshot pipeline for OBI/depth-slope + Stoikov's reference notebook for microprice + LOB-feature-analysis's OFI/MLOFI math. No single repo ships all six.
