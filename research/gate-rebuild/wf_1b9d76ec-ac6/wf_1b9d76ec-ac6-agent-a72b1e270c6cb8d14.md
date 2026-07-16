# Agent agent-a72b1e270c6cb8d14 — wf_1b9d76ec-ac6

I have enough to render a verdict. Let me lay out what I found before the structured call.

The paper is real and peer-reviewed, but the claim materially overreaches it on four independent axes:

**1. The load-bearing final clause is not in the source.** The quote compares *labeling and sampling schemes* for ML prediction. It says nothing about replacing a *strategy-selection gate*. The inference "supporting replacement of a fixed-horizon/backtest-Sharpe gate" is the reviewer's addition. Worse, it's self-undermining: the paper's own evidence *is* a backtest, validated with walk-forward only — no PBO, no deflated Sharpe. It carries the same defect as the gate it's cited to replace.

**2. Scope transfer fails.** BTC + ETH **spot** on Binance, tick data. Two assets. The target application is 200 coins of **perpetual futures** with L2 book, funding, OI, liquidations. Perps have funding carry and liquidation cascades that spot BTC/ETH 2018–2023 does not contain. Nothing in the paper speaks to 200-coin cross-sectional breadth.

**3. "Consistently positive" rests on five quarters in one regime.** OOS is Q2 2022 – Q2 2023 only. The authors concede "our test period does not include the peak of the 2021 bull market." Five quarters × 2 assets, single regime, is not "consistent" in any sense that survives the user's -0.031 problem. They also acknowledge survivorship and Binance sample bias.

**4. Validation does not meet the bar the research question demands.** Walk-forward expanding window, no purged/embargoed K-fold, no CPCV, no PBO, no DSR. Hyperparameter optimization was run with no disclosure of total configurations tried and no multiple-testing correction. Transaction costs are asserted as "accounted for" with no bps figure in the text, and no numerical Sharpe/return is reported — the headline is qualitative.

**5. A known mechanism cuts against the claim.** Triple-barrier induces *label concurrency* — overlapping labels violate IID, inflating in-sample performance while OOS decays. This is precisely the failure mode already destroying the current gate (highest-score quartile is the worst). Adopting triple-barrier without sample-uniqueness weighting and purging would import the disease, not cure it. The paper does not report uniqueness weights.

The method is likely still worth adopting — but on the strength of the broader AFML literature plus purged CPCV/DSR validation, not on this citation, which cannot bear that weight.
