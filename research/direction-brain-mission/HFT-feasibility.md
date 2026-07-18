# Can we trade hundreds of times fast, closing in seconds? — a grounded answer
2026-07-18. Owner asked to understand HFT / seconds-scale trading properly.
MEASURED numbers are from this VM today; the rest is established market structure, flagged
as such. Web-search budget was exhausted, so nothing here rests on a fresh citation — treat
the fee-tier specifics as "verify before acting".

## PART 1 — What HFT actually is (it is not "trading fast")
Four families, and only one of them is a volume business:
1. **Market making (~the whole industry).** Post BOTH a bid and an ask, earn the SPREAD, do it
   thousands of times a day. Per-trade edge is a FRACTION of a basis point. You are PAID to
   provide liquidity (maker rebates) instead of paying to take it.
2. **Latency arbitrage.** Same asset, two venues, one is stale for microseconds. Pure speed race.
3. **Statistical arbitrage** at short horizons (pairs, index-vs-constituents, perp-vs-spot basis).
4. **Order anticipation.** Detect a large order working and trade ahead of its impact.

The critical insight: **HFT firms are MAKERS, not takers.** A taker pays the spread + fee on
every trade. Nobody can pay that hundreds of times a day and survive. The entire economic
model is "collect the spread many times", not "predict direction many times".

## PART 2 — What it requires (industry reality)
- **Colocation**: servers physically in the exchange's datacenter. Round trips in
  MICROSECONDS (µs), not milliseconds.
- **Kernel-bypass networking / FPGA** for the fastest strategies. Software-in-Python is not
  in the conversation.
- **Fee tier / market-maker agreement**: at retail tiers you PAY maker fees; real MMs
  negotiate rebates (get paid per fill) in exchange for quoting obligations.
- **Cancel speed is the survival mechanism.** Your resting quote is a free option to
  better-informed traders — "adverse selection". You survive by cancelling before you get
  picked off. If you cannot cancel faster than the informed flow arrives, market making is a
  losing business by construction.
- **Rate limits** (Binance futures, order of magnitude): ~1,200 requests/min, ~300 orders/10s.
  "Hundreds of trades" collides with this quickly.

## PART 3 — OUR MEASURED REALITY (today, this VM)
| what | measured | HFT requirement |
|---|---|---|
| latency VM → Binance API | **162 ms** | microseconds (colocated) — we are ~1,000-100,000x slower |
| latency to our own engine | 9 ms | — |
| order type | **MARKET (taker) on entry AND exit** | maker/limit, or you have no business |
| round-trip cost | **0.10% of notional** (taker) | ~0.04% at retail maker, ~0 or negative for real MMs |
| finest data we hold | **5-minute bars** | tick / full order book, microsecond stamped |

## PART 4 — THE KILLER MATH (measured on our own candles)
For a trade to profit it must move MORE than the round trip. Typical |5-minute move| and the
time a TYPICAL move needs to reach our 0.10% taker cost:

| symbol | median 5m move | % of 5m bars that clear 0.10% | seconds for a typical move to reach 0.10% |
|---|---|---|---|
| BTC | 0.056% | 28.7% | **944 s (~16 min)** |
| SOL | 0.093% | 47.0% | **347 s (~6 min)** |
| ENA (mid-cap) | 0.169% | 68.0% | **106 s (~2 min)** |

**⇒ Trading "in seconds" as a TAKER is arithmetically impossible for us.** On BTC a typical
move needs ~16 minutes just to pay the fees. Even on a volatile mid-cap it needs ~2 minutes.
Add 162 ms of latency on both legs and any genuine seconds-scale signal is gone before we act.
This is not a tuning problem. It is closed.

## PART 5 — WHAT IS ACTUALLY AVAILABLE TO US
**A. Stop paying the taker fee (the real, large, immediate win).**
We are a taker on EVERY leg — measured earlier today, fees are **31% of our losses**
(255 closes in 6h paid 137 in fees). Moving entries to LIMIT (maker) cuts the round trip
0.10% → 0.04%, a **60% cost reduction**. Honest caveats: maker orders may not fill, and the
ones that DO fill are disproportionately the ones you wish had not (adverse selection). This
must be A/B'd, not assumed — but it is the single biggest cost lever we have.

**B. Fewer, better trades (already the direction of travel).**
The dip lane (X24) needs a ~3% move, not a 0.1% one, so fees are ~3% of the expected move
instead of ~100% of it. That ratio — edge-to-cost — is the only thing that matters, and it is
improved by making the EDGE bigger, not the trades faster.

**C. What would be needed to genuinely attempt market making** (a different project, honestly):
colocated/proximity hosting near the matching engine, a websocket order-book feed with
microsecond stamps, limit-order quoting with inventory skew, cancel-on-adverse-flow logic, and
a fee tier where maker is free or rebated. None of these exist here today. Our finest data is
5-minute bars — we cannot even MEASURE the phenomena market making exploits.

## PART 6 — THE HONEST BOTTOM LINE
Trading hundreds of times per day in seconds is not a strategy we can adopt; it is a different
business with different physics (µs latency, maker rebates, colocation, FPGA). Our 162 ms and
0.10% taker cost put a hard floor under our holding period of MINUTES, not seconds.
The productive reading of the owner's instinct — "many fast trades" — is: **high trade count
only works when each trade is nearly free.** Since we cannot make trades free, we must make
them RARER and BIGGER. That is exactly what today's measurements already forced:
momentum-chasing at ~40 trades/hour = −0.229%/trade, versus a rare 3% dip setup = +0.438%/trade.
