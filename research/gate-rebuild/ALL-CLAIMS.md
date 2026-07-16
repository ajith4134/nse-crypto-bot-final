# ALL unique claims from both deep-research runs

Total: 217 unique claims

[1|blog] The repo implements the triple-barrier method as a path-aware replacement for fixed-horizon labels, labeling by whichever of profit-take / stop-loss / max-holding-period barrier is hit first — directly applicable to labeling crypto perp entries.

[2|blog] The repo implements meta-labeling as a two-model architecture that separates direction prediction from sizing/conviction, with the secondary model emitting a bet size in [0,1] — i.e. the secondary model is the abstention/sizing gate, not the direction model.

[3|blog] The repo implements purging + embargoing and CPCV, generating many backtest paths rather than a single walk-forward, with purging/embargoing applied to all splits — the concrete replacement for a single in-sample backtest Sharpe gate.

[4|blog] The framework asserts multiple-testing bias (uncorrected selection across many trials) is the leading cause of false strategy discoveries, and implements Deflated Sharpe Ratio plus PBO (computed from CPCV paths) to correct/quantify it — bearing directly on selecting a winner from 142 strategies.

[5|blog] Market-microstructure features including VPIN and Kyle's Lambda are NOT implemented in this repo — they are only roadmap items, so this source provides no validated microstructure alpha code or horizons.

[6|primary] Triple-barrier labeling combined with CUSUM event-filtered (information-driven) sampling produced positive trading performance net of transaction costs, and outperformed both fixed-interval time bars and next-bar prediction — supporting replacement of a fixed-horizon/backtest-Sharpe gate with event-sampled triple-barrier labels.

[7|primary] Triple-barrier labels were parameterized as symmetric ±2.5% profit-take/stop-loss barriers with a 24-period vertical (time) barrier for the most frequent input intervals, and ±5% for less frequent intervals — a concrete, reproducible label spec to record at entry (barrier levels + max holding periods).

[8|primary] The event filter and bar-sampling thresholds tested were 1%, 2%, and 3% CUSUM/range thresholds, volume bars at 30K/50K/100K ETH, and dollar bars at $50M/$100M/$150M — i.e., sampling is a tunable hyperparameter that must itself be snapshotted alongside each entry.

[9|primary] The study evaluated transformer-family architectures (vanilla Transformer encoder, FEDformer, Autoformer) against other deep learning and classical ML baselines on BTC and ETH from January 2018 to June 2023, using 33 technical indicators plus sine/cosine time encodings as inputs — notably NO L2/microstructure features (no OFI, microprice, VPIN, queue imbalance, funding, OI).

[10|primary] The paper does NOT apply meta-labeling, sample uniqueness/weighting, or purged/embargoed cross-validation, CPCV, PBO, or deflated Sharpe — so its 'outperformance' claim carries the same overfitting/leakage exposure the research question is trying to eliminate, and it cannot be cited as validation methodology.

[11|secondary] Meta-labeling is architecturally a two-model split: a primary (exogenous, possibly rule-based) model sets the SIDE of the trade, and a secondary ML classifier decides only trade/no-trade (size), with the secondary model's predicted probability used to derive bet size. This means the entry snapshot must record the primary model's side AND the secondary model's probability separately.

[12|secondary] Meta-labeling's measured out-of-sample gains are on filtering false positives / risk-adjusted performance, not on raw precision: on S&P500 e-mini, the mean-reversion strategy's OOS precision rose only 0.17 -> 0.20 (accuracy 17% -> 63%) and the trend-following strategy's OOS precision rose 0.48 -> 0.54 (accuracy 48% -> 55%); the trend-following meta-model did NOT beat the primary on all metrics, only on a risk-adjusted basis.

[13|secondary] Meta-labeling cannot rescue a bad primary signal — it requires a primary model with genuine (high-recall) predictive power; against a bad primary it only limits the downside rather than creating edge. Directly bears on whether a meta-label layer can be bolted onto a 142-strategy gate that has zero measured correlation to realized profit.

[14|secondary] The entry-time label/feature pipeline is: CUSUM event filter thresholded on point-in-time volatility -> triple-barrier labels whose horizontal barriers are set as the rolling standard deviation of log returns times a user-defined multiple (e.g. [1,1] = 1 sigma) plus a vertical time barrier. Therefore the entry snapshot must include point-in-time volatility, the barrier multiples, the resulting upper/lower price levels, and the vertical-barrier timestamp.

[15|secondary] This paper's own validation does NOT use purged/embargoed CV or sample-uniqueness weights despite overlapping triple-barrier labels — it uses random K-fold CV with grid search plus up-sampling with replacement to fix class imbalance, and admits an iterative in-sample tuning loop. Its reported numbers are therefore optimistically biased and it is not evidence for the validation half of the question.

[16|primary] Market impact follows a square-root law in participation rate: normalized impact I/σ_D = c·(Q/V_D)^δ with δ≈0.5 and c≈0.98, implying an order of 1% of daily volume incurs ~1% of daily volatility in impact. This gives a concrete, parameterized slippage term for a net-edge cost model at entry — requiring order size Q and a daily-volume estimate V_D to be snapshotted.

