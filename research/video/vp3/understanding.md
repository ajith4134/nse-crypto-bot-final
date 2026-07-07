# vp3 — "Self-learning AI trading agent with Hermes Agent (Nous Research)" (videoplayback (3).mp4, 20:49)

## One-paragraph summary
A third creator (channel "AI Pathways", quant swing trader) shows how to run **Hermes
Agent** — Nous Research's open-source, self-improving agent framework (176k-star GitHub) —
as a **24/7 personal trading analyst on a VPS, driven entirely from Telegram**. Hermes'
three trading-relevant superpowers: (1) **persistent memory** (remembers your portfolio,
trading style, rules like "trade only when VIX<20" across all conversations), (2)
**built-in scheduler** (agent creates its own cron jobs, e.g. a daily 13:00-UTC morning
equity briefing delivered to Telegram), (3) **self-learning loop** (it builds and refines
skill files from what you ask it to do, so it improves with use). He demos morning
briefings gated on market regime, insider-activity research (Form 6-K filings), "scan for
new long opportunities", and pre-trade checks that end in a suggested trade ticket sized
off his $200K portfolio — approving trades from his phone without opening a laptop.

## Every distinct idea (timestamp + frame refs)
1. **Agent-as-employee framing** [00:00–01:19]: a 24/7 AI analyst that monitors markets +
   your portfolio, scans for setups, sends signals/alerts/suggestions to your phone; "the
   more you use it, the better it gets"; approve trades from the phone.
2. **What Hermes Agent is** [01:49–03:24, f_0021/f_0026/f_0119/f_0148]: open-source MIT
   framework by Nous Research; "creates skills from experience and refines them during
   use"; persistent memory; gateway mode connects Telegram/Discord/Slack/WhatsApp/Signal/
   email simultaneously; self-hosting keeps API keys, conversation history, broker
   credentials on your own infra. TUI shows 30 tools (browser_*, clarify, execute_code,
   computer_use, cronjob, delegate_task, discord…) and 85 skills incl. **finance:
   equity-trading-assistant, market-monitoring-alerts**, productivity:
   **daily-equity-factor-refresh**, research: **polymarket**, arxiv, blogwatcher.
3. **Chat-first > IDE-first** [02:35–03:24]: everything lives in your messages; no complex
   prompting or debugging in an IDE; Hermes creates files/skills, searches the web,
   executes for you; memory entries appear in-chat ("memory: +user: Brendan is a swing
   trader…" f_1950).
4. **Morning briefing demo** [03:41–04:43, f_0400–f_0440]: tailored to remembered context
   (VIX-regime preference, current longs & calls: NVDA, MSFT, NOK, NOW, SONY, ORCL…);
   structure: Market regime (VIX 15.32 → "your rule allows normal 1–3% sizing"; SPY/QQQ
   tape vs 50D/200D), per-position review (momentum 1M/3M/12M, IV rank, 90-day insider
   buys/sells with names), positioning takeaway (macro gate, best momentum, cleanest hold,
   most vulnerable long, options risk, insider read), **sizing reference** ($200K, VIX<20:
   1%=$2k/2%=$4k/3%=$6k + per-name share counts), bottom line.
5. **Briefing template co-designed with the agent** [f_2000]: 1 Market regime · 2 Position
   review (trend/S-R/volume, rel strength vs QQQ/SMH, catalysts, thesis quality, risk) ·
   3 Trade setup (entry zone, stop/invalidation, targets, R/R, options structure) ·
   4 Wheel-strategy lens (CSP levels, covered-call zones, assignment risk, IV
   attractiveness, worth-owning-at-strike) · 5 Clear stance (bull/neutral/cautious;
   actionable vs wait).
6. **Cron-job automation by chat** [04:43–05:18, f_0520]: "set up a cron job for this
   specific morning briefing every day" → agent creates job (name, ID, 13:00 UTC daily,
   delivery to the Telegram chat, included skills equity-trading-assistant +
   daily-equity-factor-refresh).
7. **Deep research on demand** [05:18–06:05, f_0550–f_0610]: "how is the insider activity
   in Nokia for the past 5 days" → correctly uses **Form 6-K** (foreign private issuer,
   not Form 4), lists manager acquisitions w/ dates/shares/price/value, aggregates
   (70,000 sh, ~$1.10M, VWAP ~$15.69), gives a constructive-signal read + IV caveat.
8. **Idea generation + pre-trade checks + trade ticket** [06:09–07:45]: "scan for new long
   opportunities based on today's data" → macro gate first, then picks (Palo Alto,
   Datadog, Dell) each w/ insider transactions, momentum, IV rank, bull/bear case,
   catalysts, plus "most attractive" and "avoid chasing" (Dell overextended); then "run
   pre-trade checks and execute if it passes" → checks (price, day move, VIX, momentum,
   insider activity, catalysts) → **suggested trade ticket**: starter size, share count
   off $200K, optional stops and tiered exits.
9. **Data freshness + provenance** [f_0055]: answers carry "Sources checked: Stooq delayed
   EOD quotes dated…; CBOE VIX historical feed timestamp…" lines; standing instruction
   "make sure all market data is always updated when providing outputs".
10. **Permission model** [f_0055]: each tool call shows in-chat and is "Approved
    permanently by Brendan" — explicit user authorization of tool classes.
11. **Setup path** [12:03–18:46, f_1201–f_1720]: Hostinger one-click Hermes template
    (KVM2 ~$8.99/mo), Docker Manager, WebUI basic-auth (user hermes + generated password);
    `hermes setup` quick-setup wizard: AI provider (recommends OpenAI Codex subscription —
    flat monthly, not per-token; or Claude "a tiny bit more powerful", or OpenRouter/any
    API; picks gpt-5.5), terminal backend local (defaults: max iterations 90, compression
    0.50, session reset daily), messaging platform Telegram: create bot via @BotFather,
    paste token, **restrict Allowed user IDs** (@userinfobot), set home channel; then in
    TUI "set up telegram messaging and ensure connection works" → agent self-verifies
    outbound/inbound + suggests `gateway install` for persistence across restarts.
12. **Multi-agent pattern** [11:27–12:00]: run SEVERAL Hermes agents, each with ONE narrow
    job — trader agent, researcher agent, morning-brief agent — "separated chats… they all
    excel at that one very specific task"; KVM2 VPS handles a few agents.
13. **VPS > local** [10:39–11:17]: scheduled pipelines fire every evening, alerts fire
    during market hours, agent always reachable on Telegram — nothing depends on your
    laptop being open; data privacy for keys/broker credentials/portfolio.
14. **Onboarding recipe** [18:50–19:41]: first feed it who you are, how you trade, current
    positions, connect external accounts, ideally past trades — "way better than a blank
    slate" — THEN add cron jobs.
15. His separate **factor dashboard** [00:43, f_0043]: universe 503 across 11 sectors,
    107 long / 96 short candidates by sector quintiles, factor heatmap (Momentum/Value/
    Quality/Growth/Revisions/Short-Interest), MVO (Markowitz, factor-cov, net-of-cost) vs
    conviction sizing toggle, avg est. trade cost 7.8 bps, crowding warnings, tabs
    Portfolio/Research/Risk/Performance/Execution — the kind of research artifact the
    agent maintains/refreshes (daily-equity-factor-refresh skill).
16. **Educational-only disclaimer** [01:41 card + 01:24 narration].

## Open questions
- None blocking.
