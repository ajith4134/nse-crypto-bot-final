# Agent agent-ad66ac6b22a0cd099 — wf_57b21e69-3a8

I have enough to rule. The citation is real and the numbers are verbatim — but the claim rests on a target substitution the source explicitly disclaims.

**Verified as accurate:**
- arXiv:2607.09230v1 exists — "When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in Crypto Futures," Joohyoung Jeon (Korea University), July 10, 2026.
- The quote is verbatim from §5.3: "The increment rises monotonically from calm to mixed to stressed, reaching 0.004, 0.020, and 0.038 at the one-minute horizon."
- All six ETH regime cells clear a flow-shuffle null with 90% event-cluster intervals above zero.

**Why it still fails:**

1. **Target substitution (fatal).** The paper's dependent variable is *not price*: "Our dependent variable is not price but the post-event *liquidity state* of the book, a discrete calm, mixed, or stressed regime" (Y = S^post ∈ {calm, mixed, stressed}, from relative spread / top-20 depth / top-20 imbalance terciles). The claim recasts this as order flow's "incremental predictive value" for a **trade-entry edge** model. Order flow predicting *whether the book will be stressed in 60s* is a different object from order flow predicting *direction*. The 0.004/0.020/0.038 numbers say nothing about "when order-flow features are trustworthy" for entry.

2. **The actionable conclusion is disclaimed by the source itself.** "This is a prediction study of liquidity-state transitions at a one-minute cadence, **not a trading or execution study, and reports no policy, profit, or simulator result.**" The "must be snapshotted at entry" is the claim's own inference, not the paper's.

3. **Generalization overreach on n=2.** The headline is stated as a general law about order flow, but BTC — the only other asset — shows no establishable contribution (+0.001/+0.003, not separated from null; only 1 of 6 regime cells clears, and *not* the stressed one). Authors: "the ETH-versus-BTC asymmetry is a two-point observation rather than a population statement." For a 200-coin perp universe, ETH-only cannot support "must."

4. **Units oversold.** Increments are NLL/Brier gains vs. a shuffle null, not accuracy, edge, or Sharpe. Presenting +0.004 as a calm-regime "order-flow gain" implies a decision-relevant magnitude the metric does not carry.

5. **Provenance thin for a "must."** Single-author, v1, non-peer-reviewed, six days old, no replication.

The narrow literal statement survives; the claim built on top of it does not.
