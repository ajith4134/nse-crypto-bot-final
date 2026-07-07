# vp1 — "My AI trading bot went $50→$500→$0; Autoresearch fixed my process" (videoplayback (1).mp4, 18:55)

## One-paragraph summary
Same creator as vp0. He ran an "LLM battle royale" (7 AI models, $50 each, same prompt,
trading against each other on Hyperliquid for 4 rounds; Claude Opus won +114.4% with 31
trades, Kimi-K2 second at $56.63, all others lost). He left the winner running unattended:
$50→$107→$300→$500 (10x), then stopped checking, and it bled to **zero** — 814 trades,
−$193.66 closed PnL + −$115.20 fees (banner rounds −$9,366/−$1,620 figures appear for
cumulative across bots): death by a thousand cuts when market conditions reversed, not one
catastrophic trade. Manual parameter tweaking made it WORSE (win rate 19%→12%), so he
killed the bot. Then Karpathy released **autoresearch**, and he adapted it into a
**Trading Auto-Researcher**: an infinite loop where an LLM generates a brand-new strategy
each cycle, backtests it on held-out data, rejects look-ahead cheaters, and keeps a new
strategy only if it beats the current champion — 133 generations in the first day, best at
gen 61 (+89.6% on 2025 hold-out from $1,000, 46.8% win rate, −13.71% max DD).

## Every distinct idea (timestamp + frame refs)
1. **The blow-up story** [00:00–04:26, f_0300 (Telegram w/ agent "Max"), f_0330/f_0340
   (814 trades, PnL −$9,366, fees −$1,620, final $0)]: a live bot with a static strategy
   slowly drained by small losses + fees after conditions reversed — "a boat with a small
   leak"; the balance stopped changing 24h before he noticed. Lessons embedded: monitor
   continuously, watch fee bleed, a strategy validated on 4 rounds does not scale to 400.
2. **Battle-royale benchmarking of LLMs** [00:25–01:13, f_0048]: give N models the same
   capital/prompt/market/rules, let them trade in elimination rounds ("2/7 alive"),
   leaderboard: Claude Opus #1 $87.36→$107 (+114.4%, 31 trades), Kimi K2 #2 $58.15/$56.63,
   Llama-3.3 / GPT-4o / DeepSeek / Grok negative and eliminated.
3. **Manual tweaking is the anti-pattern** [04:50–05:31]: hand-adjusting RSI/sizing/TP
   dropped win rate 19%→12%. "I'm not losing more money on this thing."
4. **Karpathy autoresearch concept** [05:39–06:34, f_0546/f_0549, f_1210–f_1510]:
   AI proposes small changes → tests → keeps winners → repeat forever; Karpathy points it
   at LLM training (~630-line single-GPU trainer; human iterates on the prompt .md, agent
   iterates on the training code .py; fixed 5-minute GPU time budget per experiment;
   val_bpb metric; progress chart "83 experiments, 11 kept improvements"; repo
   github.com/karpathy/autoresearch, 27.4k stars). He "wakes up to a log of 100
   experiments that ran overnight".
5. **Repo anatomy** [12:09–12:56, f_1310]: three files — `prepare.py` (fixed constants +
   one-time data prep), `train.py` (THE single file the agent edits/iterates), `program.md`
   (baseline instructions/goal rules for the agent). Small, deliberately constrained.
6. **His trading adaptation** [06:42–10:55, f_0640/f_0745]: data = 2 years of minute-bar
   BTC/ETH/SOL; 2024 = strategy-generation data, 2025 = hold-out backtest the AI never
   sees during generation. Each cycle: LLM (GPT-4o-mini via OpenRouter, one strategy every
   couple of minutes) generates a COMPLETELY NEW strategy (e.g. "Donchian channel breakout
   using 20-period high") → backtest on full 2025 (every candle) → Sharpe-like score →
   **automatic look-ahead-bias check**: if results look too perfect (e.g. 11,000% PnL) the
   strategy is REJECTED as having peeked at hold-out data → compare vs current best; accept
   only if better; champion locked in (gen 6 → … → gen 61 best: $1,000→$1,896.44, +89.64%,
   46.8% win rate, −13.71% max DD, 47 trades). 133 generations while filming. Dashboard
   "Trading Researcher" tab in Max HQ shows score progression + strategies table w/ notes.
7. **Setup recipe** [11:02–15:22, f_1340–f_1510]: run Claude Code (he shows Opus 4.6 "high
   effort"), paste the autoresearch repo URL + "hey I want to run this for a trading agent
   experiment, run me through the setup, let's set it up together, **use askuserquestion
   until you reach clarity**" — the agent then asks Hardware (GPU/Mac/RTX/cloud), Use-case
   (modify the loop for a trading strategy vs train a trading LLM vs learn the framework),
   Location (where to clone), then Submit. ~30 min setup.
8. **Generalization** [15:22–15:43]: anything that previously took hundreds of hours of
   manual iteration can be plugged into the auto-researcher loop.
9. **Honesty about expectations** [16:25–17:43]: current best is only 46% win rate; may
   never reach profitability live; the value = a thousand small experiments run for you +
   YOU learn what works so when conditions change you know how to think about fixing it
   rather than panic-tweaking.
10. **Follow-up promised** [18:36]: he'll report real numbers in a few weeks.

## Open questions
- None blocking. (Note: on-screen banner says PnL −$9,366 / fees −$1,620 while narration
  says −$193.66 / −$115.20 — likely account-level vs bot-level figures; both convey the
  same slow-bleed lesson.)
