# Transcript

language: en (p=1.00)

[00:00] I've built hundreds of polymarket trading bots, but the easiest bot to build is actually
[00:06] not a prediction bot, it's a copy trading bot.
[00:10] But the version I want to teach you how to build here today does not just find a whale
[00:15] and blindly follow whatever they do, because that breaks too fast.
[00:19] A wallet can show massive profit and still be a terrible copy target.
[00:25] Maybe all the profit came from one lucky trade or a few lucky trades.
[00:30] Maybe the wallet is only good in one category.
[00:33] Maybe the markets are too illiquid.
[00:35] Maybe by the time you see the trade, the price has already moved way too far.
[00:40] So this bot starts one step earlier, because before it copies trades, it finds the wallets
[00:46] worth copying.
[00:48] It pulls the polymarket leaderboard, scans the top 500 wallets, studies the last
[00:54] 30 days, scores each by ROI consistency and copyability, then it trades the best signals
[01:02] with simulated $5 to $20 positions.
[01:05] The whole thing runs through Hermes agent and the performance shows up in a dashboard inside
[01:12] of my own mission control.
[01:13] Hermes scans the leaderboard, updates the wallet profiles, watches new trades and basically
[01:19] runs almost everything for us and then sends us an end of day report.
[01:24] I've had strategies make me thousands a month and I've had strategies lose me thousands a
[01:30] month.
[01:31] By the end of this video, you should have yourself a strategy that improves with time
[01:37] on its own without you having to do anything but monitor it every once in a while.
[01:43] If you keep watching this video till the end, I'll also be giving you the full prompt
[01:48] to build out everything I'm about to outline in this video.
[01:51] So this is not just a trading bot, it's a copy trading research system that has to prove
[01:58] the edge before it earns autonomy.
[02:01] And the first problem is not how to place trades, the first problem is figuring out who is actually
[02:08] worth copying.
[02:09] Let's get started.
[02:14] The beginner mistake is thinking the leaderboard tells you who to copy because it doesn't.
[02:21] The leaderboard tells you who made the most money and that is very useful information but
[02:28] that's not enough.
[02:29] A wallet can make money in a way that is impossible for you to follow.
[02:33] If one wallet made most of its profit from one massive trade or from like three big trades,
[02:40] that is not a repeatable signal yet.
[02:42] If one wallet trades tiny markets with no liquidity, the return might look amazing
[02:49] for that wallet but copying it could be impossible.
[02:53] And if one wallet enters early and moves the price too high, you might always arrive late.
[03:00] Something very important, if one wallet is great at say politics but terrible at crypto,
[03:05] copying every trade from that wallet including the trades or the categories it sucks at
[03:11] is just a recipe for disaster.
[03:13] So the first part of the bot that I recommend you build out is a leaderboard scanner
[03:18] that pulls the top 500 wallets from Polymarket, then it does not ask who made the most money,
[03:25] it asks who is copyable.
[03:27] Here's the difference, let me explain.
[03:29] For every wallet, the bot should calculate three main scores, ROI, consistency and copyability.
[03:37] ROI tells us whether the wallet made money, consistency tells us whether the wallet seems
[03:43] repeatable or whether the results came from just a few lucky hits.
[03:48] Copyability tells us whether we can realistically follow the wallet without getting wrecked by
[03:54] late entries, bad spreads or just category mismatch.
[03:58] That score is the real starting point for any of your bots.
[04:02] Because if the wallet universe is bad, the rest of the system is just beautifully organized chaos.
[04:09] The bot should also rank wallets by category, politics, crypto, sports, macro, so on and so forth.
[04:17] A wallet should not get treated as universally smart just because it was right in one lane.
[04:24] That is where a lot of copy trading systems get sloppy.
[04:28] They treat a wallet like a genius when the wallet might only have edge in one specific market type.
[04:35] So before the bot watches trades, it creates wallet profiles and whether blind copying
[04:42] that wallet would have worked over the last 30 days because you always want to have
[04:46] a comparison, a baseline.
[04:48] That gives the bot a better foundation.
[04:50] But once we know which wallets are worth copying, we still should not blindly copy every trade.
[04:58] That is the next mistake.
[05:01] The dumb version of copy trading is simple.
[05:03] Wallet bought, yes, so I buy, yes.
[05:07] That's not a strategy.
[05:08] That is outsourcing your bad decisions to someone else's wallets.
[05:13] A better copy trading bot starts with a better question.
[05:17] Is this trade still worth copying right now?
[05:20] That means every new wallet trade gets scored before anything happens.
[05:25] Who made the trade?
[05:27] What category is this wallet actually good for?
[05:31] What price did they get in?
[05:33] What price can we get in now?
[05:34] How far has the market moved since their entry?
[05:37] How soon does this market resolve and is this wallet usually early enough to copy?
[05:43] Or is this a real thesis, not just signal?
[05:47] The decision labels that your wallet uses should be simple.
[05:52] Copy, watch list or skip.
[05:55] Copy means the trade is strong, the category is a fit, the market is liquid enough,
[06:00] the entry is not too late, it passes all the checks.
[06:04] So we copy.
[06:05] Watch list means the signal is interesting, but the entry is not clean yet.
[06:09] So the bot watches it.
[06:11] It does not copy it, but it places us on its watch list to see how it's done later on.
[06:18] Should we have copied it?
[06:19] Was it a good decision not to copy it?
[06:21] So on and so forth.
[06:22] Skip.
[06:23] The last one means the trade is too late, too illiquid, too noisy, or just outside
[06:28] that wallet's proven edge.
[06:31] This is where the bot becomes super useful.
[06:34] Not because it predicts everything, because it refuses most of the bad copies.
[06:39] A good skip is as important as a good entry.
[06:43] Trust me when I say this.
[06:44] If the bot stops you from chasing a wallet after the market already moved like 25%, that
[06:51] is valuable.
[06:52] If it ignores a high ROI wallet because the wallet only made money from a few small
[06:58] trades, that is valuable.
[07:00] If it says a wallet is interesting, but only in crypto markets, that is valuable.
[07:06] But filtering one trade is still not enough.
[07:10] The real edge comes when the bot tracks whether its filters actually worked.
[07:15] That is why the next layer is paper trading.
[07:19] Okay, hear me out when I say this.
[07:21] Ask someone who's done this hundreds of times before.
[07:25] The first version of your copy trading bot should not place real trades.
[07:30] As much as you want it out in the wild, making you as much money as early as
[07:35] possible, it should paper trade first.
[07:39] Paper trading means the bot acts as it is placing real money, but it does not
[07:44] actually execute anything.
[07:46] It just simulates that it is.
[07:49] If a high scoring wallet enters a market and the trade passes the filter, the
[07:53] bot creates a simulated position.
[07:56] It assumes as though it's placed money on it, and then it tracks.
[08:00] By the time of closing, it sees that we make money, that we lose money.
[08:05] Was it a good bet, a bad bet?
[08:07] The way I typically place my copy trading wallet is the following.
[08:12] I have three tiers.
[08:14] It places $5 bets for a decent signal, $10 bets for a strong signal, and $20 bets
[08:22] for the highest confidence signals.
[08:24] This mitigates the risk so that you're not just $20, $20, $20, $20, you end up
[08:30] wrecked after a couple of days, hours.
[08:34] Then Hermes updates the paper PNL every single hour.
[08:38] The bot should not only ask, did we make money on paper?
[08:42] It should ask, did our filtering improve the strategy?
[08:46] If blind copying the leaderboard beats our bot, then the bot is not
[08:51] adding value.
[08:52] If the filtered strategy beats blind copying, now we have something worth studying.
[08:58] I also want the bot to track missed winners and avoided losers, because those are both lessons
[09:04] that it can use to learn and improve.
[09:06] If the bot skips a trade because liquidity was bad, and that trade later loses, that
[09:12] was a good skip.
[09:13] If the bot skips a trade because the entry looked late or bad, and the market keeps
[09:19] running for some reason, maybe the late entry rule we have is a bit too strict.
[09:25] The point is that paper trading creates evidence.
[09:29] And without evidence, the bot is just confident for no reason.
[09:34] With evidence, however, the bot can improve.
[09:36] And the evidence lives inside the decision journal.
[09:41] This is the soul of your system.
[09:44] Every signal needs a decision journal entry.
[09:48] Not just what happened, why the bot made the decision.
[09:52] For example, Wallet A bought, yes, on a crypto market at 42 cents.
[09:59] The current price is 45 cents.
[10:02] The spread is 3 cents.
[10:04] The wallet has a strong crypto track record.
[10:06] Market resolves in two hours.
[10:08] Liquidity is acceptable.
[10:10] Decision, copy.
[10:12] That is what a journal entry should look like.
[10:14] Along with a reason, this wallet was strong, a good category fit, still early enough.
[10:21] Price movement is not too far.
[10:24] Your bot should place its reasoning for copying the trade.
[10:27] That journal is what lets your bot get better.
[10:30] Later, when the market moves or resolves, the bot can review all of its previous
[10:36] decisions.
[10:37] Did paper copy trades actually improve after the signal?
[10:41] Did watchlist traders become better entries later?
[10:44] Did skips save us from bad trades?
[10:47] This is where the self-improvement part of this video actually happens.
[10:53] Maybe the bot learns not to paper copy if the price has already moved more than 12 cents.
[10:59] Maybe it learns that a certain wallet is only copyable for crypto-related events.
[11:05] Maybe it raises the minimum liquidity threshold.
[11:09] This is what self-improving should mean.
[11:11] Not the agent magically becomes a genius overnight.
[11:15] Decision loop that tracks its own reasoning and gets less stupid over time.
[11:21] Or smarter over time.
[11:23] However you want to see it.
[11:24] And because this is paper trading, I recommend the rule updates to happen automatically.
[11:31] Again, the bot is not trading real money at this stage yet.
[11:35] So it should not ask you before changing a paper trading threshold.
[11:39] It should just log what changed and why.
[11:42] Rule version one becomes rule version two.
[11:45] The dashboard shows the old rule, the new rule and the evidence.
[11:49] And the reason Hermes changed it.
[11:51] That is the difference between a notification bot and an agent.
[11:55] A notification bot tells you what happened.
[11:57] An agent changes how it decides based on what happened.
[12:01] Now, the question is what we actually need to build on to step five.
[12:08] I recommend you build this in nine parts.
[12:11] And again, as I promised at the end of this video,
[12:13] I'm going to give you the full prompt so that you can build this out yourself.
[12:18] But when I say I recommend you build this in nine parts,
[12:21] it's me saying I recommend that you check each of those nine parts work,
[12:25] step by step, chronologically.
[12:28] So don't fix step five before step one works.
[12:32] That being said, let's start with one.
[12:34] First thing is the leaderboard scanner.
[12:37] It should pull the top 500 wallets and create a wallet universe.
[12:42] It's just, you know, a universe where wallets exist and are being tracked.
[12:47] Second is the wallet profiler.
[12:50] It scores ROI, consistency, copyability.
[12:54] It takes every single thing you would want to take a look at.
[12:58] And it gives it a score so that you minimize copying traders
[13:04] that are one hit wonders or that make just a few good trades
[13:08] or that impossible to copy because they trade at the very last second of a market.
[13:13] Third is a trade monitor.
[13:17] This should watch selected wallets and detect new trades.
[13:22] The fourth would be the trade score.
[13:24] It should check whether the new trade should be paper copied,
[13:28] watched or skipped, right?
[13:30] Copy, watch, skip.
[13:32] Fifth would be the decision journal.
[13:35] This is again where it records the score, the reason, the risks
[13:39] and the rules that it changed every time it decides to adapt.
[13:43] Sixth is the paper trading engine.
[13:46] It should create simulated positions.
[13:49] That's up to you whether you want it to be like mine
[13:52] where it trades between $5 to $20 positions,
[13:55] or if you want to just yolo and go straight to $100,
[13:58] it's paper trading anyways.
[14:00] So really you can choose whatever you want.
[14:03] I recommend you simulate it as though it is real
[14:07] and say you want to place $100 inside your wallet
[14:12] once it goes actually live and starts trading actual money.
[14:16] Then don't simulate $100 per trade.
[14:20] Simulate as though the wallet has $100 in total.
[14:23] So simulate reality.
[14:25] Seventh would be the hourly PNL updater,
[14:28] profit and loss updater.
[14:30] You should have a system that checks prices
[14:33] and updates your PNL every single hour.
[14:35] Eighth would be the outcome reviewer.
[14:38] This should check what happened after one hour,
[14:40] after six hours, after 24 hours,
[14:43] and the final resolution.
[14:45] And ninth, finally, the rule updater.
[14:48] It reviews performance
[14:50] and automatically updates scoring rules
[14:52] with version history, aka how you're bought.
[14:56] Improves with time.
[14:57] That is the actual system.
[14:58] And Hermes is the operating layer
[15:01] sitting on top of all of that.
[15:04] But if Hermes is running the loop,
[15:06] chat is not enough to supervise it.
[15:09] That is why we move on
[15:11] to one of the most important pieces of the puzzle,
[15:14] the dashboard.
[15:16] I want my copy trader
[15:18] to live inside my Hermes agent's mission control.
[15:22] I call mine Herme HQ.
[15:24] Telegram is good for summaries, don't get me wrong.
[15:27] Hermes is good for doing the work,
[15:29] but performance needs visualization.
[15:32] We're visual creatures.
[15:35] Hermes could send me a block of text
[15:37] and I could be like, okay, cool.
[15:40] But just seeing that PNL go up
[15:44] is what signals to my ape brain that,
[15:47] oh my God, this is working.
[15:49] The dashboard should answer three questions immediately.
[15:53] Are we profitable on paper?
[15:55] Which wallets are worth copying?
[15:57] And what did the bot learn today?
[15:59] That's it.
[16:00] You shouldn't get analysis paralysis
[16:02] by looking at thousands of different things on your screen.
[16:05] There shouldn't be a giant wall of text or charts
[16:09] that makes you feel smart,
[16:10] but does not change the decision.
[16:12] The overview page should show paper PNL,
[16:15] win rate, open paper positions, active tracked wallets,
[16:19] copy candidates today, latest rule changes
[16:23] and an end of day report status.
[16:26] It's your dashboard.
[16:27] So if there's something that you prefer to see
[16:29] or something that you prefer not to see,
[16:31] then feel free to change that.
[16:33] This is where you can get creative.
[16:35] This is where I recommend you get creative
[16:37] because the dashboard really should be something
[16:39] you enjoy looking at.
[16:40] You enjoy watching.
[16:41] You enjoy opening up
[16:43] and seeing whether you've made money or lost.
[16:49] For the actual build,
[16:50] I literally asked Hermes to refine
[16:53] my initial copy trading agent.
[16:56] And this is what it gave me.
[16:58] Build me a Hermes powered self-improving
[17:01] polymarket copy trading bot
[17:02] with a Vercel dashboard that can be added to Max HQ.
[17:06] This is my mission control,
[17:09] but for you, I would change it added to my mission control
[17:14] or if you don't have a mission control,
[17:17] here's where I recommend you just remove that
[17:20] with a dashboard, Vercel doesn't matter.
[17:25] So feel free to customize this
[17:27] depending on your situation.
[17:29] And then as you can see,
[17:31] this is a very, very, very, very long prompt.
[17:36] It will take hence why at the beginning of the video
[17:38] I said an hour of back and forth
[17:41] because there was a lot to build and focus on.
[17:47] That being said, what I did, I took this
[17:51] and I copied it onto my Hermes agent
[17:54] so I could build one out for you guys.
[17:56] Literally here, you can see me pasting
[17:59] that massive mammoth of a prompt
[18:01] and then it literally running through
[18:04] and building it out.
[18:05] And this is what it looks like.
[18:07] Now that it's done,
[18:08] it started trading at 9 a.m. today.
[18:11] It's currently 11, so it's been two hours exactly
[18:14] that it's been live.
[18:15] And as you can see, it just started
[18:17] and it's updating its positions accordingly.
[18:20] It's currently negative $5 in profit,
[18:23] but again, this is paper trading right now.
[18:28] This is where it starts developing.
[18:31] It's thesis, it starts improving every single day,
[18:36] every single week and at this point
[18:39] you just wanna let it run, let it improve,
[18:41] let it find a profitable strategy
[18:43] or profitable strategies plural
[18:46] and then you can start running it.
[18:48] This is essentially what it can look like
[18:51] once it is completely live,
[18:55] once it's learned a lot more,
[18:59] once it's developed its own strategies essentially
[19:03] and as you can see, it can start improving
[19:06] so on and so forth and scoring itself
[19:10] after every improvement.
[19:12] And as you can see, not only should it show you your PNL,
[19:15] it should show you your win rate,
[19:17] it should show you which version is on
[19:19] and what it has learned with every single version,
[19:22] with every single new version that it implements.
[19:26] And that's pretty much it.
[19:28] That's what it should look like.
[19:29] By the way, quick update here.
[19:31] Just before I go to sleep,
[19:33] I wanted to quickly check on our copy trading bot
[19:38] and this is where we are at.
[19:41] We are $27 in profit with a 57% win rate.
[19:46] It's only copied six positions today,
[19:50] yesterday, just exactly when we set it up,
[19:53] it was at seven, just right before we sleep.
[19:56] So it's been 24 hours and as you can see,
[19:59] started $5 negative, then went up to eight,
[20:04] went back to break even and boom,
[20:06] all of a sudden almost $30 in profit.
[20:11] I went ahead and asked my Hermes agent, what was up?
[20:15] What was driving that?
[20:16] And it's mostly some of these trades
[20:19] which are USA versus Australia.
[20:22] The match just happened today
[20:23] and our bet won, which won us $15.
[20:27] Again, this is paper trading money,
[20:29] so we don't actually make anything yet,
[20:33] but just goes to show the strategy is on a good turn.
[20:38] Our bot is currently self-updating and on version three.
[20:44] So yeah, this is just version three.
[20:48] The long-term goal for you should be autonomy
[20:52] for the bot to be able to run on its own,
[20:54] but autonomy has to be earned.
[20:58] I would not let this place real trades
[21:00] just because the dashboard looks cool.
[21:03] I would want at least 30 days of paper trading,
[21:07] positive paper trading, at least a hundred paper trades,
[21:12] a clear win over blind leaderboard copying,
[21:16] no major data failures and a drawdown profile
[21:20] that does not look insane.
[21:22] Until then, this is a research agent
[21:25] and that is not a limitation, by the way.
[21:27] That is the point.
[21:28] If the paper version proves the edge,
[21:31] then real execution becomes a separate problem.
[21:34] If the paper version fails,
[21:37] then the bot saved us from automating a losing strategy
[21:41] and that, my friend, is also a win as well
[21:45] because the goal is not to make an agent gamble.
[21:47] The goal is to build an evidence layer
[21:50] before money is involved.
[21:53] Look, a good polymarket copy trading bot
[21:57] is not a whale following bot.
[21:59] It's a filtering system that is the part most bots skip.
[22:04] They chase signals, but they do not review their own decisions.
[22:08] And if you do not review decisions,
[22:10] your bot simply can't improve.
[22:13] So the system you should follow
[22:14] for any copy trading bot is very simple.
[22:17] A leaderboard scanner, a wallet profiler,
[22:20] a trade scorer, a decision journal for self-improvement,
[22:24] a paper trading engine for testing validation,
[22:28] a rule updater, and a dashboard for ease of access.
[22:34] If you want to build this yourself,
[22:36] I will put the full build prompt in the description,
[22:39] but please, please, please make yourself a favor,
[22:43] do yourself a favor, start with paper trading first.
[22:46] Make the bot prove the edge,
[22:48] then decide whether it deserves real money.
[22:51] If you enjoyed this video, make sure to leave a thumbs up.
[22:54] And if you're new to this channel, make sure to subscribe
[22:57] because I have a ton more videos like this on my channel
[23:00] and a ton more coming just like it on your way.
[23:04] Oh, would you look at that?
[23:06] The algorithm gods seem to think
[23:08] that you will really enjoy this video.
[23:10] I'll see you there, question mark.
