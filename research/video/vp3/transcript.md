# Transcript

language: en (p=1.00)

[00:00] In today's video, I'll show you how I built a self-learning AI trading agent using Hermes,
[00:04] which is basically one of the most powerful AI agents on the market right now.
[00:08] We can use Hermes to act as our 24-7 AI analysts that can monitor markets and our own portfolio
[00:14] for us. It can scan for trade setups and even send signals, alerts, and trading suggestions
[00:20] directly to my phone. And because we're using Hermes, it actually has a self-improving loop
[00:24] with persistent memory. What this means is that it can actually remember things like your
[00:28] portfolio, trading styles, strategies, and your positions. So it's going to take all this
[00:33] information across every single conversation and actually improve it over time by building skills.
[00:38] This means that the more you use Hermes and the trading agent, the better it gets.
[00:43] Now, this is huge since on the channel, I almost always cover either Claude code or Claude as a
[00:48] whole. But now with Hermes, I basically have my own AI trading employee. So I can wake up in
[00:53] the morning, check my phone, see what trades it found for me or any research that I asked it to
[00:58] do. I can approve trades without ever even opening up my laptop. And then throughout the day,
[01:03] I can chat with Hermes like it's my own employee. So I have what is essentially a trading analyst
[01:09] on my phone at all times. So in this video, I'm going to show you exactly how Hermes works,
[01:15] examples of how to use it, and how to set it up yourself since it's super easy to get going.
[01:19] It's an open-source framework, so it's completely free to use once you connect your LLM to it.
[01:24] You really just need your own local dedicated computer or VPS from Hostinger and a messaging
[01:29] platform like Telegram, Discord, even iMessage. And once we do get it set up, you basically have
[01:36] this assistant that you can talk to rather than using Claude or Claude code to write these complex
[01:40] Python scripts. And like always, this video is for educational purposes only. I'm not guaranteeing
[01:45] any profits in this video as everyone would use Hermes differently. This is a super simple
[01:49] agent to use when it's all set up. And here on the screen, you can see all the available
[01:53] tools and skills that it can actually do for you. So to start with the tools, we can see that
[01:57] it's able to browse the web for us, execute code, take control of your computer as well.
[02:02] Prom jobs are what you can use to automate certain tasks. So this is going to be super
[02:06] helpful. You can literally just go to Telegram, message the Hermes agent, never look at any
[02:11] code at all. All you need to do is connect Hermes agents, either Claude, ChatGBT, or another AI
[02:16] provider, and you're pretty much good to go. So with plain language, you can tell your agent,
[02:20] your portfolio, trading styles, strategies you're using or you want to test, you can monitor certain
[02:25] sectors like semiconductors, and then you can also automate the actions with cron jobs so that
[02:30] it runs every single day, hour, minute. Now the benefit here of using a Hermes agent rather
[02:35] than just typing to Claude or using Claude code is that everything basically lives inside your
[02:39] messages. This means that as you chat with this Hermes agent, it's basically going to learn
[02:44] everything about you, how you trade, what you like it to do. It saves all this information
[02:49] into its persistent memory. And it even creates skills files around all these questions that you
[02:53] ask it and all these things you wanted to monitor. This way, the more you use this trading agent,
[02:57] the better it learns and adapts to you specifically. You have the benefits of building out automated
[03:02] systems that you typically would do in Claude code. So those are the more robust and complex
[03:06] systems that you would have Claude code, essentially generate code for you for. But
[03:10] it's also super easy to chat to have a do things for you, execute triggers and set up automated
[03:15] alerts. But you don't need super detailed prompt with endless debugging inside an IDE.
[03:20] Hermes will just simply create files for you, skills for you, search the web for you and
[03:24] automatically do things for you. So just to give an example, let me just say,
[03:28] Hello, Hermes. So this is how we basically wake it up, start talking to it. And then each time,
[03:32] like I said, when you chat with Hermes, it's going to remember everything that you've talked
[03:36] about before, your portfolios, trading styles, things like that. So as a first example, I'm
[03:41] just simply ask to give a morning briefing as a Friday when the markets were last open.
[03:45] And then as we can see, it's typing thinking and basically going to give us back a response on
[03:50] whatever we asked. It's going to be able to go through its skills that it's built for us. And
[03:54] again, this is specific to you as it learns more and more about you and how you like to
[03:58] conversate and use Hermes. And then here we can see our market briefing that's tailored
[04:02] specifically to us. Now Hermes does have the context that I like to look at market regimes
[04:07] specifically VIX to see how the macro market is doing. And then it actually goes through our
[04:11] portfolio. So again, it has the context because I've chatted with Hermes before,
[04:15] but if this is your first time using it, you would obviously feed it what you're currently
[04:18] trading, what you're currently holding. And then it's going to give you a summary on your
[04:21] current long. So here we have Nvidia, Microsoft, and then we also have our calls that we're
[04:26] holding. So Nokia, ServiceNow, Sony, Oracle, things of that sort. And this way you're
[04:31] going to have, you know, advice from Hermes based on all this information,
[04:35] sizing preferences, and then approximate share accounts, everything that you would
[04:38] ever really need inside a morning briefing. Now here's where Hermes becomes super helpful,
[04:43] but just through cron jobs or automated jobs. So rather than asking, you know,
[04:47] the Hermes agent every single day for a morning briefing, what we can do is set up
[04:51] cron jobs, which are basically scheduled tasks that run. So for a first example,
[04:55] if we just wanted this morning briefing every single day, we can say set up a cron job.
[05:00] Again, we don't have to do any complex, you know, prompting literally just type to it
[05:03] as if it's your employee. And then it's going to go ahead and set this up,
[05:07] look through its skills and make sure that you get this message in your inbox or
[05:10] through your messages every single day. And great. Now we have daily morning equity
[05:14] briefings every single day. So again, this is going to be sent to you directly to telegram.
[05:18] And then because there's persistent memory, you can ask about any message you've ever
[05:22] sent it. So if we're curious about, you know, insider reads on specific
[05:26] positions that we hold, we can literally type how is the insider activity
[05:31] in Nokia for the past five days, and then it's going to go ahead, search the web,
[05:37] go through all the filings, look through documents and then give you back all this
[05:40] information neatly. So here we have all the insider activity as of the past five days.
[05:45] So it actually went through, you know, the foreign filings on the internet
[05:49] documents as well. So we have the strict past five calendar day information.
[05:54] So it seems like we have some insider transactions from a senior manager
[05:57] on May 26. If we scroll down, we also have a second filing another senior manager.
[06:02] So we're able to see basically, you know, all the information we could ever want in
[06:05] terms of research on specific holdings that we have. And then now just to give you
[06:09] some more examples, if you wanted actual trade ideas, you would obviously feed
[06:14] it your trading strategies and styles that you prefer. Assuming that it does
[06:17] know all this context about you, you can simply just ask, you know,
[06:20] super simple questions like scan for new long opportunities based on today's data.
[06:27] So after it's Gandy universe, it basically gave us a list of picks based on, you know,
[06:31] our specific strategies and what we like. So first we have the macro gates,
[06:34] make sure that the macro market does align with our thesis before we even start.
[06:38] And then we have specific picks like pull all to networks. We have, you know,
[06:42] insider transactions, momentum, IV rank. And then it is giving us IV figures because it
[06:47] knows that we trade options on this account. So we have things like bull cases, bear cases,
[06:52] any upcoming catalysts. And then if you scroll down again, data dog, we have Dell as well.
[06:58] And then as kind of like a cherry on top, we have the most attractive for a new long
[07:02] and things to avoid chasing just because Dell is a bit overextended after, you know,
[07:06] last Friday's price action. So if we want to go a bit deeper, we can say that we like
[07:10] the data dog setup and to run pre-trade checks and execute if it passes.
[07:14] And then now what we have is the pre-trade checks. Obviously today's Sunday,
[07:18] so we don't have live market data. It's taking the information from last Friday,
[07:21] but we have the current price, the day moves, VIX, and then also the momentum,
[07:26] making sure that this passes. Again, this is all based on context that we've provided before.
[07:31] We have insider activity, you know, any upcoming catalysts. And then we also have a suggested
[07:35] trade ticket as well. So based on our 200K portfolio, we have the starter size, shares,
[07:40] approximate, and then if we wanted to, we can also add stop losses and tree exit points,
[07:45] everything that you would potentially want or need. So as you can see, Hermes is super powerful.
[07:51] Sky is basically the limit as to how you want to use it. You can have it just essentially help
[07:55] you research, you know, automate morning briefings for you. So that's more of a passive role, I would
[08:01] say. Or you can go all the way and just have Hermes basically act as your actual trade analyst,
[08:06] assuming that you give it all your parameters, your risk, tolerance, things of that sort.
[08:10] So this way it's going to be able to work with you. And you don't have to go through
[08:14] the headaches of building out an extremely robust system in an IDE that you would with
[08:18] Claude code. Now before I show you how to set up Hermes agent yourself, if you want to learn how to
[08:22] build complex trading systems with AI agents like Hermes, Claude code, or any other new AI tool,
[08:28] make sure to click the link in the description for my school community. It's currently the largest
[08:33] AI focused trading community with full and depth guides and hundreds of members in there right
[08:38] now building AI trading systems across stocks, crypto options, and any other asset class.
[08:44] And if you already have an idea of what specific trading systems you want built,
[08:48] I offer one to one custom consulting work in my website in the description at AI pathways.io.
[08:54] So now that you know how Hermes works inside a trading context, let me now go over the two
[08:57] main components to actually get the setup. Now to start, we have features of Hermes,
[09:02] which itself is the free open source AI agent framework built by news research.
[09:07] The main things that make it super useful for us for trading is persistent memory.
[09:11] It's going to remember everything that you guys discuss over days, weeks and months.
[09:15] Apart from persistent memory, it also has the built in scheduler. So this is where it can actually,
[09:19] you know, automate for you. As long as you tell it that you want certain things to be sent or
[09:24] done every single day or every single hour, it's able to set up those cron jobs. And then
[09:28] finally there's the self learning loop where it actually builds new skills based on all the
[09:32] things you have it to do and it improves over time. This is where Hermes really shines
[09:37] since it's able to self learn, understand what you like and become better essentially over time.
[09:42] Now to add the AI connection to Hermes, you can use one of three options. So you first have
[09:48] the chat GBT codec subscription. So this is just a regular chat GBT subscription,
[09:54] which is about give or take $20 a month to get a lot of usage out of Hermes without
[09:59] paying per message. Now, if you don't have a chat GBT account or you don't want to use it,
[10:03] you can also use Claude, which is going to be a tiny bit more powerful.
[10:06] And if you have any other preferences, you can use open router or any other LLM directly
[10:10] via API as well. Now, once you get the AI connection, which is basically the intelligence
[10:15] all set up, you would then have the messaging platform. So this is where you can connect to
[10:20] telegram, discord, Slack, basically any messaging platform. So this way you can interact with
[10:26] it on your phone from your computer basically anywhere. And this is going to be the main
[10:30] communication method and how you conversate with your Hermes agent and how it talks back
[10:33] to you. Now let's go over how to actually run Hermes since these are all pretty straightforward.
[10:39] But when you want to run Hermes, you have basically two main options. The first is a
[10:43] local computer and the second is a VPS. But I would highly recommend using a VPS here
[10:49] since you won't need a dedicated Mac open running 24 seven like you see people do with Mac minis.
[10:54] It gets pretty expensive if you want to buy your own computer just to run Hermes.
[10:59] But with a VPS, it can run, you know, regardless of what your computer is doing,
[11:03] you don't need a second one. And this is especially important for trading as you'll
[11:07] have the AI agent run scheduled pipeline fires, you know, every evening, you have alerts fired
[11:13] during market hours, the agents always available on telegram. So nothing really depends on your
[11:17] laptop being open. And then whether you use your local computer or VPS like hostenger, you'll have
[11:22] you know, data privacy, so all your API keys or broker credentials, portfolio data.
[11:27] And just as a final tidbit, you can actually run multiple agents at once.
[11:31] So if you want, you can set up like, you know, five Hermes agents and they all do something different.
[11:36] In my example, I just had one main agent, but I find that Hermes works best
[11:40] if you have the means to separate out your specific tasks. So like you can have a trader,
[11:44] Hermes agent, a researcher, Hermes agent, another one can be just like a morning brief
[11:48] agent. So if you have all these separated chats with all these different Hermes agents,
[11:52] they can all excel at that one very specific task that they're assigned to. So theoretically,
[11:56] you can have like five employees working for you that are all doing different trading
[12:00] contexts for you. Now let's go over how to actually set up Hermes agent.
[12:03] The best way to do this and the easiest is to use hostenger because they do have a one-click
[12:07] deploy, which makes it super simple to set up. So what you'd want to do is go to the link in
[12:11] the description for hostenger.com slash AI pathways to get directed straight to this page,
[12:16] where you can deploy Hermes agent in one click. Then what you'll need to do is choose a plan.
[12:20] So if you scroll down, you can see we have KVM one, two, four and eight.
[12:24] Now I would probably recommend KVM two, depending on, you know, your own usage.
[12:29] These have different Rams, CPU cores and bandwidth, but I found that KVM two works perfectly,
[12:34] even if you are running, you know, say a few Hermes agents all doing different things,
[12:38] they should have the bandwidth to support pretty much any tasks that you would need.
[12:42] So go ahead and click choose plan. And then on this page here, what you would first need to do
[12:45] is choose the period. So this is how long you want to use your VPS. So there's one month,
[12:50] 12 month and 24 months. Now 12 and 24 months do have the best value. So I'd probably recommend
[12:55] one of those two. This way you'll have your VPS server running pretty much for the whole year,
[12:59] especially if you know that you're going to be using this Hermes agent pretty regularly.
[13:03] And the other benefit to using a 12 or 24 month plan is that I have a coupon code for 10% off.
[13:08] So if you just go ahead and type in AI pathways and click apply, you'll basically have 10% off
[13:13] for your host and your VPS and have it running for basically the whole year.
[13:17] Next, what you'll need to do is just go ahead and click continue and then create an account
[13:21] and register all your information. Next, after going through the setup,
[13:24] it's going to automatically take you to the Hermes agent configuration,
[13:26] where it's going to create the template for you. So it's going to give you the admin username,
[13:30] which is always the same Hermes, but make sure to save this password here as this is how you
[13:34] actually log in to your Hermes terminal. So you can click show and then copy and paste this
[13:39] somewhere inside your computer. Then after that, just go ahead and click deploy and it's going
[13:43] to set up everything for you. So first it's going to set up your VPS, which is going to
[13:46] take around five minutes and then automatically set up Hermes as well. Next, it's just going
[13:51] to ask you some questions about your VPS needs. If it's your first time managing a VPS,
[13:55] if you're experienced, I would probably skip this step. But if you do want to know more about
[13:59] managing a VPS, what you can use host manager for apart from Hermes, like you can also use it to
[14:03] host, you know, NADN, web apps, things of that sort. Then you can go ahead and click into this,
[14:08] but I'll go ahead and skip all of this since we're here for Hermes. And then again,
[14:12] because you use the hostinger.com slash AI pathways link, it's going to automatically
[14:16] create this Hermes project for you. You don't need to do anything. All you need to do is
[14:21] sit back and wait for your project to be deployed. Now, after 10 minutes or so, you
[14:24] should see this Hermes agent running, which means you can now open it, log in and basically
[14:29] configure and set up your Hermes agent yourself. But if you don't see this Hermes agent
[14:33] automatically set up for you, you can also find it in the catalog. So go ahead and click
[14:37] catalog, find the Hermes template, select this, and then now you can click deploy
[14:42] with the new password. And this is also helpful if for some reason you forgot your
[14:46] password to log into the first one you made. But again, if you use my link,
[14:50] then this should automatically all set up for you. This is where you would find it,
[14:53] though, if you ever need to create a second Hermes agent or you lost your password,
[14:56] or you never had it to begin with. So heading back here, what you need to do now is go
[15:00] ahead and open the Hermes agent. So this way you can start configuring it.
[15:03] Now for the username, just type in Hermes and then for the password,
[15:06] again, this is the one that you copy and pasted from when we initially set up hostinger.
[15:10] So now go ahead and click sign in and you should be taken to the terminal.
[15:14] Just give it a second. And then now you can do either a quick setup or full setup to
[15:18] configure everything. Now, because we're using our Hermes for trading,
[15:21] you don't need to do full setup for almost everything unless you want to go deep into the weeds.
[15:26] So go ahead and click a quick setup, type enter, then it's going to ask you which AI
[15:30] provider you want to connect to. Now, like I mentioned earlier, I would recommend Open AI
[15:34] Codex just because you can use your monthly subscription. It's not API based. So as long
[15:39] as, you know, it fits within your plan, then you don't need to pay anything on top.
[15:43] So here I'm just going to go ahead, click enter on Open AI Codex. And then what you need to
[15:47] do is open this URL inside your browser. Then after you paste this code here, it should say log
[15:52] and successful. And then this is where you can select your default model. Now this is the model
[15:56] that is basically going to be connected to your Hermes agent. So if you want to use GPT 5.5,
[16:01] which is the most powerful, you can select that. Just know that you're going to hit use
[16:05] such limits a bit quicker if you use 5.5 versus something like 5.4. But I'm just going to
[16:10] do a 5.5 for the latest and greatest. Then for the terminal backend, we're just going to
[16:14] keep this the exact same. So keep current local. Then it's going to ask you to set up messaging.
[16:19] So this is where you're going to configure either Telegram, Discord, iMessage or anything else.
[16:23] So go ahead and click set up. And then for the platforms to configure, you can see
[16:27] all the different ways that you can basically connect to Hermes agent. But I'm just going
[16:32] to use Telegram here and show you guys how to set that up. So click space on Telegram,
[16:35] then click enter. Then we can see here that we need to create a bot via at bot
[16:40] father on Telegram. So this is super simple. What you need to do is go to Telegram.
[16:44] Then on Telegram, what you want to do is search up a bot father.
[16:48] Once you're on the bot father chat, click slash new bots,
[16:52] then it's going to ask you for a name. So you can call this like Hermes.
[16:55] And then for the username of the bot, I'll do the exact same thing. And then now we have
[17:00] our Hermes bot basically created. Then all we need to do is copy the token. So go ahead
[17:04] and click this to copy. And then heading back here, what you need to do is paste it,
[17:09] click enter. And then now all it needs is your user ID as well. So it tells you right here how
[17:14] to get your user ID. You just message user info bot on Telegram and then it'll give you your user
[17:19] information. So go ahead and copy this. And then on Telegram, we're just inside this get info
[17:24] bot. So if you just click slash start. So next all you want to do is paste in your ID,
[17:28] click enter. Then it'll ask you if you want to set this as your home channel,
[17:32] simply click yes. And now you're pretty much ready to go. So if you ever want to see all
[17:36] the documentation capabilities of Hermes, just go ahead and reconnect to the server.
[17:41] And you'll be able to see all the information ranging from available tools, available skills.
[17:46] If you want to get any additional information on MCPs, how to connect to GitHub,
[17:51] how to use computer use, it's basically all right here. You would just simply type in the command
[17:54] to get more information. But now what we care about obviously is setting up the Telegram messaging
[18:00] and being able to essentially connect with Hermes back and forth. So here we can type directly
[18:04] to the Hermes agent. I'm just telling it to set up Telegram messaging and ensure the connection works.
[18:09] So we can wait for it to initialize the agent and basically connect what we have here to Telegram.
[18:14] So just like plot code, it's going to go through your skills, make a plan for you,
[18:18] and then perform this action. So now we can see that Telegram messaging is set up and verified.
[18:23] So theoretically, we don't need to chat with Hermes here inside the terminal anymore. We can
[18:27] just simply go straight to Telegram and talk to it. So let's open up Telegram. And here we
[18:31] can see the Hermes connection test works, have the bear home test, everything looks like it's
[18:36] up and running. And then one way that we'll know this is actually working is just simply type in
[18:41] my Hermes. We can see that it's typing now. So this way it's going to be able to communicate
[18:46] back and forth with us. Now, if you're setting this up for the first time, I would recommend
[18:50] that you now start feeding it, you know, all the context around you as a person,
[18:54] how you like to create what you're currently trading, what your positions are,
[18:58] connecting any external accounts that you want to. So this way Hermes at least has all this
[19:02] background context before you set up any crown jobs. So here's a very simple example. I'm just typing
[19:07] in that I'm a swing trader that also likes to use a wheel strategy for options. Typically like
[19:12] to trade when VIX is below 20 and then my current positions are these separate tickers.
[19:16] Then we want Hermes to basically act as a personal training assistant that gives ideas,
[19:20] entries, market briefs, intelligent theses. And then we want to make sure that all
[19:24] market data is always updated when providing outputs. But obviously if you're working with
[19:28] Hermes, it needs to be a lot more detailed, right? You can even give all your past trades,
[19:33] things of that sort. This way it'll know exactly what you want and how to work with it,
[19:37] which is way better than having a blank slate. But I'm just go ahead and type this in just so it
[19:41] has at least some context around how we're going to be using the spot. So here we can see this
[19:46] is where the persistent memory comes in. It's going to remember everything we ever tell it.
[19:50] Then this is where you're going to be able to build on top of it, you know, add
[19:53] any scheduled actions like cron jobs if you want to get reports, trade ideas, signals every
[19:59] single day, things of that sort. Basically the sky's your limit as to how you want to use this
[20:03] Hermes agent to basically help you in your own trading endeavors. Now, if you've found this video
[20:08] helpful, make sure to like, comment and subscribe as it greatly helps out the channel. I cover
[20:13] everything regarding AI trading and how you can best use AI in your own portfolios, trading styles
[20:18] and strategies. And like I mentioned in the beginning of the video, if you do want to
[20:21] join the largest AI trading community, make sure to click the link in the description.
[20:25] We have full in depth guides, templates and systems for all of our members to use,
[20:30] as well as weekly calls, just to make sure that everyone has the latest and greatest
[20:33] information around using AI and how it can genuinely help you become a better trader.
