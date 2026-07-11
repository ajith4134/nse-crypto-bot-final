# vidup2 — "Chinese student turned <$1 into $400k via Solana DEX arbitrage bot" (13s)

## What it is
A 13-second text-over-video clip. First frame black; second frame shows a dark trading UI
("Gravia_001", $16,872, 203 trades, 100.0% win, live-stream leaderboard pane) above three
text paragraphs. No speech (0 transcript segments).

## Literal text content
- "A Chinese student reportedly created a crypto trading bot that turned less than $1 into
  over $400,000 through automated arbitrage trading on the Solana blockchain."
- "The bot scanned decentralized exchanges for small price gaps, instantly buying and
  selling assets faster than any human trader could react manually."
- "The story sparked major discussions online about how AI automation, algorithmic trading,
  and blockchain technology are reshaping financial markets through speed and software
  driven execution."

## Transferable ideas for OUR brain
1. **Cross-venue price gaps carry directional information.** We already round-robin
   binance/bybit/okx/kucoin (multi-venue data pool). When venue A prints a move venue B
   hasn't matched yet, the gap predicts B's next move (lead-lag). Even without executing
   arbitrage, the GAP ITSELF is a short-horizon direction feature — free, from data we
   already fetch.
2. **Speed edge = react to information others haven't priced yet**, not forecasting from
   stale candles. Our funnel's freshest signals (order-book imbalance, venue gaps, funding
   snaps) should outrank slow indicators at short horizons.

## Honesty note
The $1→$400k claim is unverifiable clickbait; only the mechanism (DEX/CEX price-gap
scanning) is real and well-documented.
