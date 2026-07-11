# champions-chart-strategy — reconstruction (video-understand, 2026-07-11)

**Source:** owner upload (@chartfanatics, 60s reel). **What it is:** a Volume-Profile /
Value-Area **failed-auction** long strategy — "how world-champion traders actually trade."
Owner's intent: use it to read the Binance-web candle chart to predict direction AND manage
the trade *after the brain opens it*, and mine it for ideas to add to our chart-vision pipeline.

## The strategy, literally (transcript + frames)
**Step 1 — Volume Profile + Value Area [00:09, f_0010/0020].** Draw the session's **volume
profile** (horizontal volume-at-price histogram, shown on the left of the chart). Find the
**Value Area** (the high-volume region — the two horizontal lines = VA High / VA Low). If the
value area is **building higher session after session → buyers in control → trend bullish**.

**Step 2 — dip below VA + absorption [00:20, f_0030].** Wait for price to **dip below the
value area**. Watch the **volume bars**: if volume is **declining on the move down** (red
arrow on the volume panel) **and you see absorption** — buyers stepping in, forming a **wall**
sellers cannot push through (red circle on the absorption candle) — then **the money is not
following price lower** (sellers lack conviction).

**Step 3 — failed auction = long [00:37, f_0040/0050/0100].** As soon as price **closes back
inside the value area and volume picks up**, the **downside auction failed** ("the party is
still in the range"). **That is the long.** **Stop** below the swing low (red box); **target**
the **value area high and potentially beyond** (green box).

(Symmetric for shorts: a failed *upside* auction above VA → short.)

## Binance indicator set to READ/RENDER (from the owner's IMG_8949 screenshot)
The owner's real Binance app chart (BTC/USDT, 15m) has these built-ins ON, with numeric values
overlaid as text (a VLM can read them directly):
- **MA(7,25,99)**, **EMA(7,25,99)**, **BOLL(20,2)** (UP/MB/DN), **SAR(0.02,0.2)**,
  **SUPERTREND(10,3)**, **AVL**, **VOL + MA(5,10)**, **MACD** (DIF/DEA/hist).
- Timeframe tabs 15m/1h/4h/1d; AI button, ⭐favorite, Buy/Sell, Margin, Hub.

## Concrete ideas to ADD to our pipeline (the owner's ask: "even more ideas to include")
1. **Volume Profile / Value Area engine** (NEW) — compute volume-at-price histogram, **POC**,
   **VAH/VAL** (70% value area) from candles per session/lookback. We have order-book OBI/OFI/
   walls (psychology.py) but NOT a session volume profile. → new features for the P1 bus.
2. **Value-area migration feature** — track POC/VAH/VAL shift session-over-session; "building
   higher/lower" = directional-bias feature (horizon-tagged).
3. **Failed-auction detector** — price exits VA then closes back inside + volume expansion →
   mean-reversion/continuation signal (a rule AND a feature; symmetric long/short).
4. **Absorption feature** — declining volume on a directional move + a resting wall = absorption;
   fuse with our existing OBI/wall detection (psychology.py) — we already detect walls.
5. **VLM prompt upgrade (chart_vlm.py)** — teach the reader to look for: VP value area, price vs
   VAH/VAL, absorption/failed-auction, volume expansion; AND to read the Binance overlay values
   (BOLL/EMA/MA/SAR/SUPERTREND/MACD). Output stays the structured direction score.
6. **Render VP on the annotated chart (chart_render.py)** — add the volume-profile histogram +
   VAH/VAL/POC lines + the Binance indicator set (EMA/SAR/SUPERTREND/AVL) so CNN-successor + VLM
   see what the owner sees. Matches the video's exact visual.
7. **After-entry trade management** — VAH as take-profit target, swing-low as stop; feed our
   profit-tailgate/exit policy (the "after the brain opens the trade" part of the owner's ask).
8. **Strategy-library entry** — add "VP failed-auction reversion" as a named strategy/skill so
   the generator/evolver can weight it per coin.

## Open questions
- **Session definition** for the value area — rolling N-bar window, UTC day, or per-TF? (BTC is
  24/7; equities have a natural session.) Affects VA migration.
- Build the **Volume Profile engine now** (idea 1-4, the video's core), or first do the lighter
  wins (ideas 5-6: VLM prompt + render upgrade) and add VP next?
- Does this **replace** or **complement** the current direction sources? (Recommend: complement —
  it becomes candidate features/rules the equation + Truth Ledger weigh, per the quest plan.)
