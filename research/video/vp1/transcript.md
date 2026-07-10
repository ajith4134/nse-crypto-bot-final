# Transcript

language: en (p=1.00)

[00:00] I turned 50 dollars into 500 and then I stopped checking it for a few days and when I came back
[00:09] it was all gone literally zero and here's the thing that got me I didn't lose it in one bad trade
[00:17] I actually watched it happen in real time and I didn't realize my bot was slowly draining itself
[00:25] to death so rewind to march 4 I dropped this video called I made seven AI agents fight to the death
[00:32] with real money the concept was simple I gave seven different AI models 50 bucks each with the same
[00:39] exact prompt same market same rules you get it and I just let them trade against each other on
[00:44] hyper liquid for four rounds it was a trading war and Claude opus dominated he ended with 107
[00:52] dollars that's a 114.4 percent gain from a $50 starting balance 31 trades and he crushed it
[01:03] kimmy k2 came in second place with 56.63 dollars and every other model lost money so I'm sitting there
[01:13] and I'm watching this and thinking to myself okay this bot is actually good 114.4 percent
[01:22] in four rounds what if I just kept it running so that's what I did I left the bot live with the
[01:29] exact same prompt and strategy and I started watching it daily and it kept climbing and
[01:36] climbing 50 went to 107 107 went to 300 300 went climbing towards 500 at one point
[01:46] it had 500 dollars that's a 10 times return on the original 50 that it started with
[01:54] and I'm looking at this I'm like holy crap this is actually working this AI is learning the market
[02:01] it's adapting this is the future of trading I'm telling people about it I'm thinking about this and
[02:08] then life gets busy right I stop checking as often a day goes by two days maybe three I'm not
[02:16] obsessing over the account balance anymore then one day I pull up the hyper liquid app to check
[02:24] on its progress and something feels wrong the balance hasn't been updating in like the last 24
[02:30] hours and I think to myself that's strange let me actually look at the full breakdown and I pull it up
[02:36] and I see zero the account was at zero so I do what I always do I message max on telegram and I'm
[02:45] like yo how's hyper liquid doing our balance hasn't changed in like 24 hours and max being max
[02:53] starts digging into the full data and he comes back with this I'm just gonna let you see it for a bit
[03:03] he literally says account is at zero dollars no balance no open positions looks like either
[03:11] everything was closed out or funds were moved so the zero dollar balance isn't new 814 trades
[03:19] later 814 that's a lot of trading closed PNL was negative 193 66 dollars and then fees negative 115 20
[03:34] so the bot was losing money on the trades and bleeding it all in fees net result was a negative
[03:43] 386 dollars and losses and fees combine and the account was sitting at zero here's what absolutely
[03:53] killed me about this it wasn't one catastrophic trade it wasn't like the bot went all in and
[04:00] lost everything on a stupid move it just slowly started bleeding when the market conditions all
[04:05] of a sudden reversed over hundreds of trades it lost a tiny bit here a tiny bit there
[04:12] the fees adding up and adding up the bot was like a boat with just a small leak that just
[04:19] wasn't noticeable enough and you don't notice it until you start sinking i'm sitting here thinking
[04:26] okay so what went wrong the battle royale strategy was working 114.4 percent but something
[04:37] changed maybe the market conditions shifted maybe the parameters that worked in four rounds just
[04:44] don't simply scale to 400 rounds maybe the rsi settings need adjustment or the position sizing
[04:50] or the take profit levels i genuinely don't know so i do the most logical thing i try to manually
[05:00] tweak the bot myself i'm gonna be smarter about this i'm gonna change the parameters and make it
[05:06] better you can probably tell how this one went the win rate dropped from 19 percent what it was
[05:14] after the bot started failing to 12 percent 12 percent that is far worse than it was ever before
[05:24] so now i'm zero and getting even more negative so i killed the bot i'm not losing more money on
[05:31] this thing i'm just gonna figure out what went wrong and then the same week karpathi the guy who
[05:39] founded tesla autopilot drops this concept called auto research the idea is beautiful and it's simple
[05:48] instead of a human tweaking parameters you let an ai automatically run research cycles on your
[05:55] strategy the ai proposes small changes it tests them it keeps what works and it throws away what doesn't
[06:04] and it just keeps running forever improving itself bit by bit by bit and i'm reading this and i'm
[06:12] thinking wait what if i built and automated the parameter optimization what if i built a bot that
[06:20] runs every single cycle back test the current strategy against real market data and then asks
[06:27] claud or gpt to generate a completely new trading strategy tests it if it's better it keeps it if
[06:34] it's worse it discards it and tries again so that's exactly what i built okay here's the system we
[06:42] have at play i gave it two years of crypto data minute by minute that's 2024's full calendar year in 2025
[06:52] with the prices of bitcoin ethereum and selana with millions of data points it uses the 2024 data
[07:00] to come up with a strategy and then it back tests it with the 2025 data that we have right here
[07:08] so the 2025 it never looks at it it doesn't know the outcome of what's going to happen in 2025 the ai
[07:15] doesn't see it during training and every cycle you can see all the different generations the system
[07:22] does this it generates a completely new trading strategy you can see its strategy right here
[07:28] don chain channel breakout strategy using 20 period high i have no idea what this means but
[07:34] it's back testing this strategy and you can see that it's not profitable at all it had a hundred
[07:41] percent negative pnl meaning it literally went to zero and it'll keep generating a strategy
[07:47] each couple of minutes using chat gpt 40 mini via open router then it will back test that
[07:55] new strategy against the 2025 data the full year not a week not a month every single candle it
[08:03] runs the back test and gets the sharp score is basically a measure which returns reward relative
[08:10] to risk which is right here each and every single score that you see over here and here's the critical
[08:16] part it automatically checks for look ahead bias if a strategy wins too perfectly like this one
[08:24] you can see an 11 000 profit and loss ratio which is absolutely unrealistic why
[08:31] because it was looking ahead at the data it found the 2025 data and it just you know predicted it
[08:37] perfectly is of course you can predict it perfectly and it rejects that because of the results look
[08:44] almost too good it's probably just literally accessing the 2025 data and not actually doing
[08:51] the test itself as it's supposed to because if a strategy is just fitting for the past perfectly
[08:58] then it's completely useless for the future then it compares this new strategy to our current best
[09:05] strategy so you can see here this was the best strategy gen six and it doesn't accept a new
[09:12] strategy until it finds one that is better than the previous one so you can see it discarded this
[09:16] one because it was worse than the previous best and it found this one which was better and this one
[09:22] better better better better so every time it finds a better strategy then it locks it in as the
[09:29] main winning strategy and it just keeps going on and on and on and it loops forever until it has
[09:36] an even better strategy and a better strategy our current best strategy you can see happened on
[09:42] generation 61 so far which would have gotten us if we deployed it in all of 2025 until today
[09:51] out of a thousand dollar start we would be at a thousand eight hundred ninety six that's an 89%
[10:00] profit pnl the whole thing runs fast and as i'm sitting here filming this it's literally been
[10:06] through 133 generations and it just keeps going every cycle it tries something completely new
[10:13] every cycle it learns that's actually the point the current strategy isn't as good as
[10:21] it will be eventually in a day and two and three but the auto researcher is supposed
[10:27] to find those incremental improvements cycle by cycle generation by generation will it
[10:34] actually get to a hundred percent a 200 percent pnl i have no idea that's the honest answer
[10:41] but at least now i'm not sitting here manually tweaking parameters and making things worse
[10:48] the bot is iterating automatically testing in real time against real market data and only
[10:55] keeping changes that actually improve the back test okay here's the part where i show you how
[11:02] to actually build this yourself and i'm going to be real with you i didn't invent any of this
[11:08] the whole concept comes from carpathy carpathy dropped this github repo called auto research
[11:18] a few days ago the idea is that simple given a i agent a problem let it propose changes
[11:27] test them for you and only keep the winners and just repeat forever over and over and over again
[11:36] you can see his simulation right here his version is pointed at training language models he
[11:43] literally wakes up in the morning to a log of a hundred experiments that ran overnight while he
[11:49] was sleeping i saw that and i thought okay what if i pointed that same idea at a trading strategy
[11:57] instead of an ai model you can check it out over here i'll leave the link in the description
[12:02] below if you want to install it as well you can go to the read me page and see how it works
[12:09] basically and it's a fairly simple setup i mean the repo uses three main files the first one is
[12:17] prepare dot pi these are your fixed constants one time data prep it's your training data for me it's my
[12:25] bitcoin ethereum and salana data for the last two years then you have the train dot pi file
[12:31] which is the single file the agent edits it's the strategy that it's literally trying every
[12:37] single time and it's training data this file is edited and iterated on by the agent and then
[12:42] you have the program dot md file this is your baseline instructions for the agent this is basically
[12:48] the rules that i gave my agent for what is its goal and what do i want it to get to and he also
[12:56] has a quick start section on how you can install this yourself as well the way i installed it was
[13:04] through one of my open claw agents however honestly if i was to do it again i would highly
[13:10] recommend you install it with clot code it's just gonna save you a lot of hassle a lot of time wasted
[13:17] you simply just make sure you have clot code installed first then you run clot on your terminal
[13:24] from there yes i trust this folder i'm gonna give it the github repo as it is so the full
[13:33] link there you go i recommend you use high effort for this one and just like that i'm
[13:39] gonna give it the link to auto research hey i want to run this for a trading agent experiment run me
[13:54] through the setup let's set it up together and then one of the biggest hacks you can do use ask
[14:05] user question until you reach clarity and the last part of that prompt is super important
[14:15] instead of your ai assuming things it's going to ask you questions just to make sure you both
[14:21] are on the same page and you make sure nothing happens that it shouldn't just like that that's
[14:27] exactly how i would start running it from there it's probably gonna ask you know what is the
[14:31] experiment what is the goal what do you want to do and that's where the setup or most of the time
[14:37] a few setting it up is going to end up being and there you go got it i've reviewed the repo auto
[14:43] research a few questions it has to ask so what gpu hardware do you have available and here you
[14:51] just go on and start answering for me it's a mac auto research is designed for lm training research
[14:58] how are you planning to use it for a trading agent experiment train a trading lm you want to
[15:04] auto research as is but train on financial data uh yeah absolutely so this one where do you want
[15:12] to clone and set up the project here you choose where you want to set up the project boom and
[15:18] then you submit your answers i'm not going to do it i already have it installed i don't need
[15:22] another instance of it running in parallel although there are many many other things that you
[15:30] can backtest experiment on that you can run the auto researcher on the world is your oyster
[15:37] anything that previously required you hundreds of hours to test and try out and iterate on
[15:43] you can plug this on right now today once it's running it's completely autonomous
[15:50] you just leave it every few seconds it tries a new strategy backtests it against two years of real data
[15:57] checks that it's not looking at future prices to cheat and if it's better than the current best
[16:03] it keeps it mine has been running since this morning and it's already tried 133 different
[16:10] strategies that's it go to karpati's repo read the concept then open clot code and tell it to
[16:17] adapt it for trading the whole setup takes maybe about 30 minutes now here's the part i need to be
[16:25] real with you about i still don't know how well this works i don't know if the auto researcher
[16:31] will find a path to profitability once i run it live on real time data not on the past
[16:40] years or two years worth of data the current strategy is at 46 percent win rate that's not
[16:46] good nor bad but the bot might spend a hundred hours searching and only getting to 50 percent
[16:54] or 60 percent it might fail entirely i don't know but that's the whole point the auto researcher
[17:03] is learning it's iterating it's running a thousand small experiments so i don't have to
[17:10] and in the process i'm learning what works and what doesn't every single generation teaches me
[17:16] something about the market about the strategy about how price action interacts with different
[17:22] approaches and that's honestly more valuable than just having a profitable bot handing me cash because
[17:30] when the next market condition changes when the next thing breaks i'll know how to think
[17:36] about fixing it instead of just panicking and manually tweaking it until i think it
[17:43] worse much much worse so if you want to build this yourself go grab plot code spend some time
[17:51] reading the concept then let it run watch it iterate see what happens for yourself and
[17:56] then come back in a few days and tell me if the sharp ratio improved because honestly i have no
[18:03] idea what's going to happen but i'm about to find out oh and one more thing before i let you go
[18:09] while i'm spending my time building these bots that iterate automatically the reason i can do that is
[18:16] because i'm not manually having to post on x every day that's being handled for me and if you're a
[18:24] founder and you want to actually build your presence online without spending three hours a day
[18:29] writing tweets that's what we do add on fungible it's called the timeline takeover go check it out
[18:36] at founderfunnel.com if you want to see whether the researcher actually finds a profitable strategy
[18:43] subscribe because in a few weeks i'm dropping a follow-up with real numbers either it worked
[18:49] or it didn't either way we'll find out together see you next week
