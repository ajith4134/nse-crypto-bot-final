# Transcript

language: en (p=1.00)

[00:00] A pretty crazy question that no one has asked before is can you predict the stock market?
[00:04] This is sort of a really unique question you know and I think I might be the first person
[00:08] to ask it and in fact I think that me asking this question is probably the first time that
[00:14] I made an AI that can predict the stock market. Last time we figured out that patterns really
[00:22] do show up in stock charts and it's because of math not psychology and what we found is that most
[00:28] of what we call patterns can be reduced to simple resistance lines and I'm going to use AI to start
[00:34] predicting this now. So yes psychology affects the market and makes it go up and down but the patterns
[00:40] have nothing to do with say everyone seeing a head and shoulders beginning to form and then
[00:44] everyone decides to sell causing a self-fulfilling prophecy. I mean that's a really ridiculous
[00:50] theory anyway because that would imply that everyone would have to know about how patterns
[00:54] work in order to begin trading begging the question of where the first pattern came from.
[01:00] It's the chicken and the egg question but which came first the pattern or the trader. Clearly
[01:06] patterns themselves are a quirk of how orders get filled on exchanges like say Binance or
[01:12] Robinhood and in short patterns form because there is an issue with the order book also
[01:17] known as a gap. Let's say I'm trying to buy carrots so I can look like an extra intimidating
[01:22] saber-toothed tiger when I bully my younger brother for his lunch money and the cheapest I can get carrots
[01:27] is $2.50 but someone else just bought it for $2.10 so I'm getting scammed. There is a huge gap
[01:34] between what I want and what is available. So patterns form because of how orders are placed
[01:40] in the order book and when there are large gaps price will fill these gaps. You can basically
[01:49] reduce any trading pattern into a matter of blocks and gaps and the more efficient the market the less
[01:55] that patterns will appear. It's basically a short-term issue with the order book not having
[02:00] enough liquidity. Now most of this isn't super important I go into more detail on this on my
[02:05] Crafer crypto channel so check it out if you're interested but basically if we know that patterns
[02:10] are formed as a result of the order book the most important question then isn't really about
[02:15] predicting the stock market going up or down as a whole like is today going to be a green day or a
[02:21] red day. I mean there are a lot of different psychological factors that can influence price
[02:27] on the long-term scale you know good economy bad economy red economy blue economy Powell says
[02:33] up Powell says down thank you can win then you're a clown. Sorry I don't know what came over me
[02:40] there but if we want any hope of predicting stock or crypto prices we need the least psychology possible
[02:46] what we need is something somewhere that can create these gaps without the psychology so how do we get
[02:55] that? How do you get the idea? To hammer the point home a little bit more I was talking to a
[02:59] quantrator about whether firms use AI in their trading systems and he said of course they do
[03:05] however they only use AI on the shorter time frames because the further you zoom out the more
[03:10] that psychology has an effect on the market in other words I'm not the first person to come
[03:16] up with this idea but I am the first person to make a market simulation based purely on math
[03:22] that creates trading patterns and in the last video we created a full-on market that completely
[03:28] generates charts using no psychology and it has plenty of gaps and patterns so I guess that means
[03:36] that we should and then they started cheating uh here let me back up for centuries people and
[03:44] youtubers have made neural networks to perform all sorts of activities from playing snake
[03:50] to playing snake to playing tetris to playing snake you can do many things with AI including
[03:58] playing snake I figured that our best bet with our bitcoin trading AI plan here was to investigate
[04:04] neural network AIs essentially how AIs work is that you input a bunch of random numbers they do
[04:10] some voodoo magic in the middle and then they spit out a bunch of random numbers and then you
[04:14] basically just do that for a long time and then you get this the point is that you can train
[04:19] an AI to do literally anything at all as long as it has numbers you can make an AI to do it
[04:27] I'm seriously not kidding this is literally how basic all AI training is that's why so many
[04:32] companies right now are making AIs that can basically do anything from generating audio to
[04:37] math to full-on video games what even is this so since trading and flappy bird pretty much
[04:47] both take the same amount of brain power to do we should be able to just hook up an AI to my
[04:52] market simulation and see how it does I've gone ahead and set up an AI in my market simulation
[04:56] and we're going to see how it does I've written up a little something called a genetic algorithm
[05:00] how it works is basically it spawns a whole bunch of copies of the AI with slight variations and
[05:06] then we'll pick the top 10 performers and they'll be allowed to breed and have offspring and then
[05:10] the rest are killed off um yeah and then those 10 go on to create a new population of genetic
[05:17] offspring and then the best from that generation go on and you know and you get the idea okay but
[05:22] first we got to figure out how to make a neural network neural networks are split into different
[05:27] layers they have an input layer where we stick our data into so our simulation data and then it
[05:33] calculates a bunch of functions and then outputs a bunch of numbers which will be its prediction
[05:40] we've got a lot of information available here so we'll input the entire chart for the past
[05:44] 150 bars or so uh we have the order book as well so we can throw that in there and then since we're
[05:51] only interested in whether the bot can make money I've just made the output either buy or sell or it
[05:57] does nothing this is just a simple one for buy negative one for sell and zero for nothing and
[06:03] then we just throw a whole bunch of bots in there and see what they do I've written up a
[06:07] quick graph to keep track of each generation and it just tracks their P and L throughout the
[06:12] cycle that's trader lingo for profit and loss hmm profit and profit and the idea with a genetic
[06:19] algorithm is that even if all the bots just do random stuff some of them will randomly make
[06:25] money and then we'll selectively breed those special bots and this is how they did after
[06:31] about a hundred generations they actually looked like they were doing pretty good uh and then I
[06:36] realized something I was only tracking their realized P and L so whenever you open a trade
[06:42] you have an amount that you could earn but it doesn't belong to you yet it's like an IOU
[06:48] if you have chips at a poker table unless you cash those chips in you can't get your money
[06:54] but the difference with P and L is that you can also amass losing chips which is basically just
[07:01] negative money which basically means if you just never close a losing trade it just looks like you
[07:08] never lost so the graph just only shows one half of traders that made money while hiding the other
[07:14] losing half the bots basically learned to hide their losses yeah okay so these are a bunch of
[07:22] awful bots that can't trade and it's not even really the bots fault either it's the genetic
[07:27] algorithm technically a genetic algorithm is based on the theory of evolution so the network
[07:32] only evolves once every generation which has to go through a process of mutations in order to get
[07:38] smarter and as you can imagine this would take millions of years genetic algorithms are just
[07:45] not a very efficient way of making ai's you also waste a ton of time on about 200 ai's that will
[07:51] just die in the next round anyway so this is pretty much a horrible way of making an ai well
[07:56] and given that we have a whole bunch of cheaters now who can't even trade uh we've got to try
[08:01] something different since we know that we can do something with neural networks it's time to try
[08:07] something more interesting aha we're booting up python uh i hate python ah hypothetically
[08:15] let's just say hypothetically that you set up a jupiter notebook and spend hours upon hours
[08:19] coding up acaras python ai using real bitcoin data gathered from the past four months of data
[08:25] on the one minute time frame with about 50 000 lines of data well purely hypothetically you might just
[08:31] be able to then write a script to check how accurate the model is over time and then use hyper
[08:36] dimensional calculus to improve the model and then maybe just maybe you could set up a virtual
[08:42] environment to run the ai from a server so that you could access the api from a website and then
[08:47] see the results live at crefercrypto.com all right so what's going on here the cat 1.3 model
[08:55] is an ai that i made trained on about 51 7773 minutes of bitcoin price action which by the way
[09:04] is 35 complete days of one minute candle data and all that the model tries to guess is the
[09:10] close of exactly one candle that's a lot so let me explain genetic algorithms are not the
[09:16] only way of developing ai also unity is not a great place to code up ai in fact you'll see later on
[09:23] that many of the most famous ai models out there in the world are made using tools a lot like what's
[09:28] available on python specifically the keras tensorflow library is the toolbox that lets you design any
[09:33] sort of ai you want but the reason i'm using this now instead of a genetic algorithm is because
[09:38] it actually trains ai's faster the difference between the two is that a genetic algorithm
[09:44] is more like playing plinko with 200 ai's hoping one of them randomly stumbles upon the correct answer
[09:50] while keras are actually machine learning is like having a textbook for a class and asking the ai
[09:56] to study for a test using it you only need one ai and one textbook and then it'll just grind
[10:02] out the world's fastest study session in the span of a few hours i do want to note that a genetic
[10:07] algorithm is great when you don't already have the correct answer because the ai's can solve
[10:11] problems in new or hard to explain ways like solving for walking or playing a video game but
[10:17] if i take a bitcoin price chart and cover up the right side and ask the ai to predict it there is
[10:23] technically a right answer and then the training algorithms are a little more complicated than
[10:27] you need to know about but you can think of it like fine-tuning a radio with a million different
[10:32] knobs trying to get it to output the right answer and after all of that after hours and hours of
[10:38] training really what we're doing with the cat 1.3 ai is predicting the close of one candle it predicts one
[10:47] price yep i'm using 17 megabytes of data to predict one number here's my thinking large language
[10:54] models like jim and i and chat gpt also only predict one number converted into a word in fact the
[11:01] famous chat gpt was trained on the internet so it remembers a lot of information when you
[11:06] ask it questions you feed it a series of words and it'll predict the next word in the sequence
[11:12] sort of but after one prediction is made the entire conversation gets fed back into chat gpt for the
[11:19] next prediction and so on that's why chat gpt sort of looks like it's typing when you talk to it
[11:25] it's predicting based off of its own predictions but here's the interesting part when you ask it
[11:31] about things it wasn't trained on ai models will still give answers using this sort of emergent
[11:38] reasoning that develops through the training process but what's even more crazy is that a lot
[11:43] of the time the things ai's will say actually make sense there is still active research into
[11:50] understanding how this emergent reasoning develops through training but it got me thinking
[11:55] what if i made a chat gpt of my own except instead of predicting the next word in a sequence
[12:01] it predicts the next bitcoin price we could predict as many future candles as we want
[12:10] if something like patterns really exist then a neural network will be able to pick up on these
[12:15] patterns in this form of emergent reasoning so let's get cracking chat gpt 3 used 70 billion
[12:22] neurons i can't run 70 billion neurons on my computer so i'll be making a model that uses
[12:27] 200 000 there and would you look at that this is the cat two point series i made running on test data
[12:35] this is data the model has never seen before and i want you to pay attention to these freeze frames
[12:40] surprisingly these predictions are not far off this data was pulled from just a couple days ago
[12:46] from live bitcoin data so there's no way the bot has ever seen this data before it hasn't been
[12:52] trained on it at all which means we did it we actually made an ai that learned something useful
[12:58] from the training uh oh what what is that blows my mind oh yeah uh okay yeah anyway if you want to
[13:07] see the rest of this video and other models i've made then check out my crayford crypto channel
[13:11] seriously check it out if you like crypto and stock market stuff but i do want to say a gpt
[13:16] predictive model isn't the only way of doing ai generation it happens to be easy which is why we
[13:22] have all this ai crap floating around right now but there is technically another type of neural
[13:27] network prediction known as a diffusion model it gets complicated but it has to do with refining
[13:33] the same guess over and over again until it's crystal clear and looks good enough i did not
[13:38] make a diffusion model because holy moly this was a lot of work already i will get around to it
[13:45] someday but for now i will be releasing the finished cap 1.3 and 1.4 models on my website
[13:52] they are not the most spectacular models in existence and i've already shown you how i made them and
[13:57] what they're capable of and if you want to mess around with them go ahead they are neural
[14:02] networks that learned something from the training process and i've tried to document a lot of that
[14:07] on the website i've coded up api so that you can interact with the predictions live
[14:11] and the generations roll in from the ai like chat gpt does now the website is subscription based
[14:17] because i have to host these models on a server and i have to pay big dollars so that my website
[14:22] doesn't break when hundreds of people are trying to use it all the time the models are
[14:26] quite big for a web server which is why i haven't been able to add the other models yet because
[14:30] they're even bigger in size and the cat 1.4 model alone has 33 million neurons so that's
[14:37] large but later down the road i will be releasing my two-point and three-point cat models i just
[14:46] have to get around to coding that if you want more of my stock market prediction videos price analysis
[14:52] crypto research go over to the crayford crypto channel this crayford channel will be mainly
[14:57] focused on various programming projects i have another video coming up for a crazy ai that i made
[15:02] that plays a game to make me money so if you're into stuff like that stick around here but i'll
[15:07] be doing an analysis video real soon on the crypto channel about the determinism of price
[15:12] action seeing whether you can actually find any probabilities based purely on charts and the
[15:17] order book and spoiler i did find some results you know and and there's just so much more i
[15:22] could say about this ai project as a whole and you know what i think i'll just keep talking
[15:27] oh would you look at that it's already over 10 minutes we can't be having a video that's too
[15:33] long what do i look like videos don't grow on trees oh look my next video it's almost ready
[15:41] join my patreon if you want to support me it'll help me make these videos full time and then i
[15:46] can quit my job at walmart the simulation game i made in my last video is available on there as
[15:52] well and any of my future projects will go there i'm actually pretty active on it so i'll respond
[15:57] to you if you have any questions make sure to join the discord there are tons of traders
[16:01] and developers on there we'll be collaborating more in the future so stick around and that's
[16:06] all i have so i'll see you next time thanks for watching bye
