# Agent agent-a3ee7e61d5bae2c24 — wf_57b21e69-3a8

Verification complete. The source is real and the quote is verbatim — but the claim's second sentence does not follow from it.

**What checks out:** arXiv 2607.09230 (Jeon, Korea University, submitted 2026-07-10) exists, and the supporting quote is accurate. The paper does find pre-event L2 state (spread/depth-20/imbalance-20 terciles) dominates, with order flow as an overlay.

**What breaks:** The claim silently swaps the target. The paper's dependent variable is discrete **liquidity regime** (calm/mixed/stressed), and it explicitly disclaims the entry-edge target the research question is about — the task is "distinct from latent-regime detection and price-direction prediction," and "Our dependent variable is not price but the post-event liquidity state." The clause "This implies an entry snapshot must capture the L2 state variables first" is the reviewer's inference, not the paper's, and it crosses from a liquidity target to a profitability target with no bridging evidence.

Three further defects:
1. **Scope**: findings hold only inside scheduled macro-announcement windows ("The macro-event calendar enters only by locating the windows"), not the general trading conditions an entry model faces.
2. **Self-refuting on the overlay half**: the paper warns the order-flow increment "is not robustly cross-symbol: for ETH it is present... whereas BTC shows only isolated five-minute passes." With n=2 symbols, this cannot support "never as a replacement" as a general law — and effect size over marginal is a modest 0.034–0.045.
3. **Contradicted for the target that matters**: Cont, Kukanov & Stoikov ([arXiv:1011.6402](https://arxiv.org/abs/1011.6402)) find that for *price* changes, order flow imbalance is the dominant driver, with market depth entering as an inverse scaling denominator — the exact inverse of the claimed "L2 state first, order flow as overlay" hierarchy. The claim's hierarchy is target-specific and inverts when the target becomes direction.

Worth flagging for your project context: liquidity regime is strongly autocorrelated, so "pre-event state dominates" is close to a persistence baseline — and your own measurement work already found persistence correlation of −0.214 on the direction target, which is precisely why this transfer fails.