[17|primary] The simulated impact exponent is δ = 0.539 ± 0.048 across 2,000 simulated stocks, versus a Tokyo Stock Exchange empirical benchmark of 0.489 — i.e. the square-root exponent is NOT exactly 0.5 and the simulated value sits above the equity-market empirical value, so any cost model importing δ=0.5 carries a calibration error that must be re-fit on the target venue (this paper's evidence is equity ABM, never crypto perps).

[18|primary] The square-root exponent is jointly produced by order splitting and liquidity replenishment: removing order splitting collapses δ from 0.549 to 0.324, and removing HFT liquidity-replenishing agents drops it to 0.386. Therefore δ≈0.5 is regime-dependent, and in venues/periods where metaorder splitting or market-making is absent (e.g. thin alt-perp books, liquidation cascades), a square-root cost model will misprice impact.

[19|primary] Competing single-mechanism theories of the square-root law are quantitatively falsified in this simulation — GGPS over-predicts impact by ~2x, FGLW by ~4x, and LOB-walking (static book-depth integration) under-predicts. This directly undercuts estimating slippage at entry by walking the L2 book, which is the naive method available from a 20-level book snapshot.

[20|primary] Execution-strategy micro-details are second-order to the splitting/replenishment interplay: perturbations preserving both mechanisms move δ by less than 10%. This implies a net-edge cost model needs participation rate and a liquidity-regime indicator far more than it needs fine-grained execution-tactic fields.

[21|primary] SCRC provides a risk guarantee that is CONDITIONAL ON ACCEPTANCE (non-abstention), not marginal: for a selected test point, expected loss is bounded by alpha, and the probability of being selected is at least xi. This is exactly the guarantee shape a trade-entry gate needs ("of the trades I actually take, the error rate is <= alpha"), which standard marginal conformal prediction does NOT provide.

[22|primary] Naive selection/abstention BREAKS the exchangeability that conformal validity depends on; validity is only restored if the selection rule is symmetric across calibration and test points. A gate that thresholds on a score fitted only to calibration data (the obvious implementation) forfeits the guarantee unless corrected.

[23|primary] The two implementable variants trade computation against strictness of assumption: SCRC-T computes the selection threshold jointly over calibration AND test data to preserve exact exchangeability, whereas SCRC-I uses calibration-only thresholds and recovers only a high-probability (PAC, DKW-based) guarantee under an i.i.d. assumption. For a live trade gate that cannot see future test points, only the SCRC-I style calibration-only route is deployable, and it is the weaker guarantee.

[24|primary] The paper's guarantees rest entirely on exchangeability of (X_i,Y_i) and it contains no treatment of distribution shift, temporal dependence, or non-exchangeable data. Applied to crypto perp entries — where returns are serially dependent, regime-shifting, and overlapping-labeled — the stated guarantees do NOT transfer without an adaptive/weighted-conformal modification (e.g. ACI), so this method cannot be adopted as-is for the entry gate.

[25|primary] Empirical validation is confined to static image classification (CIFAR-10 with ResNet-18, Diabetic Retinopathy Detection with ResNet-34), with results reported as prediction-set size (~2.3-2.6 classes at xi=0.7, alpha=0.1). There is zero empirical evidence for financial, trading, or time-series data, so the method's edge-estimation value here is methodological (guarantee shape) rather than validated performance.

[26|blog] The repository implements Order Flow Imbalance in both single-level and multi-level (MLOFI) form, defining OFI as the imbalance between demand and supply at the best bid and ask prices — i.e. it provides reference code for the Cont/Kukanov/Stoikov-family OFI feature we would compute from our 20-level book, but only for the OFI construction itself.

[27|blog] The repository reports NO regression models, R^2 values, coefficients, or validation metrics — it therefore supplies zero empirical evidence about the predictive power or horizon of OFI, PIN, or any other LOB feature, and cannot be cited as validation for a net-edge model.

[28|blog] The feature set is limited to four features — order-size distribution, OFI/MLOFI, PIN (Easley et al. MLE), and per-trade realized volatility — and does NOT include microprice, queue imbalance, book slope/depth, VPIN, Kyle's lambda, funding, open interest, or liquidations, so it covers only a small fraction of the entry-snapshot fields required.

[29|blog] The analysis uses volume-based bars (threshold 1,000,000 shares) and estimates volatility per trade at market-order intervals rather than fixed clock time — supporting the López de Prado argument that event/volume clocks, not 5m time bars, are the correct sampling basis for microstructure features.

[30|blog] The data is Deutsche Börse equities (via the db-lob package) with tick size 0.0001 and multi-level examples shown only up to the 2nd level — i.e. an equity venue, not crypto perpetuals, so any implied parameters do not transfer to 200-coin 20-level 500ms perp books without refitting.

[31|primary] SCOPE CAVEAT — this source does NOT study any of the L2 microstructure alphas in the research question. Despite the title's 'Market Microstructure Signals', the tested signals are five hand-crafted DAILY OHLCV heuristics (institutional accumulation, flow momentum, mean reversion, breakouts, range-bound value) on 100 US equities. Verbatim text search of the full 35-page PDF returns ZERO standalone occurrences of OFI, queue imbalance, microprice, book slope, PBO, embargo, triple-barrier, meta-labeling, conformal, or perpetual. VPIN and Kyle are mentioned only as literature citations, never computed. The paper contributes NO evidence on order-flow predictive horizons, and nothing on crypto perps.

[32|primary] Statistical power arithmetic that directly indicts small-n edge validation: with 34 out-of-sample folds and an observed effect size d=0.17, the study attains only 12% power, and ~540 independent test periods would be needed for 80% power. This transfers directly to our n=260 gate-vs-profit correlation — at realistic trading effect sizes, a few hundred observations cannot distinguish a real edge from zero, so our measured -0.031 correlation is consistent with both 'no edge' and 'small edge we cannot resolve'.

[33|primary] Strict walk-forward validation with information-set discipline collapses reported performance by 1-2 orders of magnitude relative to published backtest claims: 0.55% annualized return, Sharpe 0.33, p=0.34 (statistically insignificant) across 34 independent OOS periods, versus the 15-30% annual returns typical in the literature. This is direct empirical support for our finding that in-sample backtest Sharpe over 142 strategies is not a valid edge gate.

[34|primary] Signal edge is regime-conditional, not stationary: the same signals produced +0.60% quarterly in high-volatility 2020-2024 but -0.16% in stable 2015-2019, and the authors' stated mechanism is that informed-trading detection requires sufficient information arrival. The prescribed remedy is regime-gated abstention — allocate zero in low-volatility regimes — which argues that any entry-edge model must snapshot a realized-volatility / information-arrival regime feature at entry and be permitted to abstain.

[35|primary] The paper endorses Combinatorial Purged Cross-Validation as the best-performing anti-overfitting validator (citing Arian et al. 2024), with walk-forward retained for realistic simulation — supporting a CPCV + walk-forward pairing for our replacement gate. NOTE: the authors claim to 'combine rigorous walk-forward validation with deflated Sharpe ratios' but never actually report a Deflated Sharpe or PBO figure for their own results anywhere in the paper — DSR/CSCV appear only in the literature review and reference list. Treat the DSR/PBO endorsement as citation, not demonstration.

[36|primary] Average sample uniqueness for triple-barrier labels is computed from exactly two inputs: the label end-time series t1 (the timestamp at which the first barrier is touched) and the close-price series index — meaning an entry snapshot must record, per event, both the entry timestamp (index) and the eventual barrier-touch timestamp t1 to fit sample weights at all.

[37|primary] The uniqueness calculation is a two-stage algorithm: first num_concurrent_events counts, for each bar, how many labels' [entry, t1] spans overlap that bar; then _get_average_uniqueness averages 1/(concurrency) over each event's lifespan to produce a per-event weight. Overlapping labels therefore mechanically receive down-weighted, non-IID sample weights.

[38|primary] This implementation is a direct codification of López de Prado's Advances in Financial Machine Learning Snippet 4.1 (p. 60) and Snippet 4.2 (p. 62) — i.e., the concurrency/uniqueness weighting scheme is a published, citable method rather than a library-specific invention.

[39|primary] get_av_uniqueness_from_triple_barrier consumes the output of labeling.get_events() directly, establishing the required pipeline order: triple-barrier events must be generated first, and the resulting events DataFrame (containing t1) is the canonical carrier of the fields needed for uniqueness weighting.

[40|primary] The publicly hosted master version of this file contains only docstrings with `pass` bodies — every function implementation has been stripped — so the repository cannot be used as a working reference implementation and the algorithm must be reimplemented from the AFML snippets it cites.

[41|primary] Abstention (selective classification via the SGR algorithm thresholding softmax confidence) improved directional accuracy in EVERY tested configuration — all 4 model classes x 4 feature sets — at realized test coverage of 37-63% (binary) and 17-55% (ternary). Direct empirical support for an abstention gate on a direction classifier, but gains are small in absolute terms (LSTM/FS4: 53.66% -> 56.52% at 38.14% coverage; LR/FS2: 53.50% -> 55.79% at 47.53% coverage).

[42|primary] Classification accuracy is NOT a valid proxy for trading P&L: ternary selective classifiers achieved the HIGHEST selective accuracy (up to 63.00%) yet produced WORSE backtest Sharpe than binary selective classifiers (which peaked at only ~56.5% accuracy). Tuning on an accuracy-like metric (MCC) rather than realized net P&L was flagged by the authors as a defect to fix — the same failure mode as ranking strategies by a score uncorrelated with realized profit.

[43|primary] The measured edge is almost entirely consumed by transaction costs: at slippage of just 0.3 ticks per contract, most of the 32 (model x feature-set x selective/non-selective) configurations had NEGATIVE Sharpe; only a minority were profitable, best Sharpe = 0.57 (RF ternary selective, FS3), best binary selective = 0.33 (NN, FS1). LSTMs were never profitable. Implication: an entry-edge estimator must be fit and validated on a net-of-cost target, not a gross one.

[44|primary] The value of abstention INCREASES with transaction costs — selective classifiers beat their non-selective counterparts by a widening margin as slippage rises from 0 to 0.5 ticks, because abstention avoids position flips and the slippage paid on each contract traded. Argues an abstention gate is worth more, not less, in a high-cost venue (crypto perps: taker fees + funding).

[45|primary] Richer feature sets did not improve results: FS4 (adding trade-direction/aggressiveness i.e. taker-flow features plus volume-at-price to OHLCV + moving averages) was beaten by the minimal FS2, and FS3 was the WORST; random forests degraded on richer sets, attributed to overfitting. Transfer caveat: features were on 30-minute bars of CME metals futures (GC/HG/PA/PL/SI, 97482 bars, 2011-02-14 to 2019-05-31), NOT 500ms L2 crypto book — so this is weak evidence against microstructure alphas at sub-minute horizons; it only shows bar-aggregated taker flow adds nothing at a 30-minute horizon.

[46|primary] Realistic crypto-perp execution simulation requires full order-book reconstruction from Level-2 market-by-price or Level-3 market-by-order feeds — implying the entry snapshot must carry full multi-level book state, not just top-of-book or bar data.

[47|primary] Net-edge estimation for passive/limit entries must model order queue position at fill time; hftbacktest treats queue-position modeling as a first-class, swappable component of fill simulation rather than an optional refinement.

[48|primary] Both feed latency (data arrival) and order latency (round-trip to exchange) must be modeled separately, meaning an entry snapshot needs its own exchange-timestamp and local-receipt-timestamp fields to be usable for edge fitting.

[49|primary] The project's stated validation bar is period-matched live-vs-backtest reconciliation: a backtest replayed over the exact period a strategy traded live should closely reproduce the live results — a falsifiable alternative to in-sample backtest Sharpe as a gate.

[50|primary] The tooling targets exactly the venues in question (Binance Futures, Bybit) and points to hosted Binance USD-M tick datasets, so L2-based entry-edge fitting on crypto perps is an already-operational workflow; MIT-licensed, Rust-cored (75.9%) with a Python 3.11+ API, latest release rust-v0.9.4 / py-v2.4.4.

[51|primary] On Binance BTC/USD perpetual futures, order-flow market impact is large and positive only at the contemporaneous 5-second bucket and turns slightly negative for all subsequent lags, with cumulative impact decaying as a power law over ~100 subsequent 5s periods (~500 seconds). This bounds the horizon at which taker-flow impact information lives to roughly seconds-to-minutes, not hours — directly testable against our aggTrade + 500ms L2 data.

[52|primary] The Square-Root law of market impact holds empirically on Binance BTC/USD perps with a fitted exponent of delta = 0.59 (not the assumed 0.5), in the form I(Q,T) = k*sigma_T*(Q/V_T)^delta, where sigma_T is realized volatility and V_T is a recency-weighted average traded volume over a T = 1 hour trailing window. This gives a concrete, checkable slippage/net-edge cost model requiring exactly three snapshot fields at entry: intended net size Q, trailing 1h volatility sigma_T, and trailing 1h weighted volume V_T.

[53|primary] Market impact in BTC/USD perps is intertemporally conditional on the SIGN of the previous period's net taker flow: 5s periods following net-buy flow realize systematically lower impact than periods following net-sell flow. This makes lagged signed net taker volume a required entry-snapshot field, since impact/slippage at entry is not a function of current order size alone.

[54|primary] Trade-sign (order-sign) autocorrelation in BTC/USD perps decays as a clean power law, empirically confirming metaorder splitting in crypto perps. This means trade-sign imbalance carries persistent, long-memory predictive structure and that consecutive aggTrade signs are NOT independent — which invalidates IID sample assumptions in any CV scheme fit on overlapping order-flow windows.

[55|primary] The paper's empirical impact findings are derived only from executed-order (Level 3 trade) data on Binance BTC/USD perps from July 2020 to October 2021, WITHOUT limit-order submission or cancellation data — so its delta = 0.59 and decay-kernel results are not validated against book-dynamics features (queue imbalance, book slope, cancellations), and the authors explicitly defer empirical tuning and derivation to future work rather than presenting an out-of-sample validation.

[56|secondary] Equal-width (fixed-bin) ECE systematically UNDERESTIMATES true miscalibration and is a lower bound; equal-mass/quantile binning (ACE / ECE-EM) has strictly lower bias and faster convergence. Directly falsifiable: if you gate trades on a fixed-bin ECE, your model is more miscalibrated than the number says — switch the abstention gate's calibration check to quantile bins.

[57|secondary] The standard 'plugin' ECE estimator is biased and produces too many false alarms — it rejects well-calibrated models too often. Any hypothesis test of 'is my entry-edge model calibrated?' must use the de-biased estimator (subtracting the c_b(1-c_b)/(n_b-1) term for l2, or a Monte-Carlo bias correction for l1), otherwise the calibration test itself is invalid.

[58|secondary] Brier score and NLL conflate accuracy with calibration and are not 'complete' (a perfectly calibrated classifier does not score zero even at infinite N). Falsifiable consequence: a low Brier/log-loss on an entry-edge model is NOT evidence the probabilities are trustworthy enough to size on — calibration must be measured with a dedicated calibration metric alongside the proper score.

[59|secondary] Kernel/KDE-based calibration estimators outperform bin-based metrics on the rate of decline of mean-squared error with sample size — i.e. at the finite sample sizes of a trade journal (hundreds to thousands of entries), a KDE calibration estimator is measurably more efficient than binned ECE.

[60|secondary] Binned calibration error is not a fixed quantity: it increases monotonically with bin count, true calibration is unmeasurable with finitely many bins, and on FINITE datasets ECE can go either way (under- or over-estimate). So any single reported ECE number is an artifact of the bin choice and cannot be compared across models unless bin scheme and N are held fixed.

[61|primary] Order flow adds only marginal predictive value over a pure L2 book-shape baseline for 1m/5m state transitions in BTC/ETH perps: pooled overlay improvement was +0.010 vs a flow-shuffle null 95th percentile of +0.004 (1m) / +0.003 (5m) — i.e. barely above noise, and for BTC no regime cleared the flow test at both horizons.

[62|primary] The pre-event L2 liquidity state (spread, top-20 depth, top-20 imbalance) is a stronger predictor than order flow, improving over the marginal baseline by +0.034 (1m) and +0.045 (5m) — roughly 3-4x the order-flow overlay's +0.010.

[63|primary] Order-flow predictive power is state-dependent and concentrates in stressed liquidity regimes: for ETH the 1-minute overlay increment rises monotonically from +0.004 (calm) to +0.020 (mixed) to +0.038 (stressed), implying entry snapshots must record the liquidity regime to condition on it.

[64|primary] Absolute predictability of L2 state transitions at 1-5 minute horizons is low: the L2-shape model reached 0.586 (1m) and 0.554 (5m) classification accuracy against majority base rates of 0.571 and 0.532 — an edge of only ~1.5-2.2 percentage points over always guessing the majority class.

[65|primary] Validation used rolling monthly out-of-sample folds with event-clustered validation and a permutation null with feature shuffling blocked by month, symbol, and pre-event state — a concrete blocked-permutation protocol for testing whether an order-flow feature beats chance, over 47,513 windows per horizon.

[66|primary] Order imbalance measured at quarter-hour clock openings forecasts crypto perpetual-futures returns at a 4-to-12-hour horizon — i.e. order-flow predictive power in this study lives at multi-hour, not second- or minute-scale, horizons, and is conditional on clock phase.

[67|primary] Predictive power of order imbalance is strongest at quarter-hour marks and monotonically weaker at finer clock marks (one- and five-minute), implying that time-of-clock phase must be recorded at entry as a conditioning variable for any order-flow alpha.

[68|primary] Binance perpetual contracts exhibit periodic bursts in volatility and volume at one-, five-, and quarter-hour marks, so unconditional pooling of order-flow features across clock phases mixes structurally different regimes.

[69|primary] The periodic bursts are attributable to algorithmic participation, identified via a decline in trade-size roundness within the bursts — making trade-size roundness a recordable, cheap proxy for algo participation at entry.

[70|primary] Conventional (non-phase-resolved) autocorrelation measures conceal the serial dependence in order flow and returns that exists at quarter-hour openings, meaning standard time-series diagnostics will fail to detect this effect.

[71|primary] Selecting strategy configurations by in-sample optimization score carries a measured 58.6% probability of backtest overfitting (CSCV/PBO), even when strict t+1 execution and realistic costs are already enforced — i.e. strict semantics and cost realism do NOT rescue a score-ranked gate, which is the exact failure mode of an in-sample-Sharpe selector over 142 strategies.

[72|primary] On BTC/USDT 4h perps with parameters held fixed, a fee-only cost model inflates annualized return from 2.726 to 4.308 (CAGR, decimal; +58%) and Sharpe from 2.049 to 2.506 versus a fully costed run including slippage and funding; a zero-cost run inflates further to 5.225 CAGR / 2.711 Sharpe. Net-edge estimation must therefore charge fees AND slippage AND funding carry, not fees alone.

[73|primary] The effective number of trials for a deflated-Sharpe adjustment must count window re-evaluations and cost-scenario evaluations as selection degrees of freedom, not just the optimizer trials: 40 configs x 9 windows x 9 cost scenarios yields Ntotal in [360, 3240], and after that deflation the flagship configuration's long-window Sharpe provides no evidence against a zero-true-Sharpe null.

[74|primary] This paper contributes NOTHING to the microstructure-alpha, labeling, or entry-snapshot portions of the question: its entire empirical result set is generated from 4-hour OHLCV plus an 8-hour funding series only — no order book, no trade-level flow, no OI, no liquidations — and the framework explicitly refuses to generate or evaluate predictive signals.

[75|primary] Contrary to the common assumption that same-bar (t+0) execution universally inflates backtest results, across the top-30 Stage I trials on BTC/USDT 4h the median NAIVE-minus-STRICT uplift in annualized return was -0.018 with only 36.7% of trials showing positive uplift — so look-ahead-in-execution is not the source of the score/profit gap; selection bias is.

[76|primary] PROVENANCE CAVEAT — the source body could not be retrieved (ScienceDirect/SSRN/ACM all 403). This claim comes from a search-engine summary of the abstract, NOT verified against the paper: the study reports CPCV (Combinatorial Purged Cross-Validation) as superior to traditional out-of-sample methods at mitigating overfitting, evidenced by lower Probability of Backtest Overfitting (PBO) and a superior Deflated Sharpe Ratio test statistic. Directly relevant to replacing an in-sample-Sharpe gate. TREAT AS UNVERIFIED PENDING FULL-TEXT ACCESS.

[77|primary] PROVENANCE CAVEAT — from search-engine summary of the abstract, not verified against the paper: Walk-Forward validation is reported to perform poorly at preventing false discoveries, with higher temporal variability and weaker stationarity than CPCV. Bears on validation-method choice for the entry-edge model. TREAT AS UNVERIFIED.

[78|primary] VERIFIED via Crossref API (not the paywalled page): the paper's reference list confirms its methodological lineage — it cites de Prado 'Advances in Financial Machine Learning' (2018), Bailey et al. 'The probability of backtest overfitting' (J. Comput. Finance 2016), and Bailey & de Prado 'The Deflated Sharpe Ratio' (J. Portf. Manag. 2014). This confirms PBO and DSR are the paper's actual evaluation metrics and that those three works are the canonical primary sources to consult directly.

[79|primary] VERIFIED via Crossref API: the 'synthetic controlled environment' is built on Heston (1993) stochastic-volatility and Merton (1976) jump-diffusion processes, and the authors published a reference implementation (RiskLabAI Python/Julia libraries, plus a repo specifically implementing this paper). LIMITATION for the research question: results are from SYNTHETIC simulated price processes, not real crypto perpetual-futures order-flow data, so the CPCV-beats-walk-forward finding is not empirically validated on crypto microstructure. The RiskLabAI code is directly reusable for building a CPCV/PBO/DSR gate.

[80|blog] Top-of-book OFI on BTCUSD (Coinbase, 1-second buckets) explains ~40% of CONTEMPORANEOUS return variance but only ~3% of NEXT-bucket return variance — i.e. ~92% of the apparent explanatory power of OFI is same-bar contamination, not prediction. Any entry-time edge model must be fit on properly lagged close-to-close returns or it will report a ~13x inflated R².

[81|blog] The correctly-specified predictive OFI signal remains highly statistically significant out-of-sample (coefficient 0.144, t-stat 49.33, p<1e-99, OOS R² 0.0305 vs IS 0.0337 — almost no IS/OOS decay), so OFI's directional information at the ~1-second horizon is real and survives OOS, unlike our 142-strategy backtest-Sharpe gate.

[82|blog] Statistically-significant-and-OOS-stable OFI still produces only a 53.0% hit ratio and a Sharpe of 0.12, which is not tradeable once costs are applied — proving that statistical significance of a microstructure alpha is NOT sufficient for a net-edge gate; a fee/slippage cost model must be applied before the signal is accepted.

[83|blog] OFI's documented predictive power in this study lives at the ~1-second bucket horizon, computed from best-bid/best-ask price and size changes only (top-of-book, no multi-level depth), with five-minute rolling averages used only for normalization — the article provides no evidence for OFI predictive power at minute or hour horizons.

[84|blog] The recommended practical deployment of an OFI signal of this strength is as an overlay on market-making or execution algorithms rather than as a standalone directional entry signal, implying OFI should enter our entry-edge model as a cost/timing term rather than the primary direction driver.

[85|primary] The paper's entire empirical edge estimate lives at a 3-second horizon on Binance Futures perps: the target is the log mid-price return 3 seconds ahead, fit on 1-second order book + trade snapshots. This is direct evidence that documented order-flow predictive power in crypto perps lives at the seconds scale, not minutes/hours — and that a 500ms L2 snapshot is the right sampling rate for it, while a 5m-bar / backtest-Sharpe gate operates far outside the horizon where these features are shown to work.

[86|primary] Order flow imbalance is the dominant predictive feature and its effect is monotone with concavity at the extremes — the relationship is nonlinear and saturates, so the entry snapshot must record the raw signed imbalance value (not a bucketed or binary version) for the curve to be fittable.

[87|primary] A deliberately SHALLOW feature set is used and deep book levels are explicitly rejected as noise. The named entry-snapshot schema is: mid price, spread, level-1 bid/ask volumes, signed order flow / net traded volume, and buy-VWAP−mid plus sell-VWAP−mid deviations. This contradicts the assumption that all 20 L2 levels are needed for edge estimation.

[88|primary] Predictive effects are conditional on spread — wider spreads attenuate predictive effects and yield lower-confidence signals via adverse selection. Spread-at-entry is therefore a required snapshot field and a natural abstention/gating variable; edge is not stationary across spread regimes.

[89|primary] The execution/cost assumption flips the sign of the result on the SAME signal: modeled as taker (buy at best ask, sell at best bid, inventory marked to the unfavorable side), ARC/IR is positive on ETC (5.78/8.97), ENJ (4.06/6.58), ROSE (7.00/5.28) with p<0.05; the maker version loses on ENJ (−0.81) and ETC (−0.07) and took catastrophic adverse-selection losses in the Oct 10 2025 flash crash. Net edge is inseparable from the fill assumption, so entry snapshots must record best bid, best ask, and intended fill side.

[90|primary] OFI, defined at Level-1 as the net signed change in best bid/ask queue sizes (aggregating limit orders, market orders and cancellations), explains contemporaneous mid-price changes linearly with an average R^2 of 65% across 50 S&P 500 stocks over 10-second intervals — and this is a CONTEMPORANEOUS/instantaneous-impact regression, not an out-of-sample forecast, so it is not itself evidence of predictive edge.

[91|primary] OFI strictly dominates trade-sign/volume imbalance (TI): average R^2 65% for OFI vs 32% for TI, and when both are regressed together TI's average t-statistic falls by a factor of four and is significant in only 31% of subsamples — i.e. taker-flow imbalance adds nothing once book-event OFI is recorded.

[92|primary] The price impact coefficient beta is inversely proportional to market depth with exponent lambda ~= 1 (beta = c/AD^lambda; lambda=1 not rejected for 35 of 50 stocks), so any entry snapshot must record average best bid/ask queue size (depth) alongside OFI to normalize the coefficient — beta is not a constant, it varies intraday with depth.

[93|primary] The relation is stable across aggregation timescales from ~10 quote updates (sub-second) up to 10 minutes, with fit generally improving as the interval lengthens; event-level autocorrelations vanish after ~10 seconds, which is why the authors use a 10-second grid.

[94|primary] A large part of the 65% R^2 is mechanical/tautological because OFI contains price-changing events; excluding those events drops R^2 to 35-60%. Also, the apparent concave 'square-root' price impact of trade volume is a statistical artifact of aggregation, not a real law.

[95|primary] Under backtest overfitting the in-sample-to-out-of-sample performance relationship is NEGATIVE, not merely zero: the regression slope beta of SR_OOS on SR_IS is negative in most practical cases, so ranking strategies by IS Sharpe actively selects the worst OOS performers. This directly predicts the observed -0.031 correlation and 'highest-score quartile is the WORST' pattern in a 142-strategy IS-Sharpe gate.

[96|primary] A high in-sample Sharpe ratio carries essentially zero information about OOS validity: in a controlled experiment on a pure random walk (no true signal), a seasonal strategy search produced SR_IS between 1 and 2.2 with 100% positive IS Sharpes, yet ~53% of SR_OOS were negative and PBO was 55%. CSCV correctly diagnosed the overfit; a PSR-Stat of 2.83 (implying <1% chance true Sharpe < 0) did NOT.

[97|primary] Overfitting is unavoidable whenever more than one strategy configuration is tried (proven in Bailey et al.), and hold-out / single train-test splits cannot assess a backtest because they ignore the number of trials attempted. The correct output is therefore not a pass/fail but a probability conditional on trial count — meaning a 142-strategy selection gate is guaranteed-overfit by construction unless trial count is explicitly modeled.

[98|primary] PBO is defined as the probability that the configuration selected as optimal in-sample underperforms the MEDIAN of the N configurations out-of-sample, estimated via CSCV as phi = integral of f(lambda) from -inf to 0 over the logit distribution; the authors give an explicit operational reject threshold of PBO > 0.05, and recommend S = 16 partitions (yielding 12,780 combinations, sigma[f(lambda)] < 0.0045) with N >> 10 trials for granularity.

[99|primary] CSCV yields a stochastic-dominance test that directly answers whether an IS selection procedure beats random selection among the N candidates — if the distribution of OOS performance for IS-optimal picks does not dominate the overall OOS distribution, the selection procedure adds no value. Separately, OOS probability of loss Prob[R_n* < 0] is a distinct diagnostic: it can be high even when PBO ~ 0, meaning the strategy is simply bad rather than overfit.

[100|primary] The paper does NOT predict return direction or trade edge at all — its labels are the sign of the change in distributional/liquidity statistics (realized volatility, kurtosis, Jarque-Bera, serial correlation, skewness), not future returns. It is therefore evidence that microstructure measures forecast volatility/liquidity regime, not directional edge.

[101|primary] Random-forest predictive accuracy from 5 microstructure measures (Roll, Roll impact, Kyle's lambda, Amihud, VPIN) across 5 coins is only 0.52–0.58 (AUC 0.53–0.54 on average); it is highest for the sign of change in realized volatility (0.56–0.58) and exactly 0.50 — i.e. zero skill — for skewness.

[102|primary] The predictive horizon is one day ahead from features built on 1-minute bars with 50- or 100-bar lookback windows, re-predicted every minute; the authors handle overlapping-sample leakage by pushing the prediction far enough ahead to avoid overlapping data rather than by purging/embargo, and the paper contains zero use of purged K-fold, CPCV, PBO, deflated Sharpe, triple-barrier, meta-labeling, or conformal prediction.

[103|primary] In crypto, Kyle's lambda carries essentially no feature importance (near-zero MDA), the Roll measure is the single most important own feature, and own VPIN is frequently important — a ranking that differs from futures markets where Amihud and VPIN dominated. BTC and ETH Roll/VPIN carry cross-market predictive power while other coins' cross-measures have virtually none.

[104|primary] The entire study is built only on Binance 1-minute OHLCV candlestick bars for the top-5 coins (BTC, ETH, ADA, SOL, XRP), Jan 2021–Jul 2023 — no L2 order book, no order-flow imbalance, no queue imbalance, no microprice, and zero mentions of perpetual futures, funding rates, open interest, or liquidations. Its VPIN levels of 0.45–0.47 far exceed the 0.22–0.23 found for E-mini S&P500 and crude oil futures.

[105|primary] Selecting the best of N backtested strategies inflates Sharpe even with ZERO true skill: the expected MAXIMUM Sharpe across N independent trials grows as E[max SR] = E[SR] + sqrt(V[SR]) * ((1-gamma)*Z^-1(1-1/N) + gamma*Z^-1(1-1/(N*e))), where gamma is Euler-Mascheroni (~0.5772). This is directly falsifiable by simulation and is implemented in the paper's own Python snippet (getExpMaxSR). Directly indicts a max-Sharpe-over-142-strategies gate: with N~142 the null threshold is roughly 2.5 sigma of the cross-trial SR dispersion, so the winner's Sharpe carries no evidence of skill unless it exceeds that.

[106|primary] Backtest overfitting does not merely produce zero out-of-sample edge — in the presence of memory effects (which most financial series exhibit) it systematically produces NEGATIVE out-of-sample performance, i.e. loss maximization. This is the precise mechanism predicting the observed pathology that the highest-backtest-score quartile is the WORST realized performer (-0.031 correlation, 29.2% win rate): the selection gate is not noise, it is inverted, and the paper claims a formal proof exists in Bailey et al. (2014).

[107|primary] To compute DSR and thus validate ANY selected strategy, exactly seven quantities must be recorded — five beyond the standard Sharpe inputs: (1) SR_hat of the selected strategy, (2) T = sample length (number of return observations), (3) skewness of the selected strategy's returns, (4) kurtosis of its returns, (5) V[{SR_n}] = variance of estimated Sharpe ratios ACROSS ALL trials (including rejected ones), (6) N = number of INDEPENDENT trials. This mandates logging every rejected trial's Sharpe, not just the winner's — a concrete data-capture requirement for any replacement gate.

[108|primary] Holdout and k-fold cross-validation CANNOT prevent backtest overfitting, because they assess generality as if a single trial occurred; applying holdout ~20 times makes a false positive at 95% confidence expected rather than unlikely. Falsifiable and directly relevant: any proposed replacement gate that relies on plain OOS holdout or vanilla K-fold over 142 strategies inherits the same defect the current gate has.

[109|primary] When M trials are correlated rather than independent, the number of implied independent trials is N_hat = rho_hat + (1 - rho_hat) * M, where rho_hat is the average off-diagonal correlation of trial returns; average correlation is bounded below by -1/(M-1). Using M instead of N overstates the threshold. Concretely falsifiable, and load-bearing for a 142-strategy library where strategies are heavily correlated: the effective N must be estimated from the cross-strategy return correlation matrix (or via entropy/information-theoretic redundancy), which requires storing per-trial return series.

[110|primary] Integrated multi-level OFI (first PCA principal component of OFIs across the top 10 book levels, each scaled by average depth) massively outperforms best-level/top-of-book OFI for explaining contemporaneous returns: in-sample adjusted R² 87.14% vs 71.16%, and out-of-sample R² 83.83% vs 64.64% on 30-minute-window fits of 1-minute bins. Implication for entry snapshot: record per-level order flow at all L2 levels (not just L1 imbalance), plus average depth for scaling.

[111|primary] Contemporaneous explanatory power does NOT transfer to prediction: for one-minute-AHEAD returns, every model tested (best-level OFI, integrated OFI, cross-asset OFI, and autoregressive returns) has NEGATIVE mean out-of-sample R², from -0.37 to -0.10 — i.e. all are worse than predicting zero. This is a direct, peer-reviewed instance of the user's failure mode: high in-sample/contemporaneous fit with zero-to-negative realized predictive value. The authors argue negative R² still permits economic gain, so P&L (not R² or fit score) must be the gate.

[112|primary] Order-flow predictive power lives at SHORT horizons and decays rapidly: cross-asset OFI forecasting advantage is concentrated at short-term horizons, and annualized PnL of the models is measured across a 1/3/10/30-minute grid with cross-asset models' PnL declining fastest as the horizon lengthens. This bounds the useful entry-edge horizon for order-flow features to roughly seconds-to-minutes, not hours.

[113|primary] Multi-level OFIs are highly collinear — the first principal component alone explains over 89% of total variance across the 10 levels — which is why a single PCA-integrated OFI variable is preferred over feeding 10 raw level-OFIs to the model, explicitly as an overfitting-avoidance measure.

[114|primary] Once multi-level information is integrated into OFI, cross-asset (cross-impact) terms add essentially nothing to contemporaneous price impact — only a 0.71 percentage-point in-sample R² gain, and out-of-sample the cross-impact model is actually slightly WORSE (83.62% vs 83.62% for the single-asset integrated model). Cross-asset OFI only earns its keep in the LAGGED/forecasting setting, and for portfolio-level returns.

[115|primary] Differencing the limit order book into stationary order-flow inputs materially beats feeding raw order-book levels to the same neural architectures; stationarity of the RHS inputs — not model complexity — is the dominant driver of out-of-sample forecast accuracy. In the paper's own R2_OS charts, OF-input models span roughly 0 to +1.25% while raw-LOB-input models run negative (to about -2.0%) at short horizons, and simple LSTMs match or beat CNN-LSTM/DeepLOB once inputs are converted to order flow.

[116|primary] Order-flow predictive power lives in EVENT time, not clock time: the effective forecast horizon is approximately two (to three) average price changes. The paper defines a stock-specific increment dt = 2.34e7 / N milliseconds, where N is the average number of non-zero tick-by-tick mid-price returns per day, and tests horizons of (1/5)*k*dt for k=1..10 — i.e. between 0 and 2 average price changes. This directly answers the 'seconds vs minutes vs hours' question: horizon must be normalized per instrument by its own update/price-change rate, because 'information flows at different rates for different stocks and so horizon cannot be constant in time across stocks.'

[117|primary] Multi-level ORDER FLOW (per-level bid and ask flows concatenated, OF_t in R^20 over 10 levels) outperforms multi-level ORDER FLOW IMBALANCE (bid minus ask, OFI_t in R^10) as a model input — the subtraction that defines OFI destroys information the network can otherwise use. Stripping prices from the LOB helps, but concatenated order flow is still the best RHS. This is a falsifiable design instruction: snapshot per-level signed bid-OF and ask-OF SEPARATELY rather than only their difference.

[118|primary] The achievable out-of-sample R2 at these horizons is small in absolute terms (roughly 0-1.25%, averaging up to ~4-5% for the most predictable stocks), and the authors' claim that this converts to profit rests on horizon speed rather than any demonstrated net-of-cost backtest — the deck presents no transaction-cost, fee, or slippage model. The only concession to execution reality is a fixed 10ms latency buffer. So this paper validates SIGNAL, not NET EDGE; a cost model must be supplied separately before treating R2_OS ~1% as tradeable.

[119|primary] Validation is strict rolling walk-forward, not random K-fold: a (1,4,1) week configuration — 1 week validation for early stopping, 4 weeks training, 1 week out-of-sample test — stepped forward 3 weeks at a time, over Jan 1 2019 to Jan 31 2020 LOBSTER data on 115 Nasdaq stocks, yielding 12 x 115 x 18 (models x stocks x time periods) separately fitted networks. All independent and dependent variables are winsorized and Z-scored. A fixed 10ms latency buffer is inserted into every interval to mimic a production setting.

[120|primary] Order flow imbalance, bid-ask spread, book depth, and VWAP-to-mid deviation are the dominant short-horizon predictors of crypto perp returns by mean-absolute SHAP, and their ranking is STABLE across assets of very different liquidity (BTC vs long-tail ENJ/ROSE) — implying these are the entry-snapshot fields with the strongest documented cross-asset generalization.

[121|primary] A gradient-boosted tree model (CatBoost) on top-of-book + trade-flow tabular features is sufficient to produce statistically significant tradable signals on crypto perps — no deep LOB architecture (DeepLOB/transformer) was required, and deep order-book levels were explicitly omitted as redundant.

[122|primary] Label design matters more than architecture: replacing squared error with a direction-aware loss (GMADL) that rewards sign correctness is what converts forecasts into tradable signals — i.e. train on directional/risk-adjusted loss rather than plain magnitude regression.

[123|primary] Leakage-safe evaluation requires walk-forward CV with an explicit temporal GAP (purge/embargo) between train and validation, and SHAP attribution computed on held-out samples — not in-sample. This directly contradicts an in-sample-backtest-Sharpe gate.

[124|primary] Execution style, not signal quality, decides survival in tail regimes: with the SAME model, taker execution profited from the 2025-10-10 flash crash while maker execution suffered catastrophic losses via adverse selection (repeatedly filled on the bid into a falling market); taker strategies were statistically significant (p<0.05 on ETC/ENJ/ROSE) while ALL maker strategies were not.

[125|primary] Order flow imbalance computed across MULTIPLE order-book levels (not just the best bid/ask) carries additional explanatory power for price moves beyond best-level OFI — directly implying that a 20-level L2 snapshot should record per-level OFI, not just top-of-book.

[126|primary] A PCA-integrated OFI (first principal component across per-level OFIs) outperforms individual-level OFIs both in-sample AND out-of-sample — i.e. the dimensionality reduction is not an in-sample artifact.

[127|primary] Cross-impact terms (other assets' order flow affecting this asset's price) are SUBSUMED by multi-level OFI: once multi-level OFIs are in the model, cross-impact adds nothing to contemporaneous explanatory power — so multi-level own-book OFI should be built before any cross-sectional order-flow machinery.

[128|primary] For FORECASTING future returns (as opposed to contemporaneous impact), cross-sectional OFIs DO add value, significantly raising out-of-sample R^2 — meaning a per-coin entry snapshot should include OFI of correlated coins (e.g. BTC/ETH), even though cross-impact is redundant contemporaneously.

[129|primary] The cross-impact structure is sparse: LASSO regularization is required because only a small subset of cross-asset order-flow terms matter — a warning against dumping all 200 coins' OFI into an unregularized model.

[130|primary] Realistic fill simulation for perp market-making/HFT strategies requires explicit modeling of order queue position and both feed and order latency — a backtester that omits these produces fills that do not correspond to live results, which directly explains a gate whose in-sample Sharpe has zero correlation to realized profit.

[131|primary] The project sets an explicit falsifiable validation standard for a backtest gate: a backtest over a period must reproduce the live results of the same strategy over that exact period; this is a stricter and checkable replacement for an in-sample Sharpe gate.

[132|primary] Both overly optimistic and overly pessimistic backtest assumptions are treated as failure modes — i.e., a backtest gate can silently fail in either direction, not just by over-fitting upward.

[133|primary] Full L2 (market-by-price) and L3 (market-by-order) order book reconstruction with tick-by-tick simulation is achievable on CPU-only infrastructure for Binance Futures and Bybit perps, using Rust plus Numba-JIT'd Python strategy callbacks — no GPU is implied anywhere in the stack.

[134|primary] Order-book imbalance and queue-position-based signals are treated as first-class, documented strategy families for large-tick assets rather than speculative research ideas, indicating these microstructure predictors are the practitioner-validated baseline for perp entry edge.

[135|primary] Pre-event L2 liquidity state (discretized terciles of spread, depth-20, imbalance-20) is the dominant predictor of post-event liquidity regime, and order flow adds value only as an overlay on top of the L2 state model — never as a replacement. This implies an entry snapshot must capture the L2 state variables first, with order-flow features layered on.

[136|primary] Order flow's incremental predictive value is state-dependent and rises monotonically with stress regime: for ETH the order-flow gain is +0.004 (calm), +0.020 (mixed), +0.038 (stressed) at the 1-minute horizon — so a regime/liquidity-state field must be snapshotted at entry to condition on when order-flow features are trustworthy.

[137|primary] Order-flow edge does not generalize across assets: pooled order-flow overlay improvement is +0.010 at both horizons vs a null 95th percentile of +0.004/+0.003, but per-asset ETH clears (+0.020 1m, +0.016 5m) while BTC does not (+0.001 1m, +0.003 5m). Cross-sectional pooling can therefore manufacture a false edge that is really one asset.

[138|primary] A shallow nonlinear gradient-boosted classifier over L2 book-shape features beats both the coarse-state baseline (+0.044 at 1m, +0.060 at 5m) and multinomial/ordered logit over continuous L2 features, which actually worsens on the coarse state (−0.048 at 1m, −0.034 at 5m). Linear models over continuous book features are worse than simple discretized state.

[139|primary] Volatility-regime terciles are a much weaker conditioning variable than liquidity state: volatility terciles contribute only +0.008 to +0.015 versus the L2 state's +0.026 to +0.029, so liquidity state should be preferred over vol regime as the snapshot-at-entry context field.

[140|primary] Under purged, embargoed walk-forward CV (k=12, 60-min embargo, 5-min purge) on 3.4M minute-level Binance spot+perp observations across 6 coins, LightGBM was SIGNIFICANTLY WORSE than a random walk out-of-sample (R2 = -10.94%, Diebold-Mariano = -6.83), while plain OLS on the same microstructure features gained only +1.23% R2 (DM = 1.28, not significant). This directly falsifies the assumption that a well-tuned GBM on microstructure features beats a naive baseline at 5-min horizons.

[141|primary] Range-based spread proxies and realised volatility are the most robust/stably-selected microstructure predictors at minute frequency (stability-selection scores: realised vol 0.84, 5-min momentum 0.83, Corwin-Schultz spread proxy 0.79 vs 0.5 threshold), whereas the Amihud illiquidity ratio and Kyle's lambda were individually INSIGNIFICANT. Corwin-Schultz spread coefficient = -0.0031 (most significant).

[142|primary] Cross-asset transfer fails in crypto microstructure: a model trained on one cryptocurrency achieves only ~0.1-0.2 zero-shot transfer correlation to a different coin, while SAME-asset cross-venue transfer (spot <-> perp futures) is substantially higher (block-diagonal structure). Implication: per-symbol models, not one pooled 200-coin model; but spot and perp of the same coin can share a model.

[143|primary] 5-min-rebalance microstructure strategies require 124-204x notional daily turnover, and at Binance VIP-0 fees (10 bps spot, 2-5 bps futures) plus half-spread slippage every net Sharpe was deeply negative (-52 to -10). Any entry-edge gate must therefore be scored NET of fees+half-spread at realistic turnover, not on gross in-sample Sharpe.

[144|primary] LightGBM's failure is regime-concentrated, not uniform: OOS R2 is ~0% in calm markets but about -25% in high-volatility markets and similarly catastrophic in down-markets, because the model latches onto tail events. This argues for an explicit volatility/regime state variable snapshotted at entry and regime-conditional abstention.

[145|primary] Roll measure (serial-correlation/effective-spread proxy) and VPIN are the two dominant out-of-sample predictors of crypto price dynamics, ranked by out-of-sample MDA — while Kyle's lambda is essentially useless (near-zero MDA) and Amihud/Roll-impact only occasionally matter. This directly ranks which microstructure fields to snapshot at entry: own Roll, own VPIN, plus BTC Roll/VPIN and ETH Roll/VPIN as cross-market features.

[146|primary] The predictable target is the SIGN OF CHANGE IN REALIZED VOLATILITY (accuracy 0.56–0.58, AUC 0.53–0.54 over a ~1,500-bar / ~1-day look-ahead), NOT return direction — the paper never predicts price direction. Skewness is entirely unpredictable (accuracy/AUC = 0.50). This is a label-design result: microstructure measures forecast the second moment and autocorrelation, not the sign of returns.

[147|primary] Cross-sectional structure is real but NARROW: only BTC and ETH Roll/VPIN carry cross-market predictive power for other coins; all other cross-crypto features have near-zero MDA. So a 200-coin cross-feature matrix should be pruned to BTC/ETH lead features rather than all-pairs.

[148|primary] Crypto VPIN levels are roughly double those of established futures markets (0.45–0.47 vs 0.22–0.23 for E-mini S&P 500 and crude oil), indicating structurally higher order-flow toxicity/adverse selection — a level effect an entry model should condition on, not just the delta.

[149|primary] These microstructure→dynamics relationships are regime-stable: splitting the Jan-2021–Jul-2023 sample at the onset of 'crypto winter' produced no material change in predictability, and swapping random forest for logistic regression gave similar results — evidence that Roll/VPIN edges are not regime-drift artifacts, though scale-dependent measures (Roll, Amihud, Kyle's λ) shift with price level while Roll Impact and VPIN (scale-free) stay stable and are therefore the safer fields to persist.

[150|blog] Computing a percentile rank of an indicator (e.g. VRP) against the FULL sorted history rather than only strictly-prior data is look-ahead leakage — the canonical silent failure mode for any percentile/z-score/rank feature.

[151|blog] Full-sample percentile gating inflates backtest Sharpe by roughly 15–30% versus walk-forward percentiles over a 5+ year window — i.e. leakage in a single feature can account for a large share of apparent in-sample edge.

[152|blog] Full-sample percentiles distort ranks non-uniformly across time: extremes are under-assigned early in the sample and over-assigned late, so the bias is not a constant offset that can be calibrated away.

[153|blog] The fix is to snapshot, at each decision time t, the percentile computed against only VRP values strictly before t — with a strictly-less-than timestamp predicate, not less-than-or-equal (the bar containing t must be excluded).

[154|blog] ML models fed full-sample percentile features will learn the leakage-encoded signal itself; walk-forward percentiles must be used as the feature, not just as a backtest gate.

[155|primary] Repeatedly iterating an ML model against backtest results produces a false discovery in roughly 20 iterations at the standard 5% significance level — and walk-forward/out-of-sample framing does not protect against this. This directly indicts using backtest Sharpe as a selection gate.

[156|primary] Selecting the max-Sharpe strategy across I trials on a true martingale yields an expected maximum Sharpe bounded by sqrt(2*log[I]) despite a true Sharpe of zero; therefore the number of trials I must be tracked or FWER/FDR/PBO cannot be computed, and the Deflated Sharpe Ratio adjusts the rejection threshold SR* for trial multiplicity using the variance across trials' Sharpe estimates.

[157|primary] Fixed-time-horizon labeling (predicting return over a fixed h bars vs a constant threshold tau) is defective because a constant threshold ignores observed volatility and ignores stop-outs; the triple-barrier method instead labels by which exit condition fires first (profit-take, stop-loss scaled to estimated volatility, or bar-count expiry), making the label path-dependent.

[158|primary] Side and size should be learned by two separate models rather than one: a primary model predicts the sign/side (tuned for high recall), and a secondary meta-labeling model predicts whether the primary's positive is true or false, raising F1 and limiting overfitting because ML never decides the side.

[159|primary] Standard k-fold CV leaks in finance because serially correlated features (X_t ≈ X_t+1) combine with time-overlapping labels (Y_t ≈ Y_t+1), letting a classifier score well on irrelevant features; the fix is purging (drop training observations whose label spans overlap the test labels) plus an embargo of h ≈ 0.01*T bars after each test set.

[160|primary] In a live Binance BTC-perp experiment (232,897 minimum-sized maker orders, Feb 12-19 2024; 127,051 filled), fill probability and post-fill return are NEGATIVELY correlated: orders posted with a favorable-looking book (large opposite-side queue, small near-side queue = adverse imbalance) fill with high probability precisely because the next price move goes against them (adverse selection). Consequence: any entry model whose signal is 'follow the order-book imbalance' at the touch is systematically selecting the losing side, and the viable maker edge is CONTRARIAN to the prevailing OBI.

[161|primary] Prediction accuracy is decoupled from economic value and must never be the gate; with a ~15% reversal base rate a model gets 85% accuracy by always predicting 'no', and conversely a model whose out-of-sample predictions are mostly FALSE POSITIVES can still be economically valuable if the post-fill returns of its selected orders beat randomly-placed orders. The paper's actual gate is a two-sample t-test of the strategy's post-fill returns against a random-order baseline, reported per decision threshold (e.g. t=3.06, p=0.0011 at the 0.30 LR threshold).

[162|primary] The naive/commonly-cited market-making strategy is measurably negative-expectancy on the most liquid crypto market: -0.44 bp average realized roundtrip return NET of the best-case 0.5 bp/leg maker rebate, at 15,380 fills/day, annualized Sharpe -109. Gating the SAME strategy on a predicted-reversal probability >0.24 flips it to +0.71 bp average roundtrip at 327 roundtrips/day, Sharpe +11.97 — i.e. the edge lives entirely in the entry FILTER, not the strategy. The authors explicitly caveat that this Sharpe assumes minimum order size and the best possible rebate and would degrade materially otherwise.

[163|primary] A plain LOGISTIC REGRESSION on 173 hand-built microstructure features beats a random forest benchmark on the same features at the thresholds that matter: on the out-of-sample Undirectional test, at threshold 0.40 LR yields +2.11 bp mean 5s post-fill return vs RF -0.33 bp; at 0.46 LR +3.45 bp vs RF +0.05 bp. RF only reaches positive returns at the extreme 0.46-0.50 thresholds. The authors avoided PCA/dimensionality reduction by DESIGNING the features to be near-orthogonal (consecutive non-overlapping lookback windows per timescale; timescales separated by ~1 order of magnitude), and encoded features direction-agnostically ('near-side'/'opposite-side' rather than bid/ask) so buys and sells share one model.

[164|primary] The exact entry-time feature set (all 173 computable at submission, no look-ahead) is enumerated in 4 groups: (1) Price Dynamics — stdev_100/stdev_500 (stdev of last 100/500 ten-second returns), plus per-timescale {100ms, 1s, 5s, 30s, 300s} x 3 non-overlapping windows {w0,w1,w2} of amplitude (max-min) and ret_vwap (log return of window VWAP vs current top-of-book); (2) Trade Volume Patterns — max_size, avg_size, buy_count, sell_count, total_buy, total_sell per window; (3) Momentum — ret_autocov (autocovariance of consecutive-trade returns), ret_sum, trade_intensity (avg time between trades) per window; (4) LOB State — top_bid_liq, top_ask_liq, ob_bid_half/ob_ask_half (bp distance from touch to VWAP of executing $500K that side), totb_mean (avg top-of-book survival time over past 10 min), age (seconds since last top-of-book price change). Fitted coefficients say reversals follow a sharp 100ms price drop after oscillating (low-autocovariance) 15s price action.

[165|primary] In-sample backtest Sharpe alone is not a valid selection gate: the expected MAXIMUM Sharpe across N trials is strictly greater than zero even when true skill is exactly zero, and grows with N and with the variance of the trials' Sharpes. Therefore any 'best backtest Sharpe' selected from a search over strategies/parameters carries a guaranteed upward bias that must be subtracted before the number is interpretable. Falsifiable via Eq.(1): E[max SR_n] = E[{SR_n}] + sqrt(V[{SR_n}]) * ((1-gamma)*Z^-1[1-1/N] + gamma*Z^-1[1-1/(Ne)]), gamma = Euler-Mascheroni ~0.5772.

[166|primary] Overfit backtests do not merely fail to generalize — in series with memory (mean reversion / equilibrium restoring), they produce SYSTEMATICALLY NEGATIVE out-of-sample performance ('loss maximization'), because the optimizer selects the rules that profited from the most extreme in-sample random patterns, which are precisely the patterns that get undone. This directly predicts the observed sign of the project's gate: a NEGATIVE (not merely zero) correlation between in-sample Sharpe and realized profit (-0.031, 29.2% win rate) is the expected signature of overfitting-under-memory, not bad luck.

[167|primary] To deflate a Sharpe ratio you must record FIVE fields beyond mean and stdev of returns, and these are exactly the fields that must be snapshotted at strategy-selection/entry time: (i) N = number of INDEPENDENT trials that led to the selection, (ii) V[{SR_n}] = variance of the Sharpe ratios across all trials attempted (including the discarded/negative ones), (iii) T = sample length in observations, (iv) skewness of the selected strategy's returns, (v) kurtosis of the selected strategy's returns. Without N and V[{SR_n}] logged at selection time, DSR is not computable after the fact — the discarded trials must be retained.

[168|primary] Concrete magnitude of the correction, falsifiable by recomputation: an annualized Sharpe of 2.5 measured over 5 years of DAILY data (T=1250) is NOT significant at 95% once selection bias is accounted for. With N=1000 independent trials, V[{SR_n}]=1/2 (non-annualized), skew=-3 and kurtosis=10, the deflated threshold SR_0 ~= 0.1132 (non-annualized) and DSR ~= 0.9004 — i.e. only a 90% chance the true SR exceeds zero. The same 2.5 Sharpe WOULD have passed at 95% had it come from only N=46 independent trials.

[169|primary] The holdout / train-test split and k-fold cross-validation CANNOT prevent backtest overfitting, because they score a model as if a single trial had occurred while ignoring the growth in false positives across repeated applications; applying holdout ~20 times makes a false positive EXPECTED rather than unlikely at a 95% level. Corollary claim: non-Normality is an independent inflation source that interacts with N — in the worked example, had returns been Normal (skew=0, kurt=3), DSR would have reached 0.95 at N=88 rather than N=46, i.e. negative skew and fat tails roughly halved the number of trials the evidence could tolerate.

[170|primary] In-sample Sharpe ratio is not merely uninformative about out-of-sample performance — the relationship is INVERSE: higher IS Sharpe predicts LOWER OOS Sharpe, so no IS-Sharpe threshold can be used as a selection gate. This directly falsifies the project's current gate (in-sample backtest Sharpe, measured correlation to profit -0.031, n=260, 29.2% win) and predicts that raising the IS-Sharpe bar would make live results worse, not better.

[171|primary] In an overfit backtest, a Sharpe ratio between 1 and 3 carries zero information about OOS representativeness: in the paper's worked example 100% of in-sample Sharpes were positive while ~78% of the corresponding out-of-sample Sharpes were negative. A near-zero IS-Sharpe-vs-profit correlation is therefore the EXPECTED signature of an overfit selection process, not an anomaly.

[172|primary] A few hundred search iterations over even a small parameter space is sufficient to produce strategies that look highly profitable in-sample while performing terribly out-of-sample — the authors demonstrate this with a public tool. This sets a concrete falsifiable bound: any pipeline that evaluates hundreds of strategies/feature sets (e.g. a 142-strategy library sweep) will manufacture spurious IS Sharpe by construction.

[173|primary] CSCV yields two DISTINCT and separately-reportable diagnostics that should replace a single IS-Sharpe gate: PBO (the rate at which the IS-optimal config underperforms the OOS median, derived from a distribution of logits) and the OOS probability of loss Prob[R < 0]. They are independent — a strategy can have PBO ~= 0 yet still be unprofitable. The paper's contrast is quantitative: an overfit example scores PBO 74%, a real strategy scores PBO 0.04% with ~3% OOS probability of loss.

[174|primary] On real crypto perp LOB data (Bybit BTC/USDT, 40 levels, 500ms horizon), a well-tuned XGBoost matches or beats DeepLOB and CNN+LSTM — 0.7281 vs 0.7189 binary accuracy — meaning deep LOB architectures give no edge over GBM on this task.

[175|primary] Feature/input quality dominates architecture depth: hand-crafted microstructure features (mid-price, level-1 order imbalance, five-level aggregate imbalance, 1/i-weighted mid-price change) plus Savitzky–Golay noise filtering produced the top accuracies, and the paper attributes performance to inputs and noise-handling rather than model capacity.

[176|primary] Adding short book history (sequence length T=10 vs T=1 over 100ms snapshots) yields a small but real out-of-sample gain — XGBoost 57.32% → 59.49% (+2.17%), logistic regression 55.51% → 57.16% (+1.65%) — at ~4.4x training cost (7m04s vs 1m36s).

[177|primary] Label design used is directional classification of mid-price move at 100/500/1000ms horizons, with class imbalance handled by inverse-frequency loss weighting and, for ternary labels, tuning the stationary band ε to equalize class frequencies.

[178|primary] The result is evidentially weak for generalization: all findings rest on a single trading day of one symbol (BTC/USDT, Jan 30 2025) with a plain chronological 80/20 split and no regime/multi-day robustness testing, so accuracy numbers should not be treated as regime-robust out-of-sample edge.

[179|primary] In crypto markets, the Amihud (2002) illiquidity ratio is the WORST performer at tracking time-series variation in true (order-book-derived) liquidity — it is essentially uncorrelated with quoted spread, effective spread, price impact and cost-of-roundtrip, and the correlation sign is even negative (wrong direction). Tested on BTCUSD/ETHUSD across Bitfinex, Bitstamp and Coinbase Pro, 2017-12-16 to 2019-12-16, against 50-level order-book benchmarks. This directly falsifies Amihud as a usable illiquidity feature for crypto entry models unless sign-corrected.

[180|primary] The mechanism behind Amihud's failure is that crypto violates its core assumption: volume is POSITIVELY related to execution costs in crypto (higher trading activity → wider spreads / higher impact), whereas Amihud assumes the opposite. Any feature built on the 'volume implies liquidity' premise will carry an inverted sign in crypto. The authors note this is not crypto-unique — Bogousslavsky and Collin-Dufresne (2020) document the same for large US stocks.

[181|primary] High/low-price-based estimators (Corwin-Schultz 2012 and Abdi-Ranaldo 2017) best capture the TIME-SERIES variation of true liquidity in crypto, with daily-frequency correlations of 0.54-0.75 against quoted spread, effective spread and cost-of-roundtrip, rising to 0.86 against price impact for both estimators. This holds across all data frequencies, all three exchanges, all four benchmarks, both coins, and across high/low return, volatility and volume sub-samples.

[182|primary] The Roll (1984) serial-covariance spread estimator performs WORST at capturing the level of the effective spread, and Roll/Corwin-Schultz/Abdi-Ranaldo all suffer a frequency-dependent small-sample bias: their estimated values inflate strongly as the estimation window lengthens. This means any of these three computed at a bar frequency different from the one it was validated at is not comparable — a concrete look-ahead/mis-specification trap for feature construction.

[183|primary] Simple trade-count and dollar-volume proxies are strong (not weak) descriptors of crypto liquidity — correlating 0.82 and 0.80 respectively with price impact at daily frequency — but with a POSITIVE sign, meaning higher trading activity predicts HIGHER execution costs. At the 15-day frequency the volume-based proxies beat all other proxies on three of four benchmarks. Separately, a PCA composite of the low-frequency proxies did not improve on the best individual proxy.

[184|primary] Meta-labeling restricts the ML model to a binary trade/pass (size) decision while an exogenous primary model fixes the side, so the secondary model's label is 'was the primary's call correct', not the direction itself. This is directly transferable: the entry-edge model should snapshot the primary signal's side plus context features, and be trained to predict whether THAT signal was right — not to re-predict direction.

[185|primary] Meta-labeling cannot rescue a weak primary signal — it can only trim downside. The paper concedes its own primaries (SMA crossover, Bollinger bands) are poor signal generators, which bounds the entire result: the demonstrated gains are conditional on a primary that already has genuine in-sample edge.

[186|primary] The out-of-sample precision gain is near-negligible despite dramatic accuracy jumps: mean-reversion precision moved 0.17→0.20 with accuracy 17%→63%, and trend-following 0.48→0.54 with accuracy 48%→55%. The accuracy leap is driven almost entirely by correctly declining trades (true negatives), NOT by better trade selection — precision on taken trades barely moved. In-sample/validation gains (accuracy 20%→77%) collapsed out-of-sample, which is exactly the in-sample-metric-to-real-profit decoupling pattern.

[187|primary] Fixed-threshold directional labels are invalid under heteroskedastic returns and ignore stop-loss/take-profit exits; triple-barrier labeling with volatility-scaled horizontal barriers plus a vertical time barrier labels the realized PATH instead of the next directional move. Barriers are sized as a user-defined multiple of the rolling stdev of log returns — so the label adapts to the volatility regime at entry.

[188|primary] Meta-labeled datasets are severely class-imbalanced toward 'do not trade', and the authors handled it by up-sampling with replacement BEFORE training — a choice that, combined with grid-search CV on non-purged folds, is a known leakage vector (resampled duplicates land in both train and validation folds), plausibly explaining the validation-to-OOS collapse.

[189|primary] Across a curated 45-dataset tabular benchmark with a fair hyperparameter-search budget (~20,000 compute hours per learner), tree-based models (XGBoost, Random Forests) remain state-of-the-art versus deep learning methods on medium-sized tabular data (~10K samples) — i.e. a well-tuned GBM is the correct default baseline for tabular finance features, and deep tabular nets must earn their place empirically.

[190|primary] Neural networks on tabular data are NOT robust to uninformative features, whereas tree-based models are — so a wide, exploratory microstructure feature set (many weak/dead predictors) systematically disadvantages NN architectures relative to GBMs.

[191|primary] NNs are biased toward smooth solutions and struggle to learn irregular/non-smooth target functions, while tree-based models handle them natively — relevant because entry-edge targets over order-book features are typically non-smooth (threshold/regime-like).

[192|primary] Rotation-invariant learners (MLPs) lose performance because tabular features have meaningful individual orientation; preserving per-feature orientation matters, which argues against PCA-style rotation/orthogonalization of engineered microstructure features before modeling.

[193|primary] The paper's conclusions rest on an explicit benchmarking methodology that jointly accounts for model fitting AND hyperparameter search across 45 datasets from varied domains, with all raw search results released — i.e. the tree-vs-DL comparison is not a single-tuning-budget artifact.

[194|primary] The expected maximum Sharpe ratio across N independent trials grows without bound as N increases even when true skill is exactly zero (E[SR]=0), so a high backtest Sharpe carries no evidential weight unless N is disclosed. Falsifiable via Eq. (1)/(6): E[max{SR_n}] = sqrt(V[{SR_n}]) * ((1-gamma)*Z^-1[1-1/N] + gamma*Z^-1[1-1/(N*e)]), gamma = Euler-Mascheroni ~0.5772.

[195|primary] Backtest overfitting in financial series with memory effects produces systematically NEGATIVE out-of-sample performance, not merely zero — i.e. selecting on in-sample backtest results is loss-maximizing, which predicts a sub-50% win rate exactly like the observed 29.2%/n=260 gate failure.

[196|primary] Holdout and k-fold cross-validation do NOT prevent backtest overfitting, because they score a model as if a single trial occurred; applied ~20 times at 95% confidence, false positives become expected rather than unlikely. This falsifies the common assumption that adding a train/test split repairs a Sharpe-based gate.

[197|primary] A valid deflated significance test requires exactly five fields beyond the strategy's own Sharpe, which must be snapshotted at selection/trial time: number of independent trials N, variance of Sharpes across trials V[{SR_n}], sample length T, skewness, and kurtosis. N and V[{SR_n}] cannot be reconstructed post hoc and are the fields pipelines most often fail to record.

[198|primary] Worked example quantifies the deflation: an annualized Sharpe of 2.5 over T=1250 daily observations (5 years) with N=100 trials, skewness -3, kurtosis 10 deflates to DSR ~0.90 (fails a 95% bar); the same 2.5 Sharpe would have passed (DSR=0.9505) had it come from only N=46 trials, and under Normal returns (skew=0, kurt=3) DSR=0.95 held up to N=88 trials.

[199|primary] Gradient-boosted trees matched or exceeded zero-shot tabular foundation models (TabPFN-1.0, TabICL-base) on 3 of 4 binary-classification datasets, with accuracy gaps typically under 1 percentage point and statistically insignificant (p=0.74) — i.e. no measured accuracy edge for TFMs over a well-tuned GBM.

[200|primary] TabPFN inference is >2,000x slower than XGBoost and TabICL ~11,000x slower (960 s vs 0.019 s per test batch on Higgs), while XGBoost runs 5-19 ms per batch — a decisive argument against TFMs in a CPU-only, 500ms-cadence, 200-coin perp pipeline.

[201|primary] TabPFN-1.0 cannot process datasets exceeding ~10,000 rows due to architectural constraints, capping its use as a primary entry-edge model on large perp feature histories.

[202|primary] Tabular foundation models require substantial VRAM (TabPFN 0.8-4.4 GB; TabICL consistently >8 GB, peaking at 9.3 GB on Higgs) whereas tree ensembles require zero VRAM — making GBMs the only viable option on CPU-only hardware.

[203|primary] The authors explicitly recommend zero-shot TFMs only for prototyping/low-stakes small-data work, and state production use needs quantisation/distillation/redesign or hybrid pipelines.

[204|primary] On-chain exchange net-flow predictors yield statistically significant but economically negligible return predictability: adjusted R2 for all intraday return regressions is 0.000-0.003, meaning on-chain flows explain at most ~0.3% of intraday return variance even in-sample. This caps their value as a standalone entry-edge feature.

[205|primary] On-chain net flows predict VOLATILITY far more reliably than direction/returns: BTC net inflows have no return predictive power (t=0.208 at 1h) yet negatively predict BTC volatility at t=-10.950 across all intraday intervals. This implies on-chain flows should be snapshotted as a volatility/risk-sizing input, not a direction signal.

[206|primary] The sign of on-chain net-flow return prediction is asset-specific and does not generalize: ETH net inflows negatively predict ETH returns at all intraday intervals, while USDT net inflows positively predict BTC and ETH returns. A single pooled cross-coin on-chain coefficient would therefore be mis-signed for some assets.

[207|primary] The return-predictive power of USDT net inflows decays to zero beyond 2 hours (1h t=5.903, 2h t=2.595, 3h t=0.444, 4h t=-0.021, 6h t=-0.114), so the usable horizon for on-chain flow signals is 1-2 hours — far longer than a 500ms/5m book-driven entry model and requiring explicit horizon matching.

[208|primary] Evidence scope is limited to BTC, ETH and USDT exchange net flows over Dec 2017-Jan 2023 at 1-6h frequencies, with the authors themselves conceding USDT volatility results are unstable across subsamples and sometimes sign-flipped versus hypothesis — i.e. no evidence supports extending on-chain flows to a 200-coin perp universe at 5m.

[209|primary] The paper's predictor is FX order flow across 11 major currencies ("world order flow"), NOT crypto-exchange limit-order-book or aggTrade microstructure flow — so it does not speak to L2/queue/VPIN-style entry features despite the title.

[210|primary] World (FX) order flow beats economic fundamentals for OUT-OF-SAMPLE prediction of crypto returns, and the advantage is larger for non-linear ML models than linear ones — evidence that non-linearity adds real OOS power on this predictor class, and that the result is not a limits-to-arbitrage artifact.

[211|primary] Order flow's price impact on cryptocurrency returns is permanent rather than transitory — relevant to label/horizon design, since a permanent-impact signal argues for longer holding horizons rather than mean-reversion-style scalp exits.

[212|primary] Order flow carries both explanatory (contemporaneous) and predictive information for cryptocurrency returns; the study is framed cross-sectionally (across coins), not as a single-asset entry-timing problem.

[213|primary] All 15 benchmarked SOTA LOB deep-learning models suffered a large out-of-sample performance collapse when moved from the FI-2010 benchmark to unseen LOBSTER market data (NASDAQ 2021/2022), falling to only 48-61% F1 versus ~82% on FI-2010 — i.e. in-benchmark accuracy did not transfer to new data. The best model, BINCTABL, lost ~19.6% F1 on average across horizons.

[214|primary] Published F1 claims for LOB deep-learning models did not reproduce: measured performance differed considerably from claimed performance and the ranking of systems reordered under independent evaluation. About half of all hyperparameter-search runs diverged to F1 <= 33% (below the 3-class random baseline), showing extreme hyperparameter sensitivity. TRANSLOB and ATNBoF were the worst offenders.

[215|primary] Classification skill did not convert into profit: in the LOB-2021 trading simulation (no fees, no slippage, 1 share/trade), model returns were driven mainly by the underlying stock's daily return, not by model quality — only the two stocks with the highest positive daily returns were profitable, and the two with the most negative daily returns lost money for most models. This is direct evidence that a high-F1/high-backtest-metric gate can have near-zero correlation with realized profit.

[216|primary] Architecture complexity did not win: the top model was BINCTABL (a bilinear/attention layer with Adaptive Bilinear Normalization), which beat the second-best DLA by up to 9.2% F1, while heavier transformer architectures (TRANSLOB, AXIALLOB) ranked among the worst. Ensembles/stacking of the 15 models (including a META-LOB meta-learner) FAILED to beat the single best model, attributed to high agreement among base models. Also, none of the top three models used the conventional h=100 long input window, implying short context suffices.

[217|primary] Label design (horizon k and threshold theta) mechanically controls class balance and therefore apparent accuracy: with the 3-class up/stationary/down labelling on averaged future mid-price, the stationary class falls from 63% at k=1 to 25% at k=10, all models are biased toward predicting the stationary class, and the stock with the best measured performance (CSCO) was simply the most stationary one (18-65-17% train balance) — i.e. reported skill partly reflects label imbalance rather than predictive edge.

