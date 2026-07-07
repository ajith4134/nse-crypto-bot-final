# vp3 (videoplayback (3).mp4, 20:49) — frame observations (pre-transcript)

Third creator ("Brendan", quant swing trader, Art-of-War bookshelf). Video = set up
**Hermes Agent (Nous Research)** as a personal TRADING ASSISTANT on a VPS + Telegram.
NO-FINANCIAL-ADVICE disclaimer card at [01:41].

## What Hermes Agent is (site + repo frames)
- [00:21] hermes-agent.nousresearch.com: "THE AGENT THAT GROWS WITH YOU — not a coding
  copilot tethered to an IDE or a chatbot wrapper around a single API. An autonomous agent
  that lives on your server, remembers what it learns, and gets more capable the longer it
  runs." Install: curl install.sh | bash; `hermes setup`. Open source, MIT.
- [00:32] "self-improving AI agent built by Nous Research that creates skills from
  experience and refines them during use… builds a persistent memory that grows more
  valuable over time. Connects simultaneously to Telegram, Discord, Slack, WhatsApp,
  Signal, and email in gateway mode, with support for OpenRouter, OpenAI, Anthropic, and
  custom LLM endpoints. Self-hosting on your VPS keeps all API keys, conversation
  history, and business context on your own infrastructure, with dedicated resources for
  web browsing, code execution, and multi-agent workflows without external throttling."
- [01:19] github.com/NousResearch/hermes-agent — 176k stars, 29.7k forks, 1065 branches,
  10,142 commits; dirs: .github, _plans, acp_adapter, acp_registry, agent, apps, assets,
  cron, datagen-config-examples, docker, docs, gateway, hermes_cli, infographic….
- TUI (v0.15.1, model gpt-5.5, Nous Research): Available Tools — browser_back/
  browser_click/browser_cdp/browser_dialog, clarify, execute_code, computer_use, cronjob,
  delegate_task, discord (+21 more toolsets). Available Skills by category:
  autonomous-ai-agents (claude-code, codex, hermes-agent, kanban-codex…), creative,
  data-science (jupyter-live-kernel), devops, email (himalaya), **finance:
  equity-trading-assistant, market-monitoring-alerts**, gaming, github, mcp (native-mcp),
  media, mlops (dspy, evaluating-l…), note-taking (obsidian), productivity (airtable,
  google-workspace, linear, maps, **daily-equity-factor-refresh**…), red-teaming
  (godmode), research (arxiv, blogwatcher, llm-wiki, **polymarket**, resea…), smart-home,
  social-media (xurl), software-development. "30 tools · 85 skills".
- [08:53] Architecture sketch: Features (persistent memory, built-in scheduler,
  self-learning loop) → AI Connection (ChatGPT codex subscription, Claude, any other LLM)
  → Messaging Platform (Telegram, Discord, Slack) → How to Run (local computer, VPS) →
  Data P… (all your keys, broker credentials?, portfolio…, conversation history…).

## Deployment walkthrough
- [12:01–15:12] Hostinger VPS "Deploy Hermes Agent in one click" ($6.49/mo KVM2,
  ~$215/24mo), Docker Manager → Catalog has Hermes Agent / Hermes WebUI / Hermes
  Workspace templates; deploys container; WebUI at <host>.hstgr.cloud with basic-auth.
- [16:10–17:20] `hermes setup` wizard: Inference Provider (login via OpenAI Codex device
  code; default model gpt-5.5; options gpt-5.4, gpt-5.4-mini, gpt-5.3-codex, custom…),
  Terminal Backend local w/ recommended defaults (max iterations 90, tool progress all,
  compression threshold 0.50, session reset inactivity 1440min + daily 4:00), Messaging
  Platforms multi-select (Telegram, Slack, Matrix, Mattermost, WhatsApp, Signal, Email,
  SMS Twilio, DingTalk, Feishu/Lark, WeCom, WeChat, BlueBubbles iMessage, QQ, Yuanbao,
  Discord, Google Chat, IRC, LINE, ntfy, SimpleX, MS Teams), Telegram bot token via
  @BotFather + **Allowed user IDs** (restrict who can use the bot).
- [18:10–18:30] In TUI: "set up telegram messaging and ensure connection works" → agent
  verifies outbound CLI send, tool send, home-chat delivery, gateway polling, logs paths
  (/opt/data/config.yaml, /opt/data/.env, gateway.log), suggests `gateway install` for
  persistence.

