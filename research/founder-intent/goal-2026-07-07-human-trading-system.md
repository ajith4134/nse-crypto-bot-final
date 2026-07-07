# STANDING GOAL — The Human Trading System (owner's directive, 2026-07-07)

> Status: ACTIVE GOAL — the brain must achieve this. Saved verbatim-in-meaning per the
> owner's instruction: "save all this message as the goal and try to save all the
> important words I mention without loss of meaning".

## The owner's message (original words, lightly line-wrapped only)

"i need you now implement w1 to w8 and invent even more self evolve brain other than
this that you think needed and i need you to make brain ultra advanced and find if any
even more advanced. 2. Human-UI engine (eyes→brain→hand→memory) + headed-Xvfb rendering
to make the trades only use binance and upstocks account and learn smart trading the
only way to pick more stocks and navigating the eyes for the brain and processing the
information like how screen mirroring is used to screen the device screen it uses all
the features of the trading app to open trade and make the eyes to brain to memory and
the hand to navigate the mouse on the trading account even more advanced and check if
all the self evolve, learning, research, memory knowledge all other features are
connected to one other and using them on the future open trades like i need you to make
all the features used on open trades on crypto and nse etc and suggest best ultra
advanced ideas on eyes brain trading account ui to the fullest even more and reduce all
the cpu strain on data getting through free apis i do not want that i need the brain
like an experienced trader: open the trading account upstocks and binance and use all
the features and all the data each and every data that the trade has on the trading
account web page and extend the open trades and close trades columns for brain learning
and neural network learning and make all this all connected human trading system with
brain eyes hands memory learning exploring strategies etc make it next level and save
all this message as the goal and try to save all the important words i mentioned without
loss of meaning and complete implement it. and one additional note the freqtrade is not
working correctly it is not opening trades and also the profit tailgating for every
crypto and nse trades new column and also check the screenshots of all this project's
dashboards to see if they are working correct and the designs are correct i need you to
be professional about it and judge this project as an outside specialist so you won't be
biased on arguing to use only existing code and not thinking of if there is an entirely
new advanced and more better code or feature to add or replace the current one you have
full authority on redesigning and replacing the code and features if it is better than
the existing one save it as a goal you need to achieve"

## Clarifications the owner gave when asked (2026-07-07)
1. **Execution**: "only placing orders with real money done using the Binance and
   Zerodha API and secret keys. When we turn to live, the brain decides everything in
   the trading app's web page and places the orders in APIs only — then we use the API
   keys I gave you: Zerodha for NSE, and Binance (separate from the Binance web account
   we are using). So all live and paper is the same, but in live with real money we
   execute using the orders only then we use APIs — for paper open orders and live open
   orders." → **Eyes+hand = decide/navigate on the web apps; ALL order placement =
   API-only (Zerodha for NSE, Binance API for crypto), same pipeline paper & live.**
2. **Free-API data polling**: "option 2 but fully on UI only for now — just disable it
   and first let's see its performance only on UI web app accounts. After that we will
   decide to add a thin API safety net." → **Disable free-API market-data polling; the
   trading web pages are the ONLY data source for now; revisit a thin safety net after
   observing performance.**

## The goal, decomposed (checklist the brain must achieve)
_Statuses verified against code + live state 2026-07-07 post-session (all W-tests green: 99/99)._
- [x] W1 Goal-scoreboard layer (goal.yaml per segment; every trade scored vs goal)
      — `94c0e5a`/`e8284eb`: trading/goal.py+goal.yaml, /api/trading/goal_score, boss reads it
- [x] W2 Scientific-method rails (one-variable-only, versioned rules w/ evidence,
      parameter-ownership map, read-only-first mode flags)
      — `e8284eb`: trading/brain/surface.py (ownership map, read_only|live, rule_versions.json)
- [x] W3 Evidence lane (blind baselines, missed-winners/avoided-losers counterfactuals,
      autonomy gates, fee-bleed & frozen-balance watchdogs)
      — `e8284eb`/`90b7e78`: trading/evidence.py; evidence_lane.json live
- [x] W4 Smart-money scout swarm + consensus oracle + read-only dispatcher
      — `5c096c0`/`9dc0d5d`: trading/scouts.py (Eddie/Maya/Frank/on-chain + Sophie + Ross);
      UI-only-data-compliant scout set; DELPHI_MIN_AGREE=2 while swarm is small (env-raisable
      to 3); NSE insider/FII-DII/cenbank scouts join when the crawl captures those pages
- [x] W5 Champion-loop hardening (lineage, look-ahead tripwire, dev-branch promotion
      with dual-horizon triple-metric gate)
      — `cf14c2d`: generators/base.py champion/challenger ledger (DSR+Sharpe+return ALL-improve
      gate = vp5's dev→main mechanic) + leak_tripwire.json
- [x] W6 RL execution-policy node (PPO, (direction,SL,TP)-menu actions, paper-only)
      — `947d685`: trading/rl/exec_policy.py (SL+TP-same-candle=LOSS, strict holdout)
- [x] W7 Meta-articles per execution + per-agent/strategy track records + rule-of-three
      — `612d7bc`: trading/brain/track_record.py (hot-path-safe meta queue → brain_memory)
- [x] W8 Chat-employee layer (daily briefing w/ regime gate + sizing math, provenance)
      — `6e59911`: trading/brain/briefing.py (provenance line on every brief)
- [x] Human-UI engine: eyes (headed-Xvfb screen-mirror perception of Binance + Upstox
      web apps, EVERY datum on the page) → brain → hand (mouse navigation using ALL app
      features, stock/coin picking like an experienced trader) → memory (episodic UI
      knowledge); execution API-only (Zerodha NSE / Binance crypto)
      — `b4ea143`/`8eac96b`/`2eb6078`: human_ui.py + crawl parity + ui_health chain check
- [x] Free-API data polling disabled; UI-only market data; CPU strain reduced
      — `fc00590`/`f999224`: governor auto-flipped ui_only_mode 2026-07-07 14:00 (verified live)
- [x] Open/closed-trade columns extended with UI-derived data for brain + NN learning
      — `b0cd103` (#12): decision_snapshot.ui_view at the entry_meta.record chokepoint
- [x] Profit-tailgate columns on EVERY crypto and NSE trade — `94c0e5a` (+ crypto tailgate)
- [x] All features (self-evolve, learning, research, memory, knowledge, strategy
      exploration) verifiably connected AND used on future open trades (crypto + NSE)
      — `4d6789b`/`93bd410` (#13): trading/connectivity_check.py PRESENT/MISSING proof
- [x] Freqtrade not-opening-trades bug fixed — `e8284eb` (entry-wedge fix)
- [x] All dashboards screenshot-QA'd (working + correct design)
      — research/visual-qa/report-20260707-135402.md + data-consistency runs (`fffc3cc`)
- [x] Independent outside-specialist audit; full authority to replace/redesign anything
      when a better approach exists (no bias toward existing code)
      — `9dc0d5d` (#15): research/audits/independent-audit-20260707-140342.md + verdict
- [x] Ultra-advanced eyes-brain-UI ideas proposed beyond the above
      — `baac5e1` (#16): 8 invent-beyond ideas ledgered; #1 curiosity + #2 active-inference
      crawl BUILT; #3-#8 (UI world-model, sleep-replay, live autoresearch driver, recurrent
      exec policy, cross-app arbitrage, advintel) remain the proposed next wave
