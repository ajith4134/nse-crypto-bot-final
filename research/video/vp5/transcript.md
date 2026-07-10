# Transcript

language: en (p=0.99)

[00:00] Hey everyone, welcome back to my channel. Today we are diving deep into something I have been working on for already a few days and autonomous trading bot for Kraken.
[00:11] No, this isn't just a simple ISE bot. It's a fully self-improving system using AI, historical data and advanced risk management.
[00:22] By the end of this video you'll see why this could be the future of algorithmic trading.
[00:29] Stick around, because we are talking real code, real data and real potential, let's get started.
[00:36] First of all, what is a Kraken bot? First, what is this bot? It's a Python-based algorithm that trades Europers on Kraken,
[00:46] sync Bitcoin, Ethereum, Solana and more. It uses technical indicators like ASI, SMR and momentum scouring to spot buy and sell signals.
[00:56] But here's a twist. It's not static. It learns from its own trades and improves itself autonomously.
[01:03] We are talking 24-7 optimization using AI agents powered by some different models.
[01:11] The bot once on Raspberry Pi connected to Kraken API, it reconstructed positions from trades history,
[01:18] had its fees and has built-in risk controls like stop losses, drawn-down limits and volatility adjustments.
[01:27] Right now, it's trading with about 20 euros in capital. You see, because I'm running out of these 200 bucks,
[01:36] which I'm entered because he bought a lot of Solana. But the real magic is in backtesting and then the improvement loop.
[01:45] I'm also waiting more money to it after the next improvements. How does it trade?
[01:52] The bot uses a multi-edged signal engine, mean reversion for oversold conditions and trend following for continuous...
[02:02] For example, it buys when ASI drops below 30 and the market is in a bull regime.
[02:09] It sells at profit targets like 10% gains or via hard stops. Shorting is supported too with leverage caps.
[02:18] Risk management is key. The bot has mentioned four, three protections.
[02:23] It switches to risk off mode in volatile periods, reduces position sites and pause after losses.
[02:31] It's designed to survive to the crypto markets while it shrinks.
[02:35] So backtesting is crucial. Use over a year of cracking historical data stored on a separate NAS drive to the Raspberry Pi,
[02:45] SIG level trades for accuracy. The bot simulates trades with real fees, so the included fees and slip page.
[02:54] Current baseline around 17% ground on over the year, but with improvements we are pushing for better risk adjustments returned.
[03:02] This is where it's getting excited. The bot improves itself.
[03:06] It built an autonomous loop with AI sub-agents, as you can see here on the left side.
[03:12] Three agents run in parallel. The book strategy agent pulls ideas from trading classics like
[03:18] mastering the trade by John Carter or trading price action strengths by AI books.
[03:24] It implements setup like bolling a band, breakouts or one, two, three reversals.
[03:30] Data pattern miner analyzes the data on the NAS directly.
[03:35] It finds pattern like by other after 9am UTC courses or sell BTC on high volatility spikes.
[03:43] It lowered the ASE threshold from 33 to 30 based on backtests.
[03:49] Risk metrics improve at advanced metrics like SHARP ratio, SORTINO ratio and KEDI criterion for positioning sizing.
[03:59] It enforces maxed round-down limits and autostops. The agent uses for now GROC, an advanced eye-medal to generate code changes.
[04:07] They push to a dev branch. The system backtests again against main.
[04:12] If dev outperforms in both 30-day and one-year backtesting simulations,
[04:18] merging happens automatically and the live bot restarts within the improvements.
[04:25] So it's all autonomous, no manual intervention, the loop running 24-7 testing new ideas against real data.
[04:34] So far we have added ASE tweaks, calisizing and pattern mining.
[04:40] The goal turned the baseline bot into a profitable day trader.
[04:45] So the current status and the results, where we are now.
[04:50] The bot has trades about 90 times within a win ratio around 39, but capital is low.
[04:58] So it's conservative. With more funds, it could execute more signals.
[05:03] The autonome loop is active, we're implementing ASE performance and risk metrics.
[05:08] Next merge could happen soon if the backtest shows gains.
[05:13] Potential with good strategies that could achieve 5 up to 10% annual returns over baseline day trading is risky.
[05:21] But data-driven AI makes it smarter. You're not gambling, we are engineering here in my opinion.
[05:28] What's next? So what's next? More agents for multi-language models, external data integration or Monte Carlo simulations.
[05:38] If you're into algorithm trading, this shows the power of AI and data.
[05:43] So if you're enjoying this, having feedback for me to improve this or want to work with me at this,
[05:50] you can contact me. I have also created the Discord server, which is in description.
[05:56] And the GitHub repository is also open for everyone so you can have a look, give feedback.
[06:03] And you can also watch this bot working 24-7 in this live stream here, which is also on this channel.
[06:12] It's like a freshly channel and like an experiment.
[06:16] I hope you enjoy. Leave a like if you enjoy, please share it.