## Trading-assistant usage (Telegram "hermes-trader" bot)
- [19:20–19:50] Onboarding prompt: "I'm a swing trader that also likes to use the wheel
  strategy for positions. I typically like to trade when VIX is below 20 and my current
  positions are ORCL NVIDIA SNOW LCRX DELL MU. Please act as my personal trading
  assistant that gives ideas, entries, market briefs and intelligent thesis. Make sure
  all market data is always updated when providing outputs." → bot saves
  memory: "+user: Brendan is a swing trader…" (persistent user profile).
- [20:00] The bot proposes a briefing TEMPLATE: 1. Market regime (SPY/QQQ trend,
  rates/yields, semis & AI infrastructure strength, earnings/macro calendar risk);
  2. Position review (trend/support/resistance/volume, rel. strength vs QQQ/SMH,
  upcoming catalysts, thesis quality, risk level); 3. Trade setup (entry zone,
  stop/invalidation, target zones, risk/reward, suggested options structure);
  4. Wheel-strategy lens (cash-secured put levels, covered-call zones, assignment risk,
  IV attractiveness, worth owning at strike); 5. Clear stance (bullish/neutral/cautious,
  actionable setup vs wait).
- [03:50–04:40] Morning briefing output: VIX 15.32 → "Normal deployment — VIX<20, your
  rule allows normal 1–3% equity sizing"; SPY/QQQ tape vs 50D/200D; per-position blocks
  (NVDA price, momentum 1M/3M/12M, IV rank 43%/ATM IV 42%, 90-day insider buys/sells w/
  named directors); "Positioning takeaway": macro gate open, best momentum ORCL/NOK/NOW/
  NVDA, cleanest hold NVDA, most vulnerable long INCY, options risk (ORCL IV rank 100% =
  calls dangerous without catalyst), insider read; "Sizing reference": with ~$200K
  portfolio and VIX<20 → 1%=$2,000 / 2%=$4,000 / 3%=$6,000 + per-name share counts;
  "Bottom line" recommendation.
- [05:00–05:40] "set up a cron job for this specific morning briefing every day" →
  cronjob: create → Daily morning equity briefing, job ID, schedule 13:00 UTC (6 AM
  Pacific), delivery back to this Telegram chat, included skills:
  equity-trading-assistant + daily-equity-factor-refresh.
- [05:40–06:10] Ad-hoc deep query: "how is the insider activity in Nokia for the past 5
  days" → NOK price/IV rank/ATM IV/VIX regime + insider transactions via **Form 6-K**
  (foreign private issuer, not Form 4), two manager acquisitions w/ dates/shares/price/
  value, aggregate read (70,000 shares, ~$1.10M, VWAP $15.69), signal: constructive.
- [00:43] Separate factor-research dashboard (built by/for him): universe 503 (11
  sectors), 107 long candidates (top quintile/sector), 96 short (bottom quintile),
  highest-dispersion factor "quality", 0 crowding warnings, portfolio optimizer
  MVO (Markowitz factor-cov net-of-cost) vs conviction (top-N equal-weight + tilts),
  avg est. trade cost 7.8 bps (spread + sqrt market impact per name), factor scoring
  heatmap (Momentum/Value/Quality/Growth/Revisions/Short Interest × tickers), tabs
  Portfolio/Research/Risk/Performance/Execution.
- [00:55] Telegram: "give me trade ideas and wheel strategy candidates and a market brief,
  send them one message after another" → agent runs terminal/execute_code/send_message
  steps, each tool call "Approved permanently by Brendan" (permission model), then sends
  1/3 Market brief ("Sources checked: Stooq delayed EOD quotes dated May 29 2026; CBOE
  VIX historical feed timestamp…"), 2/3 Swing trade ideas….

## Concepts to carry into the plan
1. Chat-first trading assistant with PERSISTENT USER PROFILE memory (trading style,
   rules like "VIX<20", positions) applied to every answer.
2. Structured recurring briefing (regime gate → positions → setups → options lens →
   clear stance + sizing math) scheduled via agent-created cron, delivered to messenger.
3. Skills-from-experience + self-learning loop + built-in scheduler as the agent core.
4. Tool-call permission model ("approved permanently") + allowed-user-ID gating.
5. Honest data provenance lines ("sources checked: … dated …") in every market answer.
