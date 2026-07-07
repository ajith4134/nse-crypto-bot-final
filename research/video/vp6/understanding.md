# vp6 — "Insider Trading Agent — 7 named agents + consensus" (videoplayback (6).mp4, 13:12)

## One-paragraph summary
Lewis Jackson (ZeroOne Systems community) gives a **one-shot Claude prompt** that installs
"Insider Routines": **seven named AI agents** on your computer that scrape PUBLIC US
government / market disclosures and turn them into a consensus trading alert. Five scouts
(Eddie: SEC Form-4 insider buys daily 06:00; Maggie: 13F filings of Berkshire/Bridgewater/
Renaissance/Citadel/Two Sigma, Sun 19:00; Frank: Fed-speech dovish/hawkish sentiment, Mon
06:00; Maya: on-chain whale accumulation/distribution every 6h; Janet: your own portfolio
drift, daily 17:00) feed **Sophie, the "consensus oracle"** (every 30m), who fires ONLY
when ≥3 of 5 scouts agree on the same ticker+direction within a 7-day window; then
**Ross** (every 30m) is the sole outward-facing dispatcher, emailing (Gmail SMTP app
password) or Telegramming the human. Ross NEVER places trades — "the agents show you
what's worth looking at; you decide what to do with it."

## Every distinct idea (timestamp + frame refs)
1. **Premise** [00:00]: insiders must legally disclose (SEC Form 4); AI can read those
   disclosures before you wake up — "ears on the door" of insider trading, legally.
2. **Named human-like agents** [01:24, f_0140]: Eddie, Maggie, Frank, Maya, Janet, Sophie,
   Ross — "real names, not weird AI names".
3. **Consensus model** [01:44–03:07, f_0210/f_0520]: 5 scouts → Sophie adds signals up;
   fires a CONSENSUS event only when ≥3/5 agree on same ticker + direction in last 7 days
   (tunable: DELPHI_MIN_AGREE=3, DELPHI_WINDOW_DAYS=7); fewer/stronger trades preferred
   over many weak signals; 2/5 compelling → nothing happens.
4. **Scout specs** (cards + final schedule, f_0340/f_0430/f_1100):
   - Eddie 01 — SEC Form 4 insider buys, daily 06:00 (CEOs buying own/other stock).
   - Maggie 02 — 13F institutional tracker (Berkshire, Bridgewater, Renaissance, Citadel,
     Two Sigma); classifies every move: new position / increase / full exit; weekly Sun
     19:00; filter: new positions + exits > $50M(?).
   - Frank 03 — Fed speech sentiment (dovish/hawkish) from last week's speeches, Mon 06:00.
   - Maya 04 — on-chain whale watcher every 6h; ACCUMULATION = exchange→private wallet
     (not selling); DISTRIBUTION = private→exchange (preparing to sell); BTC/WETH/USDC/
     USDT; cross-references known wallets w/ SEC filings [04:27].
   - Janet 05 — portfolio drift scout on YOUR holdings, daily 17:00 (optional; system
     works with 6 of 7).
5. **Sophie 06 — consensus oracle** [05:17, f_0520]: "listens to all five scouts. Never
   acts on one signal alone"; output: BULLISH/BEARISH + ticker + 3+ scouts + reasons;
   runs every 30m.
6. **Ross 07 — dispatch** [05:38]: Gmail/Telegram delivery; the ONLY agent that touches
   the outside world; never places trades.
7. **Architecture facts** (install summary f_1100/f_1130): lives at ~/insider-routines/
   with .state/logs + **SQLite state.db**; each scout = a small Python script; scheduled
   via **launchd** (macOS) — cloud/24-7 optional; smoke tests run Eddie end-to-end (JSON
   parsed → signal landed in SQLite) before declaring success; v1 scouts have no web-fetch
   tool (known limitation — "scouts get more interesting as they get tool access").
8. **Config/.env** [08:37, f_0840]: ANTHROPIC_API_KEY; GMAIL_USER + GMAIL_APP_PASSWORD
   (app password, never the real password); optional TELEGRAM_BOT_TOKEN/CHAT_ID;
   **model tiering overrides**: default Sonnet 4.6 for scouts, Haiku 4.5 for the cheap
   role, INSIDER_MODEL_FAST=claude-haiku-4-5, INSIDER_MODEL_DEEP=claude-opus-4-7 (deep
   reasoning for Sophie); Delphi tuning knobs.
9. **Onboarding-agent pattern** [06:39–11:02, f_0630–f_1040]: the one-shot prompt IS an
   installer agent with a persona ("You are the Insider onboarding agent… core operating
   rule: NEVER TELL — ALWAYS DO: step requires opening a file? you open it; requires a
   URL? you open the browser at the right moment; requires editing config? you create the
   config pre-populated and open it; never dump a wall of instructions"), detects OS,
   checks existing install, writes 13 files, installs deps, opens the Anthropic console /
   Gmail app-passwords page at the right step, validates each credential (even strips
   accidental spaces from the app password), runs smoke tests.
10. **Community prompt maintenance** [06:23]: the shared prompt is continuously fixed
    when users hit problems — you always get the latest version (crowdsourced prompt CI).
11. **Demo alert** [11:54–12:40, f_1204]: "[INSIDER] CONSENSUS BULLISH on NVDA" — Sophie:
    3/5 scouts agree; Eddie: Jensen Huang bought 25,000 shares (~$0.2M... "$0.5M" intro);
    Maggie: Renaissance added 4.1M shares in latest 13F; Frank: Powell + two governors
    net dovish, rate cut back on the table for Q1.
12. **Permission bypass workflow** [06:43]: Claude app → allow once → settings → local
    sessions bypass-permissions to let the installer run uninterrupted.

## Open questions
- None blocking.
