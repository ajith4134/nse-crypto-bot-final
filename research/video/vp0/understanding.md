# vp0 — "Polymarket Copy-Trading Research Bot" (videoplayback.mp4, 23:13)

## One-paragraph summary
A builder who has "built hundreds of Polymarket trading bots" teaches how to build not a
prediction bot but a **self-improving copy-trading RESEARCH system** ("Hermes"-agent
powered, dashboard in his "Hermy HQ" mission control): it scans the Polymarket
leaderboard's top-500 wallets, profiles each wallet for ROI / consistency / copyability
(per category), watches new trades from the best wallets, scores every trade into
**copy / watchlist / skip**, paper-trades $5–20 tiered positions, journals every decision
with reasons, reviews outcomes at 1h/6h/24h/resolution, and **auto-updates its own scoring
rules with version history** — earning real-money autonomy only after ≥30 profitable paper
days, ≥100 paper trades, a clear win over blind leaderboard copying, no data failures, and
a sane drawdown profile.

## Every distinct idea (timestamp + frame refs)
1. **Blind whale-following breaks** [00:10–00:40]: profit may be a few lucky trades; wallet
   may be good in only one category; markets may be too illiquid; by the time you see the
   trade the price has moved.
2. **Find wallets worth copying first** [02:14–04:58, f_0316]: leaderboard scanner pulls
   top 500 wallets, studies last 30 days; asks "who is copyable", not "who made money".
3. **Three wallet scores** [03:29–03:58]: ROI (made money), consistency (repeatable vs a
   few lucky hits), copyability (can we realistically follow: late entries, spreads,
   category mismatch).
4. **Per-category wallet ranking** [04:02–04:35]: politics/crypto/sports/macro — a wallet
   is not universally smart because it was right in one lane.
5. **Wallet profiles include a blind-copy baseline** [04:35–04:50]: "would blind copying
   this wallet have worked over the last 30 days" — always keep a comparison baseline.
6. **Copy trading is filtering, not copying** [05:01–07:15, f_0500]: every new trade is
   scored BEFORE anything happens: who made it, category fit, their entry price vs our
   available price, how far the market moved, time to resolution, is the wallet usually
   early enough. Labels: **copy / watchlist / skip**. "A good skip is as important as a
   good entry" — the bot is useful because it refuses most bad copies.
7. **Paper trade before real money** [07:19–09:36, f_0718]: first version places NO real
   trades. Tiered sizing: $5 decent signal, $10 strong, $20 highest confidence (risk
   mitigation). Simulate reality: if live wallet will have $100 total, simulate $100
   TOTAL, not per trade [14:03–14:25]. Hourly paper-PnL updates.
8. **Judge the filter, not just PnL** [08:38–08:58]: "did our filtering improve the
   strategy?" — if blind copying beats the bot, the bot adds no value; dashboard chart
   PAPER PNL VS BLIND COPY (f_0011, f_1900: +$194.35 filtered vs −$41.80 blind over 30d).
9. **Track missed winners and avoided losers** [08:58–09:25]: skip that later lost = good
   skip; skip that kept running = maybe the late-entry rule is too strict. Both are lessons.
10. **Decision journal = "the soul of the system"** [09:41–11:24, f_0010]: every signal
    gets an entry: decision (paper_copy/watchlist/skip), score breakdown, reasons, risks,
    rule version; later the bot reviews whether each decision was good or bad and what it
    learned. Example entry [09:52]: "Wallet A bought YES on a crypto market at 42¢;
    current 45¢; spread 3¢; strong crypto track record; resolves in 2h; liquidity
    acceptable → COPY."
11. **Self-improvement = a decision loop that tracks its own reasoning** [10:47–11:24]:
    e.g. learn "don't copy if price moved >12¢", "this wallet is only copyable for
    crypto", "raise the liquidity threshold". "Not the agent magically becomes a genius
    overnight — it gets less stupid over time."
12. **Automatic rule updates in paper mode** [11:24–12:01]: don't ask permission to change
    a paper threshold; just log old rule → new rule + evidence + reason; rule v1 → v2 →
    … (demo reached v5). "A notification bot tells you what happened. An AGENT changes
    how it decides based on what happened."
13. **Nine build parts, verified chronologically** [12:08–15:04] (don't fix step 5 before
    step 1 works): 1 leaderboard scanner (wallet universe) · 2 wallet profiler
    (ROI/consistency/copyability scores) · 3 trade monitor (detect new trades) ·
    4 trade scorer (copy/watch/skip) · 5 decision journal · 6 paper-trading engine ·
    7 hourly PnL updater · 8 outcome reviewer (1h/6h/24h/final) · 9 rule updater
    (auto-updates scoring rules with version history).
14. **Dashboard = mission control** [15:16–16:43, f_1804, f_1830]: chat/Telegram is not
    enough to supervise an agent loop; the dashboard must answer 3 questions immediately:
    Are we profitable on paper? Which wallets are worth copying? What did the bot learn
    today? No analysis-paralysis walls of charts. Overview shows: paper PnL, win rate,
    open paper positions, tracked wallets, copy candidates today, latest rule changes,
    end-of-day report status. Safety banner: "Paper trading only. No private keys. No
    signing. No real orders. Demo rows labeled."
15. **Build path** [16:49–18:20, f_0002]: one very long build prompt + ~1 hour of
    AskUserQuestion back-and-forth clarification until clarity, then the agent builds it.
16. **Live result** [19:29–20:44, f_1940–f_2020]: after 24h: +$27.91, 57.1% win rate,
    7 open positions, rules self-updated to v3; "what was driving that?" → main-drivers
    table (e.g. USA vs AUS total 2.5 Under: entry 0.495 → 0.915, won $15).
17. **Autonomy has to be earned** [20:48–21:53, f_2046]: gates for real money = ≥30 days
    positive paper trading + ≥100 paper trades + clear win over blind copying + no major
    data failures + sane drawdown profile. Until then it is a research agent — "the goal
    is to build an evidence layer before money is involved". If paper fails, the bot
    saved you from automating a losing strategy — also a win.
18. **End-of-day report** [01:19–01:24]: the agent sends an end-of-day summary report.

## Open questions
- None material; the video is self-contained. (The "full build prompt" he gives is in his
  video description, not in the video itself — we only see fragments on screen.)
