# vp0 (videoplayback.mp4, 23:13) — frame observations (pre-transcript)

Creator: tech YouTuber (glasses, guitars in background). Video = building "Hermes HQ —
Polymarket Copy Research", a paper-trading copy-research bot for Polymarket prediction
markets, built with Claude Code (an AskUserQuestion clarify screen appears at [00:02]).

## Chapter cards (on-screen step titles)
- [02:13] STEP #1 — FIND COPIABLE WALLETS
- [05:00] STEP #2 — COPY TRADING IS FILTERING, NOT COPYING
- [07:18] STEP #3 — PAPER TRADE BEFORE RISKING REAL MONEY
- [09:40] STEP #4 — JOURNAL EVERY DECISION
- [12:07] STEP #5 — BOT ARCHITECTURE
- [15:15] STEP #6 — DASHBOARD
- [16:48] STEP #7 — THE BUILD PATH
- [20:46] STEP #8 — AUTONOMY HAS TO BE EARNED

## Key informative frames
- [00:00] f_0000: dark dashboard w/ green total-PnL KPI, trade table (demo of final result).
- [00:02] f_0002: red banner "100s OF POLYMARKET TRADING BOTS"; Claude Code
  AskUserQuestion flow "askuserquestion until you reach clarity" with tabs
  Architecture / Scope / Bot control / Submit; questions visible:
  - "How should the dashboard get live data — read bot's trades.json directly, or add a
    small local server to the bot that serves the data?" → Separate app
  - "Do you want the dashboard to also show your current open positions from
    Polymarket?" → Just copybot stats
  - "How should the bot on/off toggle work?" → Start/stop the process
- [00:10] f_0010: requirements/spec text file (sections visible):
  5. Paper Trades — show: simulated trades; simulated position size between $5 and $20;
     entry price; current price; hourly PnL; final PnL, if resolved; current status;
     reason for entering; linked wallet and market.
  6. Decision Journal — show: every decision; copy, watchlist, or skip; score breakdown;
     reasons; rules; whether the decision was later judged good or bad; what the bot learned.
  7. Performance — show: PnL chart ...
  (top of file: decision: paper_copy, watchlist, skip / score / reason / risk)
- [00:11] f_0011: "Polymarket Copy Research, 30-Day Demo" — "+$194.35" 30-day paper PnL;
  chart "PAPER PNL VS BLIND COPY" (tooltip: Blind leaderboard 4.6 / Bot filtered 71.5) —
  the bot monitored wallets, copied only high-confidence paper setups, learned from
  skipped/watchlisted trades, revised its rules over 30 days.
- [03:16] f_0316: dashboard "Wallet Rankings" tab — TOP-N WALLET RANKINGS table:
  rank, wallet (0x…), PnL-ish cols, action "add to paper tracking" per row.
- [18:04] f_1804: dashboard header "HERMES PAPER OPERATOR — Polymarket Copy Research";
  subtitle "Paper trading only. No private keys. No signing. No real orders. Demo rows
  are labeled as demo if seeded." Tabs: Overview | Wallet Rankings | Wallet Profile |
  Copy Signals | Copied Trades | Copy Journal | Performance | Rules | Reports.
  KPIs: Total paper PnL / Win rate / Open copied positions (3) / Tracked wallets (39) /
  Copied today (2). Panel "WHAT THE BOT LEARNED TODAY": "Live paper PnL is $-5.25 across
  3 open paper positions. Win rate is 0.0%. The bot is currently learning that the recent
  copy set is underperforming after live repricing, so rule review should tighten entries
  around liquidity, spreads, and duplicate exposure."
- [18:30–18:48] full dashboard views: left sidebar "Hermy HQ" app (Dashboard, X,
  Articles, YouTube, Overview, Client Pulse, Trading, Polymarket Copy, Copy Demo,
  Researcher, War Room, Agents, Memory Wiki, Ideas, Garden) — the copy bot lives inside a
  bigger personal AI HQ. Status chip "ready"; "PAPER ONLY" badge; rule version "v5".
- [19:00–19:20] 30-Day Demo page: +$194.35, 61.8% win rate, 34 copied trades, 6 open
  positions, 42 tracked wallets, rules v5; chart paper PnL (blue, rising) vs blind copy
  (orange, flat/declining); bottom KPIs: -$41.80 blind-copy PnL, 19 (skipped?), 117
  (decisions?); tables "WALLETS WORTH COPYING" (rank/wallet/…/copies/PnL/hold/reason) and
  "CATEGORY PERFORMANCE". Panel "WHAT HERMES LEARNED": 1. Leaderboard ROI alone was
  misleading — top raw-ROI wallet ranked 4th after concentration and liquidity penalties.
  2. The bot made most of its paper PnL by copying stream, liquid macro and politics
  trades, not chasing fast sports moves. 3. Reducing max spread from 4.0% to 2.5% cut bad
  fills... 4. (partially visible) ... 5. ...
- [19:40–20:00] phone-camera shots of live dashboard: Total paper PnL $27.91, win rate
  57.1%, 7 open copied positions, 39 tracked wallets, 6 copied today; "Automatic
  paper-trading rule update based on copied, skipped and watchlist cohort performance"
  entries (the bot auto-revises rules); PnL-over-time chart w/ tooltip pnl −5.25 @11:00AM
  rising to +27.91.
- [20:20] "Main drivers" table: markets like "USA vs AUS total 2.5, Under" entry 0.495 →
  current 0.915; "Pliskova vs Gibson, Pliskova" 0.595→0.999; "TS7 vs G2, Spirit"
  0.745→0.999; "NLD vs SWE total 2.5, Over" 0.555→0.565 (sports/esports prediction markets).

## Concepts to carry into the plan
1. Copy-research loop: rank wallets → filter (copy/watchlist/skip decisions w/ score
   breakdown) → paper-copy sized $5–20 → journal every decision → judge decisions later
   good/bad → auto-revise rules (versioned v1..v5) → "what the bot learned today".
2. "Copy trading is filtering, not copying" — value = the decision filter, not the copy.
3. Benchmark against the naive baseline (paper PnL vs BLIND copy) to prove the filter adds alpha.
4. Autonomy ladder: paper-only → earn autonomy with evidence (Step 8).
5. Safety framing: "No private keys. No signing. No real orders."
