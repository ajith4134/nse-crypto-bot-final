# Transcript

language: en (p=1.00)

[00:00] The holy grail for AI trading agents is having an agent that's able to learn from its mistakes
[00:06] and make improvements on the strategy, or with the vision of becoming more profitable.
[00:11] The thing is that most AIs that you interact with, they are very simple. You give a prompt,
[00:17] they give an output. But what we're going to do today is use an extremely powerful AI
[00:21] that automatically learns from all the engagements that you have with it. And I want
[00:25] to see if I can apply that self-learning behavior to a trading strategy. So instead of it being prompt
[00:31] outcome instead, we're going to produce a prompt that creates a strategy that creates an outcome it
[00:37] can learn from and therefore creates a new prompt to build into the strategy again. What we have
[00:42] is a self-improving trading agent. You're going to have it running 24-7 and I've even made it
[00:48] so you can just simply copy and paste one single prompt, put it into your AI and it will set this
[00:53] whole thing up for you. And the AI itself that we're using today is completely free. It does this
[00:58] self-teaching process, this self-improvement process for free. So right after you subscribe,
[01:04] let's get into it. Now I've been doing this a little while and I know that whenever you want
[01:09] to create a self-learning or a self-improving process with Claude for example, you have to
[01:15] describe how it's supposed to improve itself. And so it can get a little bit laborious,
[01:20] it's very boring and it's very frustrating because the AI doesn't quite understand it.
[01:24] However, there's a new tool that has come out over the last couple of months that's been really
[01:28] lingering in the background and today I've just seen the massive use case for it in trading and
[01:32] it's called Hermes agent. You might have heard of like Open Claw, this fully autonomous thing
[01:38] that's just took the world by storm. Well, Hermes in the background is being touted as even
[01:42] better than Open Claw because of this self-learning process. But Hermes agent on its own isn't
[01:47] going to do all the work. We actually have to put some smarts into this and this is what I do.
[01:51] I architect agents to do exactly the thing I want them to do and so there were four criteria that
[01:56] I came up with with regards to what makes a good trading agent and I came up with these four.
[02:03] So number one, it has to be accurate. Number two, it has to be reliable. Number three,
[02:07] it needs to have a very well-defined goal and number four, it needs to be self-improving.
[02:13] It needs to learn from its mistakes. Now let's first talk about the accuracy element
[02:17] because when I say accurate, I mean is the data that's coming in accurate in the first place?
[02:22] Are we able to take that information in reliably and consistently over time and when we feed that
[02:26] information to Hermes agent is the information actually accurate? Over the last couple of weeks,
[02:30] I tested every single AI that is in existence and I tested them on their ability to do trading
[02:36] and one of the most shocking results from that is the inaccuracy in the data. They're
[02:40] all supposed to be pulling information from the same place but some AIs just don't do it
[02:45] properly and so there is inherently an accuracy issue. So we need to make sure that that is resolved
[02:50] and we will resolve it in this build. So when we're trying to get accurate data through, we need to
[02:54] make sure that the API connections are very strong and reliable. We also need to make sure that if
[02:59] we're pulling in information from news feeds, for example, that that information is also
[03:03] accurate because the AI can sometimes interpret text in different ways. If you give the same
[03:08] article to multiple different agents, they might have different things to say in different
[03:12] conclusions. So we need to make sure that there are rules in place so that the conclusions are
[03:17] accurate and ideally accurate and objective and that brings me onto the reliability section.
[03:22] We need this agent to be reliable. So what do I mean by reliable? I would say that reliable is
[03:27] it's always operating 24 seven and even if our computer goes down or turns off or closes and
[03:33] it's still executing on the system that we're going to build today. We've also solved that
[03:37] issue in the one shot prompt. Now it's incredibly important that we move on to number three
[03:41] and that is that we have to make sure that the agent has a well defined goal.
[03:45] So let's talk about goals a little bit deeper because it will make all the sense in the world
[03:48] to you in just a second. So we need to define in terms of a goal, obviously there is a destination.
[03:53] Most people I'd say 90% of people right now, if you're creating a trading strategy, don't have a
[03:59] destination, don't have a definition of what achieving the goal actually looks like. And so
[04:03] in light of being thorough and actually accurate and actually having a good agent,
[04:07] so we need to define what is success and what is failure and it might sound a bit abstract,
[04:13] but in fact we need this information. What is success in the strategy? Is success making
[04:18] $10 a month? Is success making a million dollars a month? Obviously you have to
[04:22] operate in the in the realms of what's possible. An example of something that would be impossible
[04:26] would be like saying I want to make a million dollars a month and here's $10 to start with.
[04:31] So what is success? And the more details you can give here, the better. Like if you know
[04:35] anything about sharp scores, which is essentially a score that relates to the profitability of a
[04:41] trading strategy, you might want to put a specific sharp score into the agent as a goal.
[04:47] We want to work towards this goal because if you think about it, this agent is going to be
[04:51] doing a thing, getting feedback and then improving the thing to do it again. And it's going to
[04:55] do that over and over and over again until that goal is achieved. And so we need to
[04:59] define the goal. But we also need to determine what is failure? What does failure look like?
[05:04] So what the agent will be able to do in the end is almost like look at where it is in its
[05:09] current results and say, okay, anything in this direction is towards the goal and this is good
[05:14] and anything in the wrong direction away from the goal closer to failure is bad. And it's with
[05:20] that goal in mind that number four comes in and that is that it needs to be self-improving.
[05:26] So it needs to be able to assemble and organize information properly. It needs to learn from
[05:31] the outcomes. It needs to analyze the outcomes. Were they towards the goal or away from the goal?
[05:36] It then needs to form its own hypothesis about why the result was the way it was based on the
[05:42] information it had. And then it needs to make a second hypothesis about what it should do next.
[05:47] So then it should take that information and that learning apply it to a updated strategy.
[05:52] And this updated strategy I think should follow the scientific model, which if you don't know
[05:57] what the scientific method is, it's essentially changing only one variable and then seeing the
[06:02] outcome because if you change the load of variables and you went more profitable, you wouldn't know
[06:06] which variable was responsible for that trade going well. And so you only change one variable
[06:11] at a time and you run a series of tests. Every time you get one better, that is now the new
[06:15] baseline. And then you make iterations on that new baseline. And it needs to do this
[06:20] inherently. And so all four of those things make up what I think is a good agent.
[06:25] So now's the time that we're going to start creating this. I'm going to demo it for you
[06:28] from start to finish. The setup of this thing, the prompt, everything is completely free for
[06:33] you to use. I'm going to give you everything that you need to copy and paste and get this
[06:37] agent up and running with Hermes. Okay, so as always, every single prompt is freely available
[06:42] for you to copy and paste. And I hold them all in zero one systems. It's my own free
[06:47] community that you can join right now. The link is in the top line of the description
[06:51] and anytime I post any prompts in any future videos, the links and the prompts will all be
[06:57] in zero one systems. You'll come here to start with your click classroom at the top,
[07:00] then we're going to click this big YouTube button. This is for all the YouTube video
[07:03] prompts and you'll come across something titled something similar to this self
[07:08] improving trading agent Hermes self improving trading agent. The video will also be in
[07:12] here because you can see this is how I post it when it's live and we'll open that up
[07:16] and we're going to take this beautiful one shot prompt. It is so nice. And by the way,
[07:23] all of the one shot prompts that I give in my videos, they improve over time as
[07:27] well because we get feedback, people have certain issues and then we improve
[07:30] them. So the version that you're downloading right now or that you get
[07:33] in zero one systems will be the most up to date and the best one we've had
[07:36] so far and it's only getting better. It's so cool. Okay, so what we're going to do
[07:41] is we're going to come over to our terminal and this is me in my terminal.
[07:47] I'm just going to increase the size so you can see it. We're going to start a new
[07:50] session which I do with dangerously skip permissions because I'm an absolute
[07:57] savage. Okay, and then here we are. We're going to we're in Claude and we're
[08:02] just going to paste in our one shot prompt. So get ready because the journey
[08:07] begins for your self-learning, self-improving agent that's going to
[08:11] run on Hermes. So as we go through this process, we're
[08:14] going to do a series of phases which you'll see on the screen right now.
[08:18] So phase one was an environment check. What this does, it's really cool, is it
[08:21] makes sure it knows which system you're on. Are you on a Mac or on a Windows?
[08:26] And depending on which one you choose, then it will take you on a different
[08:28] journey because there's different instructions for both.
[08:31] So it said, okay, we can see that you're on a Mac and you've got no JS
[08:35] installed on Claude code. Great. Step two of seven in phase two,
[08:39] which is defining the strategy. We're going to build your trading strategy now,
[08:42] specifically what success and failures look like. The agent uses this
[08:46] file to score every trade. It's not just fives, it's just numbers.
[08:50] So we have to now decide which asset are we going to be trading. Now this is
[08:53] the moment where if you already have a strategy, you come down to number four
[08:57] and you actually would say something along the lines of this.
[09:00] Hey, I've actually already got a strategy and it's called the Waco alpha strategy.
[09:06] So could you look for that in my computer and, you know, use that
[09:10] as part of this system. Or alternatively, you could say, I don't have a strategy,
[09:15] can you just make me a basic one and it will make you a basic one.
[09:18] Like a basic solid one that everyone kind of starts with and then you can let the
[09:22] agent improve it over time rather than you. Alternatively, you can build the
[09:27] strategy in this system. The onboarding agent will work with
[09:30] you to create a strategy too. So you could choose Solana or
[09:34] USD or Ethereum or Bitcoin or any asset. But for now, I'm just going to say
[09:38] number four, I've actually already got a strategy. It's going to call in to my
[09:42] information about that strategy that I already have and it's going to build
[09:45] out my documentation based on that, which I think is so cool.
[09:48] So let's let this work for a little while. We're going to go onto
[09:51] phase three after it's found my Waco alpha strategy. You can see it
[09:56] actually has found it right here. And what's wonderful is I've created this
[09:59] strategy already and it's got over a million and a half data
[10:03] points that it's analyzed. I've been letting it run for like
[10:06] six to eight weeks, just learning from the information. And I did that all
[10:10] manually, like instructing how to learn this stuff. But the Hermes agent
[10:14] will just learn it itself. So it says what I'm seeing on the disc.
[10:18] I've got Waco alpha, the DTAL momentum and yield strategy.
[10:22] How do I how do you want me to incorporate Waco alpha into this
[10:24] Hermes deploy? Yeah, let's actually point it at this strategy.
[10:28] Like let's actually this is real money that's being traded, by the way. So
[10:31] maybe this is maybe a bit of a mistake, but by the way, you can see the
[10:34] progress of my 50,000 pounds to 500,000 pounds in a year
[10:38] challenge that I'm doing. I'll call it the 10x challenge.
[10:40] You can see that the dashboard is linked below. You can see my progress.
[10:43] The frustration is for me is that I haven't been able to put as much
[10:46] money in as I wanted to. I haven't had the dips in the market that I
[10:49] wanted to make my purchases. So that's kind of been a little bit
[10:52] difficult. Okay, so now it's actually pulled out the goals
[10:56] and it said the maximum return 30 days is this much 10x in six
[11:00] months, 40s. It's defining all my stuff. My
[11:03] minimum sharp score, my max drawdown, my failure below,
[11:06] reflection every certain amount of days. It's got all of this built in. So that's
[11:10] wonderful. And it says do you want to confirm the
[11:12] Hermes and Waco alpha setup? Yeah, so I'm going to have lock in as proposed.
[11:16] That's what I'm going to go for because this is actually real money.
[11:20] But I want you to know that I trust this system and the way that it learns
[11:24] sufficiently to put my real money on the line. That's what we're doing here and
[11:27] let's move on to the next phase. Okay, so phase three is now
[11:30] scaffolding the Hermes side state. So scaffolding all the
[11:34] folders and files to be properly analysed by Hermes when we actually come
[11:40] to install Hermes. Okay, now we're on phase four
[11:42] which has skipped actually because the Waco alpha is already deployed. If you
[11:46] hadn't got a strategy already it would start to deploy that strategy
[11:49] to make it live. You might have to connect in like APIs or whatever to make it
[11:53] trade for you. But I've got a video on how to actually
[11:56] make things trade. It's like Claude code with trading
[11:58] view that actually trades. You can also find that in zero one
[12:01] systems by the way, the whole prompt for that is there. So I'm having a little
[12:04] bit of an issue logging into railway which is going to be the place where
[12:07] we host this 24 seven so it can run regardless of whether the
[12:11] computer's on or not. It's saying it can't run
[12:14] interactive logins from inside this session. Please run this
[12:17] in the prompt yourself. So all I'm going to do is going to come over here
[12:20] in my cursor, split this terminal so I can start a new terminal session
[12:25] and I'm just pasting in this. So I'm going to paste that in. It should then
[12:28] open up railway for me to get me to log in and it's a success so I can close
[12:33] the page. Boom that's done. I can now close that
[12:36] and I'm now logged in so I can say done continuing.
[12:39] I love these one-shot prompts because I built them so that opens up these
[12:43] browsers for you. So if you don't have a railway account by the way
[12:47] what would have happened just then is that it would have opened up railway and
[12:50] you just make an account and then you come back and say hey I've
[12:53] just made an account and it's free for so much usage.
[12:56] I've only just now started having to pay for railway because
[12:59] I've got like 50 projects on there running 24 seven.
[13:02] So it's now using the CLI it's called
[13:06] to integrate with railway so anytime you publish a new strategy
[13:10] or you make a change it will update on the 24 seven server
[13:14] and just that's it just kind of works like that. So that's what's great about
[13:17] railway because it works in this way with your terminal.
[13:20] Any project that you're doing is just kind of updating. It's now just seen
[13:24] 24 gain trades and 22 loss trades and it's converting those into a
[13:29] Hermes readable ledger so it's now converting everything to be
[13:33] perfectly primed and ready for Hermes to take a look at it.
[13:37] Something else has just happened here. Oh yes these new documents have just
[13:40] come up. Sorry about my desktop. Let's hide all the clutter. So my strategy
[13:44] document has now been populated. It's also opening them in my
[13:48] cursor as well. That's really helpful. It's got my strategy. This is my strategy.
[13:52] The maximum amount of positions I'm going to hold is 12. My slippage
[13:56] tolerance is this. My gas reserve is this. The score awaits everything. This is
[13:59] all pulled from my actual strategy. It's also defined my goals right.
[14:03] My target return over 30 days is 4.7
[14:07] which is 47% by the way. That's my target return for every 30 days.
[14:12] So it's going to be working until it achieves these goals. These are all the
[14:15] trades that have taken place as well. How cool is that? So it's just
[14:18] organizing all these files now so Hermes can have a look at it and
[14:22] learn from it. So right now we're in the handoff to
[14:24] Hermes phase like just like that. So I hope if you're following along
[14:27] I think it's about time to subscribe don't you? Anyway.
[14:31] So it's basically looking at it's oh my goodness it already installed Hermes.
[14:36] It already did it. It already installed Hermes. That is insane
[14:40] actually. I didn't realize that would just happen so quickly.
[14:43] Okay so Hermes is now being installed. I can now type in Hermes
[14:47] in this terminal or any other terminal. So let's go over to the split terminal
[14:52] again and I'm just going to type Hermes in here just to see
[14:54] if it is in fact. I can't because I can't quite believe that it did install.
[14:58] It did and now I fully have Hermes just up and running. That was just so quick.
[15:02] We could do a whole video on Hermes by the way. It's unbelievable
[15:05] but what it's done right now is it has outlined everything that it's doing.
[15:09] So now that we know Hermes is actually installed we can come back to that later.
[15:12] So let's have a look at everything. So final confirmation.
[15:16] We have a self-improving trading agent which is deployed right now
[15:19] and adapted for my Waco Alpha strategy which trades real money by the way.
[15:23] It's working on Railway 24-7 and its strategy is using the bit tensor subnets.
[15:29] We're looking for that return. We're looking for that as a max drawdown
[15:33] minimum sharp of one. The brain is Hermes. It's going to be watching
[15:36] the live service and weekly cadence. Hermes owns the portfolio mechanics
[15:40] and scorer weights and Cornelius who's another agent of mine
[15:43] owns the filter thresholds. The first cycle is read only and review only.
[15:47] It's going to flip the strategy.yml mode to live when it's ready.
[15:52] So it's actually not trading yet and when it's ready
[15:55] Hermes will decide it's time to go baby and then we'll start making some money.
[15:59] Okay so what happens from here? My strategy will keep firing every 30 minutes
[16:03] on Railway which it does already. It does a daily reshuffle and a 30-minute
[16:06] reshuffle. Cornelius my other agent is going to keep
[16:10] tuning the learned parameters JSON every week. That means he's like
[16:14] looking at all the data that comes in those one and a half million data points
[16:17] that we have right now and kind of learning from those.
[16:19] So I bet Cornelius and Hermes now are just kind of together.
[16:22] Hermes reviews the trades weekly but he has a three day offset from Cornelius.
[16:26] Interesting. The first Hermes cycle will produce
[16:28] a markdown review with no actual writing. I will approve by setting mode
[16:33] so I can come here and just like approve the strategy from there
[16:36] and a day after check-in I can do any of the check-ins that I want using these
[16:40] commands. To go live not today is to edit the
[16:43] Hermes trading strategy and Hermes will start writing on the next
[16:47] weekly cycle. Hermes is watching close this terminal the agent is running.
[16:51] Kablam kaboom there we go. What about that then?
[16:57] So cool! Okay so I really want to hear your stories
[17:01] about this when you've installed. The best place to come and do that is to
[17:04] come into the classroom there's another person that's joined who's actually
[17:07] taken on the 60-day challenge. Come into the YouTube video prompts
[17:10] take your prompt here come over to the community once you've done it and
[17:13] tell us all about it how cool it was and that it that it works wonderfully.
[17:17] The response of the last video regarding the Markov method strategy
[17:25] people have absolutely you can see like no one has any issues with this thing they
[17:30] loved it and they're using it and people are very excited about it but let's see
[17:33] the response of this one so we'll have a similar post like that on the community
[17:36] when you come in. Anyway I want to thank you for being here
[17:39] this is so much fun right click like and if you can
[17:43] is actually a capability of you to do something called a hype so if you've
[17:46] got this far in the video hype the video on it on the phone you can kind
[17:49] of like scroll across if you click like the hype
[17:52] button will appear below I think it really helps viewership so
[17:55] give it a go you can also hype on a computer but I don't know where it is
[17:58] so anyway that's all have fun with it bye
